/**
 * Admin visibility for public proposal module interests.
 *
 * Catches regressions where an operator cannot see the modules a client selected
 * or loses the corresponding audit entry after opening the proposal from its list.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';

const PROPOSAL_ID = 144;
const proposalSummary = {
  id: PROPOSAL_ID,
  uuid: 'a1444444-bbbb-4ccc-8ddd-eeeeeeeeeeee',
  title: 'Propuesta de módulos E2E',
  client_name: 'Cliente de módulos',
  client_email: 'cliente-modulos@example.com',
  language: 'es',
  status: 'sent',
  is_active: true,
  total_investment: '5000000',
  currency: 'COP',
  view_count: 2,
  heat_score: 4,
  created_at: '2026-09-20T10:00:00Z',
  last_activity_at: '2026-09-29T12:00:00Z',
};
const proposalDetail = {
  ...proposalSummary,
  sections: [],
  requirement_groups: [],
  module_interests_updated_at: '2026-09-29T12:00:00Z',
  module_interests: [{ id: 97, name_es: 'Reportes semanales', category_es: 'Crecimiento' }],
  change_logs: [{
    id: 14401,
    change_type: 'module_interests',
    description: JSON.stringify([{ id: 97, name_es: 'Reportes semanales', category_es: 'Crecimiento' }]),
    created_at: '2026-09-29T12:00:00Z',
  }],
};

function json(body) {
  return { status: 200, contentType: 'application/json', body: JSON.stringify(body) };
}

async function setupProposalAdminApi(page) {
  await mockApi(page, async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'proposals/') return json([proposalSummary]);
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return json(proposalDetail);
    if (apiPath === `proposals/${PROPOSAL_ID}/analytics/`) return json({
      total_views: 2, unique_sessions: 1, comparison: {}, section_views: [], daily_views: [], funnel: [], share_links: [], skipped_sections: [], device_breakdown: {}, activity_log: [], sections: [], sessions: [], timeline: [],
    });
    if (apiPath === 'proposals/dashboard/') return json({ total: 1, conversion_rate: 0 });
    if (apiPath === 'proposals/alerts/') return json([]);
    if (apiPath === 'panel/dashboard/') return json({
      finance: null,
      proposals: {
        total_proposals: 1,
        conversion_rate: 0,
        by_status: { sent: 1 },
        monthly_trend: [],
        recent: [proposalSummary],
        pipeline_value: 5000000,
        pipeline_count: 1,
      },
      additional_modules: null,
      operations: null,
      attention: [],
    });
    return null;
  });
}

test.describe('Admin proposal module interests', () => {
  test.setTimeout(60_000);

  test('opens a listed proposal and shows its selected modules in General and Activity', {
    tag: ['@flow:admin-proposal-module-interests', '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8144, role: 'admin', is_staff: true },
    });
    await setupProposalAdminApi(page);
    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    const proposalsLink = page.getByRole('link', { name: 'Ver análisis completo' });
    await expect(proposalsLink).toHaveAttribute('href', '/en-us/panel/proposals');
    await proposalsLink.click();

    const proposalLink = page.getByTestId(`proposal-open-${PROPOSAL_ID}`);
    await expect(proposalLink).toContainText('Cliente de módulos');
    await proposalLink.click();
    await expect(page).toHaveURL(new RegExp(`/panel/proposals/${PROPOSAL_ID}/edit`));

    const interests = page.getByTestId('proposal-module-interests');
    await expect(interests).toContainText('Módulos de interés');
    await expect(interests).toContainText('Reportes semanales · Crecimiento');

    await page.getByRole('tab', { name: 'Actividad' }).click();
    await expect(page.getByText('Interés en módulos')).toBeVisible();
    await expect(page.getByText('Módulos de interés: Reportes semanales')).toBeVisible();
  });
});
