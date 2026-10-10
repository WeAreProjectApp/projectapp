<script setup>
import { useId, computed, ref, watch } from 'vue'
import PartnerSplitInput from './PartnerSplitInput.vue'
import PeriodDateField from './PeriodDateField.vue'
import { useHostingPeriod } from '~/composables/useHostingPeriod'
import { DEDUCTION_TYPE_OPTIONS as deductionOptions } from '~/utils/accountingDeductions'
import { formatMoney } from '~/utils/formatMoney'
import { todayISO } from '~/utils/periodDates'
import { FREQUENCY_OPTIONS as cadenceOptions } from '~/utils/recurring'
import { settlementBlockedReason } from '~/utils/incomeSettlement'

const props = defineProps({
  open: { type: Boolean, default: false },
  /** The expected income being settled. */
  record: { type: Object, default: null },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'submit'])

const destinationOptions = [
  { value: 'pocket', label: 'Bolsillo ProjectApp' },
  { value: 'partners', label: 'Socios' },
]

const form = ref(defaultForm())
const deductions = ref([])
const followUps = ref([])
const deductionsOpen = ref(false)
const followUpsOpen = ref(false)
// The exact payment day is the default; the toggle downgrades to
// month-only when only the month is known.
const exactDate = ref(true)

function defaultForm() {
  return {
    concept: '',
    period_date: '',
    destination: 'pocket',
    total_amount: '',
    gustavo_amount: '',
    carlos_amount: '',
    notes: '',
    // Only ever filled for a hosting charge that never recorded its window;
    // they travel as `period` and describe the EXPECTED income, not this
    // payment (see the covered-period block in the write serializer).
    period_start: '',
    period_end: '',
    period_cadence: '',
  }
}

const isPersonal = computed(() => props.record?.ledger !== 'company')

/**
 * The window a hosting charge covers, asked for here when the charge never
 * recorded one — the gap shows up while liquidating, so it gets resolved
 * while liquidating instead of sending the operator to another screen.
 *
 * It is a courtesy and never a condition: leaving the block empty settles
 * exactly the same. Liquidar registers that the money came in; the period
 * describes what the charge covers, and holding the money for a descriptive
 * field is what broke this flow in the first place.
 */
const needsPeriod = computed(
  () => props.record?.origin === 'hosting' && !props.record?.period_start,
)

const {
  anchorStart,
  cycleOptions,
  isCycleActive,
  applyCycle,
  onPeriodEndEdited,
  periodEndError,
} = useHostingPeriod(form, {
  isHosting: needsPeriod,
  // `isEdit: false` is what keeps the duration shortcuts on screen, and no
  // settlement is ever a duplicate. `resolveAnchor` is deliberately never
  // called: it looks up where a client's NEXT window opens, and this block
  // completes one that already happened.
  isEdit: computed(() => false),
  isDuplicate: computed(() => false),
  seed: computed(() => null),
})

// Duration, not increment: the same four cadences the income form offers as
// "+3 meses" for the period that FOLLOWS read as the length of this one.
const CYCLE_LABELS = { 1: '1 mes', 3: '3 meses', 6: '6 meses', 12: '1 año' }

const cycleLabel = (months) => CYCLE_LABELS[months] ?? `${months} meses`

/** The start we proposed. Sitting there untouched, it is not an answer. */
const proposedPeriodStart = computed(() => props.record?.period_date ?? '')

// Same pristine idea the deduction and follow-up rows use: a value the modal
// filled in by itself must not turn an optional block into a required one.
const periodTouched = computed(() => Boolean(
  form.value.period_end
  || form.value.period_cadence
  || (
    form.value.period_start
    && form.value.period_start !== proposedPeriodStart.value
  ),
))

const periodComplete = computed(() => Boolean(
  form.value.period_start
  && form.value.period_end
  && form.value.period_cadence
  && !periodEndError.value,
))

/** Started and left half-written — the one state the block does block on. */
const periodIncomplete = computed(
  () => needsPeriod.value && periodTouched.value && !periodComplete.value,
)

const pending = computed(() => Number(props.record?.pending_amount ?? 0))

const money = (value) => formatMoney(Number(value ?? 0), 'COP')

const sumAmounts = (rows) =>
  rows.reduce((total, row) => total + Number(row.amount || 0), 0)

/** What was invoiced but did not arrive with this payment. */
const shortfall = computed(() =>
  Math.max(pending.value - Number(form.value.total_amount || 0), 0),
)
// An auto-added row the user never touched must not block the submit nor
// reach the payload — otherwise "leave the rest pending" (no allocation)
// would require deleting the row the auto-expand just created.
const isPristineDeduction = (row) =>
  !(Number(row.amount) > 0) && !row.detail.trim() && row.type === ''

const activeDeductions = computed(() =>
  deductions.value.filter((row) => !isPristineDeduction(row)),
)

const defaultFollowUpConcept = computed(
  () => `${props.record?.concept ?? ''} - saldo`,
)
// Same pristine idea for follow-ups: the row auto-added on expand keeps its
// prefilled concept, so it must not block a submit from inside a collapsed
// group the user never filled.
const isPristineFollowUp = (row) =>
  row.amount == null
  && !row.period_date
  && row.concept === defaultFollowUpConcept.value

const activeFollowUps = computed(() =>
  followUps.value.filter((row) => !isPristineFollowUp(row)),
)

const allocated = computed(
  () => sumAmounts(activeDeductions.value) + sumAmounts(activeFollowUps.value),
)
/** Left over after allocating; stays pending on the expected income. */
const unassigned = computed(() => shortfall.value - allocated.value)
const overAllocated = computed(() => unassigned.value < 0)

// The row whose amount was edited last: when the sum overflows, that input
// is the one flagged. Object identity survives row removal (splice).
const overSource = ref(null)

function onLineAmountInput(row, value) {
  row.amount = value
  overSource.value = row
}

const amountError = (row) => {
  if (row.amount == null || row.amount === '') return 'Ingresa el monto.'
  if (!(Number(row.amount) > 0)) return 'El monto debe ser mayor a cero.'
  if (overAllocated.value && row === overSource.value) {
    return `Con este monto la suma supera el saldo por ${money(-unassigned.value)}.`
  }
  return null
}

const deductionErrors = computed(() => deductions.value.map((row) => {
  if (isPristineDeduction(row)) return null
  if (!row.type) return { field: 'type', message: 'Selecciona el concepto.' }
  const amount = amountError(row)
  if (amount) return { field: 'amount', message: amount }
  if (row.type === 'other' && !row.detail.trim()) {
    return { field: 'detail', message: 'Describe el concepto.' }
  }
  return null
}))

const followUpErrors = computed(() => followUps.value.map((row) => {
  if (isPristineFollowUp(row)) return null
  if (!row.concept.trim()) return { field: 'concept', message: 'Escribe el concepto.' }
  if (!row.period_date) return { field: 'period', message: 'Indica el mes.' }
  const amount = amountError(row)
  if (amount) return { field: 'amount', message: amount }
  return null
}))

const hasIncompleteRow = computed(
  () => deductionErrors.value.some(Boolean) || followUpErrors.value.some(Boolean),
)

const canSubmit = computed(
  () => !settlementBlockedReason(props.record) && !overAllocated.value && !hasIncompleteRow.value && !periodIncomplete.value,
)

/** Why the submit is blocked — shown next to the disabled button. */
const submitBlockReason = computed(() => {
  const billingReason = settlementBlockedReason(props.record)
  if (billingReason) return billingReason
  if (canSubmit.value) return ''
  if (overAllocated.value) {
    return `La distribución supera el saldo por resolver por ${money(-unassigned.value)}.`
  }
  if (periodIncomplete.value) {
    return periodEndError.value
      || 'Completa el período que cubre el cobro, o déjalo vacío.'
  }
  if (deductionErrors.value.some(Boolean)) {
    return 'Hay líneas de gasto incompletas: revisa concepto y monto.'
  }
  return 'Hay líneas de ingreso esperado incompletas.'
})

// Status badge next to the section total. Each asserted phrase lives whole
// inside one element (badge or clause) — split text breaks substring checks.
const remainingState = computed(() => {
  if (overAllocated.value) {
    return {
      variant: 'danger',
      badge: `Te pasaste por ${money(-unassigned.value)}`,
      clause: 'del saldo disponible.',
    }
  }
  if (unassigned.value > 0) {
    return {
      variant: 'info',
      badge: `Sin asignar: ${money(unassigned.value)}`,
      clause: 'quedará pendiente en este ingreso.',
    }
  }
  return {
    variant: 'success',
    badge: 'Saldo resuelto por completo',
    clause: 'el ingreso esperado queda cerrado.',
  }
})

function addDeduction() {
  // No preselected concept: the choice must be explicit and readable.
  deductions.value.push({ type: '', detail: '', amount: null })
}

function addFollowUp() {
  followUps.value.push({
    concept: defaultFollowUpConcept.value,
    period_date: '',
    amount: null,
  })
}

// Opening an empty section with no row to fill reads as broken.
watch(deductionsOpen, (open) => {
  if (open && !deductions.value.length) addDeduction()
})
watch(followUpsOpen, (open) => {
  if (open && !followUps.value.length) addFollowUp()
})

// Reveal the resolution path the moment a shortfall appears — the section
// used to materialize with both groups collapsed, which read as "the
// option is not there". One-shot per modal open, so a user who collapses
// the group and keeps editing the amount stays in control.
const autoExpanded = ref(false)
watch(shortfall, (value) => {
  if (value > 0 && !autoExpanded.value) {
    autoExpanded.value = true
    deductionsOpen.value = true
  }
})

watch(
  () => [props.open, props.record],
  () => {
    if (!props.open || !props.record) return
    exactDate.value = true
    deductions.value = []
    followUps.value = []
    deductionsOpen.value = false
    followUpsOpen.value = false
    autoExpanded.value = false
    overSource.value = null
    // The window opens on the charge's own date — the same reading the backend
    // calls `original_date` when it duplicates an income with no window
    // recorded. Set before the form is replaced, so the composable's watchers
    // already have their anchor when the fields land.
    anchorStart.value = props.record.period_date ?? ''
    form.value = {
      ...defaultForm(),
      concept: props.record.concept ?? '',
      // Proposed, not imposed: the operator can move it, and the end follows
      // from whatever periodicity they pick.
      period_start: needsPeriod.value ? (props.record.period_date ?? '') : '',
      // Liquidating records a payment that just happened, so today beats
      // the expected period (which is exactly the stale value).
      period_date: todayISO(),
      // Default to what is still owed, not the full projection: the whole
      // point of liquidating is that they often pay late and short. The
      // partner split starts empty and PartnerSplitInput's auto mode splits
      // this amount as it mounts, so the settlement sends the split on screen.
      total_amount: props.record.pending_amount ?? props.record.total_amount,
    }
  },
  { immediate: true },
)

function onSubmit() {
  if (!canSubmit.value) return
  // A cleared BaseCurrencyInput emits null; the server expects 0 for a
  // residual-only settlement (nothing received, shortfall fully allocated).
  const amount = form.value.total_amount
  const payload = {
    concept: form.value.concept,
    period_date: form.value.period_date,
    destination: form.value.destination,
    total_amount: amount === '' || amount == null ? 0 : amount,
    // Empty arrays make the backend behave exactly like a plain liquidation.
    deductions: activeDeductions.value.map((row) => ({
      type: row.type,
      detail: row.type === 'other' ? row.detail.trim() : '',
      amount: row.amount,
    })),
    expected_incomes: activeFollowUps.value.map((row) => ({
      concept: row.concept.trim(),
      period_date: row.period_date,
      amount: row.amount,
    })),
  }
  const { gustavo_amount, carlos_amount } = form.value
  if (!isPersonal.value && gustavo_amount !== '' && carlos_amount !== '') {
    payload.gustavo_amount = gustavo_amount
    payload.carlos_amount = carlos_amount
  }
  // Absent unless the block was completed: the backend applies it to the
  // expected income, and its absence is an ordinary liquidation.
  if (needsPeriod.value && periodComplete.value) {
    payload.period = {
      period_start: form.value.period_start,
      period_end: form.value.period_end,
      period_cadence: form.value.period_cadence,
    }
  }
  payload.notes = form.value.notes
  emit('submit', payload)
}

const modalFormId = useId();
</script>

<template>
  <BaseModal
    :model-value="open"
    kind="form-wide"
    title-id="income-liquidate-title"
    @close="emit('close')"
  >
    <div class="px-6 pt-6 pb-2">
      <h3 id="income-liquidate-title" class="text-lg font-bold text-text-default">
        Liquidar ingreso esperado
      </h3>
      <p v-if="record" class="text-sm text-text-subtle mt-1">
        Se registrará un ingreso líquido nuevo enlazado a
        <span class="font-medium text-text-default">{{ record.concept }}</span>
        ({{ record.period_label }}, {{ money(record.total_amount) }}). El ingreso
        esperado se conserva.
      </p>
    </div>

    <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
      <div
        v-if="record"
        class="rounded-lg bg-surface-raised px-4 py-3 text-sm text-text-muted"
        data-testid="income-liquidate-pending"
      >
        Pendiente por cobrar:
        <span class="font-medium text-text-default tabular-nums">
          {{ money(pending) }}
        </span>
      </div>

      <p
        v-if="record && shortfall <= 0"
        class="text-xs text-text-subtle"
        data-testid="income-liquidate-shortfall-hint"
      >
        ¿Recibiste menos? Escribe el monto real: la diferencia podrás
        registrarla como deducción (comisión o retención) o como un nuevo
        ingreso esperado.
      </p>

      <BaseFormField label="Concepto" required>
        <BaseInput v-model="form.concept" required />
      </BaseFormField>

      <BaseFormRow :cols="isPersonal ? 1 : 2" :gap="3">
        <PeriodDateField
          v-model="form.period_date"
          v-model:exact="exactDate"
          label-exact="Fecha en que se pagó"
          label-month="Mes en que se pagó"
          toggle-label="Registrar el día exacto de pago"
          required
          input-testid="income-liquidate-period"
          toggle-testid="income-liquidate-exact-date"
        />

        <BaseFormField v-if="!isPersonal" label="Destino">
          <BaseSegmented
            v-model="form.destination"
            :options="destinationOptions"
            full-width
          />
        </BaseFormField>
      </BaseFormRow>

      <PartnerSplitInput
        v-if="!isPersonal"
        compact
        v-model:total="form.total_amount"
        v-model:gustavoAmount="form.gustavo_amount"
        v-model:carlosAmount="form.carlos_amount"
      />

      <BaseFormField v-else label="Valor pagado" required>
        <BaseCurrencyInput v-model="form.total_amount" required />
      </BaseFormField>

      <!-- The window this hosting charge covers, when it never recorded one.
           Optional by design: an untouched block settles exactly the same. -->
      <section
        v-if="needsPeriod"
        class="rounded-lg border border-border-muted p-4 space-y-3"
        data-testid="income-liquidate-period-block"
      >
        <div>
          <h4 class="text-sm font-medium text-text-default">
            Período que cubre este cobro
          </h4>
          <p class="mt-0.5 text-xs text-text-subtle">
            Este hosting no tiene período registrado. Complétalo si lo sabes:
            si lo dejas vacío, la liquidación se registra igual.
          </p>
        </div>

        <BaseFormRow :cols="3" :gap="3">
          <BaseFormField
          label="Periodicidad"
          hint="Al elegirla se calcula la fecha de fin del período."
        >
          <BaseSelect
            v-model="form.period_cadence"
            :options="cadenceOptions"
            placeholder="Elegir periodicidad"
            data-testid="income-liquidate-period-cadence"
          />
        </BaseFormField>

          <BaseFormField label="Inicio del período">
            <BaseInput
              v-model="form.period_start"
              type="date"
              data-testid="income-liquidate-period-start"
            />
          </BaseFormField>
          <BaseFormField label="Fin del período" :error="periodEndError">
            <BaseInput
              v-model="form.period_end"
              type="date"
              :error="!!periodEndError"
              data-testid="income-liquidate-period-end"
              @update:model-value="onPeriodEndEdited"
            />
          </BaseFormField>
        </BaseFormRow>

        <div v-if="cycleOptions.length">
          <p class="mb-1.5 text-xs text-text-subtle">Duración del período:</p>
          <div class="flex flex-wrap gap-1.5" data-testid="income-liquidate-cycles">
            <BaseButton
              v-for="option in cycleOptions"
              :key="option.months"
              type="button"
              size="sm"
              :variant="isCycleActive(option) ? 'primary' : 'secondary'"
              :aria-pressed="isCycleActive(option)"
              :data-testid="`income-liquidate-cycle-${option.months}`"
              @click="applyCycle(option)"
            >
              {{ cycleLabel(option.months) }}
            </BaseButton>
          </div>
        </div>
      </section>

      <!-- Shortfall: the money that was invoiced but did not arrive. -->
      <section
        v-if="shortfall > 0"
        class="rounded-lg border border-border-muted p-4 space-y-3"
        data-testid="income-liquidate-shortfall"
      >
        <div class="flex items-baseline justify-between gap-3">
          <h4 class="text-sm font-medium text-text-default">Saldo por resolver</h4>
          <span class="text-sm font-medium text-text-default tabular-nums">
            {{ money(shortfall) }}
          </span>
        </div>
        <div
          class="flex flex-wrap items-center gap-x-2 gap-y-1"
          data-testid="income-liquidate-remaining"
        >
          <BaseBadge :variant="remainingState.variant" class="tabular-nums">
            {{ remainingState.badge }}
          </BaseBadge>
          <span class="text-xs text-text-subtle">{{ remainingState.clause }}</span>
        </div>
        <p class="text-xs text-text-subtle">
          Si el faltante fue una comisión o una retención, regístralo como gasto.
          Si sí lo vas a cobrar después, crea un ingreso esperado nuevo.
        </p>

        <!-- Deduction rows -->
        <button
          type="button"
          class="flex w-full items-center gap-2 text-sm font-medium text-text-default hover:text-text-brand transition-colors"
          :aria-expanded="deductionsOpen"
          aria-controls="liquidate-deductions"
          data-testid="income-liquidate-deductions-toggle"
          @click="deductionsOpen = !deductionsOpen"
        >
          <BaseActionIcon :action="deductionsOpen ? 'collapse' : 'expand'" class="text-text-subtle" />
          No es un cobro pendiente, es un gasto
        </button>
        <BaseCollapse id="liquidate-deductions" :open="deductionsOpen">
          <div class="space-y-2 pt-1">
            <div
              v-for="(row, index) in deductions"
              :key="`deduction-${index}`"
              class="space-y-2 rounded-lg bg-surface-raised p-3"
              :data-testid="`income-liquidate-deduction-${index}`"
            >
              <!-- Grid, not flex: the base inputs are w-full and would fight
                   fallthrough width classes; the tracks own the split instead.
                   Single column below sm so nothing gets crushed. -->
              <div class="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_9rem_auto] gap-2 items-start">
                <BaseSelect
                  v-model="row.type"
                  :options="deductionOptions"
                  placeholder="Seleccionar concepto"
                  :error="deductionErrors[index]?.field === 'type'"
                  aria-label="Concepto del gasto"
                  :data-testid="`deduction-type-${index}`"
                />
                <BaseCurrencyInput
                  :model-value="row.amount"
                  :suggestion="Math.max(unassigned, 0)"
                  :error="deductionErrors[index]?.field === 'amount'"
                  aria-label="Monto del gasto"
                  :data-testid="`deduction-amount-${index}`"
                  @update:model-value="onLineAmountInput(row, $event)"
                />
                <BaseButton
                  type="button"
                  variant="ghost"
                  size="sm"
                  class="justify-self-start sm:justify-self-auto"
                  aria-label="Quitar gasto"
                  @click="deductions.splice(index, 1)"
                >
                  Quitar
                </BaseButton>
              </div>
              <BaseInput
                v-if="row.type === 'other'"
                v-model="row.detail"
                placeholder="¿Cuál concepto?"
                :error="deductionErrors[index]?.field === 'detail'"
                aria-label="Concepto del gasto"
                :data-testid="`deduction-detail-${index}`"
              />
              <p
                v-if="deductionErrors[index]"
                class="text-xs text-danger-strong"
                :data-testid="`deduction-error-${index}`"
              >
                {{ deductionErrors[index].message }}
              </p>
            </div>
            <BaseButton
              type="button"
              variant="secondary"
              size="sm"
              data-testid="income-liquidate-add-deduction"
              @click="addDeduction"
            >
              Agregar gasto
            </BaseButton>
          </div>
        </BaseCollapse>

        <!-- Follow-up expected incomes -->
        <button
          type="button"
          class="flex w-full items-center gap-2 text-sm font-medium text-text-default hover:text-text-brand transition-colors"
          :aria-expanded="followUpsOpen"
          aria-controls="liquidate-follow-ups"
          data-testid="income-liquidate-followups-toggle"
          @click="followUpsOpen = !followUpsOpen"
        >
          <BaseActionIcon :action="followUpsOpen ? 'collapse' : 'expand'" class="text-text-subtle" />
          Sí lo voy a cobrar: crear ingreso esperado
        </button>
        <BaseCollapse id="liquidate-follow-ups" :open="followUpsOpen">
          <div class="space-y-2 pt-1">
            <div
              v-for="(row, index) in followUps"
              :key="`follow-up-${index}`"
              class="space-y-2 rounded-lg bg-surface-raised p-3"
              :data-testid="`income-liquidate-followup-${index}`"
            >
              <BaseInput
                v-model="row.concept"
                placeholder="Concepto"
                :error="followUpErrors[index]?.field === 'concept'"
                aria-label="Concepto del ingreso esperado"
                :data-testid="`followup-concept-${index}`"
              />
              <div class="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_9rem_auto] gap-2 items-start">
                <BaseInput
                  v-model="row.period_date"
                  type="month"
                  :error="followUpErrors[index]?.field === 'period'"
                  aria-label="Mes esperado de cobro"
                  :data-testid="`followup-period-${index}`"
                />
                <BaseCurrencyInput
                  :model-value="row.amount"
                  :suggestion="Math.max(unassigned, 0)"
                  :error="followUpErrors[index]?.field === 'amount'"
                  aria-label="Monto esperado"
                  :data-testid="`followup-amount-${index}`"
                  @update:model-value="onLineAmountInput(row, $event)"
                />
                <BaseButton
                  type="button"
                  variant="ghost"
                  size="sm"
                  class="justify-self-start sm:justify-self-auto"
                  aria-label="Quitar ingreso esperado"
                  @click="followUps.splice(index, 1)"
                >
                  Quitar
                </BaseButton>
              </div>
              <p
                v-if="followUpErrors[index]"
                class="text-xs text-danger-strong"
                :data-testid="`followup-error-${index}`"
              >
                {{ followUpErrors[index].message }}
              </p>
            </div>
            <BaseButton
              type="button"
              variant="secondary"
              size="sm"
              data-testid="income-liquidate-add-followup"
              @click="addFollowUp"
            >
              Agregar ingreso esperado
            </BaseButton>
          </div>
        </BaseCollapse>

      </section>

      <BaseFormField label="Notas">
        <BaseTextarea v-model="form.notes" :rows="2" />
      </BaseFormField>

    </form>
    <template #footer>
      <div class="space-y-2 border-t border-border-muted px-4 py-4 panel-portrait:px-6">
        <!-- Always rendered: a live region created on demand never announces. -->
        <p
          id="income-liquidate-submit-reason"
          aria-live="polite"
          class="text-xs text-danger-strong text-right min-h-4"
          data-testid="income-liquidate-submit-reason"
        >
          {{ saving ? '' : submitBlockReason }}
        </p>
        <div class="flex flex-col-reverse items-stretch gap-2 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-end">
          <BaseButton type="button" variant="secondary" @click="emit('close')">
            Cancelar
          </BaseButton>
          <BaseButton
            type="submit" :form="modalFormId"
            variant="primary"
            :loading="saving"
            :disabled="!canSubmit"
            :disabled-reason="submitBlockReason"
            aria-describedby="income-liquidate-submit-reason"
            data-testid="income-liquidate-submit"
          >
            {{ saving ? 'Guardando...' : 'Liquidar' }}
          </BaseButton>
        </div>
      </div>
    </template>
  </BaseModal>
</template>
