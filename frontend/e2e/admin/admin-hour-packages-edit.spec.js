/** Edit specs catch a fetched tier being rewritten with retired hourly fields. */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { mockRequirementPackages, colombiaPackages } from '../helpers/requirement-packages.js';
import { ADMIN_HOUR_PACKAGES_EDIT } from '../helpers/flow-tags.js';

test.describe('Admin requirement package edit', () => {
  test.setTimeout(60_000);
  test.beforeEach(async ({ page }) => setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9600, role: 'admin', is_staff: true } }));

  test('loaded Pro renders its requirement quantities', { tag: [...ADMIN_HOUR_PACKAGES_EDIT, '@role:admin', '@outcome:display'] }, async ({ page }) => {
    // Bug caught: edit uses missing hourly fields for a requirement package.
    // quality: allow-deep-link (the catalog owns navigation to a package detail; this flow verifies its loaded allowance fields)
    await mockRequirementPackages(page, { detail: colombiaPackages[1] });
    await page.goto('/panel/hour-packages/2/edit', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('package-xs-count').click();
    await expect(page.getByTestId('package-xs-count')).toHaveValue('30');
    await expect(page.getByTestId('package-s-count')).toHaveValue('20');
    await expect(page.getByTestId('package-validity')).toHaveValue('12');
  });

  test('editing M quota PATCHes the requirement field', { tag: [...ADMIN_HOUR_PACKAGES_EDIT, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: editing composition does not reach the backend payload.
    const detail = { ...colombiaPackages[1], id: 3 };
    const capture = await mockRequirementPackages(page, { detail });
    await page.goto('/panel/hour-packages/3/edit', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('package-m-count').fill('10');
    await page.getByRole('button', { name: 'Guardar cambios' }).click();
    expect(capture.update).toMatchObject({ xs_count: 30, s_count: 20, m_count: 10, validity_months: 12 });
    await expect(page).toHaveURL(/\/panel\/hour-packages$/);
  });
});
