<template>
  <div
    class="min-w-0"
    :data-testid="`receivable-control-${row.id}`"
    @click.stop
    @keydown.stop
  >
    <span v-if="row.kind !== 'expected'" class="text-text-subtle">—</span>

    <div v-else-if="eligible" class="flex min-w-0 items-center gap-2">
      <BaseToggle
        :model-value="Boolean(row.is_receivable_candidate)"
        size="sm"
        :disabled="busy"
        :aria-label="candidateAriaLabel"
        @update:model-value="emit('change', { is_receivable_candidate: $event })"
      />
      <div class="flex min-w-0 flex-1 items-center gap-2">
        <ReceivableConfidenceDot :confidence="row.collection_confidence" />
        <BaseChoiceSelect
          :model-value="row.collection_confidence || ''"
          :options="RECEIVABLE_CONFIDENCE_OPTIONS"
          size="sm"
          class="min-w-0 flex-1"
          :disabled="busy"
          disabled-reason="Guardando la previsión de cobro."
          :aria-label="`Probabilidad de cobro de ${row.concept}`"
          @update:model-value="emit('change', { collection_confidence: $event })"
        />
      </div>
      <span v-if="busy" class="sr-only" role="status">Guardando</span>
    </div>

    <div v-else class="flex items-center gap-2">
      <ReceivableConfidenceBadge
        :confidence="row.collection_confidence"
      />
      <span class="text-[10px] text-text-muted">{{ unavailableReason }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import BaseChoiceSelect from '~/components/base/BaseChoiceSelect.vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import ReceivableConfidenceBadge from '~/components/accounting/ReceivableConfidenceBadge.vue';
import ReceivableConfidenceDot from '~/components/accounting/ReceivableConfidenceDot.vue';
import {
  RECEIVABLE_CONFIDENCE_OPTIONS,
  isReceivableEligible,
} from '~/utils/receivables';

const props = defineProps({
  row: { type: Object, required: true },
  busy: { type: Boolean, default: false },
});

const emit = defineEmits(['change']);
const eligible = computed(() => isReceivableEligible(props.row));
const candidateAriaLabel = computed(() =>
  `${props.row.is_receivable_candidate ? 'Quitar' : 'Agregar'} ${props.row.concept} de pendientes por cobrar`,
);
const unavailableReason = computed(() => {
  if (props.row.ledger !== 'company') return 'Sólo empresa';
  if (props.row.payment_status === 'paid') return 'Cobrado';
  return 'Cerrado';
});
</script>
