<script setup>
import { computed } from 'vue'
import { INPUT_FIELD_BASE, INPUT_FIELD_SIZE } from '~/components/base/inputClasses'
const props = defineProps({ modelValue: { type: Object, required: true }, options: { type: Object, default: null }, payments: { type: Array, default: () => [] } })
const emit = defineEmits(['update:modelValue'])
const fieldClass = `${INPUT_FIELD_BASE} ${INPUT_FIELD_SIZE.md || ''}`
const amendments = computed(() => props.options?.contracts?.find(row => row.id === props.modelValue.contract_id)?.amendments || [])
function nature(value) { emit('update:modelValue', { billing_nature: value, contract_id: null, amendment_id: null, project_hosting_id: null, hosting_payment_id: null }) }
function change(key, value) {
  const next = { ...props.modelValue, [key]: value ? Number(value) : null }
  if (key === 'contract_id') next.amendment_id = null
  emit('update:modelValue', next)
}
</script>
<template>
  <fieldset class="space-y-3 rounded-xl border border-border-default p-4" data-testid="billing-context-fields">
    <legend class="px-1 text-sm font-semibold text-text-default">Tipo de cobro y documento vinculado</legend>
    <label class="block text-sm text-text-default">¿Qué estás cobrando?
      <select data-testid="billing-nature" :value="modelValue.billing_nature || ''" :class="fieldClass" @change="nature($event.target.value)">
        <option value="">Elige el tipo de cobro…</option><option value="contract">Trabajo de un contrato / otrosí</option><option value="hosting">Hosting del proyecto</option>
      </select>
    </label>
    <template v-if="modelValue.billing_nature === 'contract'">
      <div class="grid grid-cols-1 gap-3 panel-portrait:grid-cols-2">
      <label class="block min-w-0 text-sm text-text-default">Contrato
        <select data-testid="billing-contract" :value="modelValue.contract_id || ''" :class="fieldClass" @change="change('contract_id', $event.target.value)"><option value="">Seleccionar…</option><option v-for="contract in options?.contracts || []" :key="contract.id" :value="contract.id">{{ contract.title }}</option></select>
      </label>
      <label class="block text-sm text-text-default">Otrosí (opcional)
        <select data-testid="billing-amendment" :value="modelValue.amendment_id || ''" :class="fieldClass" @change="change('amendment_id', $event.target.value)"><option value="">Sin otrosí</option><option v-for="amendment in amendments" :key="amendment.id" :value="amendment.id">{{ amendment.title }}</option></select>
      </label>
      </div>
    </template>
    <template v-if="modelValue.billing_nature === 'hosting'">
      <label class="block text-sm text-text-default">Hosting
        <select data-testid="billing-hosting" :value="modelValue.project_hosting_id || ''" :class="fieldClass" @change="change('project_hosting_id', $event.target.value)"><option value="">Seleccionar…</option><option v-if="options?.hosting_id" :value="options.hosting_id">Hosting de {{ options.project_name }}</option></select>
      </label>
      <p v-if="!options?.hosting_id" class="text-sm text-text-muted">El proyecto requiere asociación administrativa de su hosting.</p>
      <label v-if="payments.length" class="block text-sm text-text-default">Período de hosting que estás cobrando
        <select data-testid="billing-payment" :value="modelValue.hosting_payment_id || ''" :class="fieldClass" @change="change('hosting_payment_id', $event.target.value)"><option value="">Selecciona el período…</option><option v-for="payment in payments" :key="payment.id" :value="payment.id">#{{ payment.id }} · {{ payment.billing_period_start }} — {{ payment.billing_period_end }} · {{ payment.amount }} · {{ payment.status }}</option></select>
      </label>
    </template>
  </fieldset>
</template>
