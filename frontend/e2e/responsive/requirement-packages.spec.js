// qa: draft-unvalidated (2026-11-12 — app not running)
/**
 * R-requirement-packages-01: the manual evaluation queue must keep its
 * matching request reachable at every supported Panel viewport.
 */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  mockRequirementPackagesWorkspace,
  REQUIREMENT_PACKAGE_PROJECT,
} from '../helpers/requirement-packages-workspace.js';
import { setPlatformAuth, mockPlatformClient } from '../helpers/platform-auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const scenario = getResponsiveScenario('frontend/pages/panel/requirement-packages/index.vue');
const platformScenario = getResponsiveScenario('frontend/pages/platform/projects/[id]/packages.vue');
const personalClientToken = 'eyJhbGciOiJub25lIn0.eyJ1c2VyX2lkIjo5MDAyfQ.signature';

const queueEntryByProfile = Object.freeze({
  compact: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Solicitudes por tallas', exact: true }).click(); },
  portrait: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Solicitudes por tallas', exact: true }).click(); },
  landscape: (page) => page.getByRole('link', { name: 'Solicitudes por tallas', exact: true }).click(),
  desktop: (page) => page.getByRole('link', { name: 'Solicitudes por tallas', exact: true }).click(),
  wide: (page) => page.getByRole('link', { name: 'Solicitudes por tallas', exact: true }).click(),
});

async function setupQueue(page) {
  await setAuthLocalStorage(page, {
    token: 'e2e-responsive-panel-token',
    userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
  });
  await mockRequirementPackagesWorkspace(page, { admin: true });
}

async function setupPlatformPackages(page) {
  await setPlatformAuth(page, { user: mockPlatformClient, accessToken: personalClientToken });
  await mockRequirementPackagesWorkspace(page, { user: mockPlatformClient });
}

async function openPlatformPackages(page) {
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' });
  await page.getByTestId(`project-row-${REQUIREMENT_PACKAGE_PROJECT.id}`).click();
  await expect(page.getByRole('heading', { name: REQUIREMENT_PACKAGE_PROJECT.name, exact: true })).toHaveText(REQUIREMENT_PACKAGE_PROJECT.name);
  await page.getByRole('link', { name: 'Paquetes de requerimientos', exact: true }).click();
  await expect(page).toHaveURL(/\/platform\/projects\/1\/packages$/);
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`requirement packages responsive · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('filters a queued request without horizontal overflow', {
      tag: ['@flow:admin-requirement-packages-queue', '@outcome:display', '@role:admin', '@responsive:projects', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      // Bug caught: a responsive Panel menu hides the queue, or its matching request overflows beyond the viewport.
      await setupQueue(page);
      // quality: allow-deep-link (the authenticated Panel home is the shell entry; this test reaches the queue through responsive navigation)
      await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
      await queueEntryByProfile[profile](page);
      await expect(page.getByRole('heading', { name: 'Solicitudes por tallas', exact: true })).toHaveText('Solicitudes por tallas');

      await page.getByLabel('Buscar proyecto o solicitud').fill('Atlas');
      const request = page.getByText('Mostrar el estado del pedido', { exact: true });
      await expect(request).toHaveText('Mostrar el estado del pedido');
      await assertResponsiveScenario(page, testInfo, scenario, { profile, priorityLocator: request });
    });

    test('keeps package examples and catalog usable from the client project space', {
      tag: ['@flow:platform-requirement-packages-purchase', '@outcome:display', '@role:platform-client', '@responsive:clients', `@responsive-scenario:${platformScenario.catalogKey}`, `@responsive-batch:${batchForScenario(platformScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      // Bug caught: a narrow project space hides package examples or the package the client needs to review.
      await setupPlatformPackages(page);
      // quality: allow-deep-link (the authenticated project list is the shell entry; this test follows the visible project and packages links)
      await openPlatformPackages(page);

      const xsExample = page.getByTestId('package-size-XS');
      await expect(xsExample).toContainText('Cambiar el texto de bienvenida de Atlas');
      await expect(page.getByText('Paquete Atlas', { exact: true })).toBeVisible();
      await assertResponsiveScenario(page, testInfo, platformScenario, { profile, priorityLocator: xsExample });
    });
  });
}
