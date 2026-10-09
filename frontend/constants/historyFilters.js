/**
 * Filter shape and predefined tabs for /panel/accounting/history.
 *
 * The two subtabs answer different questions — "who did this email reach"
 * and "who changed this record" — so they get one config each, and one
 * saved-tab view each, rather than sharing a filter dict where half the keys
 * would be meaningless.
 *
 * Historial is the one accounting view that paginates server-side, so unlike
 * the other pages the matchers here never run: the narrowing happens in
 * `accounting_history_service`, and `SENDS_PARAM_MAPPING` /
 * `CHANGES_PARAM_MAPPING` translate this state into its query params.
 * `useAccountingFilters` still needs the matcher keys, which is what drives
 * the active-filter count and the chips.
 */

/**
 * Declare a filter the server applies. The predicate is never called (the
 * page does not use `applyFilters`); the `keys` list is the contract.
 */
function serverFilter(...keys) {
  const fn = () => true;
  fn.keys = keys;
  return fn;
}

/** Local YYYY-MM-DD, so "Hoy" means today in the operator's timezone. */
export function isoDay(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

export function daysAgo(days) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return isoDay(date);
}

/**
 * Tabs whose meaning is a date relative to now, or that must hold a fixed
 * position in the strip. They are code-level: never persisted, never
 * renamed or deleted, and — being computed at render time — never stale.
 *
 * The rest of the predefined cuts are seeded rows in
 * `accounts/default_filter_tabs.py`, so "Restablecer" can put them back.
 */
export function sendsBuiltinTabs() {
  return [
    // Second in the strip on purpose, right after "Todas": it is the first
    // place anyone goes when someone says a notice never arrived.
    { id: 'failed', name: 'Fallidos', filters: { status: ['failed'] } },
    { id: 'today', name: 'Hoy', filters: { date_from: isoDay() } },
    { id: 'last7', name: 'Últimos 7 días', filters: { date_from: daysAgo(7) } },
  ];
}

export function changesBuiltinTabs() {
  return [
    { id: 'today', name: 'Hoy', filters: { date_from: isoDay() } },
    { id: 'last7', name: 'Últimos 7 días', filters: { date_from: daysAgo(7) } },
  ];
}

// Mirrors EMAIL_TEMPLATE_LABELS in content/serializers/accounting.py; a
// backend test pins the two together so they cannot drift.
export const TEMPLATE_KEY_OPTIONS = [
  { value: 'accounting_change', label: 'Cambio contable' },
  { value: 'accounting_card_reminder', label: 'Recordatorio de deuda de tarjetas' },
  { value: 'accounting_statement_reminder', label: 'Recordatorio de extractos' },
  { value: 'accounting_payment_calendar', label: 'Calendario de cobros y pagos' },
  { value: 'collection_account_sent', label: 'Cuenta de cobro' },
  { value: 'income_payment_received_client', label: 'Confirmación de pago' },
  { value: 'payment_status_team', label: 'Pago de hosting' },
];

export const SEND_STATUS_OPTIONS = [
  { value: 'sent', label: 'Enviado' },
  { value: 'delivered', label: 'Entregado' },
  { value: 'bounced', label: 'Rebotado' },
  { value: 'failed', label: 'Fallido' },
];

// The record types an email can be about. Mirrors EmailLogTarget's choices,
// trimmed to the ones the panel can actually reach from a row.
export const SEND_ENTITY_OPTIONS = [
  { value: 'income', label: 'Ingreso' },
  { value: 'expense', label: 'Gasto' },
  { value: 'hosting', label: 'Hosting' },
  { value: 'collection_account', label: 'Cuenta de cobro' },
  { value: 'recurring', label: 'Pago recurrente' },
  { value: 'credit_card', label: 'Tarjeta de crédito' },
  { value: 'statement', label: 'Extracto de tarjeta' },
  { value: 'payment', label: 'Pago de plataforma' },
];

export const CHANGE_ENTITY_OPTIONS = [
  { value: 'income', label: 'Ingreso' },
  { value: 'expense', label: 'Gasto' },
  { value: 'hosting', label: 'Hosting' },
  { value: 'pocket', label: 'Bolsillo' },
  { value: 'recurring', label: 'Pago recurrente' },
  { value: 'ads', label: 'Ads' },
  { value: 'card_snapshot', label: 'Saldo tarjeta' },
  { value: 'credit_card', label: 'Tarjeta de crédito' },
  { value: 'statement', label: 'Extracto de tarjeta' },
  { value: 'statement_tx', label: 'Transacción de extracto' },
  { value: 'merchant_alias', label: 'Alias de comercio' },
  { value: 'notification_recipient', label: 'Destinatario de notificación' },
  { value: 'settings', label: 'Configuración' },
  { value: 'project', label: 'Proyecto' },
  { value: 'collection_account', label: 'Cuenta de cobro' },
];

export const ACTION_OPTIONS = [
  { value: 'created', label: 'Creado' },
  { value: 'updated', label: 'Actualizado' },
  { value: 'deleted', label: 'Eliminado' },
];

export const SENDS_DEFAULTS = {
  template_key: [],
  status: [],
  origin_action: [],
  entity_type: [],
  client: [],
  project: [],
  recipient: '',
  // Only ever set by a deep link from the record's own row; there is no
  // control for it, and the chip that shows it clears it.
  object_id: '',
  date_from: '',
  date_to: '',
};

export const CHANGES_DEFAULTS = {
  entity_type: [],
  action: [],
  client: [],
  project: [],
  actor: '',
  object_id: '',
  date_from: '',
  date_to: '',
};

/** Panel fields for Envíos. Client and project options come from the page. */
export function sendsFilterFields({ clients = [], projects = [] } = {}) {
  return [
    { kind: 'multi', key: 'template_key', label: 'Aviso', options: TEMPLATE_KEY_OPTIONS },
    { kind: 'multi', key: 'status', label: 'Estado', options: SEND_STATUS_OPTIONS },
    { kind: 'multi', key: 'entity_type', label: 'Tipo de registro', options: SEND_ENTITY_OPTIONS },
    { kind: 'multi', key: 'client', label: 'Cliente', options: clients },
    { kind: 'multi', key: 'project', label: 'Proyecto', options: projects },
    { kind: 'multi', key: 'origin_action', label: 'Acción de origen', options: ACTION_OPTIONS },
    {
      kind: 'text',
      key: 'recipient',
      label: 'Destinatario',
      placeholder: 'correo…',
    },
    { kind: 'daterange', label: 'Fecha', minKey: 'date_from', maxKey: 'date_to' },
  ];
}

/** Panel fields for Cambios. Client and project options come from the page —
 * the question a reassignment raises is "qué le pasó a ESTE cliente", and
 * until now only the send log could answer it. */
export function changesFilterFields({ clients = [], projects = [] } = {}) {
  return [
    { kind: 'multi', key: 'entity_type', label: 'Entidad', options: CHANGE_ENTITY_OPTIONS },
    { kind: 'multi', key: 'action', label: 'Acción', options: ACTION_OPTIONS },
    { kind: 'multi', key: 'client', label: 'Cliente', options: clients },
    { kind: 'multi', key: 'project', label: 'Proyecto', options: projects },
    { kind: 'text', key: 'actor', label: 'Usuario', placeholder: 'quién lo hizo…' },
    { kind: 'daterange', label: 'Fecha', minKey: 'date_from', maxKey: 'date_to' },
  ];
}

// `search` is the factory's own debounced free-text key; each subtab points
// it at the column its question is really about.
export const SENDS_PARAM_MAPPING = {
  template_key: 'template_key',
  status: 'status',
  origin_action: 'origin_action',
  entity_type: 'entity_type',
  recipient: 'recipient',
  client: 'client',
  project: 'project',
  object_id: 'object_id',
  date_from: 'date_from',
  date_to: 'date_to',
  search: 'subject',
};

export const CHANGES_PARAM_MAPPING = {
  entity_type: 'entity_type',
  action: 'action',
  client: 'client',
  project: 'project',
  actor: 'actor',
  object_id: 'object_id',
  date_from: 'date_from',
  date_to: 'date_to',
  search: 'object_repr',
};

export const SENDS_FILTERS_CONFIG = {
  viewName: 'accounting_history_sends',
  tabQueryParam: 'sendsTab',
  searchFields: [],
  defaultTabId: 'all',
  syncFiltersToUrl: true,
  defaults: { ...SENDS_DEFAULTS },
  matchers: {
    template_key: serverFilter('template_key'),
    status: serverFilter('status'),
    origin_action: serverFilter('origin_action'),
    entity_type: serverFilter('entity_type'),
    recipient: serverFilter('recipient'),
    client: serverFilter('client'),
    project: serverFilter('project'),
    object_id: serverFilter('object_id'),
    dateRange: serverFilter('date_from', 'date_to'),
  },
  builtinTabs: sendsBuiltinTabs(),
};

export const CHANGES_FILTERS_CONFIG = {
  viewName: 'accounting_history_changes',
  tabQueryParam: 'changesTab',
  searchFields: [],
  defaultTabId: 'all',
  syncFiltersToUrl: true,
  defaults: { ...CHANGES_DEFAULTS },
  matchers: {
    entity_type: serverFilter('entity_type'),
    action: serverFilter('action'),
    client: serverFilter('client'),
    project: serverFilter('project'),
    actor: serverFilter('actor'),
    object_id: serverFilter('object_id'),
    dateRange: serverFilter('date_from', 'date_to'),
  },
  builtinTabs: changesBuiltinTabs(),
};
