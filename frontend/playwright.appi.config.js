import { defineConfig, devices } from '@playwright/test'

const port = Number(process.env.APPI_E2E_PORT || 3041)
const batch = (process.env.APPI_E2E_BATCH || 'flows').replace(/[^a-z0-9-]/gi, '-')
const baseURL = `http://127.0.0.1:${port}`

export default defineConfig({
  testDir: './e2e',
  testMatch: ['platform/platform-appi.spec.js', 'platform/platform-appi-responsive.spec.js'],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  outputDir: `./test-results/appi-${batch}`,
  reporter: [
    ['list'],
    ['json', { outputFile: `../test-results/appi/browser-${batch}.json` }],
    ['junit', { outputFile: `../test-results/appi/browser-${batch}.xml` }],
  ],
  use: { baseURL, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium-appi', use: { ...devices['Desktop Chrome'] } }],
  webServer: process.env.E2E_REUSE_SERVER === '1' ? undefined : {
    command: `npm run dev -- --host 127.0.0.1 --port ${port} --strictPort`,
    url: `${baseURL}/es-co/platform/projects`,
    reuseExistingServer: false,
    timeout: 180_000,
    env: { NUXT_DEVTOOLS_ENABLED: 'false', NUXT_PUBLIC_RECAPTCHA_ENABLED: 'false', DJANGO_DEV_TARGET: 'http://127.0.0.1:9' },
  },
})
