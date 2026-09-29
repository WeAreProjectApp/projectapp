/**
 * E2E tests for admin proposal documents management flow.
 *
 * @flow:admin-proposal-documents-manage
 * Covers: upload form renders, document list with type badges,
 *         upload calls API, delete button on non-generated docs,
 *         custom type label for "Otro" type.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_DOCUMENTS_MANAGE } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 1;
const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

const additionalDoc = {
  id: 20,
  document_type: 'amendment',
  document_type_display: 'Otrosí',
  title: 'Otrosí No. 1',
  file: '/media/docs/otrosi-1.pdf',
  is_generated: false,
  created_at: '2026-04-01T12:00:00Z',
};

const generatedContractDoc = {
  id: 10,
  document_type: 'contract',
  document_type_display: 'Contrato',
  title: 'Contrato de desarrollo',
  file: '/media/contracts/contract.pdf',
  is_generated: true,
  created_at: '2026-04-01T10:00:00Z',
};

const mockProposal = {
  id: PROPOSAL_ID,
  uuid: '11111111-1111-1111-1111-111111111111',
  title: 'Documents Manage Test',
  client_name: 'Acme Corp',
  client_email: 'acme@example.com',
  language: 'es',
  status: 'negotiating',
  total_investment: '10000000',
  currency: 'COP',
  view_count: 3,
  sent_at: '2026-03-28T10:00:00Z',
  sections: [
    { id: 1, section_type: 'greeting', title: 'Saludo', order: 0, is_enabled: true, content_json: { clientName: 'Acme Corp' } },
  ],
  requirement_groups: [],
  proposal_documents: [generatedContractDoc, additionalDoc],
  contract_params: { contract_source: 'default' },
};

test.describe('Admin Proposal Documents Manage', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  test('additional documents section renders with existing docs', {
    tag: [...ADMIN_PROPOSAL_DOCUMENTS_MANAGE, '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — asserts the additional-docs list renders type badge and title from proposal_documents; upload/delete actions are exercised by the tests below)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    // Additional docs section header
    await expect(page.getByText('Documentos adjuntos').first()).toBeVisible();
    // Document type badge
    await expect(page.getByText('Otrosí').first()).toBeVisible();
    // Document title
    await expect(page.getByRole('button', { name: 'Otrosí No. 1', exact: true })).toBeVisible();
  });

  test('uploads a document and it appears in the attached list', {
    tag: [...ADMIN_PROPOSAL_DOCUMENTS_MANAGE, '@role:admin'],
  }, async ({ page }) => {
    let documents = [generatedContractDoc, additionalDoc];
    const uploadedDoc = { id: 30, document_type: 'amendment', document_type_display: 'Otrosí',
      title: 'Otrosí No. 2', file: '/media/docs/otrosi-2.pdf', is_generated: false, created_at: '2026-04-05T09:00:00Z' };

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...mockProposal, proposal_documents: documents }) };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/documents/upload/` && method === 'POST') {
        documents = [...documents, uploadedDoc];
        return { status: 201, contentType: 'application/json', body: JSON.stringify(uploadedDoc) };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    const additionalSection = page.locator('section').filter({ hasText: 'Documentos adjuntos' });
    await additionalSection.getByPlaceholder(/Ej: Anexo técnico/i).fill('Otrosí No. 2');
    await additionalSection.getByRole('combobox').selectOption('amendment');
    await additionalSection.locator('input[type="file"]').setInputFiles({
      name: 'otrosi-2.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 fake'),
    });

    const uploadResponse = page.waitForResponse((r) =>
      r.url().includes(`proposals/${PROPOSAL_ID}/documents/upload/`) && r.status() === 201);
    await additionalSection.getByRole('button', { name: /Subir$/i }).click();
    await uploadResponse;

    await expect(page.getByRole('alert')).toContainText('Documento subido.');
    await expect(additionalSection.getByRole('button', { name: 'Otrosí No. 2', exact: true })).toBeVisible();
  });

  test('delete button visible on non-generated documents only', {
    tag: [...ADMIN_PROPOSAL_DOCUMENTS_MANAGE, '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (permission display — asserts exactly one delete button renders, for the non-generated doc only; generated contract docs must not offer delete. The click-through delete is exercised by the test below)
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(mockProposal) };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    // The additional docs section should have at least one delete button (for the non-generated doc)
    const additionalSection = page.locator('section').filter({ hasText: 'Documentos adjuntos' });
    const deleteButtons = additionalSection.getByRole('button', { name: 'Eliminar documento' });
    await expect(deleteButtons).toHaveCount(1);
  });

  test('deleting an additional document removes it from the attached list', {
    tag: [...ADMIN_PROPOSAL_DOCUMENTS_MANAGE, '@role:admin'],
  }, async ({ page }) => {
    let documents = [generatedContractDoc, additionalDoc];

    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ ...mockProposal, proposal_documents: documents }),
        };
      }
      if (apiPath === `proposals/${PROPOSAL_ID}/documents/${additionalDoc.id}/delete/` && method === 'DELETE') {
        documents = documents.filter((doc) => doc.id !== additionalDoc.id);
        return { status: 204, contentType: 'application/json', body: '' };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    const additionalSection = page.locator('section').filter({ hasText: 'Documentos adjuntos' });
    await expect(additionalSection.getByRole('button', { name: 'Otrosí No. 1', exact: true })).toBeVisible();

    const deleteButton = additionalSection.getByRole('button', { name: 'Eliminar documento' });
    await Promise.all([
      page.waitForResponse((r) =>
        r.url().includes(`proposals/${PROPOSAL_ID}/documents/${additionalDoc.id}/delete/`) && r.status() === 204
      ),
      deleteButton.click(),
    ]);

    await expect(page.getByRole('alert')).toContainText('Documento eliminado.');
    await expect(additionalSection.getByRole('button', { name: 'Otrosí No. 1', exact: true })).toHaveCount(0);
  });

  test('shows empty state when no additional documents', {
    tag: [...ADMIN_PROPOSAL_DOCUMENTS_MANAGE, '@role:admin'],
  }, async ({ page }) => {
    // quality: allow-no-interaction (display — asserts the empty-state copy renders when proposal_documents has no non-contract entries)
    const proposalNoAdditional = {
      ...mockProposal,
      proposal_documents: [generatedContractDoc],
    };
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(proposalNoAdditional) };
      }
      return null;
    });

    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByText('No hay documentos adjuntos.')).toBeVisible();
  });
});
