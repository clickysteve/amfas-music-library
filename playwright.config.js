// @ts-check
const { defineConfig } = require('@playwright/test');
const fs = require('fs');

// Some sandboxed dev environments pre-install a Chromium at a fixed path;
// use it when present. CI and normal dev machines install via
// `npx playwright install chromium` instead.
const PREINSTALLED = '/opt/pw-browsers/chromium';
const baseArgs = ['--autoplay-policy=no-user-gesture-required', '--mute-audio'];
const launchOptions = fs.existsSync(PREINSTALLED)
  ? { executablePath: PREINSTALLED, args: baseArgs.concat('--no-sandbox') }
  : { args: baseArgs };

module.exports = defineConfig({
  testDir: 'tests',
  timeout: 30000,
  fullyParallel: true,
  retries: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    viewport: { width: 1280, height: 720 },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'python3 -m http.server 4173 --bind 127.0.0.1',
    url: 'http://127.0.0.1:4173/index.html',
    reuseExistingServer: true,
    timeout: 30000,
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium', launchOptions } }],
});
