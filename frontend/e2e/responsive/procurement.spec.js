/**
 * Responsive procurement matrix.
 *
 * R-projects-03: SECOP cards or their classification detail could become
 * unreachable at a panel breakpoint while desktop remained usable.
 */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js'
import { waitForNuxtApp } from '../helpers/navigation.js'
import { viewportUse } from '../helpers/viewports.js'
import { opportunity, setProcurementAdmin, setupProcurementApi } from '../helpers/procurement.js'
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js'

const listScenario = getResponsiveScenario('frontend/pages/panel/procurement/index.vue')
const detailScenario = getResponsiveScenario('frontend/pages/panel/procurement/[id].vue')

const procurementNavigationByProfile = Object.freeze({
  compact: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Oportunidades SECOP', exact: true }).click() },
  portrait: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Oportunidades SECOP', exact: true }).click() },
  landscape: (page) => page.getByRole('link', { name: 'Oportunidades SECOP', exact: true }).click(),
  desktop: (page) => page.getByRole('link', { name: 'Oportunidades SECOP', exact: true }).click(),
  wide: (page) => page.getByRole('link', { name: 'Oportunidades SECOP', exact: true }).click(),
})

async function enterProcurement(page, profile) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  await procurementNavigationByProfile[profile](page)
  await expect(page).toHaveURL(/\/panel\/procurement$/)
  await expect(page.getByTestId('procurement-page')).toHaveCount(1)
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`procurement catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile))

    test('SECOP card remains reachable from the responsive panel navigation', {
      tag: [
        '@flow:admin-procurement-opportunity-list', '@outcome:display', '@responsive:projects',
        `@responsive-scenario:${listScenario.catalogKey}`, `@responsive-batch:${batchForScenario(listScenario.catalogKey)}`,
        `@viewport:${profile}`,
      ],
    }, async ({ page }, testInfo) => {
      // Catches a responsive sidebar that hides the only route to SECOP cards.
      await setProcurementAdmin(page)
      await setupProcurementApi(page)
      // quality: allow-deep-link (the panel home initializes authenticated chrome; navigation to SECOP is performed through the visible sidebar)
      await enterProcurement(page, profile)
      await page.getByRole('button', { name: 'Actualizar', exact: true }).click()
      const card = page.getByTestId(`procurement-opportunity-${opportunity.id}`)
      await expect(card).toContainText('Mantenimiento de espacios públicos')
      await assertResponsiveScenario(page, testInfo, listScenario, { profile, priorityLocator: card })
    })

    test('classification detail remains reachable from the responsive SECOP card', {
      tag: [
        '@flow:admin-procurement-classification', '@outcome:display', '@responsive:projects',
        `@responsive-scenario:${detailScenario.catalogKey}`, `@responsive-batch:${batchForScenario(detailScenario.catalogKey)}`,
        `@viewport:${profile}`,
      ],
    }, async ({ page }, testInfo) => {
      // Catches a responsive opportunity card that no longer opens its classification detail.
      await setProcurementAdmin(page)
      await setupProcurementApi(page)
      // quality: allow-deep-link (the panel home initializes authenticated chrome; both procurement routes are reached through visible controls)
      await enterProcurement(page, profile)
      await page.getByTestId(`procurement-opportunity-${opportunity.id}`).getByRole('link', { name: opportunity.title }).click()
      await expect(page).toHaveURL(new RegExp(`/panel/procurement/${opportunity.id}$`))
      const detail = page.getByTestId('procurement-detail')
      await expect(detail.getByRole('heading', { name: opportunity.title, level: 1 })).toHaveText(opportunity.title)
      await assertResponsiveScenario(page, testInfo, detailScenario, { profile })
    })
  })
}
