/**
 * E2E tests for admin manually logging activity on a proposal.
 *
 * Covers: activity tab renders log form and timeline, submitting a note
 * calls the API and appends to the timeline, empty description disables submit.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_ACTIVITY_LOG } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 5;
const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const mockProposal = {
  id: PROPOSAL_ID,
  uuid: 'log-act-uuid-1234-5678-abcdef',
  title: 'Activity Log Test',
  client_name: 'Log Client',
  client_email: 'log@test.com',
  status: 'sent',
  language: 'es',
  total_investment: '5000000',
  currency: 'COP',
  is_active: true,
  sections: [
    { id: 10, section_type: 'greeting', title: 'Bienvenido', order: 0, is_enabled: true, content_json: { clientName: 'Log Client' } },
  ],
  requirement_groups: [],
  change_logs: [
    { id: 1, change_type: 'created', description: 'Propuesta creada', created_at: '2026-03-01T10:00:00Z' },
    { id: 2, change_type: 'sent', description: 'Enviada al cliente', created_at: '2026-03-02T12:00:00Z' },
  ],
};

const updatedProposal = {
  ...mockProposal,
  change_logs: [
    ...mockProposal.change_logs,
    { id: 3, change_type: 'note', description: 'Llamé al cliente para seguimiento', created_at: '2026-03-05T14:00:00Z' },
  ],
};

test.describe('Admin Proposal Activity Log', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8600, role: 'admin', is_staff: true },
    });
  });

  test('activity tab shows log form and existing timeline entries', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ACTIVITY_LOG, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    // Switch to activity tab
    const activityTab = page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Seguimiento', exact: true });
    await expect(activityTab).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'tracking', 'activity');

    // Log form should be visible
    await expect(page.getByText('Registrar actividad')).toBeVisible({ timeout: 5000 });
    await expect(page.getByPlaceholder(/Descripción de la actividad/i)).toBeVisible();

    // Existing timeline entries should render
    await expect(page.getByText('Propuesta creada')).toBeVisible();
    await expect(page.getByText('Enviada al cliente')).toBeVisible();
  });

  test('submit button is disabled when description is empty', {
    tag: [...ADMIN_PROPOSAL_ACTIVITY_LOG, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    const activityTab = page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Seguimiento', exact: true });
    await expect(activityTab).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'tracking', 'activity');
    await expect(page.getByText('Registrar actividad')).toBeVisible({ timeout: 5000 });

    const submitBtn = page.getByRole('button', { name: /Agregar/i });
    await expect(submitBtn).toBeDisabled();
  });

  test('submitting activity calls API and refreshes timeline', {
    tag: [...ADMIN_PROPOSAL_ACTIVITY_LOG, '@role:admin'],
  }, async ({ page }) => {
    let logCalled = false;
    let capturedPayload = null;

    await mockApi(page, async ({ route, apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        const body = logCalled ? updatedProposal : mockProposal;
        return { status: 200, contentType: 'application/json', body: JSON.stringify(body) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/log-activity/`) {
        logCalled = true;
        capturedPayload = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify({ id: 3, change_type: 'note', description: 'Llamé al cliente para seguimiento' }) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    const activityTab = page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Seguimiento', exact: true });
    await expect(activityTab).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'tracking', 'activity');
    await expect(page.getByText('Registrar actividad')).toBeVisible({ timeout: 5000 });

    // Fill description and submit
    await page.getByPlaceholder(/Descripción de la actividad/i).fill('Llamé al cliente para seguimiento');

    const [logResponse] = await Promise.all([
      page.waitForResponse(r => r.url().includes(`proposals/${PROPOSAL_ID}/log-activity/`)),
      page.getByRole('button', { name: /Agregar/i }).click(),
    ]);
    await logResponse.finished();

    expect(logCalled).toBe(true);
    expect(capturedPayload.change_type).toBe('note');
    expect(capturedPayload.description).toBe('Llamé al cliente para seguimiento');

    // New entry should appear in the timeline
    await expect(page.getByText('Llamé al cliente para seguimiento')).toBeVisible({ timeout: 5000 });
  });
});
