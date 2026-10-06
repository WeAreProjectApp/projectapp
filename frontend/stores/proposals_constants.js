// Offline fallback for the hosting percentage of the total investment.
// The real default is admin-editable (ProposalDefaultConfig.hosting_percent)
// and is fetched on the create page; this constant only covers the moment
// before that fetch resolves (or its failure) and mirrors the backend model
// default (BusinessProposal.hosting_percent).
export const DEFAULT_HOSTING_PERCENT = 60;

// Default hosting payment-frequency tiers, ordered best-discount first. Single
// source of truth shared by the public Investment view and the admin editor so
// the nine-month/semiannual/quarterly discounts never drift between them.
// Monthly pay-as-you-go is intentionally not offered.
export const DEFAULT_BILLING_TIERS = [
  { frequency: 'nine_month', months: 9, discountPercent: 40, label: 'Cada 9 meses', badge: 'Máximo descuento' },
  { frequency: 'semiannual', months: 6, discountPercent: 20, label: 'Semestral', badge: '20% dcto' },
  { frequency: 'quarterly', months: 3, discountPercent: 10, label: 'Trimestral', badge: '10% dcto' },
];

export const PROPOSAL_STATUS = Object.freeze({
  DRAFT: 'draft',
  SENT: 'sent',
  VIEWED: 'viewed',
  NEGOTIATING: 'negotiating',
  ACCEPTED: 'accepted',
  REJECTED: 'rejected',
  EXPIRED: 'expired',
  FINISHED: 'finished',
});

export const CONTRACT_LOCKED_STATUSES = Object.freeze([
  PROPOSAL_STATUS.SENT,
  PROPOSAL_STATUS.VIEWED,
]);

// How a negotiated deal closes: one contract, or a product contract plus a
// separate hosting, maintenance and support contract. Mirrors
// BusinessProposal.ContractModality and backend content/services/contract_variants.py.
export const CONTRACT_MODALITY = Object.freeze({
  SINGLE: 'single',
  SPLIT: 'split',
});

// Every proposal state can change modality; the server confirms outside negotiation.
export const CONTRACT_MODALITY_EDITABLE_STATUSES = Object.freeze(Object.values(PROPOSAL_STATUS));
export const CONTRACT_MODALITY_VISIBLE_STATUSES = CONTRACT_MODALITY_EDITABLE_STATUSES;

export const CONTRACT_VARIANTS = Object.freeze({
  combined: Object.freeze({
    key: 'combined',
    docType: 'contract',
    label: 'Contrato de desarrollo',
    subtitle: '',
    sourceKey: 'contract_source',
    customKey: 'custom_contract_markdown',
  }),
  product: Object.freeze({
    key: 'product',
    docType: 'contract_product',
    label: 'Contrato de producto',
    subtitle: 'Desarrollo e implementación del software',
    sourceKey: 'product_contract_source',
    customKey: 'product_custom_contract_markdown',
  }),
  service: Object.freeze({
    key: 'service',
    docType: 'contract_service',
    label: 'Contrato de servicio',
    subtitle: 'Hosting, mantenimiento y soporte',
    sourceKey: 'service_contract_source',
    customKey: 'service_custom_contract_markdown',
  }),
});

export const CONTRACT_MODALITY_VARIANTS = Object.freeze({
  [CONTRACT_MODALITY.SINGLE]: Object.freeze(['combined']),
  [CONTRACT_MODALITY.SPLIT]: Object.freeze(['product', 'service']),
});

// Generated contract documents are never ordinary attachments.
export const CONTRACT_DOC_TYPES = Object.freeze(
  Object.values(CONTRACT_VARIANTS).map((variant) => variant.docType),
);

// The three terms the standalone service contract fills per proposal.
export const SERVICE_CONTRACT_FIELDS = Object.freeze([
  Object.freeze({ key: 'service_initial_term', label: 'Duración inicial', optionsKey: 'duration_options', defaultKey: 'default_duration', duration: true }),
  Object.freeze({ key: 'service_renewal_notice_days', label: 'Preaviso para no renovar (días calendario)', optionsKey: 'notice_options', defaultKey: 'default_renewal_notice' }),
  Object.freeze({ key: 'service_termination_notice_days', label: 'Preaviso de terminación del cliente (días calendario)', optionsKey: 'notice_options', defaultKey: 'default_termination_notice' }),
]);

export function contractVariantsFor(proposal) {
  return CONTRACT_MODALITY_VARIANTS[proposal?.contract_modality] || CONTRACT_MODALITY_VARIANTS.single;
}

// Statuses where the client's decision is already settled. Time-sensitive /
// urgency notices on the public view (expiration countdown, limited-time
// discount banner, hosting tier discount badges) must be hidden for these.
// `expired` is handled separately via the expired-state logic.
export const RESOLVED_PROPOSAL_STATUSES = Object.freeze([
  PROPOSAL_STATUS.ACCEPTED,
  PROPOSAL_STATUS.REJECTED,
  PROPOSAL_STATUS.FINISHED,
]);

/**
 * Default "method phases" block for the proposal initial email. Shared by
 * the edit page's form hydration and ProposalGeneralTab's ensureMethodPhases.
 */
export const DEFAULT_METHOD_PHASES = Object.freeze([
  { number: '01', title: 'Diagnóstico', duration: '', description: 'Mapeo de procesos y alcance final.' },
  { number: '02', title: 'Construcción', duration: '', description: 'Sprints con demo cada viernes.' },
  { number: '03', title: 'Lanzamiento', duration: '', description: 'Deploy, capacitación y soporte.' },
]);
