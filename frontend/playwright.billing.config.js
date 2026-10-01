import { defineConfig } from '@playwright/test'
import base from './playwright.config.js'

// Billing tests warm their own routes through real UI navigation and explicit
// waits. The general warmup visits unrelated marketing and project-authoring
// routes whose API fixtures do not belong to this domain.
export default defineConfig({
  ...base,
  globalSetup: undefined,
  // A caller opting into reuse owns its isolated server. Avoid starting a
  // competing Nuxt process in the same worktree when a root-route probe fails.
  webServer: process.env.E2E_REUSE_SERVER === '1' ? undefined : {
    ...base.webServer,
    url: `${base.use.baseURL}/en-us/platform/collection-accounts`,
  },
  testMatch: [
    '**/platform/platform-collection-accounts.spec.js',
    '**/platform/platform-hosting-subscription.spec.js',
    '**/admin/admin-project-billing-context.spec.js',
    '**/admin/admin-accounting-collections.spec.js',
    '**/admin/admin-accounting-hosting-billing-cycles.spec.js',
    '**/responsive/accounting-specials.spec.js',
    '**/responsive/billing.spec.js',
  ],
})
