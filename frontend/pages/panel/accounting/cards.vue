<template>
  <BasePageShell>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Tarjetas</h1>
        <p class="text-sm text-text-subtle mt-1">
          Registros semanales de disponible y deuda de las tarjetas de crédito.
        </p>
      </div>
      <BaseButton
        variant="primary"
        size="md"
        class="w-full panel-portrait:w-auto"
        data-testid="cards-new-button"
        @click="openCreateModal"
      >
        <BaseActionIcon action="create" />
        <span>Nuevo registro</span>
      </BaseButton>
    </div>

    <AccountingSubnav active="cards" />

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

    <!-- Search + Filter toggle + Export -->
    <div class="flex flex-wrap items-center gap-2 mb-5">
      <BaseInput
        v-model="searchInput"
        type="text"
        placeholder="Buscar por tarjeta o notas..."
        data-testid="cards-search-input"
        class="w-full sm:max-w-xs"
      />
      <UiFilterToggleButton
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
      <AccountingExportButton section="card_snapshot" :params="exportParams" />
    </div>

    <!-- Filter panel -->
    <AccountingFilterPanel
      :fields="filterFields"
      :model-value="currentFilters"
      :is-open="isFilterPanelOpen"
      :results-count="filteredRecords.length"
      :search-value="currentFilters.search"
      @update:model-value="Object.assign(currentFilters, $event)"
      @reset="handleResetFilters"
      @clear-search="searchInput = ''"
    />

    <!-- Summary chip (latest debt per card over filtered rows) -->
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <span
        class="text-xs px-2.5 py-1 rounded-full bg-danger-soft text-danger-strong font-medium tabular-nums"
        data-testid="cards-total-debt"
        title="La columna % es la utilización del cupo: deuda de la fila / cupo de su tarjeta"
      >
        Deuda total (últimos por tarjeta): {{ formatMoney(latestDebtTotal) }}
      </span>
    </div>

    <!-- Error -->
    <AccountingErrorState
      v-if="store.error === 'fetch_failed'"
      title="No se pudieron cargar los registros de tarjetas"
      :retrying="store.isLoading"
      @retry="loadRecords"
    />

    <!-- Empty -->
    <BaseEmptyState
      v-else-if="!store.isLoading && filteredRecords.length === 0"
      :title="hasActiveFilters ? 'Sin resultados con esos filtros' : 'No hay registros de tarjetas aún'"
      :description="hasActiveFilters
        ? 'Ajusta o limpia los filtros para ver más registros.'
        : 'Registra el primer snapshot de disponible y deuda.'"
    >
      <template #actions>
        <BaseButton
          v-if="hasActiveFilters"
          variant="secondary"
          size="sm"
          @click="handleResetFilters"
        >
          Limpiar filtros
        </BaseButton>
        <BaseButton v-else variant="primary" size="sm" @click="openCreateModal">
          <BaseActionIcon action="create" />
          <span>Nuevo registro</span>
        </BaseButton>
      </template>
    </BaseEmptyState>

    <!-- Table -->
    <template v-else>
      <AccountingTable
        :loading="store.isLoading"
        :highlight-id="lastMutatedId"
        :columns="columns"
        :rows="pagedRecords"
        :highlight-query="currentFilters.search"
        :sort-key="sortKey"
        :sort-dir="sortDir"
        :show-default-actions="false"
        row-actions-layout="menu-start"
        @sort="toggleSort"
      >
        <template #row-actions="{ row }">
          <AccountingRowActionsButton
            :label="`Acciones de ${snapshotLabel(row)}`"
            :test-id="`cards-actions-${row.id}`"
            @open="actionsRow = row"
          />
        </template>
        <template #cell-debt_amount="{ row }">
          <span class="tabular-nums text-danger-strong">
            {{ formatMoney(Number(row.debt_amount)) }}
          </span>
        </template>
        <template #cell-notes="{ row }">
          <BaseButton
            v-if="row.notes?.trim()"
            variant="ghost"
            size="sm"
            :aria-label="`Ver nota de ${snapshotLabel(row)}`"
            :data-testid="`cards-notes-${row.id}`"
            @click="noteRow = row"
          >
            <BaseActionIcon action="notes" />
            <span>Ver nota</span>
          </BaseButton>
          <span v-else class="text-text-subtle">—</span>
        </template>
      </AccountingTable>

      <BasePagination
        v-if="!store.isLoading"
        :current-page="currentPage"
        :total-pages="totalPages"
        :total-items="totalItems"
        :range-from="rangeFrom"
        :range-to="rangeTo"
        class="mt-4"
        @prev="prevPage"
        @next="nextPage"
        @go="goToPage"
      />
    </template>

    <!-- Create/edit modal -->
    <CardSnapshotFormModal
      :open="isModalOpen"
      :record="editingRecord"
      :saving="store.isUpdating"
      :cards="activeCatalogCards"
      @close="closeModal"
      @submit="handleSubmit"
    />

    <AccountingRowActionsModal
      :open="actionsRow !== null"
      :record="actionsRow"
      :title="actionsRow?.card_name || `Registro de tarjeta #${actionsRow?.id}`"
      :subtitle="actionsSubtitle"
      :actions="SNAPSHOT_ROW_ACTIONS"
      test-id-prefix="cards"
      @close="actionsRow = null"
      @select="runSnapshotAction"
    />

    <EntityHistoryRecordModal
      :open="historyRow !== null"
      entity-type="card_snapshot"
      :record="historyRow"
      @close="historyRow = null"
    />

    <AccountingNoteModal
      :open="noteRow !== null"
      :subtitle="noteSubtitle"
      :notes="noteRow?.notes ?? ''"
      :highlight-query="currentFilters.search"
      @close="noteRow = null"
    />

    <!-- Confirm modal for delete -->
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
import ConfirmModal from '~/components/ConfirmModal.vue';
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';
import AccountingSubnav from '~/components/accounting/AccountingSubnav.vue';
import AccountingTable from '~/components/accounting/AccountingTable.vue';
import AccountingRowActionsButton from '~/components/accounting/AccountingRowActionsButton.vue';
import AccountingRowActionsModal from '~/components/accounting/AccountingRowActionsModal.vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import AccountingFilterPanel from '~/components/accounting/AccountingFilterPanel.vue';
import AccountingExportButton from '~/components/accounting/AccountingExportButton.vue';
import CardSnapshotFormModal from '~/components/accounting/CardSnapshotFormModal.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useAccountingCrudPage } from '~/composables/useAccountingCrudPage';
import {
  useAccountingFilters,
  matchDateRange,
  matchNumberRange,
  matchIncludes,
} from '~/composables/useAccountingFilters';
import { useAccountingStore } from '~/stores/accounting';
import { buildExportParams } from '~/utils/accountingExportParams';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';
import { HISTORY_ROW_ACTION } from '~/utils/accountingRowActions';
import { percentOf } from '~/utils/percent';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const store = useAccountingStore();

// -------------------------------------------------------------------
// Filters
// -------------------------------------------------------------------

const {
  currentFilters,
  searchInput,
  savedTabs,
  activeTabId: filterTabId,
  isFilterPanelOpen,
  hasActiveFilters,
  activeFilterCount,
  isTabLimitReached,
  applyFilters,
  resetFilters,
  selectTab: selectFilterTab,
  saveTab,
  deleteTab: deleteFilterTab,
  renameTab: renameFilterTab,
  restoreTab: restoreFilterTab,
  rebaseTab: rebaseFilterTab,
  reorderTabs: reorderFilterTabs,
} = useAccountingFilters({
  viewName: 'accounting_cards',
  defaults: {
    dateAfter: '',
    dateBefore: '',
    debtMin: '',
    debtMax: '',
    cardName: [],
  },
  matchers: {
    date: matchDateRange('snapshot_date', 'dateAfter', 'dateBefore'),
    debt: matchNumberRange('debt_amount', 'debtMin', 'debtMax'),
    cardName: matchIncludes('card_name', 'cardName'),
  },
  searchFields: ['card_name', 'notes'],
});

// Filter options: catalog cards (so a registered card is filterable before
// its first snapshot) plus names already used by snapshots (so historical
// cards no longer in the catalog stay reachable — card_name is free text
// with no FK on purpose).
const knownCards = computed(() =>
  [...new Set([
    ...store.creditCards.map((card) => card.name),
    ...store.cardSnapshots.map((r) => r.card_name),
  ])].sort(),
);

const activeCatalogCards = computed(() =>
  store.creditCards.filter((card) => card.is_active),
);

const filterFields = computed(() => [
  { kind: 'daterange', label: 'Fecha', minKey: 'dateAfter', maxKey: 'dateBefore' },
  { kind: 'range', label: 'Deuda', minKey: 'debtMin', maxKey: 'debtMax', type: 'money' },
  {
    kind: 'multi',
    key: 'cardName',
    label: 'Tarjeta',
    options: knownCards.value.map((card) => ({ value: card, label: card })),
  },
]);

const EXPORT_MAPPING = {
  dateAfter: 'date_from',
  dateBefore: 'date_to',
  debtMin: 'amount_min',
  debtMax: 'amount_max',
  cardName: 'card_name',
  search: 'q',
};

const exportParams = computed(() =>
  buildExportParams(currentFilters, EXPORT_MAPPING),
);

// -------------------------------------------------------------------
// Data + CRUD controller (modal, delete confirm, pagination)
// -------------------------------------------------------------------

const filteredRecords = computed(() => applyFilters(store.cardSnapshots));

const latestDebtTotal = computed(() => {
  const latestByCard = new Map();
  for (const row of filteredRecords.value) {
    const current = latestByCard.get(row.card_name);
    if (!current || row.snapshot_date > current.snapshot_date) {
      latestByCard.set(row.card_name, row);
    }
  }
  return [...latestByCard.values()].reduce(
    (sum, row) => sum + (Number(row.debt_amount) || 0),
    0,
  );
});

// The % is each snapshot's credit utilization: its debt over ITS card's
// credit limit from the catalog, so every row (historical included) reads as
// "how full was this card then". Cards no longer in the catalog have no
// known limit and show 0%.
const creditLimitByName = computed(() => {
  const limits = new Map();
  for (const card of store.creditCards) {
    limits.set(card.name, Number(card.credit_limit) || 0);
  }
  return limits;
});

const weightedRecords = computed(() =>
  filteredRecords.value.map((row) => ({
    ...row,
    weight_pct: percentOf(
      Number(row.debt_amount) || 0,
      creditLimitByName.value.get(row.card_name) || 0,
    ),
  })),
);

const {
  isModalOpen,
  editingRecord,
  openCreateModal,
  lastMutatedId,
  openEditModal,
  closeModal,
  handleSubmit,
  confirmDeleteRecord,
  confirmState,
  handleConfirmed,
  handleCancelled,
  currentPage,
  totalPages,
  totalItems,
  rangeFrom,
  rangeTo,
  pagedRecords,
  prevPage,
  nextPage,
  goToPage,
  handleCreateFilterTab,
  handleResetFilters,
  sortKey,
  sortDir,
  toggleSort,
} = useAccountingCrudPage({
  entity: 'cards',
  resetPageOn: currentFilters,
  store,
  filteredRecords: weightedRecords,
  sortDefaults: {
    snapshot_date: 'desc',
    available_amount: 'desc',
    debt_amount: 'desc',
    weight_pct: 'desc',
  },
  saveTab,
  resetFilters,
  isFilterPanelOpen,
  labels: {
    entityName: 'registro de tarjeta',
    created: 'Registro de tarjeta creado',
    updated: 'Registro de tarjeta actualizado',
    deleted: 'Registro de tarjeta eliminado',
    saveErrorTitle: 'No se pudo guardar',
    deleteErrorTitle: 'No se pudo eliminar',
    deleteTitle: 'Eliminar registro de tarjeta',
    deleteMessage: (record) =>
      `Esto eliminará el registro de "${record.card_name}" del ${record.snapshot_date} de forma permanente. Esta acción no se puede deshacer.`,
  },
});

const columns = [
  {
    key: 'card_name', label: 'Tarjeta', sortable: true,
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'snapshot_date', label: 'Fecha', sortable: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'available_amount', label: 'Disponible', format: 'money', sortable: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'debt_amount', label: 'Deuda', format: 'money', group: 'money', sortable: true,
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'weight_pct', label: '%', format: 'percent', group: 'money', sortable: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    // The cell renders a "Ver nota" button: a long note used to stretch the
    // whole row, so the text itself lives in AccountingNoteModal.
    key: 'notes', label: 'Notas',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
];

// ── Row actions, detail/history and notes ──
// One kebab per row in the leading track, which fits nothing else; its modal
// owns Detalle e historial, Editar and Eliminar. The note has its own column
// here (the operator asked for it), so the menu does not repeat it.

const SNAPSHOT_ROW_ACTIONS = [
  HISTORY_ROW_ACTION,
  { id: 'edit', action: 'edit', label: 'Editar' },
  { id: 'delete', action: 'delete', label: 'Eliminar', danger: true },
];

const actionsRow = ref(null);
const historyRow = ref(null);
const noteRow = ref(null);

function snapshotLabel(row) {
  return `${row.card_name} del ${formatDate(row.snapshot_date)}`;
}

const actionsSubtitle = computed(() => (actionsRow.value
  ? `${formatDate(actionsRow.value.snapshot_date)} · Deuda ${formatMoney(Number(actionsRow.value.debt_amount ?? 0))}`
  : ''));

const snapshotActionHandlers = {
  history: (row) => { historyRow.value = row; },
  edit: (row) => openEditModal(row),
  delete: (row) => confirmDeleteRecord(row),
};

function runSnapshotAction(id, row) {
  snapshotActionHandlers[id]?.(row);
}

const noteSubtitle = computed(() => (noteRow.value
  ? `${noteRow.value.card_name} · ${formatDate(noteRow.value.snapshot_date)}`
  : ''));

async function loadRecords() {
  await Promise.all([
    store.fetchRecords('cards'),
    store.fetchRecords('creditCards'),
  ]);
}

// Default view: the registered (active catalog) cards, shown as removable
// filter chips rather than a silent cut — historical card names reappear by
// clearing the filter. Applied once per visit, only from onMounted (never on
// a panel refresh, which must not undo the user clearing the filter), and
// never over a saved tab restored from the URL or filters already touched.
// It cannot go in `defaults:` — a filter sitting on its default is inactive.
function applyDefaultCardFilter() {
  if (filterTabId.value === 'all' && currentFilters.cardName.length === 0) {
    currentFilters.cardName = activeCatalogCards.value.map((card) => card.name);
  }
}

onMounted(async () => {
  await loadRecords();
  applyDefaultCardFilter();
});
usePanelRefresh(loadRecords);
</script>
