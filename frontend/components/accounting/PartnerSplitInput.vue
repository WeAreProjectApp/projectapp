<template>
  <div class="space-y-4">
    <VatAmountInput v-if="showVat" :model-value="total" :rate="vatRate" :reset-key="vatResetKey" input-test-id="partner-split-total"
      @update:model-value="onTotalInput" @update:rate="emit('update:vatRate', $event)" @capture="emit('vatCapture', $event)" />
    <div v-else>
      <label class="block text-xs font-medium text-text-muted mb-1">Valor total</label>
      <BaseCurrencyInput
        :model-value="total"
        placeholder="0"
        data-testid="partner-split-total"
        @update:model-value="onTotalInput"
      />
    </div>

    <div class="flex items-center gap-2">
      <BaseToggle
        :model-value="autoSplit"
        aria-label="Reparto automático 50/50"
        data-testid="partner-split-auto"
        @update:model-value="onToggleAuto"
      />
      <span class="text-sm text-text-default">Reparto automático 50/50</span>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div>
        <label class="block text-xs font-medium text-text-muted mb-1">Gustavo</label>
        <BaseCurrencyInput
          :model-value="gustavoAmount"
          placeholder="0"
          :disabled="autoSplit"
          disabled-reason="Desactiva el reparto automático para editar este valor."
          data-testid="partner-split-gustavo"
          @update:model-value="emit('update:gustavoAmount', $event)"
        />
      </div>
      <div>
        <label class="block text-xs font-medium text-text-muted mb-1">Carlos</label>
        <BaseCurrencyInput
          :model-value="carlosAmount"
          placeholder="0"
          :disabled="autoSplit"
          disabled-reason="Desactiva el reparto automático para editar este valor."
          data-testid="partner-split-carlos"
          @update:model-value="emit('update:carlosAmount', $event)"
        />
      </div>
    </div>

    <p v-if="autoSplit" class="text-xs text-text-subtle">
      Desactiva el reparto automático para editar los valores de cada socio.
    </p>

    <p
      v-if="sumExceedsTotal"
      data-testid="partner-split-warning"
      class="text-xs text-warning-strong"
    >
      La suma de socios supera el total
    </p>

    <p
      v-if="remainder > 0"
      data-testid="partner-split-remainder"
      class="text-xs text-text-muted"
    >
      Bolsillo ProjectApp: {{ formatMoney(remainder, 'COP') }}
    </p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import VatAmountInput from './VatAmountInput.vue';
import BaseCurrencyInput from '~/components/base/BaseCurrencyInput.vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import { formatMoney } from '~/utils/formatMoney';

const props = defineProps({
  showVat: { type: Boolean, default: false },
  vatRate: { type: [Number, String], default: null },
  vatResetKey: { type: [Boolean, Number, String], default: null },
  total: { type: [String, Number], default: '' },
  gustavoAmount: { type: [String, Number], default: '' },
  carlosAmount: { type: [String, Number], default: '' },
});

const emit = defineEmits(['update:total', 'update:gustavoAmount', 'update:carlosAmount', 'update:vatRate', 'vatCapture']);

const autoSplit = ref(true);

function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

// Integer COP split that always sums exactly to the total.
function splitFrom(totalValue) {
  const n = Math.max(0, Math.floor(toNumber(totalValue)));
  const gustavo = Math.floor(n / 2);
  return { gustavo, carlos: n - gustavo };
}

function emitSplit(totalValue) {
  const { gustavo, carlos } = splitFrom(totalValue);
  emit('update:gustavoAmount', gustavo);
  emit('update:carlosAmount', carlos);
}

function onTotalInput(value) {
  emit('update:total', value);
  if (autoSplit.value) emitSplit(value);
}

function onToggleAuto(value) {
  autoSplit.value = value;
  if (value) emitSplit(props.total);
}

const sumExceedsTotal = computed(
  () =>
    !autoSplit.value &&
    toNumber(props.gustavoAmount) + toNumber(props.carlosAmount) > toNumber(props.total),
);

const remainder = computed(
  () => toNumber(props.total) - toNumber(props.gustavoAmount) - toNumber(props.carlosAmount),
);
</script>
