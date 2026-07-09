#!/usr/bin/env python3
"""Generate waveforms.json for the AMFAS Music Library.

Fetches the track list from the Cloudflare Worker API, decodes each track's
audio (streamed straight from Dropbox through ffmpeg, nothing saved to disk),
and writes a JSON file mapping track id -> { d: duration_seconds,
w: [200 normalized peak points] }. The site and the embed widget read this
file so visitors get instant waveforms and durations with no client-side
audio decoding.

Requirements: Python 3.8+, ffmpeg on PATH (macOS: brew install ffmpeg).
No third-party Python packages needed.

Usage:
    python3 tools/generate_waveforms.py           # incremental: only new tracks
    python3 tools/generate_waveforms.py --force   # regenerate everything
    python3 tools/generate_waveforms.py --workers 8

Run this after adding new tracks (step 8 of the audio processing pipeline),
then commit the updated waveforms.json.
"""

import argparse
import array
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "https://amfas-tracks.allmyfas.workers.dev"
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "waveforms.json")
SAMPLES = 200          # points per waveform (matches the site's renderer)
DECODE_RATE = 8000     # Hz; plenty for peak extraction, keeps decode fast


def to_stream_url(url: str) -> str:
    """Convert a Dropbox share link to a direct-download URL."""
    parts = urllib.parse.urlsplit(url)
    netloc = parts.netloc.replace("www.dropbox.com", "dl.dropboxusercontent.com")
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "dl"]
    return urllib.parse.urlunsplit(
        (parts.scheme, netloc, parts.path, urllib.parse.urlencode(query), "")
    )


def fetch_tracks() -> list:
    req = urllib.request.Request(
        API_URL, headers={"User-Agent": "amfas-waveform-generator/1.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        data = json.load(res)
    if "error" in data:
        raise RuntimeError(f"API error: {data['error']}")
    return data["tracks"]


def analyse(url: str) -> dict:
    """Decode audio via ffmpeg and return duration + normalized peaks."""
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-i", url,
            "-ac", "1", "-ar", str(DECODE_RATE),
            "-f", "s16le", "-",
        ],
        capture_output=True,
        timeout=600,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "ffmpeg produced no output")

    pcm = array.array("h")
    pcm.frombytes(proc.stdout[: len(proc.stdout) - (len(proc.stdout) % 2)])
    n = len(pcm)
    if n == 0:
        raise RuntimeError("decoded zero samples")

    duration = n / DECODE_RATE
    block = max(1, n // SAMPLES)
    points = []
    for i in range(SAMPLES):
        start = i * block
        seg = pcm[start : start + block]
        if not seg:
            points.append(0.0)
            continue
        points.append(sum(abs(s) for s in seg) / len(seg))

    peak = max(points) or 1.0
    return {
        "d": round(duration, 1),
        "w": [round(p / peak, 3) for p in points],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="regenerate all tracks, not just new ones")
    parser.add_argument("--workers", type=int, default=4, help="parallel downloads (default 4)")
    args = parser.parse_args()

    existing = {}
    if os.path.exists(OUT_PATH) and not args.force:
        with open(OUT_PATH) as f:
            existing = json.load(f)

    tracks = [t for t in fetch_tracks() if t.get("audio")]
    todo = [t for t in tracks if t["id"] not in existing]
    print(f"{len(tracks)} tracks with audio; {len(todo)} to analyse "
          f"({len(existing)} already baked)")

    if not todo:
        return 0

    results = dict(existing)
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(analyse, to_stream_url(t["audio"])): t for t in todo
        }
        done = 0
        for fut in as_completed(futures):
            t = futures[fut]
            name = t.get("finalName") or t.get("title") or t["id"]
            done += 1
            try:
                results[t["id"]] = fut.result()
                print(f"  [{done}/{len(todo)}] ok      {name}")
            except Exception as e:  # noqa: BLE001 - report and continue
                failures.append(name)
                print(f"  [{done}/{len(todo)}] FAILED  {name}: {e}", file=sys.stderr)

    # Drop entries for tracks that no longer exist in the API
    live_ids = {t["id"] for t in tracks}
    results = {k: v for k, v in results.items() if k in live_ids}

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, separators=(",", ":"))
    print(f"wrote {len(results)} waveforms to {os.path.normpath(OUT_PATH)}")

    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
