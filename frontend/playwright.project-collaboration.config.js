import { defineConfig, devices } from '@playwright/test'
import { backendUrl, frontendPort, frontendUrl } from './e2e/project-collaboration/ports.js'
const python = process.env.PROJECT_COLLABORATION_TEST_PYTHON || 'python3'
const quotedPython = "'" + python.replaceAll("'", "'\\''") + "'"
const reuse = process.env.PROJECT_COLLABORATION_REUSE_SERVER === '1'
export default defineConfig({
  globalSetup: './e2e/project-collaboration/global-setup.js',
  testDir: './e2e',
  testMatch: ['project-collaboration/*.spec.js'],
  timeout: 60_000, expect: { timeout: 15_000 }, workers: 1, retries: 0,
  reporter: [
    ['list'],
    ['json', { outputFile: 'e2e-results/project-collaboration.json' }],
    ...(process.env.CI ? [['blob']] : []),
  ],
  use: { baseURL: frontendUrl, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium-project-collaboration', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    { command: `${quotedPython} ../backend/accounts/tests/project_collaboration_browser_server.py`,
      url: `${backendUrl}/__p4_ready__`, reuseExistingServer: reuse, timeout: 420_000 },
    { command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      url: frontendUrl, reuseExistingServer: reuse, timeout: 120_000,
      env: { DJANGO_DEV_TARGET: backendUrl, NUXT_PUBLIC_RECAPTCHA_ENABLED: 'false', NUXT_DEVTOOLS_ENABLED: 'false' } },
  ],
})
