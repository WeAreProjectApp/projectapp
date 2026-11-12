/** Bugs caught: a missing panel entry, broken KPI inspection, a broken resource partition, or a failed case request hiding its error. */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { installMonitoringMock, monitoringCaseTitle, monitoringServerTitle } from '../helpers/monitoring.js';

test.setTimeout(60_000);

async function chooseFilter(page, testId, label, option) {
  await page.getByTestId(testId).click();
  await page.getByRole('dialog', { name: label, exact: true }).getByRole('checkbox', { name: option, exact: true }).check();
}

async function openMonitoring(page, options = {}) {
  const state = await installMonitoringMock(page, options);
  await page.goto('/panel/monitoring', { waitUntil: 'domcontentloaded' });
  return state;
}

test.describe('Monitoring case list', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8400, role: 'admin', is_staff: true } });
  });

  test('opens monitoring from the panel navigation and renders the project case fixture', {
    tag: ['@flow:admin-monitoring-case-list', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await installMonitoringMock(page);
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('navigation', { name: 'Navegación del panel' }).getByRole('link', { name: 'Monitoreo', exact: true }).click();

    await expect(page).toHaveURL(/\/panel\/monitoring/);
    await expect(page.getByTestId('monitoring-page').getByRole('button', { name: monitoringCaseTitle, exact: true })).toHaveCount(1);
  });

  test('switching to servers requests and shows the server case partition', {
    tag: ['@flow:admin-monitoring-case-list', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    await installMonitoringMock(page);
    await page.goto('/panel/monitoring', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Servers', exact: true }).click();

    await expect(page.getByRole('button', { name: monitoringServerTitle, exact: true })).toHaveCount(1);
  });

  test('shows a concrete load alert when the case request fails', {
    tag: ['@flow:admin-monitoring-case-list', '@outcome:failure', '@role:admin'],
  }, async ({ page }) => {
    await installMonitoringMock(page, { listFailure: true });
    await page.goto('/panel/monitoring', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Refresh', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Could not load data. Try refreshing.');
  });

  test('applies dynamic filters and clears them into a new first-page consultation', {
    tag: ['@flow:admin-monitoring-case-list', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    const state = await openMonitoring(page, { corpusSize: 55 });
    await chooseFilter(page, 'monitor-resource', 'Project', 'Mimittos');
    await chooseFilter(page, 'monitor-source', 'Source', 'Mimittos · Application queries');
    await page.getByLabel('Search').fill('Consulta');

    await expect.poll(() => state.requests.some(request => request.apiPath === 'monitoring/cases/' && request.params.resource === '1' && request.params.source === '11' && request.params.search === 'Consulta' && request.params.page === '1' && request.params.snapshot === 'new')).toBe(true);
    await expect(page.getByRole('button', { name: monitoringCaseTitle, exact: true })).toHaveCount(1);

    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();

    await expect(page.getByTestId('monitor-resource')).toHaveText('Project');
    await expect(page.getByLabel('Search')).toHaveValue('');
    await expect.poll(() => state.requests.some(request => request.apiPath === 'monitoring/cases/' && request.params.kind === 'project' && request.params.page === '1' && request.params.snapshot === 'new' && !request.params.resource && !request.params.source && !request.params.search)).toBe(true);
    await expect(page.getByRole('navigation', { name: 'Paginación' })).toContainText('Mostrando 1–25 de 55');
  });

  test('blocks inverted dates with an explicit validation message', {
    tag: ['@flow:admin-monitoring-case-list', '@outcome:error', '@role:admin'],
  }, async ({ page }) => {
    await openMonitoring(page);
    await page.getByLabel('From').fill('2026-09-20');
    await page.getByLabel('Until').fill('2026-09-19');

    await expect(page.getByRole('alert')).toHaveText('The end date must be on or after the start date.');
    await expect(page.getByRole('button', { name: monitoringCaseTitle, exact: true })).toHaveCount(0);
  });

  test('uses the same snapshot for the next real case page', {
    tag: ['@flow:admin-monitoring-case-list', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    const state = await openMonitoring(page, { corpusSize: 55 });
    await page.getByRole('button', { name: 'Página siguiente', exact: true }).click();

    await expect(page.getByRole('navigation', { name: 'Paginación' })).toContainText('Mostrando 26–50 de 55');
    await expect(page.getByRole('button', { name: 'Observación de prueba 26', exact: true })).toHaveCount(1);
    await expect.poll(() => state.requests.some(request => request.apiPath === 'monitoring/cases/' && request.params.page === '2' && request.params.snapshot === 'fixture-snapshot-1')).toBe(true);
  });

  test('refreshes an expired consultation without discarding its chosen filters', {
    tag: ['@flow:admin-monitoring-case-list', '@outcome:error', '@role:admin'],
  }, async ({ page }) => {
    const state = await openMonitoring(page, { snapshotExpiredOnce: true });
    await expect(page.getByRole('alert')).toHaveText('This consultation expired. Use Refresh to continue with the same filters.');

    await chooseFilter(page, 'monitor-resource', 'Project', 'Mimittos');
    await page.getByLabel('Search').fill('Consulta');
    await page.getByRole('button', { name: 'Refresh', exact: true }).click();

    await expect(page.getByRole('button', { name: monitoringCaseTitle, exact: true })).toHaveCount(1);
    await expect(page.getByTestId('monitor-resource')).toHaveText('Project: Mimittos');
    await expect(page.getByLabel('Search')).toHaveValue('Consulta');
    await expect.poll(() => state.requests.some(request => request.apiPath === 'monitoring/cases/' && request.params.resource === '1' && request.params.search === 'Consulta' && request.params.page === '1' && request.params.snapshot === 'new')).toBe(true);
  });

  test('opens the active warning KPI as a fresh filtered case consultation', {
    tag: ['@flow:admin-monitoring-case-list', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    const state = await openMonitoring(page);
    await page.getByTestId('monitoring-summary').getByRole('button', { name: /Active · Warning/ }).click();

    await expect.poll(() => state.requests.some(request => request.apiPath === 'monitoring/cases/' && request.params.condition === 'active' && request.params.severity === 'warning' && request.params.page === '1' && request.params.snapshot === 'new')).toBe(true);
    await expect(page.getByRole('button', { name: monitoringCaseTitle, exact: true })).toHaveCount(1);
  });

  test('opens stale server-source details without leaving the server context', {
    tag: ['@flow:admin-monitoring-case-list', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await installMonitoringMock(page);
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('navigation', { name: 'Navegación del panel' }).getByRole('link', { name: 'Monitoreo', exact: true }).click();
    await page.getByRole('button', { name: 'Servers', exact: true }).click();
    await page.getByTestId('monitoring-summary').getByRole('button', { name: /Stale sources/ }).click();

    const sourceDialog = page.getByRole('dialog', { name: 'Source status', exact: true });
    await expect(sourceDialog.getByRole('heading', { name: 'Source status', exact: true })).toHaveCount(1);
    await expect(sourceDialog.getByText('VPS de producción · Availability', { exact: true })).toHaveCount(1);
    await expect(sourceDialog.getByText(/Stale · Last updated:/)).toHaveCount(1);
    await expect(sourceDialog.getByText('Expected observation interval: 300 seconds.', { exact: true })).toHaveCount(1);
    await expect(sourceDialog.getByText('Sin espacio suficiente', { exact: true })).toHaveCount(1);

    await sourceDialog.getByRole('button', { name: 'Close', exact: true }).click();
    await expect(sourceDialog).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Servers', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('button', { name: monitoringServerTitle, exact: true })).toHaveCount(1);
  });
});
