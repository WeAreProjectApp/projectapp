/**
 * Falla si el paquete aprobado deja de ser alcanzable desde Documentos, si una
 * revisión se confirma por el endpoint inicial o si un fallo borra el borrador.
 * Los HTTP simulan el servidor: estos specs verifican interacción y UI, no DB.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { viewportUse } from '../helpers/viewports.js';
import { expectCompactModal } from '../helpers/modal-layout.js';
import { PROPOSAL_ID, buildProposal, buildHandler, json, openDocuments, openDocumentsFromPanel } from '../helpers/contract-modals.js';

test.setTimeout(60_000);

function fixture() {
  const project = { id: 41, name: 'Portal Atlas', client_profile_id: 7 };
  return {
    proposal: buildProposal({ status: 'accepted', approval_package_number: 2, linked_project: project, project_review_required: false }),
    project, packageNumber: 2, pending: true, submissions: [],
  };
}

function preview(state) {
  return {
    confirmed: true, use_proposal_contracts: true, package_number: state.packageNumber, source_hash: 'approval-version-2',
    client: { profile_id: 7, name: 'Atlas' }, linked_project: state.project,
    commercial_summary: { title: state.proposal.title, total_investment: '12000000', currency: 'COP', payment_milestones: [], hosting_tiers: [] },
    contracts: { available: true, modality: 'single', documents: [{ id: 501, title: 'Contrato Atlas' }] },
    optional_documents: [],
    confirmed_files: [{ id: 802, title: 'Contrato Atlas', filename: 'atlas-v2.pdf', document_type: 'contract', download_url: `/api/proposals/${PROPOSAL_ID}/approval/files/802/` }],
    shared_documents: [{
      document_id: 91, source_key: 'contract:single', current_file_id: 802, is_current: true, has_pending_changes: state.pending,
      history: [
        { id: 802, package_number: 2, title: 'Contrato Atlas', filename: 'atlas-v2.pdf', download_url: `/api/proposals/${PROPOSAL_ID}/approval/files/802/` },
        { id: 801, package_number: 1, title: 'Contrato Atlas', filename: 'atlas-v1.pdf', download_url: `/api/proposals/${PROPOSAL_ID}/approval/files/801/` },
      ],
    }],
  };
}

async function mockSharedDocuments(page, state, rejection = null) {
  const proposalHandler = buildHandler(state);
  await mockApi(page, async args => {
    const { apiPath, method, route } = args;
    if (apiPath === `proposals/${PROPOSAL_ID}/approval/` && method === 'GET') return json(200, preview(state));
    if (apiPath === `proposals/${PROPOSAL_ID}/approval/revisions/` && method === 'POST') {
      const request = route.request();
      const contentType = request.headers()['content-type'];
      const payload = contentType.startsWith('multipart/form-data')
        ? JSON.parse(request.postData().split('name="payload"\r\n\r\n')[1].split('\r\n--')[0])
        : request.postDataJSON();
      state.submissions.push(payload);
      if (rejection) return json(rejection.status, rejection.body);
      state.packageNumber = 3;
      state.pending = false;
      return json(200, { ...preview(state), action: 'confirm' });
    }
    if (apiPath === 'documents/91/detail/') return json(200, { id: 91, title: 'Contrato Atlas', folder: null, language: 'es', proposal_source: { proposal_id: PROPOSAL_ID, document_id: 91, source_editor_url: `/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`, source_hash: 'approval-version-2', can_replace_binary: false } });
    if (['document-states/', 'document-state-groups/', 'document-folders/'].includes(apiPath)) return json(200, []);
    if (apiPath === 'documents/91/communications/' || apiPath === 'documents/91/email-usage/') return json(200, { count: 0, results: [] });
    if (apiPath === 'projects/') return json(200, { results: [state.project] });
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/') return json(200, []);
    return proposalHandler(args);
  });
}

async function openReview(page) {
  await openDocuments(page);
  await page.getByTestId('proposal-revision-open').click();
  await expect(page.getByTestId('approval-confirm')).toBeEnabled();
}

test.beforeEach(async ({ page }) => {
  await setAuthLocalStorage(page, { token: 'shared-documents-token', userAuth: { id: 8110, role: 'admin', is_staff: true } });
});

test('confirming a revision refreshes the current package', {
  tag: ['@flow:admin-proposal-shared-documents', '@module:admin', '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  const state = fixture();
  await mockSharedDocuments(page, state);
  await openReview(page);
  await page.getByTestId('approval-confirm').click();

  await expect(page.getByTestId('proposal-approval-modal')).toHaveCount(0);
  await expect(page.getByTestId('proposal-shared-documents')).toContainText('Paquete vigente 3 · Al día');
  expect(state.submissions).toEqual([expect.objectContaining({ action: 'confirm', accept_proposal: false, project_id: 41, client_profile_id: 7, source_hash: 'approval-version-2' })]);
});

test('a stale revision keeps the selected custom contract', {
  tag: ['@flow:admin-proposal-shared-documents', '@module:admin', '@role:admin', '@outcome:error'],
}, async ({ page }) => {
  const state = fixture();
  await mockSharedDocuments(page, state, { status: 409, body: { detail: 'La fuente cambió. Revisa la versión vigente.', code: 'approval_source_changed' } });
  await openReview(page);
  const modal = page.getByTestId('proposal-approval-modal');
  await modal.getByTestId('approval-contract-switch').click();
  await modal.getByTestId('approval-custom-files').setInputFiles({ name: 'contrato-firmado.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\nAtlas\n%%EOF') });
  await page.getByTestId('approval-confirm').click();

  await expect(modal.getByTestId('approval-review-error')).toContainText('La fuente cambió. Revisa la versión vigente.');
  await expect(modal.getByTestId('approval-custom-document')).toContainText('contrato-firmado.pdf');
  await expect(modal.getByTestId('approval-contract-switch')).toHaveAttribute('aria-checked', 'false');
  await expect(page.getByTestId('proposal-shared-documents')).toContainText('Paquete vigente 2 · Borrador pendiente');
});

test('a failed confirmation preserves the current package', {
  tag: ['@flow:admin-proposal-shared-documents', '@module:admin', '@role:admin', '@outcome:failure'],
}, async ({ page }) => {
  const state = fixture();
  await mockSharedDocuments(page, state, { status: 503, body: { detail: 'No fue posible confirmar el paquete.' } });
  await openReview(page);
  await page.getByTestId('approval-confirm').click();

  await expect(page.getByTestId('approval-review-error')).toContainText('No fue posible confirmar el paquete.');
  await expect(page.getByTestId('proposal-shared-documents')).toContainText('Paquete vigente 2 · Borrador pendiente');
  await expect(page.getByTestId('approval-confirm')).toBeEnabled();
  expect(state.submissions).toHaveLength(1);
});

test('proposal navigation exposes approved revision history', {
  tag: ['@flow:admin-proposal-shared-documents', '@module:admin', '@role:admin', '@outcome:display'],
}, async ({ page }) => {
  // quality: allow-deep-link (panel es el inicio autenticado; llega por Propuestas → propuesta → Documentos).
  const state = fixture();
  await mockSharedDocuments(page, state);
  await openDocumentsFromPanel(page);
  const shared = page.getByTestId('proposal-shared-documents');
  await shared.getByText('Revisiones', { exact: true }).click();

  await expect(shared).toContainText('Paquete vigente 2 · Borrador pendiente');
  await expect(shared.getByRole('link', { name: 'Contrato Atlas', exact: true })).toHaveAttribute('href', '/es-co/panel/documents/91/edit');
  await expect(shared.getByRole('link', { name: 'Contrato Atlas · v1', exact: true })).toHaveText('Contrato Atlas · v1');
  await expect(shared.getByRole('link', { name: 'Contrato Atlas · v2', exact: true })).toHaveText('Contrato Atlas · v2');
  expect(state.submissions).toEqual([]);
});


test('the manager opens the same structured source from the proposal', {
  tag: ['@flow:admin-proposal-shared-documents', '@module:admin', '@role:admin', '@outcome:success'],
}, async ({ page }) => {
  // Falla si el gestor ofrece editar una copia Markdown en lugar de la fuente contractual de la propuesta.
  const state = fixture();
  await mockSharedDocuments(page, state);
  await openDocuments(page);
  await page.getByTestId('proposal-shared-documents').getByRole('link', { name: 'Contrato Atlas', exact: true }).click();

  await expect(page).toHaveURL(/\/es-co\/panel\/documents\/91\/edit$/);
  await expect(page.getByTestId('document-shared-source')).toContainText('Este recurso se comparte con la propuesta.');
  await expect(page.getByTestId('doc-markdown-editor-panel')).toHaveCount(0);
  await page.getByTestId('document-edit-source').click();
  await expect(page).toHaveURL(new RegExp(`/es-co/panel/proposals/${PROPOSAL_ID}/edit\\?tab=documents`));
  await expect(page.getByTestId('proposal-shared-documents')).toContainText('Paquete vigente 2 · Borrador pendiente');
  expect(state.submissions).toEqual([]);
});

for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
  test.describe(`shared documents at ${profile}`, () => {
    test.use(viewportUse(profile));

    test('revision history keeps the confirmation reachable', {
      tag: ['@flow:admin-proposal-shared-documents', '@module:admin', '@role:admin', '@outcome:success', `@viewport:${profile}`],
    }, async ({ page }) => {
      // quality: allow-duplicate (per-viewport contract: shared revision history and approval modal at five canonical widths)
      // Falla si el historial desborda o la confirmación queda fuera de la pantalla en un ancho soportado.
      const state = fixture();
      await mockSharedDocuments(page, state);
      await openDocuments(page);
      const shared = page.getByTestId('proposal-shared-documents');
      await shared.getByText('Revisiones', { exact: true }).click();
      await expect(shared.getByRole('link', { name: 'Contrato Atlas · v1', exact: true })).toHaveText('Contrato Atlas · v1');
      await expect.poll(() => page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
      await shared.getByTestId('proposal-revision-open').click();
      const confirmation = page.getByTestId('approval-confirm');
      await expect(confirmation).toHaveText('Confirmar nueva versión');
      await expect(confirmation).toBeEnabled();
      await expectCompactModal(page.getByRole('dialog'), page.viewportSize());
      const buttonBox = await confirmation.boundingBox();
      expect(buttonBox.y + buttonBox.height).toBeLessThanOrEqual(page.viewportSize().height + 1);
      await page.getByRole('dialog').getByRole('button', { name: 'Cancelar', exact: true }).click();
      await expect(page.getByTestId('proposal-approval-modal')).toHaveCount(0);
      expect(state.submissions).toEqual([]);
    });
  });
}
