/**
 * E2E tests for admin blog post deletion.
 *
 * Covers: the row menu's delete entry + confirm dialog triggers the delete API and closes.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_BLOG_DELETE } from '../helpers/flow-tags.js';
import { chooseRowAction } from '../helpers/row-actions.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const mockPosts = [
  { id: 1, title_es: 'Post a Borrar', title_en: 'Post to Delete', slug: 'post-borrar', is_published: true, category: 'ai', read_time_minutes: 5, is_featured: false, published_at: '2026-03-01T12:00:00Z', created_at: '2026-03-01T10:00:00Z' },
];

test.describe('Admin Blog Delete', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9000, role: 'admin', is_staff: true } });
  });

  test('confirming the delete calls the API and closes the dialog', {
    tag: [...ADMIN_BLOG_DELETE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Fails if confirming the delete stops calling the delete endpoint or leaves the dialog open.
    let deleteCalled = false;
    await mockApi(page, async ({ apiPath, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'blog/admin/') return { status: 200, contentType: 'application/json', body: JSON.stringify(mockPosts) };
      if (apiPath === 'blog/admin/1/delete/' && route.request().method() === 'DELETE') {
        deleteCalled = true;
        return { status: 204, contentType: 'application/json', body: '' };
      }
      return null;
    });
    await page.goto('/panel/blog');

    const table = page.locator('table');
    await expect(table.getByText('Post a Borrar')).toBeVisible();

    await chooseRowAction(page, {
      kebab: 'blog-post-actions-1',
      menu: 'blog-post-actions-modal',
      action: 'blog-post-delete-1',
    });
    const modal = page.getByRole('dialog', { name: 'Eliminar post' });
    await expect(modal).toBeVisible();

    const deletePromise = page.waitForResponse((r) => r.url().includes('blog/admin/1/delete') && r.request().method() === 'DELETE');
    await modal.getByRole('button', { name: 'Eliminar' }).click();
    await deletePromise;
    expect(deleteCalled).toBe(true);
    await expect(modal).not.toBeVisible();
  });
});
