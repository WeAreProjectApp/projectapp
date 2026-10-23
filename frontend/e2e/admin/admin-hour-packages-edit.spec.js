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
    await page.goto('/es-co/panel/hour-packages/2/edit', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('package-xs-count').click();
    await expect(page.getByTestId('package-xs-count')).toHaveValue('30');
    await expect(page.getByTestId('package-s-count')).toHaveValue('20');
    await expect(page.getByTestId('package-validity')).toHaveValue('12');
  });

  test('editing M quota PATCHes the requirement field', { tag: [...ADMIN_HOUR_PACKAGES_EDIT, '@role:admin', '@outcome:success'] }, async ({ page }) => {
    // Bug caught: editing composition does not reach the backend payload.
    const detail = { ...colombiaPackages[1], id: 3 };
    const capture = await mockRequirementPackages(page, { detail });
    await page.goto('/es-co/panel/hour-packages/3/edit', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('package-m-count').fill('10');
    await page.getByRole('button', { name: 'Guardar cambios' }).click();
    expect(capture.update).toMatchObject({ xs_count: 30, s_count: 20, m_count: 10, validity_months: 12 });
    await expect(page).toHaveURL(/\/panel\/hour-packages$/);
  });

  test('server composition error keeps zeroed quotas', { tag: [...ADMIN_HOUR_PACKAGES_EDIT, '@role:admin', '@outcome:error'] }, async ({ page }) => {
    // Bug caught: a rejected empty composition discards the operator's quotas.
    const detail = { ...colombiaPackages[1], id: 3 };
    const capture = await mockRequirementPackages(page, { detail, updateStatus: 400, packageUpdateBody: { non_field_errors: ['Incluye al menos un cupo.'] } });
    await page.goto('/es-co/panel/hour-packages/3/edit', { waitUntil: 'domcontentloaded' });
    await page.getByTestId('package-xs-count').fill('0');
    await page.getByTestId('package-s-count').fill('0');
    await page.getByTestId('package-m-count').fill('0');
    await page.getByRole('button', { name: 'Guardar cambios' }).click();
    await expect(page.getByText('No se pudo guardar el paquete. Revisa los campos.')).toBeVisible();
    await expect(page.getByTestId('package-xs-count')).toHaveValue('0');
    await expect(page.getByTestId('package-s-count')).toHaveValue('0');
    await expect(page.getByTestId('package-m-count')).toHaveValue('0');
    expect(capture.update).toMatchObject({ xs_count: 0, s_count: 0, m_count: 0 });
  });
});
