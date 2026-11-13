/** Bugs caught: measured server trends disappearing, period changes retaining stale data, or a failed series being unrecoverable. */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { installMonitoringMock } from '../helpers/monitoring.js';

test.setTimeout(60_000);

async function openServerMonitoring(page, options = {}) {
  const state = await installMonitoringMock(page, options);
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('navigation', { name: 'Navegación del panel' }).getByRole('link', { name: 'Monitoreo', exact: true }).click();
  await page.getByRole('button', { name: 'Servers', exact: true }).click();
  return state;
}

test.describe('Monitoring server trends', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8400, role: 'admin', is_staff: true } });
  });

  test('shows the measured server capacity before the event list', {
    tag: ['@flow:admin-monitoring-server-trends', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await openServerMonitoring(page);

    await expect(page.getByTestId('monitoring-charts').getByRole('heading', { name: 'Server trends', exact: true })).toHaveCount(1);
    await expect(page.getByText('RAM 2.00 / 4.00 GiB · 2 vCPU', { exact: true })).toHaveCount(1);
    await expect(page.getByTestId('monitoring-charts').getByText('Actual measurements; gaps indicate missing data. Aggregated intervals show the average and maximum of available samples.', { exact: true })).toHaveCount(1);
    await expect(page.getByTestId('monitoring-charts').getByRole('heading', { name: 'Disk', exact: true })).toHaveCount(1);
    await expect(page.getByTestId('monitoring-charts').getByRole('heading', { name: 'CPU', exact: true })).toHaveCount(1);
    await expect(page.getByTestId('monitoring-charts').getByRole('heading', { name: 'Processing load', exact: true })).toHaveCount(1);
  });

  test('requests the selected seven-day measured period', {
    tag: ['@flow:admin-monitoring-server-trends', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    const state = await openServerMonitoring(page);
    const charts = page.getByTestId('monitoring-charts');
    await charts.getByRole('button', { name: 'Period: Last 24 hours', exact: true }).click();
    await page.getByRole('dialog', { name: 'Period', exact: true }).getByRole('checkbox', { name: 'Last 7 days', exact: true }).check();

    await expect(charts.getByRole('button', { name: 'Period: Last 7 days', exact: true })).toHaveCount(1);
    await expect.poll(() => state.requests.some(request => request.apiPath === 'monitoring/servers/2/series/' && request.params.period === '7d')).toBe(true);
    await expect(charts.getByRole('heading', { name: 'RAM', exact: true })).toHaveCount(1);
  });

  test('labels a server without measurements as no measured history', {
    tag: ['@flow:admin-monitoring-server-trends', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await openServerMonitoring(page, { noHistory: true });

    await expect(page.getByTestId('monitoring-charts')).toContainText('No measured history for this period. Charts start when collection is activated; earlier values are not estimated.');
  });

  test('retries a failed series request and restores the measured chart', {
    tag: ['@flow:admin-monitoring-server-trends', '@outcome:failure', '@role:admin'],
  }, async ({ page }) => {
    await openServerMonitoring(page, { seriesFailureOnce: true });
    const charts = page.getByTestId('monitoring-charts');
    await expect(charts.getByRole('alert').getByText('Could not load data. Try refreshing.', { exact: true })).toHaveCount(1);
    await charts.getByRole('button', { name: 'Refresh', exact: true }).click();

    await expect(charts.getByRole('heading', { name: 'RAM', exact: true })).toHaveCount(1);
  });
});
