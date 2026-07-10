#!/usr/bin/env python3
"""Generate analysis.json for the AMFAS Music Library.

For every track with audio, decodes the file (streamed through ffmpeg, nothing
saved to disk) and computes:

  bpm      tempo estimate (librosa beat tracker)
  key      musical key, e.g. "A minor" (Krumhansl-Schmuckler chroma profile)
  keyConf  0-1 confidence in the key estimate (margin over runner-up)
  lufs     integrated loudness (pyloudnorm; approximate - mono @ 22.05kHz)
  rms      mean RMS energy (raw; the site normalizes across the library)
  bright   mean spectral centroid in Hz (raw)
  sim      6 most sonically similar track ids (cosine over timbre/harmony/
           rhythm features, z-scored across the library)
  xy       2D map coordinates, 0-1 normalized (t-SNE over the same features)

Raw per-track feature vectors are cached in tools/features.json so incremental
runs only download/analyse NEW tracks; similarity and the map are recomputed
over the whole library every run (cheap once features exist).

Requirements: Python 3.9+, ffmpeg on PATH, and:
    pip install numpy scipy librosa pyloudnorm scikit-learn

Usage:
    python3 tools/generate_analysis.py             # incremental
    python3 tools/generate_analysis.py --force     # re-analyse everything
    python3 tools/generate_analysis.py --workers 6
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import librosa  # noqa: E402
import pyloudnorm  # noqa: E402

API_URL = "https://amfas-tracks.allmyfas.workers.dev"
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_PATH = os.path.join(ROOT, "analysis.json")
FEATURES_PATH = os.path.join(ROOT, "tools", "features.json")
SR = 22050
N_SIMILAR = 6

# Krumhansl-Schmuckler key profiles
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def to_stream_url(url):
    parts = urllib.parse.urlsplit(url)
    netloc = parts.netloc.replace("www.dropbox.com", "dl.dropboxusercontent.com")
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "dl"]
    return urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, urllib.parse.urlencode(query), ""))


def fetch_tracks():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "amfas-analysis-generator/1.0"})
    with urllib.request.urlopen(req, timeout=60) as res:
        data = json.load(res)
    if "error" in data:
        raise RuntimeError(f"API error: {data['error']}")
    return data["tracks"]


def decode(url):
    """Stream-decode audio to mono float32 at SR via ffmpeg."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", url, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
        timeout=900,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "ffmpeg produced no output")
    y = np.frombuffer(proc.stdout, dtype=np.float32)
    if y.size < SR:
        raise RuntimeError("decoded under one second of audio")
    return y


def estimate_key(chroma_mean):
    """Correlate averaged chroma against K-S profiles in all 24 keys."""
    scores = []
    for shift in range(12):
        rolled = np.roll(chroma_mean, -shift)
        for name, profile in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            r = np.corrcoef(rolled, profile)[0, 1]
            scores.append((r, f"{PITCHES[shift]} {name}"))
    scores.sort(reverse=True)
    best, second = scores[0], scores[1]
    conf = max(0.0, min(1.0, (best[0] - second[0]) * 5 + 0.3))
    return best[1], round(float(conf), 2)


def analyse(url):
    """Return (public_metrics, feature_vector) for one track."""
    y = decode(url)

    # Loudness (approximate: mono, 22.05kHz decode)
    meter = pyloudnorm.Meter(SR)
    try:
        lufs = float(meter.integrated_loudness(y.astype(np.float64)))
        if not np.isfinite(lufs):
            lufs = None
    except Exception:
        lufs = None

    # Tempo
    tempo = librosa.feature.tempo(y=y, sr=SR, aggregate=np.median)
    bpm = float(np.atleast_1d(tempo)[0])

    # Chroma / key
    chroma = librosa.feature.chroma_cqt(y=y, sr=SR)
    chroma_mean = chroma.mean(axis=1)
    key, key_conf = estimate_key(chroma_mean)

    # Timbre / energy / brightness
    mfcc = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=13)
    rms = librosa.feature.rms(y=y)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=SR)[0]
    onset = librosa.onset.onset_strength(y=y, sr=SR)

    metrics = {
        "bpm": round(bpm, 1),
        "key": key,
        "keyConf": key_conf,
        "lufs": round(lufs, 1) if lufs is not None else None,
        "rms": round(float(rms.mean()), 5),
        "bright": round(float(centroid.mean()), 1),
    }
    features = np.concatenate([
        mfcc.mean(axis=1), mfcc.std(axis=1),               # 26: timbre
        chroma_mean,                                        # 12: harmony
        [bpm, rms.mean(), rms.std(), centroid.mean(),
         centroid.std(), onset.mean(), onset.std()],        # 7: rhythm/energy
    ])
    return metrics, [round(float(v), 5) for v in features]


def compute_similarity_and_map(features_by_id):
    """Cosine top-N neighbours + t-SNE 2D layout over z-scored features."""
    from sklearn.manifold import TSNE

    ids = sorted(features_by_id)
    X = np.array([features_by_id[i] for i in ids], dtype=np.float64)
    mu, sigma = X.mean(axis=0), X.std(axis=0)
    sigma[sigma == 0] = 1.0
    Z = (X - mu) / sigma

    # Cosine similarity
    norms = np.linalg.norm(Z, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    U = Z / norms
    S = U @ U.T
    sim = {}
    for i, tid in enumerate(ids):
        order = np.argsort(-S[i])
        sim[tid] = [ids[j] for j in order if j != i][:N_SIMILAR]

    # 2D map
    n = len(ids)
    perplexity = max(5, min(30, (n - 1) // 3))
    xy = TSNE(n_components=2, perplexity=perplexity, init="pca",
              learning_rate="auto", random_state=42).fit_transform(Z)
    xy -= xy.min(axis=0)
    span = xy.max(axis=0)
    span[span == 0] = 1.0
    xy /= span
    coords = {tid: [round(float(x), 4), round(float(y), 4)] for tid, (x, y) in zip(ids, xy)}
    return sim, coords


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-analyse all tracks")
    parser.add_argument("--workers", type=int, default=4, help="parallel downloads (default 4)")
    args = parser.parse_args()

    metrics_by_id, features_by_id = {}, {}
    if not args.force:
        if os.path.exists(OUT_PATH):
            with open(OUT_PATH) as f:
                metrics_by_id = json.load(f)
        if os.path.exists(FEATURES_PATH):
            with open(FEATURES_PATH) as f:
                features_by_id = json.load(f)

    tracks = [t for t in fetch_tracks() if t.get("audio")]
    live_ids = {t["id"] for t in tracks}
    todo = [t for t in tracks if t["id"] not in features_by_id or t["id"] not in metrics_by_id]
    print(f"{len(tracks)} tracks with audio; {len(todo)} to analyse "
          f"({len(features_by_id)} cached)")

    failures = []
    if todo:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(analyse, to_stream_url(t["audio"])): t for t in todo}
            done = 0
            for fut in as_completed(futures):
                t = futures[fut]
                name = t.get("finalName") or t.get("title") or t["id"]
                done += 1
                try:
                    metrics, features = fut.result()
                    metrics_by_id[t["id"]] = metrics
                    features_by_id[t["id"]] = features
                    print(f"  [{done}/{len(todo)}] ok      {name}  "
                          f"({metrics['bpm']} bpm, {metrics['key']})")
                except Exception as e:  # noqa: BLE001
                    failures.append(name)
                    print(f"  [{done}/{len(todo)}] FAILED  {name}: {e}", file=sys.stderr)

    # Drop deleted tracks, then rebuild similarity + map over the full library
    metrics_by_id = {k: v for k, v in metrics_by_id.items() if k in live_ids}
    features_by_id = {k: v for k, v in features_by_id.items() if k in live_ids}

    if metrics_by_id:
        print("computing similarity + map layout...")
        shared = {k: features_by_id[k] for k in metrics_by_id if k in features_by_id}
        sim, coords = compute_similarity_and_map(shared)
        for tid in metrics_by_id:
            metrics_by_id[tid]["sim"] = sim.get(tid, [])
            metrics_by_id[tid]["xy"] = coords.get(tid)

    with open(OUT_PATH, "w") as f:
        json.dump(metrics_by_id, f, separators=(",", ":"))
    with open(FEATURES_PATH, "w") as f:
        json.dump(features_by_id, f, separators=(",", ":"))
    print(f"wrote {len(metrics_by_id)} entries to {os.path.basename(OUT_PATH)}")

    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
