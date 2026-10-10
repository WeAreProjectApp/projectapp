/**
 * E2E tests for the Linktrees panel module.
 *
 * Covers flow: admin-linktrees
 *   - Creating a linktree (name + handle) lands on the editor.
 *   - Saving buttons that violate tier cardinality surfaces the backend error.
 *   - Deleting a linktree after confirmation.
 *   - Each row leads with an actions button that opens its menu in place.
 *   - Assigning a linktree as a QR card destination.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_LINKTREES } from '../helpers/flow-tags.js';
import { openRowMenu } from '../helpers/row-actions.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';

test.setTimeout(60_000);

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const TREE_ID = '11111111-1111-1111-1111-111111111111';

const existingTree = {
  id: TREE_ID,
  handle: 'gustavo',
  name: 'Gustavo',
  kind: 'personal',
  display_name: 'Gustavo Pérez',
  role: 'Co Founder & CEO',
  bio: '',
  avatar: null,
  claim_line_1: '',
  claim_line_2: '',
  badge_text: '',
  footer_tagline: 'DISEÑO · CÓDIGO · RESULTADOS',
  show_brand_header: true,
  pwa_enabled: true,
  pwa_title: 'Guarda la tarjeta en tu teléfono',
  pwa_description: 'Queda como un ícono en tu pantalla de inicio.',
  vcard_first_name: 'Gustavo',
  vcard_last_name: 'Pérez',
  vcard_org: 'ProjectApp.',
  vcard_email: 'team@projectapp.co',
  vcard_tel: '+573238122373',
  vcard_url: 'https://projectapp.co',
  is_active: true,
  public_path: '/lk/@gustavo',
  buttons_count: 1,
  buttons: [
    {
      id: 1, tier: 'primary', action: 'linkedin', label: 'Conectemos en LinkedIn',
      href: 'https://linkedin.com/in/x', icon: '', resolved_icon: 'linkedin',
      kind: 'url', is_pending: false, order: 0, is_active: true,
    },
  ],
  created_at: '2026-08-12T10:00:00Z',
  updated_at: '2026-08-12T10:00:00Z',
};

function countActivePrimaries(buttons) {
  return (buttons || []).filter((b) => (b.is_active ?? true) && b.tier === 'primary').length;
}

function setupLinktreesMock(page, { trees = [] } = {}) {
  let store = [...trees];
  return mockApi(page, async ({ apiPath, route }) => {
    const method = route.request().method();
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'linktrees/admin/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(store) };
    }
    if (apiPath === 'linktrees/admin/create/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      const created = {
        ...existingTree,
        id: '22222222-2222-2222-2222-222222222222',
        buttons: [],
        buttons_count: 0,
        ...payload,
        handle: String(payload.handle || '').replace(/^@/, '').toLowerCase(),
      };
      created.public_path = `/lk/@${created.handle}`;
      store = [created, ...store];
      return { status: 201, contentType: 'application/json', body: JSON.stringify(created) };
    }
    if (apiPath.match(/^linktrees\/admin\/[^/]+\/update\/$/) && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      if (payload.buttons && payload.buttons.length && countActivePrimaries(payload.buttons) !== 1) {
        return {
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ buttons: ['Debe haber exactamente 1 botón principal (tier primary).'] }),
        };
      }
      const id = apiPath.split('/')[2];
      store = store.map((t) => (t.id === id ? { ...t, ...payload } : t));
      const updated = store.find((t) => t.id === id) || { ...existingTree, ...payload };
      return { status: 200, contentType: 'application/json', body: JSON.stringify(updated) };
    }
    if (apiPath === `linktrees/admin/${TREE_ID}/logo/`) {
      const logo = method === 'DELETE' ? null : 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aMfsAAAAASUVORK5CYII=';
      store = store.map((tree) => ({ ...tree, logo }));
      return { status: 200, contentType: 'application/json', body: JSON.stringify(store[0]) };
    }
    if (apiPath.match(/^linktrees\/admin\/[^/]+\/delete\/$/) && method === 'DELETE') {
      const id = apiPath.split('/')[2];
      store = store.filter((t) => t.id !== id);
      return { status: 204, contentType: 'application/json', body: '' };
    }
    if (apiPath.match(/^linktrees\/admin\/[^/]+\/$/) && method === 'GET') {
      const id = apiPath.split('/')[2];
      const tree = store.find((t) => t.id === id) || existingTree;
      return { status: 200, contentType: 'application/json', body: JSON.stringify(tree) };
    }
    return null;
  });
}

test.describe('Admin Linktrees', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8900, role: 'admin', is_staff: true } });
  });

  test('creates a linktree and lands on the editor', {
    tag: [...ADMIN_LINKTREES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (admin panel E2E specs enter routes directly; sidebar navigation is covered by layout specs)
    await setupLinktreesMock(page, { trees: [] });
    await page.goto('/panel/linktrees');
    await page.waitForLoadState('domcontentloaded');

    await page.getByTestId('linktree-new').click();
    await page.getByTestId('linktree-name-input').fill('Gustavo');
    await page.getByTestId('linktree-handle-input').fill('@Gustavo');
    await page.getByTestId('linktree-save').click();

    await expect(page).toHaveURL(/\/panel\/linktrees\/.+\/edit/);
    await expect(page.getByTestId('linktree-public-link')).toContainText('/lk/@gustavo');
  });

  test('violating the one-primary rule surfaces the backend error', {
    tag: [...ADMIN_LINKTREES, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupLinktreesMock(page, { trees: [existingTree] });
    await page.goto(`/panel/linktrees/${TREE_ID}/edit`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByTestId('linktree-button-row-0')).toBeVisible();
    await page.getByTestId('linktree-add-button').click();
    await page.locator('#lt-btn-tier-1').selectOption('primary');
    await page.getByTestId('linktree-button-label-1').fill('Segundo principal');
    await page.getByTestId('linktree-save').click();

    await expect(page.getByTestId('linktree-buttons-error')).toContainText('exactamente 1 botón principal');
  });

  test('confirming the delete removes the linktree', {
    tag: [...ADMIN_LINKTREES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupLinktreesMock(page, { trees: [existingTree] });
    await page.goto('/panel/linktrees');
    await page.waitForLoadState('domcontentloaded');

    await page.getByTestId(`linktree-actions-${TREE_ID}`).click();
    await page.getByTestId(`linktree-delete-${TREE_ID}`).click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Sin linktrees todavía')).toBeVisible();
    await expect(page.getByTestId(`linktree-row-${TREE_ID}`)).not.toBeVisible();
  });

  test('renders row actions as a leading menu that opens without navigating', {
    tag: [...ADMIN_LINKTREES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (admin panel E2E specs enter routes directly; this test isolates the row-actions layout and menu contract)
    await setupLinktreesMock(page, { trees: [existingTree] });
    await page.goto('/panel/linktrees', { waitUntil: 'domcontentloaded' });

    const actionsHeader = page.getByTestId('linktree-row-actions-header');
    await expect(actionsHeader).toBeVisible();
    const leadingHeaders = await actionsHeader.evaluate((header) => (
      Array.from(header.parentElement.children).slice(0, 2).map((cell) => ({
        testId: cell.getAttribute('data-testid'),
        label: cell.getAttribute('aria-label'),
        text: cell.textContent.trim(),
      }))
    ));
    expect(leadingHeaders).toEqual([
      { testId: 'linktree-row-actions-header', label: 'Acciones', text: '' },
      { testId: null, label: null, text: 'Nombre' },
    ]);
    await expectNoBlankBand(actionsHeader.locator('xpath=ancestor::table'));

    const kebab = page.getByTestId(`linktree-actions-${TREE_ID}`);
    await expect(kebab).toHaveAccessibleName('Acciones de Gustavo');
    await expect(kebab).toHaveText('');

    const listUrl = page.url();
    await openRowMenu(page, { kebab: `linktree-actions-${TREE_ID}`, menu: 'linktree-actions-modal' });
    const menu = page.getByTestId('linktree-actions-modal');
    await expect(menu.getByRole('heading')).toHaveText('Gustavo');
    await expect(menu.getByRole('listitem')).toHaveText(['Editar', 'Eliminar']);
    await expect(menu.getByTestId(`linktree-edit-${TREE_ID}`)).toHaveAttribute('href', new RegExp(`/panel/linktrees/${TREE_ID}/edit$`));
    await expect(page).toHaveURL(listUrl);
  });

  test('assigns a linktree as QR card destination', {
    tag: [...ADMIN_LINKTREES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const card = {
      id: '33333333-3333-3333-3333-333333333333',
      name: 'Tarjeta evento X',
      destination_url: '',
      destination_type: 'url',
      linktree: null,
      linktree_handle: null,
      linktree_name: null,
      is_active: true,
      created_at: '2026-08-01T10:00:00Z',
    };
    let cards = [card];
    await mockApi(page, async ({ apiPath, route }) => {
      const method = route.request().method();
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'linktrees/admin/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify([existingTree]) };
      }
      if (apiPath === 'qr-cards/admin/' && method === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(cards) };
      }
      if (apiPath.match(/^qr-cards\/admin\/[^/]+\/update\/$/) && method === 'PATCH') {
        const payload = route.request().postDataJSON();
        cards = cards.map((c) => (c.id === card.id ? {
          ...c,
          ...payload,
          linktree_handle: payload.linktree ? existingTree.handle : null,
          linktree_name: payload.linktree ? existingTree.name : null,
        } : c));
        return { status: 200, contentType: 'application/json', body: JSON.stringify(cards[0]) };
      }
      return null;
    });

    await page.goto('/panel/qr-cards');
    await page.waitForLoadState('domcontentloaded');

    await page.getByTestId(`qr-card-actions-${card.id}`).click();
    await page.getByTestId(`qr-card-edit-${card.id}`).click();
    await page.getByTestId('qr-card-destination-type').getByRole('tab', { name: 'Linktree' }).click();
    await page.getByTestId('qr-card-linktree-select').selectOption(TREE_ID);
    await page.getByTestId('qr-card-save').click();

    await expect(page.getByText('Linktree: @gustavo')).toBeVisible();
  });
});


test.describe('Linktree branding', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8900, role: 'admin', is_staff: true } });
    await setupLinktreesMock(page, { trees: [existingTree] });
  });

  test('saves custom colors and font and keeps them after reopening', {
    tag: ['@flow:admin-linktree-branding', '@outcome:success'],
  }, async ({ page }) => {
    await page.goto(`/en-us/panel/linktrees/${TREE_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('textbox', { name: 'Fondo hexadecimal', exact: true }).fill('#abcdef');
    await page.getByRole('combobox', { name: 'Tipografía', exact: true }).selectOption('Montserrat');
    await expect(page.getByTestId('linktree-card')).toHaveCSS('background-color', 'rgb(171, 205, 239)');
    await page.getByTestId('linktree-save').click();
    await expect(page.getByTestId('linktree-unsaved-notice')).toHaveCount(0);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('textbox', { name: 'Fondo hexadecimal', exact: true })).toHaveValue('#abcdef');
    await expect(page.getByRole('combobox', { name: 'Tipografía', exact: true })).toHaveValue('Montserrat');
  });

  test('loads an additional Google Fonts family', {
    tag: ['@flow:admin-linktree-branding', '@outcome:success'],
  }, async ({ page }) => {
    await page.route('https://fonts.googleapis.com/css2?family=Lora*', (route) => route.fulfill({
      status: 200, contentType: 'text/css', body: '@font-face {font-family: Lora; src: local(serif);}',
    }));
    await page.goto(`/en-us/panel/linktrees/${TREE_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('textbox', { name: 'Añadir desde Google Fonts' }).fill('Lora');
    await page.getByRole('button', { name: 'Cargar tipografía' }).click();
    await expect(page.getByRole('combobox', { name: 'Tipografía', exact: true })).toHaveValue('Lora');
    await expect(page.getByTestId('linktree-card')).toHaveCSS('font-family', /Lora/);
  });

  test('rejects an unknown Google family without replacing the current font', {
    tag: ['@flow:admin-linktree-branding', '@outcome:error'],
  }, async ({ page }) => {
    await page.route('https://fonts.googleapis.com/css2?family=Missing*', (route) => route.fulfill({ status: 400, body: 'Unknown font' }));
    await page.goto(`/en-us/panel/linktrees/${TREE_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('textbox', { name: 'Añadir desde Google Fonts' }).fill('Missing Family');
    await page.getByRole('button', { name: 'Cargar tipografía' }).click();
    await expect(page.getByText('No se encontró esa familia en Google Fonts. Verifica el nombre.')).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Tipografía', exact: true })).toHaveValue('Ubuntu');
  });

  test('reports a Google Fonts connection failure', {
    tag: ['@flow:admin-linktree-branding', '@outcome:failure'],
  }, async ({ page }) => {
    await page.route('https://fonts.googleapis.com/css2?family=Lora*', (route) => route.abort());
    await page.goto(`/en-us/panel/linktrees/${TREE_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('textbox', { name: 'Añadir desde Google Fonts' }).fill('Lora');
    await page.getByRole('button', { name: 'Cargar tipografía' }).click();
    await expect(page.getByText('No se pudo conectar con Google Fonts. Inténtalo de nuevo.')).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Tipografía', exact: true })).toHaveValue('Ubuntu');
  });

  test('uploads and removes the brand logo', {
    tag: ['@flow:admin-linktree-branding', '@outcome:success'],
  }, async ({ page }) => {
    await page.goto(`/en-us/panel/linktrees/${TREE_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Logo de marca').setInputFiles({ name: 'logo.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aMfsAAAAASUVORK5CYII=', 'base64') });
    await expect(page.getByTestId('linktree-brand-logo')).toHaveAttribute('src', /^data:image/);
    await page.getByRole('button', { name: 'Quitar logo' }).click();
    await expect(page.getByTestId('linktree-brand-logo')).toHaveCount(0);
    await expect(page.getByTestId('linktree-card')).toContainText('ProjectApp.');
  });

  test('opens the editor from the list and displays the existing appearance on mobile', {
    tag: ['@flow:admin-linktree-branding', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the list is the entry point; the editor is reached through its real Edit action)
    await page.setViewportSize({ width: 412, height: 915 });
    await page.goto('/en-us/panel/linktrees', { waitUntil: 'domcontentloaded' });
    await page.getByTestId(`linktree-actions-${TREE_ID}`).click();
    await page.getByTestId(`linktree-edit-${TREE_ID}`).click();
    await expect(page.getByRole('combobox', { name: 'Tipografía', exact: true })).toHaveValue('Ubuntu');
    await expect(page.getByTestId('linktree-card')).toContainText('Gustavo Pérez');
    await expect(page.getByTestId('linktree-card')).toHaveCSS('background-color', 'rgb(0, 23, 19)');
  });
});
