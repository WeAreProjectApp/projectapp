import { chromium } from '@playwright/test'
import { fixture, login } from './helpers.js'
import { setPlatformAuth } from '../helpers/platform-auth.js'
import { waitForNuxtApp } from '../helpers/navigation.js'

// Compile the changed SPA routes before measuring user actions on a clean runner.
// A cold Vite optimization can reload the document during the first route click.
// Warm each route directly; the scenarios still exercise the real navigation.
// Authentication and fixtures use the same real APIs as the browser scenarios.
export default async function globalSetup() {
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({ baseURL: 'http://127.0.0.1:4213' })
    const data = await fixture(page.request, { title: 'issues-browser-warmup' })
    const session = await login(page.request, data.client)
    await setPlatformAuth(page, {
      user: session.user, accessToken: session.tokens.access, refreshToken: session.tokens.refresh,
    })
    const routes = [
      '/es-co/platform/projects',
      `/es-co/platform/projects/${data.general_project.id}`,
      `/es-co/platform/projects/${data.general_project.id}/bugs`,
      `/es-co/platform/projects/${data.project.id}/changes`,
    ]
    for (const route of routes) {
      await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 90_000 })
      await waitForNuxtApp(page, { timeout: 90_000 })
    }
    await page.getByRole('heading', { name: 'Solicitudes de cambio', exact: true }).waitFor({ state: 'visible' })
  } finally {
    await browser.close()
  }
}
