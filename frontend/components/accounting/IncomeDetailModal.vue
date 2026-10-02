<template>
  <!--
    Esc and the backdrop are disabled while the reparto is open on top: the
    BaseModal keydown handler lives on `window`, so without this Escape would
    close BOTH modals and yank the detail out from under the operator. Same
    guard ClientEmailsModal uses for its preview.
  -->
  <BaseModal
    :model-value="open"
    kind="detail"
    size="xl"
    title-id="income-detail-title"
    :close-on-esc="!allocationsOpen"
    :close-on-backdrop="!allocationsOpen"
    @close="emit('close')"
  >
    <div data-testid="income-detail-modal">
      <EntityHistorySection v-if="open && income?.id" entity-type="income" :object-id="income.id" class="mx-5" />
      <div class="px-6 pt-6 pb-4 border-b border-border-muted">
        <h3 id="income-detail-title" class="text-lg font-bold text-text-default">
          {{ income?.concept || 'Ingreso' }}
        </h3>
        <p class="text-sm text-text-muted mt-1">
          {{ income?.client_name || 'Sin cliente' }}
          <span v-if="income?.project_name"> · {{ income.project_name }}</span>
          · {{ income?.period_label }}
        </p>
      </div>

      <div class="px-6 py-5 space-y-6">
        <p v-if="loading" class="text-sm text-text-subtle py-4">Cargando el ingreso...</p>
        <p
          v-else-if="error"
          class="text-sm text-danger-strong py-4"
          data-testid="income-detail-error"
        >
          No se pudo cargar el ingreso. Cierra el modal e intenta de nuevo.
        </p>

        <template v-else-if="income">
          <VatBreakdown :total="income.total_amount" :rate="income.vat_rate" />
          <!-- Cifras -->
          <section class="grid gap-4 sm:grid-cols-4">
            <div>
              <p class="text-xs uppercase tracking-wider text-text-subtle">Total</p>
              <p class="text-sm text-text-default mt-1 tabular-nums" data-testid="income-detail-total">
                {{ money(income.total_amount) }}
              </p>
            </div>
            <div>
              <p class="text-xs uppercase tracking-wider text-text-subtle">Abonado</p>
              <p class="text-sm text-text-muted mt-1 tabular-nums">
                {{ income.paid_amount === null ? '—' : money(income.paid_amount) }}
              </p>
            </div>
            <div>
              <p class="text-xs uppercase tracking-wider text-text-subtle">Pendiente</p>
              <p class="text-sm text-warning-strong mt-1 tabular-nums font-semibold">
                {{ income.pending_amount === null ? '—' : money(income.pending_amount) }}
              </p>
            </div>
            <div>
              <p class="text-xs uppercase tracking-wider text-text-subtle">Estado</p>
              <div class="mt-1" data-testid="income-detail-status">
                <IncomePaymentStateCell :row="income" />
              </div>
            </div>
          </section>

          <section data-testid="income-detail-receivable">
            <h4 class="mb-2 text-sm font-semibold text-text-default">Previsión de cobro</h4>
            <div v-if="receivableApplies" class="flex flex-wrap items-center gap-2">
              <ReceivableConfidenceBadge :confidence="income.collection_confidence" />
              <span
                class="rounded-full border px-2.5 py-1 text-xs font-medium"
                :class="income.is_receivable_candidate
                  ? 'border-success-soft bg-success-soft text-success-strong'
                  : 'border-border-muted bg-surface-raised text-text-muted'"
                data-testid="income-detail-receivable-selection"
              >
                {{ income.is_receivable_candidate ? 'Incluido en la previsión' : 'Fuera de la previsión' }}
              </span>
            </div>
            <div
              v-else-if="income.collection_confidence"
              class="flex flex-wrap items-center gap-2"
            >
              <ReceivableConfidenceBadge :confidence="income.collection_confidence" />
              <span class="text-xs text-text-muted">Clasificación histórica · No aplica</span>
            </div>
            <p v-else class="text-sm text-text-subtle">No aplica</p>
          </section>

          <!-- Split de socios: lo que dejó de ocupar dos columnas en la tabla -->
          <section class="grid gap-4 sm:grid-cols-3 text-sm" data-testid="income-detail-split">
            <div>
              <span class="text-text-subtle">Gustavo:</span>
              <span class="text-text-default tabular-nums ml-1">{{ money(income.gustavo_amount) }}</span>
            </div>
            <div>
              <span class="text-text-subtle">Carlos:</span>
              <span class="text-text-default tabular-nums ml-1">{{ money(income.carlos_amount) }}</span>
            </div>
            <div>
              <span class="text-text-subtle">Empresa:</span>
              <span class="text-text-default tabular-nums ml-1">{{ money(income.company_amount) }}</span>
            </div>
          </section>

          <!-- Cuenta de cobro vinculada -->
          <section v-if="cuenta" data-testid="income-detail-collection">
            <h4 class="text-sm font-semibold text-text-default mb-1">Cuenta de cobro</h4>
            <p class="text-sm text-text-muted">
              {{ cuenta.public_number }} · {{ money(cuenta.total) }}
              · emitida {{ formatDate(cuenta.issue_date) }}
            </p>
          </section>

          <!-- Historial de liquidación -->
          <section>
            <h4 class="text-sm font-semibold text-text-default mb-2">
              Historial de liquidación
            </h4>
            <p
              v-if="!settlements.length"
              class="text-sm text-text-subtle"
              data-testid="income-detail-settlements-empty"
            >
              Sin liquidaciones registradas.
            </p>
            <div v-else class="overflow-x-auto">
              <table class="w-full min-w-[460px] text-sm">
                <thead>
                  <tr class="text-left text-xs text-text-subtle uppercase tracking-wider">
                    <th class="px-3 py-2">Fecha</th>
                    <th class="px-3 py-2">Concepto</th>
                    <th class="px-3 py-2">Tipo</th>
                    <th class="px-3 py-2">Movimiento</th>
                    <th class="px-3 py-2 text-right">Monto</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in settlements"
                    :key="`${row.kind}-${row.id}`"
                    class="border-t border-border-muted"
                    data-testid="income-detail-settlement-row"
                  >
                    <td class="px-3 py-2 text-text-muted text-xs whitespace-nowrap">
                      {{ formatDate(row.date) }}
                    </td>
                    <td class="px-3 py-2 text-text-default">{{ row.concept }}</td>
                    <td class="px-3 py-2 text-text-muted text-xs">{{ row.label }}</td>
                    <!--
                      Qué movimiento del bolsillo pagó esta línea. Un abono
                      compartido abre el reparto completo — con los hermanos,
                      que es lo que no se podía ver desde acá: el mismo control
                      y la misma etiqueta que el listado del bolsillo, para que
                      el operador aprenda uno solo.
                    -->
                    <td class="px-3 py-2 text-xs">
                      <BaseButton
                        v-if="row.movement?.is_shared"
                        variant="ghost"
                        size="sm"
                        :data-testid="`income-detail-movement-${row.id}`"
                        @click="openAllocations(row.movement)"
                      >
                        Abono · {{ row.movement.allocation_count }} ingresos
                      </BaseButton>
                      <span
                        v-else-if="row.movement"
                        class="text-text-muted"
                        :data-testid="`income-detail-movement-${row.id}`"
                      >
                        {{ row.movement.concept }}
                        · {{ formatDate(row.movement.movement_date) }}
                      </span>
                      <!-- Sin movimiento es información: ese dinero no pasó
                           por el bolsillo y no es rastreable en el ledger. -->
                      <span v-else class="text-text-subtle" title="No pasó por el bolsillo">—</span>
                    </td>
                    <td class="px-3 py-2 text-right tabular-nums text-text-default">
                      {{ money(row.amount) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>
      </div>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton
          v-if="income"
          variant="secondary"
          data-testid="income-detail-duplicate"
          @click="emit('duplicate', income)"
        >
          Duplicar
        </BaseButton>
        <BaseButton variant="primary" @click="emit('close')">Cerrar</BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>

  <!--
    Apilado, no anidado en el slot: es como el repo apila modales
    (CollectionAccountFormModal hace lo mismo con IncomeFormModal). El de
    reparto es exactamente el del bolsillo, alimentado por el mismo payload.
  -->
  <PocketMovementAllocationsModal
    :open="allocationsOpen"
    :movement="allocationsMovement"
    @close="allocationsMovement = null"
  />
</template>

<script setup>
import VatBreakdown from './VatBreakdown.vue';
import EntityHistorySection from '~/components/history/EntityHistorySection.vue';
import { computed, ref, watch } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import IncomePaymentStateCell from '~/components/accounting/IncomePaymentStateCell.vue';
import PocketMovementAllocationsModal from '~/components/accounting/PocketMovementAllocationsModal.vue';
import ReceivableConfidenceBadge from '~/components/accounting/ReceivableConfidenceBadge.vue';
import { useAccountingStore } from '~/stores/accounting';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';

/**
 * One income, read-only: amounts, status, dates, client, project, the
 * partner split the table no longer has room for, and the settlement
 * history — which needed a backend endpoint, because the liquid children of
 * an expected income were unreachable from the panel until now.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  incomeId: { type: [Number, String], default: null },
});

const emit = defineEmits(['close', 'duplicate']);

const store = useAccountingStore();
const detail = ref(null);
const loading = ref(false);
const error = ref(false);

const income = computed(() => detail.value?.income ?? null);
const cuenta = computed(() => detail.value?.collection_account ?? null);
const receivableApplies = computed(() => (
  income.value?.kind === 'expected' && income.value?.ledger === 'company'
));

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

/**
 * El movimiento cuyo reparto se está mirando, o null. Derivar `open` de él en
 * vez de llevar un segundo booleano evita el parpadeo de payload viejo al
 * cerrar.
 */
const allocationsMovement = ref(null);
const allocationsOpen = computed(() => allocationsMovement.value !== null);

function openAllocations(movement) {
  allocationsMovement.value = movement;
}

const settlements = computed(() => {
  const liquid = (detail.value?.liquid ?? []).map((row) => ({
    id: row.id,
    kind: 'liquid',
    concept: row.concept,
    amount: row.total_amount,
    date: row.period_date,
    // Un hijo nacido de un abono compartido dejaba de distinguirse de una
    // liquidación cualquiera; la etiqueta sola ya cierra media brecha.
    label: row.movement?.is_shared ? 'Abono' : 'Liquidación',
    movement: row.movement ?? null,
  }));
  const deductions = (detail.value?.expenses ?? []).map((row) => ({
    id: row.id,
    kind: 'deduction',
    concept: row.concept,
    amount: row.total_amount,
    date: row.period_date,
    label: row.deduction_type_label || 'Deducción',
    // Una deducción acredita el bruto sin pasar por el bolsillo.
    movement: null,
  }));
  return [...liquid, ...deductions].sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  );
});

async function load() {
  detail.value = null;
  error.value = false;
  // El reparto que estuviera abierto pertenece al ingreso anterior.
  allocationsMovement.value = null;
  if (!props.incomeId) return;
  loading.value = true;
  const result = await store.fetchIncomeDetail(props.incomeId);
  loading.value = false;
  if (result.success) detail.value = result.data;
  else error.value = true;
}

watch(
  () => [props.open, props.incomeId],
  () => {
    if (props.open) load();
  },
  { immediate: true },
);
</script>
