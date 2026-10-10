/**
 * E2E tests for admin portfolio work deletion.
 *
 * Covers: row menu button visible in list, its delete entry's confirm dialog
 * triggers the API call.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PORTFOLIO_DELETE } from '../helpers/flow-tags.js';
import { chooseRowAction } from '../helpers/row-actions.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const mockWorks = [
  { id: 1, title_es: 'Proyecto a Borrar', title_en: 'Project to Delete', slug: 'proyecto-borrar', is_published: true, order: 1, published_at: '2026-03-01T12:00:00Z', created_at: '2026-03-01T10:00:00Z' },
];

test.describe('Admin Portfolio Delete', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9200, role: 'admin', is_staff: true } });
  });

  test('renders portfolio list with delete-capable work', {
    tag: [...ADMIN_PORTFOLIO_DELETE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — the list renders a work with its delete control; the delete interaction is covered below)
    await mockApi(page, async ({ apiPath, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'portfolio/admin/' && route.request().method() === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockWorks) };
      }
      if (apiPath === 'portfolio/admin/1/delete/' && route.request().method() === 'DELETE') {
        return { status: 204, contentType: 'application/json', body: '' };
      }
      return null;
    });
    await page.goto('/panel/portfolio');

    const table = page.locator('table');
    await expect(table.getByText('Proyecto a Borrar')).toBeVisible();
    const row = table.getByRole('row', { name: /Proyecto a Borrar/ });
    await expect(row.getByTestId('portfolio-work-actions-1')).toBeVisible();
  });

  test('delete button triggers confirm dialog', {
    tag: [...ADMIN_PORTFOLIO_DELETE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let deleteApiCalled = false;
    await mockApi(page, async ({ apiPath, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'portfolio/admin/' && route.request().method() === 'GET') {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockWorks) };
      }
      if (apiPath === 'portfolio/admin/1/delete/' && route.request().method() === 'DELETE') {
        deleteApiCalled = true;
        return { status: 204, contentType: 'application/json', body: '' };
      }
      return null;
    });
    await page.goto('/panel/portfolio');

    await chooseRowAction(page, {
      kebab: 'portfolio-work-actions-1',
      menu: 'portfolio-work-actions-modal',
      action: 'portfolio-work-delete-1',
    });

    const modal = page.getByRole('dialog', { name: 'Eliminar trabajo' });
    await expect(modal).toBeVisible();
    await expect(modal.getByText('Proyecto a Borrar')).toBeVisible();

    const deletePromise = page.waitForResponse((resp) => resp.url().includes('portfolio/admin/1/delete') && resp.request().method() === 'DELETE');
    await modal.getByRole('button', { name: 'Eliminar' }).click();
    await deletePromise;
    expect(deleteApiCalled).toBe(true);
    // the confirm modal closes once the delete resolves
    await expect(modal).not.toBeVisible();
  });
});
