/** Delete specs catch catalogue rows disappearing without confirmation or failure feedback. */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { mockRequirementPackages } from '../helpers/requirement-packages.js';
import { ADMIN_HOUR_PACKAGES_DELETE } from '../helpers/flow-tags.js';
import { chooseRowAction } from '../helpers/row-actions.js';

const deleteAgile = { kebab: 'hour-package-actions-1', menu: 'hour-package-actions-modal', action: 'hour-package-delete-1' };
test.describe('Admin requirement package deletion', () => {
  test.setTimeout(60_000);
  test.beforeEach(async ({ page }) => setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9700, role: 'admin', is_staff: true } }));

  test('cancelling deletion keeps Ágil in the catalog', { tag: [...ADMIN_HOUR_PACKAGES_DELETE, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: cancelling a destructive dialog still removes the package.
    const capture = await mockRequirementPackages(page);
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await chooseRowAction(page, deleteAgile);
    await page.getByRole('button', { name: 'Cancelar' }).click();
    await expect(page.getByRole('table')).toContainText('Ágil');
    expect(capture.deleted).toBeUndefined();
  });

  test('confirming deletion removes Ágil from the catalog', { tag: [...ADMIN_HOUR_PACKAGES_DELETE, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: confirmation sends delete but leaves a stale package row.
    const capture = await mockRequirementPackages(page);
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await chooseRowAction(page, deleteAgile);
    await page.getByTestId('confirm-modal-confirm').click();
    expect(capture.deleted).toBe(true);
    await expect(page.getByRole('table')).not.toContainText('Ágil');
    await expect(page.getByRole('table')).toContainText('Pro');
  });

  test('delete failure retains Ágil with an error', { tag: [...ADMIN_HOUR_PACKAGES_DELETE, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
    // Bug caught: a rejected delete removes the package from the visible catalog.
    await mockRequirementPackages(page, { deleteStatus: 500 });
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await chooseRowAction(page, deleteAgile);
    await page.getByTestId('confirm-modal-confirm').click();
    await expect(page.getByText('No se pudo eliminar el paquete.')).toBeVisible();
    await expect(page.getByRole('table')).toContainText('Ágil');
  });
});
