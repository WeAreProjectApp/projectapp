import { test, expect } from '../helpers/test.js'
import { commercialPages, setupCommercialPublic, openCommercial } from '../helpers/commercial-public.js'

test.setTimeout(60_000)

for (const entry of commercialPages) {
  test(`${entry.name} shares the exact URL in a themed dialog`, {
    tag: [`@flow:${entry.shareFlow}`, '@outcome:success', '@role:guest'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await setupCommercialPublic(page)
    await openCommercial(page, { ...entry, path: `${entry.path}?source=message#details` })
    await page.getByTestId(`${entry.prefix}-theme-toggle`).click()

    await page.getByTestId(entry.share).click()
    await page.getByTestId(`${entry.prefix}-copy-link`).click()

    await expect(page.getByTestId(`${entry.prefix}-share-feedback`)).toHaveText('Enlace copiado')
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(page.url())
    await expect(page.getByTestId(`${entry.prefix}-share-dialog`).locator('.share-modal-card')).toHaveCSS('background-color', 'rgb(19, 54, 47)')
    await page.keyboard.press('Escape')
    await expect(page.getByTestId(entry.share)).toBeFocused()
  })

  test(`${entry.name} keeps the saved theme while recovering from a load failure`, {
    tag: [`@flow:${entry.flow}`, '@outcome:failure', '@role:guest'],
  }, async ({ page }) => {
    await setupCommercialPublic(page, { fail: true })
    await page.addInitScript((key) => localStorage.setItem(key, 'dark'), `projectapp-${entry.prefix}-theme`)
    // quality: allow-deep-link (recipients open these documents directly from shared URLs)
    await page.goto(entry.path, { waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('heading', { name: /No pudimos cargar/ })).toBeVisible()
    await expect(page.getByTestId(`${entry.prefix}-public-page`)).toHaveCSS('background-color', 'rgb(10, 31, 28)')
    await setupCommercialPublic(page)

    await page.getByRole('button', { name: 'Reintentar', exact: true }).click()

    await expect(page.getByTestId(entry.root)).toBeVisible()
    await expect(page.getByTestId(`${entry.prefix}-theme-toggle`)).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByTestId(entry.root)).toHaveCSS('background-color', 'rgb(10, 31, 28)')
  })
}

test('catalog modal restores light colors under an inherited dark panel', {
  tag: ['@flow:public-additional-modules-theme', '@outcome:success', '@role:guest'],
}, async ({ page }) => {
  await setupCommercialPublic(page)
  await openCommercial(page, commercialPages[0])
  // Reproduce the theme left by an earlier panel visit without changing storage.
  await page.evaluate(() => document.documentElement.classList.add('dark'))

  await page.getByTestId('additional-module-card-landing-page').click()

  await expect(page.getByTestId('additional-module-detail-modal')).toHaveCSS('background-color', 'rgb(242, 247, 245)')
  await expect(page.getByRole('heading', { name: 'Qué es' })).toHaveCSS('color', 'rgb(0, 41, 33)')
  await page.keyboard.press('Escape')
  await page.getByTestId('additional-modules-theme-toggle').click()
  await page.getByTestId('additional-module-card-landing-page').click()
  await expect(page.getByTestId('additional-module-detail-modal')).toHaveCSS('background-color', 'rgb(10, 31, 28)')
})

for (const entry of commercialPages.filter((page) => page.guideFlow)) {
  test(`${entry.name} guide follows the local dark theme`, {
    tag: [`@flow:${entry.guideFlow}`, '@outcome:success', '@role:guest'],
  }, async ({ page }) => {
    await setupCommercialPublic(page, { video: true })
    await openCommercial(page, entry)
    await page.getByTestId(`${entry.prefix}-theme-toggle`).click()

    await page.getByTestId(`${entry.prefix}-guide-restart`).click()

    await expect(page.getByTestId(`${entry.prefix}-guide`)).toHaveCSS('background-color', 'rgb(19, 54, 47)')
    await expect(page.getByTestId(`${entry.prefix}-guide`)).toContainText(entry.guideTitle)
    await page.getByRole('button', { name: 'Omitir' }).click()
    await expect(page.getByTestId(`${entry.prefix}-guide`)).toHaveCount(0)
  })
}

test('partnership shows clipboard errors inside the share dialog', {
  tag: ['@flow:public-financing-share', '@outcome:failure', '@role:guest'],
}, async ({ page }) => {
  await setupCommercialPublic(page)
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.reject(new Error('denied')) } })
  })
  await openCommercial(page, commercialPages[2])
  await page.getByTestId('financing-share').click()

  await page.getByTestId('financing-copy-link').click()

  await expect(page.getByRole('alert')).toContainText('No pudimos copiar el enlace')
})
