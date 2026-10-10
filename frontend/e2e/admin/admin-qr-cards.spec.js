/**
 * E2E tests for the Tarjetas QR panel module.
 *
 * Covers flow: admin-qr-cards
 *   - Creating a card with only a name (destination left empty).
 *   - Editing a card's destination_url.
 *   - Toggling a card's active state.
 *   - Deleting a card requires confirmation; cancelling keeps it, confirming removes it.
 *   - Each row leads with an actions button that opens its menu in place.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_QR_CARDS } from '../helpers/flow-tags.js';
import { chooseRowAction, openRowMenu } from '../helpers/row-actions.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';

test.setTimeout(60_000);

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const existingCard = {
  id: '11111111-1111-1111-1111-111111111111',
  name: 'Tarjeta evento X',
  destination_url: '',
  is_active: true,
  created_at: '2026-08-01T10:00:00Z',
};

function setupQrCardsMock(page, { cards = [] } = {}) {
  let store = [...cards];
  return mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'linktrees/admin/' && route.request().method() === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    if (apiPath === 'qr-cards/admin/' && route.request().method() === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(store) };
    }
    if (apiPath === 'qr-cards/admin/create/' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON();
      const created = {
        id: '22222222-2222-2222-2222-222222222222',
        is_active: true,
        destination_url: '',
        created_at: '2026-08-02T10:00:00Z',
        ...payload,
      };
      store = [created, ...store];
      return { status: 201, contentType: 'application/json', body: JSON.stringify(created) };
    }
    if (apiPath.match(/^qr-cards\/admin\/[^/]+\/update\/$/) && route.request().method() === 'PATCH') {
      const payload = route.request().postDataJSON();
      const id = apiPath.split('/')[2];
      store = store.map((c) => (c.id === id ? { ...c, ...payload } : c));
      const updated = store.find((c) => c.id === id);
      return { status: 200, contentType: 'application/json', body: JSON.stringify(updated) };
    }
    if (apiPath.match(/^qr-cards\/admin\/[^/]+\/delete\/$/) && route.request().method() === 'DELETE') {
      const id = apiPath.split('/')[2];
      store = store.filter((c) => c.id !== id);
      return { status: 204, contentType: 'application/json', body: '' };
    }
    return null;
  });
}

test.describe('Admin QR Cards', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8900, role: 'admin', is_staff: true } });
  });

  test('creates a new card with only a name', {
    tag: [...ADMIN_QR_CARDS, '@role:admin', '@outcome:success', '@responsive:content'],
  }, async ({ page }) => {
    await setupQrCardsMock(page, { cards: [] });
    await page.goto('/panel/qr-cards');
    await page.waitForLoadState('domcontentloaded');

    await page.getByTestId('qr-card-new').click();
    await page.getByTestId('qr-card-name-input').fill('Tarjeta evento X');
    await page.getByTestId('qr-card-save').click();

    await expect(page.getByText('Tarjeta evento X')).toBeVisible();
  });

  test('editing destination_url updates the row', {
    tag: [...ADMIN_QR_CARDS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupQrCardsMock(page, { cards: [existingCard] });
    await page.goto('/panel/qr-cards');
    await page.waitForLoadState('domcontentloaded');

    await page.getByTestId(`qr-card-actions-${existingCard.id}`).click();
    await page.getByTestId(`qr-card-edit-${existingCard.id}`).click();
    await page.getByTestId('qr-card-destination-input').fill('https://example.com/landing');
    await page.getByTestId('qr-card-save').click();

    await expect(page.getByText('https://example.com/landing')).toBeVisible();
  });

  test('toggling active state calls the update endpoint', {
    tag: [...ADMIN_QR_CARDS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupQrCardsMock(page, { cards: [existingCard] });
    await page.goto('/panel/qr-cards');
    await page.waitForLoadState('domcontentloaded');

    await page.getByTestId(`qr-card-toggle-${existingCard.id}`).click();

    await expect(page.getByTestId(`qr-card-toggle-${existingCard.id}`)).toHaveAttribute('aria-checked', 'false');
  });

  test('cancelling the delete confirmation keeps the card', {
    tag: [...ADMIN_QR_CARDS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (admin panel E2E specs enter routes directly; sidebar navigation is covered by layout specs)
    await setupQrCardsMock(page, { cards: [existingCard] });
    await page.goto('/panel/qr-cards');
    await page.waitForLoadState('domcontentloaded');

    await chooseRowAction(page, {
      kebab: `qr-card-actions-${existingCard.id}`,
      menu: 'qr-card-actions-modal',
      action: `qr-card-delete-${existingCard.id}`,
    });
    const confirmDialog = page.getByRole('dialog', { name: 'Eliminar tarjeta' });
    await expect(confirmDialog).toContainText('dejará de funcionar');
    await confirmDialog.getByRole('button', { name: 'Cancelar', exact: true }).click();

    await expect(confirmDialog).toHaveCount(0);
    await expect(page.getByTestId(`qr-card-row-${existingCard.id}`)).toBeVisible();
  });

  test('confirming the delete removes the card', {
    tag: [...ADMIN_QR_CARDS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupQrCardsMock(page, { cards: [existingCard] });
    await page.goto('/panel/qr-cards');
    await page.waitForLoadState('domcontentloaded');

    await page.getByTestId(`qr-card-actions-${existingCard.id}`).click();
    await page.getByTestId(`qr-card-delete-${existingCard.id}`).click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Sin tarjetas todavía')).toBeVisible();
    await expect(page.getByTestId(`qr-card-row-${existingCard.id}`)).not.toBeVisible();
  });

  test('renders row actions as a leading menu that opens without navigating', {
    tag: [...ADMIN_QR_CARDS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (admin panel E2E specs enter routes directly; this test isolates the row-actions layout and menu contract)
    await setupQrCardsMock(page, { cards: [existingCard] });
    await page.goto('/panel/qr-cards', { waitUntil: 'domcontentloaded' });

    const actionsHeader = page.getByTestId('qr-card-row-actions-header');
    await expect(actionsHeader).toBeVisible();
    const leadingHeaders = await actionsHeader.evaluate((header) => (
      Array.from(header.parentElement.children).slice(0, 2).map((cell) => ({
        testId: cell.getAttribute('data-testid'),
        label: cell.getAttribute('aria-label'),
        text: cell.textContent.trim(),
      }))
    ));
    expect(leadingHeaders).toEqual([
      { testId: 'qr-card-row-actions-header', label: 'Acciones', text: '' },
      { testId: null, label: null, text: 'Nombre' },
    ]);
    await expectNoBlankBand(actionsHeader.locator('xpath=ancestor::table'));

    const kebab = page.getByTestId(`qr-card-actions-${existingCard.id}`);
    await expect(kebab).toHaveAccessibleName('Acciones de Tarjeta evento X');
    await expect(kebab).toHaveText('');

    const listUrl = page.url();
    await openRowMenu(page, { kebab: `qr-card-actions-${existingCard.id}`, menu: 'qr-card-actions-modal' });
    const menu = page.getByTestId('qr-card-actions-modal');
    await expect(menu.getByRole('heading')).toHaveText('Tarjeta evento X');
    await expect(menu.getByRole('listitem')).toHaveText(['Descargar QR', 'Editar', 'Eliminar']);
    await expect(page).toHaveURL(listUrl);
  });
});
