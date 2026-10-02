/** R-communications-04: the client secure-link workspace and confirmation remain reachable at every approved profile. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { installPlatformSecureLinksMock, openPlatformSecureLinks } from '../helpers/platform-secure-links.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

test.setTimeout(60_000);

const scenario = getResponsiveScenario('frontend/pages/platform/projects/[id]/secure-links.vue');

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`platform secure links · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('keeps the client management confirmation reachable without horizontal overflow', {
      tag: ['@flow:platform-secure-link-manage', '@outcome:display', '@responsive:communications', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await installPlatformSecureLinksMock(page);
      // quality: allow-deep-link (the authenticated project list is the shell entry; the test clicks the project then its client-only navigation item)
      await openPlatformSecureLinks(page);
      await page.getByTestId('platform-secure-manage-7').click();
      await page.getByTestId('platform-secure-revoke').click();
      const confirmation = page.getByRole('dialog').filter({ hasText: 'Confirmar acción' });
      await expect(confirmation.getByText('El enlace dejará de abrirse. Se conservan el contenido cifrado y el historial.')).toHaveCount(1);
      await assertResponsiveScenario(page, testInfo, scenario, {
        profile,
        priorityLocator: page.getByTestId('platform-secure-row-7').getByText('Acceso de despliegue', { exact: true }),
        modalLocator: confirmation,
        finalActionLocator: confirmation.getByTestId('platform-secure-confirm'),
      });
    });
  });
}
