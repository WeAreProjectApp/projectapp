/**
 * E2E tests for the document preview eye-icon on the Documentos tab.
 *
 * @flow:admin-proposal-document-preview
 *
 * Covers: clicking the eye icon next to a previewable document opens
 * the preview modal with the document title and an iframe/img viewer.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_DOCUMENT_PREVIEW } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 9;

const authOk = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const PDF_FILE_URL = 'https://e2e.example/uploads/anexo-tecnico.pdf';

function makeProposal() {
  return {
    id: PROPOSAL_ID,
    uuid: 'eeee9999-1111-2222-3333-444455556666',
    slug: 'doc-preview-test',
    title: 'Doc Preview Test',
    client_name: 'Preview Client',
    status: 'sent',
    language: 'es',
    total_investment: '5000000',
    currency: 'COP',
    sections: [
      { id: 21, section_type: 'greeting', title: 'Bienvenido', order: 0, is_enabled: true, content_json: {} },
    ],
    requirement_groups: [],
    change_logs: [],
    proposal_documents: [
      {
        id: 101,
        title: 'Anexo Técnico',
        file: PDF_FILE_URL,
        document_type: 'legal_annex',
        document_type_display: 'Anexo legal',
        is_generated: false,
        uploaded_at: '2026-04-30T12:00:00Z',
      },
    ],
  };
}

test.describe('Admin Proposal — Document Preview (eye icon)', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 9100, role: 'admin', is_staff: true },
    });
    // Mock the actual file fetch so loadPreviewBlob() doesn't fail.
    await page.route(PDF_FILE_URL, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/pdf',
        body: Buffer.from('%PDF-1.4\n%mock\n'),
      });
    });
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authOk;
      if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
        return { status: 200, contentType: 'application/json', body: JSON.stringify(makeProposal()) };
      }
      return null;
    });
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('proposal-attachment-101')).toBeVisible({ timeout: 15000 });
  });

  test('eye icon is visible next to a previewable PDF document', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_DOCUMENT_PREVIEW, '@role:admin'],
  }, async ({ page }) => {
    const attachment = page.getByTestId('proposal-attachment-101');
    await expect(attachment.getByRole('button', { name: 'Vista previa de Anexo Técnico', exact: true })).toBeVisible();
  });

  test('clicking the eye icon opens the preview modal with the document title', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_DOCUMENT_PREVIEW, '@role:admin'],
  }, async ({ page }) => {
    const attachment = page.getByTestId('proposal-attachment-101');
    await attachment.getByRole('button', { name: 'Vista previa de Anexo Técnico', exact: true }).click();

    const preview = page.getByTestId('markdown-preview-modal-panel');
    await expect(preview.getByRole('heading', { name: 'Anexo Técnico', exact: true })).toBeVisible();
    await expect(preview.locator('iframe[title="Vista previa"]')).toBeVisible();
  });

  test('attachment title keeps its preview inside the current screen', {
    tag: ['@outcome:success', ...ADMIN_PROPOSAL_DOCUMENT_PREVIEW, '@role:admin'],
  }, async ({ page, context }) => {
    const previousUrl = page.url();
    const pagesBefore = context.pages().length;
    await page.getByTestId('proposal-attachment-101').getByRole('button', { name: 'Anexo Técnico', exact: true }).click();

    const preview = page.getByTestId('markdown-preview-modal-panel');
    await expect(preview.getByRole('heading', { name: 'Anexo Técnico', exact: true })).toBeVisible();
    await expect(preview.locator('iframe[title="Vista previa"]')).toBeVisible();
    await preview.getByRole('button', { name: 'Cerrar vista previa', exact: true }).click();
    await expect(preview).toBeHidden();
    await expect(page).toHaveURL(previousUrl);
    expect(context.pages()).toHaveLength(pagesBefore);
  });
});
