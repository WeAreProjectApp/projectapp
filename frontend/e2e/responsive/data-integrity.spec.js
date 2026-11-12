/** R-dashboard-02: the integrity finding and its required preview stay reachable at every panel width. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { buildDataIntegrityApi } from '../helpers/data-integrity-fixture.js';
import {
  ADMIN_DATA_INTEGRITY_FINDINGS,
  ADMIN_DATA_INTEGRITY_FIX,
} from '../helpers/flow-tags.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

test.setTimeout(60_000);

const scenario = getResponsiveScenario('frontend/pages/panel/data-integrity.vue');
async function enterIntegrity(page, profile) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  if (profile === 'compact' || profile === 'portrait') {
    await page.getByRole('button', { name: 'Abrir menú', exact: true }).click();
    await page.getByRole('dialog', { name: 'Menú principal', exact: true }).getByRole('link', { name: 'Integridad de datos', exact: true }).click();
  } else {
    await page.getByRole('link', { name: 'Integridad de datos', exact: true }).click();
  }
  await expect(page).toHaveURL(/\/es-co\/panel\/data-integrity/);
}

async function setup(page) {
  const fixture = buildDataIntegrityApi();
  await setAuthLocalStorage(page, {
    token: 'data-integrity-responsive-token',
    userAuth: { id: 1, role: 'admin', is_staff: true, is_superuser: true },
  });
  await mockApi(page, fixture.handler);
}

async function openPreview(page) {
  const finding = page.getByTestId('integrity-finding-DC9');
  await expect(finding).toContainText('Documento sin carpeta');
  await finding.getByRole('checkbox', { name: 'Incluir en la corrección', exact: true }).check();
  await page.getByTestId('integrity-preview').click();
  const modal = page.getByTestId('integrity-confirm-modal');
  await expect(modal).toContainText('Carpeta: Sin carpeta → Actas · 51');
  await modal.getByLabel('Motivo', { exact: true }).fill('Se verifica el cambio antes de confirmar.');
  const confirm = page.getByTestId('integrity-confirm');
  await expect(confirm).toHaveText('Confirmar');
  return { finding, modal, confirm };
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`data integrity catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    // Bug caught: the responsive shell clips a persisted finding or leaves the preview confirmation unreachable.
    test('keeps the finding correction preview reachable', {
      tag: [
        ...ADMIN_DATA_INTEGRITY_FINDINGS,
        ...ADMIN_DATA_INTEGRITY_FIX,
        '@role:admin',
        '@outcome:display',
        '@responsive:dashboard',
        `@responsive-scenario:${scenario.catalogKey}`,
        `@responsive-batch:${batchForScenario(scenario.catalogKey)}`,
        `@viewport:${profile}`,
      ],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (the localized Dashboard is the entry point; integrity is reached through its sidebar or drawer)
      await setup(page);
      await enterIntegrity(page, profile);
      const { finding, modal, confirm } = await openPreview(page);
      await expect(finding).toContainText('Acta de entrega');
      await assertResponsiveScenario(page, testInfo, scenario, {
        profile,
        priorityLocator: finding,
        modalLocator: modal,
        finalActionLocator: confirm,
      });
    });
  });
}
