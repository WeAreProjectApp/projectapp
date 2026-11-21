import { defineConfig, devices } from '@playwright/test'

// pytest supplies a disposable, seeded SQLite database and serves build:django
// through the application's URLconf. Each suite writes its own mergeable report.
const suite = process.env.PUBLISHED_SUITE
export default defineConfig({
  testDir: './e2e',
  testMatch: ['published/*.spec.js'],
  workers: 1,
  retries: 0,
  maxFailures: 1,
  outputDir: `test-results-published/${suite}`,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['blob', { outputDir: `published-blob/${suite}`, fileName: `report-${suite}.zip` }]],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.PUBLISHED_ORIGIN,
    serviceWorkers: 'block',
  },
})
