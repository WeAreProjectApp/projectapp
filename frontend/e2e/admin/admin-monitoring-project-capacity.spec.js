// qa: draft-unvalidated (2026-11-12 — app not running)
/** Bugs caught: capacity edits silently changing a server quota, invalid allocation reaching the API, or failed saves discarding the operator's values. */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { installMonitoringMock } from '../helpers/monitoring.js';

test.setTimeout(60_000);

async function openProjectCapacity(page, options = {}) {
  const state = await installMonitoringMock(page, options);
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('navigation', { name: 'Navegación del panel' }).getByRole('link', { name: 'Monitoreo', exact: true }).click();
  await page.getByTestId('monitor-resource').click();
  await page.getByRole('dialog', { name: 'Project', exact: true }).getByRole('checkbox', { name: 'Mimittos', exact: true }).check();
  await expect(page.getByTestId('monitoring-capacity').getByRole('heading', { name: 'Project capacity', exact: true })).toHaveCount(1);
  return state;
}

const capacityPanel = (page) => page.getByTestId('monitoring-capacity');
const capacityWrites = (state) => state.requests.filter(request => request.apiPath === 'monitoring/resources/1/capacity/' && request.payload);

test.describe('Monitoring project capacity', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8400, role: 'admin', is_staff: true } });
  });

  test('shows allocation as an informational record separate from consumption', {
    tag: ['@flow:admin-monitoring-project-capacity', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await openProjectCapacity(page);

    await expect(capacityPanel(page).getByText('Informational allocation record. Saving does not change services or server quotas.', { exact: true })).toHaveCount(1);
    await expect(capacityPanel(page).getByText('Project consumption is unavailable. Server measurements include shared resources; a service limit does not represent the entire project.', { exact: true })).toHaveCount(1);
    await expect(capacityPanel(page).getByRole('button', { name: 'Storage: Shared', exact: true })).toHaveCount(1);
  });

  test('saves CPU and RAM allocations while preserving shared storage', {
    tag: ['@flow:admin-monitoring-project-capacity', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    const state = await openProjectCapacity(page);
    await page.getByLabel('CPU (vCPU)').fill('2');
    await capacityPanel(page).getByRole('button', { name: 'Save capacity', exact: true }).click();

    await expect(capacityPanel(page).getByRole('status')).toHaveText('Capacity recorded.');
    expect(capacityWrites(state)).toContainEqual({ apiPath: 'monitoring/resources/1/capacity/', payload: { version: 1, cpu_mode: 'assigned', cpu_vcpu: 2, ram_mode: 'assigned', ram_bytes: 2 * 1024 ** 3, storage_mode: 'shared', storage_bytes: null } });
  });

  test('keeps a nonpositive allocation out of the capacity API', {
    tag: ['@flow:admin-monitoring-project-capacity', '@outcome:error', '@role:admin'],
  }, async ({ page }) => {
    const state = await openProjectCapacity(page);
    const cpu = page.getByLabel('CPU (vCPU)');
    await cpu.fill('0');
    await capacityPanel(page).getByRole('button', { name: 'Save capacity', exact: true }).click();

    await expect(cpu).toHaveValue('0');
    await expect(cpu).toBeInvalid();
    expect(capacityWrites(state)).toHaveLength(0);
  });

  test('keeps the operator allocation after a conflicting save', {
    tag: ['@flow:admin-monitoring-project-capacity', '@outcome:error', '@role:admin'],
  }, async ({ page }) => {
    await openProjectCapacity(page, { capacityConflict: true });
    await page.getByLabel('CPU (vCPU)').fill('2');
    await capacityPanel(page).getByRole('button', { name: 'Save capacity', exact: true }).click();

    await expect(capacityPanel(page).getByRole('alert')).toHaveText('Someone else changed the capacity. Your edit is preserved; reload capacity before saving again.');
    await expect(page.getByLabel('CPU (vCPU)')).toHaveValue('2');
  });

  test('reloads the saved allocation after a server failure', {
    tag: ['@flow:admin-monitoring-project-capacity', '@outcome:failure', '@role:admin'],
  }, async ({ page }) => {
    await openProjectCapacity(page, { capacityFailure: true });
    await page.getByLabel('CPU (vCPU)').fill('2');
    await capacityPanel(page).getByRole('button', { name: 'Save capacity', exact: true }).click();

    await expect(capacityPanel(page).getByRole('alert')).toHaveText('Could not save the change.');
    await capacityPanel(page).getByRole('button', { name: 'Reload capacity', exact: true }).click();
    await expect(page.getByLabel('CPU (vCPU)')).toHaveValue(/^0\.4(?:0{0,2})$/);
  });
});
