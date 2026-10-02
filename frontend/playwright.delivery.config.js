import { defineConfig, devices } from '@playwright/test'

const python = process.env.DELIVERY_TEST_PYTHON || 'python3'
const quotedPython = "'" + python.replaceAll("'", "'\\''") + "'"

export default defineConfig({
  globalSetup: './e2e/delivery/global-setup.js',
  testDir: './e2e',
  testMatch: ['delivery/*.spec.js'],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:3203', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium-delivery', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${quotedPython} ../backend/accounts/tests/delivery_browser_server.py`,
      url: 'http://127.0.0.1:3202/__delivery_ready__',
      reuseExistingServer: false,
      timeout: 420_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 3203 --strictPort',
      url: 'http://127.0.0.1:3203',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        DJANGO_DEV_TARGET: 'http://127.0.0.1:3202',
        NUXT_PUBLIC_RECAPTCHA_ENABLED: 'false',
        NUXT_DEVTOOLS_ENABLED: 'false',
      },
    },
  ],
})
