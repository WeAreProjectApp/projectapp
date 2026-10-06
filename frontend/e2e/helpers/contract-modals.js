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
  onPreview = () => {},
  onConfirm = () => {},
  onCancel = () => {},
  onUpdate = () => {},
  companySettings = SERVICE_SETTINGS,
  companySettingsStatuses = [],
  updateResponses = [],
  previewResponses = [],
  contractSnapshots = [],
  contractSnapshotDetails = {},
  beforeUpdate = async () => {},
} = {}) {
  let companySettingsRequests = 0;
  let updateRequests = 0;
  let previewRequests = 0;
  const confirmations = new Map();

  function restorationSnapshot(payload) {
    return contractSnapshotDetails[String(payload.snapshot_id)] || null;
  }

  function snapshotDocuments(snapshot) {
    const documents = snapshot?.payload?.documents || [];
    const docsByVariant = { combined: COMBINED, product: PRODUCT, service: SERVICE };
    return documents.map(({ variant }) => docsByVariant[variant]).filter(Boolean);
  }

  function previewFor(payload, confirmationId) {
    const restoring = payload.snapshot_id != null;
    const snapshot = restoring ? restorationSnapshot(payload) : null;
    const previous = state.proposal.contract_modality;
    const target = restoring ? snapshot?.from_modality : payload.contract_modality;
    const params = restoring
      ? snapshot?.payload?.contract_params || {}
      : { ...state.proposal.contract_params, ...(payload.contract_params || {}) };
    const productSource = params.contract_source === 'custom' ? 'custom' : 'default';
    return {
      confirmation_id: confirmationId,
      expires_at: '2026-10-06T12:10:00Z',
      impact: {
        previous_modality: previous,
        contract_modality: target,
        contracts: restoring
          ? (snapshot?.payload?.documents || []).map((document) => ({
            variant: document.variant,
            action: 'restore',
            source: document.source,
          }))
          : target === 'split'
          ? [
            { variant: 'product', action: productSource === 'custom' ? 'move' : 'create', source: productSource },
            { variant: 'service', action: 'create', source: 'default' },
          ]
          : [{ variant: 'combined', action: productSource === 'custom' ? 'move' : 'create', source: productSource }],
        archive: restoring
          ? (state.proposal.proposal_documents || []).map((document) => ({
            variant: document.document_type === 'contract_product' ? 'product' : document.document_type === 'contract_service' ? 'service' : 'combined',
            document_id: document.id,
          }))
          : target === 'split' ? [{ variant: 'combined', document_id: COMBINED.id }] : [
          { variant: 'product', document_id: PRODUCT.id },
          { variant: 'service', document_id: SERVICE.id },
        ],
        contract_params: params,
        warnings: ['Los documentos enviados, aprobados o firmados se conservan. Este cambio no envía documentos ni solicita nuevas firmas.'],
        linked_documents: [],
      },
    };
  }

  function confirmedProposal(payload) {
    const restoring = payload.snapshot_id != null;
    const snapshot = restoring ? restorationSnapshot(payload) : null;
    const target = restoring ? snapshot?.from_modality : payload.contract_modality;
    const previousParams = state.proposal.contract_params || {};
    const nextParams = restoring
      ? snapshot?.payload?.contract_params || {}
      : {
        ...previousParams,
        ...(payload.contract_params || {}),
        product_contract_source: previousParams.contract_source === 'custom' ? 'custom' : 'default',
        service_contract_source: 'default',
      };
    const proposal = {
      ...state.proposal,
      contract_modality: target,
      contract_params: nextParams,
      proposal_documents: restoring ? snapshotDocuments(snapshot) : target === 'split' ? [PRODUCT, SERVICE] : [COMBINED],
    };
    if (restoring) {
      const snapshotId = Math.max(0, ...contractSnapshots.map(({ snapshot_id: id }) => id)) + 1;
      contractSnapshots.unshift({
        snapshot_id: snapshotId,
        created_at: '2026-10-06T12:05:00Z',
        actor: 'Admin E2E',
        source: 'panel',
        change_note: payload.change_note,
        from_modality: state.proposal.contract_modality,
        to_modality: target,
        restored_from_id: payload.snapshot_id,
      });
    }
    return proposal;
  }

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
    if (apiPath === `proposals/${PROPOSAL_ID}/contract/modality/preview/` && method === 'POST') {
      const payload = route.request().postDataJSON();
      onPreview(payload);
      const response = previewResponses[previewRequests++];
      if (response) return response;
      const confirmationId = `contract-change-${previewRequests}`;
      confirmations.set(confirmationId, payload);
      return json(200, previewFor(payload, confirmationId));
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/contract/modality/confirm/` && method === 'POST') {
      const { confirmation_id: confirmationId } = route.request().postDataJSON();
      onConfirm(confirmationId);
      const payload = confirmations.get(confirmationId);
      if (!payload) return json(409, { error: 'La confirmación venció o fue cancelada.' });
      state.proposal = confirmedProposal(payload);
      return json(200, state.proposal);
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/contract/modality/cancel/` && method === 'POST') {
      const { confirmation_id: confirmationId } = route.request().postDataJSON();
      onCancel(confirmationId);
      confirmations.delete(confirmationId);
      return json(200, { cancelled: true });
    }
    if (apiPath === `proposals/${PROPOSAL_ID}/contract/snapshots/` && method === 'GET') {
      return json(200, { total: contractSnapshots.length, snapshots: contractSnapshots });
    }
    const snapshotMatch = apiPath.match(new RegExp(`^proposals/${PROPOSAL_ID}/contract/snapshots/(\\d+)/$`));
    if (snapshotMatch && method === 'GET') {
      return json(200, contractSnapshotDetails[snapshotMatch[1]] || {});
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
