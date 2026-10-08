/**
 * E2E tests for the public Waiter product and legal pages.
 *
 * @flow:public-waiter-legal-pages
 * Covers: product page, navigation to the three legal pages through the
 * legal footer, verified legal identity, English courtesy translation.
 */
import { test, expect } from '../helpers/test.js';
import { PUBLIC_WAITER_LEGAL_PAGES } from '../helpers/flow-tags.js';

test.describe('Waiter product and legal pages', () => {
  test.setTimeout(60_000);

  test('home footer opens Waiter with its WhatsApp connection steps', {
    tag: ['@outcome:display', ...PUBLIC_WAITER_LEGAL_PAGES, '@role:guest'],
  }, async ({ page }) => {
    await page.goto('/es-co', { waitUntil: 'domcontentloaded' });
    const footer = page.getByTestId('legal-footer');
    await expect(footer.getByTestId('legal-footer-identity')).toContainText('NIT 1021513348-7', { timeout: 20_000 });

    await footer.getByTestId('legal-footer-link-product').click();

    await expect(page).toHaveURL(/\/es-co\/waiter$/);
    await expect(page.getByRole('heading', { level: 1, name: 'Waiter' })).toBeVisible({ timeout: 15_000 });
    const steps = page.locator('main ol > li');
    await expect(steps).toHaveCount(4);
    await expect(steps.first()).toContainText('«Conectar WhatsApp»');
  });

  test('legal footer leads to privacy, terms and data deletion', {
    tag: ['@outcome:success', ...PUBLIC_WAITER_LEGAL_PAGES, '@role:guest'],
  }, async ({ page }) => {
    await page.goto('/es-co/waiter', { waitUntil: 'domcontentloaded' });
    const footer = page.getByTestId('legal-footer');
    await expect(footer).toBeVisible({ timeout: 15_000 });
    await expect(footer.getByTestId('legal-footer-identity')).toContainText('SOFTPROJECTAPPCO');
    await expect(footer.getByTestId('legal-footer-identity')).toContainText('NIT 1021513348-7');

    const destinations = [
      ['legal-footer-link-privacy', /\/es-co\/waiter\/privacy$/, 'Política de tratamiento de datos personales de ProjectApp'],
      ['legal-footer-link-terms', /\/es-co\/waiter\/terms$/, 'Condiciones del servicio de Waiter'],
      ['legal-footer-link-deletion', /\/es-co\/waiter\/data-deletion$/, 'Cómo pedir la eliminación de tus datos'],
    ];
    for (const [testId, url, title] of destinations) {
      await page.getByTestId('legal-footer').getByTestId(testId).click();
      await expect(page).toHaveURL(url);
      await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('legal-footer-identity')).toContainText('Calle 30A #79-42');
    }
  });

  test('English privacy policy lists AWS hosting and the translation notice', {
    tag: ['@outcome:display', ...PUBLIC_WAITER_LEGAL_PAGES, '@role:guest'],
  }, async ({ page }) => {
    await page.goto('/en-us', { waitUntil: 'domcontentloaded' });
    const footer = page.getByTestId('legal-footer');
    await expect(footer.getByTestId('legal-footer-link-privacy')).toBeVisible({ timeout: 20_000 });

    await footer.getByTestId('legal-footer-link-privacy').click();

    await expect(page).toHaveURL(/\/en-us\/waiter\/privacy$/);
    await expect(page.getByRole('heading', { level: 1, name: 'ProjectApp Personal Data Processing Policy' })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('legal-document-notice')).toContainText('The Spanish version is the official text');
    const awsRow = page.locator('#sharing tbody tr', { hasText: 'Amazon Web Services (AWS)' });
    await expect(awsRow.locator('td').nth(2)).toHaveText('United States');
  });
});
