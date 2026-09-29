/**
 * E2E tests for admin Proposal — "Documentos" tab.
 *
 * Covers: tab visibility based on proposal status, unified documents list
 * (contract + commercial PDF + technical PDF), "Documentos adjuntos" section,
 * and absence of "Enviar al cliente" section (removed in Apr 22 reorganization).
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_PROPOSAL_DIAGNOSTIC_TEMPLATES,
} from '../helpers/flow-tags.js';

const PROPOSAL_ID = 42;
const futureDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

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
  file: '/media/contracts/contract.pdf',
  is_generated: true,
};

const uploadedDoc = {
  id: 21,
  document_type: 'amendment',
  document_type_display: 'Otrosí',
  title: 'Otrosí No. 1',
  file: '/media/docs/otrosi-1.pdf',
  is_generated: false,
};

function makeProposal(overrides = {}) {
  return {
    id: PROPOSAL_ID,
    uuid: 'doc-tab-test-uuid',
    title: 'Documents Tab Test Proposal',
    client_name: 'Templates Client',
    client_email: 'client@templates.com',
    status: 'sent',
    language: 'es',
    total_investment: '5000000',
    currency: 'COP',
    view_count: 1,
    sent_at: '2026-04-01T10:00:00Z',
    expires_at: futureDate,
    is_active: true,
    sections: [],
    requirement_groups: [],
    change_logs: [],
    proposal_documents: [],
    ...overrides,
  };
}

function baseHandler(proposal) {
  return async ({ apiPath }) => {
    if (apiPath === 'auth/check/') return authOk;
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(proposal) };
    }
    return null;
  };
}

test.describe('Admin Proposal — Documentos tab', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 9200, role: 'admin', is_staff: true },
    });
  });

  test('Documentos tab is hidden for draft proposals', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_DIAGNOSTIC_TEMPLATES, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal({ status: 'draft' })));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);

    await expect(page.getByRole('tab', { name: 'General' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('tab', { name: 'Documentos' })).not.toBeVisible();
  });

  test('Documentos tab is visible for sent proposals', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_DIAGNOSTIC_TEMPLATES, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal({ status: 'sent' })));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);

    await expect(page.getByRole('tab', { name: 'Documentos' })).toBeVisible({ timeout: 15000 });
  });

  test('documents tab renders unified list with contract, commercial and technical entries', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_DIAGNOSTIC_TEMPLATES, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal({ status: 'negotiating' })));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);

    await page.getByRole('tab', { name: 'Documentos' }).click();

    const docsList = page.getByRole('list').first();
    await expect(docsList.getByText('Contrato de desarrollo', { exact: true })).toBeVisible({ timeout: 10000 });
    await expect(docsList.getByText('Propuesta comercial formal', { exact: true })).toBeVisible();
    await expect(docsList.getByText('Detalle técnico formal', { exact: true })).toBeVisible();
  });

  test('documents tab shows generate contract button when no contract doc exists', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_DIAGNOSTIC_TEMPLATES, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal({ status: 'negotiating', proposal_documents: [] })));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);

    await page.getByRole('tab', { name: 'Documentos' }).click();

    await expect(page.getByText('Generar contrato')).toBeVisible({ timeout: 10000 });
  });

  test('documents tab shows Documentos adjuntos section with upload form', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_DIAGNOSTIC_TEMPLATES, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal({ status: 'negotiating' })));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);

    await page.getByRole('tab', { name: 'Documentos' }).click();

    await expect(page.getByRole('heading', { name: 'Documentos adjuntos' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByPlaceholder(/Ej: Anexo técnico/i)).toBeVisible();
  });

  test('documents tab does not show Enviar al cliente section', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_DIAGNOSTIC_TEMPLATES, '@role:admin'],
  }, async ({ page }) => {
    await mockApi(page, baseHandler(makeProposal({ status: 'negotiating' })));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);

    await page.getByRole('tab', { name: 'Documentos' }).click();
    await expect(page.getByText('Contrato de desarrollo')).toBeVisible({ timeout: 10000 });

    await expect(page.getByText('Enviar documentos al cliente')).not.toBeVisible();
  });

  test('uploaded non-contract documents appear in the adjuntos list', {
    tag: ['@outcome:display', ...ADMIN_PROPOSAL_DIAGNOSTIC_TEMPLATES, '@role:admin'],
  }, async ({ page }) => {
    const proposal = makeProposal({
      status: 'negotiating',
      proposal_documents: [generatedContractDoc, uploadedDoc],
    });
    await mockApi(page, baseHandler(proposal));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit`);

    await page.getByRole('tab', { name: 'Documentos' }).click();

    await expect(page.getByText('Otrosí No. 1')).toBeVisible({ timeout: 10000 });
  });
});
