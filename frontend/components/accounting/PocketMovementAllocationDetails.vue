<script setup>
import { computed } from 'vue';
import { formatMoney } from '~/utils/formatMoney';

const props = defineProps({ movement: { type: Object, required: true } });
const { t } = useI18n();
const localePath = useLocalePath();
const entries = computed(() => props.movement.allocation_details || []);
const total = computed(() => entries.value.reduce((sum, entry) => sum + Math.round(Number(entry.amount) * 100), 0));
const inconsistent = computed(() => total.value !== Math.round(Number(props.movement.amount) * 100));
function incomeTo(entry) {
  return localePath({ path: '/panel/accounting/incomes', query: { income: String(entry.expected_income_id || entry.income_id) } });
}
</script>

<template>
  <section class="min-w-0 space-y-3" data-testid="pocket-allocation-details">
    <h4 class="text-sm font-semibold text-text-default">{{ t('accountingPocket.allocations') }}</h4>
    <ul class="divide-y divide-border-muted">
      <li v-for="entry in entries" :key="entry.income_id" class="min-w-0 py-3" data-testid="pocket-allocation-detail-row">
        <BaseRowLink :to="incomeTo(entry)" class="break-words text-sm font-medium text-text-brand">
          {{ entry.concept }}
        </BaseRowLink>
        <p v-if="entry.is_credit" class="mt-1 text-xs text-text-muted">{{ t('accountingPocket.credit') }}</p>
        <dl class="mt-2 grid min-w-0 gap-2 text-sm panel-portrait:grid-cols-2">
          <div class="min-w-0">
            <dt class="text-text-muted">{{ t(entry.is_credit ? 'accountingPocket.credit' : 'accountingPocket.allocation') }}</dt>
            <dd class="tabular-nums text-text-default">{{ formatMoney(entry.amount) }}</dd>
          </div>
          <div v-if="entry.pending_amount !== null" class="min-w-0">
            <dt class="text-text-muted">{{ t('accountingPocket.pending') }}</dt>
            <dd class="tabular-nums text-text-default" data-testid="pocket-allocation-pending">{{ formatMoney(entry.pending_amount) }}</dd>
          </div>
        </dl>
      </li>
    </ul>
    <p class="flex flex-wrap justify-between gap-2 border-t border-border-muted pt-3 text-sm font-semibold text-text-default">
      <span>{{ t('accountingPocket.total') }}</span>
      <span class="tabular-nums" data-testid="pocket-allocation-detail-total">{{ formatMoney(total / 100) }}</span>
    </p>
    <p v-if="inconsistent" role="alert" class="text-sm text-warning-strong">{{ t('accountingPocket.discrepancy') }}</p>
  </section>
</template>
