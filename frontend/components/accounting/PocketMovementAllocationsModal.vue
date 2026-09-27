<template>
  <BaseModal
    :model-value="open"
    kind="detail"
    size="lg"
    title-id="pocket-allocations-title"
    @close="emit('close')"
  >
    <div class="px-6 pt-6 pb-6" data-testid="pocket-allocations-modal">
      <h3 id="pocket-allocations-title" class="text-lg font-bold text-text-default">
        Reparto del abono
      </h3>
      <p class="text-sm text-text-muted mt-1">
        {{ subtitle }}
      </p>

      <div class="overflow-x-auto mt-4">
        <table class="w-full min-w-[360px] text-sm">
          <thead>
            <tr class="text-left text-xs text-text-subtle uppercase tracking-wider">
              <th class="px-3 py-2">Concepto</th>
              <th class="px-3 py-2 text-right">Monto</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in allocations"
              :key="entry.income_id"
              class="border-t border-border-muted"
              data-testid="pocket-allocation-row"
            >
              <td class="px-3 py-2 text-text-default">{{ entry.concept }}</td>
              <td class="px-3 py-2 text-right tabular-nums text-text-default">
                {{ money(entry.amount) }}
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr class="border-t border-border-default font-semibold">
              <td class="px-3 py-2 text-text-default">Total</td>
              <td
                class="px-3 py-2 text-right tabular-nums text-text-default"
                data-testid="pocket-allocations-total"
              >
                {{ money(total) }}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="secondary" @click="emit('close')">
          Cerrar
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed } from 'vue';

import BaseButton from '~/components/base/BaseButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';

/**
 * Read-only breakdown of an abono movement: which incomes the single pocket
 * entry covered and with how much each. Fed by the movement serializer's
 * `allocations`; deleting the movement (from the table's own action) is what
 * reverses the whole abono.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  movement: { type: Object, default: null },
});

const emit = defineEmits(['close']);

const allocations = computed(() => (
  Array.isArray(props.movement?.allocations) ? props.movement.allocations : []
));

const total = computed(() => allocations.value.reduce(
  (acc, entry) => acc + Number(entry.amount ?? 0), 0,
));

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

const subtitle = computed(() => {
  if (!props.movement) return '';
  return `${props.movement.concept} · ${formatDate(props.movement.movement_date)} · ${money(props.movement.amount)}`;
});
</script>
