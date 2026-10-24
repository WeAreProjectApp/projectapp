/** R-platform-help-01: every supported viewport reaches the platform-help editor through its real panel navigation. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const platformHelpScenario = getResponsiveScenario('frontend/pages/panel/platform/help.vue');
const platformHelpTour = {
  id: 91,
  slug: 'platform-basics',
  context: 'general',
  kind: 'onboarding',
  priority: 10,
  is_active: true,
  version: 1,
  published_revision: 1,
  content: {
    title_es: 'Conoce tu espacio',
    title_en: 'Know your space',
    steps: [{ target: 'projects', title_es: 'Tus proyectos', title_en: 'Your projects', description_es: 'Aquí ves el avance.', description_en: 'Track progress here.' }],
  },
};

async function setupPlatformHelp(page) {
  await setAuthLocalStorage(page, { token: 'platform-help-responsive', userAuth: { id: 91, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method }) => {
    const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'help-admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'platform/help/settings/' && method === 'GET') return json({ tour_enabled: true, video_enabled: true, version: 1 });
    if (apiPath === 'platform/help/admin/tours/' && method === 'GET') return json({ results: [platformHelpTour], targets: { projects: { context: 'general', route: '/platform/projects' } } });
    if (apiPath === 'platform/help/clients/' && method === 'GET') return json({ results: [], page: 1, count: 0 });
    if (apiPath === 'platform/help/admin/progress/' && method === 'GET') return json({ results: [], page: 1, count: 0 });
    return null;
  });
}

const platformHelpEntryByProfile = Object.freeze({
  compact: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Ayuda de la plataforma', exact: true }).click(); },
  portrait: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Ayuda de la plataforma', exact: true }).click(); },
  landscape: (page) => page.getByRole('link', { name: 'Ayuda de la plataforma', exact: true }).click(),
  desktop: (page) => page.getByRole('link', { name: 'Ayuda de la plataforma', exact: true }).click(),
  wide: (page) => page.getByRole('link', { name: 'Ayuda de la plataforma', exact: true }).click(),
});

async function enterPlatformHelp(page, profile) {
  await page.goto('/en-us/panel', { waitUntil: 'domcontentloaded' });
  await platformHelpEntryByProfile[profile](page);
  await expect(page).toHaveURL(/\/panel\/platform\/help$/);
  await expect(page.getByTestId('platform-help-admin').getByRole('heading', { name: 'Platform help', exact: true })).toHaveText('Platform help');
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`platform help catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('platform help editor remains reachable through responsive navigation', {
      tag: ['@flow:admin-platform-help-settings', '@outcome:display', '@responsive:projects', `@responsive-scenario:${platformHelpScenario.catalogKey}`, `@responsive-batch:${batchForScenario(platformHelpScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (the authenticated panel home is the entry point; this test clicks the visible responsive Plataforma navigation)
      // Bug caught: a responsive sidebar or drawer hides the route into platform-help administration.
      await setupPlatformHelp(page);
      await enterPlatformHelp(page, profile);
      await expect(page.getByLabel('Select tour', { exact: true })).toHaveValue(String(platformHelpTour.id));
      const tourToggle = page.getByRole('switch', { name: 'Enable tours', exact: true });
      await tourToggle.click();
      await expect(tourToggle).toHaveAttribute('aria-checked', 'false');
      await tourToggle.click();
      await expect(tourToggle).toHaveAttribute('aria-checked', 'true');
      await assertResponsiveScenario(page, testInfo, platformHelpScenario, { profile });
    });
  });
}
