/** Bugs caught: state and note requests that silently lose the operator's follow-up, and reports exposing case controls. */
import { test, expect } from '../helpers/test.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { installMonitoringMock, monitoringCase, monitoringCaseTitle, monitoringReportTitle } from '../helpers/monitoring.js';

test.setTimeout(60_000);

async function openCase(page, options = {}) {
  const state = await installMonitoringMock(page, options);
  await page.goto('/panel/monitoring', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: monitoringCaseTitle, exact: true }).click();
  await expect(page.getByTestId('monitoring-detail').getByRole('heading', { name: monitoringCaseTitle, exact: true })).toHaveCount(1);
  return state;
}

async function openCaseFromPanel(page, options = {}) {
  const state = await installMonitoringMock(page, options);
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('navigation', { name: 'Navegación del panel' }).getByRole('link', { name: 'Monitoreo', exact: true }).click();
  await page.getByRole('button', { name: monitoringCaseTitle, exact: true }).click();
  await expect(page.getByTestId('monitoring-detail').getByRole('heading', { name: monitoringCaseTitle, exact: true })).toHaveCount(1);
  return state;
}

const caseDetail = (page) => page.getByTestId('monitoring-detail');
const dialogStatus = (page) => page.getByRole('dialog', { name: 'Status' });

async function chooseUnderReview(page) {
  await caseDetail(page).getByTestId('monitor-detail-state').click();
  await dialogStatus(page).getByRole('checkbox', { name: 'Under review', exact: true }).check();
}

test.describe('Monitoring case follow-up and reports', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8400, role: 'admin', is_staff: true } });
  });

  test('opens a case detail with its current pending state', {
    tag: ['@flow:admin-monitoring-case-follow-up', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await openCaseFromPanel(page);
    await expect(caseDetail(page).getByTestId('monitor-detail-state')).toHaveText('Status: Pending');
    await expect(caseDetail(page).getByRole('heading', { name: monitoringCaseTitle, exact: true })).toHaveCount(1);
  });

  test('saves a reviewing state with the case version and renders the returned state', {
    tag: ['@flow:admin-monitoring-case-follow-up', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    const state = await openCase(page);
    await chooseUnderReview(page);
    await page.getByRole('button', { name: 'Save status', exact: true }).click();

    await expect(caseDetail(page).getByTestId('monitor-detail-state')).toHaveText('Status: Under review');
    await expect(page.getByText('Problem detected · Under review', { exact: true })).toHaveCount(1);
    expect(state.requests).toContainEqual({ apiPath: 'monitoring/cases/71/state/', payload: { state: 'reviewing', version: 3 } });
  });

  test('keeps the selected state and explains a concurrent update conflict', {
    tag: ['@flow:admin-monitoring-case-follow-up', '@outcome:error', '@role:admin'],
  }, async ({ page }) => {
    await openCase(page, { stateConflict: true });
    await chooseUnderReview(page);
    await page.getByRole('button', { name: 'Save status', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('The case changed. Refresh the detail before saving.');
    await expect(caseDetail(page).getByTestId('monitor-detail-state')).toHaveText('Status: Under review');
  });

  test('shows a save failure after a server error instead of pretending the state changed', {
    tag: ['@flow:admin-monitoring-case-follow-up', '@outcome:failure', '@role:admin'],
  }, async ({ page }) => {
    await openCase(page, { stateFailure: true });
    await chooseUnderReview(page);
    await page.getByRole('button', { name: 'Save status', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Could not save the change.');
    await expect(page.getByText('Problem detected · Pending', { exact: true })).toHaveCount(1);
  });

  test('persists a trimmed operator note in the visible activity history', {
    tag: ['@flow:admin-monitoring-case-note', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    const state = await openCase(page);
    await page.getByLabel('Note').fill('  I reviewed the index and it remains pending closure.  ');
    await page.getByRole('button', { name: 'Add note', exact: true }).click();

    await expect(page.getByText('I reviewed the index and it remains pending closure.', { exact: true })).toHaveCount(1);
    expect(state.requests).toContainEqual({ apiPath: 'monitoring/cases/71/notes/', payload: { text: 'I reviewed the index and it remains pending closure.' } });
  });

  test('shows an existing note in a case reached from the panel navigation', {
    tag: ['@flow:admin-monitoring-case-note', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await openCaseFromPanel(page, {
      state: {
        detail: monitoringCase({ activities: [{ id: 8, actor_name: 'admin', text: 'El índice quedó revisado.', created_at: '2026-09-19T10:06:00Z', from_state: '', to_state: '' }] }),
      },
    });
    await expect(caseDetail(page).getByText('El índice quedó revisado.', { exact: true })).toHaveCount(1);
  });

  test('keeps an operator note visible when the API rejects its content', {
    tag: ['@flow:admin-monitoring-case-note', '@outcome:error', '@role:admin'],
  }, async ({ page }) => {
    await openCase(page, { noteValidation: true });
    await page.getByLabel('Note').fill('Note rejected by policy');
    await page.getByRole('button', { name: 'Add note', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Could not save the change.');
    await expect(page.getByLabel('Note')).toHaveValue('Note rejected by policy');
  });

  test('keeps an operator note visible when its save fails on the server', {
    tag: ['@flow:admin-monitoring-case-note', '@outcome:failure', '@role:admin'],
  }, async ({ page }) => {
    await openCase(page, { noteFailure: true });
    await page.getByLabel('Note').fill('Note that cannot be lost');
    await page.getByRole('button', { name: 'Add note', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Could not save the change.');
    await expect(page.getByLabel('Note')).toHaveValue('Note that cannot be lost');
  });

  test('opens reports from the monitoring tab and renders its retained data', {
    tag: ['@flow:admin-monitoring-reports', '@outcome:display', '@role:admin'],
  }, async ({ page }) => {
    await installMonitoringMock(page);
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('navigation', { name: 'Navegación del panel' }).getByRole('link', { name: 'Monitoreo', exact: true }).click();
    await page.getByRole('button', { name: 'Reports', exact: true }).click();

    await expect(page.getByText('Informational reports are retained for 90 days.', { exact: true })).toHaveCount(1);
    await expect(page.getByRole('button', { name: monitoringReportTitle, exact: true })).toHaveCount(1);
  });

  test('shows a report as read-only text without state or note controls', {
    tag: ['@flow:admin-monitoring-reports', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    await installMonitoringMock(page);
    await page.goto('/panel/monitoring', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Reports', exact: true }).click();
    await page.getByRole('button', { name: monitoringReportTitle, exact: true }).click();

    await expect(caseDetail(page).getByText('Se detectaron 12 consultas N+1.')).toContainText('Se detectaron 12 consultas N+1.');
    await expect(caseDetail(page).getByLabel('Status')).toHaveCount(0);
    await expect(caseDetail(page).getByRole('button', { name: 'Add note', exact: true })).toHaveCount(0);
  });

  test('shows the load alert when reports cannot be retrieved', {
    tag: ['@flow:admin-monitoring-reports', '@outcome:failure', '@role:admin'],
  }, async ({ page }) => {
    await installMonitoringMock(page, { reportsFailure: true });
    await page.goto('/panel/monitoring', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Reports', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('Could not load data. Try refreshing.');
  });

  test('recovers reports after an expired consultation response', {
    tag: ['@flow:admin-monitoring-reports', '@outcome:error', '@role:admin'],
  }, async ({ page }) => {
    await installMonitoringMock(page, { reportsExpiredOnce: true });
    await page.goto('/panel/monitoring', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Reports', exact: true }).click();

    await expect(page.getByRole('alert')).toHaveText('This consultation expired. Use Refresh to continue with the same filters.');
    await page.getByRole('button', { name: 'Refresh', exact: true }).click();

    await expect(page.getByRole('button', { name: monitoringReportTitle, exact: true })).toHaveCount(1);
  });
});
