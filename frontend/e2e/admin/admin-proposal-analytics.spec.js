/**
 * E2E tests for admin proposal analytics tab.
 *
 * Covers: analytics tab rendering, summary cards, comparison badges,
 * and CSV export button visibility.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_PROPOSAL_ANALYTICS,
  ADMIN_PROPOSAL_ENGAGEMENT_SCORE,
  ADMIN_PROPOSAL_FIRST_VIEW_RETRY,
} from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;
const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

function _buildSection(id, type, title, order, contentJson = {}) {
  return { id, section_type: type, title, order, is_enabled: true, is_wide_panel: false, content_json: contentJson };
}

const mockProposal = {
  id: PROPOSAL_ID,
  uuid: '11111111-1111-1111-1111-111111111111',
  title: 'Analytics Test Proposal',
  client_name: 'Test Client',
  client_email: 'test@example.com',
  language: 'es',
  status: 'draft',
  total_investment: '5000000',
  currency: 'COP',
  view_count: 0,
  sent_at: null,
  expires_at: null,
  sections: [
    _buildSection(101, 'greeting', 'Greeting', 0),
    _buildSection(102, 'executive_summary', 'Resumen', 1),
    _buildSection(103, 'context_diagnostic', 'Contexto', 2),
    _buildSection(104, 'conversion_strategy', 'Estrategia', 3),
    _buildSection(105, 'design_ux', 'Diseño', 4),
    _buildSection(106, 'creative_support', 'Soporte', 5),
    _buildSection(107, 'development_stages', 'Etapas', 6),
    _buildSection(108, 'functional_requirements', 'Reqs', 7),
    _buildSection(109, 'timeline', 'Timeline', 8),
    _buildSection(110, 'investment', 'Inversión', 9),
    _buildSection(111, 'final_note', 'Nota Final', 10),
    _buildSection(112, 'next_steps', 'Próximos pasos', 11),
  ],
  requirement_groups: [],
};

const mockAnalytics = {
  total_views: 8,
  unique_sessions: 3,
  first_viewed_at: '2026-01-11T14:30:00Z',
  time_to_first_view_hours: 28.5,
  time_to_response_hours: null,
  responded_at: null,
  comparison: {
    avg_time_to_first_view_hours: 12,
    avg_time_to_response_hours: 48,
    avg_views: 5,
  },
  section_views: [],
  daily_views: [],
  funnel: [],
  share_links: [],
  skipped_sections: [],
  device_breakdown: { desktop: 5, mobile: 2, tablet: 1 },
  activity_log: [],
  sections: [],
  sessions: [],
  timeline: [],
  first_view_notification: {
    status: 'sent',
    attempts: 1,
    attempted_at: '2026-01-11T14:30:10Z',
    sent_at: '2026-01-11T14:30:12Z',
    last_error: '',
    can_retry: false,
  },
};

function setupMock(page, { analytics = mockAnalytics, retryResponse = null } = {}) {
  let retryQueued = false;
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return authCheck;
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
    if (apiPath === `proposals/${PROPOSAL_ID}/analytics/`) {
      const currentAnalytics = retryQueued
        ? { ...analytics, first_view_notification: JSON.parse(retryResponse.body) }
        : analytics;
      return { status: 200, contentType: 'application/json', body: JSON.stringify(currentAnalytics) };
    }
    if (
      apiPath === `proposals/${PROPOSAL_ID}/notifications/first-view/retry/`
      && method === 'POST'
      && retryResponse
    ) {
      retryQueued = retryResponse.status < 400;
      return retryResponse;
    }
    return null;
  });
}

test.describe('Admin Proposal Analytics', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8100, role: 'admin', is_staff: true },
    });
  });

  test('analytics tab renders summary cards with metrics', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ANALYTICS, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'tracking', 'analytics');
    await expect(page.getByRole('button', { name: 'Exportar CSV' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Dispositivos')).toBeVisible();
    await expect(page.getByTestId('first-view-notification-status')).toContainText('Enviado');
  });

  test('analytics tab shows comparison badges', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ANALYTICS, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'tracking', 'analytics');
    await expect(page.getByRole('button', { name: 'Exportar CSV' })).toBeVisible({ timeout: 15000 });
  });

  test('analytics tab shows CSV export button', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ANALYTICS, '@role:admin'],
  }, async ({ page }) => {
    await setupMock(page);
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'tracking', 'analytics');
    await expect(page.getByRole('button', { name: 'Exportar CSV' })).toBeVisible({ timeout: 15000 });
  });

  test('analytics tab renders engagement score with color-coded level', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ENGAGEMENT_SCORE, '@role:admin'],
  }, async ({ page }) => {
    const analyticsWithScore = { ...mockAnalytics, engagement_score: 75 };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      if (apiPath === `proposals/${PROPOSAL_ID}/analytics/`) return { status: 200, contentType: 'application/json', body: JSON.stringify(analyticsWithScore) };
      return null;
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'tracking', 'analytics');
    await expect(page.getByText('Engagement Score')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('75', { exact: true })).toBeVisible();
    await expect(page.getByText(/Alto engagement/)).toBeVisible();
  });

  test('engagement score shows low engagement warning when score is below 40', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_ENGAGEMENT_SCORE, '@role:admin'],
  }, async ({ page }) => {
    const analyticsLowScore = { ...mockAnalytics, engagement_score: 20 };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      if (apiPath === `proposals/${PROPOSAL_ID}/analytics/`) return { status: 200, contentType: 'application/json', body: JSON.stringify(analyticsLowScore) };
      return null;
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'tracking', 'analytics');
    await expect(page.getByText('Engagement Score')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Bajo engagement/)).toBeVisible();
  });

  test('admin retries a failed first-view alert', {
    tag: ['@outcome:success', ...ADMIN_PROPOSAL_FIRST_VIEW_RETRY, '@role:admin'],
  }, async ({ page }) => {
    const failedNotification = {
      status: 'failed', attempts: 4, attempted_at: '2026-01-11T14:30:10Z',
      sent_at: null, last_error: 'SMTP timeout', can_retry: true,
    };
    const pendingNotification = {
      status: 'pending', attempts: 0, attempted_at: null,
      sent_at: null, last_error: '', can_retry: false,
    };
    await setupMock(page, {
      analytics: { ...mockAnalytics, first_view_notification: failedNotification },
      retryResponse: {
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify(pendingNotification),
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'tracking', 'analytics');

    await expect(page.getByTestId('first-view-notification-status')).toContainText('SMTP timeout');
    await page.getByTestId('retry-first-view-notification').click();

    await expect(page.getByTestId('first-view-notification-status')).toContainText('Pendiente');
    await expect(page.getByTestId('retry-first-view-notification')).not.toBeVisible();
  });

  test('admin sees a failure when first-view retry is rejected', {
    tag: ['@outcome:failure', ...ADMIN_PROPOSAL_FIRST_VIEW_RETRY, '@role:admin'],
  }, async ({ page }) => {
    const failedNotification = {
      status: 'failed', attempts: 4, attempted_at: '2026-01-11T14:30:10Z',
      sent_at: null, last_error: 'SMTP timeout', can_retry: true,
    };
    await setupMock(page, {
      analytics: { ...mockAnalytics, first_view_notification: failedNotification },
      retryResponse: {
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'queue unavailable' }),
      },
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
    await selectProposalDestination(page, 'tracking', 'analytics');

    await page.getByTestId('retry-first-view-notification').click();

    await expect(page.getByTestId('first-view-notification-status')).toContainText('Falló');
    await expect(page.getByTestId('retry-first-view-notification')).toBeVisible();
  });
});
