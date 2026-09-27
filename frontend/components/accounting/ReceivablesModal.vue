<template>
  <BaseModal
    :model-value="open"
    kind="workspace"
    title-id="receivables-modal-title"
    @close="emit('close')"
  >
    <div data-testid="receivables-modal">
      <header class="border-b border-border-muted px-4 pb-4 pt-5 panel-portrait:px-6 panel-portrait:pt-6">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h3 id="receivables-modal-title" class="text-lg font-bold text-text-default">
              Pendientes por cobrar
            </h3>
            <p class="mt-1 text-sm text-text-muted">
              Previsión manual sobre ingresos esperados abiertos de la empresa, sin límite de fecha.
            </p>
          </div>
          <ReceivableLegend />
        </div>
      </header>

      <div class="px-4 pt-4 panel-portrait:px-6">
        <BaseTabs
          v-model="activeTab"
          :tabs="tabs"
          aria-label="Secciones de pendientes por cobrar"
        />
      </div>

      <main class="min-h-[360px] px-4 pb-5 panel-portrait:px-6">
        <div v-if="store.receivablesLoading" class="space-y-3 py-4" data-testid="receivables-loading">
          <div class="h-20 rounded-xl bg-surface-raised motion-safe:animate-pulse" />
          <div class="h-44 rounded-xl bg-surface-raised motion-safe:animate-pulse" />
        </div>

        <div v-else-if="store.receivablesError" class="py-10 text-center">
          <p class="text-sm font-medium text-danger-strong">
            No se pudieron cargar los pendientes por cobrar.
          </p>
          <BaseButton class="mt-4" variant="secondary" size="sm" @click="load">
            Reintentar
          </BaseButton>
        </div>

        <template v-else>
          <section v-if="activeTab === 'summary'" class="space-y-5" data-testid="receivables-summary-tab">
            <p class="text-sm text-text-muted">
              Totales originales de los ingresos seleccionados, separados por nivel de confianza.
            </p>
            <article
              v-for="group in confidenceGroups"
              :key="group.key"
              class="overflow-hidden rounded-xl border border-border-muted bg-surface"
              :data-testid="`receivables-group-${group.key}`"
            >
              <div class="flex flex-col gap-3 bg-surface-raised px-3 py-3 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between panel-portrait:px-4">
                <div class="flex items-center gap-2">
                  <ReceivableConfidenceBadge :confidence="group.confidence" />
                  <span class="text-xs text-text-muted">
                    {{ group.summary.count }} {{ group.summary.count === 1 ? 'ingreso' : 'ingresos' }}
                  </span>
                </div>
                <dl class="grid grid-cols-3 gap-3 text-xs panel-portrait:gap-5">
                  <div>
                    <dt class="text-text-muted">Total original</dt>
                    <dd class="font-semibold tabular-nums text-text-default">
                      {{ money(group.summary.total_amount) }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-text-muted">Abonado</dt>
                    <dd class="font-semibold tabular-nums text-text-default">
                      {{ money(group.summary.paid_amount) }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-text-muted">Saldo abierto</dt>
                    <dd class="font-semibold tabular-nums text-warning-strong">
                      {{ money(group.summary.pending_amount) }}
                    </dd>
                  </div>
                </dl>
              </div>
              <div v-if="group.rows.length" class="p-3 panel-portrait:p-4">
                <ReceivableRowsTable :rows="group.rows" />
              </div>
            </article>
          </section>

          <section v-else-if="activeTab === 'selected'" class="space-y-5" data-testid="receivables-selected-tab">
            <StatsSummaryStrip :items="selectedStrip" />
            <p class="text-sm text-text-muted">
              Selección completa definida en “Gestionar candidatos”. Sólo las filas verdes suman en la tarjeta.
            </p>
            <ReceivableRowsTable
              :rows="selectedRows"
              empty-title="Todavía no has seleccionado ingresos para la previsión."
            />
          </section>

          <section v-else class="space-y-4" data-testid="receivables-manage-tab">
            <div class="flex flex-col gap-3 panel-portrait:flex-row panel-portrait:items-end panel-portrait:justify-between">
              <div class="min-w-0 flex-1">
                <label for="receivable-search" class="mb-1 block text-xs font-medium text-text-muted">
                  Buscar ingreso esperado
                </label>
                <BaseInput
                  id="receivable-search"
                  v-model="search"
                  placeholder="Concepto, cliente o proyecto"
                  data-testid="receivables-search"
                />
              </div>
              <div class="flex flex-col items-start gap-2 panel-portrait:items-end">
                <p class="text-xs text-text-muted">
                  {{ filteredCandidates.length }} de {{ store.receivables.length }} candidatos
                </p>
                <div class="flex flex-wrap items-center gap-2">
                  <BaseSegmented
                    :model-value="candidateViewMode"
                    :options="candidateViewOptions"
                    size="sm"
                    aria-label="Vista de candidatos por cobrar"
                    data-testid="receivables-view-mode"
                    @update:model-value="candidateViewMode = $event"
                  />
                  <BaseSegmented
                    v-if="candidateViewMode === 'grouped'"
                    :model-value="candidateGroupBy"
                    :options="candidateGroupOptions"
                    size="sm"
                    aria-label="Agrupar candidatos por cobrar por"
                    data-testid="receivables-group-by"
                    @update:model-value="changeCandidateGroupBy"
                  />
                </div>
              </div>
            </div>
            <div class="rounded-xl border border-border-muted bg-surface-raised p-3 text-xs text-text-muted">
              Elige el nivel de cobro y activa el interruptor sólo cuando quieras incluir el ingreso en la previsión.
              Ambos controles son independientes y cada cambio se guarda de inmediato.
            </div>
            <IncomeGroupedTable
              v-if="candidateViewMode === 'grouped'"
              :columns="groupedCandidateColumns"
              :groups="candidateGroups"
              :collapsed-ids="collapsedCandidateGroupIds"
              :show-actions="false"
              :group-metrics="candidateGroupMetrics"
              :footer-metrics="candidateGroupMetrics"
              :summary-totals="candidateGroupTotals"
              :aria-label="candidateGroupAriaLabel"
              :group-noun="candidateGroupNoun"
              group-test-prefix="receivable-candidate"
              row-noun="candidatos"
              filtered-adjective="filtrados"
              unassigned-badge="sin asignar"
              footer-label="Total de candidatos filtrados"
              @toggle-group="toggleCandidateGroup"
            >
              <template #cell-client_name="{ row }">
                <span>{{ row.client_name || 'Sin cliente' }}</span>
              </template>
              <template #cell-project_name="{ row }">
                <span>{{ row.project_name || 'Sin proyecto' }}</span>
              </template>
              <template #cell-collection_confidence="{ row }">
                <ReceivableStateControl
                  :row="row"
                  :busy="store.receivableUpdatingIds.includes(row.id)"
                  @change="updateState(row, $event)"
                />
              </template>
            </IncomeGroupedTable>
            <ReceivableRowsTable
              v-else
              :rows="filteredCandidates"
              manageable
              :busy-ids="store.receivableUpdatingIds"
              empty-title="No hay ingresos esperados abiertos que coincidan con la búsqueda."
              @change="updateState"
            />
          </section>
        </template>
      </main>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="secondary" @click="emit('close')">Cerrar</BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseTabs from '~/components/base/BaseTabs.vue';
import StatsSummaryStrip from '~/components/stats/StatsSummaryStrip.vue';
import IncomeGroupedTable from '~/components/accounting/IncomeGroupedTable.vue';
import ReceivableConfidenceBadge from '~/components/accounting/ReceivableConfidenceBadge.vue';
import ReceivableLegend from '~/components/accounting/ReceivableLegend.vue';
import ReceivableRowsTable from '~/components/accounting/ReceivableRowsTable.vue';
import ReceivableStateControl from '~/components/accounting/ReceivableStateControl.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useAccountingStore } from '~/stores/accounting';
import {
  buildReceivablesSummary,
  groupReceivables,
  sumReceivableGroups,
} from '~/utils/receivables';
import { formatMoney } from '~/utils/formatMoney';

const props = defineProps({
  open: { type: Boolean, default: false },
});

const emit = defineEmits(['close']);
const store = useAccountingStore();
const notify = usePanelNotify();
const activeTab = ref('summary');
const search = ref('');
const candidateViewMode = ref('grouped');
const candidateGroupBy = ref('client');
const collapsedCandidateGroupIds = ref([]);

const candidateViewOptions = [
  { value: 'grouped', label: 'Agrupado', testId: 'receivables-view-grouped' },
  { value: 'classic', label: 'Clásico', testId: 'receivables-view-classic' },
];
const candidateGroupOptions = [
  { value: 'client', label: 'Cliente', testId: 'receivables-group-client' },
  { value: 'project', label: 'Proyecto', testId: 'receivables-group-project' },
];
const candidateColumns = [
  {
    key: 'concept', label: 'Concepto', size: 'name',
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'client_name', label: 'Cliente', size: 'name',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'project_name', label: 'Proyecto', size: 'name',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'period_label', label: 'Período', size: 'date',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'total_amount', label: 'Total original', format: 'money',
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'paid_amount', label: 'Abonado', format: 'money',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'pending_amount', label: 'Saldo abierto', format: 'money',
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'collection_confidence', label: 'Previsión', size: 'name',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
];
const candidateGroupMetrics = [
  { key: 'total_amount', label: 'Total original', format: 'money', tone: 'default' },
  { key: 'paid_amount', label: 'Abonado', format: 'money', tone: 'success' },
  { key: 'pending_amount', label: 'Saldo abierto', format: 'money', tone: 'warning' },
];

const selectedRows = computed(() =>
  store.receivables.filter((row) => row.is_receivable_candidate),
);
const summary = computed(() =>
  store.receivablesSummary || buildReceivablesSummary(store.receivables),
);

const tabs = computed(() => [
  { id: 'summary', label: 'Por estado', badge: summary.value.selected_count || 0 },
  { id: 'selected', label: 'Selección', badge: selectedRows.value.length },
  { id: 'manage', label: 'Gestionar candidatos', badge: store.receivables.length },
]);

const groupDefinitions = [
  { key: 'high', confidence: 'high' },
  { key: 'medium', confidence: 'medium' },
  { key: 'low', confidence: 'low' },
  { key: 'unclassified', confidence: '' },
];

const confidenceGroups = computed(() =>
  groupDefinitions.map((definition) => ({
    ...definition,
    summary: summary.value.by_confidence?.[definition.key] || {
      count: 0,
      total_amount: 0,
      paid_amount: 0,
      pending_amount: 0,
    },
    rows: selectedRows.value.filter(
      (row) => (row.collection_confidence || 'unclassified') === definition.key,
    ),
  })),
);

const selectedStrip = computed(() => [
  { label: 'Seleccionados', value: String(summary.value.selected_count || 0) },
  { label: 'Total original', value: money(summary.value.selected_total) },
  { label: 'Abonado', value: money(summary.value.paid_total), tone: 'success' },
  { label: 'Saldo abierto', value: money(summary.value.pending_total), tone: 'warning' },
  {
    label: 'Tarjeta (verdes)',
    value: money(summary.value.high_total),
    tone: 'success',
    sub: `${summary.value.high_count || 0} en verde`,
  },
]);

const filteredCandidates = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('es');
  if (!query) return store.receivables;
  return store.receivables.filter((row) =>
    [row.concept, row.client_name, row.project_name, row.period_label]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase('es').includes(query)),
  );
});

const candidateGroups = computed(() =>
  groupReceivables(filteredCandidates.value, candidateGroupBy.value),
);
const candidateGroupTotals = computed(() => sumReceivableGroups(candidateGroups.value));
const groupedCandidateColumns = computed(() => candidateColumns.filter((column) => (
  candidateGroupBy.value === 'client'
    ? column.key !== 'client_name'
    : column.key !== 'project_name'
)));
const candidateGroupNoun = computed(() => (
  candidateGroupBy.value === 'client' ? 'clientes' : 'proyectos'
));
const candidateGroupAriaLabel = computed(() => (
  `Candidatos por cobrar agrupados por ${candidateGroupBy.value === 'client' ? 'cliente' : 'proyecto'}`
));

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

async function load() {
  await store.fetchReceivables();
}

async function updateState(row, payload) {
  const result = await store.updateReceivableState(row.id, payload);
  if (result.success) {
    notify.success({
      title: 'Previsión de cobro actualizada',
      detail: row.concept,
    });
    return;
  }
  notify.error({
    title: 'No se pudo actualizar la previsión',
    detail: result.message || 'Intenta de nuevo.',
  });
}

function toggleCandidateGroup(id) {
  collapsedCandidateGroupIds.value = collapsedCandidateGroupIds.value.includes(id)
    ? collapsedCandidateGroupIds.value.filter((groupId) => groupId !== id)
    : [...collapsedCandidateGroupIds.value, id];
}

function changeCandidateGroupBy(criterion) {
  candidateGroupBy.value = criterion;
  collapsedCandidateGroupIds.value = [];
}

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    activeTab.value = 'summary';
    search.value = '';
    candidateViewMode.value = 'grouped';
    candidateGroupBy.value = 'client';
    collapsedCandidateGroupIds.value = [];
    load();
  },
  { immediate: true },
);
</script>
