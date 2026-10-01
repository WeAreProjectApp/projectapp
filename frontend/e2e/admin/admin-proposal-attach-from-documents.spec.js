/**
 * E2E tests for admin Proposal — Adjuntar desde Documentos flow.
 *
 * @flow:admin-proposal-attach-from-documents
 * Covers: button visible in Correos tab, modal lists available documents,
 * selection adds ref badges to composer, POST body includes doc_refs.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { selectProposalDestination } from '../helpers/proposal-navigation.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_ATTACH_FROM_DOCUMENTS } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 9;

const authOk = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const generatedContractDoc = {
  id: 10,
  document_type: 'contract',
  document_type_display: 'Contrato',
  title: 'Contrato de desarrollo',
  is_generated: true,
  file: '/media/contracts/contract.pdf',
};

const uploadedDoc = {
  id: 11,
  document_type: 'amendment',
  document_type_display: 'Otrosí',
  title: 'Otrosí No. 1',
  is_generated: false,
  file: '/media/docs/otrosi.pdf',
};

const emailDefaults = {
  recipient_email: 'client@test.com',
  subject: 'Propuesta — Test Client',
  greeting: 'Hola Test Client',
  sections: [''],
  footer: '',
};

const emptyHistory = { results: [], total: 0, page: 1, has_next: false };

function makeProposal(overrides = {}) {
  return {
    id: PROPOSAL_ID,
    uuid: 'attach-docs-test-uuid',
    slug: 'test-client',
    title: 'Attach Docs Test',
    client_name: 'Test Client',
    client_email: 'client@test.com',
    status: 'sent',
    language: 'es',
    total_investment: '5000000',
    currency: 'COP',
    view_count: 0,
    sent_at: '2026-04-01T10:00:00Z',
    expires_at: new Date(Date.now() + 30 * 86400000).toISOString(),
    is_active: true,
    sections: [],
    requirement_groups: [],
    change_logs: [],
    proposal_documents: [],
    public_url: '/proposal/test-client',
    ...overrides,
  };
}

function baseHandler(proposal) {
  return async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authOk;
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
    }
    // activeMode defaults to 'proposal', so basePath = 'proposal-email'
    if (apiPath === `proposals/${PROPOSAL_ID}/proposal-email/defaults/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emailDefaults) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/proposal-email/history/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emptyHistory) };
    }
    // Also cover branded-email in case mode switches
    if (apiPath === `proposals/${PROPOSAL_ID}/branded-email/defaults/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emailDefaults) };
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/branded-email/history/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(emptyHistory) };
    }
    return null;
  };
}

test.describe('Admin Proposal — Adjuntar desde Documentos', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 1010, role: 'admin', is_staff: true },
    });
  });

  test('"Adjuntar desde Documentos" button is visible in the Correos tab', {
    tag: [...ADMIN_PROPOSAL_ATTACH_FROM_DOCUMENTS, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal()));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'communication', 'emails');

    await expect(page.getByRole('button', { name: /Adjuntar desde Documentos/i }))
      .toBeVisible({ timeout: 15000 });
  });

  test('clicking the button opens the AttachFromDocumentsModal', {
    tag: [...ADMIN_PROPOSAL_ATTACH_FROM_DOCUMENTS, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal()));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'communication', 'emails');
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();

    await expect(page.getByText('Adjuntar desde Documentos').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: /Adjuntar \(/i })).toBeVisible();
  });

  test('modal shows commercial and technical PDF items', {
    tag: [...ADMIN_PROPOSAL_ATTACH_FROM_DOCUMENTS, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal()));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'communication', 'emails');
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();

    await expect(page.getByText('Propuesta comercial (PDF)')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Detalle técnico (PDF)')).toBeVisible();
  });

  test('modal shows contract items when a generated contract exists', {
    tag: [...ADMIN_PROPOSAL_ATTACH_FROM_DOCUMENTS, '@role:admin'],
  }, async ({ page }) => {
    const proposal = makeProposal({ proposal_documents: [generatedContractDoc] });
    await mockApi(page, baseHandler(proposal));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'communication', 'emails');
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();

    await expect(page.getByText('Contrato de desarrollo (PDF)')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Contrato de desarrollo (borrador)')).toBeVisible();
  });

  test('selecting a document and confirming adds a ref badge to the composer', {
    tag: [...ADMIN_PROPOSAL_ATTACH_FROM_DOCUMENTS, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal()));
    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);

    await selectProposalDestination(page, 'communication', 'emails');
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();

    await page.getByLabel('Propuesta comercial (PDF)').check();

    const confirmBtn = page.getByRole('button', { name: /Adjuntar \(1\)/i });
    await expect(confirmBtn).toBeEnabled();
    await confirmBtn.click();

    // The dialog should close (the button with the same label stays visible).
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 3000 });
    // A "Documento" badge label appears inside the doc_ref attachment chip
    await expect(page.locator('span', { hasText: 'Documento' }).first()).toBeVisible();
  });

  test('POST to send/ includes doc_refs when a ref is selected', {
    tag: [...ADMIN_PROPOSAL_ATTACH_FROM_DOCUMENTS, '@role:admin'],
  }, async ({ page }) => {
    let capturedDocRefs = null;

    await mockApi(page, async ({ apiPath, method, route }) => {
      const base = await baseHandler(makeProposal())({ apiPath, method });
      if (base) return base;
      // activeMode = 'proposal' → basePath = 'proposal-email'
      if (apiPath === `proposals/${PROPOSAL_ID}/proposal-email/send/` && method === 'POST') {
        const body = await route.request().postData();
        capturedDocRefs = body && body.includes('doc_refs') ? body : null;
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'sent' }) };
      }
      return null;
    });

    await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`);
    await selectProposalDestination(page, 'communication', 'emails');

    // Fill required fields — subject is not auto-filled from defaults in proposal mode
    await page.getByPlaceholder('Asunto del correo').fill('Asunto de prueba');
    await page.locator('textarea[placeholder="Escribe el contenido de esta sección..."]').fill('Contenido del correo de prueba.');

    // Attach a document
    await page.getByRole('button', { name: /Adjuntar desde Documentos/i }).click();
    await page.getByLabel('Propuesta comercial (PDF)').check();
    await page.getByRole('button', { name: /Adjuntar \(1\)/i }).click();

    await page.getByRole('button', { name: /Enviar correo/i }).click();

    await expect(() => expect(capturedDocRefs).toBeTruthy()).toPass({ timeout: 5000 });
  });
});
