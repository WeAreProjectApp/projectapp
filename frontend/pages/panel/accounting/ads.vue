<template>
  <BasePageShell>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Ads</h1>
        <p class="text-sm text-text-subtle mt-1">
          Gastos en publicidad por plataforma y tarjeta de origen.
        </p>
      </div>
      <BaseButton
        variant="primary"
        size="md"
        class="w-full panel-portrait:w-auto"
        data-testid="ads-new-button"
        @click="openCreateModal"
      >
        <BaseActionIcon action="create" />
        <span>Nuevo gasto en Ads</span>
      </BaseButton>
    </div>

    <AccountingSubnav active="ads" />

    <!-- Saved filter tabs -->
    <ProposalFilterTabs
      :tabs="savedTabs"
      :active-tab-id="filterTabId"
      :is-tab-limit-reached="isTabLimitReached"
      @select="selectFilterTab"
      @create="handleCreateFilterTab"
      @rename="renameFilterTab"
      @delete="deleteFilterTab"
      @restore="restoreFilterTab"
      @rebase="rebaseFilterTab"
      @reorder="reorderFilterTabs"
    />

    <!-- Stat card -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
      <AccountingStatCard
        label="Total filtrado"
        :value="money(filteredTotal)"
        :sub="`${filteredRows.length} registro${filteredRows.length === 1 ? '' : 's'}`"
      />
    </div>

    <!-- Filter toggle -->
    <div class="flex items-center justify-end gap-2 mb-5">
      <UiFilterToggleButton
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
      <AccountingExportButton section="ads" :params="exportParams" />
    </div>

    <!-- Filter panel -->
    <AccountingFilterPanel
      :fields="filterFields"
      :model-value="currentFilters"
      :is-open="isFilterPanelOpen"
      :results-count="filteredRows.length"
      :search-value="currentFilters.search"
      @update:model-value="Object.assign(currentFilters, $event)"
      @reset="handleResetFilters"
      @clear-search="searchInput = ''"
    />

    <!-- Error -->
    <AccountingErrorState
      v-if="store.error === 'fetch_failed'"
      title="No se pudieron cargar los gastos en Ads"
      :retrying="store.isLoading"
      @retry="loadRecords"
    />

    <!-- Empty -->
    <BaseEmptyState
      v-else-if="!store.isLoading && filteredRows.length === 0"
      :title="hasActiveFilters ? 'Sin resultados con esos filtros' : 'No hay gastos en Ads aún'"
      :description="hasActiveFilters
        ? 'Ajusta o limpia los filtros para ver más registros.'
        : 'Registra el primer gasto publicitario por plataforma.'"
    >
      <template #actions>
        <BaseButton
          v-if="hasActiveFilters"
          variant="secondary"
          size="sm"
          @click="resetFilters"
        >
          Limpiar filtros
        </BaseButton>
        <BaseButton v-else variant="primary" size="sm" @click="openCreateModal">
          <BaseActionIcon action="create" />
          <span>Nuevo gasto en Ads</span>
        </BaseButton>
      </template>
    </BaseEmptyState>

    <template v-else>
      <AccountingTable
        :loading="store.isLoading"
        :highlight-id="lastMutatedId"
        :columns="columns"
        :rows="pagedRows"
        :highlight-query="currentFilters.search"
        :sort-key="sortKey"
        :sort-dir="sortDir"
        :show-default-actions="false"
        row-actions-layout="menu-start"
        @sort="toggleSort"
      >
        <template #row-actions="{ row }">
          <AccountingRowActionsButton
            :label="`Acciones de ${adSpendLabel(row)}`"
            :test-id="`ads-actions-${row.id}`"
            @open="actionsRow = row"
          />
        </template>
        <template #cell-origin_card="{ row }">
          {{ row.origin_card || '—' }}
        </template>
        <template #cell-accumulated="{ row }">
          <span class="tabular-nums text-text-muted">
            {{ row.accumulated !== null && row.accumulated !== undefined && row.accumulated !== ''
              ? money(row.accumulated)
              : '—' }}
          </span>
        </template>
      </AccountingTable>

      <p class="text-xs text-text-muted mt-2">
        El acumulado se calcula sobre el historial completo.
      </p>

      <BasePagination
        v-if="!store.isLoading && filteredRows.length > 0"
        :current-page="currentPage"
        :total-pages="totalPages"
        :total-items="totalItems"
        :range-from="rangeFrom"
        :range-to="rangeTo"
        class="mt-4"
        @prev="prev"
        @next="next"
        @go="goTo"
      />
    </template>

    <AccountingRowActionsModal
      :open="actionsRow !== null"
      :record="actionsRow"
      :title="actionsRow ? adSpendLabel(actionsRow) : ''"
      :subtitle="adSpendSummary(actionsRow)"
      :actions="adSpendActions"
      test-id-prefix="ads"
      @close="actionsRow = null"
      @select="runAdSpendAction"
    />

    <!-- Create / edit modal -->
    <AdSpendFormModal
      :open="showFormModal"
      :record="editingRecord"
      :saving="store.isUpdating"
      @close="closeFormModal"
      @submit="submitForm"
    />

    <EntityHistoryRecordModal
      :open="historyRow !== null"
      entity-type="ads"
      :record="historyRow"
      @close="historyRow = null"
    />

    <AccountingNoteModal
      :open="noteRow !== null"
      :subtitle="adSpendSummary(noteRow)"
      :notes="noteRow?.notes ?? ''"
      :highlight-query="currentFilters.search"
      @close="noteRow = null"
    />

    <!-- Confirm delete -->
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      :require-type-text="confirmState.requireTypeText"
      :hide-cancel="confirmState.hideCancel"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />
  </BasePageShell>
</template>

<script setup>
import EntityHistoryRecordModal from '~/components/history/EntityHistoryRecordModal.vue';
import { computed, onMounted, ref } from 'vue';
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';
import AccountingRowActionsButton from '~/components/accounting/AccountingRowActionsButton.vue';
import AccountingRowActionsModal from '~/components/accounting/AccountingRowActionsModal.vue';
import AccountingSubnav from '~/components/accounting/AccountingSubnav.vue';
import AccountingStatCard from '~/components/accounting/AccountingStatCard.vue';
import AccountingTable from '~/components/accounting/AccountingTable.vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import AccountingFilterPanel from '~/components/accounting/AccountingFilterPanel.vue';
import AccountingExportButton from '~/components/accounting/AccountingExportButton.vue';
import AdSpendFormModal from '~/components/accounting/AdSpendFormModal.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import UiFilterToggleButton from '~/components/ui/FilterToggleButton.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useAccountingCrudPage } from '~/composables/useAccountingCrudPage';
import {
  useAccountingFilters,
  matchDateRange,
  matchIncludes,
  matchNumberRange,
} from '~/composables/useAccountingFilters';
import { useAccountingStore } from '~/stores/accounting';
import { buildExportParams } from '~/utils/accountingExportParams';
import { leadingRowActions } from '~/utils/accountingRowActions';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';
import { addWeightPct } from '~/utils/percent';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const store = useAccountingStore();
const notify = usePanelNotify();

// -------------------------------------------------------------------
// Filters
// -------------------------------------------------------------------

const {
  currentFilters,
  searchInput,
  isFilterPanelOpen,
  activeFilterCount,
  hasActiveFilters,
  applyFilters,
  resetFilters,
  savedTabs,
  activeTabId: filterTabId,
  isTabLimitReached,
  selectTab: selectFilterTab,
  saveTab,
  deleteTab: deleteFilterTab,
  renameTab: renameFilterTab,
  restoreTab: restoreFilterTab,
  rebaseTab: rebaseFilterTab,
  reorderTabs: reorderFilterTabs,
} = useAccountingFilters({
  viewName: 'accounting_ads',
  defaults: {
    spend_from: '',
    spend_to: '',
    origin_card: [],
    platform: [],
    amount_min: '',
    amount_max: '',
  },
  matchers: {
    spendRange: matchDateRange('spend_date', 'spend_from', 'spend_to'),
    origin_card: matchIncludes('origin_card', 'origin_card'),
    platform: matchIncludes('platform', 'platform'),
    amountRange: matchNumberRange('amount', 'amount_min', 'amount_max'),
  },
});

const originCardOptions = computed(() => {
  const values = new Set();
  store.adsRecords.forEach((record) => {
    if (record.origin_card) values.add(record.origin_card);
  });
  return Array.from(values).sort().map((value) => ({ value, label: value }));
});

const filterFields = computed(() => [
  { kind: 'daterange', minKey: 'spend_from', maxKey: 'spend_to', label: 'Fecha' },
  { kind: 'multi', key: 'origin_card', label: 'Tarjeta', options: originCardOptions.value },
  {
    kind: 'multi',
    key: 'platform',
    label: 'Plataforma',
    options: [
      { value: 'facebook', label: 'Facebook Ads' },
      { value: 'google', label: 'Google Ads' },
      { value: 'other', label: 'Otro' },
    ],
  },
  { kind: 'range', minKey: 'amount_min', maxKey: 'amount_max', label: 'Valor', type: 'money' },
]);

const EXPORT_MAPPING = {
  spend_from: 'date_from',
  spend_to: 'date_to',
  origin_card: 'origin_card',
  platform: 'platform',
  amount_min: 'amount_min',
  amount_max: 'amount_max',
  search: 'q',
};

const exportParams = computed(() =>
  buildExportParams(currentFilters, EXPORT_MAPPING),
);

// -------------------------------------------------------------------
// Data + table (keeps the backend chronological order)
// -------------------------------------------------------------------

// Value and its share of the filtered total are one number in two readings,
// so they group; the server-side accumulated column is another axis.
const columns = [
  {
    key: 'spend_date', label: 'Fecha', format: 'date', sortable: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'platform_label', label: 'Plataforma',
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'origin_card', label: 'Tarjeta',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'amount', label: 'Valor', format: 'money', group: 'money', sortable: true,
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'weight_pct', label: '%', format: 'percent', group: 'money', sortable: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'accumulated', label: 'Acumulado', align: 'right',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
];

const filteredRows = computed(() => applyFilters(store.adsRecords));

const filteredTotal = computed(() =>
  filteredRows.value.reduce((total, record) => total + (Number(record.amount) || 0), 0),
);

// Same base as the "Total filtrado" stat: the visible rows sum to 100%.
const weightedRows = computed(() =>
  addWeightPct(filteredRows.value, (row) => Number(row.amount) || 0),
);

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

const {
  isModalOpen: showFormModal,
  editingRecord,
  openCreateModal,
  lastMutatedId,
  openEditModal,
  closeModal: closeFormModal,
  handleSubmit: submitForm,
  confirmDeleteRecord: confirmDelete,
  confirmState,
  handleConfirmed,
  handleCancelled,
  currentPage,
  totalPages,
  totalItems,
  rangeFrom,
  rangeTo,
  pagedRecords: pagedRows,
  prevPage: prev,
  nextPage: next,
  goToPage: goTo,
  handleCreateFilterTab,
  handleResetFilters,
  sortKey,
  sortDir,
  toggleSort,
} = useAccountingCrudPage({
  entity: 'ads',
  resetPageOn: currentFilters,
  store,
  filteredRecords: weightedRows,
  sortDefaults: { spend_date: 'desc', amount: 'desc', weight_pct: 'desc' },
  saveTab,
  resetFilters,
  isFilterPanelOpen,
  labels: {
    created: 'Gasto en Ads creado',
    updated: 'Gasto en Ads actualizado',
    deleted: 'Gasto en Ads eliminado',
    saveErrorTitle: (editing) =>
      editing ? 'No se pudo actualizar el gasto en Ads' : 'No se pudo crear el gasto en Ads',
    deleteErrorTitle: 'No se pudo eliminar el gasto en Ads',
    deleteTitle: 'Eliminar gasto en Ads',
    deleteMessage: (record) =>
      `Esto eliminará el gasto del ${record.spend_date} por ${money(record.amount)} ` +
      'de forma permanente. Esta acción no se puede deshacer.',
  },
  // Refetch: the accumulated column depends on the full history order.
  onAfterMutation: loadRecords,
});

// ── Row actions ──
// One kebab per row in the leading track; its menu owns Detalle e historial,
// Ver nota (when the spend has one), Editar and Eliminar.

const actionsRow = ref(null);
const historyRow = ref(null);
const noteRow = ref(null);

function adSpendLabel(row) {
  return `${row.platform_label || row.platform || 'Ads'} del ${formatDate(row.spend_date)}`;
}

function adSpendSummary(row) {
  return row ? `${formatDate(row.spend_date)} · ${money(row.amount)}` : '';
}

const adSpendActions = computed(() => (actionsRow.value
  ? [
    ...leadingRowActions(actionsRow.value),
    { id: 'edit', action: 'edit', label: 'Editar' },
    { id: 'delete', action: 'delete', label: 'Eliminar', danger: true },
  ]
  : []));

const adSpendActionHandlers = {
  history: (row) => { historyRow.value = row; },
  notes: (row) => { noteRow.value = row; },
  edit: (row) => openEditModal(row),
  delete: (row) => confirmDelete(row),
};

function runAdSpendAction(id, row) {
  adSpendActionHandlers[id]?.(row);
}

async function loadRecords() {
  const result = await store.fetchRecords('ads');
  if (!result.success) {
    notify.error({ title: 'No se pudieron cargar los gastos en Ads', detail: result.message });
  }
}

onMounted(loadRecords);
usePanelRefresh(loadRecords);
</script>
