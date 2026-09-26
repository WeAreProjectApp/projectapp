/** R-communications-03: secure-link cards and the detail modal must remain usable across the panel profiles. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { json, revealedContent, secureLinkRow, secureLinkTypes } from '../helpers/secure-links.js';
import { viewportUse } from '../helpers/viewports.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

const secureLinksScenario = getResponsiveScenario('frontend/pages/panel/secure-links/index.vue');
const row = secureLinkRow({ title: 'Credenciales responsive con un título largo sin espacios_para_probar_el_ajuste' });

async function installSecureLinksMock(page) {
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'panel/dashboard/' && method === 'GET') {
      return json({ finance: null, proposals: { total_proposals: 0, by_status: {}, recent: [] }, additional_modules: {}, operations: {}, attention: [] });
    }
    if (apiPath === 'secure-links/public/types/') return json({ types: secureLinkTypes });
    if (apiPath === 'secure-links/' && method === 'GET') {
      return json({ results: [row], count: 1, page: 1, page_size: 25, counts: { active: 1, consumed: 0, expired: 0, revoked: 0, all: 1 }, unopened_received: 0, public_create_url: 'http://localhost:3000/es-co/secure-link' });
    }
    if (apiPath === `secure-links/${row.id}/` && method === 'GET') {
      return json({ ...row, events: [{ id: 1, kind: 'created', kind_label: 'Creado', actor_name: 'Admin', ip_address: null, details: {}, created_at: row.created_at }] });
    }
    if (apiPath === `secure-links/${row.id}/content/` && method === 'POST') return json(revealedContent);
    return null;
  });
}

const openNav = async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); };
const enterByProfile = Object.freeze({
  compact: async (page) => { await openNav(page); await page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click(); },
  portrait: async (page) => { await openNav(page); await page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click(); },
  landscape: (page) => page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click(),
  desktop: (page) => page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click(),
  wide: (page) => page.getByRole('link', { name: 'Enlaces seguros', exact: true }).click(),
});

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`secure links catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('opens a secure link detail and its content from the responsive list', {
      tag: ['@flow:admin-secure-link-manage', '@outcome:display', '@responsive:communications', `@responsive-scenario:${secureLinksScenario.catalogKey}`, `@responsive-batch:${batchForScenario(secureLinksScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setAuthLocalStorage(page, { token: 'secure-links-responsive-token', userAuth: { id: 9002, role: 'admin', is_staff: true, is_superuser: true } });
      await installSecureLinksMock(page);
      // quality: allow-deep-link (the authenticated panel home is the shell entry; this test reaches Enlaces seguros through the visible responsive navigation)
      await page.goto('/panel', { waitUntil: 'domcontentloaded' });
      await enterByProfile[profile](page);
      const title = page.getByTestId('secure-links-page').getByText(row.title, { exact: true }).filter({ visible: true });
      await expect(title).toHaveCount(1);
      await title.click();

      const modal = page.getByTestId('secure-link-detail');
      await modal.getByTestId('secure-link-view-content').click();
      await expect(modal.getByTestId('secure-link-text-service')).toHaveText('Django admin');
      await assertResponsiveScenario(page, testInfo, secureLinksScenario, {
        profile,
        modalLocator: modal,
        finalActionLocator: modal.getByTestId('secure-link-view-content'),
      });
    });
  });
}
