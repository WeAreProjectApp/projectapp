<template>
  <dl class="grid min-w-0 gap-2 text-xs" :class="compact ? '' : 'panel-portrait:grid-cols-2'">
    <div v-for="field in fields" :key="field" class="min-w-0">
      <dt class="text-text-muted">{{ text[field] }}</dt>
      <dd class="break-words text-text-default" :class="compact ? 'line-clamp-2' : 'whitespace-pre-wrap'">{{ value(field) }}</dd>
    </div>
  </dl>
</template>
<script setup>
import { computed } from 'vue';
import { useDashboardAttentionText } from '~/composables/useDashboardAttentionText';
import { formatDateTime, formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';
const props = defineProps({ record: { type: Object, required: true }, compact: Boolean });
const text = useDashboardAttentionText();
const fields = computed(() => ({
  emails_failed: ['recipient', 'sent_at', 'error_message'],
  recurring_due: ['amount', 'due_date', 'payment_method'],
  tasks_overdue: props.compact ? ['assignee', 'due_date', 'priority'] : ['assignee', 'due_date', 'priority', 'description'],
  documents_overdue: ['client', 'amount', 'due_date'],
  collection_documents_pending: ['client', 'amount', 'pending_at'],
  proposals_stale: ['client', 'sent_at', 'days_unopened'],
}[props.record.type] || []));
function value(field) {
  const row = props.record;
  if (field === 'amount') return row.amount == null ? text.value.unavailable : formatMoney(row.amount, row.currency, { decimals: row.currency === 'USD' ? 2 : 0 });
  if (field === 'pending_at') return formatDateTime(row.pending_at, { fallback: text.value.unavailable });
  if (field === 'sent_at') return formatDateTime(row.sent_at, { fallback: text.value.unavailable });
  if (field === 'due_date') return formatDate(row.due_date, { fallback: text.value.unavailable });
  if (field === 'recipient') return [...(row.to_recipients || []), ...(row.cc_recipients || [])].map((entry) => entry.email).filter(Boolean).join(', ') || row.recipient || text.value.unavailable;
  return row[field] === 0 ? '0' : (row[field] || text.value.unavailable);
}
</script>
