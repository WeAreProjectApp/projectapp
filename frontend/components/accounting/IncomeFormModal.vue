<script setup>
import { useId, computed, ref, watch } from 'vue'
import PartnerSplitInput from './PartnerSplitInput.vue'
import VatAmountInput from './VatAmountInput.vue'
import PeriodDateField from './PeriodDateField.vue'
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue'
import ProjectSelect from '~/components/accounting/ProjectSelect.vue'
import ReceivableConfidenceBadge from '~/components/accounting/ReceivableConfidenceBadge.vue'
import ReceivableConfidenceDot from '~/components/accounting/ReceivableConfidenceDot.vue'
import ClientFormFields from '~/components/clients/ClientFormFields.vue'
import { useProposalClientsStore } from '~/stores/proposal_clients'
import { useHostingPeriod } from '~/composables/useHostingPeriod'
import { clientFormPayload, emptyClientForm } from '~/utils/billingCode'
import { formatDate } from '~/utils/formatDate'
import { todayISO } from '~/utils/periodDates'
import { RECEIVABLE_CONFIDENCE_OPTIONS } from '~/utils/receivables'
import { FREQUENCY_OPTIONS } from '~/utils/recurring'

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  saving: { type: Boolean, default: false },
  /**
   * Client fixed by the parent (id + display name). Set when this modal is
   * stacked inside the cuenta-de-cobro flow, where the client was already
   * chosen: a second picker there would be redundant and could contradict it.
   */
  lockedClient: { type: Object, default: null },
  /**
   * Prefill for a form that still creates: duplicating an income opens here
   * with the original's data but no `record`, so saving POSTs a new row
   * instead of editing the one it was copied from.
   */
  seed: { type: Object, default: null },
})

const emit = defineEmits(['close', 'submit', 'project-created'])

const clientsStore = useProposalClientsStore()
const creatingClient = ref(false)
const inlineClientOpen = ref(false)
const inlineClient = ref(emptyClientForm())
const inlineClientErrors = ref({})

const originOptions = [
  { value: 'development', label: 'Desarrollo' },
  { value: 'hosting', label: 'Hosting' },
  { value: 'diagnostic', label: 'Diagnóstico' },
  { value: 'other', label: 'Otro' },
]

const isEdit = computed(() => !!props.record)
const isDuplicate = computed(() => !props.record && !!props.seed)
const title = computed(() => {
  if (isEdit.value) return 'Editar Ingreso'
  return isDuplicate.value ? 'Duplicar Ingreso' : 'Nuevo Ingreso'
})

const kindOptions = [
  { value: 'expected', label: 'Esperado' },
  { value: 'liquid', label: 'Líquido' },
  { value: 'lost', label: 'Perdido' },
]

const destinationOptions = [
  { value: 'partners', label: 'Socios' },
  { value: 'pocket', label: 'Bolsillo ProjectApp' },
]

const ledgerOptions = [
  { value: 'company', label: 'Empresa' },
  { value: 'gustavo', label: 'Personal Gustavo' },
  { value: 'carlos', label: 'Personal Carlos' },
]

function defaultForm() {
  return {
    concept: '',
    kind: 'expected',
    period_date: todayISO(),
    destination: 'partners',
    ledger: 'company',
    client: null,
    project: null,
    client_name: '',
    origin: '',
    is_receivable_candidate: false,
    collection_confidence: '',
    period_start: '',
    period_end: '',
    period_cadence: '',
    total_amount: '',
    vat_rate: 19,
    vat_capture: null,
    gustavo_amount: '',
    carlos_amount: '',
    notes: '',
  }
}

const form = ref(defaultForm())
// Exact day by default; the toggle downgrades to month-only.
const exactDate = ref(true)

const isPersonal = computed(() => form.value.ledger !== 'company')
watch(() => form.value.ledger, (ledger) => {
  if (!props.record && !form.value.vat_capture) form.value.vat_rate = ledger === 'company' ? 19 : 0
})
// Hosting is a service window, not a point payment: the date block swaps to
// start + end + cadence, and the backend derives period_date from the start.
const isHosting = computed(() => form.value.origin === 'hosting')
const forecastApplicable = computed(() => (
  form.value.kind === 'expected' && form.value.ledger === 'company'
))
// A paid expected income keeps its last classification as historical context,
// but cannot be reintroduced into the active forecast from an ordinary edit.
const forecastReadOnly = computed(() => (
  isEdit.value
  && props.record?.kind === 'expected'
  && props.record?.ledger === 'company'
  && props.record?.payment_status === 'paid'
))

const cadenceOptions = FREQUENCY_OPTIONS

const {
  anchorStart,
  anchorSource,
  anchorOriginDate,
  anchorOriginStart,
  anchorOriginEnd,
  previousPeriodEnd,
  beginHydration,
  cycleOptions,
  isCycleActive,
  applyCycle,
  onPeriodEndEdited,
  periodEndError,
  resolveAnchor,
} = useHostingPeriod(form, {
  isHosting,
  isEdit,
  isDuplicate,
  seed: computed(() => props.seed),
})

// Only while the proposed date is untouched: once it changes, the hint would
// be describing a date that is no longer the one the hosting cycle produced.
// A hosting seed lands the proposal on `period_start` (the visible field),
// so the comparison follows it there.
const showsCycleHint = computed(() => {
  if (!isDuplicate.value || props.seed?.period_date_source !== 'hosting_cycle') {
    return false
  }
  const shown = isHosting.value ? form.value.period_start : form.value.period_date
  return shown === props.seed.period_date
})

// Same idea for a duplicate seeded from the income's own recorded window.
const showsPeriodHint = computed(
  () => isDuplicate.value
    && props.seed?.period_date_source === 'income_period'
    && form.value.period_start === props.seed.period_start,
)

const CYCLE_LABELS = { 1: '+1 mes', 3: '+3 meses', 6: '+6 meses', 12: '+1 año' }

function cycleLabel(months) {
  return CYCLE_LABELS[months] ?? `+${months} meses`
}

// Match the field's current granularity: month mode stores 'YYYY-MM', so
// handing it a full date would leave the month input showing nothing.
function cycleValue(option) {
  return exactDate.value ? option.date : option.date.slice(0, 7)
}

function onCycleClick(option) {
  // Outside hosting a shortcut is still just the server's proposed date for a
  // single-date income; the window logic belongs to the composable.
  if (!isHosting.value) {
    form.value.period_date = cycleValue(option)
    periodDateTouched.value = true
    return
  }
  applyCycle(option)
}

function isCycleSelected(option) {
  if (isHosting.value) return isCycleActive(option)
  return !!form.value.period_date && form.value.period_date === cycleValue(option)
}

/**
 * What the operator gains from the periodicity, said where they are choosing
 * it. When the client already has a window on the book, the start says which
 * one this period follows — the reason the dates land where they land.
 */
const cadenceHint = 'Al elegirla se calcula la fecha de fin del período.'

const HOSTING_CYCLE_HINT = 'Siguiente ciclo del hosting. Ajústala si no corresponde.'

const periodDateHint = computed(() => (showsCycleHint.value ? HOSTING_CYCLE_HINT : ''))

/**
 * Where this duplicate's window is counted from, said out loud. Duplicating
 * exists to continue the previous period, so the dates have to be traceable to
 * the record they continue — otherwise they show up alone and the operator has
 * no way to tell a chained date from a guess. Only while duplicating a
 * hosting: creating has no original to point at, and editing is not opening a
 * period at all.
 */
const duplicateAnchorNotice = computed(() => {
  if (!isDuplicate.value || !isHosting.value) return ''
  if (anchorSource.value === 'income_period') {
    return `El ingreso original cubre del ${formatDate(anchorOriginStart.value)}`
      + ` al ${formatDate(anchorOriginEnd.value)}, así que este duplicado`
      + ` arranca el ${formatDate(anchorStart.value)}.`
  }
  if (anchorSource.value === 'hosting_cycle') {
    return 'El ingreso original no tiene período registrado: se cuenta desde su'
      + ` fecha (${formatDate(anchorOriginDate.value)}) con el ciclo del hosting,`
      + ` así que este duplicado arranca el ${formatDate(anchorStart.value)}.`
  }
  if (anchorSource.value === 'original_date') {
    return 'El ingreso original no tiene período registrado: el cálculo parte de'
      + ` su fecha (${formatDate(anchorOriginDate.value)}) y de la periodicidad`
      + ' que elijas.'
  }
  if (anchorSource.value === 'none') {
    // Nothing to chain with, and saying so is the point: an unexplained window
    // opening on today reads exactly like one that continues something.
    return 'El ingreso original no tiene período ni fecha registrada, así que'
      + ' este rango arranca hoy y no encadena con nada.'
  }
  // A draft from before the anchor travelled. Better silent than asserting a
  // provenance nobody sent.
  return ''
})

/**
 * The origin travels with the duplicate; when the original has none, what
 * travels is the blank. Saying so is the whole point: an empty Origen that
 * explains itself is a field left to fill, and one that does not is
 * indistinguishable from a copy that failed — which is exactly how it was read
 * when this was reported. Most of the book predates the field, so this is the
 * common case, not the exception.
 *
 * Mutually exclusive with `duplicateAnchorNotice`, which needs origin
 * `hosting`: the two never stack.
 */
const duplicateOriginNotice = computed(() => (
  isDuplicate.value && !form.value.origin
    ? 'El ingreso original no tiene origen registrado: elige la línea de negocio,'
      + ' porque de ella depende el bloque de fechas.'
    : ''
))

/**
 * Origen decides which date block the form shows, so leaving it unset is not a
 * blank field but an unanswered question. `BaseSegmented` is not a native
 * control and cannot carry `required`, so the refusal lives here — held back
 * until the first attempt, since a form that opens already complaining teaches
 * the operator to ignore it.
 */
const submitAttempted = ref(false)

const originError = computed(() => (
  submitAttempted.value && !form.value.origin
    ? 'Elige la línea de negocio del ingreso.'
    : ''
))

const periodStartHint = computed(() => {
  if (showsPeriodHint.value) {
    return 'Siguiente período según la periodicidad registrada. Ajústalo si no corresponde.'
  }
  if (showsCycleHint.value) return HOSTING_CYCLE_HINT
  if (previousPeriodEnd.value) {
    return `El período anterior terminó el ${formatDate(previousPeriodEnd.value)}.`
  }
  return ''
})

/**
 * A create prefills the single date with today, which is boilerplate rather
 * than an answer. Carrying that into the window would hide the period the
 * client's last charge actually points to, so only a date the operator (or a
 * record) put there counts as written.
 */
const periodDateTouched = ref(false)

/**
 * Requisito of the origin switch: what was already written survives. Only the
 * date block changes shape, seeding the incoming mode's date from the
 * outgoing one so the operator never re-types it.
 */
function onOriginChange() {
  if (isHosting.value && !form.value.period_start && periodDateTouched.value) {
    form.value.period_start = form.value.period_date
  } else if (!isHosting.value && !form.value.period_date && form.value.period_start) {
    form.value.period_date = form.value.period_start
  }
}

/**
 * Copy the fields the form owns out of an existing income — the record being
 * edited, or the draft a duplicate was seeded with. A duplicate may arrive
 * with no `period_date` (nothing to propose): it stays empty and the field's
 * `required` forces a date before saving.
 */
function applyRecord(source) {
  // A duplicate is a new collection event. Operational forecast state never
  // travels from the occurrence it copies, even if a future draft payload
  // starts exposing those fields.
  const resetForecast = isDuplicate.value
  form.value = {
    concept: source.concept ?? '',
    kind: source.kind ?? 'expected',
    period_date: source.period_date ?? '',
    destination: source.destination ?? 'partners',
    ledger: source.ledger ?? 'company',
    client: source.client ?? null,
    project: source.project ?? null,
    client_name: source.client_name ?? '',
    origin: source.origin ?? '',
    is_receivable_candidate: resetForecast
      ? false
      : Boolean(source.is_receivable_candidate),
    collection_confidence: resetForecast
      ? ''
      : (source.collection_confidence ?? ''),
    period_start: source.period_start ?? '',
    period_end: source.period_end ?? '',
    period_cadence: source.period_cadence ?? '',
    total_amount: source.total_amount ?? '',
        vat_rate: source.vat_rate ?? null,
        vat_capture: null,
    gustavo_amount: source.gustavo_amount ?? '',
    carlos_amount: source.carlos_amount ?? '',
    notes: source.notes ?? '',
  }
  // A legacy hosting source proposes a plain date (hosting_cycle lookup, or
  // a record predating the window): that date is the start of the window the
  // form now asks for, so it lands there instead of getting lost.
  if (form.value.origin === 'hosting' && !form.value.period_start) {
    form.value.period_start = form.value.period_date ?? ''
  }
}

watch(
  () => [props.open, props.record, props.seed],
  () => {
    if (!props.open) return
    // Prefill from the raw period_date — `period` is 'YYYY-MM' and would
    // silently reset the day to the 1st on every edit. Edits always open
    // in full-date mode showing the stored day (01 for month-only
    // records, whose real day was never captured); the toggle still
    // downgrades when only the month is known.
    exactDate.value = true
    // Prefilling writes start, end and cadence at once: the period watchers
    // must not treat that batch as the operator choosing a cadence and
    // recompute an end the record already stated.
    beginHydration()
    // Every opening starts without a refusal on screen: the previous one
    // belonged to the record that was being saved, not to this one.
    submitAttempted.value = false
    const source = props.record || props.seed
    // A stored date is an answer, not boilerplate.
    periodDateTouched.value = !!source
    if (source) applyRecord(source)
    else form.value = defaultForm()
    inlineClientOpen.value = false
    inlineClientErrors.value = {}
    if (props.lockedClient) {
      form.value.client = props.lockedClient.id ?? null
      form.value.client_name = props.lockedClient.name ?? ''
    }
    resolveAnchor()
  },
  { immediate: true },
)

// The antecedent is the client's, so it is re-resolved whenever the form
// changes whose it is — including the project, which narrows the lookup when
// one client holds several hostings.
watch(
  () => [form.value.client, form.value.project, isHosting.value],
  () => {
    if (!props.open) return
    resolveAnchor()
  },
)

function onClientSelect(client) {
  form.value.client_name = client?.name || ''
}

function onCreateNewClient(typedName) {
  inlineClientOpen.value = true
  inlineClient.value = { ...emptyClientForm(), name: typedName || '' }
  inlineClientErrors.value = {}
}

function clearInlineClientError(field) {
  if (!inlineClientErrors.value[field]) return
  const next = { ...inlineClientErrors.value }
  delete next[field]
  inlineClientErrors.value = next
}

async function createInlineClient() {
  inlineClientErrors.value = {}
  if (!inlineClient.value.name.trim()) {
    inlineClientErrors.value = { name: 'Escribe el nombre del cliente.' }
    return
  }
  creatingClient.value = true
  const result = await clientsStore.createClient(clientFormPayload(inlineClient.value))
  creatingClient.value = false
  if (result.success && result.data?.id) {
    inlineClientOpen.value = false
    form.value.client = result.data.id
    form.value.client_name = result.data.name || ''
    return
  }
  inlineClientErrors.value = Object.fromEntries(
    Object.entries(result.errors || {})
      .filter(([field]) => !['message', 'error'].includes(field))
      .map(([field, messages]) => [
        field,
        Array.isArray(messages) ? messages.join(' ') : String(messages || ''),
      ]),
  )
}

function onSubmit() {
  submitAttempted.value = true
  // The serializer rejects both too, but a 400 round trip to say what the form
  // already knows is a worse way to find out.
  if (originError.value || periodEndError.value) return
  const payload = {
    concept: form.value.concept,
    kind: form.value.kind,
    // Pocket is liquid-and-company-only server-side. Deriving here (the
    // same condition that shows the Destino field) instead of syncing via
    // watches keeps the user's pocket choice across a liquid→lost→liquid
    // round-trip.
    destination:
      form.value.kind === 'liquid' && !isPersonal.value
        ? form.value.destination
        : 'partners',
    ledger: form.value.ledger,
    total_amount: form.value.total_amount,
    vat_rate: form.value.vat_rate,
    // Always sent, null included: that is what lets an edit UNLINK a client
    // (same reason `notes` is always sent).
    client: form.value.client,
    // Always sent, null included: that is what lets an edit unlink it.
    project: form.value.project,
    origin: form.value.origin,
  }
  if (isHosting.value) {
    // The backend derives period_date from the start of the window; sending
    // both would just be two chances to disagree.
    payload.period_start = form.value.period_start
    payload.period_end = form.value.period_end
    payload.period_cadence = form.value.period_cadence
  } else {
    payload.period_date = form.value.period_date
    // Nulls on purpose, like `client`: switching an edit away from hosting
    // has to clear the window it no longer covers.
    payload.period_start = null
    payload.period_end = null
    payload.period_cadence = ''
  }
  if (form.value.vat_capture) {
    delete payload.total_amount
    Object.assign(payload, form.value.vat_capture)
  }
  if (!isPersonal.value) {
    payload.gustavo_amount = form.value.gustavo_amount
    payload.carlos_amount = form.value.carlos_amount
  }
  // When the shape stops being eligible these fields are omitted: the
  // serializer owns automatic deactivation and preserves the stored colour.
  // Paid records are likewise read-only, so a routine edit cannot replay an
  // old confidence value as a new assignment.
  if (forecastApplicable.value && !forecastReadOnly.value) {
    payload.is_receivable_candidate = Boolean(form.value.is_receivable_candidate)
    payload.collection_confidence = form.value.collection_confidence || ''
  }
  payload.notes = form.value.notes
  emit('submit', payload)
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="form-wide" title-id="income-form-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="income-form-title" class="text-lg font-bold text-text-default">{{ title }}</h3>
    </div>
    <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
      <BaseFormField label="Concepto" required>
        <BaseInput v-model="form.concept" data-testid="income-form-concept" required />
      </BaseFormField>

      <BaseFormField label="Cliente">
        <div
          v-if="lockedClient"
          class="rounded-xl border border-border-default bg-surface-raised px-3 py-2.5 text-sm text-text-default"
          data-testid="income-form-client-locked"
        >
          {{ form.client_name || lockedClient.name }}
        </div>
        <ClientAutocomplete
          v-else
          v-model="form.client"
          :initial-label="form.client_name"
          test-id="income-form-client"
          allow-create
          @select="onClientSelect"
          @create-new="onCreateNewClient"
        />
      </BaseFormField>

      <ProjectSelect
        v-model="form.project"
        :client-profile-id="form.client"
        :client-label="form.client_name || lockedClient?.name || ''"
        :auto-select-single="!isEdit"
        testid="income-form-project"
        @created="emit('project-created', $event)"
      />

      <!-- Inline client creation: the module de clientes without leaving the form -->
      <div
        v-if="inlineClientOpen"
        class="rounded-xl border border-border-default bg-surface-raised p-4 space-y-3"
        data-testid="income-form-inline-client"
      >
        <p class="text-sm font-medium text-text-default">Crear cliente nuevo</p>
        <ClientFormFields
          v-model="inlineClient"
          :errors="inlineClientErrors"
          testid-prefix="income-form-inline-client"
          dense
          @clear-error="clearInlineClientError"
        />
        <div class="flex justify-end gap-2">
          <BaseButton type="button" variant="secondary" size="sm" @click="inlineClientOpen = false">
            Cancelar
          </BaseButton>
          <BaseButton
            type="button"
            variant="primary"
            size="sm"
            :disabled="creatingClient"
            data-testid="income-form-inline-client-save"
            @click="createInlineClient"
          >
            {{ creatingClient ? 'Creando...' : 'Crear cliente' }}
          </BaseButton>
        </div>
      </div>

      <BaseFormField
        label="Origen"
        required
        hint="Línea de negocio que genera el ingreso."
        :error="originError"
      >
        <BaseSegmented
          v-model="form.origin"
          :options="originOptions"
          full-width
          data-testid="income-form-origin"
          @update:model-value="onOriginChange"
        />
      </BaseFormField>

      <!-- Right under the field it is about, and above the date block it
           explains the shape of. -->
      <BaseAlert
        v-if="duplicateOriginNotice"
        variant="info"
        data-testid="income-form-origin-notice"
      >
        {{ duplicateOriginNotice }}
      </BaseAlert>

      <!-- Above the block it explains, and outside the rows: a wrapper inside
           a BaseFormRow would break its subgrid alignment. -->
      <BaseAlert
        v-if="duplicateAnchorNotice"
        variant="info"
        data-testid="income-form-anchor-notice"
      >
        {{ duplicateAnchorNotice }}
      </BaseAlert>

      <!-- How often first, then the window it produces: the periodicity sits
           beside Tipo because it is chosen before the dates it proposes. -->
      <BaseFormRow
        :cols="2"
        :gap="4"
        :help="isHosting ? cadenceHint : periodDateHint"
        :help-testid="isHosting ? undefined : 'income-form-period-hint'"
      >
        <BaseFormField label="Tipo" required>
          <BaseSegmented v-model="form.kind" :options="kindOptions" full-width />
        </BaseFormField>
        <PeriodDateField
          v-if="!isHosting"
          v-model="form.period_date"
          v-model:exact="exactDate"
          label-exact="Fecha"
          label-month="Mes"
          required
          input-testid="income-form-period"
          toggle-testid="income-form-exact-date"
          @update:model-value="periodDateTouched = true"
        />
        <BaseFormField v-else label="Periodicidad" required>
          <BaseSelect
            v-model="form.period_cadence"
            :options="cadenceOptions"
            placeholder="Elegir periodicidad"
            required
            data-testid="income-form-period-cadence"
          />
        </BaseFormField>
      </BaseFormRow>

      <!-- The window a hosting income covers, read left to right. The end
           proposes itself from start + cadence and stays editable; writing it
           by hand is what turns the periodicity into `Personalizada`. -->
      <BaseFormRow
        v-if="isHosting"
        :cols="2"
        :gap="4"
        :help="periodStartHint"
        help-testid="income-form-period-hint"
      >
        <PeriodDateField
          v-model="form.period_start"
          v-model:exact="exactDate"
          label-exact="Inicio del período"
          label-month="Mes de inicio"
          required
          input-testid="income-form-period-start"
          toggle-testid="income-form-exact-date"
        />
        <BaseFormField label="Fin del período" required :error="periodEndError">
          <BaseInput
            v-model="form.period_end"
            type="date"
            :error="!!periodEndError"
            required
            data-testid="income-form-period-end"
            @update:model-value="onPeriodEndEdited"
          />
        </BaseFormField>
      </BaseFormRow>

      <div v-if="cycleOptions.length" class="-mt-1">
        <p class="mb-1.5 text-xs text-text-subtle">Siguiente período:</p>
        <div class="flex flex-wrap gap-1.5" data-testid="income-form-cycles">
          <BaseButton
            v-for="option in cycleOptions"
            :key="option.months"
            type="button"
            size="sm"
            :variant="isCycleSelected(option) ? 'primary' : 'secondary'"
            :aria-pressed="isCycleSelected(option)"
            :data-testid="`income-form-cycle-${option.months}`"
            @click="onCycleClick(option)"
          >
            {{ cycleLabel(option.months) }}
          </BaseButton>
        </div>
      </div>

      <BaseFormField label="Contabilidad">
        <BaseSegmented v-model="form.ledger" :options="ledgerOptions" full-width />
      </BaseFormField>

      <section
        v-if="forecastApplicable"
        class="rounded-xl border border-border-muted bg-surface-raised p-4"
        data-testid="income-form-receivable"
      >
        <div class="mb-3">
          <h4 class="text-sm font-semibold text-text-default">Previsión de cobro</h4>
          <p class="mt-1 text-xs text-text-muted">
            El nivel y el interruptor son independientes. Elegir un color no activa la previsión.
          </p>
        </div>

        <div v-if="!forecastReadOnly" class="grid gap-4 panel-portrait:grid-cols-2">
          <BaseFormField label="Nivel de cobro" for="income-form-confidence">
            <div class="flex items-center gap-3">
              <ReceivableConfidenceDot :confidence="form.collection_confidence" />
              <BaseSelect
                id="income-form-confidence"
                v-model="form.collection_confidence"
                :options="RECEIVABLE_CONFIDENCE_OPTIONS"
                class="min-w-0 flex-1"
                data-testid="income-form-confidence"
              />
            </div>
          </BaseFormField>
          <BaseFormField label="Incluir en la previsión">
            <div class="flex min-h-10 items-center gap-3">
              <BaseToggle
                v-model="form.is_receivable_candidate"
                aria-label="Incluir ingreso en pendientes por cobrar"
                data-testid="income-form-candidate"
              />
              <span class="text-sm text-text-muted">
                {{ form.is_receivable_candidate ? 'Interruptor activado' : 'Interruptor desactivado' }}
              </span>
            </div>
          </BaseFormField>
        </div>

        <div v-else class="flex flex-wrap items-center gap-2" data-testid="income-form-receivable-readonly">
          <ReceivableConfidenceBadge :confidence="form.collection_confidence" />
          <span class="text-xs text-text-muted">Cobrado · previsión desactivada</span>
        </div>
      </section>

      <BaseFormField v-if="form.kind === 'liquid' && !isPersonal" label="Destino">
        <BaseSegmented v-model="form.destination" :options="destinationOptions" full-width />
      </BaseFormField>

      <PartnerSplitInput
        v-if="!isPersonal"
        show-vat
        v-model:vat-rate="form.vat_rate"
        :vat-reset-key="open"
        @vat-capture="form.vat_capture = $event"
        v-model:total="form.total_amount"
        v-model:gustavoAmount="form.gustavo_amount"
        v-model:carlosAmount="form.carlos_amount"
      />

      <BaseFormField v-else label="Valor" required>
        <VatAmountInput v-model="form.total_amount" v-model:rate="form.vat_rate" :reset-key="open" @capture="form.vat_capture = $event" />
      </BaseFormField>

      <BaseFormField label="Notas">
        <BaseTextarea v-model="form.notes" :rows="3" />
      </BaseFormField>

    </form>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="secondary" @click="emit('close')">
          Cancelar
        </BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          :disabled="saving"
          data-testid="income-form-submit"
        >
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
