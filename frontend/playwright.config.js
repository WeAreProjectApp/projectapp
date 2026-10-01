import { defineConfig, devices } from '@playwright/test';

const PORT = process.env.E2E_PORT ? Number(process.env.E2E_PORT) : 3000;
const baseURL = process.env.E2E_BASE_URL || `http://localhost:${PORT}`;
const reuseExistingServer = !process.env.CI;
const isResponsiveRun = process.env.E2E_RESPONSIVE === '1';
const workers = process.env.E2E_WORKERS ? Number(process.env.E2E_WORKERS) : 3;

if (!Number.isInteger(workers) || workers < 1) {
  throw new Error(`E2E_WORKERS must be a positive integer; received ${process.env.E2E_WORKERS}`);
}

const reporters = [
  ['list'],
  ['html', { open: 'never' }],
  ['json', { outputFile: 'e2e-results/results.json' }],
  ['./e2e/reporters/flow-coverage-reporter.mjs', { outputDir: 'e2e-results' }],
];

if (isResponsiveRun) {
  reporters.push(['./e2e/reporters/responsive-matrix-reporter.mjs', { outputDir: 'e2e-results' }]);
}

export default defineConfig({
  globalSetup: './e2e/global-setup.js',
  testDir: './e2e',
  // Actual worker/offline checks require a production build served by Django.
  // They run in CI through playwright.pwa.config.js, separately from Nuxt dev.
  testIgnore: ['**/pwa/**', '**/captcha/**', '**/delivery/**', '**/issues/**'],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  retries: process.env.CI ? 2 : 1,
  workers,
  reporter: reporters,
  use: {
    baseURL,
    navigationTimeout: 60_000,
    trace: 'retain-on-failure',
    screenshot: 'off',
    video: 'off',
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: baseURL,
    // The devtools launcher sits over full-screen modal footers on mobile.
    env: { NUXT_PUBLIC_RECAPTCHA_ENABLED: 'false', NUXT_DEVTOOLS_ENABLED: 'false' },
    reuseExistingServer,
    timeout: 120_000,
  },
  // Responsive specs declare their canonical profile with test.use(). Keeping
  // one browser project prevents unrelated E2E tests from being multiplied by
  // five and makes every catalog/profile cell explicit in the test report.
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
