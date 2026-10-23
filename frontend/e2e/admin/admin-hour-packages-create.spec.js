/** Create specs catch requests that send retired hourly fields instead of requirement allowances. */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { mockRequirementPackages } from '../helpers/requirement-packages.js';
import { ADMIN_HOUR_PACKAGES_CREATE } from '../helpers/flow-tags.js';

test.describe('Admin requirement package creation', () => {
  test.setTimeout(60_000);
  test.beforeEach(async ({ page }) => setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9500, role: 'admin', is_staff: true } }));

  test('form previews Premium total from its composition', { tag: [...ADMIN_HOUR_PACKAGES_CREATE, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // Bug caught: the form computes a price from hours instead of sizes.
    // quality: allow-deep-link (the catalog owns navigation to the creation form; this flow exercises its composition inputs)
    await mockRequirementPackages(page);
    await page.goto('/panel/hour-packages/create', { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Nombre (ES)').fill('Premium');
    await page.getByLabel('Name (EN)').fill('Premium');
    await page.getByTestId('package-xs-count').fill('30');
    await page.getByTestId('package-s-count').fill('20');
    await page.getByTestId('package-m-count').fill('10');
    await page.getByTestId('package-discount').fill('25');
    await expect(page.getByTestId('package-price-preview')).toContainText('Total: $5.700.000 COP + IVA');
  });

  test('EXT query preselects USD currency', { tag: [...ADMIN_HOUR_PACKAGES_CREATE, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // Bug caught: opening the foreign creation route restores Colombia currency.
    // quality: allow-deep-link (the catalog owns creation navigation; this pins its market query contract)
    await mockRequirementPackages(page);
    await page.goto('/panel/hour-packages/create?nationality=EXT', { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Nacionalidad').selectOption('EXT');
    await expect(page.getByLabel('Nacionalidad')).toHaveValue('EXT');
    await expect(page.getByText('USD (derivada de la nacionalidad)')).toBeVisible();
  });

  test('submit sends XS S M validity and discount', { tag: [...ADMIN_HOUR_PACKAGES_CREATE, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: creating a tier loses its validity or sends `hours`.
    const capture = await mockRequirementPackages(page);
    await page.goto('/panel/hour-packages/create', { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Nombre (ES)').fill('Premium');
    await page.getByLabel('Name (EN)').fill('Premium');
    await page.getByTestId('package-xs-count').fill('30');
    await page.getByTestId('package-s-count').fill('20');
    await page.getByTestId('package-m-count').fill('10');
    await page.getByTestId('package-validity').fill('12');
    await page.getByTestId('package-discount').fill('25');
    await page.getByRole('button', { name: 'Crear paquete' }).click();
    expect(capture.create).toMatchObject({ xs_count: 30, s_count: 20, m_count: 10, validity_months: 12, discount_percent: 25 });
    expect(capture.create.hours).toBeUndefined();
    await expect(page).toHaveURL(/\/panel\/hour-packages$/);
  });

  test('server composition error keeps entered values', { tag: [...ADMIN_HOUR_PACKAGES_CREATE, '@role:admin', '@outcome:error'] }, async ({ page }) => {
    // Bug caught: a server validation response erases a new package draft.
    await mockRequirementPackages(page, { createStatus: 400, createBody: { xs_count: ['Usa al menos un cupo.'] } });
    await page.goto('/panel/hour-packages/create', { waitUntil: 'domcontentloaded' });
    await page.getByLabel('Nombre (ES)').fill('Sin cupos');
    await page.getByLabel('Name (EN)').fill('No slots');
    await page.getByTestId('package-xs-count').fill('0');
    await page.getByTestId('package-s-count').fill('0');
    await page.getByTestId('package-m-count').fill('0');
    await page.getByRole('button', { name: 'Crear paquete' }).click();
    await expect(page.getByText('Usa al menos un cupo.')).toBeVisible();
    await expect(page.getByTestId('package-xs-count')).toHaveValue('0');
  });
});
