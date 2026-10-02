<script setup>
import { computed, ref, watch } from 'vue'
import VatBreakdown from './VatBreakdown.vue'
import { vatBreakdown } from '~/utils/accountingVat'
const props = defineProps({
  modelValue: { type: [Number, String], default: null },
  rate: { type: [Number, String], default: null },
  inputTestId: { type: String, default: 'vat-amount' },
  disabled: { type: Boolean, default: false },
  disabledReason: { type: String, default: '' },
  required: { type: Boolean, default: true },
  resetKey: { type: [Boolean, Number, String], default: null },
})
const emit = defineEmits(['update:modelValue', 'update:rate', 'capture'])
const mode = ref('vat_included')
const modes = [
  { value: 'vat_included', label: 'Total con IVA' },
  { value: 'before_vat', label: 'Antes de IVA', disabled: props.rate == null },
]
const inputAmount = ref(props.modelValue)
const invalid = ref(false)
function refreshAmount() {
  const values = vatBreakdown(props.modelValue, props.rate)
  inputAmount.value = mode.value === 'before_vat' ? values?.base : props.modelValue
}
watch(() => props.resetKey, () => { mode.value = 'vat_included'; invalid.value = false; refreshAmount() })
watch(() => props.modelValue, refreshAmount)
watch(mode, refreshAmount)
watch(() => props.rate, () => {
  if (props.rate == null && mode.value === 'before_vat') mode.value = 'vat_included'
  refreshAmount()
})
function emitCapture(amount, amountMode = mode.value) {
  const emptyOptional = !props.required && (amount === null || amount === undefined || amount === '')
  emit('capture', emptyOptional ? null : { amount, amount_mode: amountMode })
}
function capture(value, rate = props.rate) {
  inputAmount.value = value
  const values = vatBreakdown(value, rate, mode.value)
  invalid.value = !values && value !== null && value !== ''
  emitCapture(value)
  emit('update:modelValue', values?.total ?? value)
}
function changeMode(value) {
  mode.value = value
  refreshAmount()
  emitCapture(inputAmount.value, value)
}
function changeRate(value) {
  const rate = value === '' || value === null ? null : value
  const previousAmount = inputAmount.value
  emit('update:rate', rate)
  if (mode.value === 'before_vat' && rate !== null) {
    capture(previousAmount, rate)
  } else {
    if (rate === null) mode.value = 'vat_included'
    emitCapture(props.modelValue, 'vat_included')
  }
}
const modeOptions = computed(() => modes.map(item => ({ ...item, disabled: item.value === 'before_vat' && props.rate == null, disabledReason: 'Define el IVA para introducir un valor antes del impuesto.' })))
</script>
<template>
  <div class="space-y-3" data-testid="vat-input">
    <BaseFormField label="Cómo introduces el valor">
      <BaseSegmented :model-value="mode" @update:model-value="changeMode($event)" :options="modeOptions" full-width :disabled="disabled" :disabled-reason="disabledReason" />
    </BaseFormField>
    <BaseFormRow :cols="2">
      <BaseFormField :label="mode === 'before_vat' ? 'Valor antes de IVA' : 'Total con IVA incluido'" :required="required">
        <BaseCurrencyInput :model-value="inputAmount" :decimals="2" :required="required" :data-testid="inputTestId" :disabled="disabled" :disabled-reason="disabledReason" @update:model-value="capture($event)" />
      </BaseFormField>
      <BaseFormField label="IVA (%)" hint="Usa 0 para Sin IVA; vacío significa sin registrar.">
        <BaseInput :model-value="rate" type="number" min="0" max="100" step="0.01" placeholder="Sin registrar" data-testid="vat-rate" :disabled="disabled" :disabled-reason="disabledReason" @update:model-value="changeRate($event)" />
        <BaseButton type="button" variant="link" size="sm" :disabled="disabled" :disabled-reason="disabledReason" @click="changeRate(0)">Sin IVA</BaseButton>
      </BaseFormField>
    </BaseFormRow>
    <p v-if="invalid" class="text-sm text-danger-strong" role="alert">Revisa el importe y el porcentaje de IVA.</p>
    <VatBreakdown :total="modelValue" :rate="rate" />
  </div>
</template>
