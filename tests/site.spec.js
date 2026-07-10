// @ts-check
// Hermetic tests for the AMFAS Music Library.
// The Notion/Worker API, waveforms.json, and analysis.json are all stubbed
// with fixtures; audio is a locally served 1-second tone, so nothing here
// touches Dropbox or the real Worker.
const { test, expect } = require('@playwright/test');

const ORIGIN = 'http://127.0.0.1:4173';
const API_GLOB = '**amfas-tracks.allmyfas.workers.dev**';

// ── Fixtures ──────────────────────────────────────────────────────────────
function trackId(i) {
  return `${String(i).padStart(2, '0')}abcdef-1111-2222-3333-444444444444`;
}
function hash8(id) {
  return id.replace(/-/g, '').slice(0, 8);
}

const N = 12;
const TRACKS = [];
for (let i = 1; i <= N; i++) {
  TRACKS.push({
    id: trackId(i),
    title: `Track${String(i).padStart(2, '0')}`,
    finalName: null,
    feel: i === 1 ? ['dark', 'electronic'] : i === 2 ? ['ambient'] : ['electronic'],
    gear: ['synth'],
    audio: i === N ? null : `${ORIGIN}/tests/fixtures/tone.wav?rlkey=fix${i}&dl=0`,
    hasVocals: i === 3,
    createdAt: i === 2 ? new Date().toISOString() : '2020-01-01T00:00:00.000Z',
  });
}
TRACKS[0].finalName = 'Alpha Dark';

const WAVEFORMS = {};
const ANALYSIS = {};
for (let i = 1; i < N; i++) {
  const id = trackId(i);
  WAVEFORMS[id] = { d: i === 1 ? 60 : i === 3 ? 300 : 180, w: Array(200).fill(0.5) };
  ANALYSIS[id] = {
    bpm: 80 + i * 10,
    key: i === 1 ? 'A minor' : 'C major',
    keyConf: 0.9,
    lufs: -12,
    rms: 0.1 + i * 0.01,
    bright: 2000,
    sim: i === 1 ? [trackId(2), trackId(3)] : [trackId(1)],
    xy: i === 1 ? [0.5, 0.5] : [0.05 + i * 0.07, 0.9],
  };
}

async function stub(page) {
  // Catch-all FIRST (registered routes are matched last-to-first): block every
  // external request so tests are fully hermetic and never hang on fonts,
  // YouTube, or Dropbox. Specific stubs below take precedence.
  await page.route('**/*', (route) => {
    const url = route.request().url();
    if (url.startsWith('http://127.0.0.1')) return route.continue();
    return route.abort();
  });
  await page.route(API_GLOB, (route) =>
    route.fulfill({ json: { tracks: TRACKS } }));
  await page.route('**/waveforms.json', (route) =>
    route.fulfill({ json: WAVEFORMS }));
  await page.route('**/analysis.json', (route) =>
    route.fulfill({ json: ANALYSIS }));
}

test.beforeEach(async ({ page }) => {
  await stub(page);
});

// ── Library page ──────────────────────────────────────────────────────────
test('renders the library with the default Has Audio filter', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect(page.locator('.track-card')).toHaveCount(N - 1);
  await expect(page.locator('#visible-count')).toHaveText(String(N - 1));
  await expect(page.locator('.badge-new')).toHaveCount(1); // Track02 is new
  expect(errors).toEqual([]);
});

test('shows BPM and key badges from analysis.json', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.track-meta').first()).toContainText('bpm');
  await expect(page.getByText('90 bpm · A min')).toBeVisible();
});

test('search matches titles and musical keys', async ({ page }) => {
  await page.goto('/');
  await page.fill('#search', 'Alpha');
  await expect(page.locator('.track-card')).toHaveCount(1);
  await page.fill('#search', 'A minor');
  await expect(page.locator('.track-card')).toHaveCount(1); // only Track01 is minor
  await page.fill('#search', '');
  await expect(page.locator('.track-card')).toHaveCount(N - 1);
});

test('tag filter buttons and URL state sync', async ({ page }) => {
  await page.goto('/');
  await page.click('.filter-btn[data-filter="ambient"]');
  await expect(page.locator('.track-card')).toHaveCount(1);
  expect(page.url()).toContain('filter=ambient');
  // And the reverse: arriving with a filter param applies it
  await page.goto('/?filter=dark');
  await expect(page.locator('.filter-btn[data-filter="dark"]')).toHaveClass(/active/);
  await expect(page.locator('.track-card')).toHaveCount(1);
});

test('sorts by BPM ascending', async ({ page }) => {
  await page.goto('/');
  await page.selectOption('#sort-select', 'bpm');
  await expect(page.locator('.track-title').first()).toHaveText('Alpha Dark'); // 90 bpm is lowest
});

test('duration filter uses baked durations', async ({ page }) => {
  await page.goto('/');
  await page.selectOption('#length-select', 'short');
  await expect(page.locator('.track-card')).toHaveCount(1); // 60s track
  await page.selectOption('#length-select', 'long');
  await expect(page.locator('.track-card')).toHaveCount(1); // 300s track
  await page.selectOption('#length-select', 'any');
  await expect(page.locator('.track-card')).toHaveCount(N - 1);
});

test('plays a track: mini player, pause via spacebar, sounds-like row', async ({ page }) => {
  await page.goto('/');
  await page.locator('.play-btn').first().click();
  await expect(page.locator('#mini-player')).toHaveClass(/active/, { timeout: 15000 });
  await expect(page.locator('#mini-play')).toHaveText('▮▮');
  // Sound-based similarity row appears on the playing card
  await expect(page.locator('.similar-row')).toContainText('sounds like');
  await expect(page.locator('.similar-btn')).toHaveCount(2);
  // Spacebar pauses
  await page.keyboard.press('Space');
  await expect(page.locator('#mini-play')).toHaveText('▶');
});

test('favourites: toggle, filter, share button appears', async ({ page }) => {
  await page.goto('/');
  await page.locator('.fav-btn').first().click();
  await page.click('.filter-btn[data-filter="favourites"]');
  await expect(page.locator('.track-card')).toHaveCount(1);
  await expect(page.locator('#share-favs-btn')).toBeVisible();
});

test('shared favourites link shows import banner', async ({ page }) => {
  await page.goto(`/?favs=${hash8(trackId(2))}.${hash8(trackId(3))}`);
  await expect(page.locator('#shared-banner')).toBeVisible();
  await expect(page.locator('#shared-banner-text')).toContainText('2 favourite tracks');
  await expect(page.locator('.track-card')).toHaveCount(2);
});

test('deep link scrolls to and highlights the track', async ({ page }) => {
  const id = trackId(5);
  await page.goto(`/#amfas-${hash8(id)}-track05`);
  const card = page.locator('.track-card.highlighted');
  await expect(card).toHaveCount(1);
  await expect(card.locator('.track-title')).toHaveText('Track05');
  await expect(page.locator('.filter-btn[data-filter="all"]')).toHaveClass(/active/);
});

test('"/" focuses search and back-to-top appears after scrolling', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('/');
  await expect(page.locator('#search')).toBeFocused();
  await page.keyboard.press('Escape');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(page.locator('#top-btn')).toHaveClass(/visible/);
  await page.click('#top-btn');
  await expect.poll(() => page.evaluate(() => window.scrollY), { timeout: 5000 }).toBeLessThan(100);
});

// ── Embed widget ──────────────────────────────────────────────────────────
test('embed.html renders and plays a track', async ({ page }) => {
  await page.goto(`/embed.html#amfas-${hash8(trackId(1))}`);
  await expect(page.locator('.title')).toHaveText('Alpha Dark');
  await page.click('#play');
  await expect(page.locator('#play')).toHaveText('▮▮', { timeout: 15000 });
  await expect(page.locator('#time')).toContainText('/');
});

// ── Sound map ─────────────────────────────────────────────────────────────
test('map.html renders nodes and selecting one opens the panel', async ({ page }) => {
  await page.goto('/map.html');
  await expect(page.locator('#state')).toBeHidden();
  // Track01 sits at xy [0.5, 0.5] → centre of the plot area
  const { x, y } = await page.evaluate(() => {
    const W = window.innerWidth, H = window.innerHeight;
    return { x: 70 + 0.5 * (W - 140), y: (H - 140) * 0.5 + 90 };
  });
  await page.mouse.move(x, y);
  await expect(page.locator('#tooltip')).toBeVisible();
  await expect(page.locator('#tooltip')).toContainText('Alpha Dark');
  await page.mouse.click(x, y);
  await expect(page.locator('#panel')).toHaveClass(/active/);
  await expect(page.locator('#p-title')).toHaveText('Alpha Dark');
  await expect(page.locator('#p-open')).toHaveAttribute('href', `./#amfas-${hash8(trackId(1))}`);
});
