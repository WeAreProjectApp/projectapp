/**
 * Catches the Clients inline approval bypassing the shared review modal or
 * leaving its cached proposal row stale after an approval deferred for review.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';

test.setTimeout(60_000);

const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

function buildClientReviewFixture() {
  const client = {
    id: 101, name: 'Cliente Cierre por Correo', email: 'cierre@example.test', phone: '', company: 'Cierre SAS',
    is_onboarded: false, is_email_placeholder: false, total_proposals: 1, total_projects: 0,
    is_orphan: false, is_archived: false, created_at: '2026-09-01T10:00:00Z', updated_at: '2026-10-01T10:00:00Z',
  };
  const proposal = {
    id: 71, title: 'Portal Cierre por Correo', client_name: client.name, client_email: client.email,
    status: 'negotiating', available_transitions: ['accepted', 'rejected'], total_investment: '5000000',
    currency: 'COP', view_count: 3, sent_at: '2026-09-01T12:00:00Z', project_review_required: false,
    linked_project: null, platform_onboarding_status: null, platform_onboarding_completed_at: null,
  };
  return { client, proposal, writes: [], detailReads: [], listReads: 0 };
}

function approvalPreview(state) {
  return {
    source_hash: 'c'.repeat(64), client: { profile_id: state.client.id, name: state.client.name, email: state.client.email },
    linked_project: null, commercial_summary: { title: state.proposal.title, total_investment: '5000000', currency: 'COP', payment_milestones: [], hosting_tiers: [] },
    contracts: { modality: 'single', available: true, error: null, documents: [{ id: 601, title: 'Contrato Cierre por Correo', document_type: 'contract' }] },
    optional_documents: [], confirmed_files: [], confirmed: false,
    proposal: {
      id: state.proposal.id, status: state.proposal.status, platform_onboarding_status: null,
      platform_onboarding_completed_at: null, available_transitions: state.proposal.available_transitions,
      project_review_required: state.proposal.project_review_required, linked_project: null,
    },
  };
}

async function mockClientReview(page, state) {
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (method !== 'GET') state.writes.push({ apiPath, method, payload: route.request().postDataJSON() });
    if (apiPath === 'proposals/client-profiles/status-counts/') return json({ all: 1, active: 1, orphans: 0, archived: 0 });
    if (apiPath === 'proposals/client-profiles/') {
      state.listReads += 1;
      return json([state.client]);
    }
    if (apiPath === 'proposals/client-profiles/101/') {
      state.detailReads.push(101);
      return json({ ...state.client, proposals: [{ ...state.proposal }], projects: [], diagnostics: [], hostings: [], incomes: [], documents: [] });
    }
    if (apiPath === 'proposals/71/approval/' && method === 'GET') return json(approvalPreview(state));
    if (apiPath === 'proposals/71/approval/' && method === 'POST') {
      Object.assign(state.proposal, { status: 'accepted', available_transitions: ['finished'], project_review_required: true });
      return json({ ...approvalPreview(state), action: 'defer', idempotent: false });
    }
    if (apiPath === 'projects/') return json({ results: [], meta: { total: 0 } });
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/') return json([]);
    return null;
  });
}

test('Clients inline approval defers through the shared review modal', {
  tag: ['@flow:admin-proposal-approval', '@module:admin', '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const state = buildClientReviewFixture();
  await setAuthLocalStorage(page, { token: 'client-approval-token', userAuth: { id: 8000, role: 'admin', is_staff: true } });
  await mockClientReview(page, state);
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Clientes', exact: true }).click();
  const header = page.getByTestId('client-header-101');
  await expect(header).toContainText(state.client.name);
  await header.click();
  const proposalRow = page.getByTestId('client-proposal-row-71');
  await expect(proposalRow).toContainText(state.proposal.title);
  await expect(proposalRow.getByRole('combobox')).toHaveValue('negotiating');
  const listReadsBeforeApproval = state.listReads;
  await proposalRow.getByRole('combobox').selectOption('accepted');
  await expect(page.getByTestId('approval-defer')).toBeEnabled();
  await expect(page.getByTestId('proposal-approval-modal').getByTestId('approval-client')).toHaveValue(state.client.name);
  await expect(proposalRow.getByRole('combobox')).toHaveValue('negotiating');
  expect(state.writes).toEqual([]);
  await page.getByTestId('approval-defer').click();
  await expect(page.getByTestId('proposal-approval-modal')).toHaveCount(0);
  await expect(proposalRow.getByRole('combobox')).toHaveValue('accepted');
  await expect(proposalRow.getByTestId('client-approval-review-71')).toHaveText('Pending internal review');
  expect(state.writes).toEqual([{ apiPath: 'proposals/71/approval/', method: 'POST', payload: { action: 'defer', accept_proposal: true } }]);
  expect(state.detailReads).toEqual([101, 101]);
  // The existing refresh reloads the read-only list to update client counters.
  expect(state.listReads).toBe(listReadsBeforeApproval + 1);
  expect(state.proposal.linked_project).toBeNull();
});
