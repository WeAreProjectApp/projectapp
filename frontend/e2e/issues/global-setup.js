import { chromium } from '@playwright/test'
import { fixture, open } from './helpers.js'

// Compile the changed SPA routes before measuring user actions on a clean runner.
// Authentication and fixtures use the same real APIs as the browser scenarios.
export default async function globalSetup() {
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({ baseURL: 'http://127.0.0.1:4213' })
    const data = await fixture(page.request, { title: 'issues-browser-warmup' })
    await open(page, page.request, data, data.general_project.id)
    await open(page, page.request, data, data.project.id, 'changes')
  } finally {
    await browser.close()
  }
}
