/** Configuration specs catch stale price inputs and saves that report success after rejection. */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { mockRequirementPackages, pricingSettings, colombiaPackages } from '../helpers/requirement-packages.js';
import { ADMIN_HOUR_PACKAGES_CONFIG } from '../helpers/flow-tags.js';

test.describe('Admin requirement package configuration', () => {
  test.setTimeout(60_000);
  test.beforeEach(async ({ page }) => setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9700, role: 'admin', is_staff: true } }));

  test('configuration renders internal prices and alliance cups', { tag: [...ADMIN_HOUR_PACKAGES_CONFIG, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // Bug caught: configuration still renders per-hour prices.
    // quality: allow-deep-link (panel navigation is covered centrally; this flow clicks the configuration section)
    await mockRequirementPackages(page);
    await page.goto('/es-co/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('hour-packages-section-config').click();
    await expect(page.getByTestId('packages-setting-xs_price_cop')).toHaveValue('50000');
    await expect(page.getByTestId('packages-setting-s_price_cop')).toHaveValue('125000');
    await expect(page.getByTestId('packages-alliance-m')).toHaveValue('1');
  });

  test('saving XS price refreshes the catalog total', { tag: [...ADMIN_HOUR_PACKAGES_CONFIG, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: price configuration saves but new catalog totals remain stale.
    const nextAgile = { ...colombiaPackages[0], reference_price: '1800000', savings: '180000', total_price: '1620000' };
    const capture = await mockRequirementPackages(page, { afterSettingsCol: [nextAgile, ...colombiaPackages.slice(1)], updateBody: { ...pricingSettings, xs_price_cop: 60000 } });
    await page.goto('/es-co/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('hour-packages-view-table').click();
    await expect(page.getByRole('table')).toContainText('$1.350.000 COP');
    await page.getByTestId('hour-packages-section-config').click();
    await page.getByTestId('packages-setting-xs_price_cop').fill('60000');
    await page.getByTestId('hour-packages-save-base-rates').click();
    await expect(page.getByText('Configuración guardada. Las ofertas emitidas conservan sus condiciones.')).toBeVisible();
    expect(capture.settings.xs_price_cop).toBe(60000);
    await page.getByTestId('hour-packages-section-catalog').click();
    await page.getByTestId('hour-packages-view-table').click();
    await expect(page.getByRole('table')).toContainText('$1.620.000 COP');
  });

  test('server validation keeps configuration visible', { tag: [...ADMIN_HOUR_PACKAGES_CONFIG, '@role:admin', '@outcome:error'] }, async ({ page }) => {
    // Bug caught: a 400 clears fields or shows a success notification.
    await mockRequirementPackages(page, { updateStatus: 400 });
    await page.goto('/es-co/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('hour-packages-section-config').click();
    await page.getByTestId('packages-setting-xs_price_cop').fill('0');
    await page.getByTestId('hour-packages-save-base-rates').click();
    await expect(page.getByText('No se pudo guardar. Revisa valores positivos, cupos enteros y al menos un cupo para Alianza.')).toBeVisible();
    await expect(page.getByTestId('packages-setting-xs_price_cop')).toHaveValue('0');
  });

  test('server failure does not report configuration success', { tag: [...ADMIN_HOUR_PACKAGES_CONFIG, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
    // Bug caught: a 500 confirmation is mistaken for a saved price configuration.
    await mockRequirementPackages(page, { updateStatus: 500 });
    await page.goto('/es-co/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('hour-packages-section-config').click();
    await page.getByTestId('packages-setting-xs_price_cop').fill('60000');
    await page.getByTestId('hour-packages-save-base-rates').click();
    await expect(page.getByText('No se pudo guardar. Revisa valores positivos, cupos enteros y al menos un cupo para Alianza.')).toBeVisible();
  });

  test('restore confirmation reloads the three default tiers', { tag: [...ADMIN_HOUR_PACKAGES_CONFIG, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: restore discards configuration or produces the old hour ladder.
    const capture = await mockRequirementPackages(page, { col: [{ ...colombiaPackages[0], name_es: 'Custom' }] });
    await page.goto('/es-co/panel/hour-packages', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('hour-packages-section-config').click();
    await page.getByTestId('hour-packages-restore-defaults').click();
    await page.getByTestId('confirm-modal-confirm').click();
    expect(capture.restore).toMatchObject({ nationality: 'COL' });
    await page.getByTestId('hour-packages-section-catalog').click();
    await page.getByTestId('hour-packages-view-table').click();
    await expect(page.getByRole('table')).toContainText('Premium');
    await page.getByTestId('hour-packages-section-config').click();
    await expect(page.getByTestId('packages-setting-m_price_cop')).toHaveValue('360000');
  });
});
