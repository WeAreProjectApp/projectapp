import { ADMIN_HOSTING_CONTROLS } from '../helpers/flow-tags.js'
import { test, expect, assertResponsiveScenario } from '../helpers/test.js'
import { setupHostingControls } from '../helpers/hosting-controls.js'
import { viewportUse } from '../helpers/viewports.js'
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js'

test.setTimeout(60_000)
const scenario = getResponsiveScenario('frontend/pages/panel/projects/hosting.vue')

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`hosting control ${profile}`, () => {
    test.use(viewportUse(profile))
    test('message editing remains usable from Projects', {
      tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:success', '@role:admin', '@responsive:projects', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      const state = await setupHostingControls(page, { throughProjects: true })
      await page.getByTestId('hosting-title-banner').fill('Aviso de prueba responsivo')
      await page.getByTestId('hosting-save-banner').click()
      await expect.poll(() => state.banner_title).toBe('Aviso de prueba responsivo')
      await expect(page.getByTestId('hosting-configured-mode')).toContainText('Funcionamiento normal')
      await assertResponsiveScenario(page, testInfo, scenario, { profile })
    })
  })
}
