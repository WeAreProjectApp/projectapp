/** PA-228 / RESP-R001: a real, populated chart must shrink after a desktop render. */
import { test, expect } from '../helpers/test.js';
import { viewportUse } from '../helpers/viewports.js';
import { PANEL_VIEWPORTS } from '../../config/responsive.js';
import { RESPONSIVE_PROFILES } from './catalog-scenarios.js';
import { openPa228, expectFitsHorizontally, expectPageFits } from '../helpers/pa228-responsive.js';

test.setTimeout(60_000);

async function expectTrendFits(page) {
  const chart = page.getByTestId('dashboard-trend-chart');
  await expect(chart.getByText('Aceptadas', { exact: true })).toBeVisible();
  await expect.poll(async () => chart.evaluate((element) => {
    const svg = element.querySelector('svg');
    return svg ? Math.abs(svg.getBoundingClientRect().width - element.clientWidth) : Infinity;
  })).toBeLessThanOrEqual(2);
  await expectFitsHorizontally(chart);
  await expectFitsHorizontally(page.getByTestId('dashboard-status-pills').locator('span'));
  await expectPageFits(page);
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`PA-228 dashboard · ${profile}`, {
    tag: ['@responsive:dashboard', '@responsive-special:dashboard', '@responsive-batch:dashboard-special-1', `@viewport:${profile}`],
  }, () => {
    test.use({ ...viewportUse(profile), reducedMotion: 'reduce' });

    test('proposal trend retains its six months after resizing', {
      tag: ['@flow:admin-dashboard', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (the ticket requires comparing a direct load with resizing the same mounted dashboard)
      await openPa228(page, '/panel');
      await expect(page.getByTestId('dashboard-status-pills')).toContainText('4');
      await expectTrendFits(page);

      await page.setViewportSize(PANEL_VIEWPORTS.desktop);
      await expectTrendFits(page);
      await page.setViewportSize(PANEL_VIEWPORTS[profile]);
      await expectTrendFits(page);
      await expect(page.getByTestId('dashboard-trend-chart').locator('tspan').filter({ hasText: /^may$/ })).toBeVisible();
      await expect(page.getByTestId('dashboard-trend-chart').locator('tspan').filter({ hasText: /^oct$/ })).toBeVisible();
    });
  });
}
