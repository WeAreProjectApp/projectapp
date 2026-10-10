/**
 * E2E tests for admin portfolio works list.
 *
 * Covers: renders portfolio list with works, shows empty state,
 * shows create link, displays status badges, row actions as a leading
 * kebab column that opens the actions menu.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PORTFOLIO_LIST } from '../helpers/flow-tags.js';
import { openRowMenu } from '../helpers/row-actions.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const mockWorks = [
  { id: 1, title_es: 'Proyecto Web', title_en: 'Web Project', slug: 'proyecto-web', is_published: true, order: 1, published_at: '2026-03-01T12:00:00Z', created_at: '2026-03-01T10:00:00Z' },
  { id: 2, title_es: 'App Móvil', title_en: 'Mobile App', slug: 'app-movil', is_published: false, order: 2, published_at: null, created_at: '2026-02-28T10:00:00Z' },
];

function setupMock(page, { works = mockWorks } = {}) {
  return mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'portfolio/admin/' && route.request().method() === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(works) };
    }
    return null;
  });
}

test.describe('Admin Portfolio List', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9100, role: 'admin', is_staff: true } });
  });

  test('renders portfolio works list with titles and status badges', {
    tag: [...ADMIN_PORTFOLIO_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — portfolio list renders works with status badges; the list's interaction is covered by the create-link test)
    await setupMock(page);
    await page.goto('/panel/portfolio');

    const table = page.locator('table');
    await expect(table.getByRole('link', { name: 'Proyecto Web' })).toBeVisible();
    await expect(table.getByRole('link', { name: 'App Móvil' })).toBeVisible();
    await expect(table.getByText('Publicado')).toBeVisible();
    await expect(table.getByText('Borrador')).toBeVisible();
  });

  test('the new-project button navigates to the create page', {
    tag: [...ADMIN_PORTFOLIO_LIST, '@role:admin', '@outcome:display', '@responsive:content'],
  }, async ({ page }) => {
    // Fails if the "Nuevo Proyecto" button stops linking to the create page.
    await setupMock(page);
    await page.goto('/panel/portfolio');

    await page.getByRole('link', { name: /Nuevo Proyecto/ }).click();

    await expect(page).toHaveURL(/\/panel\/portfolio\/create/);
  });

  test('shows empty state when no works exist', {
    tag: [...ADMIN_PORTFOLIO_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — empty state renders when no works exist)
    await setupMock(page, { works: [] });
    await page.goto('/panel/portfolio');

    await expect(page.getByText('No hay proyectos aún')).toBeVisible();
  });

  test('row actions lead the table and open the work menu in place', {
    tag: [...ADMIN_PORTFOLIO_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the list-entry path is covered by the owning flow; this test isolates the leading kebab column and its menu)
    await setupMock(page);
    await page.goto('/panel/portfolio', { waitUntil: 'domcontentloaded' });

    const row = page.getByTestId('portfolio-work-row-1');
    await expect(row).toContainText('Proyecto Web', { timeout: 20_000 });
    const leadingHeaders = await page.getByTestId('portfolio-work-row-actions-header').evaluate((header) => (
      Array.from(header.parentElement.children).slice(0, 2).map((cell) => ({
        testId: cell.getAttribute('data-testid'),
        label: cell.getAttribute('aria-label'),
        text: cell.textContent.trim(),
      }))
    ));
    expect(leadingHeaders).toEqual([
      { testId: 'portfolio-work-row-actions-header', label: 'Acciones', text: '' },
      { testId: null, label: null, text: 'Título' },
    ]);
    await expectNoBlankBand(row.locator('xpath=ancestor::table'));

    // The kebab names its work for assistive tech only: no visible text.
    const kebab = row.getByTestId('portfolio-work-row-actions-cell-1').getByTestId('portfolio-work-actions-1');
    await expect(kebab).toHaveAccessibleName('Acciones de Proyecto Web');
    await expect(kebab).toHaveText('');

    const listUrl = page.url();
    await openRowMenu(page, { kebab: 'portfolio-work-actions-1', menu: 'portfolio-work-actions-modal' });
    const menu = page.getByTestId('portfolio-work-actions-modal');
    await expect(menu.getByRole('heading')).toHaveText('Proyecto Web');
    await expect(menu.getByRole('listitem')).toHaveText(['Editar', 'Duplicar', 'Eliminar']);
    await expect(menu.getByTestId('portfolio-work-edit-1')).toHaveAttribute('href', /\/panel\/portfolio\/1\/edit$/);
    await expect(menu.getByTestId('portfolio-work-duplicate-1')).toBeVisible();
    await expect(menu.getByTestId('portfolio-work-delete-1')).toBeVisible();
    await expect(page).toHaveURL(listUrl);
  });
});
