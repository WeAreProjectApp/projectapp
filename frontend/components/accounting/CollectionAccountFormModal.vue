<script setup>
import { computed, ref, useId, watch } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import BaseFloatingListbox from '~/components/base/BaseFloatingListbox.vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import ClientFormFields from '~/components/clients/ClientFormFields.vue';
import VatBreakdown from '~/components/accounting/VatBreakdown.vue';
import VatAmountInput from '~/components/accounting/VatAmountInput.vue';
import IncomeFormModal from '~/components/accounting/IncomeFormModal.vue';
import CollectionAccountProjectContext from '~/components/accounting/billing/CollectionAccountProjectContext.vue';
import { INPUT_FIELD_BASE, INPUT_FIELD_SIZE } from '~/components/base/inputClasses';
import { PANEL_BREAKPOINTS } from '~/config/responsive';
import { useIsMobile } from '~/composables/useIsMobile';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePersistedRef } from '~/composables/usePersistedRef';
import { useAccountingStore } from '~/stores/accounting';
import { useProposalClientsStore } from '~/stores/proposal_clients';
import { clientCustomerSnapshot, clientFormPayload, emptyClientForm } from '~/utils/billingCode';
import { downloadUrl } from '~/utils/downloadFile';
import { formatMoney } from '~/utils/formatMoney';

/**
 * Two-step create modal for cuentas de cobro: form → preview → send.
 *
 * The preview step shows the REAL email (subject + rendered body) and the
 * PDF the backend will attach — produced by the same pipeline as the send,
 * rolled back server-side — so confirming sends exactly what was reviewed.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  /** Preselected income row (entry point from the Ingresos tab). */
  income: { type: Object, default: null },
});

const emit = defineEmits(['close', 'created']);

const store = useAccountingStore();
const clientsStore = useProposalClientsStore();
const notify = usePanelNotify();

const step = ref('form');
const previewing = ref(false);
const saving = ref(false);
const validationAttempted = ref(false);
const preview = ref(null);
// Served by the backend, not a blob: the viewer names its download after the
// URL / Content-Disposition, and a blob: URL carries neither.
const pdfUrl = ref('');
// <embed> gives no load/error events, so the viewer's state comes from
// probing the URL with fetch: 'loading' | 'ready' | 'error' | 'idle'.
const pdfState = ref('idle');

// ── Client ──
const clientId = ref(null);
const suggestedNumber = ref('');
const numberDirty = ref(false);
const showInlineClient = ref(false);
const creatingClient = ref(false);
const selectedClient = ref(null);
const clientEmailDraft = ref('');
const clientEmailError = ref('');
const savingClientEmail = ref(false);
const editingClient = ref(false);
const savingClient = ref(false);
const clientEdit = ref(emptyClientForm());
const clientEditErrors = ref({});
// Client resolved from the selected income (PA-24): shown locked.
const clientFromIncome = ref(null);
const loadingClient = ref(false);
const inlineClient = ref(emptyClientForm());
const inlineClientErrors = ref({});
let clientRequestId = 0;

// ── Income ──
const selectedIncome = ref(null);
const billingContext = ref({});
const billingContextValid = ref(false);
const billingContextMessage = ref('');
const incomeQuery = ref('');
/** The FULL eligible set for the current search term, unscoped by client. */
const incomeOptions = ref([]);
const incomeOpen = ref(false);
const searchingIncomes = ref(false);
const showIncomeForm = ref(false);
const incomeBoxRef = ref(null);
const incomeInputRef = ref(null);
const incomeListboxId = `${useId()}-income-listbox`;

/**
 * Quick filters, applied client-side.
 *
 * The incomes endpoint does not paginate and the whole eligible ledger is a
 * couple of hundred rows, so alcance and estado are decided here instead of
 * round-tripping: every chip count is then exact, and switching a filter costs
 * no request — which is what keeps the dropdown open and the cursor in the box.
 * If the eligible set ever reaches the thousands, the counts move to the
 * endpoint's `meta` and this goes back to being server-side.
 */
const DEFAULT_INCOME_KIND = 'expected';
const incomeScope = ref('all'); // 'client' | 'all'
const incomeKind = ref(DEFAULT_INCOME_KIND); // 'all' | 'expected' | 'liquid'

/** Rows rendered per group; the rest are announced, never dropped in silence. */
const INCOME_GROUP_LIMIT = 25;
// Monotonic token: an extra keystroke while a debounced search is in flight
// would otherwise let the older response land last and win the list.
let incomeRequestId = 0;
// Whether the options were ever fetched, so refocusing an empty-but-loaded
// list does not re-ask for it.
let incomeFetched = false;

function defaultForm() {
  return {
    public_number: '',
    billing_concept: '',
    billing_description: '',
    unit_price: null,
    vat_rate: 19,
    vat_capture: null,
    period_start: '',
    period_end: '',
    term: 'days',
    payment_term_days: 8,
    due_date: '',
    city: '',
    customer: {
      name: '',
      identification_type: '',
      identification: '',
      email: '',
      contact_name: '',
      address: '',
    },
    notes: '',
  };
}

const form = ref(defaultForm());

const termOptions = [
  { value: 'days', label: 'Días tras emisión' },
  { value: 'fixed', label: 'Fecha fija' },
];
const identTypeOptions = [
  { value: 'NIT', label: 'NIT' },
  { value: 'CC', label: 'C.C.' },
];

/** Display name of the client currently chosen, whatever filled it in. */
const selectedClientName = computed(() => (
  clientFromIncome.value?.name
  || form.value.customer.name
  || form.value.customer.contact_name
  || (clientId.value ? `Cliente #${clientId.value}` : '')
));

watch(
  () => props.open,
  (open) => {
    clientRequestId += 1;
    if (!open) return;
    step.value = 'form';
    validationAttempted.value = false;
    preview.value = null;
    clearPdf();
    form.value = defaultForm();
    clientId.value = null;
    suggestedNumber.value = '';
    numberDirty.value = false;
    showInlineClient.value = false;
    selectedClient.value = null;
    clientEmailDraft.value = '';
    clientEmailError.value = '';
    savingClientEmail.value = false;
    savingClient.value = false;
    editingClient.value = false;
    clientEditErrors.value = {};
    showIncomeForm.value = false;
    clientFromIncome.value = null;
    loadingClient.value = false;
    inlineClientErrors.value = {};
    selectedIncome.value = null;
    billingContext.value = {};
    billingContextValid.value = false;
    billingContextMessage.value = '';
    incomeQuery.value = '';
    incomeOptions.value = [];
    incomeScope.value = 'all';
    incomeKind.value = DEFAULT_INCOME_KIND;
    incomeFetched = false;
    if (props.income) {
      applyIncome(props.income);
    } else {
      loadIncomes('');
    }
  },
  { immediate: true },
);

// ── Income combobox (remote search over expected+liquid incomes) ──

function applyIncome(income) {
  selectedIncome.value = income;
  const hasPayments = income.kind === 'liquid' || Number(income.paid_amount || 0) > 0;
  form.value.vat_rate = income.vat_rate ?? (hasPayments ? null : 19);
  form.value.vat_capture = null;
  incomeQuery.value = income.concept || '';
  if (!form.value.billing_concept) {
    form.value.billing_concept = income.concept || '';
  }
  if (!form.value.unit_price) {
    const amount = Number(income.pending_amount ?? income.total_amount ?? 0);
    form.value.unit_price = amount > 0 ? amount : null;
  }
  // A hosting income records the window it covers; the cuenta bills that
  // same window, so it arrives pre-filled instead of re-typed.
  if (income.period_start && !form.value.period_start) {
    form.value.period_start = income.period_start;
    form.value.period_end = income.period_end || '';
  }
  // The income already knows whose money this is: resolve the client from
  // it instead of asking for it again.
  if (income.client && !clientId.value) {
    clientFromIncome.value = {
      id: income.client,
      name: income.client_name || `Cliente #${income.client}`,
    };
    clientId.value = income.client;
    applyClientById(income.client);
  }
}

/** Fill the customer snapshot + suggested number from a client id alone. */
async function applyClientById(profileId) {
  const requestId = ++clientRequestId;
  loadingClient.value = true;
  const result = await clientsStore.fetchClient(profileId);
  if (requestId !== clientRequestId || !props.open) return;
  loadingClient.value = false;
  if (result.success && result.data) {
    await onClientSelect(result.data);
  }
}

async function loadIncomes(query) {
  const requestId = ++incomeRequestId;
  const params = {};
  if (query) params.q = query;
  // No `client` param on purpose: the request is the same whoever is billed,
  // so the alcance filter below can widen and narrow without a round trip and
  // its counts can be exact.
  searchingIncomes.value = true;
  const result = await store.searchIncomesForCollection(params);
  // A newer search (extra keystroke) already owns the list.
  if (requestId !== incomeRequestId) return;
  searchingIncomes.value = false;
  if (result.success) {
    incomeOptions.value = result.data;
    incomeFetched = true;
  }
}

// Changing client re-aims the filters, it never re-fetches: the options ref
// already holds every eligible income. The recorte of the previous selection
// must not survive the switch, and 'Del cliente' means nothing without one.
watch(clientId, (id) => {
  if (!props.open) return;
  incomeScope.value = id ? 'client' : 'all';
  // A cuenta normally bills money that is still expected. Reset to that
  // stable starting point instead of remembering the previous client's cut.
  incomeKind.value = DEFAULT_INCOME_KIND;
});

const debouncedIncomeSearch = useDebounceFn(
  () => loadIncomes(incomeQuery.value.trim()),
  250,
);

function onIncomeInput() {
  incomeOpen.value = true;
  if (selectedIncome.value && incomeQuery.value !== selectedIncome.value.concept) {
    selectedIncome.value = null;
  }
  debouncedIncomeSearch();
}

function onIncomeFocus() {
  incomeOpen.value = true;
  // Once loaded, an empty list is an answer ("nothing matches"), not a reason
  // to ask again — and re-asking on the concept of an already picked income
  // would shrink the set the chip counts describe.
  if (!incomeFetched) loadIncomes(incomeQuery.value.trim());
}

// ── Quick filters: alcance × estado ──

/** 'Del cliente' is literal: only their ledger. Anything unassigned, or filed
 *  under someone else, is what 'Todos' is for. */
function inScope(row, scope) {
  return scope === 'all' || row.client === clientId.value;
}

function inKind(row, kind) {
  return kind === 'all' || row.kind === kind;
}

/** Without a client there is no 'Del cliente' to speak of. */
const effectiveIncomeScope = computed(() => (clientId.value ? incomeScope.value : 'all'));

const filteredIncomes = computed(() => incomeOptions.value.filter(
  (row) => inScope(row, effectiveIncomeScope.value) && inKind(row, incomeKind.value),
));

// Faceted: each group is counted with the OTHER group's filter already
// applied, so a chip's number is exactly what clicking it would show.
const scopeCounts = computed(() => {
  const rows = incomeOptions.value.filter((row) => inKind(row, incomeKind.value));
  return {
    client: rows.filter((row) => inScope(row, 'client')).length,
    all: rows.length,
  };
});

const kindCounts = computed(() => {
  const rows = incomeOptions.value.filter(
    (row) => inScope(row, effectiveIncomeScope.value),
  );
  return {
    all: rows.length,
    expected: rows.filter((row) => row.kind === 'expected').length,
    liquid: rows.filter((row) => row.kind === 'liquid').length,
  };
});

const incomeScopeOptions = computed(() => [
  {
    value: 'client',
    label: `Del cliente (${scopeCounts.value.client})`,
    testId: 'collection-form-income-scope-client',
    disabled: !clientId.value,
    disabledReason: 'Selecciona un cliente para filtrar sus ingresos.',
  },
  {
    value: 'all',
    label: `Todos (${scopeCounts.value.all})`,
    testId: 'collection-form-income-scope-all',
  },
]);

const incomeKindOptions = computed(() => [
  {
    value: 'all',
    label: `Todos (${kindCounts.value.all})`,
    testId: 'collection-form-income-kind-all',
  },
  {
    value: 'expected',
    label: `Esperados (${kindCounts.value.expected})`,
    testId: 'collection-form-income-kind-expected',
  },
  {
    value: 'liquid',
    label: `Líquidos (${kindCounts.value.liquid})`,
    testId: 'collection-form-income-kind-liquid',
  },
]);

// Applying a filter must reveal its result, never hide it: the chips sit right
// above the input, so a closed list would read as "the filter emptied it".
function setIncomeScope(value) {
  incomeScope.value = value;
  incomeOpen.value = true;
}

function setIncomeKind(value) {
  incomeKind.value = value;
  incomeOpen.value = true;
}

function buildIncomeGroup(key, label, rows, { hint = '', showClient = false } = {}) {
  return {
    key,
    label,
    hint,
    showClient,
    total: rows.length,
    rows: rows.slice(0, INCOME_GROUP_LIMIT),
    hidden: Math.max(0, rows.length - INCOME_GROUP_LIMIT),
  };
}

/**
 * Under 'Del cliente' there is a single block: their ledger. Widening to
 * 'Todos' adds the other clients' rows — each naming its owner, since that is
 * the whole reason to look outside — and the still-unassigned ones, selectable
 * on purpose because issuing the cuenta assigns the client to them. Each block
 * declares how many rows it is holding back, so a long ledger never loses
 * records without saying so.
 */
const incomeGroups = computed(() => {
  const rows = filteredIncomes.value;
  const groups = [];
  if (clientId.value) {
    groups.push(buildIncomeGroup(
      'own',
      `De ${selectedClientName.value}`,
      rows.filter((row) => row.client === clientId.value),
    ));
  }
  if (effectiveIncomeScope.value === 'all') {
    groups.push(buildIncomeGroup(
      'others',
      clientId.value ? 'De otros clientes' : 'Con cliente asignado',
      rows.filter((row) => row.client != null && row.client !== clientId.value),
      { showClient: true },
    ));
    groups.push(buildIncomeGroup(
      'orphan',
      'Sin cliente',
      rows.filter((row) => row.client == null),
      {
        hint: clientId.value
          ? `Al elegirlo se asigna a ${selectedClientName.value}`
          : '',
      },
    ));
  }
  return groups.filter((group) => group.total > 0);
});

const hasIncomeMatches = computed(
  () => incomeGroups.value.some((group) => group.rows.length),
);

const INCOME_KIND_PHRASE = {
  all: 'ingresos para cobrar',
  expected: 'ingresos esperados',
  liquid: 'ingresos líquidos',
};

const INCOME_KIND_NOUN = {
  all: 'ingreso',
  expected: 'ingreso esperado',
  liquid: 'ingreso líquido',
};

/** A combination with no rows says WHICH combination came back empty: an empty
 *  list is otherwise indistinguishable from a load that failed. */
const incomeEmptyMessage = computed(() => {
  const query = incomeQuery.value.trim();
  const scoped = effectiveIncomeScope.value === 'client';
  if (query) {
    const owner = scoped ? ` de ${selectedClientName.value}` : '';
    return `Ningún ${INCOME_KIND_NOUN[incomeKind.value]}${owner} coincide con «${query}».`;
  }
  return scoped
    ? `${selectedClientName.value} no tiene ${INCOME_KIND_PHRASE[incomeKind.value]}.`
    : `No hay ${INCOME_KIND_PHRASE[incomeKind.value]} registrados.`;
});

/**
 * One-click escape from an empty combination.
 *
 * Prefer removing the kind cut while keeping the selected client. Only when
 * that client has no eligible income at all do we fall back to widening the
 * scope, preserving the existing route to unassigned and other-client rows.
 */
const incomeEmptyAction = computed(() => {
  if (incomeKind.value !== 'all' && kindCounts.value.all > 0) {
    return { dimension: 'kind', count: kindCounts.value.all };
  }
  if (effectiveIncomeScope.value === 'client' && scopeCounts.value.all > 0) {
    return { dimension: 'scope', count: scopeCounts.value.all };
  }
  return null;
});

function widenEmptyIncomeResults() {
  if (incomeEmptyAction.value?.dimension === 'kind') {
    setIncomeKind('all');
    return;
  }
  if (incomeEmptyAction.value?.dimension === 'scope') {
    setIncomeScope('all');
  }
}

function pickIncome(option) {
  if (option.has_collection_account) return;
  incomeOpen.value = false;
  applyIncome(option);
}

function incomeAmountLabel(option) {
  const amount = Number(option.pending_amount ?? option.total_amount ?? 0);
  return formatMoney(amount, 'COP');
}

// ── Client ↔ income coherence ──
//
// Only reachable by picking the income first and switching client afterwards:
// the backend rejects the pair with a 400, so the form says so up front
// instead of spending a preview round-trip on it.

const incomeClientConflict = computed(() => (
  selectedIncome.value?.client != null
  && clientId.value != null
  && selectedIncome.value.client !== clientId.value
));

const incomeOwnerName = computed(() => (
  selectedIncome.value?.client_name
  || `Cliente #${selectedIncome.value?.client}`
));

/**
 * The other half of the pairing: an income nobody owns yet.
 *
 * Issuing adopts the client onto it (the create service does it in the same
 * transaction), so the form says so before the send rather than mutating the
 * income now — abandoning the modal must leave the ledger as it was.
 */
const orphanIncomeSelected = computed(() => (
  !!selectedIncome.value && selectedIncome.value.client == null
));

/**
 * Hand the client picker back to the operator.
 *
 * Picking an income locks its client (PA-24), which is right when the income
 * IS the starting point — the Ingresos-tab origin. Starting from this tab the
 * client is a choice, so the lock has to be undoable; otherwise a wrong income
 * means closing the modal and beginning again.
 */
function releaseClientFromIncome() {
  clientRequestId += 1;
  clientFromIncome.value = null;
  clientId.value = null;
  selectedClient.value = null;
  clientEmailDraft.value = '';
  clientEmailError.value = '';
  loadingClient.value = false;
  editingClient.value = false;
  form.value.customer = defaultForm().customer;
  suggestedNumber.value = '';
  form.value.public_number = '';
}

/** Resolve towards the income: adopt the client it already belongs to. */
async function useIncomeClient() {
  const income = selectedIncome.value;
  if (!income?.client) return;
  clientFromIncome.value = { id: income.client, name: incomeOwnerName.value };
  clientId.value = income.client;
  await applyClientById(income.client);
}

/** Resolve the other way: drop the income and keep the chosen client. */
function clearSelectedIncome() {
  selectedIncome.value = null;
  incomeQuery.value = '';
  loadIncomes('');
}

// ── Client selection + snapshot prefill ──

async function onClientSelect(client) {
  const requestId = ++clientRequestId;
  editingClient.value = false;
  selectedClient.value = client || null;
  clientEmailError.value = '';
  clientEmailDraft.value = client?.is_email_placeholder ? '' : (client?.email || '');
  if (!client) {
    form.value.customer = defaultForm().customer;
    suggestedNumber.value = '';
    form.value.public_number = '';
    return;
  }
  form.value.customer = clientCustomerSnapshot(client);
  numberDirty.value = false;
  const result = await store.fetchCollectionAccountNextNumber(client.id);
  if (requestId !== clientRequestId || !props.open) return;
  if (result.success) {
    suggestedNumber.value = result.data.suggested_number || '';
    form.value.public_number = suggestedNumber.value;
    if (!form.value.city) form.value.city = result.data.issuer_city || '';
  }
}

function startClientEdit() {
  clientEdit.value = {
    ...emptyClientForm(), ...selectedClient.value,
    email: selectedClientMissingEmail.value ? '' : selectedClient.value.email,
    identification_type: selectedClient.value.nit ? 'NIT' : (selectedClient.value.cedula ? 'CC' : 'NIT'),
  };
  clientEditErrors.value = {};
  editingClient.value = true;
}

function clearClientEditError(field) {
  const next = { ...clientEditErrors.value };
  delete next[field];
  clientEditErrors.value = next;
}

async function saveClientDetails() {
  if (savingClient.value) return;
  if (!clientEdit.value.name.trim()) {
    clientEditErrors.value = { name: 'Escribe el nombre del cliente.' };
    return;
  }
  const id = clientId.value;
  const requestId = clientRequestId;
  savingClient.value = true;
  const result = await clientsStore.updateClient(id, clientFormPayload(clientEdit.value));
  if (requestId !== clientRequestId || !props.open || clientId.value !== id) return;
  savingClient.value = false;
  if (!result.success) {
    clientEditErrors.value = result.errors || {};
    notify.error({ title: 'No se pudieron guardar los datos del cliente', detail: result.errors?.message || '' });
    return;
  }
  selectedClient.value = result.data;
  form.value.customer = clientCustomerSnapshot(result.data);
  clientEmailDraft.value = result.data.is_email_placeholder ? '' : (result.data.email || '');
  clientEmailError.value = '';
  if (clientFromIncome.value) clientFromIncome.value.name = result.data.name;
  editingClient.value = false;
  notify.success({ title: 'Datos del cliente guardados', detail: 'La cuenta usa los mismos datos de su ficha.' });
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim());
}

const selectedClientMissingEmail = computed(() => (
  !!selectedClient.value
  && (
    selectedClient.value.is_email_placeholder
    || !isValidEmail(selectedClient.value.email)
  )
));

/** Persist the repair on the canonical profile; the rest of this modal stays local. */
async function saveClientEmail() {
  const email = clientEmailDraft.value.trim().toLowerCase();
  clientEmailError.value = '';
  if (!isValidEmail(email)) {
    clientEmailError.value = 'Escribe un correo válido antes de guardarlo.';
    return;
  }
  if (!clientId.value) {
    clientEmailError.value = 'Selecciona un cliente antes de guardar el correo.';
    return;
  }

  savingClientEmail.value = true;
  const result = await clientsStore.updateClient(clientId.value, { email });
  savingClientEmail.value = false;
  if (!result.success) {
    clientEmailError.value = result.errors?.message
      || result.errors?.email?.[0]
      || result.errors?.error
      || 'No se pudo guardar el correo. Intenta nuevamente.';
    return;
  }

  selectedClient.value = result.data;
  clientEmailDraft.value = result.data.email || email;
  form.value.customer.email = result.data.email || email;
  notify.success({
    title: 'Correo guardado en el cliente',
    detail: 'También se usará como destinatario de esta cuenta de cobro.',
  });
}

function onCreateNewClient(typedName) {
  showInlineClient.value = true;
  inlineClient.value = { ...emptyClientForm(), name: typedName || '' };
  inlineClientErrors.value = {};
}

function clearInlineClientError(field) {
  if (!inlineClientErrors.value[field]) return;
  const next = { ...inlineClientErrors.value };
  delete next[field];
  inlineClientErrors.value = next;
}

async function createInlineClient() {
  inlineClientErrors.value = {};
  if (!inlineClient.value.name.trim()) {
    inlineClientErrors.value = { name: 'Escribe el nombre del cliente.' };
    return;
  }
  creatingClient.value = true;
  const result = await clientsStore.createClient(clientFormPayload(inlineClient.value));
  creatingClient.value = false;
  if (result.success && result.data?.id) {
    showInlineClient.value = false;
    clientId.value = result.data.id;
    await onClientSelect(result.data);
    notify.success({ title: 'Cliente creado' });
  } else {
    const fields = Object.fromEntries(
      Object.entries(result.errors || {})
        .filter(([field]) => field !== 'message' && field !== 'error')
        .map(([field, messages]) => [
          field,
          Array.isArray(messages) ? messages.join(' ') : String(messages || ''),
        ]),
    );
    inlineClientErrors.value = fields;
    if (!Object.keys(fields).length) {
      notify.error({
        title: 'No se pudo crear el cliente',
        detail: result.errors?.message || '',
      });
    }
  }
}

/** The client chosen upstream: the stacked income form inherits it instead
 *  of offering a second picker that could contradict this one. */
const lockedClientForIncome = computed(() => (
  clientId.value
    ? { id: clientId.value, name: selectedClientName.value }
    : null
));

function onNumberInput() {
  numberDirty.value = form.value.public_number !== suggestedNumber.value;
}

// ── Inline expected-income creation (stacked IncomeFormModal) ──

async function handleIncomeCreated(payload) {
  const result = await store.createRecord('incomes', payload);
  if (result.success) {
    showIncomeForm.value = false;
    if (result.data?.kind !== 'lost') {
      applyIncome(result.data);
    }
    notify.success({ title: 'Ingreso creado' });
  } else {
    notify.error({ title: 'No se pudo crear el ingreso', detail: result.message });
  }
}

// ── Preview layout: correo | PDF ──
//
// The review step shows two independently scrolling panes instead of the old
// vertical stack, which produced three nested scrollbars (panel + email iframe
// + PDF viewer) and let neither piece be read. Here the panel itself never
// scrolls (BaseModal `fullHeight`); the scroll of each column is the one the
// embedded document already brings — the srcdoc's own for the email, the
// native viewer's for the PDF. One level per column, none on the modal.
const SPLIT_MIN = 25;
const SPLIT_MAX = 60;
const SPLIT_DEFAULT = 40;
const SPLIT_KEY = 'projectapp-collection-preview-split';

// Below the canonical landscape profile neither pane stays legible side by
// side, so both collapse into tabs; compact opens on the PDF first.
const { isMobile: isNarrow } = useIsMobile(PANEL_BREAKPOINTS.landscape - 1);
const { isMobile: isPhone } = useIsMobile(PANEL_BREAKPOINTS.portrait - 1);
const isSplit = computed(() => !isNarrow.value);

function clampSplit(value) {
  const pct = Number(value);
  if (!Number.isFinite(pct)) return SPLIT_DEFAULT;
  return Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, pct));
}

const { ref: emailPct, write: writeSplit } = usePersistedRef(SPLIT_KEY, SPLIT_DEFAULT);
emailPct.value = clampSplit(emailPct.value);

const previewPane = ref('email');
const previewPaneOptions = [
  { value: 'email', label: 'Correo', testId: 'collection-preview-tab-email' },
  { value: 'pdf', label: 'PDF', testId: 'collection-preview-tab-pdf' },
];

const splitRef = ref(null);
const dragging = ref(false);

const gridStyle = computed(() => ({
  gridTemplateColumns: isSplit.value
    ? `${emailPct.value}% 1rem minmax(0, 1fr)`
    : 'minmax(0, 1fr)',
}));

function showsPane(pane) {
  return isSplit.value || previewPane.value === pane;
}

function onSplitDown(e) {
  if (!isSplit.value) return;
  dragging.value = true;
  e.currentTarget.setPointerCapture?.(e.pointerId);
}

function onSplitMove(e) {
  if (!dragging.value || !splitRef.value) return;
  const rect = splitRef.value.getBoundingClientRect();
  if (!rect.width) return;
  emailPct.value = clampSplit(((e.clientX - rect.left) / rect.width) * 100);
}

function onSplitUp(e) {
  if (!dragging.value) return;
  dragging.value = false;
  e.currentTarget.releasePointerCapture?.(e.pointerId);
  writeSplit(emailPct.value);
}

function onSplitKey(e) {
  let next = null;
  if (e.key === 'ArrowLeft') next = emailPct.value - 2;
  else if (e.key === 'ArrowRight') next = emailPct.value + 2;
  else if (e.key === 'Home') next = SPLIT_MIN;
  else if (e.key === 'End') next = SPLIT_MAX;
  if (next === null) return;
  e.preventDefault();
  emailPct.value = clampSplit(next);
  writeSplit(emailPct.value);
}

// ── Preview + confirm ──

const clientValidationError = computed(() => {
  if (!validationAttempted.value) return '';
  if (!clientId.value) return 'Elige o crea un cliente.';
  if (loadingClient.value) return 'Espera a que carguen los datos del cliente.';
  if (editingClient.value) return 'Guarda los datos del cliente o cancela su edición antes de revisar la cuenta.';
  if (selectedClientMissingEmail.value) return 'Agrega y guarda el correo del cliente.';
  return '';
});
const incomeValidationError = computed(() => {
  if (!validationAttempted.value) return '';
  if (!selectedIncome.value?.id) return 'Selecciona un ingreso vinculado.';
  if (incomeClientConflict.value) return 'Resuelve el conflicto con el cliente del ingreso.';
  return '';
});
const billingContextValidationError = computed(() => (
  validationAttempted.value
  && (selectedIncome.value?.project || selectedIncome.value?.project_id)
  && !billingContextValid.value
    ? (billingContextMessage.value || 'Completa el tipo de cobro y selecciona el contrato o hosting en «Cobro del proyecto».')
    : ''
));
const amountValidationError = computed(() => (
  validationAttempted.value && !(Number(form.value.unit_price) > 0)
    ? 'Ingresa un valor mayor a cero.'
    : ''
));
const conceptValidationError = computed(() => (
  validationAttempted.value && !form.value.billing_concept.trim()
    ? 'Escribe el concepto del servicio.'
    : ''
));
const customerEmailValidationError = computed(() => (
  validationAttempted.value
  && clientId.value
  && !selectedClientMissingEmail.value
  && !isValidEmail(form.value.customer.email)
    ? 'Escribe un correo destinatario válido.'
    : ''
));
const dueDateValidationError = computed(() => (
  validationAttempted.value && form.value.term === 'fixed' && !form.value.due_date
    ? 'Selecciona la fecha fija de pago.'
    : ''
));

const previewBlockers = computed(() => [
  clientValidationError.value,
  incomeValidationError.value,
  billingContextValidationError.value,
  amountValidationError.value,
  conceptValidationError.value,
  customerEmailValidationError.value,
  dueDateValidationError.value,
].filter(Boolean));

const canPreview = computed(() => previewBlockers.value.length === 0);

function buildPayload() {
  const payload = {
    client_profile_id: clientId.value,
    income_record_id: selectedIncome.value.id,
    ...billingContext.value,
    billing_concept: form.value.billing_concept,
    vat_rate: form.value.vat_rate,
    items: [{
      // The Descripción column of the detalle. Sent raw — the backend falls
      // back to the concepto corto when it arrives empty, so a simple cuenta
      // still reads the way it does today.
      description: form.value.billing_description,
      quantity: '1',
      amount: String(form.value.vat_capture?.amount ?? form.value.unit_price),
      amount_mode: form.value.vat_capture?.amount_mode ?? 'vat_included',
      period_start: form.value.period_start || null,
      period_end: form.value.period_end || null,
    }],
    city: form.value.city,
    customer: { ...form.value.customer },
    notes: form.value.notes,
  };
  if (numberDirty.value && form.value.public_number.trim()) {
    payload.public_number = form.value.public_number.trim();
  }
  if (form.value.term === 'fixed' && form.value.due_date) {
    payload.due_date = form.value.due_date;
  } else {
    // `|| 8` read a deliberate 0 — pago inmediato — as "empty" and billed it
    // at the default term instead, so the zero has to survive on its own.
    // Blank is tested before Number(), which turns '' into 0 and would have
    // made an emptied field mean immediate payment.
    const raw = form.value.payment_term_days;
    const days = Number(raw);
    const unset = raw === '' || raw === null || raw === undefined;
    // The input declares min=0/max=120 but typed values bypass those bounds;
    // clamping here keeps a stray "-5" from bouncing off the serializer as a 400.
    payload.payment_term_days = unset || Number.isNaN(days)
      ? 8
      : Math.min(120, Math.max(0, Math.trunc(days)));
  }
  return payload;
}

async function goPreview() {
  validationAttempted.value = true;
  if (!canPreview.value || previewing.value) return;
  previewing.value = true;
  const result = await store.previewCollectionAccount(buildPayload());
  previewing.value = false;
  if (!result.success) {
    notify.error({
      title: 'No se pudo generar la previsualización',
      detail: result.message,
    });
    return;
  }
  preview.value = result.data;
  // A real same-origin URL ending in the consecutivo and served with
  // `Content-Disposition: inline; filename=...`. That header is what names the
  // save in Chrome's own viewer button and in "Save to Drive" — the blob: URL
  // this used to build had no name and the viewer fell back to its UUID.
  pdfUrl.value = result.data.pdf_url || '';
  probePdf();
  // On a phone two columns would leave ~180px each and the PDF unreadable, so
  // the tabs open on the document; from a tablet up the email leads.
  previewPane.value = isPhone.value ? 'pdf' : 'email';
  step.value = 'preview';
}

/**
 * The embed only mounts once the URL is known to answer: a blocked or broken
 * URL would otherwise leave the browser's own connection-refused page inside
 * the frame, which says nothing about what to do next. On failure the panel
 * keeps Descargar / Abrir PDF as the way to review before sending.
 */
async function probePdf() {
  if (!pdfUrl.value) {
    pdfState.value = 'error';
    return;
  }
  pdfState.value = 'loading';
  try {
    const response = await fetch(pdfUrl.value, { credentials: 'same-origin' });
    pdfState.value = response.ok ? 'ready' : 'error';
  } catch {
    pdfState.value = 'error';
  }
}

async function confirmSend() {
  saving.value = true;
  const result = await store.createCollectionAccount(buildPayload());
  saving.value = false;
  if (!result.success) {
    notify.error({
      title: 'No se pudo crear la cuenta de cobro',
      detail: result.message,
    });
    return;
  }
  const number = result.data?.document?.public_number || '';
  if (result.data?.email_sent) {
    notify.success({
      title: 'Cuenta de cobro enviada',
      detail: number
        ? `Documento ${number} enviado a ${preview.value?.customer_email || 'cliente'}.`
        : '',
    });
  } else {
    notify.warning({
      title: `Cuenta ${number} emitida, pero el correo falló`,
      detail: 'Reenvíala con la acción "Reenviar al cliente".',
    });
  }
  emit('created', result.data);
  close();
}

/** Nothing to revoke any more; the URL is the backend's, not an object URL. */
function clearPdf() {
  pdfUrl.value = '';
  pdfState.value = 'idle';
}

function close() {
  clearPdf();
  emit('close');
}

function openPdfTab() {
  if (pdfUrl.value) window.open(pdfUrl.value, '_blank', 'noopener');
}

function downloadPdf() {
  if (!pdfUrl.value) return;
  const number = preview.value?.public_number || 'cuenta-de-cobro';
  downloadUrl(pdfUrl.value, `${number}.pdf`);
}

const modalFormId = useId();
</script>

<template>
  <BaseModal
    :model-value="open"
    :kind="step === 'preview' ? 'workspace' : 'form'"
    :full-height="step === 'preview'"
    title-id="collection-form-title"
    @close="close"
  >
    <div class="shrink-0 px-6 pt-6 pb-2 flex items-center justify-between gap-3">
      <h3 id="collection-form-title" class="text-lg font-bold text-text-default">
        {{ step === 'form' ? 'Nueva cuenta de cobro' : 'Revisar antes de enviar' }}
      </h3>
      <span class="text-xs text-text-subtle">
        Paso {{ step === 'form' ? '1' : '2' }} de 2
      </span>
    </div>

    <!-- ── Step 1: form ── -->
    <form :id="modalFormId"
      v-if="step === 'form'"
      class="px-6 py-4 space-y-4"
      novalidate
      @submit.prevent="goPreview"
    >
      <BaseFormField label="Cliente" required :error="clientValidationError">
        <div
          v-if="clientFromIncome"
          class="flex items-center justify-between gap-2 rounded-xl border border-border-default bg-surface-raised px-3 py-2.5 text-sm text-text-default"
          data-testid="collection-form-client-locked"
        >
          <span>
            {{ clientFromIncome.name }}
            <span class="text-text-subtle">· desde el ingreso</span>
          </span>
          <button
            v-if="!props.income"
            type="button"
            class="text-xs text-text-brand hover:underline whitespace-nowrap"
            data-testid="collection-form-change-client"
            @click="releaseClientFromIncome"
          >
            Cambiar
          </button>
        </div>
        <ClientAutocomplete
          v-else
          v-model="clientId"
          test-id="collection-form-client"
          allow-create
          :error="!!clientValidationError"
          @select="onClientSelect"
          @create-new="onCreateNewClient"
        />
        <div
          v-if="selectedClientMissingEmail"
          class="mt-2 rounded-xl border border-warning-strong bg-warning-soft p-3 space-y-2"
          data-testid="collection-form-client-email-warning"
        >
          <div>
            <p class="text-sm font-medium text-text-default">Este cliente no tiene correo.</p>
            <p class="text-xs text-text-muted">
              La cuenta necesita un destinatario. Guárdalo aquí y podrás continuar sin perder lo diligenciado.
            </p>
          </div>
          <div class="flex flex-col gap-2 panel-portrait:flex-row panel-portrait:items-start">
            <div class="flex-1">
              <BaseInput
                v-model="clientEmailDraft"
                type="email"
                placeholder="cliente@empresa.com"
                data-testid="collection-form-client-email-repair"
                :aria-invalid="Boolean(clientEmailError)"
                @keydown.enter.prevent="saveClientEmail"
              />
              <p
                v-if="clientEmailError"
                class="text-xs text-danger-strong mt-1"
                role="alert"
                data-testid="collection-form-client-email-error"
              >
                {{ clientEmailError }}
              </p>
            </div>
            <BaseButton
              type="button"
              variant="primary"
              size="sm"
              :loading="savingClientEmail"
              data-testid="collection-form-client-email-save"
              @click="saveClientEmail"
            >
              {{ savingClientEmail ? 'Guardando...' : 'Guardar y usar' }}
            </BaseButton>
          </div>
        </div>
      </BaseFormField>

      <!-- Inline client creation (module de clientes, sin salir del flujo) -->
      <div
        v-if="showInlineClient"
        class="rounded-xl border border-border-default bg-surface-raised p-4 space-y-3"
        data-testid="collection-form-inline-client"
      >
        <p class="text-sm font-medium text-text-default">Crear cliente nuevo</p>
        <ClientFormFields
          v-model="inlineClient"
          :errors="inlineClientErrors"
          testid-prefix="collection-form-inline-client"
          dense
          @clear-error="clearInlineClientError"
        />
        <div class="flex justify-end gap-2">
          <BaseButton type="button" variant="secondary" size="sm" @click="showInlineClient = false">
            Cancelar
          </BaseButton>
          <BaseButton
            type="button"
            variant="primary"
            size="sm"
            :disabled="creatingClient"
            data-testid="collection-form-inline-client-save"
            @click="createInlineClient"
          >
            {{ creatingClient ? 'Creando...' : 'Crear cliente' }}
          </BaseButton>
        </div>
      </div>

      <!-- Income combobox: mandatory link -->
      <BaseFormField
        label="Ingreso vinculado"
        required
        hint="Los ingresos perdidos nunca se listan"
        :error="incomeValidationError"
      >
        <template v-if="props.income">
          <div
            class="rounded-xl border border-border-default bg-surface-raised px-3 py-2.5 text-sm text-text-default"
            data-testid="collection-form-income-locked"
          >
            {{ props.income.concept }}
            <span class="text-text-subtle">· {{ incomeAmountLabel(props.income) }}</span>
          </div>
        </template>
        <div v-else ref="incomeBoxRef">
          <!-- Narrowing the set before searching it. The row cancels the
               mousedown default action — the one that moves focus — so a chip
               click never pulls the cursor out of the box below nor collapses
               the list, the same trick the option rows already use. -->
          <div
            class="flex flex-wrap items-center gap-x-3 gap-y-2 mb-2"
            data-testid="collection-form-income-filters"
            @mousedown.prevent
          >
            <span class="flex items-center gap-1.5 text-xs text-text-muted">
              Alcance
              <BaseSegmented
                :model-value="effectiveIncomeScope"
                :options="incomeScopeOptions"
                size="sm"
                @update:model-value="setIncomeScope"
              />
            </span>
            <span class="flex items-center gap-1.5 text-xs text-text-muted">
              Estado
              <BaseSegmented
                :model-value="incomeKind"
                :options="incomeKindOptions"
                size="sm"
                @update:model-value="setIncomeKind"
              />
            </span>
          </div>
          <p v-if="!clientId" class="mb-2 text-xs text-text-subtle">
            Selecciona un cliente para habilitar el filtro «Del cliente».
          </p>
          <div class="relative">
            <input
              ref="incomeInputRef"
              v-model="incomeQuery"
              type="text"
              role="combobox"
              autocomplete="off"
              aria-autocomplete="list"
              aria-haspopup="listbox"
              :aria-expanded="incomeOpen"
              :aria-controls="incomeOpen ? incomeListboxId : undefined"
              placeholder="Buscar ingreso por concepto..."
              data-testid="collection-form-income"
              :class="[INPUT_FIELD_BASE, INPUT_FIELD_SIZE.md]"
              @input="onIncomeInput"
              @focus="onIncomeFocus"
              @keydown.esc.prevent="incomeOpen = false"
            >
            <BaseFloatingListbox
              :id="incomeListboxId"
              as="ul"
              :open="incomeOpen"
              :anchor="incomeInputRef"
              :owner="incomeBoxRef"
              @close="incomeOpen = false"
            >
              <li v-if="searchingIncomes" class="px-3 py-2 text-sm text-text-subtle">
                Buscando...
              </li>
              <!-- Naming the combination that came back empty: a blank panel
                   reads as a load that failed. -->
              <li
                v-else-if="!hasIncomeMatches"
                class="px-3 py-2 text-sm text-text-subtle"
                data-testid="collection-form-income-empty"
              >
                {{ incomeEmptyMessage }}
                <button
                  v-if="incomeEmptyAction"
                  type="button"
                  class="underline text-text-brand"
                  data-testid="collection-form-income-see-all"
                  @click="widenEmptyIncomeResults"
                >
                  Ver todos ({{ incomeEmptyAction.count }})
                </button>
              </li>
              <template v-for="group in incomeGroups" :key="group.key">
                <li
                  v-if="group.label"
                  role="presentation"
                  :data-testid="`collection-form-income-group-${group.key}`"
                  class="sticky top-0 bg-surface-raised px-3 py-1.5 text-xs font-medium text-text-subtle border-b border-border-default"
                >
                  {{ group.label }} ({{ group.total }})
                  <span v-if="group.hint" class="block font-normal">{{ group.hint }}</span>
                </li>
                <li
                  v-for="option in group.rows"
                  :key="option.id"
                  role="option"
                  :aria-disabled="option.has_collection_account"
                  :data-testid="`collection-form-income-option-${option.id}`"
                  :class="[
                    'px-3 py-2 text-sm transition-colors',
                    option.has_collection_account
                      ? 'opacity-50 cursor-not-allowed'
                      : 'cursor-pointer hover:bg-surface-raised text-text-default',
                  ]"
                  @mousedown.prevent="pickIncome(option)"
                >
                  <span class="flex items-center justify-between gap-2">
                    <span class="truncate">{{ option.concept }}</span>
                    <span class="text-xs text-text-subtle whitespace-nowrap">
                      {{ option.kind_label }} · {{ incomeAmountLabel(option) }}
                    </span>
                  </span>
                  <!-- Outside the client's own ledger the owner is the fact that
                       decides whether the row is billable at all. -->
                  <span
                    v-if="group.showClient"
                    class="block text-xs text-text-subtle"
                    :data-testid="`collection-form-income-client-${option.id}`"
                  >
                    {{ option.client_name || `Cliente #${option.client}` }}
                  </span>
                  <span
                    v-if="option.has_collection_account"
                    class="block text-xs text-warning-strong"
                  >
                    Ya tiene cuenta de cobro ({{ option.collection_account_number }})
                  </span>
                </li>
                <li
                  v-if="group.hidden"
                  role="presentation"
                  :data-testid="`collection-form-income-more-${group.key}`"
                  class="px-3 py-2 text-xs text-text-subtle"
                >
                  Mostrando {{ group.rows.length }} de {{ group.total }} · escribe para filtrar
                </li>
              </template>
            </BaseFloatingListbox>
            <p
              v-if="incomeClientConflict"
              class="text-xs text-warning-strong mt-1"
              data-testid="collection-form-income-conflict"
            >
              Este ingreso es de {{ incomeOwnerName }}, no de {{ selectedClientName }}.
              <button
                type="button"
                class="underline"
                data-testid="collection-form-use-income-client"
                @click="useIncomeClient"
              >
                Usar el cliente del ingreso
              </button>
              ·
              <button
                type="button"
                class="underline"
                data-testid="collection-form-clear-income"
                @click="clearSelectedIncome"
              >
                Quitar el ingreso
              </button>
            </p>
            <p
              v-else-if="orphanIncomeSelected"
              class="text-xs text-text-muted mt-1"
              data-testid="collection-form-income-orphan-notice"
            >
              Ingreso <span class="tabular-nums">#{{ selectedIncome.id }}</span> sin cliente:
              <template v-if="clientId">
                al emitir quedará asignado a {{ selectedClientName }}.
              </template>
              <template v-else>
                elige el cliente arriba y quedará asignado a él al emitir.
              </template>
            </p>
            <p v-else-if="selectedIncome" class="text-xs text-text-subtle mt-1">
              Ingreso enlazado: {{ selectedIncome.concept }}
              <span class="tabular-nums">(#{{ selectedIncome.id }})</span>
            </p>
            <button
              type="button"
              class="text-xs text-text-brand hover:underline mt-1"
              data-testid="collection-form-create-income"
              @click="showIncomeForm = true"
            >
              <BaseActionIcon action="create" />
              Crear ingreso esperado
            </button>
          </div>
        </div>
      </BaseFormField>

      <CollectionAccountProjectContext
        v-if="open"
        v-model="billingContext"
        :project-id="selectedIncome?.project || selectedIncome?.project_id || null"
        :validation-error="billingContextValidationError"
        @valid="billingContextValid = $event"
        @validation-message="billingContextMessage = $event"
      />

      <BaseFormRow :cols="2" :gap="4" help="El consecutivo sugerido se puede editar.">
        <BaseFormField label="Consecutivo">
          <BaseInput
            v-model="form.public_number"
            data-testid="collection-form-number"
            :placeholder="suggestedNumber || 'Selecciona un cliente'"
            @input="onNumberInput"
          />
        </BaseFormField>
        <BaseFormField label="Concepto del servicio" required :error="conceptValidationError">
          <BaseInput
            v-model="form.billing_concept"
            data-testid="collection-form-concept"
            :error="!!conceptValidationError"
          />
        </BaseFormField>
      </BaseFormRow>

      <VatAmountInput v-model="form.unit_price" v-model:rate="form.vat_rate" :reset-key="open"
          :error="amountValidationError"
          input-test-id="collection-form-amount" :disabled="selectedIncome?.kind === 'liquid' || Number(selectedIncome?.paid_amount || 0) > 0"
          disabled-reason="Este ingreso ya tiene pagos; se conservan su saldo y su IVA." @capture="form.vat_capture = $event" />
      <p class="text-xs text-text-muted" data-testid="collection-income-vat-hint">
        Al emitir, el valor y el IVA se actualizarán también en el ingreso si todavía no tiene pagos ni deducciones.
      </p>

      <BaseFormField
        label="Descripción del concepto"
        hint="Va en la columna Descripción del PDF. Si queda vacía, se muestra el concepto."
      >
        <BaseTextarea
          v-model="form.billing_description"
          :rows="3"
          data-testid="collection-form-description"
          placeholder="Ej.&#10;- Ajuste del formulario de cotización&#10;- Reporte mensual de ventas por asesor"
        />
      </BaseFormField>

      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Inicio del período facturado">
          <BaseInput v-model="form.period_start" type="date" data-testid="collection-form-period-start" />
        </BaseFormField>
        <BaseFormField label="Fin del período facturado">
          <BaseInput v-model="form.period_end" type="date" data-testid="collection-form-period-end" />
        </BaseFormField>
      </BaseFormRow>

      <!-- The hint only holds for the days mode; the fixed-date mode shares
           this field, where a 0 would mean nothing. -->
      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Ciudad">
          <BaseInput v-model="form.city" placeholder="Ciudad de emisión" />
        </BaseFormField>
      <BaseFormField
        label="Plazo de pago"
        :error="dueDateValidationError"
        :hint="form.term === 'days'
          ? '0 días = pago inmediato: la cuenta sale sin fecha de vencimiento.'
          : undefined"
      >
        <div class="space-y-2">
          <BaseSegmented v-model="form.term" :options="termOptions" full-width />
          <BaseInput
            v-if="form.term === 'days'"
            v-model="form.payment_term_days"
            type="number"
            min="0"
            max="120"
            data-testid="collection-form-term-days"
          />
          <BaseInput
            v-else
            v-model="form.due_date"
            type="date"
            :error="!!dueDateValidationError"
            data-testid="collection-form-due-date"
          />
        </div>
      </BaseFormField>
      </BaseFormRow>

      <!-- Editable customer snapshot -->
      <div class="rounded-xl border border-border-default p-4 space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="text-sm font-medium text-text-default">Datos del cliente en el documento</p>
          <BaseButton v-if="selectedClient" type="button" variant="link" size="sm" data-testid="collection-form-edit-client" @click="startClientEdit">
            Editar ficha del cliente
          </BaseButton>
        </div>
        <p class="text-xs text-text-muted">Se completan desde la ficha del cliente: nombre, identificación, contacto, correo y dirección.</p>
        <div v-if="editingClient" class="space-y-3" data-testid="collection-form-client-edit">
          <ClientFormFields v-model="clientEdit" :errors="clientEditErrors" testid-prefix="collection-form-client-edit" dense @clear-error="clearClientEditError" />
          <div class="flex flex-wrap justify-end gap-2">
            <BaseButton type="button" variant="secondary" size="sm" :disabled="savingClient" @click="editingClient = false">Cancelar edición</BaseButton>
            <BaseButton type="button" variant="primary" size="sm" :disabled="savingClient" data-testid="collection-form-client-edit-save" @click="saveClientDetails">{{ savingClient ? 'Guardando…' : 'Guardar datos del cliente' }}</BaseButton>
          </div>
        </div>
        <BaseFormRow
          :cols="2"
          :gap="3"
          help="El correo se completa desde el cliente; cambiarlo aquí sólo afecta esta cuenta."
        >
          <BaseFormField label="Nombre / Razón social">
            <BaseInput v-model="form.customer.name" data-testid="collection-form-customer-name" />
          </BaseFormField>
          <BaseFormField label="Correo destinatario de esta cuenta" required :error="customerEmailValidationError">
            <BaseInput
              v-model="form.customer.email"
              type="email"
              data-testid="collection-form-customer-email"
              required
              :error="!!customerEmailValidationError"
              :disabled="selectedClientMissingEmail"
              disabled-reason="Guarda el correo del cliente en el aviso superior para habilitar este campo."
            />
          </BaseFormField>
        </BaseFormRow>
        <BaseFormRow :cols="2" :gap="3">
          <BaseFormField label="Tipo de identificación">
            <BaseSegmented
              v-model="form.customer.identification_type"
              :options="identTypeOptions"
              full-width
            />
          </BaseFormField>
          <BaseFormField label="Número de identificación">
            <BaseInput
              v-model="form.customer.identification"
              data-testid="collection-form-customer-identification"
            />
          </BaseFormField>
        </BaseFormRow>
        <BaseFormRow :cols="2" :gap="3">
          <BaseFormField label="Contacto">
            <BaseInput v-model="form.customer.contact_name" />
          </BaseFormField>
          <BaseFormField label="Dirección">
            <BaseInput v-model="form.customer.address" data-testid="collection-form-customer-address" />
          </BaseFormField>
        </BaseFormRow>
      </div>

      <p class="text-xs text-text-subtle">
        Se incluirán los datos de pago configurados del emisor; los verás en la previsualización.
      </p>

      <BaseFormField
        label="Notas internas"
        hint="Sólo para ti: no aparecen en el PDF ni en el correo. Las vuelves a ver en el listado de cuentas de cobro."
      >
        <BaseTextarea
          v-model="form.notes"
          :rows="2"
          data-testid="collection-form-notes"
        />
      </BaseFormField>

    </form>

    <!-- ── Step 2: preview ── -->
    <div v-else class="flex-1 min-h-0 flex flex-col">
      <!-- Fixed: what is being sent and to whom, always in sight. -->
      <div class="shrink-0 px-6 pb-3 space-y-3">
        <div class="rounded-xl border border-border-default bg-surface-raised p-4 space-y-1 text-sm">
          <p class="text-text-default" data-testid="collection-preview-subject">
            <span class="font-medium">Asunto:</span> {{ preview?.subject }}
          </p>
          <p class="text-text-subtle">
            <span class="font-medium text-text-default">Para:</span>
            {{ preview?.customer_email }}
            <span class="mx-1">·</span>
            <span class="font-medium text-text-default">Número:</span>
            {{ preview?.public_number }}
            <span class="mx-1">·</span>
            <span class="font-medium text-text-default">Total:</span>
            {{ formatMoney(Number(preview?.total ?? 0), 'COP') }}
          </p>
        </div>
        <VatBreakdown :total="preview?.total" :rate="preview?.vat_rate ?? null" :tax="preview?.vat_rate != null ? preview.tax_total : null" />
        <p v-if="preview?.income_total" class="text-xs text-text-muted" data-testid="collection-preview-income-total">
          Total del ingreso al confirmar: {{ formatMoney(preview.income_total, 'COP') }}.
        </p>
        <BaseSegmented
          v-if="!isSplit"
          v-model="previewPane"
          :options="previewPaneOptions"
          size="sm"
          full-width
        />
      </div>

      <!-- The two panes. Each owns its scroll; the modal owns none. -->
      <div
        ref="splitRef"
        class="flex-1 min-h-0 px-6 grid"
        :class="dragging ? 'select-none' : ''"
        :style="gridStyle"
      >
        <section v-show="showsPane('email')" class="min-h-0 flex flex-col">
          <p class="shrink-0 text-sm font-medium text-text-default mb-2">
            Correo que recibirá el cliente
          </p>
          <iframe
            v-if="preview?.html_body"
            :srcdoc="preview.html_body"
            sandbox=""
            title="Vista previa del correo"
            class="flex-1 min-h-0 w-full rounded-xl border border-border-default bg-surface"
            :class="dragging ? 'pointer-events-none' : ''"
            data-testid="collection-preview-email"
          />
        </section>

        <!-- Without capture + pointer-events-none the iframe/embed below swallow
             the move events and the drag dies as soon as it enters a pane. -->
        <div
          v-if="isSplit"
          role="separator"
          aria-orientation="vertical"
          aria-label="Ajustar el ancho entre el correo y el PDF"
          :aria-valuenow="Math.round(emailPct)"
          :aria-valuemin="SPLIT_MIN"
          :aria-valuemax="SPLIT_MAX"
          tabindex="0"
          class="group flex cursor-col-resize items-center justify-center focus:outline-none"
          data-testid="collection-preview-split-handle"
          @pointerdown="onSplitDown"
          @pointermove="onSplitMove"
          @pointerup="onSplitUp"
          @pointercancel="onSplitUp"
          @keydown="onSplitKey"
        >
          <span
            class="h-10 w-1 rounded-full bg-border-default transition-colors group-hover:bg-text-brand group-focus-visible:bg-text-brand"
          />
        </div>

        <section v-show="showsPane('pdf')" class="min-h-0 flex flex-col">
          <div class="shrink-0 flex items-center justify-between gap-2 mb-2">
            <p class="text-sm font-medium text-text-default">PDF adjunto</p>
            <div v-if="pdfUrl" class="flex items-center gap-2">
              <!-- Both buttons and the viewer's own download now resolve to the
                   same served URL, so all three save PA-XXXX-001.pdf. -->
              <BaseButton
                type="button"
                variant="secondary"
                size="sm"
                data-testid="collection-preview-download-pdf"
                @click="downloadPdf"
              >
                Descargar
              </BaseButton>
              <BaseButton
                type="button"
                variant="secondary"
                size="sm"
                data-testid="collection-preview-open-pdf"
                @click="openPdfTab"
              >
                Abrir PDF
              </BaseButton>
            </div>
          </div>
          <embed
            v-if="pdfState === 'ready'"
            :src="pdfUrl"
            type="application/pdf"
            class="flex-1 min-h-0 w-full rounded-xl border border-border-default"
            :class="dragging ? 'pointer-events-none' : ''"
            data-testid="collection-preview-pdf"
          >
          <div
            v-else-if="pdfState === 'loading'"
            class="flex-1 min-h-0 flex items-center justify-center gap-2 rounded-xl border border-border-default text-sm text-text-subtle"
            data-testid="collection-preview-pdf-loading"
          >
            <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            Cargando el documento…
          </div>
          <div
            v-else
            class="flex-1 min-h-0 flex flex-col items-center justify-center gap-1 rounded-xl border border-border-default px-6 text-center"
            data-testid="collection-preview-pdf-error"
          >
            <template v-if="pdfUrl">
              <p class="text-sm font-medium text-text-default">
                No pudimos mostrar la previsualización del PDF.
              </p>
              <p class="text-sm text-text-subtle">
                El documento existe: revísalo con «Descargar» o «Abrir PDF» antes de enviarlo.
              </p>
            </template>
            <p v-else class="text-sm text-danger-strong">
              No se pudo generar el PDF de previsualización.
            </p>
          </div>
        </section>
      </div>

      <!-- Fixed: the send decision never needs scrolling to reach. -->
    </div>
    <template #footer>
      <BaseModalActions v-if="step === 'form'">
        <BaseButton type="button" variant="secondary" @click="close">
          Cancelar
        </BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          :loading="previewing"
          data-testid="collection-form-preview"
        >
          {{ previewing ? 'Generando...' : 'Previsualizar' }}
        </BaseButton>
      </BaseModalActions>
      <BaseModalActions v-else>
        <BaseButton
          type="button"
          variant="secondary"
          data-testid="collection-form-back"
          @click="step = 'form'"
        >
          Volver a editar
        </BaseButton>
        <BaseButton
          type="button"
          variant="primary"
          :disabled="saving"
          data-testid="collection-form-confirm"
          @click="confirmSend"
        >
          {{ saving ? 'Enviando...' : 'Confirmar y enviar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>

  <!-- Stacked: create the expected income without leaving the flow -->
  <IncomeFormModal
    :open="showIncomeForm"
    :saving="store.isUpdating"
    :locked-client="lockedClientForIncome"
    @close="showIncomeForm = false"
    @submit="handleIncomeCreated"
  />
</template>
