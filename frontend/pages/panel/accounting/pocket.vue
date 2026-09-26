<template>
  <BasePageShell>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Bolsillo ProjectApp</h1>
        <p class="text-sm text-text-subtle mt-1" data-testid="pocket-subtitle">
          {{ hasActiveFilters
            ? 'Con filtros activos, la columna Acumulado suma sólo los movimientos visibles.'
            : 'Libro de movimientos del bolsillo compartido, con saldo corrido.' }}
        </p>
      </div>
      <BaseButton
        variant="primary"
        size="md"
        class="w-full panel-portrait:w-auto"
        data-testid="pocket-new-button"
        @click="openCreateModal"
      >
        <BaseActionIcon action="create" />
        <span>Nuevo movimiento</span>
      </BaseButton>
    </div>

    <AccountingSubnav active="pocket" />

    <!-- Balance card -->
    <div class="bg-surface rounded-xl border border-border-muted shadow-sm p-5 sm:p-6 mb-6">
      <p class="text-xs text-text-muted uppercase tracking-wider mb-1">
        Saldo del bolsillo
        <!-- The server owns this figure and always aggregates every movement,
             so it has to say so out loud once the rows below are a subset. -->
        <span v-if="hasActiveFilters" class="normal-case tracking-normal">
          (total, no refleja los filtros)
        </span>
      </p>
      <p
        class="text-3xl font-semibold tabular-nums"
        :class="pocketBalance >= 0 ? 'text-success-strong' : 'text-danger-strong'"
        data-testid="pocket-balance"
      >
        {{ formatMoney(pocketBalance) }}
      </p>
      <p
        v-if="hasActiveFilters"
        class="text-sm text-text-muted mt-2 tabular-nums"
        data-testid="pocket-filtered-net"
      >
        {{ filteredMovements.length }}
        {{ filteredMovements.length === 1 ? 'movimiento' : 'movimientos' }}
        filtrados · neto {{ formatMoney(filteredNet) }}
      </p>
    </div>

    <!-- Saved filter tabs -->
    <ProposalFilterTabs
      :tabs="savedTabs"
      :active-tab-id="filterTabId"
      :counts="tabCounts"
      :is-tab-limit-reached="isTabLimitReached"
      @select="selectFilterTab"
      @create="handleCreateFilterTab"
      @rename="renameFilterTab"
      @delete="deleteFilterTab"
      @restore="restoreFilterTab"
      @rebase="rebaseFilterTab"
      @reorder="reorderFilterTabs"
    />

    <!-- Search + Filter toggle -->
    <div class="flex flex-wrap items-center gap-2 mb-5">
      <BaseInput
        v-model="searchInput"
        type="text"
        placeholder="Buscar por concepto o notas..."
        data-testid="pocket-search-input"
        class="w-full sm:max-w-xs"
      />
      <UiFilterToggleButton
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
      <AccountingExportButton section="pocket" :params="exportParams" />
    </div>

    <!-- Filter panel -->
    <AccountingFilterPanel
      :fields="filterFields"
      :model-value="currentFilters"
      :is-open="isFilterPanelOpen"
      :results-count="filteredMovements.length"
      :search-value="currentFilters.search"
      @update:model-value="Object.assign(currentFilters, $event)"
      @reset="handleResetFilters"
      @clear-search="searchInput = ''"
    />

    <!-- Error -->
    <AccountingErrorState
      v-if="store.error === 'fetch_failed'"
      title="No se pudieron cargar los movimientos"
      :retrying="store.isLoading"
      @retry="loadRecords"
    />

    <!-- Empty -->
    <BaseEmptyState
      v-else-if="!store.isLoading && filteredMovements.length === 0"
      :title="hasActiveFilters ? 'Sin resultados con esos filtros' : 'No hay movimientos aún'"
      :description="hasActiveFilters
        ? 'Ajusta o limpia los filtros para ver más registros.'
        : 'Registra el primer movimiento del Bolsillo ProjectApp.'"
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
          <span>Nuevo movimiento</span>
        </BaseButton>
      </template>
    </BaseEmptyState>

    <!-- Ledger: true cards on compact widths, priority table above them. -->
    <template v-else>
      <div
        v-if="isCompactCards"
        class="mb-3 flex min-w-0 flex-wrap items-center gap-2"
        aria-label="Ordenar movimientos"
        data-testid="pocket-card-sort"
      >
        <span class="text-xs font-medium text-text-muted">Ordenar por</span>
        <BaseButton
          v-for="option in compactSortOptions"
          :key="option.key"
          variant="secondary"
          size="sm"
          :aria-pressed="sortKey === option.key"
          :data-testid="`pocket-card-sort-${option.key}`"
          @click="toggleSort(option.key)"
        >
          <span>{{ option.label }}</span>
          <BaseActionIcon
            v-if="sortKey === option.key"
            :action="sortDir === 'asc' ? 'sort-ascending' : 'sort-descending'"
            class="h-3.5 w-3.5"
          />
        </BaseButton>
      </div>

      <PocketMovementCards
        v-if="isCompactCards"
        :rows="pagedMovements"
        :loading="store.isLoading"
        :highlight-id="lastMutatedId"
        :has-active-filters="hasActiveFilters"
        @open-actions="openActions"
        @open-allocations="openAllocations"
      />

      <AccountingTable
        v-else
        :loading="store.isLoading"
        :highlight-id="lastMutatedId"
        :columns="columns"
        :rows="pagedMovements"
        :highlight-query="currentFilters.search"
        :sort-key="sortKey"
        :sort-dir="sortDir"
        :show-default-actions="false"
        row-actions-layout="menu-start"
        @edit="handleEdit"
        @delete="handleDelete"
        @sort="toggleSort"
      >
        <template #row-actions="{ row }">
          <PocketMovementRowActionsButton :row="row" @open="openActions" />
        </template>
        <template #cell-concept="{ row }">
          <span class="inline-flex min-w-0 flex-wrap items-center gap-2">
            <span class="min-w-0 break-words">{{ row.concept }}</span>
            <!-- Un abono cubre varios ingresos: el badge genérico se vuelve
                 la puerta al reparto. El guard de Array degrada al badge de
                 siempre si el serializer aún no manda allocations. -->
            <BaseButton
              v-if="Array.isArray(row.allocations) && row.allocations.length > 1"
              variant="ghost"
              size="sm"
              :data-testid="`pocket-allocations-${row.id}`"
              @click="openAllocations(row)"
            >
              Abono · {{ row.allocations.length }} ingresos
            </BaseButton>
            <BaseBadge
              v-else-if="row.is_auto_managed"
              size="sm"
              title="Sincronizado con el ingreso o gasto vinculado"
              :data-testid="`pocket-linked-${row.id}`"
            >
              Vinculado
            </BaseBadge>
          </span>
        </template>
        <template #cell-direction_label="{ row }">
          <BaseBadge
            :variant="row.direction === 'in' ? 'success' : 'danger'"
            :data-testid="`pocket-direction-${row.id}`"
          >
            {{ row.direction_label }}
          </BaseBadge>
        </template>
        <template #cell-amount="{ row }">
          <span
            class="tabular-nums"
            :class="row.direction === 'out' ? 'text-danger-strong' : 'text-text-muted'"
          >
            {{ (row.direction === 'out' ? '-' : '') + formatMoney(row.amount) }}
          </span>
          <span
            v-if="isNarrowTable"
            class="mt-1 block text-xs font-normal tabular-nums text-text-muted"
            :data-testid="`pocket-running-balance-${row.id}`"
          >
            {{ hasActiveFilters ? 'Acumulado filtrado' : 'Saldo después' }}:
            {{ formatMoney(row.running_balance) }}
          </span>
        </template>
        <template #cell-running_balance="{ row }">
          <span v-if="!isNarrowTable" class="tabular-nums">
            {{ formatMoney(row.running_balance) }}
          </span>
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

    <!-- First modal on purpose: its close must patch before the dialog it
         opens (form, history, note, confirmation), or the two trade focus
         traps and the page loses its scroll lock. -->
    <PocketMovementActionsModal
      :open="actionsRow !== null"
      :record="actionsRow"
      @close="closeActions"
      @history="openHistory"
      @notes="openNote"
      @edit="handleEdit"
      @delete="handleDelete"
    />

    <!-- Create/edit modal -->
    <PocketMovementFormModal
      :open="isModalOpen"
      :record="editingRecord"
      :saving="store.isUpdating"
      @close="closeModal"
      @submit="handleSubmit"
    />

    <!-- Reparto de un abono: qué ingresos cubrió este movimiento -->
    <PocketMovementAllocationsModal
      :open="allocationsOpen"
      :movement="allocationsMovement"
      @close="closeAllocations"
    />

    <EntityHistoryRecordModal
      :open="historyRow !== null"
      entity-type="pocket"
      :record="historyRow"
      @close="closeHistory"
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
import AccountingSubnav from '~/components/accounting/AccountingSubnav.vue';
import AccountingTable from '~/components/accounting/AccountingTable.vue';
import PocketMovementActionsModal from '~/components/accounting/PocketMovementActionsModal.vue';
import PocketMovementCards from '~/components/accounting/PocketMovementCards.vue';
import PocketMovementRowActionsButton from '~/components/accounting/PocketMovementRowActionsButton.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseBadge from '~/components/base/BaseBadge.vue';
import PocketMovementAllocationsModal from '~/components/accounting/PocketMovementAllocationsModal.vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import AccountingFilterPanel from '~/components/accounting/AccountingFilterPanel.vue';
import AccountingExportButton from '~/components/accounting/AccountingExportButton.vue';
import PocketMovementFormModal from '~/components/accounting/PocketMovementFormModal.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import { PANEL_BREAKPOINTS } from '~/config/responsive';
import { useIsMobile } from '~/composables/useIsMobile';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useAccountingCrudPage } from '~/composables/useAccountingCrudPage';
import {
  useAccountingFilters,
  matchDateRange,
  matchNumberRange,
  matchIncludes,
  matchBooleanIncludes,
} from '~/composables/useAccountingFilters';
import { useAccountingStore } from '~/stores/accounting';
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';
import { buildExportParams } from '~/utils/accountingExportParams';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';
import { withRunningBalance } from '~/utils/pocketRunningBalance';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const store = useAccountingStore();
const { isMobile: isCompactCards } = useIsMobile(PANEL_BREAKPOINTS.portrait - 1);
const { isMobile: isNarrowTable } = useIsMobile(PANEL_BREAKPOINTS.landscape - 1);

const compactSortOptions = [
  { key: 'movement_date', label: 'Fecha' },
  { key: 'concept', label: 'Concepto' },
  { key: 'amount', label: 'Valor' },
];

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
  countTabs,
  resetFilters,
  selectTab: selectFilterTab,
  saveTab,
  deleteTab: deleteFilterTab,
  renameTab: renameFilterTab,
  restoreTab: restoreFilterTab,
  rebaseTab: rebaseFilterTab,
  reorderTabs: reorderFilterTabs,
} = useAccountingFilters({
  viewName: 'accounting_pocket',
  defaults: {
    dateAfter: '',
    dateBefore: '',
    direction: [],
    amountMin: '',
    amountMax: '',
    attribution: [],
    linked: [],
  },
  matchers: {
    date: matchDateRange('movement_date', 'dateAfter', 'dateBefore'),
    direction: matchIncludes('direction', 'direction'),
    amount: matchNumberRange('amount', 'amountMin', 'amountMax'),
    // `linked_ledger` is null on movements that mirror nothing; the backend
    // spells that case 'none' too, so export and panel share one vocabulary.
    attribution: matchIncludes('linked_ledger', 'attribution', { nullAs: 'none' }),
    linked: matchBooleanIncludes('is_auto_managed', 'linked'),
  },
  // The backend `q` has always searched both; the panel used to search only
  // the concept, so a note was captured and then unreachable.
  searchFields: ['concept', 'notes'],
});

const filterFields = [
  { kind: 'daterange', label: 'Fecha', minKey: 'dateAfter', maxKey: 'dateBefore' },
  {
    kind: 'segmented',
    key: 'direction',
    label: 'Tipo',
    options: [
      { value: '', label: 'Todos' },
      { value: 'in', label: 'Ingreso' },
      { value: 'out', label: 'Egreso' },
    ],
  },
  { kind: 'range', label: 'Valor', minKey: 'amountMin', maxKey: 'amountMax', type: 'money' },
  {
    // Same vocabulary as the modal's "Atribuir a": whatever the form captures
    // is what the panel can cut by. "Sin vínculo" is deliberately absent — it
    // is the same set as Vínculo → "Sin vincular", and offering both invites
    // a guaranteed-empty combination.
    kind: 'multi',
    key: 'attribution',
    label: 'Atribuir a',
    options: [
      { value: 'company', label: 'Empresa' },
      { value: 'gustavo', label: 'Gustavo' },
      { value: 'carlos', label: 'Carlos' },
    ],
  },
  {
    kind: 'segmented',
    key: 'linked',
    label: 'Vínculo',
    options: [
      { value: '', label: 'Todos' },
      { value: 'true', label: 'Vinculados' },
      { value: 'false', label: 'Sin vincular' },
    ],
  },
];

const EXPORT_MAPPING = {
  dateAfter: 'date_from',
  dateBefore: 'date_to',
  direction: 'direction',
  amountMin: 'amount_min',
  amountMax: 'amount_max',
  attribution: 'attribution',
  linked: 'linked',
  search: 'q',
};

const exportParams = computed(() =>
  buildExportParams(currentFilters, EXPORT_MAPPING),
);

// -------------------------------------------------------------------
// Data + CRUD controller (modal, delete confirm, pagination)
// -------------------------------------------------------------------

// Server meta is the single owner of the headline balance.
const pocketBalance = computed(() => Number(store.metaFor('pocket').balance ?? 0));

// Filter first, accumulate second: the Saldo column has to add up to what the
// reader is looking at. With no filter active `applyFilters` passes the array
// straight through, so the figures are the same ones as before this split.
// `withRunningBalance` always returns fresh rows in a fresh array, so reversing
// it in place is safe and yields the newest-first default view.
const filteredMovements = computed(() =>
  withRunningBalance(applyFilters(store.pocketMovements)).reverse(),
);

// Net of the visible cut = the last accumulated value, which the reversed array
// carries in its first row.
const filteredNet = computed(() =>
  filteredMovements.value.length ? filteredMovements.value[0].running_balance : 0,
);

// Each tab counts its own cut of the whole ledger, not of the current one: the
// badge answers "how many would I see there", so it must ignore live filters.
const tabCounts = computed(() => countTabs(store.pocketMovements));

const {
  isModalOpen,
  editingRecord,
  openCreateModal,
  lastMutatedId,
  openEditModal: handleEdit,
  closeModal,
  handleSubmit,
  confirmDeleteRecord: handleDelete,
  confirmState,
  handleConfirmed,
  handleCancelled,
  currentPage,
  totalPages,
  totalItems,
  rangeFrom,
  rangeTo,
  pagedRecords: pagedMovements,
  prevPage,
  nextPage,
  goToPage,
  handleCreateFilterTab,
  handleResetFilters,
  sortKey,
  sortDir,
  toggleSort,
} = useAccountingCrudPage({
  entity: 'pocket',
  resetPageOn: currentFilters,
  store,
  filteredRecords: filteredMovements,
  sortDefaults: { movement_date: 'desc', amount: 'desc' },
  labels: {
    created: 'Movimiento creado',
    updated: 'Movimiento actualizado',
    deleted: 'Movimiento eliminado',
    saveErrorTitle: 'No se pudo guardar',
    deleteErrorTitle: 'No se pudo eliminar',
    deleteTitle: 'Eliminar movimiento',
    deleteMessage: (record) => {
      const isAbono = Array.isArray(record.allocations)
        && record.allocations.length > 1;
      const cascade = isAbono
        ? `Se revertirá el abono completo: sus ${record.allocations.length} ingresos vinculados vuelven a quedar pendientes. `
        : (record.is_auto_managed
          ? 'También se eliminará el ingreso/gasto vinculado. '
          : '');
      return `Esto eliminará el movimiento "${record.concept}" de forma permanente. `
        + cascade
        + 'Esta acción no se puede deshacer.';
    },
  },
  onAfterMutation: async () => {
    // Refresh meta.balance + link fields, and drop the sibling caches so
    // the Ingresos/Gastos tabs refetch the mirrored records on mount.
    await loadRecords();
    store.incomes = [];
    store.expenses = [];
  },
  saveTab,
  resetFilters,
  isFilterPanelOpen,
});

// Value and running balance are the same number in two readings, so they group.
// Date, concept and value are what a ledger is for; the rest can collapse.
const columns = computed(() => [
  {
    key: 'movement_date', label: 'Fecha', format: 'date', sortable: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'concept', label: 'Concepto', size: 'name', sortable: true,
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'direction_label', label: 'Tipo', size: 'badge', hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'amount', label: 'Valor', format: 'money', group: 'money', sortable: true,
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'running_balance',
    // Under a filter the column stops being the pocket's balance: it is the
    // accumulation of the visible rows, starting from zero at the first one.
    label: hasActiveFilters.value ? 'Acumulado' : 'Saldo',
    format: 'money',
    group: 'money',
    hideBelow: 'md',
    responsive: { compact: 'hide', portrait: 'hide', landscape: 'keep' },
  },
]);

// ── Reparto de un abono ──

const allocationsOpen = ref(false);
const allocationsMovement = ref(null);
const actionsRow = ref(null);

function openActions(row) {
  actionsRow.value = row;
}

function closeActions() {
  actionsRow.value = null;
}

// Detalle e historial is a menu entry, never a sibling of the kebab: the
// leading track is 56 px wide and anything else overflows onto the ledger.
const historyRow = ref(null);

function openHistory(row) {
  historyRow.value = row;
}

function closeHistory() {
  historyRow.value = null;
}

// «Ver nota» is offered by the menu only when the movement has one; the ledger
// has no notes column, but the search does match them.
const noteRow = ref(null);

function openNote(row) {
  noteRow.value = row;
}

const noteSubtitle = computed(() => (noteRow.value
  ? `${noteRow.value.concept || `Movimiento #${noteRow.value.id}`} · ${formatDate(noteRow.value.movement_date)}`
  : ''));

function openAllocations(row) {
  allocationsMovement.value = row;
  allocationsOpen.value = true;
}

function closeAllocations() {
  allocationsOpen.value = false;
  allocationsMovement.value = null;
}

async function loadRecords() {
  await store.fetchRecords('pocket');
}

onMounted(loadRecords);
usePanelRefresh(loadRecords);
</script>
