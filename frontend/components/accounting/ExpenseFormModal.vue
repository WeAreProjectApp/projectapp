<script setup>
import EntityHistorySection from '~/components/history/EntityHistorySection.vue';
import { useId, computed, ref, watch } from 'vue'
import PartnerSplitInput from './PartnerSplitInput.vue'
import VatAmountInput from './VatAmountInput.vue'
import PeriodDateField from './PeriodDateField.vue'
import { todayISO } from '~/utils/periodDates'

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'submit'])

const isEdit = computed(() => !!props.record)
const title = computed(() => (isEdit.value ? 'Editar Gasto' : 'Nuevo Gasto'))

const categoryOptions = [
  { value: 'business', label: 'Negocio' },
  { value: 'personal', label: 'Personal' },
]

const ledgerOptions = [
  { value: 'company', label: 'Empresa' },
  { value: 'gustavo', label: 'Personal Gustavo' },
  { value: 'carlos', label: 'Personal Carlos' },
]

function defaultForm() {
  return {
    concept: '',
    period_date: todayISO(),
    category: 'business',
    ledger: 'company',
    total_amount: '',
    vat_rate: 19,
    vat_capture: null,
    gustavo_amount: '',
    carlos_amount: '',
    register_in_pocket: true,
    notes: '',
  }
}

const form = ref(defaultForm())
// Exact payment day by default; the toggle downgrades to month-only.
const exactDate = ref(true)

const isPersonal = computed(() => form.value.ledger !== 'company')
// Deductions are born in the settlement flow; here they only get their
// amounts/notes touched, and the pocket toggle disappears — the backend
// forces register_in_pocket off for them anyway.
const isDeduction = computed(() => !!props.record?.deduction_type)

watch(
  () => [props.open, props.record],
  () => {
    if (!props.open) return
    if (props.record) {
      // Prefill from the raw period_date — `period` is 'YYYY-MM' and would
      // silently reset the day to the 1st on every edit. Edits always open
      // in full-date mode showing the stored day (01 for month-only
      // records, whose real day was never captured); the toggle still
      // downgrades when only the month is known.
      exactDate.value = true
      form.value = {
        concept: props.record.concept ?? '',
        period_date: props.record.period_date ?? '',
        category: props.record.category ?? 'business',
        ledger: props.record.ledger ?? 'company',
        total_amount: props.record.total_amount ?? '',
        vat_rate: props.record.vat_rate ?? null,
        vat_capture: null,
        gustavo_amount: props.record.gustavo_amount ?? '',
        carlos_amount: props.record.carlos_amount ?? '',
        register_in_pocket: props.record.pocket_movement != null,
        notes: props.record.notes ?? '',
      }
    } else {
      exactDate.value = true
      form.value = defaultForm()
    }
  },
  { immediate: true },
)

function onSubmit() {
  const payload = {
    concept: form.value.concept,
    period_date: form.value.period_date,
    category: form.value.category,
    ledger: form.value.ledger,
    total_amount: form.value.total_amount,
    vat_rate: form.value.vat_rate,
  }
  if (form.value.vat_capture) {
    delete payload.total_amount
    Object.assign(payload, form.value.vat_capture)
  }
  if (!isPersonal.value) {
    payload.gustavo_amount = form.value.gustavo_amount
    payload.carlos_amount = form.value.carlos_amount
  }
  if (!isDeduction.value) {
    payload.register_in_pocket = form.value.register_in_pocket
  }
  payload.notes = form.value.notes
  emit('submit', payload)
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="form" title-id="expense-form-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="expense-form-title" class="text-lg font-bold text-text-default">{{ title }}</h3>
    </div>
    <EntityHistorySection v-if="open && record?.id" entity-type="expense" :object-id="record.id" class="mx-5" />
    <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
      <BaseFormField label="Concepto" required>
        <BaseInput v-model="form.concept" required />
      </BaseFormField>

      <BaseFormRow :cols="2" :gap="4">
        <PeriodDateField
          v-model="form.period_date"
          v-model:exact="exactDate"
          label-exact="Fecha"
          label-month="Mes"
          required
          input-testid="expense-form-period"
          toggle-testid="expense-form-exact-date"
        />
        <BaseFormField label="Categoría">
          <BaseSelect v-model="form.category" :options="categoryOptions" />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormField label="Contabilidad" class="panel-portrait:max-w-md">
        <BaseSegmented v-model="form.ledger" :options="ledgerOptions" full-width />
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

      <VatAmountInput v-else v-model="form.total_amount" v-model:rate="form.vat_rate" :reset-key="open" @capture="form.vat_capture = $event" />

      <div
        v-if="isDeduction"
        class="text-xs text-info-strong bg-info-soft rounded-lg px-3 py-2"
        data-testid="expense-deduction-edit-hint"
      >
        Deducción sobre ingreso ({{ record.deduction_type_label }}) — se crea
        desde Liquidar y nunca registra egreso en bolsillo.
      </div>
      <div v-else class="flex items-center justify-between gap-3">
        <div>
          <p class="text-sm font-medium text-text-default">Registrar egreso en bolsillo</p>
          <p class="text-xs text-text-subtle">
            Desactívalo para ajustes contables o gastos que no salieron del bolsillo.
          </p>
          <p
            v-if="isPersonal && form.register_in_pocket"
            class="text-xs text-warning-strong mt-1"
            data-testid="expense-pocket-draw-hint"
          >
            Al salir del bolsillo se registrará como retiro de la empresa
            asignado 100% al socio.
          </p>
        </div>
        <BaseToggle
          v-model="form.register_in_pocket"
          aria-label="Registrar egreso en bolsillo"
          data-testid="expense-register-in-pocket"
        />
      </div>

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
          data-testid="expense-form-submit"
        >
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
