import { defineConfig, devices } from '@playwright/test'
const python = process.env.ISSUES_TEST_PYTHON || 'python3'
const quotedPython = "'" + python.replaceAll("'", "'\\''") + "'"
const reuseExistingServer = !process.env.CI && process.env.ISSUES_REUSE_SERVER === '1'

export default defineConfig({
  testDir: './e2e', testMatch: ['issues/*.spec.js'],
  globalSetup: './e2e/issues/global-setup.js',
  timeout: 60_000, expect: { timeout: 15_000 }, workers: 1, retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:4213', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium-issues', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    { command: `${quotedPython} ../backend/accounts/tests/issue_browser_server.py`, url: 'http://127.0.0.1:4212/__issues_ready__', reuseExistingServer, timeout: 120_000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 4213 --strictPort', url: 'http://127.0.0.1:4213/platform', reuseExistingServer, timeout: 120_000,
      env: { DJANGO_DEV_TARGET: 'http://127.0.0.1:4212', NUXT_PUBLIC_RECAPTCHA_ENABLED: 'false', NUXT_DEVTOOLS_ENABLED: 'false' } },
  ],
})
