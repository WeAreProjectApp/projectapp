import { expect } from './test.js';
import { waitForNuxtApp } from './navigation.js';

export const PROPOSAL_ID = 911;
export const CONTRACT_PARAMS = {
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

export function contractDoc(id, documentType, title) {
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

export const COMBINED = contractDoc(501, 'contract', 'Contrato de desarrollo de software');
export const PRODUCT = contractDoc(502, 'contract_product', 'Contrato de producto');
export const SERVICE = contractDoc(503, 'contract_service', 'Contrato de servicio');
export const SERVICE_SETTINGS = {
  duration_options: [3, 6, 9, 12],
  notice_options: [30, 60, 90],
  default_duration: 9,
  default_renewal_notice: 60,
  default_termination_notice: 60,
};

export function buildProposal(overrides = {}) {
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

export function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) };
}

export function buildHandler(state, {
  modalityStatus = 200,
  onModality = () => {},
  onUpdate = () => {},
  companySettings = SERVICE_SETTINGS,
  companySettingsStatuses = [],
  updateResponses = [],
  beforeUpdate = async () => {},
} = {}) {
  let companySettingsRequests = 0;
  let updateRequests = 0;
  return async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return json(200, { user: { username: 'admin', is_staff: true } });
    if (apiPath === 'proposals/dashboard/') return json(200, { total: 1, conversion_rate: 100 });
    if (apiPath === 'proposals/alerts/') return json(200, []);
    if (apiPath === 'proposals/' && method === 'GET') return json(200, [state.proposal]);
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/`) return json(200, state.proposal);
    if (apiPath === 'proposals/company-settings/' && method === 'GET') {
      const status = companySettingsStatuses[companySettingsRequests] ?? 200;
      companySettingsRequests += 1;
      return status === 200
        ? json(200, { service_contract_settings: companySettings })
        : json(status, { detail: 'Configuración no disponible.' });
    }
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
      await beforeUpdate();
      const response = updateResponses[updateRequests++];
      if (response) return response;
      state.proposal = {
        ...state.proposal,
        contract_params: { ...state.proposal.contract_params, ...payload.contract_params },
        proposal_documents: [COMBINED, PRODUCT, SERVICE],
      };
      return json(200, state.proposal);
    }
    return null;
  };
}

export async function openDocuments(page) {
  await page.goto(`/es-co/panel/proposals/${PROPOSAL_ID}/edit?tab=documents`, { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await expect(page.getByTestId('proposal-contract-modality')).toBeVisible({ timeout: 20_000 });
}

// Display outcomes arrive the way an admin does: panel → Propuestas → proposal → Documentos.
export async function openDocumentsFromPanel(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Propuestas', exact: true }).click({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/es-co\/panel\/proposals$/);
  await page.getByTestId(`proposal-open-${PROPOSAL_ID}`).click({ timeout: 15_000 });
  await expect(page).toHaveURL(new RegExp(`/es-co/panel/proposals/${PROPOSAL_ID}/edit`));
  await page.getByRole('tab', { name: 'Documentos' }).click();
}
