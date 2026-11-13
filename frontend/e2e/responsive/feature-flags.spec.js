import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { setPlatformAuth, mockPlatformClient } from '../helpers/platform-auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';
import catalog from '../../../contracts/platform-features.json' with { type: 'json' };

test.setTimeout(60_000);

const json = body => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
const adminScenario = getResponsiveScenario('frontend/pages/panel/platform/feature-flags.vue');
const unavailableScenario = getResponsiveScenario('frontend/pages/platform/unavailable.vue');

async function setupAdmin(page) {
  await setAuthLocalStorage(page, { token: 'feature-responsive', userAuth: { id: 51, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, ({ apiPath }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'feature-admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'platform/features/admin/') return json({ version: 0, features: catalog.features.map(item => ({ ...item, global_value: item.default_enabled, effective: item.default_enabled, source: 'global' })) });
    if (apiPath === 'platform/features/admin/clients/' || apiPath === 'platform/features/admin/events/') return json({ results: [], count: 0, page: 1 });
    return null;
  });
}

async function enterAdmin(page, profile) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  if (profile === 'compact' || profile === 'portrait') await page.getByRole('button', { name: 'Abrir menú', exact: true }).click();
  await page.getByRole('link', { name: 'Feature flags', exact: true }).click();
}

async function setupUnavailable(page) {
  await setPlatformAuth(page, { user: mockPlatformClient });
  await mockApi(page, ({ apiPath }) => {
    if (apiPath === 'accounts/me/') return json(mockPlatformClient);
    if (apiPath === 'platform/features/') return json({ user_id: mockPlatformClient.user_id, features: { ...Object.fromEntries(catalog.features.map(item => [item.key, item.default_enabled])), 'platform.documents': false } });
    if (apiPath === 'accounts/projects/') return json([]);
    if (apiPath === 'accounts/notifications/unread-count/') return json({ count: 0 });
    if (apiPath === 'platform/help/') return json({ tours: [], tour_enabled: false, video_enabled: false });
    return null;
  });
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`feature flag administration · ${profile}`, () => {
    test.use({ ...viewportUse(profile), locale: 'en-US' });
    test('availability choices remain usable from Panel navigation', {
      tag: ['@flow:panel-platform-feature-flags', '@outcome:display', '@role:admin', '@responsive:projects', `@responsive-scenario:${adminScenario.catalogKey}`, `@responsive-batch:${batchForScenario(adminScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setupAdmin(page);
      await enterAdmin(page, profile);
      const card = page.getByTestId('feature-platform.documents');
      await expect(card.getByTestId('feature-effective')).toHaveText('Effective value: Enabled');
      await card.getByRole('button').click();
      const option = page.getByRole('menuitem', { name: 'Disabled', exact: true });
      await expect(option).toBeVisible();
      await assertResponsiveScenario(page, testInfo, adminScenario, { profile, priorityLocator: option });
    });
  });

  test.describe(`unavailable feature · ${profile}`, () => {
    test.use(viewportUse(profile));
    test('direct access retains the disabled feature explanation', {
      tag: ['@flow:platform-feature-availability', '@outcome:error', '@role:platform-client', '@responsive:clients', `@responsive-scenario:${unavailableScenario.catalogKey}`, `@responsive-batch:${batchForScenario(unavailableScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setupUnavailable(page);
      await page.goto('/es-co/platform/documents', { waitUntil: 'domcontentloaded' });
      const explanation = page.getByTestId('platform-feature-unavailable');
      await expect(page).toHaveURL(/\/platform\/unavailable$/);
      await expect(explanation).toContainText('Esta funcionalidad está deshabilitada para tu cuenta.');
      await expect(explanation.getByRole('link', { name: 'Volver a Proyectos', exact: true })).toHaveAttribute('href', '/es-co/platform/projects');
      await assertResponsiveScenario(page, testInfo, unavailableScenario, { profile, priorityLocator: explanation });
      await explanation.getByRole('link', { name: 'Volver a Proyectos', exact: true }).click();
      await expect(page).toHaveURL(/\/platform\/projects$/);
    });
  });
}
