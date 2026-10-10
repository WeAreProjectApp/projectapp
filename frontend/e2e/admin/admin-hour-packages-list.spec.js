/**
 * E2E tests for the admin hour-packages list.
 *
 * Covers: renders package list with derived currency, switching the
 * nationality tab refetches and shows that country's prices, empty state,
 * row actions as a leading kebab column that opens the actions menu.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_HOUR_PACKAGES_LIST } from '../helpers/flow-tags.js';
import { openRowMenu } from '../helpers/row-actions.js';
import { expectNoBlankBand } from '../helpers/table-geometry.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const colPackages = [
  { id: 1, nationality: 'COL', currency: 'COP', name_es: 'Paquete Ágil', name_en: 'Agile Pack', hours: 20, hourly_rate: '90000.00', discount_percent: 0, is_active: true, order: 1, updated_at: '2026-07-01T10:00:00Z' },
  { id: 2, nationality: 'COL', currency: 'COP', name_es: 'Paquete Pro', name_en: 'Pro Pack', hours: 60, hourly_rate: '90000.00', discount_percent: 10, is_active: true, order: 2, updated_at: '2026-07-01T10:00:00Z' },
];

const extPackages = [
  { id: 3, nationality: 'EXT', currency: 'USD', name_es: 'Paquete Ágil EXT', name_en: 'Agile Pack EXT', hours: 20, hourly_rate: '45.00', discount_percent: 0, is_active: true, order: 1, updated_at: '2026-07-01T10:00:00Z' },
];

function setupMock(page, { col = colPackages, ext = extPackages } = {}) {
  return mockApi(page, async ({ apiPath, route }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === 'hour-packages/admin/' && route.request().method() === 'GET') {
      const url = new URL(route.request().url());
      const nationality = url.searchParams.get('nationality');
      const body = nationality === 'EXT' ? ext : nationality === 'USA' ? [] : col;
      return { status: 200, contentType: 'application/json', body: JSON.stringify(body) };
    }
    return null;
  });
}

test.describe('Admin Hour Packages List', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9400, role: 'admin', is_staff: true } });
  });

  test('renders COL packages with COP prices by default', {
    tag: [...ADMIN_HOUR_PACKAGES_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/hour-packages');

    const table = page.locator('table');
    await expect(table.getByRole('link', { name: 'Paquete Ágil', exact: true })).toBeVisible();
    await expect(table.getByRole('link', { name: 'Paquete Pro', exact: true })).toBeVisible();
    await expect(table.getByText('$90.000 COP').first()).toBeVisible();
    await expect(page.getByText('se cotizan en COP')).toBeVisible();
  });

  test('switching to the EXT tab shows USD prices for that country', {
    tag: [...ADMIN_HOUR_PACKAGES_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/hour-packages');

    const table = page.locator('table');
    await expect(table.getByRole('link', { name: 'Paquete Ágil', exact: true })).toBeVisible();

    await page.getByTestId('hour-packages-tab-ext').click();

    await expect(table.getByRole('link', { name: 'Paquete Ágil EXT' })).toBeVisible();
    await expect(table.getByText('$45 USD').first()).toBeVisible();
    await expect(page.getByText('se cotizan en USD')).toBeVisible();
    await expect(table.getByRole('link', { name: 'Paquete Pro', exact: true })).toBeHidden();
  });

  test('shows empty state for a nationality without packages', {
    tag: [...ADMIN_HOUR_PACKAGES_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto('/panel/hour-packages');

    await page.getByTestId('hour-packages-tab-usa').click();

    await expect(page.getByText('Sin paquetes para esta nacionalidad')).toBeVisible();
  });

  test('paginates when the list exceeds one page', {
    tag: [...ADMIN_HOUR_PACKAGES_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const many = Array.from({ length: 14 }, (_, i) => ({
      id: 100 + i,
      nationality: 'COL',
      currency: 'COP',
      name_es: `Paquete ${String(i + 1).padStart(2, '0')}`,
      name_en: `Pack ${i + 1}`,
      hours: 10 + i,
      hourly_rate: '90000.00',
      discount_percent: 0,
      is_active: true,
      order: i + 1,
      updated_at: '2026-07-01T10:00:00Z',
    }));
    await setupMock(page, { col: many });
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });

    const table = page.getByRole('table');
    await expect(table.getByText('Paquete 01')).toBeVisible({ timeout: 20_000 });
    // pageSize is 10 → the 11th package lives on page 2.
    await expect(table.getByText('Paquete 11')).toBeHidden();

    await page.getByRole('button', { name: 'Siguiente' }).click();

    await expect(table.getByText('Paquete 11')).toBeVisible();
    await expect(table.getByText('Paquete 01')).toBeHidden();
  });

  test('mobile viewport renders the card variant instead of the table', {
    tag: [...ADMIN_HOUR_PACKAGES_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await setupMock(page);
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });

    // The table is hidden below the sm breakpoint; the card list takes over.
    await expect(page.getByRole('table')).toBeHidden({ timeout: 20_000 });
    await expect(page.getByText('Paquete Ágil').first()).toBeVisible();
  });

  test('row actions lead the table and open the package menu in place', {
    tag: [...ADMIN_HOUR_PACKAGES_LIST, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the list-entry path is covered by the owning flow; this test isolates the leading kebab column and its menu)
    await setupMock(page);
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });

    const row = page.getByTestId('hour-package-row-1');
    await expect(row).toContainText('Paquete Ágil', { timeout: 20_000 });
    const leadingHeaders = await page.getByTestId('hour-package-row-actions-header').evaluate((header) => (
      Array.from(header.parentElement.children).slice(0, 2).map((cell) => ({
        testId: cell.getAttribute('data-testid'),
        label: cell.getAttribute('aria-label'),
        text: cell.textContent.trim(),
      }))
    ));
    expect(leadingHeaders).toEqual([
      { testId: 'hour-package-row-actions-header', label: 'Acciones', text: '' },
      { testId: null, label: null, text: 'Paquete' },
    ]);
    await expectNoBlankBand(row.locator('xpath=ancestor::table'));

    // The kebab names its package for assistive tech only: no visible text.
    const kebab = row.getByTestId('hour-package-row-actions-cell-1').getByTestId('hour-package-actions-1');
    await expect(kebab).toHaveAccessibleName('Acciones de Paquete Ágil');
    await expect(kebab).toHaveText('');

    const listUrl = page.url();
    await openRowMenu(page, { kebab: 'hour-package-actions-1', menu: 'hour-package-actions-modal' });
    const menu = page.getByTestId('hour-package-actions-modal');
    await expect(menu.getByRole('heading')).toHaveText('Paquete Ágil');
    await expect(menu.getByRole('listitem')).toHaveText(['Editar', 'Eliminar']);
    await expect(menu.getByTestId('hour-package-edit-1')).toHaveAttribute('href', /\/panel\/hour-packages\/1\/edit$/);
    await expect(menu.getByTestId('hour-package-delete-1')).toBeVisible();
    await expect(page).toHaveURL(listUrl);
  });
});

