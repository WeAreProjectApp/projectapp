<script setup>
import { ref, useId } from 'vue';
import VatAmountInput from './VatAmountInput.vue';

const props = defineProps({
  record: { type: Object, required: true },
  amount: { type: [Number, String], required: true },
  draft: { type: Object, required: true },
  blockedReason: { type: String, default: '' },
  multiple: { type: Boolean, default: false },
});
const emit = defineEmits(['rate', 'toggle', 'capture']);
const open = ref(false);
const id = useId();
function toggle(value) {
  emit('toggle', value);
  if (value) open.value = true;
}
</script>

<template>
  <section class="rounded-lg border border-border-muted" :data-testid="`income-liquidate-vat-${record.id}`">
    <div class="flex flex-wrap items-center gap-3 px-4 py-3">
      <button type="button" class="flex min-w-0 flex-1 items-center gap-2 text-left text-sm font-medium text-text-default" :aria-expanded="open" :aria-controls="id" :data-testid="`income-liquidate-vat-toggle-${record.id}`" @click="open = !open">
        <BaseActionIcon :action="open ? 'collapse' : 'expand'" class="text-text-subtle" />
        <span class="min-w-0 [overflow-wrap:anywhere]">IVA<span v-if="multiple"> · {{ record.concept }}</span></span>
      </button>
      <BaseToggle :model-value="draft.enabled" :aria-label="`Aplicar IVA a ${record.concept}`" :disabled="Boolean(blockedReason)" :disabled-reason="blockedReason" :data-testid="`income-liquidate-apply-vat-${record.id}`" @update:model-value="toggle" />
      <span class="text-xs text-text-muted" :data-testid="`income-liquidate-vat-status-${record.id}`">{{ draft.rate === null ? (draft.enabled ? 'Por definir' : 'Sin registrar') : Number(draft.rate) === 0 ? 'Sin IVA · 0 %' : `${draft.rate} %` }}</span>
    </div>
    <BaseCollapse :id="id" :open="open">
      <div class="space-y-3 px-4 pb-4">
        <p v-if="blockedReason" class="text-xs text-text-subtle" :data-testid="`income-liquidate-vat-lock-${record.id}`">{{ blockedReason }}</p>
        <p v-else class="text-xs text-text-muted">El porcentaje se guarda en el ingreso original al liquidar. Apagar el interruptor lo deja Sin IVA (0 %).</p>
        <VatAmountInput :model-value="amount" :rate="draft.rate" :rate-disabled="Boolean(blockedReason) || !draft.enabled" :rate-disabled-reason="blockedReason || 'Activa el interruptor de IVA para definir el porcentaje.'" :input-test-id="`income-liquidate-vat-amount-${record.id}`" @update:rate="emit('rate', $event)" @capture="emit('capture', $event)" />
      </div>
    </BaseCollapse>
  </section>
</template>
