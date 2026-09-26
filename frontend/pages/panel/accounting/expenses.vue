<template>
  <BasePageShell>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Gastos</h1>
        <p class="text-sm text-text-subtle mt-1">
          Gastos del negocio y personales, con su reparto entre socios.
        </p>
      </div>
      <BaseButton
        variant="primary"
        size="md"
        class="w-full panel-portrait:w-auto"
        data-testid="expenses-new-button"
        @click="openCreateModal"
      >
        <BaseActionIcon action="create" />
        <span>Nuevo gasto</span>
      </BaseButton>
    </div>

    <AccountingSubnav active="expenses" />

    <!-- KPI cards (year scope, server-computed) -->
    <AccountingIndicatorGroup :columns="5" :secondary-count="2">
      <template #primary>
        <AccountingStatCard
          label="Total año"
          :value="money(expensesMeta.year_total)"
        />
        <AccountingStatCard
          label="Mes actual"
          :value="money(expensesMeta.current_month_total)"
          :tone="expensesMeta.current_month_alert ? 'warning' : 'default'"
          :sub="expensesMeta.current_month_alert
            ? 'Inusualmente alto vs promedio mensual'
            : ''"
        />
        <AccountingStatCard
          label="Deducciones (año)"
          :value="money(expensesMeta.deductions_total)"
          :sub="deductionsBreakdownSub"
          data-testid="expenses-deductions-card"
        />
      </template>
      <template #secondary>
        <AccountingStatCard
          label="Mayor gasto del año"
          :value="expensesMeta.top_expense ? money(expensesMeta.top_expense.amount) : '—'"
          :sub="expensesMeta.top_expense?.concept || ''"
        />
        <AccountingStatCard
          label="Negocio (año)"
          :value="money(expensesMeta.business_total)"
          :sub="`Personal: ${money(expensesMeta.personal_total)}`"
          tone="brand"
        />
      </template>
    </AccountingIndicatorGroup>

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

    <!-- Search + Filter toggle -->
    <div class="flex flex-wrap items-center gap-2 mb-5">
      <BaseInput
        v-model="searchInput"
        type="text"
        placeholder="Buscar por concepto o notas..."
        data-testid="expenses-search-input"
        class="w-full sm:max-w-xs"
      />
      <UiFilterToggleButton
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
      <AccountingExportButton section="expense" :params="exportParams" />
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

    <!-- Summary chips (filtered rows) -->
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <span
        class="text-xs px-2.5 py-1 rounded-full bg-danger-soft text-danger-strong font-medium tabular-nums"
        data-testid="expenses-total-filtered"
      >
        Total gastos: {{ formatMoney(totalFiltered) }}
      </span>
      <template v-if="totalDeductions > 0">
        <span
          class="text-xs px-2.5 py-1 rounded-full bg-surface-raised text-text-muted font-medium tabular-nums"
          data-testid="expenses-total-operational"
        >
          Operativo: {{ formatMoney(totalOperational) }}
        </span>
        <span
          class="text-xs px-2.5 py-1 rounded-full bg-info-soft text-info-strong font-medium tabular-nums"
          data-testid="expenses-total-deductions"
        >
          Deducciones: {{ formatMoney(totalDeductions) }}
        </span>
      </template>
    </div>

    <!-- Error -->
    <AccountingErrorState
      v-if="store.error === 'fetch_failed'"
      title="No se pudieron cargar los gastos"
      :retrying="store.isLoading"
      @retry="loadRecords"
    />

    <!-- Empty -->
    <BaseEmptyState
      v-else-if="!store.isLoading && filteredRecords.length === 0"
      :title="hasActiveFilters ? 'Sin resultados con esos filtros' : 'No hay gastos aún'"
      :description="hasActiveFilters
        ? 'Ajusta o limpia los filtros para ver más registros.'
        : 'Registra el primer gasto del negocio o personal.'"
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
          <span>Nuevo gasto</span>
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
            :label="`Acciones de ${expenseLabel(row)}`"
            :test-id="`expense-actions-${row.id}`"
            @open="actionsRow = row"
          />
        </template>
        <template #cell-concept="{ row }">
          <span class="text-text-default">{{ row.concept }}</span>
          <!-- Deductions reduce utility like any expense; the pill keeps
               the type and its origin income visible in the list. -->
          <span
            v-if="row.deduction_type"
            class="ml-2 text-[10px] px-2 py-0.5 rounded-full font-medium bg-info-soft text-info-strong whitespace-nowrap"
            :title="deductionPillTitle(row)"
            :data-testid="`expense-deduction-pill-${row.id}`"
          >
            {{ row.deduction_type_label }}
          </span>
        </template>
        <template #cell-category_label="{ row }">
          <span
            class="text-xs px-2.5 py-1 rounded-full font-medium"
            :class="row.category === 'personal'
              ? 'bg-warning-soft text-warning-strong'
              : 'bg-surface-raised text-text-muted'"
          >
            {{ row.category_label }}
          </span>
        </template>
        <template #cell-ledger_label="{ row }">
          <span
            class="text-xs px-2.5 py-1 rounded-full font-medium"
            :class="row.ledger === 'company'
              ? 'bg-surface-raised text-text-muted'
              : 'bg-info-soft text-info-strong'"
          >
            {{ row.ledger === 'company' ? 'Empresa' : row.ledger_label }}
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

    <AccountingRowActionsModal
      :open="actionsRow !== null"
      :record="actionsRow"
      :title="actionsRow ? expenseLabel(actionsRow) : ''"
      :subtitle="expenseSummary(actionsRow)"
      :actions="expenseActions"
      test-id-prefix="expense"
      @close="actionsRow = null"
      @select="runExpenseAction"
    />

    <!-- Create/edit modal -->
    <ExpenseFormModal
      :open="isModalOpen"
      :record="editingRecord"
      :saving="store.isUpdating"
      @close="closeModal"
      @submit="handleSubmit"
    />

    <EntityHistoryRecordModal
      :open="historyRow !== null"
      entity-type="expense"
      :record="historyRow"
      @close="historyRow = null"
    />

    <AccountingNoteModal
      :open="noteRow !== null"
      :subtitle="expenseSummary(noteRow)"
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
import AccountingRowActionsButton from '~/components/accounting/AccountingRowActionsButton.vue';
import AccountingRowActionsModal from '~/components/accounting/AccountingRowActionsModal.vue';
import AccountingSubnav from '~/components/accounting/AccountingSubnav.vue';
import AccountingTable from '~/components/accounting/AccountingTable.vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import AccountingIndicatorGroup from '~/components/accounting/AccountingIndicatorGroup.vue';
import AccountingStatCard from '~/components/accounting/AccountingStatCard.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import AccountingFilterPanel from '~/components/accounting/AccountingFilterPanel.vue';
import AccountingExportButton from '~/components/accounting/AccountingExportButton.vue';
import ExpenseFormModal from '~/components/accounting/ExpenseFormModal.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useAccountingCrudPage } from '~/composables/useAccountingCrudPage';
import {
  useAccountingFilters,
  matchDateRange,
  matchNumberRange,
  matchIncludes,
  matchAnyToken,
} from '~/composables/useAccountingFilters';
import { useAccountingStore } from '~/stores/accounting';
import { DEDUCTION_TYPE_OPTIONS } from '~/utils/accountingDeductions';
import { buildExportParams } from '~/utils/accountingExportParams';
import { leadingRowActions } from '~/utils/accountingRowActions';
import { formatMoney } from '~/utils/formatMoney';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const store = useAccountingStore();

const expensesMeta = computed(() => store.metaFor('expenses'));

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

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
  viewName: 'accounting_expense',
  defaults: {
    periodAfter: '',
    periodBefore: '',
    amountMin: '',
    amountMax: '',
    categories: [],
    ledger: [],
    nature: [],
    deductionTypes: [],
  },
  matchers: {
    period: matchDateRange('period_date', 'periodAfter', 'periodBefore'),
    amount: matchNumberRange('total_amount', 'amountMin', 'amountMax'),
    categories: matchIncludes('category', 'categories'),
    ledger: matchIncludes('ledger', 'ledger'),
    // Operational spending vs money discounted from an income — derived from
    // `deduction_type`, not a column of its own, so each token is a predicate.
    nature: matchAnyToken('nature', {
      operational: (record) => !record.deduction_type,
      deduction: (record) => Boolean(record.deduction_type),
    }),
    deductionTypes: matchIncludes('deduction_type', 'deductionTypes'),
  },
  searchFields: ['concept', 'notes'],
});

const filterFields = [
  { kind: 'daterange', label: 'Mes', minKey: 'periodAfter', maxKey: 'periodBefore' },
  { kind: 'range', label: 'Total', minKey: 'amountMin', maxKey: 'amountMax', type: 'money' },
  {
    kind: 'multi',
    key: 'categories',
    label: 'Categoría',
    options: [
      { value: 'business', label: 'Negocio' },
      { value: 'personal', label: 'Personal' },
    ],
  },
  {
    kind: 'segmented',
    key: 'ledger',
    label: 'Contabilidad',
    options: [
      { value: '', label: 'Todas' },
      { value: 'company', label: 'Empresa' },
      { value: 'gustavo', label: 'Personal Gustavo' },
      { value: 'carlos', label: 'Personal Carlos' },
    ],
  },
  {
    kind: 'segmented',
    key: 'nature',
    label: 'Naturaleza',
    options: [
      { value: '', label: 'Todos' },
      { value: 'operational', label: 'Gasto operativo' },
      { value: 'deduction', label: 'Descuento de ingreso' },
    ],
  },
  {
    kind: 'multi',
    key: 'deductionTypes',
    label: 'Tipo de deducción',
    options: DEDUCTION_TYPE_OPTIONS,
  },
];

const EXPORT_MAPPING = {
  periodAfter: 'date_from',
  periodBefore: 'date_to',
  amountMin: 'amount_min',
  amountMax: 'amount_max',
  categories: 'category',
  ledger: 'ledger',
  deductionTypes: 'deduction_type',
  search: 'q',
};

const exportParams = computed(() =>
  buildExportParams(currentFilters, EXPORT_MAPPING),
);

// -------------------------------------------------------------------
// Data + CRUD controller (modal, delete confirm, pagination)
// -------------------------------------------------------------------

const filteredRecords = computed(() => applyFilters(store.expenses));

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
  entity: 'expenses',
  resetPageOn: currentFilters,
  // The month column shows the localized label but sorts by the ISO date.
  sortAccessors: { period_label: 'period_date' },
  sortDefaults: {
    period_label: 'desc',
    total_amount: 'desc',
    gustavo_amount: 'desc',
    carlos_amount: 'desc',
  },
  store,
  filteredRecords,
  saveTab,
  resetFilters,
  isFilterPanelOpen,
  labels: {
    entityName: 'gasto',
    created: 'Gasto creado',
    updated: 'Gasto actualizado',
    deleted: 'Gasto eliminado',
    saveErrorTitle: 'No se pudo guardar',
    deleteErrorTitle: 'No se pudo eliminar',
    deleteTitle: 'Eliminar gasto',
    deleteMessage: (record) =>
      `Esto eliminará el gasto "${record.concept}" de forma permanente. ` +
      (record.pocket_movement != null
        ? 'También se eliminará el egreso vinculado en bolsillo. '
        : '') +
      'Esta acción no se puede deshacer.',
  },
  // Expense mutations can create/mirror/delete pocket movements: drop the
  // pocket cache so the Bolsillo tab refetches fresh on mount.
  onAfterMutation: () => {
    store.pocketMovements = [];
  },
});

// ── Row actions ──
// One kebab per row in the leading track; its menu owns Detalle e historial,
// Ver nota (when the expense has one), Editar and Eliminar.

const actionsRow = ref(null);
const historyRow = ref(null);
const noteRow = ref(null);

function expenseLabel(row) {
  return row.concept || `Gasto #${row.id}`;
}

function expenseSummary(row) {
  return row ? `${row.period_label} · ${money(row.total_amount)}` : '';
}

const expenseActions = computed(() => (actionsRow.value
  ? [
    ...leadingRowActions(actionsRow.value),
    { id: 'edit', action: 'edit', label: 'Editar' },
    { id: 'delete', action: 'delete', label: 'Eliminar', danger: true },
  ]
  : []));

const expenseActionHandlers = {
  history: (row) => { historyRow.value = row; },
  notes: (row) => { noteRow.value = row; },
  edit: (row) => openEditModal(row),
  delete: (row) => confirmDeleteRecord(row),
};

function runExpenseAction(id, row) {
  expenseActionHandlers[id]?.(row);
}

const totalFiltered = computed(() =>
  filteredRecords.value.reduce((sum, r) => sum + (Number(r.total_amount) || 0), 0),
);

const totalDeductions = computed(() =>
  filteredRecords.value.reduce(
    (sum, r) => sum + (r.deduction_type ? Number(r.total_amount) || 0 : 0),
    0,
  ),
);

const totalOperational = computed(() => totalFiltered.value - totalDeductions.value);

const DEDUCTION_LABELS = Object.fromEntries(
  DEDUCTION_TYPE_OPTIONS.map((option) => [option.value, option.label]),
);

const deductionsBreakdownSub = computed(() => {
  const byType = expensesMeta.value.deductions_by_type || {};
  return Object.entries(byType)
    .map(([type, total]) => `${DEDUCTION_LABELS[type] || type}: ${money(total)}`)
    .join(' · ');
});

function deductionPillTitle(row) {
  const origin = row.source_income_concept
    ? ` — origen: ${row.source_income_concept}`
    : '';
  return (
    `Deducción sobre ingreso (resta utilidad): `
    + `${row.deduction_type_label}${origin}`
  );
}

// Same shape as Ingresos: concept on the widest floor, the three amounts grouped, and
// the metadata columns collapsing first on narrow screens.
const columns = [
  {
    key: 'concept', label: 'Concepto', size: 'name', sortable: true,
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'period_label', label: 'Mes', sortable: true, hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'category_label', label: 'Categoría', size: 'badge',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'ledger_label', label: 'Contabilidad', hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'total_amount', label: 'Total', format: 'money', group: 'money', sortable: true,
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'gustavo_amount', label: 'Gustavo', format: 'money', group: 'money', sortable: true, hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'carlos_amount', label: 'Carlos', format: 'money', group: 'money', sortable: true, hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
];

async function loadRecords() {
  await store.fetchRecords('expenses');
}

onMounted(loadRecords);
usePanelRefresh(loadRecords);
</script>
