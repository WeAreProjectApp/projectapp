/**
 * Editor entry points for explicit proposal-to-project review.
 * Catches the actions menu bypassing review, the old force-launch endpoint
 * recreating data, missing confirmation feedback, or a failed save disabling
 * the sticky review entry permanently.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_PLATFORM_HANDOFF } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 42;
const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });

function makeAcceptedProposal(overrides = {}) {
  return {
    id: PROPOSAL_ID, uuid: 'aaaa1111-bbbb-2222-cccc-3333dddd4444', slug: 'cliente-aceptado',
    title: 'Propuesta Aceptada — Revisión', client_name: 'Cliente Aceptado', client_email: 'cliente@example.com',
    status: 'accepted', language: 'es', total_investment: '15000000', currency: 'COP',
    view_count: 5, sent_at: '2026-04-01T10:00:00Z', accepted_at: '2026-04-15T10:00:00Z',
    expires_at: '2099-01-01T12:00:00Z', is_active: true, sections: [], requirement_groups: [],
    change_logs: [], proposal_documents: [], public_url: '/proposal/cliente-aceptado',
    available_transitions: ['finished'], platform_onboarding_completed_at: null,
    platform_onboarding_status: null, linked_project: null, project_review_required: true,
    ...overrides,
  };
}

function makeState() {
  return {
    proposal: makeAcceptedProposal(), submissions: [], legacyLaunches: [], detailReads: 0,
    client: { profile_id: 201, name: 'Cliente Aceptado', email: 'cliente@example.com' },
    project: { id: 81, name: 'Proyecto Aceptado', client: { profile_id: 201 }, client_profile_id: 201 },
  };
}

function approvalPreview(state) {
  return {
    source_hash: 'b'.repeat(64), client: state.client, linked_project: state.proposal.linked_project,
    commercial_summary: { title: state.proposal.title, total_investment: '15000000', currency: 'COP', payment_milestones: [], hosting_tiers: [] },
    contracts: { modality: 'single', available: true, documents: [{ id: 901, title: 'Contrato acordado', document_type: 'contract' }], error: null },
    optional_documents: [], confirmed: !!state.proposal.linked_project, confirmed_files: [],
    proposal: {
      id: state.proposal.id,
      status: state.proposal.status,
      platform_onboarding_status: state.proposal.platform_onboarding_status,
      platform_onboarding_completed_at: state.proposal.platform_onboarding_completed_at,
      available_transitions: state.proposal.available_transitions,
      project_review_required: state.proposal.project_review_required,
      linked_project: state.proposal.linked_project,
    },
  };
}

async function setupReviewApi(page, state, { fail = false } = {}) {
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      state.detailReads += 1;
      return json({ ...state.proposal });
    }
    if (apiPath === 'projects/') return json({ results: [state.project], meta: { total: 1 } });
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/') return json([]);
    if (apiPath === `proposals/${PROPOSAL_ID}/approval/` && method === 'GET') return json(approvalPreview(state));
    if (apiPath === `proposals/${PROPOSAL_ID}/approval/` && method === 'POST') {
      state.submissions.push(route.request().postDataJSON());
      if (fail) return json({}, 503);
      state.proposal = makeAcceptedProposal({
        linked_project: state.project, project_review_required: false,
        platform_onboarding_status: 'completed', platform_onboarding_completed_at: '2026-10-02T12:00:00Z',
      });
      return json({ ...approvalPreview(state), action: 'confirm', idempotent: false });
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/launch-to-platform/` && method === 'POST') {
      state.legacyLaunches.push(route.request().postDataJSON());
      return json({ detail: 'La vinculación debe confirmarse explícitamente.' }, 409);
    }
    return null;
  });
}

async function openEditor(page) {
  await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('proposal-actions-menu')).toBeVisible({ timeout: 15_000 });
}

async function openReviewFromMenu(page) {
  await page.getByTestId('proposal-actions-menu').click();
  await page.getByTestId('proposal-action-launch').click();
  await expect(page.getByTestId('approval-confirm')).toBeEnabled();
}

async function selectProject(page) {
  const modal = page.getByTestId('proposal-approval-modal');
  await modal.getByRole('radio', { name: 'Select existing project', exact: true }).check();
  await modal.getByTestId('approval-project').selectOption('81');
}

test.describe('Admin Proposal — Platform Handoff Review', () => {
  test.setTimeout(60_000);
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-admin-token', userAuth: { id: 9001, role: 'admin', is_staff: true } });
  });

  test('accepted proposal opens review from its actions menu', {
    tag: [...ADMIN_PROPOSAL_PLATFORM_HANDOFF, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = makeState();
    await setupReviewApi(page, state);
    await openEditor(page);
    await page.getByTestId('proposal-actions-menu').click();
    const review = page.getByTestId('proposal-action-launch');
    await expect(review).toContainText('Completar revisión');
    await review.click();
    await expect(page.getByTestId('approval-client')).toHaveValue('Cliente Aceptado');
    await expect(page.getByTestId('approval-packet-preview')).toContainText('Contrato acordado');
    expect(state.submissions).toEqual([]);
    expect(state.legacyLaunches).toEqual([]);
  });

  test('editor handoff confirms the explicitly selected project', {
    tag: [...ADMIN_PROPOSAL_PLATFORM_HANDOFF, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = makeState();
    await setupReviewApi(page, state);
    await openEditor(page);
    await openReviewFromMenu(page);
    await selectProject(page);
    expect(state.submissions).toEqual([]);
    await page.getByTestId('approval-confirm').click();
    await expect(page.getByTestId('proposal-approval-modal')).toHaveCount(0);
    expect(state.submissions).toHaveLength(1);
    expect(state.submissions[0]).toMatchObject({ action: 'confirm', accept_proposal: false, source_hash: 'b'.repeat(64), client_profile_id: 201, project_id: 81, use_proposal_contracts: true });
    expect(state.submissions[0].force).toBeUndefined();
    expect(state.submissions[0].new_project).toBeUndefined();
    expect(state.legacyLaunches).toEqual([]);
    await expect(page.getByTestId('approval-review-42')).toHaveCount(0);
  });

  test('successful editor handoff shows packet confirmation', {
    tag: [...ADMIN_PROPOSAL_PLATFORM_HANDOFF, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = makeState();
    await setupReviewApi(page, state);
    await openEditor(page);
    await openReviewFromMenu(page);
    await selectProject(page);
    await page.getByTestId('approval-confirm').click();
    await expect(page.getByText('Project linked; packet confirmed.', { exact: true })).toHaveCount(1);
    await expect(page.getByTestId('proposal-next-action-launch')).toHaveCount(0);
    await expect(page.getByTestId('proposal-next-action-finish')).toHaveText('Marcar como finalizada');
    const statusSelect = page.getByRole('combobox', { name: 'Cambiar estado de la propuesta', exact: true });
    await expect(statusSelect.locator('optgroup[label="Flujo normal"] option')).toHaveAttribute('value', 'finished');
    await expect(statusSelect.locator('optgroup[label="Flujo normal"] option')).toHaveText('Finalizada');
    expect(state.detailReads).toBe(1);
    expect(state.submissions).toHaveLength(1);
    expect(state.legacyLaunches).toEqual([]);
  });

  test('failed editor handoff leaves the sticky review entry usable', {
    tag: [...ADMIN_PROPOSAL_PLATFORM_HANDOFF, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches malformed server errors or a sticky CTA left disabled after saving.
    const state = makeState();
    await setupReviewApi(page, state, { fail: true });
    await openEditor(page);
    await openReviewFromMenu(page);
    await selectProject(page);
    await page.getByTestId('approval-confirm').click();
    await expect(page.getByTestId('proposal-approval-modal').getByTestId('approval-review-error')).toContainText('Ocurrió un error. Inténtalo de nuevo.');
    await expect(page.getByTestId('approval-confirm')).toBeEnabled();
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(page.getByTestId('proposal-approval-modal')).toHaveCount(0);
    const sticky = page.getByTestId('proposal-next-action-launch');
    await expect(sticky).toBeEnabled();
    await expect(sticky).toHaveText('Completar revisión');
    await sticky.click();
    await expect(page.getByTestId('approval-confirm')).toBeEnabled();
    expect(state.submissions).toHaveLength(1);
    expect(state.legacyLaunches).toEqual([]);
  });
});
