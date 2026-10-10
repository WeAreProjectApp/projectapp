<script setup>
import { computed } from 'vue';
import { formatMoney } from '~/utils/formatMoney';
import { formatDate, formatDayMonth } from '~/utils/formatDate';

const props = defineProps({
  row: { type: Object, required: true },
});

// `bg-surface` + a ring instead of a soft fill: these rows are tinted green or
// amber by payment state in the classic view, and a soft fill on top of the
// tint muddies both.
const PAYMENT_BADGE_CLASSES = {
  paid: 'bg-surface text-success-strong ring-1 ring-inset ring-success-strong/30',
  partial: 'bg-surface text-warning-strong ring-1 ring-inset ring-warning-strong/30',
};

const MUTED_BADGE_CLASS =
  'bg-surface text-text-muted ring-1 ring-inset ring-text-subtle/40';

// Shown in the "Cobro" column on purpose: muting suppresses the chase, and
// this is the chase column. "Sigue sin cobrarse, pero acordamos no
// perseguirlo" reads as one thought in one cell.
const mutedLabel = computed(() => {
  if (!props.row.reminders_muted) return '';
  return props.row.reminders_muted_until
    ? `Silenciado hasta ${formatDayMonth(props.row.reminders_muted_until)}`
    : 'Silenciado';
});

const mutedTitle = computed(() => (
  props.row.reminders_muted_until
    ? `Los avisos se reanudan el ${formatDate(props.row.reminders_muted_until)}`
    : 'Avisos silenciados indefinidamente'
));
</script>

<template>
  <span
    v-if="row.payment_status"
    class="inline-flex flex-wrap items-center gap-1.5"
    :data-testid="`income-payment-${row.id}`"
  >
    <span
      v-if="PAYMENT_BADGE_CLASSES[row.payment_status]"
      class="text-xs px-2.5 py-1 rounded-full font-medium"
      :class="PAYMENT_BADGE_CLASSES[row.payment_status]"
    >
      {{ row.payment_status_label }}
    </span>
    <span v-else class="text-text-subtle">—</span>
    <span
      v-if="row.payment_status === 'partial'"
      class="text-2xs text-warning-strong tabular-nums"
    >
      faltan {{ formatMoney(Number(row.pending_amount)) }}
    </span>
    <span
      v-if="row.requires_collection_account"
      class="text-2xs text-warning-strong"
      :data-testid="`income-account-pending-${row.id}`"
    >
      Cuenta pendiente de emitir
    </span>
    <span
      v-if="row.reminders_muted"
      class="text-xs px-2.5 py-1 rounded-full font-medium"
      :class="MUTED_BADGE_CLASS"
      :title="mutedTitle"
      :data-testid="`income-muted-${row.id}`"
    >
      {{ mutedLabel }}
    </span>
  </span>
</template>
