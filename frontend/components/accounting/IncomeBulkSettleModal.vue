<template>
  <BaseModal
    :model-value="open"
    kind="form"
    title-id="income-bulk-settle-title"
    @close="emit('close')"
  >
    <div data-testid="income-bulk-settle-modal">
      <div class="px-6 pt-6 pb-2">
        <h3 id="income-bulk-settle-title" class="text-lg font-bold text-text-default">
          Registrar abono
        </h3>
        <p class="text-sm text-text-muted mt-1">
          Un solo pago repartido entre los ingresos esperados seleccionados.
          Se registrará un único movimiento en el Bolsillo ProjectApp.
        </p>
        <p
          v-if="excludedCount > 0"
          class="text-xs text-text-subtle mt-1"
          data-testid="income-bulk-settle-excluded"
        >
          {{ excludedNote }}
        </p>
        <p
          v-if="mixedClients"
          class="text-xs text-warning-strong mt-1"
          data-testid="income-bulk-settle-mixed-clients"
        >
          La selección mezcla ingresos de {{ clientListLabel }}. El abono se
          registrará igual como un solo pago.
        </p>
      </div>

      <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
        <BaseFormRow :cols="2" :gap="3" help-testid="income-bulk-settle-destination-help">
          <BaseFormField label="Valor recibido" required>
            <BaseCurrencyInput
              v-model="form.total"
              required
              data-testid="income-bulk-settle-total"
            />
          </BaseFormField>

          <PeriodDateField
            v-model="form.period_date"
            v-model:exact="exactDate"
            label-exact="Fecha en que se recibió el pago"
            label-month="Mes en que se recibió el pago"
            toggle-label="Registrar el día exacto de pago"
            required
            input-testid="income-bulk-settle-period"
            toggle-testid="income-bulk-settle-exact-date"
          />

          <template #help>
            Destino:
            <span class="font-medium text-text-default" data-testid="income-bulk-settle-destination">Bolsillo ProjectApp</span>.
            El pago entra como un único movimiento al bolsillo de la empresa.
          </template>
        </BaseFormRow>

        <!-- El reparto: la tabla renderiza en el MISMO orden en que el dinero
             llena (más antiguo primero) — mostrado en otro orden, el prellenado
             leería como arbitrario. -->
        <div class="space-y-2">
          <div class="flex items-center justify-between gap-2 min-h-8">
            <h4 class="text-sm font-medium text-text-default">
              Reparto entre los seleccionados
            </h4>
            <div v-if="touched" class="flex items-center gap-2">
              <span
                class="text-xs text-text-subtle"
                data-testid="income-bulk-settle-manual-hint"
              >
                Reparto manual: ya no se recalcula al cambiar el valor.
              </span>
              <BaseButton
                type="button"
                variant="ghost"
                size="sm"
                data-testid="income-bulk-settle-recalculate"
                @click="recalculate"
              >
                Recalcular reparto
              </BaseButton>
            </div>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[560px] text-sm">
              <thead>
                <tr class="text-left text-xs text-text-subtle uppercase tracking-wider">
                  <th class="px-3 py-2">Concepto</th>
                  <th class="px-3 py-2">Fecha prevista</th>
                  <th class="px-3 py-2 text-right">Pendiente</th>
                  <th class="px-3 py-2 text-right">Imputado</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in orderedRecords"
                  :key="row.id"
                  class="border-t border-border-muted"
                >
                  <td class="px-3 py-2 text-text-default">{{ row.concept }}</td>
                  <td class="px-3 py-2 text-text-muted text-xs whitespace-nowrap">
                    {{ row.period_label || row.period_date }}
                  </td>
                  <td class="px-3 py-2 text-right tabular-nums text-warning-strong">
                    {{ money(row.pending_amount) }}
                  </td>
                  <td class="px-3 py-2 text-right w-40">
                    <BaseCurrencyInput
                      :model-value="allocations[row.id]"
                      :error="Boolean(rowErrors[row.id])"
                      :aria-label="`Imputado a ${row.concept}`"
                      :data-testid="`income-bulk-settle-amount-${row.id}`"
                      @update:model-value="onRowInput(row.id, $event)"
                    />
                    <p
                      v-if="rowErrors[row.id]"
                      class="text-xs text-danger-strong mt-1 text-right"
                      :data-testid="`income-bulk-settle-row-error-${row.id}`"
                    >
                      {{ rowErrors[row.id] }}
                    </p>
                  </td>
                </tr>
              </tbody>
              <tfoot>
                <tr class="border-t border-border-default font-semibold">
                  <td class="px-3 py-2 text-text-default" colspan="2">Total</td>
                  <td
                    class="px-3 py-2 text-right tabular-nums text-warning-strong"
                    data-testid="income-bulk-settle-pending-sum"
                  >
                    {{ money(pendingSum) }}
                  </td>
                  <td
                    class="px-3 py-2 text-right tabular-nums text-text-default"
                    data-testid="income-bulk-settle-allocated-sum"
                  >
                    {{ money(allocatedSum) }}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        <!-- Cada frase asertada vive entera en UN elemento: partirla rompe
             los substring checks de los tests. -->
        <div
          class="flex flex-wrap items-center gap-x-2 gap-y-1"
          data-testid="income-bulk-settle-summary"
        >
          <BaseBadge :variant="summaryState.variant" class="tabular-nums">
            {{ summaryState.badge }}
          </BaseBadge>
          <span class="text-xs text-text-subtle">{{ summaryState.clause }}</span>
          <span
            class="text-xs text-text-subtle tabular-nums"
            data-testid="income-bulk-settle-coverage"
          >
            Quedan pagados: {{ coverage.paid }} · parciales: {{ coverage.partial }} · sin abono: {{ coverage.skipped }}
          </span>
        </div>

        <BaseFormField label="Notas">
          <BaseTextarea
            v-model="form.notes"
            :rows="2"
            data-testid="income-bulk-settle-notes"
          />
        </BaseFormField>

      </form>
    </div>
    <template #footer>
      <div class="space-y-2 border-t border-border-muted px-4 py-4 panel-portrait:px-6">
        <p
          id="income-bulk-settle-submit-reason"
          class="text-xs text-danger-strong text-right min-h-4"
          aria-live="polite"
          data-testid="income-bulk-settle-submit-reason"
        >
          {{ saving ? '' : submitBlockReason }}
        </p>
        <div class="flex flex-col-reverse items-stretch gap-2 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-end">
          <BaseButton type="button" variant="secondary" @click="emit('close')">
            Cancelar
          </BaseButton>
          <BaseButton
            type="submit" :form="modalFormId"
            :loading="saving"
            :disabled="!canSubmit"
            :disabled-reason="submitBlockReason"
            aria-describedby="income-bulk-settle-submit-reason"
            data-testid="income-bulk-settle-submit"
          >
            {{ saving ? 'Guardando...' : 'Registrar abono' }}
          </BaseButton>
        </div>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { useId, computed, ref, watch } from 'vue';

import BaseBadge from '~/components/base/BaseBadge.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseCurrencyInput from '~/components/base/BaseCurrencyInput.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import { settlementBlockedReason } from '~/utils/incomeSettlement';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseTextarea from '~/components/base/BaseTextarea.vue';
import PeriodDateField from '~/components/accounting/PeriodDateField.vue';
import { clientLabelOf, NO_CLIENT_LABEL } from '~/utils/incomeClients';
import { formatMoney } from '~/utils/formatMoney';
import { joinEs } from '~/utils/spanishList';
import { distributeOldestFirst, sortForSettle } from '~/utils/settleAllocation';
import { todayISO } from '~/utils/periodDates';

/**
 * One abono over several expected incomes: value received, date, note, and
 * the distribution table pre-filled oldest-first. The proposal follows the
 * value live until the operator touches a row; from there the reparto is
 * theirs and "Recalcular reparto" is the way back. Whatever the rows leave
 * of the value becomes the client's saldo a favor — which is why an excess
 * needs an unambiguous client and blocks when the selection mixes them.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  /** Eligible expected rows (the bar already filtered the selection). */
  records: { type: Array, default: () => [] },
  /** Selected rows that did NOT qualify, announced instead of hidden. */
  excludedCount: { type: Number, default: 0 },
  saving: { type: Boolean, default: false },
});

const emit = defineEmits(['close', 'submit']);

const form = ref({ total: null, period_date: '', notes: '' });
const exactDate = ref(true);
const touched = ref(false);
const allocations = ref({});

const orderedRecords = computed(() => sortForSettle(props.records));

const pendingSum = computed(() => props.records.reduce(
  (acc, row) => acc + (Number(row.pending_amount) || 0), 0,
));

const allocatedSum = computed(() => props.records.reduce(
  (acc, row) => acc + (Number(allocations.value[row.id]) || 0), 0,
));

const totalValue = computed(() => Number(form.value.total) || 0);

/** Money the allocations leave over — the saldo a favor the backend books. */
const creditAmount = computed(
  () => Math.max(totalValue.value - allocatedSum.value, 0),
);

const clientLabels = computed(() => {
  const labels = [];
  for (const row of props.records) {
    const label = clientLabelOf(row);
    if (!labels.includes(label)) labels.push(label);
  }
  return labels;
});

const mixedClients = computed(() => clientLabels.value.length > 1);
const clientListLabel = computed(() => joinEs(clientLabels.value));

const excludedNote = computed(() => (
  props.excludedCount === 1
    ? 'Se excluyó 1 seleccionado: requiere saldo pendiente, contabilidad de empresa y, si tiene cliente, una cuenta de cobro emitida.'
    : `Se excluyeron ${props.excludedCount} seleccionados: requieren saldo pendiente, contabilidad de empresa y, si tienen cliente, una cuenta de cobro emitida.`
));

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

function applyProposal() {
  const proposal = distributeOldestFirst(props.records, totalValue.value);
  allocations.value = Object.fromEntries(
    proposal.map((entry) => [entry.income_id, entry.amount]),
  );
}

// Prellenado con la suma de pendientes (el precedente del modal de liquidar:
// suelen pagar exactamente lo pedido) — el caso de cobertura exacta queda a
// cero tipeos.
watch(() => [props.open, props.records], () => {
  if (!props.open || !props.records.length) return;
  exactDate.value = true;
  touched.value = false;
  form.value = {
    total: pendingSum.value,
    period_date: todayISO(),
    notes: '',
  };
  applyProposal();
}, { immediate: true });

watch(() => form.value.total, () => {
  if (!touched.value) applyProposal();
});

function onRowInput(id, value) {
  touched.value = true;
  allocations.value = { ...allocations.value, [id]: value };
}

function recalculate() {
  applyProposal();
  touched.value = false;
}

const rowErrors = computed(() => {
  const errors = {};
  for (const row of props.records) {
    const amount = Number(allocations.value[row.id]) || 0;
    const pending = Number(row.pending_amount) || 0;
    if (amount < 0) {
      errors[row.id] = 'El monto no puede ser negativo.';
    } else if (amount > pending) {
      errors[row.id] = `Supera el pendiente de esta fila por ${money(amount - pending)}.`;
    }
  }
  return errors;
});

const coverage = computed(() => {
  let paid = 0;
  let partial = 0;
  let skipped = 0;
  for (const row of props.records) {
    const amount = Number(allocations.value[row.id]) || 0;
    const pending = Number(row.pending_amount) || 0;
    if (amount <= 0) skipped += 1;
    else if (amount >= pending) paid += 1;
    else partial += 1;
  }
  return { paid, partial, skipped };
});

const creditOwnerClause = computed(() => {
  const owner = clientLabels.value[0];
  return owner && owner !== NO_CLIENT_LABEL
    ? `quedará como saldo a favor de ${owner}.`
    : 'quedará como saldo a favor sin cliente asignado.';
});

const summaryState = computed(() => {
  if (creditAmount.value > 0) {
    return {
      variant: 'warning',
      badge: `Excedente: ${money(creditAmount.value)}`,
      clause: creditOwnerClause.value,
    };
  }
  const uncovered = pendingSum.value - allocatedSum.value;
  if (uncovered > 0) {
    return {
      variant: 'info',
      badge: `Quedan ${money(uncovered)} sin cubrir`,
      clause: 'seguirán pendientes en la selección.',
    };
  }
  return {
    variant: 'success',
    badge: 'Cobro cubierto por completo',
    clause: 'todos los seleccionados quedan pagados.',
  };
});

const submitBlockReason = computed(() => {
  const blocked = props.records.find(row => settlementBlockedReason(row));
  if (blocked) return `${blocked.concept}: ${settlementBlockedReason(blocked)}`;
  if (totalValue.value <= 0) {
    return 'Ingresa un valor recibido mayor a cero.';
  }
  if (props.records.some(
    (row) => (Number(allocations.value[row.id]) || 0) < 0,
  )) {
    return 'Hay montos inválidos en el reparto.';
  }
  if (props.records.some((row) => {
    const amount = Number(allocations.value[row.id]) || 0;
    return amount > (Number(row.pending_amount) || 0);
  })) {
    return 'Hay filas que superan su pendiente: revisa el reparto.';
  }
  if (allocatedSum.value > totalValue.value) {
    return `El reparto suma ${money(allocatedSum.value)} y el valor recibido es ${money(totalValue.value)}. Ajusta las filas o usa Recalcular reparto.`;
  }
  if (allocatedSum.value <= 0) {
    return 'Imputa al menos una fila o reduce el valor.';
  }
  if (creditAmount.value > 0 && mixedClients.value) {
    return 'Con clientes mezclados el excedente no se puede asignar como saldo a favor: ajusta el valor.';
  }
  return '';
});

const canSubmit = computed(() => submitBlockReason.value === '');

function onSubmit() {
  if (props.saving || !canSubmit.value) return;
  emit('submit', {
    total_amount: totalValue.value,
    period_date: form.value.period_date,
    notes: form.value.notes,
    allocations: orderedRecords.value
      .map((row) => ({
        income_id: row.id,
        amount: Number(allocations.value[row.id]) || 0,
      }))
      // Cero = "este ingreso no entra en el abono": fuera del payload, como
      // las filas pristine del modal de liquidar.
      .filter((entry) => entry.amount > 0),
  });
}

const modalFormId = useId();
</script>
