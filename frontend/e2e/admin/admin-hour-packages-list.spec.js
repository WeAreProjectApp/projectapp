/** Catalog specs catch market conversions and cards that describe hours instead of requirements. */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { mockRequirementPackages } from '../helpers/requirement-packages.js';
import { ADMIN_HOUR_PACKAGES_LIST } from '../helpers/flow-tags.js';

test.describe('Admin requirement package catalog', () => {
  test.setTimeout(60_000);
  test.beforeEach(async ({ page }) => setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9400, role: 'admin', is_staff: true } }));

  test('EXT tab displays the USD package price', { tag: [...ADMIN_HOUR_PACKAGES_LIST, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // Bug caught: foreign packages retain Colombia totals after market selection.
    // quality: allow-deep-link (the admin sidebar route is covered by navigation specs; this flow changes market through the UI)
    await mockRequirementPackages(page);
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('hour-packages-tab-ext').click();
    await expect(page.getByRole('table')).toContainText('Ágil exterior');
    await expect(page.getByRole('table')).toContainText('$472.5 USD');
  });

  test('cards show Premium composition and savings', { tag: ['@flow:admin-hour-packages-view-modes', '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // Bug caught: card mode hides requirement composition or the recommended saving.
    // quality: allow-deep-link (the admin sidebar route is covered by navigation specs; this flow changes display mode through the UI)
    await mockRequirementPackages(page);
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('hour-packages-view-cards').click();
    const premium = page.getByTestId('hour-package-card-3');
    await expect(premium).toContainText('30 XS · 20 S · 10 M');
    await expect(premium).toContainText('$1.900.000 COP');
  });

  test('comparison marks Premium as highest discount', { tag: ['@flow:admin-hour-packages-view-modes', '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // Bug caught: comparative mode recommends the wrong tier after discounts change.
    // quality: allow-deep-link (the admin sidebar route is covered by navigation specs; this flow changes display mode through the UI)
    await mockRequirementPackages(page);
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('hour-packages-view-compare').click();
    await expect(page.getByTestId('hour-package-tier-3')).toContainText('Mayor descuento');
    await expect(page.getByTestId('hour-package-tier-3')).toContainText('Ahorra $1.900.000 COP');
  });

  test('next page shows the eleventh requirement tier', { tag: [...ADMIN_HOUR_PACKAGES_LIST, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // Bug caught: pagination keeps the first ten tiers after selecting next.
    // quality: allow-deep-link (the admin sidebar route is covered by navigation specs; this flow clicks pagination)
    const tiers = Array.from({ length: 14 }, (_, index) => ({
      id: 100 + index, pricing_model: 'requirements', nationality: 'COL', currency: 'COP',
      name_es: `Tier ${index + 1}`, name_en: `Tier ${index + 1}`, xs_count: 30, s_count: 0, m_count: 0,
      validity_months: 12, reference_price: '1500000', discount_percent: 10, savings: '150000', total_price: '1350000', is_active: true, order: index + 1,
    }));
    await mockRequirementPackages(page, { col: tiers });
    await page.goto('/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('table')).toContainText('Tier 1');
    await page.getByRole('button', { name: 'Siguiente' }).click();
    await expect(page.getByRole('table')).toContainText('Tier 11');
    await expect(page.getByRole('table')).not.toContainText('Tier 1');
  });
});
