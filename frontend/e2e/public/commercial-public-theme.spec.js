import { test, expect } from '../helpers/test.js'
import { PANEL_VIEWPORTS } from '../../config/responsive.js'
import { waitForNuxtApp } from '../helpers/navigation.js'
import { commercialPages, setupCommercialPublic, openCommercial, expectReadableHeading, expectFloatingOrder, expectLayeredCard } from '../helpers/commercial-public.js'

for (const entry of commercialPages) {
  for (const [profile, viewport] of Object.entries(PANEL_VIEWPORTS)) {
    test.describe(`${entry.name} · ${profile}`, () => {
      test.use({ viewport })
      test.setTimeout(60_000)

      test('keeps public controls readable when switching theme', {
        tag: [`@flow:${entry.flow}`, '@outcome:success', '@role:guest'],
      }, async ({ page }, testInfo) => {
        await setupCommercialPublic(page)
        await openCommercial(page, entry)
        await expectReadableHeading(page, entry)
        await expectFloatingOrder(page, entry)
        await expectLayeredCard(page, entry)

        await page.getByTestId(`${entry.prefix}-theme-toggle`).click()

        await expect(page.getByTestId(entry.root)).toHaveCSS('background-color', 'rgb(10, 31, 28)')
        await expectReadableHeading(page, entry)
        await expectLayeredCard(page, entry)
        await page.screenshot({ path: testInfo.outputPath('dark.png') })
        await page.reload({ waitUntil: 'domcontentloaded' })
        await waitForNuxtApp(page)
        await expect(page.getByTestId(entry.root)).toHaveCSS('background-color', 'rgb(10, 31, 28)')
        await page.getByTestId(`${entry.prefix}-theme-toggle`).click()
        await expect(page.getByTestId(entry.root)).toHaveCSS('background-color', 'rgb(242, 247, 245)')
        await page.screenshot({ path: testInfo.outputPath('light.png') })
      })
    })
  }
}
