<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import HostingPeriodSummary from './HostingPeriodSummary.vue'
const props = defineProps({ periods: { type: Array, required: true }, modelValue: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const update = fields => emit('update:modelValue', { ...props.modelValue, ...fields })
const entries = computed(() => props.modelValue.entries || [])
function evidence(period, field, id) {
  const previous = entries.value.find(row => row.income_id === period.income_id)
  const row = { ...previous, income_id: period.income_id, hosting_record_id: period.hosting_record_id }
  if (id) row[field] = Number(id)
  else delete row[field]
  update({ entries: [...entries.value.filter(entry => entry.income_id !== period.income_id), row] })
}
function choices(rows) {
  return [{ value: '', label: t('hostingBilling.noneSelected') },
    ...rows.map(row => ({ value: row.id, label: [row.receipt_id && `#${row.receipt_id} ${row.issuer} ${row.reference}`, `#${row.id}`, row.date, `${row.amount} COP`].filter(Boolean).join(' · ') }))]
}
</script>
<template>
  <section class="space-y-3" data-testid="hosting-receipt-fields">
    <div v-for="period in periods" :key="period.income_id" class="space-y-2 rounded-lg bg-surface-raised p-3">
      <HostingPeriodSummary :period="period" :show-blocker="period.state === 'conflict' || period.state === 'blocked'" />
      <BaseFormField v-if="period.cycles?.length" :label="t('hostingBilling.existingCycle')">
        <BaseSelect :model-value="entries.find(row => row.income_id === period.income_id)?.cycle_id || ''"
          :options="choices(period.cycles)" @update:model-value="evidence(period, 'cycle_id', $event)" />
      </BaseFormField>
      <BaseFormField v-if="period.liquids?.length" :label="t('hostingBilling.existingLiquid')">
        <BaseSelect :model-value="entries.find(row => row.income_id === period.income_id)?.liquid_id || ''"
          :options="choices(period.liquids)" @update:model-value="evidence(period, 'liquid_id', $event)" />
      </BaseFormField>
    </div>
    <p class="text-sm text-text-muted">{{ t('hostingBilling.receiptHelp') }}</p>
    <BaseFormRow :cols="2">
      <BaseFormField :label="t('hostingBilling.issuer')">
        <BaseInput :model-value="modelValue.issuer" maxlength="96" data-testid="hosting-receipt-issuer" @update:model-value="update({ issuer: $event })" />
      </BaseFormField>
      <BaseFormField :label="t('hostingBilling.reference')">
        <BaseInput :model-value="modelValue.reference" maxlength="128" data-testid="hosting-receipt-reference" @update:model-value="update({ reference: $event })" />
      </BaseFormField>
    </BaseFormRow>
  </section>
</template>
