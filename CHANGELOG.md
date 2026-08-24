# Changelog

All notable changes to the AMFAS Music Library site are documented here.
Versioning is semantic-ish: patch bump for bug fixes and tweaks, minor bump
for new features. The current version is declared in `index.html` (a
`<meta name="version">` tag and the footer) and in `README.md`.

## [2.4.0] - 2026-08-24

### Added
- Working title now shown on the card as a small "aka" line under the main
  title whenever a track has a Final Name set and it differs from the
  working title. The Final Name (the name of record) still overrides the
  working title everywhere it's used — card title, sort, search results
  order, "sounds like" suggestions, embed widget — this just keeps the
  working title visible for anyone who knows a track by its old name.

## [2.3.1] - 2026-07-10

### Changed
- Auto-detected BPM is no longer displayed anywhere (card badges, sort
  option, search, map tooltips/panel): beat tracking proved too unreliable
  on this material. The values remain in `analysis.json` as rough backend
  data and still feed the similarity fingerprints and the map layout.
  Key badges, energy sort, and key search remain.

## [2.3] - 2026-07-10

Feature release: the library learned what it sounds like.

### Added
- Audio analysis: `tools/generate_analysis.py` analyses every track (BPM,
  musical key + confidence, integrated loudness, RMS energy, brightness,
  and a 45-dim timbre/harmony/rhythm fingerprint) and bakes the results
  into `analysis.json`. 184 of 186 tracks analysed.
- BPM and key badges on every track card, "BPM: slow to fast" and
  "Energy: high to low" sort options, and search now matches musical keys
  ("A minor") and BPM ("120 bpm").
- Sound Map (`map.html`): the whole library as an explorable 2D map
  (t-SNE over the audio fingerprints) where similar-sounding tracks sit
  together. Pan/zoom, hover tooltips, click to preview, cyan links to the
  selected track's closest sonic neighbours. Linked from the controls bar.
- "Sounds like" suggestions: the more-like-this row now uses real audio
  similarity (cosine over the fingerprints), falling back to tag overlap
  for unanalysed tracks.
- Weekly maintenance GitHub Action (`.github/workflows/maintain.yml`):
  checks every Dropbox audio link (opens an issue if any are dead), bakes
  waveforms + analysis for new tracks, and commits the results. The site
  now maintains itself when tracks are added in Notion.
- Playwright test suite (`tests/site.spec.js`): 13 hermetic tests covering
  rendering, search, filters, sorting, playback, favourites, deep links,
  shareable state, the embed widget, and the sound map. Runs on every push
  via `.github/workflows/test.yml`.

## [2.2.1] - 2026-07-09

### Added
- "Back to top" button: appears bottom-right after scrolling down, smooth
  scrolls back up, and shifts up out of the way when the mini player is open.

### Changed
- Re-baked waveforms.json: 4 previously dead Dropbox links were fixed and
  their tracks now have waveforms/durations (184 of 186 baked). Still dead:
  "woop wahp euro" and "tbd".

## [2.2] - 2026-07-09

Feature release.

### Added
- Pre-baked waveforms and durations: `tools/generate_waveforms.py` analyses
  every track via ffmpeg and writes `waveforms.json` (served from this repo),
  so visitors get instant waveforms and durations with no client-side audio
  decoding or double-downloading. Client-side generation remains as a
  fallback for unbaked tracks.
- Embed widget: new `embed.html` renders a minimal single-track player for
  iframes, and every track card has a "</> embed" button that copies the
  embed code.
- Shareable view state: search, filter, sort, and length choices are
  reflected in the URL, so any filtered view can be shared as a link.
- Shareable favourites: a "share favs" button (on the Favs view) copies a
  link encoding your favourites; recipients get a banner with a one-click
  "add to my favourites" import.
- Duration filter: any length / under 2 min / 2-4 min / over 4 min, powered
  by the baked durations.
- "More like this": up to three tag-overlap suggestions shown on the
  currently playing track's card.
- Media Session API: lock-screen and hardware-key play/pause/next/previous
  and seek support, with track metadata and artwork.
- Keyboard: "/" focuses the search box.

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
