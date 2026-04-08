# The AMFAS Music Library

A publicly shared database of music created by **Stephen McLeod** (aka *allmyfriendsaresynths*), built for independent artists, film-makers, vloggers, and other creative folks to use in their projects.

All tracks are free for non-commercial use under a [Creative Commons CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) license, provided you credit **Stephen McLeod aka allmyfriendsaresynths** and link back to the site.

**Live site:** [clickysteve.github.io/amfas-music-library](https://clickysteve.github.io/amfas-music-library/)

## Features

- **Live data from Notion** — track listings are pulled in real-time from a Notion database via a Cloudflare Worker API, so updates to the database appear on the site immediately
- **Audio previews** — high-quality WAV streaming directly from Dropbox, with play/pause, progress scrubbing, and time display
- **Search** — filter tracks by name, gear, or feel in real-time
- **Tag filtering** — preset filter buttons (Electronic, Ambient, Dark, Glitchy, Has Vocals, Has Audio) plus clickable tags on each track card for ad-hoc filtering
- **Download links** — direct Dropbox download links for each track
- **Single-file deployment** — the entire front-end is one `index.html` file hosted on GitHub Pages, no build step required

## Architecture

```
Notion Database  -->  Cloudflare Worker (API)  -->  GitHub Pages (front-end)
```

- **Notion** holds all track data (titles, audio links, gear, tags)
- **Cloudflare Worker** queries the Notion API, extracts the relevant properties, and serves the result as JSON with CORS headers
- **GitHub Pages** serves the static `index.html` which fetches from the Worker on page load

## Setting Up Your Own

If you wanted to replicate this for your own music library:

### 1. Notion Database

Create a Notion database with the following properties:

| Property | Type | Purpose |
|---|---|---|
| `Name` | Title | Working title of the track |
| `Final Name (if exists)` | Rich text | Display name (falls back to Name) |
| `How does it sound?` | Multi-select | Feel/mood tags (e.g. "ambient", "dark", "electronic") |
| `AUDIO` | URL | Dropbox sharing link to the audio file |
| `Gear Used` | Multi-select or rich text | Instruments/gear used on the track |

Create a [Notion integration](https://www.notion.so/my-integrations) and share your database with it. You'll need the integration token and the database ID (the long hex string in the database URL).

### 2. Cloudflare Worker

Create a Cloudflare Worker that:
- Reads your Notion integration token from an environment variable (`NOTION_SECRET`)
- Queries the Notion database API with pagination
- Extracts the properties above into a simple JSON format
- Returns the result with CORS headers so the front-end can fetch it

Set your `NOTION_SECRET` as an encrypted environment variable in the Cloudflare dashboard.

### 3. Front-end

Update the `API_URL` constant in `index.html` to point to your Cloudflare Worker URL, then enable GitHub Pages (Settings > Pages > Deploy from branch > main).

### Audio Hosting

Audio files are hosted on Dropbox. The site converts standard Dropbox share links to direct streaming URLs by swapping `www.dropbox.com` for `dl.dropboxusercontent.com`. Any host that supports direct file access would work.

## License

The code in this repository is provided as-is. The music tracks themselves are licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
