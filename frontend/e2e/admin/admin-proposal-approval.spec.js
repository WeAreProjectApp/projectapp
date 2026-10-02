/**
 * Explicit approval review from the Panel, with the API as the mocked boundary.
 * Catches approval provisioning before confirmation, lost deferred reviews,
 * custom contracts being replaced by originals, dropped form values on errors,
 * duplicated confirmation on retry, inaccessible Escape, and modal overflow.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

const SOURCE_HASH = 'a'.repeat(64);
const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });

function buildFixture({ status = 'negotiating', confirmed = false } = {}) {
  const client = { id: 101, name: 'Cliente Atlas', email: 'atlas@example.test', phone: '+573001234567', company: 'Atlas', nit: '900123456', billing_code: 'ATLAS' };
  const project = { id: 41, name: 'Portal Atlas', client_profile_id: client.id, client_name: client.name, client: { id: 701, profile_id: client.id } };
  const proposal = {
    id: 71, uuid: '11111111-1111-4111-8111-111111111171', title: 'Propuesta Portal Atlas',
    client_name: client.name, client_email: client.email, client_phone: client.phone, client,
    status, language: 'es', total_investment: '5000000', currency: 'COP',
    is_active: true, view_count: 2, heat_score: 0, sections: [], requirement_groups: [],
    created_at: '2026-09-01T12:00:00Z', expires_at: '2099-01-01T12:00:00Z',
    available_transitions: status === 'accepted' ? ['finished'] : ['accepted', 'rejected'],
    project_review_required: status === 'accepted' && !confirmed,
    linked_project: confirmed ? project : null,
    platform_onboarding_status: confirmed ? 'completed' : null,
  };
  return { client, project, proposal, confirmed, submissions: [], otherMutations: [] };
}

function preview(state) {
  return {
    source_hash: SOURCE_HASH,
    client: { ...state.client, profile_id: state.client.id },
    linked_project: state.proposal.linked_project,
    commercial_summary: {
      title: state.proposal.title, total_investment: state.proposal.total_investment, currency: 'COP',
      payment_milestones: [{ label: 'Anticipo', percentage: 50, amount: '2500000' }],
      hosting_tiers: [{ months: 1, total: '150000' }],
    },
    contracts: {
      modality: 'single', available: true, error: null,
      documents: [{ id: 601, title: 'Contrato de producto y servicio Atlas', document_type: 'contract' }],
    },
    optional_documents: [],
    confirmed: state.confirmed,
    confirmed_files: state.confirmed ? [
      { id: 801, title: 'Detalle comercial', document_type: 'commercial', filename: 'comercial.pdf' },
      { id: 802, title: 'Detalle técnico', document_type: 'technical', filename: 'tecnico.pdf' },
    ] : [],
    proposal: { ...state.proposal },
  };
}

function readSubmission(request) {
  const contentType = request.headers()['content-type'] || '';
  if (!contentType.startsWith('multipart/form-data')) {
    return { payload: request.postDataJSON(), files: [] };
  }
  const boundary = contentType.match(/boundary=(?:"([^"]+)"|([^;]+))/);
  const parts = request.postDataBuffer().toString('utf8').split(`--${boundary[1] || boundary[2]}`).slice(1, -1);
  let payload;
  const files = [];
  for (const part of parts) {
    const separator = part.indexOf('\r\n\r\n');
    const header = part.slice(0, separator);
    const value = part.slice(separator + 4, -2);
    const name = header.match(/name="([^"]+)"/)?.[1];
    const filename = header.match(/filename="([^"]+)"/)?.[1];
    if (name === 'payload') payload = JSON.parse(value);
    if (name === 'custom_files[]') files.push({ filename, content: value });
  }
  return { payload, files };
}

async function mockApproval(page, state, { rejectFirst = null } = {}) {
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'proposals/') return json([{ ...state.proposal }]);
    if (apiPath === 'proposals/dashboard/') return json({});
    if (apiPath === 'proposals/alerts/') return json([]);
    if (apiPath === 'proposals/71/detail/') return json({ ...state.proposal });
    if (apiPath === 'proposals/client-profiles/search/' || apiPath === 'proposals/client-profiles/') {
      if (method === 'GET') return json([state.client]);
    }
    if (apiPath === 'accounting/projects/') return json({ results: [state.project] });
    if (apiPath === 'projects/') return json({ results: [state.project], meta: { total: 1 } });
    if (apiPath === 'project-states/') return json([{ id: 2, name: 'En desarrollo', is_active: true, merged_into: null, system_key: 'development' }]);
    if (apiPath === 'project-state-groups/') return json([]);
    if (apiPath === 'proposals/71/approval/' && method === 'GET') return json(preview(state));
    if (apiPath === 'proposals/71/approval/' && method === 'POST') {
      const submission = readSubmission(route.request());
      state.submissions.push(submission);
      if (rejectFirst && state.submissions.length === 1) return json(rejectFirst.body, rejectFirst.status);
      if (submission.payload.action === 'defer') {
        Object.assign(state.proposal, { status: 'accepted', project_review_required: true, linked_project: null, available_transitions: ['finished'] });
      } else {
        state.confirmed = true;
        if (submission.payload.new_client) state.client = { ...submission.payload.new_client, id: 102 };
        if (submission.payload.new_project) state.project = { id: 42, name: submission.payload.new_project.name, client_profile_id: state.client.id };
        Object.assign(state.proposal, {
          status: 'accepted', project_review_required: false, linked_project: state.project,
          platform_onboarding_status: 'completed', available_transitions: ['finished'],
        });
      }
      return json({ ...preview(state), action: submission.payload.action, idempotent: false });
    }
    if (method !== 'GET') state.otherMutations.push({ apiPath, method });
    return null;
  });
}

async function openList(page) {
  await page.goto('/panel/proposals', { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('proposal-actions-71')).toBeVisible({ timeout: 25_000 });
}

test.beforeEach(async ({ page }) => {
  await setAuthLocalStorage(page, { token: 'approval-e2e-token', userAuth: { id: 8000, role: 'admin', is_staff: true, is_superuser: true } });
});

async function openInlineApproval(page) {
  const row = page.getByRole('row').filter({ has: page.getByTestId('proposal-open-71') });
  await row.getByRole('combobox').selectOption('accepted');
  await expect(page.getByTestId('approval-confirm')).toBeEnabled();
}

async function selectExistingProject(page) {
  const modal = page.getByTestId('proposal-approval-modal');
  await modal.getByRole('radio', { name: 'Select existing project', exact: true }).check();
  await modal.getByTestId('approval-project').selectOption('41');
}

function customFiles() {
  return [
    { name: 'contrato-firmado.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\nContrato firmado por correo\n%%EOF') },
    { name: 'anexo-alcance.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\nAnexo de alcance acordado\n%%EOF') },
  ];
}

function newClientScenario() {
  return { name: 'Cliente Firma Correo', email: 'firma@example.test', projectName: 'Proyecto Firma Correo' };
}

async function stageCustomDocuments(page) {
  const modal = page.getByTestId('proposal-approval-modal');
  await modal.getByTestId('approval-contract-switch').click();
  await modal.getByTestId('approval-custom-files').setInputFiles(customFiles());
  const rows = modal.getByTestId('approval-custom-document');
  await rows.nth(0).getByRole('textbox', { name: 'Document title', exact: true }).fill('Contrato firmado Atlas');
  await rows.nth(1).getByRole('textbox', { name: 'Document title', exact: true }).fill('Anexo de alcance Atlas');
  await rows.nth(1).getByRole('combobox', { name: 'Document type', exact: true }).selectOption('legal_annex');
}

async function expectAccepted(page) {
  const row = page.getByRole('row').filter({ has: page.getByTestId('proposal-open-71') });
  await expect(row.getByRole('combobox')).toHaveValue('accepted');
}

test('inline approval links the selected project only after confirmation', {
  tag: ['@flow:admin-proposal-approval', '@module:admin', '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  // Catches the old status PATCH silently creating a project before review.
  const state = buildFixture();
  await mockApproval(page, state);
  await openList(page);
  await openInlineApproval(page);
  await selectExistingProject(page);
  await expect(page.getByTestId('approval-packet-preview')).toContainText('Contrato de producto y servicio Atlas');
  expect(state.submissions).toEqual([]);
  expect(state.otherMutations).toEqual([]);
  await page.getByTestId('approval-confirm').click();
  await expect(page.getByTestId('proposal-approval-modal')).toHaveCount(0);
  await expectAccepted(page);
  expect(state.submissions).toHaveLength(1);
  expect(state.submissions[0].payload).toMatchObject({
    action: 'confirm', accept_proposal: true, client_profile_id: 101, project_id: 41,
    source_hash: SOURCE_HASH, use_proposal_contracts: true, selected_document_ids: [],
  });
  expect(state.submissions[0].payload.new_project).toBeUndefined();
  expect(state.submissions[0].files).toEqual([]);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expectAccepted(page);
  await expect(page.getByTestId('approval-review-71')).toHaveCount(0);
});

test('deferred approval can resume from the accepted pending row', {
  tag: ['@flow:admin-proposal-approval', '@module:admin', '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  // Catches accepted proposals losing the review action after leaving the modal.
  const state = buildFixture();
  await mockApproval(page, state);
  await openList(page);
  await openInlineApproval(page);
  await page.getByTestId('approval-defer').click();
  await expect(page.getByTestId('proposal-approval-modal')).toHaveCount(0);
  await expectAccepted(page);
  expect(state.submissions).toEqual([{ payload: { action: 'defer', accept_proposal: true }, files: [] }]);
  expect(state.proposal.linked_project).toBeNull();
  expect(state.otherMutations).toEqual([]);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByTestId('approval-review-71').click();
  await expect(page.getByTestId('approval-confirm')).toBeEnabled();
  await selectExistingProject(page);
  await page.getByTestId('approval-confirm').click();
  await expect(page.getByTestId('proposal-approval-modal')).toHaveCount(0);
  await expect(page.getByTestId('approval-review-71')).toHaveCount(0);
  expect(state.submissions[1].payload).toMatchObject({ action: 'confirm', accept_proposal: false, client_profile_id: 101, project_id: 41 });
});

test('custom closure creates the staged client with both uploaded documents', {
  tag: ['@flow:admin-proposal-approval', '@module:admin', '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  // Catches lost annexes or original contracts leaking into the custom packet.
  const state = buildFixture();
  const scenario = newClientScenario();
  await mockApproval(page, state);
  await openList(page);
  await openInlineApproval(page);
  const modal = page.getByTestId('proposal-approval-modal');
  await modal.getByTestId('approval-toggle-client').click();
  await modal.getByTestId('approval-new-client-name').fill(scenario.name);
  await modal.getByTestId('approval-new-client-email').fill(scenario.email);
  await modal.getByTestId('approval-project-name').fill(scenario.projectName);
  await stageCustomDocuments(page);
  const packet = modal.getByTestId('approval-packet-preview');
  await expect(packet).toContainText('Commercial details');
  await expect(packet).toContainText('Technical details');
  await expect(packet).toContainText('Contrato firmado Atlas');
  await expect(packet).toContainText('Anexo de alcance Atlas');
  await expect(packet).not.toContainText('Contrato de producto y servicio Atlas');
  expect(state.otherMutations).toEqual([]);
  expect(state.submissions).toEqual([]);
  await page.getByTestId('approval-confirm').click();
  await expect(modal).toHaveCount(0);
  const submission = state.submissions[0];
  expect(submission.payload).toMatchObject({
    action: 'confirm', use_proposal_contracts: false,
    new_client: { name: scenario.name, email: scenario.email },
    new_project: { name: scenario.projectName, state_id: 2 },
    selected_document_ids: [],
    custom_documents: [{ title: 'Contrato firmado Atlas', document_type: 'contract' }, { title: 'Anexo de alcance Atlas', document_type: 'legal_annex' }],
  });
  expect(submission.payload.client_profile_id).toBeUndefined();
  expect(submission.payload.project_id).toBeUndefined();
  expect(submission.files).toEqual(customFiles().map((file) => ({ filename: file.name, content: file.buffer.toString('utf8') })));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expectAccepted(page);
  await expect(page.getByTestId('approval-review-71')).toHaveCount(0);
});

test('document validation preserves the entered custom packet', {
  tag: ['@flow:admin-proposal-approval', '@module:admin', '@role:admin', '@outcome:error'],
}, async ({ page }) => {
  // Catches confirming without custom files or clearing files after a field error.
  const state = buildFixture();
  await mockApproval(page, state, { rejectFirst: { status: 400, body: { custom_documents: ['El anexo debe incluir la firma del cliente.'] } } });
  await openList(page);
  await openInlineApproval(page);
  await selectExistingProject(page);
  const modal = page.getByTestId('proposal-approval-modal');
  await modal.getByTestId('approval-contract-switch').click();
  await page.getByTestId('approval-confirm').click();
  await expect(modal.getByTestId('approval-review-error')).toContainText('Attach at least one valid document.');
  expect(state.submissions).toEqual([]);
  await modal.getByTestId('approval-custom-files').setInputFiles(customFiles());
  await modal.getByTestId('approval-custom-document').nth(1).getByRole('textbox', { name: 'Document title', exact: true }).fill('Anexo firmado pendiente');
  await page.getByTestId('approval-confirm').click();
  await expect(modal.getByTestId('approval-review-error')).toContainText('El anexo debe incluir la firma del cliente.');
  await expect(modal.getByTestId('approval-custom-document')).toHaveCount(2);
  await expect(modal.getByTestId('approval-custom-document').nth(1).getByRole('textbox', { name: 'Document title', exact: true })).toHaveValue('Anexo firmado pendiente');
  await expect(modal.getByTestId('approval-project')).toHaveValue('41');
  await expect(modal.getByTestId('approval-contract-switch')).toHaveAttribute('aria-checked', 'false');
  expect(state.submissions).toHaveLength(1);
  expect(state.proposal.status).toBe('negotiating');
});

test('failed confirmation retries the identical staged packet', {
  tag: ['@flow:admin-proposal-approval', '@module:admin', '@role:admin', '@outcome:failure'],
}, async ({ page }) => {
  // Catches a transient server failure replacing the request key or losing uploads.
  const state = buildFixture();
  await mockApproval(page, state, { rejectFirst: { status: 503, body: { detail: 'No se pudo guardar el paquete. Inténtalo de nuevo.' } } });
  await openList(page);
  await openInlineApproval(page);
  const modal = page.getByTestId('proposal-approval-modal');
  await modal.getByTestId('approval-project-name').fill('Proyecto recuperable');
  await stageCustomDocuments(page);
  await page.getByTestId('approval-confirm').click();
  await expect(modal.getByTestId('approval-review-error')).toContainText('No se pudo guardar el paquete. Inténtalo de nuevo.');
  await expect(modal.getByTestId('approval-project-name')).toHaveValue('Proyecto recuperable');
  await expect(modal.getByTestId('approval-custom-document')).toHaveCount(2);
  await page.getByTestId('approval-confirm').click();
  await expect(modal).toHaveCount(0);
  await expectAccepted(page);
  expect(state.submissions).toHaveLength(2);
  expect(state.submissions[1]).toEqual(state.submissions[0]);
  expect(state.submissions[0].payload.request_id).toMatch(/^[a-f0-9-]{36}$/);
  expect(state.otherMutations).toEqual([]);
});

test('review packet is reachable through proposal navigation', {
  tag: ['@flow:admin-proposal-approval', '@module:admin', '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  // Catches the pending-review action being hidden for a commercially accepted deal.
  const state = buildFixture({ status: 'accepted' });
  await mockApproval(page, state);
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Propuestas', exact: true }).click();
  await page.getByTestId('approval-review-71').click();
  const modal = page.getByTestId('proposal-approval-modal');
  await expect(modal.getByTestId('approval-client')).toHaveValue('Cliente Atlas');
  await expect(modal).toContainText('5,000,000 COP');
  await expect(modal.getByTestId('approval-packet-preview')).toContainText('Contrato de producto y servicio Atlas');
  await expect(modal.getByTestId('approval-packet-preview')).toContainText('Technical details');
  expect(state.submissions).toEqual([]);
});

for (const alias of ['compact', 'portrait']) {
  test.describe(`approval modal at ${alias}`, () => {
    test.use(viewportUse(alias));

    test('Escape discards staged documents without changing the pending approval', {
      tag: ['@flow:admin-proposal-approval', '@module:admin', '@role:admin', '@outcome:success', `@viewport:${alias}`],
    }, async ({ page }) => {
      // quality: allow-duplicate (per-viewport contract: approval Escape and overflow at compact/portrait)
      // Catches cancel persisting staged files or returning focus to a detached control.
      const state = buildFixture({ status: 'accepted' });
      await mockApproval(page, state);
      await openList(page);
      const opener = page.getByTestId('approval-review-71');
      await opener.click();
      const modal = page.getByTestId('proposal-approval-modal');
      await expect(page.getByTestId('approval-confirm')).toBeEnabled();
      await stageCustomDocuments(page);
      await expect(modal.getByTestId('approval-custom-document')).toHaveCount(2);
      await expect.poll(() => page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
      await page.keyboard.press('Escape');
      await expect(modal).toHaveCount(0);
      await expect(opener).toBeFocused();
      expect(state.submissions).toEqual([]);
      expect(state.otherMutations).toEqual([]);
      await opener.click();
      await expect(page.getByTestId('approval-confirm')).toBeEnabled();
      await expect(modal.getByTestId('approval-contract-switch')).toHaveAttribute('aria-checked', 'true');
      await expect(modal.getByTestId('approval-custom-document')).toHaveCount(0);
      expect(state.proposal.status).toBe('accepted');
      expect(state.proposal.linked_project).toBeNull();
    });
  });
}
