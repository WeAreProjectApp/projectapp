/**
 * E2E tests for admin proposal activity log / comment flow.
 *
 * Covers: activity tab rendering, submitting activity notes,
 * and viewing activity timeline.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_COMMENT } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;
const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

function _buildSection(id, type, title, order) {
  return { id, section_type: type, title, order, is_enabled: true, is_wide_panel: false, content_json: {} };
}

const mockProposal = {
  id: PROPOSAL_ID,
  uuid: '11111111-1111-1111-1111-111111111111',
  title: 'Comment Test Proposal',
  client_name: 'Test Client',
  client_email: 'test@example.com',
  language: 'es',
  status: 'draft',
  total_investment: '5000000',
  currency: 'COP',
  view_count: 0,
  sent_at: null,
  expires_at: null,
  sections: [_buildSection(101, 'greeting', 'Greeting', 0)],
  requirement_groups: [],
  change_logs: [
    { id: 1, change_type: 'created', description: 'Propuesta creada', created_at: '2026-01-10T10:00:00Z' },
  ],
};

const mockAnalytics = {
  total_views: 0, unique_sessions: 0, first_viewed_at: null,
  time_to_first_view_hours: null, time_to_response_hours: null, responded_at: null,
  comparison: {}, section_views: [], daily_views: [], funnel: [], share_links: [],
  skipped_sections: [], device_breakdown: {}, activity_log: [], sections: [], sessions: [], timeline: [],
};

function setupMock(page, capturedActivities = []) {
  let currentProposal = JSON.parse(JSON.stringify(mockProposal));

  return mockApi(page, async ({ route, apiPath }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(currentProposal) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/analytics/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockAnalytics) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/log-activity/` && route.request().method() === 'POST') {
      const body = route.request().postDataJSON();
      capturedActivities.push(body);
      const newLog = { id: Date.now(), ...body, created_at: new Date().toISOString() };
      currentProposal.change_logs.push(newLog);
      return { status: 201, contentType: 'application/json', body: JSON.stringify(newLog) };
    }
    return null;
  });
}

test.describe('Admin Proposal Comment / Activity', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  test('activity tab shows existing activity log', {
    tag: [...ADMIN_PROPOSAL_COMMENT, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    // Wait for page content instead of networkidle
    await expect(page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Seguimiento', exact: true })).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'tracking', 'activity');

    await expect(page.getByText('Registrar actividad')).toBeVisible();
    await expect(page.getByText('Propuesta creada')).toBeVisible();
  });

  test('activity tab shows activity form with type selector', {
    tag: [...ADMIN_PROPOSAL_COMMENT, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await expect(page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Seguimiento', exact: true })).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'tracking', 'activity');

    await expect(page.getByText('Registrar actividad')).toBeVisible();
    await expect(page.getByPlaceholder('Descripción de la actividad...')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Agregar' })).toBeVisible();
  });

  test('submitting activity note captures correct payload', {
    tag: [...ADMIN_PROPOSAL_COMMENT, '@role:admin'],
  }, async ({ page }) => {
    const captured = [];
    await setupMock(page, captured);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await expect(page.getByTestId('proposal-primary-navigation').getByRole('tab', { name: 'Seguimiento', exact: true })).toBeVisible({ timeout: 15000 });
    await selectProposalDestination(page, 'tracking', 'activity');

    // Wait for the input to be ready before filling
    const descInput = page.getByPlaceholder('Descripción de la actividad...');
    await expect(descInput).toBeVisible();
    await descInput.fill('Llamada de seguimiento con cliente');
    await page.getByRole('button', { name: 'Agregar' }).click();

    // Wait for form to clear (indicates successful submission)
    await expect(page.getByPlaceholder('Descripción de la actividad...')).toHaveValue('', { timeout: 10000 });

    expect(captured.length).toBeGreaterThanOrEqual(1);
    expect(captured[0].description).toBe('Llamada de seguimiento con cliente');
    expect(captured[0].change_type).toBe('note');
  });
});
