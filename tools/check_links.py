#!/usr/bin/env python3
"""Check every track's Dropbox audio link and report dead ones.

Used by the weekly maintenance GitHub Action, and runnable locally:
    python3 tools/check_links.py

Exit code 0 = all links fine, 1 = dead links found (details on stdout as
a Markdown fragment suitable for a job summary or an issue body).
"""

import json
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "https://amfas-tracks.allmyfas.workers.dev"


def to_stream_url(url):
    parts = urllib.parse.urlsplit(url)
    netloc = parts.netloc.replace("www.dropbox.com", "dl.dropboxusercontent.com")
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "dl"]
    return urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, urllib.parse.urlencode(query), ""))


def check(track):
    req = urllib.request.Request(
        to_stream_url(track["audio"]), method="HEAD",
        headers={"User-Agent": "amfas-link-checker/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            return track, res.status, None
    except urllib.error.HTTPError as e:
        return track, e.code, None
    except Exception as e:  # noqa: BLE001
        return track, None, str(e)


def main():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "amfas-link-checker/1.0"})
    with urllib.request.urlopen(req, timeout=60) as res:
        tracks = [t for t in json.load(res)["tracks"] if t.get("audio")]

    dead = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for fut in as_completed([pool.submit(check, t) for t in tracks]):
            track, status, err = fut.result()
            if status is not None and status >= 400:
                dead.append((track, f"HTTP {status}"))
            elif err:
                dead.append((track, err))

    print(f"Checked {len(tracks)} audio links: "
          f"{len(tracks) - len(dead)} OK, {len(dead)} dead.")
    if not dead:
        return 0

    print("\n| Track | Problem | Link |")
    print("|---|---|---|")
    for track, why in sorted(dead, key=lambda d: (d[0].get("finalName") or d[0].get("title") or "")):
        name = track.get("finalName") or track.get("title") or track["id"]
        print(f"| {name} | {why} | {track['audio']} |")
    print("\nFix: regenerate the Dropbox share link and update the AUDIO "
          "column in Notion, then re-run the bake.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
