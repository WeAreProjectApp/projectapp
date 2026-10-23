const STATUS_LABELS = {
  draft: 'Borrador',
  ready: 'Listo para firma',
  active: 'Activo',
  completed: 'Completado',
  cancelled: 'Cancelado',
}

const ACTIONS_BY_STATUS = {
  draft: ['edit', 'download_draft', 'mark_ready', 'cancel'],
  ready: ['download_draft', 'reopen', 'upload_signed', 'cancel'],
  active: ['download_signed', 'complete', 'cancel'],
  completed: ['download_signed', 'create_second_cycle', 'archive'],
  cancelled: ['archive'],
}

export const financingAgreementTemplateFixture = {
  id: 7,
  name: 'Otrosí de financiación',
  version: 2,
  content_markdown: '# OTROSÍ {agreement_number}\n\n{client_full_name}',
  is_default: true,
  is_active: true,
  created_at: '2026-09-01T12:00:00Z',
  updated_at: '2026-09-01T12:00:00Z',
}

export const financingPolicyFixture = {
  id: 2,
  version: 2,
  minimum_project_value_cop: '20000000.00',
  maximum_project_value_cop: '140000000.00',
  financing_months: 12,
  maximum_financed_percent: '80.00',
  minimum_initial_payment_percent: '20.00',
  late_hosting_increase_percent: '2.00',
  installment_due_day_start: 1,
  installment_due_day_end: 5,
  created_by: null,
  created_by_name: 'Sistema',
  created_at: '2026-09-01T12:00:00Z',
}

export function financingSettingsFixture(overrides = {}) {
  const current = { ...financingPolicyFixture, ...overrides }
  return {
    current,
    history: [current],
    usd_exchange_rate: '4000.00',
    fixed_terms: {
      ordinary_interest_percent: 0,
      modalities: [
        { key: 'five_year', years: 5, financing_cycles: 2, monthly_requirement_allowance: true },
        { key: 'three_year', years: 3, financing_cycles: 1, monthly_requirement_allowance: false },
      ],
    },
  }
}

export const financingClientFixture = {
  id: 41,
  name: 'Ana Semilla',
  email: 'ana@semilla.test',
  phone: '+57 300 000 0041',
  company: 'Semilla SAS',
  nit: '901234567-8',
  cedula: '',
  is_email_placeholder: false,
  total_proposals: 1,
}

export function financingScheduleFixture(balance = 20000000) {
  const installment = Math.floor((balance * 100) / 12) / 100
  return Array.from({ length: 12 }, (_, index) => ({
    number: index + 1,
    due_date: `2026-${String(index + 1).padStart(2, '0')}-05`,
    amount: (index === 11
      ? balance - (installment * 11)
      : installment).toFixed(2),
  }))
}

export function financingAgreementFixture(overrides = {}) {
  const status = overrides.status || 'draft'
  const isArchived = overrides.is_archived ?? false
  const cycleNumber = overrides.cycle_number || 1
  const base = {
    id: 501,
    uuid: '3b548ea1-a5a7-45e5-a695-83e189a340b1',
    number: status === 'draft' ? null : 'OFIN-2026-001',
    client: financingClientFixture.id,
    client_name: financingClientFixture.name,
    client_full_name: financingClientFixture.name,
    client_company: financingClientFixture.company,
    client_id_type: 'NIT',
    client_id_number: financingClientFixture.nit,
    client_email: financingClientFixture.email,
    client_phone: financingClientFixture.phone,
    source_proposal: 91,
    source_project: 71,
    original_contract_reference: 'Contrato de desarrollo PA-041',
    original_contract_date: '2026-01-15',
    project_name: 'Plataforma Semilla',
    financed_scope: 'Desarrollo e implementación de la fase comercial.',
    modality: 'five_year',
    modality_label: 'Alianza a 5 años',
    cycle_number: cycleNumber,
    previous_agreement: cycleNumber === 2 ? 501 : null,
    previous_agreement_number: cycleNumber === 2 ? 'OFIN-2026-001' : null,
    second_cycle_id: null,
    partnership_start_date: '2026-01-01',
    partnership_end_date: '2031-01-01',
    currency: 'COP',
    policy_revision: financingPolicyFixture.id,
    policy_version: financingPolicyFixture.version,
    policy: financingPolicyFixture,
    eligibility_exchange_rate: null,
    equivalent_total_cop: '25000000.00',
    total_value: '25000000.00',
    initial_payment: '5000000.00',
    financed_balance: '20000000.00',
    hosting_value: '500000.00',
    hosting_period: 'monthly',
    installment_schedule: financingScheduleFixture(),
    status,
    status_label: STATUS_LABELS[status],
    template_name: financingAgreementTemplateFixture.name,
    template_version: financingAgreementTemplateFixture.version,
    template: financingAgreementTemplateFixture,
    contract_markdown: financingAgreementTemplateFixture.content_markdown,
    resolved_contract_markdown: status === 'draft' ? '' : '# OTROSÍ OFIN-2026-001',
    resolved_contract_sha256: status === 'draft' ? '' : 'a'.repeat(64),
    has_signed_document: ['active', 'completed'].includes(status),
    signed_document_sha256: ['active', 'completed'].includes(status) ? 'b'.repeat(64) : '',
    signed_document_size: ['active', 'completed'].includes(status) ? 1024 : 0,
    allowed_actions: isArchived ? ['restore'] : ACTIONS_BY_STATUS[status],
    is_archived: isArchived,
    archived_at: isArchived ? '2026-09-02T15:00:00Z' : null,
    ready_at: status === 'draft' ? null : '2026-09-02T12:00:00Z',
    ready_by: status === 'draft' ? null : 1,
    ready_by_name: status === 'draft' ? '' : 'Admin Prueba',
    activated_at: ['active', 'completed'].includes(status) ? '2026-09-02T13:00:00Z' : null,
    activated_by: ['active', 'completed'].includes(status) ? 1 : null,
    activated_by_name: ['active', 'completed'].includes(status) ? 'Admin Prueba' : '',
    completed_at: status === 'completed' ? '2026-09-02T14:00:00Z' : null,
    completed_by: status === 'completed' ? 1 : null,
    completed_by_name: status === 'completed' ? 'Admin Prueba' : '',
    completion_note: status === 'completed' ? 'Pago íntegro verificado.' : '',
    cancelled_at: status === 'cancelled' ? '2026-09-02T14:00:00Z' : null,
    cancelled_by: status === 'cancelled' ? 1 : null,
    cancelled_by_name: status === 'cancelled' ? 'Admin Prueba' : '',
    cancellation_reason: status === 'cancelled' ? 'Acuerdo cerrado por las partes.' : '',
    second_cycle_approved_at: cycleNumber === 2 ? '2026-09-02T15:00:00Z' : null,
    second_cycle_approved_by: cycleNumber === 2 ? 1 : null,
    events: [{
      id: 1,
      event_type: status === 'draft' ? 'created' : 'marked_ready',
      actor: 1,
      actor_name: 'Admin Prueba',
      before_state: {},
      after_state: {},
      details: {},
      created_at: '2026-09-02T12:00:00Z',
    }],
    created_at: '2026-09-02T12:00:00Z',
    updated_at: '2026-09-02T12:00:00Z',
  }

  return {
    ...base,
    ...overrides,
    status_label: overrides.status_label ?? STATUS_LABELS[status],
    allowed_actions: overrides.allowed_actions
      ?? (isArchived ? ['restore'] : ACTIONS_BY_STATUS[status]),
  }
}

export function financingClientContextFixture() {
  return {
    client: {
      id: financingClientFixture.id,
      name: financingClientFixture.name,
      company: financingClientFixture.company,
      email: financingClientFixture.email,
      phone: financingClientFixture.phone,
      id_type: 'NIT',
      id_number: financingClientFixture.nit,
    },
    proposals: [{
      id: 91,
      title: 'Propuesta Plataforma Semilla',
      status: 'accepted',
      total_investment: '25000000.00',
      currency: 'COP',
    }],
    projects: [{ id: 71, name: 'Plataforma Semilla', status: 'active' }],
  }
}
