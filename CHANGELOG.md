# Changelog

All notable changes to the AMFAS Music Library site are documented here.
Versioning is semantic-ish: patch bump for bug fixes and tweaks, minor bump
for new features. The current version is declared in `index.html` (a
`<meta name="version">` tag and the footer) and in `README.md`.

## [2.1] - 2026-07-09

Bug-fix and performance release. No new features.

### Fixed
- Seeking while paused now updates the progress bar, waveform, and time
  display immediately (previously stale until play was pressed).
- Track-end handling: when a track ends with no other audible tracks in the
  current filter, the player no longer gets stuck showing a pause icon on
  dead audio; when it is the only audible track, it replays instead of
  silently pausing.
- Playback errors mid-track (e.g. a network drop) now reset the player UI
  in any state, not just while loading.
- Stale `canplay` handlers no longer accumulate when switching tracks
  rapidly or when a load errors out.
- Track titles, tags, and gear from Notion are now HTML-escaped, so names
  containing `&`, `<`, `>`, or quotes render correctly.
- Dropbox URL handling rewritten on the `URL` API: the `dl` query param is
  stripped/set correctly wherever it appears, and download links get
  `dl=1` even when the original share link has no `dl` param.
- Deep-link track hashes lengthened from 5 to 8 characters to avoid
  collisions; legacy 5-character links still resolve.
- Canonical URL metadata now points at musiclibrary.allmyfriendsaresynths.com
  (og:url, header link, new `rel="canonical"`, new meta description).
  README live-site link updated to match.

### Performance
- Waveform generation checks file size first (HEAD request) and skips files
  over 30MB, so a first play no longer re-downloads a large WAV twice in
  parallel. Generation is also deferred until playback has started.
- Search input is debounced (120ms) instead of rebuilding the grid on every
  keystroke.
- The YouTube embed lazy-loads instead of loading with the page.

## [2.0] - baseline (2026-07 and earlier)

Everything before the changelog existed: single-file static site on GitHub
Pages, live track data from Notion via a Cloudflare Worker, search, tag
filters, sorting, shuffle, favourites, audio previews with waveforms and a
mini player, keyboard shortcuts, deep links, copy link/credit buttons, and
the custom domain.
