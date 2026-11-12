import { test, expect } from '../helpers/test.js'

import { ADMIN_PWA_OFFLINE, ADMIN_PWA_INSTALL } from '../helpers/flow-tags.js'

async function openInstalledPanel(page) {
  // This public panel entry registers the actual worker without requiring a
  // production account or any database fixture.
  const configResponse = page.waitForResponse((response) => (
    new URL(response.url()).pathname === '/api/auth/config/'
    && response.request().method() === 'GET'
  ));
  await page.goto('/es-co/panel/login', { waitUntil: 'domcontentloaded' })
  expect((await configResponse).status()).toBe(200)
  const passwordEntry = page.getByRole('link', { name: 'Entrar con contraseña' })
  await expect(passwordEntry).toHaveAttribute('href', '/admin/login/?next=%2Fpanel%2F')
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
    if (!navigator.serviceWorker.controller) {
      await new Promise((resolve) => navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true }))
    }
  })
}

test.describe('PWA build served by Django', () => {
  test.setTimeout(60_000)

  test('exposes an installable application at the panel entry', {
    tag: [...ADMIN_PWA_INSTALL, '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (the browser discovers installation metadata automatically on entry; the native install dialog is outside Playwright)
    // quality: allow-deep-link (installation metadata is discovered on a direct panel entry before the user chooses any in-app navigation)
    await openInstalledPanel(page)
    await expect(page.locator('link[rel="manifest"]')).toHaveAttribute('href', '/manifest.webmanifest')
    const browserProtocol = await page.context().newCDPSession(page)
    const manifest = await browserProtocol.send('Page.getAppManifest')
    expect(JSON.parse(manifest.data)).toMatchObject({ id: '/panel', start_url: '/es-co/panel', display: 'standalone' })
    expect(manifest.errors).toEqual([])
    expect((await browserProtocol.send('Page.getInstallabilityErrors')).installabilityErrors).toEqual([])
  })

  test('retries the original panel URL after connectivity returns', {
    tag: [...ADMIN_PWA_OFFLINE, '@outcome:success', '@role:admin'],
  }, async ({ page, context }) => {
    await openInstalledPanel(page)
    await context.setOffline(true)
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('heading', { name: 'Sin conexión' })).toBeVisible()
    await context.setOffline(false)
    await page.getByRole('button', { name: 'Reintentar' }).click()
    await expect(page.getByRole('link', { name: 'Entrar con contraseña' })).toHaveAttribute('href', '/admin/login/?next=%2Fpanel%2F')
    await expect(page).toHaveURL(/\/es-co\/panel\/login$/)
    expect(await page.evaluate(() => caches.keys())).toEqual([])
  })

  test('keeps the offline notice when a retry still cannot reach the server', {
    tag: [...ADMIN_PWA_OFFLINE, '@outcome:failure', '@role:admin'],
  }, async ({ page, context }) => {
    await openInstalledPanel(page)
    await context.setOffline(true)
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.getByRole('button', { name: 'Reintentar' }).click()
    await expect(page.getByRole('heading', { name: 'Sin conexión' })).toBeVisible()
    await expect(page).toHaveURL(/\/es-co\/panel\/login$/)
  })

  test('requests authentication when opening the installed app without a session', {
    tag: [...ADMIN_PWA_OFFLINE, '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (launching the installed icon is represented by navigating to the manifest start_url; the session guard redirects before any panel control is usable)
    await openInstalledPanel(page)
    const manifest = await (await page.request.get('/manifest.webmanifest')).json()
    await page.goto(manifest.start_url, { waitUntil: 'domcontentloaded' })
    await expect(page).toHaveURL(/\/admin\/login\/\?next=\/es-co\/panel$/)
    await expect(page.getByRole('textbox', { name: /Username|usuario/i })).toBeVisible()
  })
})
