/**
 * Admin chooses how a negotiated deal closes: one contract, or a product
 * contract plus a hosting, maintenance and support contract.
 *
 * @flow:admin-proposal-contract-modality
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_PROPOSAL_CONTRACT_MODALITY } from '../helpers/flow-tags.js';

const PROPOSAL_ID = 911;
const CONTRACT_PARAMS = {
  contract_source: 'default',
  contractor_full_name: 'Project App S.A.S.',
  contractor_nit: '900.123.456-7',
  contractor_email: 'contratos@example.com',
  bank_name: 'Banco de Pruebas',
  bank_account_type: 'Ahorros',
  bank_account_number: '000-000000-00',
  contract_city: 'Medellín',
  client_full_name: 'Cliente Modalidad',
  client_cedula: '1.020.304.050',
  client_email: 'cliente@example.com',
  contract_date: '2026-09-26',
};

function contractDoc(id, documentType, title) {
  return {
    id,
    document_type: documentType,
    document_type_display: title,
    title,
    file: `/media/proposal_documents/${documentType}.pdf`,
    is_generated: true,
    created_at: '2026-09-26T10:00:00Z',
    updated_at: '2026-09-26T10:00:00Z',
  };
}

const COMBINED = contractDoc(501, 'contract', 'Contrato de desarrollo de software');
const PRODUCT = contractDoc(502, 'contract_product', 'Contrato de producto');
const SERVICE = contractDoc(503, 'contract_service', 'Contrato de servicio');

function buildProposal(overrides = {}) {
  return {
    id: PROPOSAL_ID,
    uuid: 'ed911111-1111-1111-1111-111111111111',
    title: 'Modalidad de cierre E2E',
    client_name: 'Cliente Modalidad',
    client_email: 'cliente@example.com',
    language: 'es',
    status: 'negotiating',
    total_investment: '12000000',
    currency: 'COP',
    contract_modality: 'single',
    contract_params: CONTRACT_PARAMS,
    proposal_documents: [COMBINED],
    sections: [],
    requirement_groups: [],
    ...overrides,
  };
}

function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

function buildHandler(state, { modalityStatus = 200, onModality = () => {}, onUpdate = () => {} } = {}) {
  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return json(200, { user: { username: 'admin', is_staff: true } });
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return json(200, state.proposal);
    if (apiPath === 'proposals/company-settings/') return json(200, {});
    if (apiPath === `proposals/${PROPOSAL_ID}/contract/modality/` && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      onModality(payload);
      if (modalityStatus !== 200) {
        return json(modalityStatus, {
          error: 'El contrato por defecto no se puede separar en producto y servicio. Revisa el texto de la plantilla del contrato.',
          code: 'split_unavailable',
        });
      }
      state.proposal = {
        ...state.proposal,
        contract_modality: payload.contract_modality,
        proposal_documents: payload.contract_modality === 'split' ? [COMBINED, PRODUCT] : [COMBINED],
      };
      return json(200, state.proposal);
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/contract/update/` && method === 'PATCH') {
      const payload = route.request().postDataJSON();
      onUpdate(payload);
      state.proposal = {
        ...state.proposal,
        contract_params: { ...state.proposal.contract_params, ...payload.contract_params },
        proposal_documents: [...state.proposal.proposal_documents, SERVICE],
      };
      return json(200, state.proposal);
    }
    return null;
  };
}

async function openDocuments(page) {
  await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('proposal-contract-modality')).toBeVisible({ timeout: 20_000 });
}

test.describe('Admin proposal contract modality', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(60_000);
    await setAuthLocalStorage(page, {
      token: 'e2e-admin-token',
      userAuth: { id: 8110, role: 'admin', is_staff: true },
    });
  });

  test('switching to product and service shows both separate contracts', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { proposal: buildProposal() };
    let modalityPayload = null;
    await mockApi(page, buildHandler(state, { onModality: payload => { modalityPayload = payload; } }));
    await openDocuments(page);
    await expect(page.getByTestId('proposal-contract-row-combined')).toBeVisible();

    await page.getByTestId('proposal-contract-modality-split').click();

    await expect(page.getByText('El negocio se cierra con contrato de producto y contrato de servicio.')).toBeVisible({ timeout: 10_000 });
    expect(modalityPayload).toEqual({ contract_modality: 'split' });
    await expect(page.getByTestId('proposal-contract-modality-split')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-row-combined')).toHaveCount(0);
    const product = page.getByTestId('proposal-contract-row-product');
    await expect(product.getByRole('link', { name: 'Descargar PDF' })).toHaveAttribute('href', `/api/proposals/${PROPOSAL_ID}/contract/pdf/?variant=product`);
    await expect(page.getByTestId('proposal-contract-row-service')).toContainText('PDF · No generado');
  });

  test('the service contract is generated with its three terms', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const state = { proposal: buildProposal({ contract_modality: 'split', proposal_documents: [COMBINED, PRODUCT] }) };
    let updatePayload = null;
    await mockApi(page, buildHandler(state, { onUpdate: payload => { updatePayload = payload; } }));
    await openDocuments(page);

    await page.getByTestId('proposal-generate-contract-service').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Generar contrato de servicio' })).toBeVisible();
    await dialog.getByPlaceholder('Ej.: doce (12) meses').fill('doce (12) meses');
    await dialog.getByPlaceholder('Ej.: treinta (30)').first().fill('treinta (30)');
    await dialog.getByPlaceholder('Ej.: treinta (30)').last().fill('quince (15)');
    await dialog.getByRole('button', { name: 'Generar contrato', exact: true }).click();

    await expect(page.getByTestId('proposal-contract-row-service')).toContainText('Generado el', { timeout: 10_000 });
    expect(updatePayload.variant).toBe('service');
    expect(updatePayload.contract_params).toMatchObject({
      service_contract_source: 'default',
      service_initial_term: 'doce (12) meses',
      service_renewal_notice_days: 'treinta (30)',
      service_termination_notice_days: 'quince (15)',
    });
  });

  test('a refused separation keeps the single contract and explains why', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const state = { proposal: buildProposal() };
    await mockApi(page, buildHandler(state, { modalityStatus: 409 }));
    await openDocuments(page);

    await page.getByTestId('proposal-contract-modality-split').click();

    await expect(page.getByText('El contrato por defecto no se puede separar en producto y servicio.', { exact: false })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('proposal-contract-modality-single')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-row-combined')).toBeVisible();
  });

  test('an accepted proposal shows its modality without letting it change', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const state = { proposal: buildProposal({ status: 'accepted', contract_modality: 'split', proposal_documents: [COMBINED, PRODUCT, SERVICE] }) };
    await mockApi(page, buildHandler(state));
    await openDocuments(page);

    await expect(page.getByTestId('proposal-contract-modality-split')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('proposal-contract-modality-single')).toBeDisabled();
    await expect(page.getByTestId('proposal-contract-row-product')).toBeVisible();
    await expect(page.getByTestId('proposal-contract-row-service')).toBeVisible();
  });

  test('the switch stays hidden before the negotiation', {
    tag: [...ADMIN_PROPOSAL_CONTRACT_MODALITY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const state = { proposal: buildProposal({ status: 'sent', proposal_documents: [] }) };
    await mockApi(page, buildHandler(state));
    await page.goto(`/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`, { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('proposal-contract-row-combined')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId('proposal-contract-modality')).toHaveCount(0);
  });
});
