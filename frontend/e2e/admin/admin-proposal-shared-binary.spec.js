/**
 * Falla si la página del Gestor desmonta el editor al revisar un conflicto y
 * pierde el archivo local. HTTP simula la concurrencia; Vue y Pinia son reales.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { PROPOSAL_ID, buildProposal, buildHandler, json, openDocumentsFromPanel } from '../helpers/contract-modals.js';

test.setTimeout(60_000);

const DOCUMENT_ID = 91;
const ATTACHMENT_NAME = 'anexo-retenido.pdf';
const ATTACHMENT_CONTENT = '%PDF-1.4\nQA retention fixture\n%%EOF';

function fixture() {
  const project = { id: 41, name: 'Portal Atlas', client_profile_id: 7 };
  return {
    proposal: buildProposal({ status: 'accepted', approval_package_number: 2, linked_project: project, project_review_required: false }),
    project, sourceHash: 'source-opened', pending: false, reviewUnavailable: false, submissions: [],
  };
}

function source(state) {
  return {
    document_id: DOCUMENT_ID, proposal_id: PROPOSAL_ID, source_key: 'original-701',
    source_hash: state.sourceHash, can_replace_binary: true, has_pending_changes: state.pending,
    is_current: true, package_number: 2, current_file_id: 802,
    source_editor_url: `/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`,
    history: [{ id: 802, package_number: 2, title: 'Anexo Atlas', filename: 'anexo-v2.pdf', download_url: `/api/proposals/${PROPOSAL_ID}/approval/files/802/` }],
  };
}

function preview(state) {
  return {
    confirmed: true, use_proposal_contracts: true, package_number: 2, source_hash: state.sourceHash,
    client: { profile_id: 7, name: 'Atlas' }, linked_project: state.project,
    commercial_summary: { title: state.proposal.title, total_investment: '12000000', currency: 'COP', payment_milestones: [], hosting_tiers: [] },
    contracts: { available: true, modality: 'single', documents: [{ id: 501, title: 'Contrato Atlas' }] },
    optional_documents: [],
    confirmed_files: [{ id: 802, title: 'Anexo Atlas', filename: 'anexo-v2.pdf', document_type: 'legal_annex', download_url: `/api/proposals/${PROPOSAL_ID}/approval/files/802/` }],
    shared_documents: [source(state)],
  };
}

function submittedDraft(request) {
  const body = request.postData() || '';
  return {
    source_hash: body.match(/name="source_hash"\r\n\r\n([^\r]*)/)?.[1],
    filename: body.match(/name="file"; filename="([^"]*)"/)?.[1],
    content: body.match(/name="file"; filename="[^"]*"\r\n[\s\S]*?\r\n\r\n([\s\S]*?)\r\n--/)?.[1],
  };
}

async function mockSharedBinary(page, state) {
  const proposalHandler = buildHandler(state);
  await mockApi(page, async args => {
    const { apiPath, method, route } = args;
    if (apiPath === `proposals/${PROPOSAL_ID}/approval/` && method === 'GET') return json(200, preview(state));
    if (apiPath === `documents/${DOCUMENT_ID}/detail/`) {
      return json(200, { id: DOCUMENT_ID, title: 'Anexo Atlas', folder: null, language: 'es', proposal_source: source(state) });
    }
    if (apiPath === `documents/${DOCUMENT_ID}/proposal-source/`) {
      if (method === 'GET' && state.reviewUnavailable) return json(503, { detail: 'No disponible.' });
      if (method === 'POST') {
        const submitted = submittedDraft(route.request());
        state.submissions.push(submitted);
        if (submitted.source_hash !== state.sourceHash) return json(409, { detail: 'La fuente cambió.', code: 'stale_source' });
        state.sourceHash = 'source-saved';
        state.pending = true;
      }
      return json(200, { document: source(state), approval: preview(state) });
    }
    if (['document-states/', 'document-state-groups/', 'document-folders/'].includes(apiPath)) return json(200, []);
    if (apiPath === `documents/${DOCUMENT_ID}/communications/` || apiPath === `documents/${DOCUMENT_ID}/email-usage/`) return json(200, { count: 0, results: [] });
    if (apiPath === 'projects/') return json(200, { results: [state.project] });
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/') return json(200, []);
    return proposalHandler(args);
  });
}

async function openConflict(page, state) {
  await mockSharedBinary(page, state);
  await openDocumentsFromPanel(page);
  await page.getByTestId('proposal-shared-documents').getByRole('link', { name: 'Anexo Atlas', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/es-co/panel/documents/${DOCUMENT_ID}/edit$`));
  await expect(page.getByTestId('document-detail-id')).toHaveText(`#${DOCUMENT_ID}`);
  await page.getByTestId('shared-binary-file').setInputFiles({ name: ATTACHMENT_NAME, mimeType: 'application/pdf', buffer: Buffer.from(ATTACHMENT_CONTENT) });
  // Another editor changes the server source after this editor captured H0.
  state.sourceHash = 'source-concurrent';
  state.pending = true;
  await page.getByTestId('shared-binary-save').click();
  await expect(page.getByTestId('shared-binary-editor').getByRole('alert')).toContainText('La fuente cambió. Conservamos tu archivo');
}

test.beforeEach(async ({ page }) => {
  await setAuthLocalStorage(page, { token: 'shared-binary-token', userAuth: { id: 8110, role: 'admin', is_staff: true } });
});

test('reviewing a stale source retains the selected attachment', {
  tag: ['@flow:admin-proposal-shared-documents', '@module:admin', '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const state = fixture();
  await openConflict(page, state);

  await page.getByTestId('shared-binary-review').click();

  await expect(page.getByTestId('shared-binary-editor').getByRole('status')).toContainText('Versión actual consultada.');
  await expect(page.getByTestId('proposal-shared-documents')).toContainText('Paquete vigente 2 · Borrador pendiente');
  await expect(page.getByTestId('shared-binary-save')).toBeEnabled();
  expect(await page.getByTestId('shared-binary-file').evaluate(input => Array.from(input.files, file => file.name))).toEqual([ATTACHMENT_NAME]);
  expect(state.submissions).toHaveLength(1);
  await page.getByTestId('shared-binary-save').click();

  await expect(page.getByTestId('shared-binary-editor').getByRole('status')).toContainText('Borrador guardado.');
  await expect(page.getByTestId('shared-binary-save')).toBeDisabled();
  expect(state.submissions).toEqual([
    { source_hash: 'source-opened', filename: ATTACHMENT_NAME, content: ATTACHMENT_CONTENT },
    { source_hash: 'source-concurrent', filename: ATTACHMENT_NAME, content: ATTACHMENT_CONTENT },
  ]);
});

test('a failed source review retains the selected attachment', {
  tag: ['@flow:admin-proposal-shared-documents', '@module:admin', '@role:admin', '@outcome:failure'],
}, async ({ page }) => {
  const state = fixture();
  state.reviewUnavailable = true;
  await openConflict(page, state);

  await page.getByTestId('shared-binary-review').click();

  await expect(page.getByTestId('shared-binary-editor').getByRole('alert')).toHaveText('No se pudo consultar la versión actual. Conservamos tu archivo.');
  await expect(page.getByTestId('shared-binary-save')).toBeEnabled();
  await expect(page.getByTestId('shared-binary-review')).toBeEnabled();
  expect(await page.getByTestId('shared-binary-file').evaluate(input => Array.from(input.files, file => file.name))).toEqual([ATTACHMENT_NAME]);
  expect(state.submissions).toEqual([{ source_hash: 'source-opened', filename: ATTACHMENT_NAME, content: ATTACHMENT_CONTENT }]);
});
