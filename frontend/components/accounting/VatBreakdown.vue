<script setup>
import { computed } from 'vue'
import { formatMoney } from '~/utils/formatMoney'
import { vatBreakdown } from '~/utils/accountingVat'
const props = defineProps({
  total: { type: [Number, String], default: null },
  rate: { type: [Number, String], default: null },
  tax: { type: [Number, String], default: null },
  currency: { type: String, default: 'COP' },
  showCents: Boolean,
})
function money(amount) {
  return formatMoney(amount, props.currency, { decimals: props.showCents ? 'auto' : 0 })
}
const breakdown = computed(() => {
  if (props.tax !== null && props.tax !== undefined) {
    return { base: Number(props.total) - Number(props.tax), vat: props.tax, total: props.total }
  }
  return vatBreakdown(props.total, props.rate)
})
</script>
<template>
  <dl v-if="breakdown" class="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3" data-testid="vat-breakdown">
    <div v-if="breakdown.base !== null"><dt class="text-text-muted">Valor antes de IVA</dt><dd class="tabular-nums text-text-default" data-testid="vat-base">{{ money(breakdown.base) }}</dd></div>
    <div><dt class="text-text-muted">IVA<span v-if="rate !== null && rate !== undefined"> ({{ Number(rate) }} %)</span></dt><dd class="tabular-nums text-text-default" data-testid="vat-tax">{{ breakdown.vat === null ? 'IVA sin registrar' : money(breakdown.vat) }}</dd></div>
    <div><dt class="text-text-muted">Total</dt><dd class="font-semibold tabular-nums text-text-default" data-testid="vat-total">{{ money(breakdown.total) }}</dd></div>
  </dl>
</template>
