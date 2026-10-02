import { chromium } from '@playwright/test'
import { authenticate, authenticatePanel, fixture, frontendUrl } from './helpers.js'
import { waitForNuxtApp } from '../helpers/navigation.js'
export default async function globalSetup() {
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage()
    page.on('pageerror', (error) => console.error(`P4 browser: ${error.message}`))
    const data = await fixture(page.request, { title: 'p4-warmup' })
    await authenticate(page, page.request, data, 'admin')
    for (const path of ['/es-co/platform/projects', `/es-co/platform/projects/${data.project.id}`,
      `/es-co/platform/projects/${data.project.id}/ideas`, `/es-co/platform/projects/${data.project.id}/access`]) {
      await page.goto(`${frontendUrl}${path}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
      await waitForNuxtApp(page, { timeout: 120_000 })
    }
    await authenticatePanel(page, data)
    for (const path of ['/es-co/panel/projects', `/es-co/panel/projects/${data.project.id}/ideas`]) {
      await page.goto(`${frontendUrl}${path}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
      await waitForNuxtApp(page, { timeout: 120_000 })
    }
  } finally { await browser.close() }
}
