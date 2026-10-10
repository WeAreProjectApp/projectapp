/**
 * E2E tests for admin hour-package deletion.
 *
 * Covers: the row menu's delete entry opens the ConfirmModal, confirming sends
 * DELETE and removes the row, cancelling keeps the row.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_HOUR_PACKAGES_DELETE } from '../helpers/flow-tags.js';
import { chooseRowAction } from '../helpers/row-actions.js';

const deleteFirstPackage = {
  kebab: 'hour-package-actions-1',
  menu: 'hour-package-actions-modal',
  action: 'hour-package-delete-1',
};

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const colPackages = [
  { id: 1, nationality: 'COL', currency: 'COP', name_es: 'Paquete Ágil', name_en: 'Agile Pack', hours: 20, hourly_rate: '90000.00', discount_percent: 0, is_active: true, order: 1, updated_at: '2026-07-01T10:00:00Z' },
  { id: 2, nationality: 'COL', currency: 'COP', name_es: 'Paquete Pro', name_en: 'Pro Pack', hours: 60, hourly_rate: '90000.00', discount_percent: 10, is_active: true, order: 2, updated_at: '2026-07-01T10:00:00Z' },
];

function setupMock(page) {
  let deleteCalled = false;
  mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'hour-packages/admin/' && route.request().method() === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(colPackages) };
    }
    if (apiPath === 'hour-packages/admin/1/delete/' && route.request().method() === 'DELETE') {
      deleteCalled = true;
      return { status: 204, body: '' };
    }
    return null;
  });
  return { wasDeleteCalled: () => deleteCalled };
}

test.describe('Admin Hour Packages Delete', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9700, role: 'admin', is_staff: true } });
  });

  test('confirming the modal deletes the package and removes the row', {
    tag: [...ADMIN_HOUR_PACKAGES_DELETE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const { wasDeleteCalled } = setupMock(page);
    await page.goto('/panel/hour-packages');

    const table = page.locator('table');
    await expect(table.getByRole('link', { name: 'Paquete Ágil', exact: true })).toBeVisible();

    await chooseRowAction(page, deleteFirstPackage);
    const dialog = page.getByRole('dialog', { name: 'Eliminar paquete' });
    await expect(dialog.getByText('¿Eliminar "Paquete Ágil"?')).toBeVisible();
    await dialog.getByTestId('confirm-modal-confirm').click();

    await expect(table.getByRole('link', { name: 'Paquete Ágil', exact: true })).toBeHidden();
    await expect(table.getByRole('link', { name: 'Paquete Pro', exact: true })).toBeVisible();
    expect(wasDeleteCalled()).toBe(true);
  });

  test('cancelling the modal keeps the package', {
    tag: [...ADMIN_HOUR_PACKAGES_DELETE, '@role:admin'],
  }, async ({ page }) => {
    const { wasDeleteCalled } = setupMock(page);
    await page.goto('/panel/hour-packages');

    const table = page.locator('table');
    await chooseRowAction(page, deleteFirstPackage);
    const dialog = page.getByRole('dialog', { name: 'Eliminar paquete' });
    await expect(dialog.getByText('¿Eliminar "Paquete Ágil"?')).toBeVisible();
    await dialog.getByRole('button', { name: 'Cancelar' }).click();

    await expect(dialog).toBeHidden();
    await expect(table.getByRole('link', { name: 'Paquete Ágil', exact: true })).toBeVisible();
    expect(wasDeleteCalled()).toBe(false);
  });
});
