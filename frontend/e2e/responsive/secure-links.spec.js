/** R-communications-03: secure-link cards and the detail modal must remain usable across the panel profiles. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { chooseSecureLinkType, json, revealedContent, secureLinkRow, secureLinkTypes } from '../helpers/secure-links.js';
import { viewportUse } from '../helpers/viewports.js';
import { expectCompactModal } from '../helpers/modal-layout.js';
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js';

test.setTimeout(60_000);

const secureLinksScenario = getResponsiveScenario('frontend/pages/panel/secure-links/index.vue');
const row = secureLinkRow({ folder: 902, title: 'Credenciales responsive con un título largo sin espacios_para_probar_el_ajuste' });
const folderRoot = {
  id: 901,
  name: 'Cliente responsive',
  parent: null,
  order: 0,
  client: null,
  project: null,
  managed_project: null,
  folder_kind: 'manual',
  is_archived: false,
  is_read_only: false,
  link_count: 0,
  archived_link_count: 0,
};
const folderChild = { ...folderRoot, id: 902, name: 'Accesos responsive', parent: folderRoot.id, link_count: 1 };
const folderNavigation = {
  totals: { active: { folders: 2, documents: 1 }, archived: { folders: 0, documents: 0 } },
  unassigned: {
    project: { active: { folders: 2, documents: 1 }, archived: { folders: 0, documents: 0 } },
    client: { active: { folders: 2, documents: 1 }, archived: { folders: 0, documents: 0 } },
  },
  projects: [],
  clients: [],
};

async function installSecureLinksMock(page) {
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'panel/dashboard/' && method === 'GET') {
      return json({ finance: null, proposals: { total_proposals: 0, by_status: {}, recent: [] }, additional_modules: {}, operations: {}, attention: [] });
    }
    if (apiPath === 'secure-links/public/types/') return json({ types: secureLinkTypes });
    if (apiPath === 'secure-links/folders/' && method === 'GET') {
      return json({ folders: [folderRoot, folderChild], navigation: folderNavigation });
    }
    if (apiPath === 'secure-links/' && method === 'GET') {
      return json({ results: [row], count: 1, page: 1, page_size: 25, counts: { active: 1, consumed: 0, expired: 0, revoked: 0, all: 1 }, lifecycle_counts: { ready: 1, sent: 0, opened: 0, expired: 0, revoked: 0, all: 1 }, unopened_received: 0, public_create_url: 'http://localhost:3000/es-co/secure-link' });
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

const visibleFolders = (page) => expect(page.getByTestId('secure-folders-sidebar').filter({ visible: true })).toBeVisible();
const revealFoldersByProfile = Object.freeze({
  compact: (page) => page.getByTestId('secure-folders-open').click(),
  portrait: (page) => page.getByTestId('secure-folders-open').click(),
  landscape: visibleFolders,
  desktop: visibleFolders,
  wide: visibleFolders,
});

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`secure links catalog · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test('opens a secure link from a nested folder', {
      tag: ['@flow:admin-secure-link-manage', '@outcome:display', '@responsive:communications', `@responsive-scenario:${secureLinksScenario.catalogKey}`, `@responsive-batch:${batchForScenario(secureLinksScenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setAuthLocalStorage(page, { token: 'secure-links-responsive-token', userAuth: { id: 9002, role: 'admin', is_staff: true, is_superuser: true } });
      await installSecureLinksMock(page);
      // quality: allow-deep-link (the authenticated panel home is the shell entry; this test reaches Enlaces seguros through the visible responsive navigation)
      await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
      await enterByProfile[profile](page);
      await revealFoldersByProfile[profile](page);
      await page.getByText(folderRoot.name, { exact: true }).filter({ visible: true }).click();
      const child = page.getByTestId(`secure-folder-child-${folderChild.id}`);
      await expect(child).toHaveText(`${folderChild.name} · 1`);
      await child.click();
      await expect(page.getByTestId(`folder-breadcrumb-${folderRoot.id}`)).toHaveText(folderRoot.name);
      await expect.poll(() => new URL(page.url()).searchParams.get('folder')).toBe(String(folderChild.id));
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

    // Bug caught: the floating Custom listbox could be clipped outside a compact panel viewport.
    test('keeps custom fields usable in the create modal', {
      tag: ['@flow:admin-secure-link-create', '@outcome:display', '@outcome:error', '@responsive:communications', `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setAuthLocalStorage(page, { token: 'secure-links-responsive-token', userAuth: { id: 9002, role: 'admin', is_staff: true, is_superuser: true } });
      await installSecureLinksMock(page);
      // quality: allow-deep-link (the panel home is the shell entry; navigation opens the module and its create modal)
      await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
      await enterByProfile[profile](page);
      await page.getByTestId('secure-links-new').click();
      // Language and validity share one row inside the 42rem form panel.
      await expectCompactModal(page.getByRole('dialog'), page.viewportSize(), {
        lines: [{ fields: [page.getByTestId('secure-link-language'), page.getByTestId('secure-link-validity')] }],
      });
      await chooseSecureLinkType(page, { name: 'Personalizado' });
      await page.getByTestId('secure-link-title').fill('Referencia');
      await page.getByTestId('secure-link-field-custom_name').fill('Instrucciones');
      await expect(page.getByTestId('secure-link-field-custom_name')).toHaveValue('Instrucciones');
      await page.getByTestId('secure-link-save').click();

      const modal = page.getByTestId('secure-link-form');
      await expect(modal.getByText('Este campo es obligatorio.')).toHaveText('Este campo es obligatorio.');
      await expect(page.getByTestId('secure-link-field-content')).toBeFocused();
      await assertResponsiveScenario(page, testInfo, secureLinksScenario, {
        profile, modalLocator: modal, finalActionLocator: modal.getByTestId('secure-link-save'),
      });
    });
  });
}
