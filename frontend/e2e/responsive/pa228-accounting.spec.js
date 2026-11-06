/** PA-228 / RESP-R010 and RESP-R013: complete monetary values and 31 readable billing days. */
import { test, expect } from '../helpers/test.js';
import { viewportUse } from '../helpers/viewports.js';
import { PANEL_VIEWPORTS } from '../../config/responsive.js';
import { RESPONSIVE_PROFILES } from './catalog-scenarios.js';
import {
  openPa228, longConcept, longAmount, selectCalendar, resizeFromDesktop,
  expectFitsHorizontally, expectReadable, expectPageFits,
} from '../helpers/pa228-responsive.js';

test.setTimeout(60_000);

async function expectDaysDistinct(page) {
  const chart = page.getByTestId('recurring-calendar');
  // SVG text is the renderer boundary: inspect the real day labels, never a stubbed chart.
  const labels = chart.locator('text').filter({ hasText: /^(?:[1-9]|[12]\d|3[01])$/ });
  await expect(labels).toHaveCount(31);
  await expect(labels).toHaveText(Array.from({ length: 31 }, (_, index) => String(index + 1)));
  await expect.poll(() => labels.evaluateAll((elements) => {
    const boxes = elements.map((element) => element.getBoundingClientRect());
    return boxes.slice(1).some((box, index) => {
      const previous = boxes[index];
      return Math.min(box.right, previous.right) - Math.max(box.left, previous.left) > 0.5
        && Math.min(box.bottom, previous.bottom) - Math.max(box.top, previous.top) > 0.5;
    });
  })).toBe(false);
  await expectFitsHorizontally(labels);
  await expectPageFits(page);
}

async function selectLostIndicator(page, profile) {
  if (['compact', 'portrait'].includes(profile)) {
    await page.getByRole('button', { name: 'Ver detalle del resultado anual', exact: true }).click();
    await expect(page.getByTestId('income-indicator-detail-liquid')).toContainText('$522.238.000 COP');
    await page.getByTestId('income-indicator-detail-lost').click();
  } else {
    await page.getByRole('button', { name: 'Filtrar ingresos perdidos del año', exact: true }).click();
  }
}

function incomeValues(page, profile) {
  const compact = ['compact', 'portrait'].includes(profile);
  return {
    annual: page.getByTestId(compact ? 'income-stat-result-summary' : 'income-stat-liquid').getByTestId('accounting-stat-value'),
    operational: page.getByTestId(compact ? 'income-stat-operational-summary' : 'income-stat-operational').getByTestId('accounting-stat-value'),
  };
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`PA-228 accounting · ${profile}`, {
    tag: ['@responsive:accounting', '@responsive-special:accounting', '@responsive-batch:accounting-special-5', `@viewport:${profile}`],
  }, () => {
    test.use({ ...viewportUse(profile), reducedMotion: 'reduce' });

    test('billing calendar distinguishes every day', {
      tag: ['@flow:admin-accounting-recurring', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (compare the ticket's direct recurring route with a resize while its calendar stays open)
      await openPa228(page, '/panel/accounting/recurring');
      await page.getByTestId('recurring-charts-button').click();
      await selectCalendar(page, profile);
      await expectDaysDistinct(page);

      await page.setViewportSize(PANEL_VIEWPORTS.desktop);
      await expectDaysDistinct(page);
      await page.setViewportSize(PANEL_VIEWPORTS[profile]);
      await expectDaysDistinct(page);
      // Apex's per-point SVG path identifies the rendered bar for the tenth day.
      const bars = page.getByTestId('recurring-calendar').locator('path[j]');
      await expect(bars).toHaveCount(31);
      await bars.nth(9).hover();
      await expect(page.getByText('$10.000 COP/mes · Pago ficticio del día 10', { exact: true })).toBeVisible();
    });

    test('classic income keeps its total in the first horizontal frame', {
      tag: ['@flow:admin-accounting-income-crud', '@outcome:success'],
    }, async ({ page }) => {
      // quality: allow-deep-link (the reported income route must also fit on a direct mobile load)
      await openPa228(page, '/panel/accounting/incomes');
      await page.getByTestId('incomes-view-mode').getByRole('tab', { name: 'Clásico', exact: true }).click();
      await page.getByTestId('incomes-search-input').fill('QA RESPONSIVE');
      const row = page.getByTestId('accounting-row-979');
      const amount = row.getByText(longAmount, { exact: true });
      await expect(page.getByTestId('income-open-979')).toHaveText(longConcept);
      await expect(amount).toHaveCount(1);
      await expectReadable(amount);
      await expectFitsHorizontally(page.getByTestId('income-actions-979'));
      await expect(row.getByRole('link', { name: longConcept, exact: true })).toHaveAttribute('href', /[?&]income=979(?:&|$)/);
      await expectPageFits(page);

      await resizeFromDesktop(page, profile);
      await expectReadable(amount);
      await expectReadable(row.getByRole('link', { name: longConcept, exact: true }));
      await expect(page.getByTestId('accounting-row-980').getByText('$1.250.000 COP', { exact: true })).toHaveCount(1);
      await expect(row).toHaveJSProperty('scrollLeft', 0);
      await page.getByTestId('income-actions-979').click();
      await expect(page.getByRole('dialog').getByText(longConcept, { exact: true })).toBeVisible();
    });

    test('income indicators expose complete currency values after filtering', {
      tag: ['@flow:admin-accounting-income-crud', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (the ticket requires direct income loading before applying the annual lost filter)
      await openPa228(page, '/panel/accounting/incomes');
      await selectLostIndicator(page, profile);
      const values = incomeValues(page, profile);
      await expect(values.annual).toHaveText('$522.238.000 COP');
      await expect(values.operational).toHaveText('$97.542.000 COP');
      await expectReadable(values.annual);
      await expectReadable(values.operational);
      await expectPageFits(page);

      await resizeFromDesktop(page, profile);
      await expectReadable(incomeValues(page, profile).annual);
      await expectReadable(incomeValues(page, profile).operational);
      await page.getByRole('button', { name: 'Ver detalle operativo de ingresos', exact: true }).click();
      await expect(page.getByTestId('income-indicator-detail-current-month')).toContainText('$97.542.000 COP');
    });
  });
}
