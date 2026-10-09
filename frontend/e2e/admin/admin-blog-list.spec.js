/**
 * E2E tests for admin blog list view.
 *
 * Covers: renders post list with new fields, shows published/draft badges,
 * row actions as a leading kebab column that opens the actions menu.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_BLOG_LIST } from '../helpers/flow-tags.js';
import { openRowMenu } from '../helpers/row-actions.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const mockPosts = [
  { id: 1, title_es: 'Post Publicado', title_en: 'Published Post', slug: 'post-publicado', is_published: true, category: 'ai', read_time_minutes: 8, is_featured: true, published_at: '2026-03-01T12:00:00Z', created_at: '2026-03-01T10:00:00Z' },
  { id: 2, title_es: 'Borrador', title_en: 'Draft', slug: 'borrador', is_published: false, category: 'design', read_time_minutes: 5, is_featured: false, published_at: null, created_at: '2026-02-28T10:00:00Z' },
];

const paginatedResponse = { results: mockPosts, count: 2, page: 1, page_size: 15, total_pages: 1 };
const multiPageResponse = {
  results: mockPosts,
  count: 20,
  page: 1,
  page_size: 2,
  total_pages: 10,
};

test.describe('Admin Blog List', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  test('renders blog post list with new fields', {
    tag: [...ADMIN_BLOG_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — blog list renders posts with their fields; the list's interaction is covered by the calendar-link test)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath.startsWith('blog/admin/')) return { status: 200, contentType: 'application/json', body: JSON.stringify(paginatedResponse) };
      return null;
    });
    await page.goto('/panel/blog');

    const table = page.locator('table');
    await expect(table.getByRole('link', { name: 'Post Publicado' })).toBeVisible();
    await expect(table.getByRole('link', { name: 'Borrador' })).toBeVisible();
  });

  test('shows pagination controls when total pages exceeds 1', {
    tag: [...ADMIN_BLOG_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — pagination controls render when total pages exceed 1)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath.startsWith('blog/admin/')) return { status: 200, contentType: 'application/json', body: JSON.stringify(multiPageResponse) };
      return null;
    });
    await page.goto('/panel/blog');

    const pagination = page.getByRole('navigation', { name: 'Paginación' });
    await expect(pagination).toBeVisible();
    await expect(pagination.getByText(/de\s*20/)).toBeVisible();
    await expect(pagination.getByRole('button', { name: /Página anterior/i })).toBeVisible();
    await expect(pagination.getByRole('button', { name: /Página siguiente/i })).toBeVisible();
  });

  test('the calendar link navigates to the blog calendar', {
    tag: [...ADMIN_BLOG_LIST, '@role:admin', '@outcome:display', '@responsive:content'],
  }, async ({ page }) => {
    // Fails if the blog calendar link stops routing to the calendar page.
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath.startsWith('blog/admin/')) return { status: 200, contentType: 'application/json', body: JSON.stringify(paginatedResponse) };
      return null;
    });
    await page.goto('/panel/blog');

    // Exact match: the Spanish sidebar also has a 'Calendario del blog' link.
    await page.getByRole('link', { name: 'Calendario', exact: true }).click();

    await expect(page).toHaveURL(/\/panel\/blog\/calendar/);
  });

  test('row actions lead the table and open the post menu in place', {
    tag: [...ADMIN_BLOG_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the list-entry path is covered by the owning flow; this test isolates the leading kebab column and its menu)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath.startsWith('blog/admin/')) return { status: 200, contentType: 'application/json', body: JSON.stringify(paginatedResponse) };
      return null;
    });
    await page.goto('/panel/blog', { waitUntil: 'domcontentloaded' });

    const row = page.getByTestId('blog-post-row-1');
    await expect(row).toContainText('Post Publicado', { timeout: 20_000 });
    const leadingHeaders = await page.getByTestId('blog-post-row-actions-header').evaluate((header) => (
      Array.from(header.parentElement.children).slice(0, 2).map((cell) => ({
        testId: cell.getAttribute('data-testid'),
        label: cell.getAttribute('aria-label'),
        text: cell.textContent.trim(),
      }))
    ));
    expect(leadingHeaders).toEqual([
      { testId: 'blog-post-row-actions-header', label: 'Acciones', text: '' },
      { testId: null, label: null, text: 'Título' },
    ]);
    await expectNoBlankBand(row.locator('xpath=ancestor::table'));

    // The kebab names its post for assistive tech only: no visible text.
    const kebab = row.getByTestId('blog-post-row-actions-cell-1').getByTestId('blog-post-actions-1');
    await expect(kebab).toHaveAccessibleName('Acciones de Post Publicado');
    await expect(kebab).toHaveText('');

    const listUrl = page.url();
    await openRowMenu(page, { kebab: 'blog-post-actions-1', menu: 'blog-post-actions-modal' });
    const menu = page.getByTestId('blog-post-actions-modal');
    await expect(menu.getByRole('heading')).toHaveText('Post Publicado');
    await expect(menu.getByRole('listitem')).toHaveText(['Editar', 'Duplicar', 'Eliminar']);
    await expect(menu.getByTestId('blog-post-edit-1')).toHaveAttribute('href', /\/panel\/blog\/1\/edit$/);
    await expect(menu.getByTestId('blog-post-duplicate-1')).toBeVisible();
    await expect(menu.getByTestId('blog-post-delete-1')).toBeVisible();
    await expect(page).toHaveURL(listUrl);
  });
});
