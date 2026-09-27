/** R-projects-02: monitoring cards and the follow-up modal must remain usable across the panel profiles. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { installMonitoringMock, monitoringCaseTitle } from '../helpers/monitoring.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const monitoringScenario = getResponsiveScenario('frontend/pages/panel/monitoring/index.vue');

const enterMonitoringByProfile = Object.freeze({
  compact: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Monitoreo', exact: true }).click(); },
  portrait: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Monitoreo', exact: true }).click(); },
  landscape: (page) => page.getByRole('link', { name: 'Monitoreo', exact: true }).click(),
  desktop: (page) => page.getByRole('link', { name: 'Monitoreo', exact: true }).click(),
  wide: (page) => page.getByRole('link', { name: 'Monitoreo', exact: true }).click(),
});

async function enterMonitoring(page, profile) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await enterMonitoringByProfile[profile](page);
  await expect(page.getByTestId('monitoring-page').getByRole('heading', { name: 'Monitoring', exact: true })).toHaveCount(1);
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`monitoring catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('opens a project case from the responsive monitoring card', {
      tag: ['@flow:admin-monitoring-case-follow-up', '@outcome:display', '@responsive:projects', `@responsive-scenario:${monitoringScenario.catalogKey}`, `@responsive-batch:${batchForScenario(monitoringScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setAuthLocalStorage(page, { token: 'monitoring-responsive-token', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
      await installMonitoringMock(page);
      // quality: allow-deep-link (the authenticated panel home is the shell entry; this test reaches Monitoring through the visible responsive navigation)
      await enterMonitoring(page, profile);
      const card = page.getByTestId('monitoring-page').getByRole('button', { name: monitoringCaseTitle, exact: true });
      await expect(card).toHaveCount(1);
      await card.click();

      const modal = page.getByRole('dialog').filter({ has: page.getByTestId('monitoring-detail') });
      await expect(modal.getByRole('heading', { name: monitoringCaseTitle, exact: true })).toHaveCount(1);
      await assertResponsiveScenario(page, testInfo, monitoringScenario, {
        profile,
        modalLocator: modal,
        finalActionLocator: modal.getByRole('button', { name: 'Close', exact: true }),
      });
    });
  });
}
