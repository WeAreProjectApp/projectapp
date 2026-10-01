import { chromium } from '@playwright/test'
import { authenticate, fixture, frontendUrl } from './helpers.js'
import { waitForNuxtApp } from '../helpers/navigation.js'

// Compile these SPA routes before testing navigation. Vite's first dependency
// optimization can reload the document during a route click on a clean runner.
// Real JWT authentication and disposable delivery data are used for this setup.
export default async function globalSetup() {
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage()
    const data = await fixture(page.request, { title: 'delivery-browser-warmup' })
    await authenticate(page, page.request, data, 'admin')
    const routes = [
      '/es-co/platform/projects',
      `/es-co/platform/projects/${data.project.id}`,
      `/es-co/platform/projects/${data.project.id}/delivery`,
    ]
    for (const route of routes) {
      await page.goto(`${frontendUrl}${route}`, { waitUntil: 'domcontentloaded' })
      await waitForNuxtApp(page)
    }
    await page.getByTestId(`delivery-stage-${data.stage_id}`).waitFor({ state: 'visible' })
  } finally {
    await browser.close()
  }
}
