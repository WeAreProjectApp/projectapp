<script setup>
import EntityHistorySection from '~/components/history/EntityHistorySection.vue';
import { useId, computed, ref, watch } from 'vue'
import { formatMoney } from '~/utils/formatMoney'
import {
  calculateRecurringCopEquivalent,
  calculateRecurringMonthlyCop,
  CUSTOM_FREQUENCY,
  formatMonthlyCop,
  FREQUENCY_OPTIONS,
} from '~/utils/recurring'

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  seed: { type: Object, default: null },
  saving: { type: Boolean, default: false },
  categories: { type: Array, default: () => [] },
  usdExchangeRate: { type: [Number, String], default: null },
})

const emit = defineEmits(['close', 'submit'])

const isEdit = computed(() => !!props.record)
const isDuplicate = computed(() => !props.record && !!props.seed)
const title = computed(() =>
  isEdit.value
    ? 'Editar pago recurrente'
    : isDuplicate.value
      ? 'Duplicar pago recurrente'
      : 'Nuevo pago recurrente',
)

const currencyOptions = [
  { value: 'COP', label: 'COP' },
  { value: 'USD', label: 'USD' },
]

const paymentMethodOptions = [
  { value: 'cash', label: 'Efectivo' },
  { value: 'credit_card', label: 'T.C' },
]

const frequencyOptions = FREQUENCY_OPTIONS

const costTypeOptions = [
  { value: 'fixed', label: 'Fijo' },
  { value: 'variable', label: 'Variable' },
]

const categoryOptions = computed(() => [
  { value: '', label: 'Sin categoría' },
  ...props.categories.map((category) => ({
    value: category.id,
    label: category.name,
  })),
])

function defaultForm() {
  return {
    name: '',
    price: '',
    currency: 'COP',
    payment_method: 'cash',
    frequency: 'monthly',
    custom_months: '',
    billing_day: '',
    cycle_anchor_date: '',
    cost_type: 'fixed',
    category: '',
    is_active: true,
    notes: '',
  }
}

const form = ref(defaultForm())

const isCustomFrequency = computed(() => form.value.frequency === CUSTOM_FREQUENCY)
const isMonthlyFrequency = computed(() => form.value.frequency === 'monthly')
const duplicateNeedsAnchor = computed(() => (
  isDuplicate.value && props.seed?.schedule_requires_anchor
))

// A day of the month cannot say *which* month a quarterly or annual charge
// lands on, so anything beyond monthly needs the reference date to be announced.
const anchorHint = computed(() => (
  isMonthlyFrequency.value
    ? 'Con periodicidad mensual basta el día de cobro.'
    : 'Cualquier cobro conocido. Sin ella este pago no genera avisos.'
))

watch(
  () => [props.open, props.record, props.seed],
  () => {
    if (!props.open) return
    const source = props.record || props.seed
    if (source) {
      form.value = {
        name: source.name ?? '',
        price: source.price ?? '',
        currency: source.currency ?? 'COP',
        payment_method: source.payment_method ?? 'cash',
        frequency: source.frequency ?? 'monthly',
        custom_months: source.custom_months ?? '',
        billing_day: source.billing_day ?? '',
        cycle_anchor_date: source.cycle_anchor_date ?? '',
        cost_type: source.cost_type ?? 'fixed',
        category: source.category ?? '',
        is_active: source.is_active ?? true,
        notes: source.notes ?? '',
      }
    } else {
      form.value = defaultForm()
    }
  },
  { immediate: true },
)

const copEquivalentPreview = computed(() =>
  calculateRecurringCopEquivalent(form.value, props.usdExchangeRate),
)
const monthlyCopPreview = computed(() =>
  calculateRecurringMonthlyCop(form.value, props.usdExchangeRate),
)
const formattedRate = computed(() =>
  formatMoney(Number(props.usdExchangeRate || 0), 'COP'),
)

function onSubmit() {
  const payload = {
    name: form.value.name,
    price: form.value.price,
    currency: form.value.currency,
    payment_method: form.value.payment_method,
    frequency: form.value.frequency,
    // Only a custom cycle carries a month count; the API clears it otherwise.
    custom_months: isCustomFrequency.value && form.value.custom_months !== ''
      ? form.value.custom_months
      : null,
    cost_type: form.value.cost_type,
    // '' is the "Sin categoría" option; the API expects an explicit null.
    category: form.value.category === '' ? null : form.value.category,
    is_active: form.value.is_active,
  }
  payload.billing_day = form.value.billing_day === '' ? null : form.value.billing_day
  payload.cycle_anchor_date =
    form.value.cycle_anchor_date === '' ? null : form.value.cycle_anchor_date
  payload.notes = form.value.notes
  emit('submit', payload)
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="form" title-id="recurring-payment-form-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="recurring-payment-form-title" class="text-lg font-bold text-text-default">{{ title }}</h3>
    </div>
    <EntityHistorySection v-if="open && record?.id" entity-type="recurring" :object-id="record.id" class="mx-5" />
    <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
      <BaseFormField label="Nombre" required>
        <BaseInput v-model="form.name" required />
      </BaseFormField>

      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Precio" required>
          <BaseCurrencyInput
            v-model="form.price"
            :decimals="form.currency === 'USD' ? 2 : 0"
            data-testid="recurring-payment-form-price"
            required
          />
        </BaseFormField>
        <BaseFormField label="Moneda">
          <BaseSegmented v-model="form.currency" :options="currencyOptions" full-width />
        </BaseFormField>
      </BaseFormRow>

      <div
        class="rounded-xl border border-border-muted bg-surface-raised px-4 py-3"
        data-testid="recurring-payment-cop-preview"
      >
        <template v-if="copEquivalentPreview != null">
          <div class="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span class="text-text-muted">Equivalente COP</span>
            <strong class="tabular-nums text-text-default">
              {{ formatMonthlyCop(copEquivalentPreview) }}
            </strong>
          </div>
          <div class="flex flex-wrap items-center justify-between gap-2 mt-1 text-sm">
            <span class="text-text-muted">Equivalente COP mensual</span>
            <strong class="tabular-nums text-text-default">
              {{ formatMonthlyCop(monthlyCopPreview) }}
            </strong>
          </div>
          <p v-if="form.currency === 'USD'" class="mt-1 text-xs text-text-subtle">
            Tasa vigente: {{ formattedRate }}/USD. El servidor recalcula este valor al guardar.
          </p>
          <p v-else class="mt-1 text-xs text-text-subtle">
            En COP, el equivalente toma el precio automáticamente.
          </p>
        </template>
        <p v-else class="text-sm text-warning-strong">
          Configura una tasa USD válida para calcular el equivalente en COP.
        </p>
      </div>

      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Método de pago">
          <BaseSelect v-model="form.payment_method" :options="paymentMethodOptions" />
        </BaseFormField>
        <BaseFormField label="Frecuencia">
          <BaseSelect
            v-model="form.frequency"
            :options="frequencyOptions"
            data-testid="recurring-payment-form-frequency"
          />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormField
        v-if="isCustomFrequency"
        label="Cada cuántos meses"
        hint="El equivalente mensual es el precio dividido entre este número"
        required
      >
        <BaseInput
          v-model="form.custom_months"
          type="number"
          step="1"
          min="1"
          data-testid="recurring-payment-form-custom-months"
        />
      </BaseFormField>

      <BaseFormField
        label="Fecha de referencia del cobro"
        :hint="anchorHint"
        :required="duplicateNeedsAnchor"
      >
        <BaseInput
          v-model="form.cycle_anchor_date"
          type="date"
          :required="duplicateNeedsAnchor"
          data-testid="recurring-payment-form-cycle-anchor-date"
        />
        <p
          v-if="isDuplicate"
          class="mt-1 text-xs"
          :class="duplicateNeedsAnchor ? 'text-warning-strong' : 'text-text-subtle'"
          data-testid="recurring-duplicate-schedule-notice"
        >
          {{ seed?.schedule_notice }}
        </p>
      </BaseFormField>

      <BaseFormRow
        :cols="2"
        :gap="4"
        :help="isMonthlyFrequency ? '' : 'El próximo cobro se calcula desde la fecha de referencia.'"
      >
        <BaseFormField label="Día de cobro">
          <BaseInput v-model="form.billing_day" type="number" step="1" min="1" max="31" />
        </BaseFormField>
        <BaseFormField label="Tipo de costo">
          <BaseSegmented v-model="form.cost_type" :options="costTypeOptions" full-width />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormField label="Categoría" hint="Agrupa el recurrente en la vista por categorías">
        <BaseSelect
          v-model="form.category"
          :options="categoryOptions"
          data-testid="recurring-payment-form-category"
        />
      </BaseFormField>

      <BaseFormField label="Activo">
        <BaseToggle v-model="form.is_active" aria-label="Activo" />
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
          data-testid="recurring-payment-form-submit"
        >
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
