<template>
  <BaseModal
    :model-value="open"
    kind="detail"
    size="xl"
    title-id="income-client-totals-title"
    @close="emit('close')"
  >
    <div class="px-6 pt-6 pb-2" data-testid="income-client-totals-modal">
      <h3 id="income-client-totals-title" class="text-lg font-bold text-text-default">
        Totales por cliente
      </h3>
      <p class="text-sm text-text-muted mt-1">
        Sobre los {{ rows.length }} ingresos que cumplen los filtros activos.
        Facturado son los esperados; cobrado, los líquidos.
      </p>
    </div>

    <div class="px-6 py-4 space-y-4">
      <p v-if="groups.length === 0" class="text-sm text-text-subtle py-4">
        Sin ingresos que totalizar con los filtros actuales.
      </p>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[640px] text-sm">
          <thead>
            <tr class="text-left text-xs text-text-subtle uppercase tracking-wider">
              <th class="px-3 py-2">Cliente</th>
              <th class="px-3 py-2 text-right">Ingresos</th>
              <th class="px-3 py-2 text-right">Facturado</th>
              <th class="px-3 py-2 text-right">Cobrado</th>
              <th class="px-3 py-2 text-right">Pendiente</th>
              <th class="px-3 py-2 text-right">%</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="group in groups"
              :key="group.id"
              class="border-t border-border-muted"
              :data-testid="`income-client-row-${group.id}`"
            >
              <!-- Capping the name is what keeps a long client from widening
                   its column and wrapping the amounts mid figure; the badge
                   stays out of the cap so it never gets clipped. -->
              <td class="px-3 py-2 text-text-default">
                <div class="flex items-center gap-1">
                  <span class="max-w-[220px] truncate">{{ group.name }}</span>
                  <span
                    v-if="group.id === NO_CLIENT_KEY"
                    class="flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded-full font-semibold uppercase tracking-wider bg-warning-soft text-warning-strong"
                  >
                    por completar
                  </span>
                </div>
              </td>
              <td class="px-3 py-2 text-right tabular-nums whitespace-nowrap text-text-muted">
                {{ group.count }}
              </td>
              <td class="px-3 py-2 text-right tabular-nums whitespace-nowrap text-text-default">
                {{ money(group.billed) }}
              </td>
              <td class="px-3 py-2 text-right tabular-nums whitespace-nowrap text-success-strong">
                {{ money(group.collected) }}
              </td>
              <td
                class="px-3 py-2 text-right tabular-nums whitespace-nowrap font-semibold text-warning-strong"
              >
                {{ money(group.pending) }}
              </td>
              <td class="px-3 py-2 text-right tabular-nums whitespace-nowrap text-text-muted">
                {{ formatPercent(group.weightPct) }}
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr class="border-t border-border-default font-semibold">
              <td class="px-3 py-2 text-text-default">Total</td>
              <td class="px-3 py-2 text-right tabular-nums text-text-muted">
                {{ sums.count }}
              </td>
              <td
                class="px-3 py-2 text-right tabular-nums text-text-default"
                data-testid="income-client-billed-sum"
              >
                {{ money(sums.billed) }}
              </td>
              <td class="px-3 py-2 text-right tabular-nums text-success-strong">
                {{ money(sums.collected) }}
              </td>
              <td
                class="px-3 py-2 text-right tabular-nums text-warning-strong"
                data-testid="income-client-pending-sum"
              >
                {{ money(sums.pending) }}
              </td>
              <td class="px-3 py-2"></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <!-- Hostings: the standing monthly cost each client carries -->
      <div v-if="hostingGroups.length" data-testid="hosting-client-totals">
        <p class="text-sm font-medium text-text-default mb-2">Hostings por cliente</p>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[560px] text-sm">
            <thead>
              <tr class="text-left text-xs text-text-subtle uppercase tracking-wider">
                <th class="px-3 py-2">Cliente</th>
                <th class="px-3 py-2 text-right">Hostings</th>
                <th class="px-3 py-2 text-right">Valor/mes activo</th>
                <th class="px-3 py-2 text-right">Total pagado</th>
                <th class="px-3 py-2 text-right">%</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="group in hostingGroups"
                :key="group.id"
                class="border-t border-border-muted"
                :data-testid="`hosting-client-row-${group.id}`"
              >
                <td class="px-3 py-2 text-text-default">
                  {{ group.name }}
                  <span
                    v-if="group.id === NO_CLIENT_KEY"
                    class="ml-1 text-[10px] px-1.5 py-0.5 rounded-full font-semibold uppercase tracking-wider bg-warning-soft text-warning-strong"
                  >
                    por vincular
                  </span>
                </td>
                <td class="px-3 py-2 text-right tabular-nums text-text-muted">
                  {{ group.count }}
                </td>
                <td class="px-3 py-2 text-right tabular-nums text-text-default">
                  {{ money(group.monthly) }}
                </td>
                <td class="px-3 py-2 text-right tabular-nums text-success-strong">
                  {{ money(group.paid) }}
                </td>
                <td class="px-3 py-2 text-right tabular-nums text-text-muted">
                  {{ formatPercent(group.weightPct) }}
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="border-t border-border-default font-semibold">
                <td class="px-3 py-2 text-text-default">Total</td>
                <td class="px-3 py-2 text-right tabular-nums text-text-muted">
                  {{ hostingSums.count }}
                </td>
                <td
                  class="px-3 py-2 text-right tabular-nums text-text-default"
                  data-testid="hosting-client-monthly-sum"
                >
                  {{ money(hostingSums.monthly) }}
                </td>
                <td class="px-3 py-2 text-right tabular-nums text-success-strong">
                  {{ money(hostingSums.paid) }}
                </td>
                <td class="px-3 py-2"></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="secondary" @click="emit('close')">Cerrar</BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed } from 'vue';
import {
  NO_CLIENT_KEY,
  groupByClient,
  groupHostingsByClient,
  sumClientGroups,
  withClientWeights,
} from '~/utils/incomeClients';
import { formatMoney } from '~/utils/formatMoney';
import { formatPercent } from '~/utils/percent';

/**
 * Read-only breakdown of the filtered incomes by client. It totals what the
 * page is already showing, so the period and every active filter carry over
 * without this modal knowing anything about them.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  /** The FILTERED income rows the table is showing. */
  rows: { type: Array, default: () => [] },
  /** All hostings of those clients (unfiltered: they are a standing cost,
   *  not something the income period narrows). */
  hostingRows: { type: Array, default: () => [] },
});

const emit = defineEmits(['close']);

const groups = computed(() => withClientWeights(groupByClient(props.rows)));
const sums = computed(() => sumClientGroups(groups.value));

const hostingGroups = computed(
  () => withClientWeights(groupHostingsByClient(props.hostingRows), 'monthly'),
);
const hostingSums = computed(() => hostingGroups.value.reduce(
  (totals, group) => ({
    count: totals.count + group.count,
    monthly: totals.monthly + group.monthly,
    paid: totals.paid + group.paid,
  }),
  { count: 0, monthly: 0, paid: 0 },
));

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}
</script>
