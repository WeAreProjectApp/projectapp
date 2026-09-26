<template>
  <BasePageShell>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Pagos recurrentes</h1>
        <p class="text-sm text-text-subtle mt-1">
          Suscripciones y costos operativos que se repiten mes a mes o año a año.
        </p>
      </div>
      <div class="flex w-full flex-wrap items-center gap-2 panel-portrait:w-auto">
        <BaseButton
          variant="secondary"
          size="md"
          class="flex-1 panel-portrait:flex-none"
          data-testid="recurring-manage-categories"
          @click="showCategoriesModal = true"
        >
          <BaseActionIcon action="tags" />
          <span>Gestionar categorías</span>
        </BaseButton>
        <BaseButton
          variant="primary"
          size="md"
          class="flex-1 panel-portrait:flex-none"
          data-testid="recurring-new-button"
          @click="openCreateModal"
        >
          <BaseActionIcon action="create" />
          <span>Nuevo pago recurrente</span>
        </BaseButton>
      </div>
    </div>

    <AccountingSubnav active="recurring" />

    <div class="mb-4 flex flex-col gap-2 panel-portrait:flex-row panel-portrait:items-center">
      <BaseSegmented
        v-model="archiveScope"
        :options="archiveScopeOptions"
        size="sm"
        data-testid="recurring-archive-scope"
        aria-label="Estado de conservación de los pagos recurrentes"
      />
      <p class="text-xs text-text-subtle" data-testid="recurring-budget-scope-note">
        <template v-if="isArchivedScope">
          Los archivados se conservan para consulta, pero no cuentan en totales, porcentajes ni avisos.
        </template>
        <template v-else>
          El presupuesto y los porcentajes incluyen solo pagos activos; los inactivos quedan fuera.
        </template>
      </p>
    </div>

    <!-- Stat cards -->
    <div v-if="!isArchivedScope" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
      <AccountingStatCard
        data-testid="recurring-monthly-cop-total"
        label="Costo mensual (COP)"
        :value="money(monthlyCopTotal)"
        sub="Pagos activos prorrateados por mes"
      />
      <AccountingStatCard
        label="Costo mensual (USD)"
        :value="monthlyUsdTotal != null ? formatMoney(monthlyUsdTotal, 'USD') : '—'"
        :sub="usdKpiSub"
        tone="brand"
      />
      <div class="bg-surface rounded-xl border border-border-muted shadow-sm p-4 sm:p-5">
        <div class="flex items-center justify-between gap-2 mb-2">
          <p class="text-xs text-text-muted uppercase tracking-wider">Desglose mensual</p>
          <BaseSegmented
            v-model="breakdownView"
            :options="breakdownOptions"
            size="sm"
          />
        </div>
        <p v-if="breakdownEntries.length === 0" class="text-xs text-text-subtle">Sin pagos activos.</p>
        <dl v-else class="space-y-1 text-sm" data-testid="recurring-breakdown">
          <div
            v-for="[label, total] in breakdownEntries"
            :key="label"
            class="flex items-center justify-between gap-3"
          >
            <dt class="min-w-0 max-w-full truncate text-text-muted" :title="label">{{ label }}</dt>
            <dd class="tabular-nums text-text-default whitespace-nowrap">{{ money(total) }}</dd>
          </div>
        </dl>
      </div>
    </div>

    <!-- Saved filter tabs -->
    <ProposalFilterTabs
      :tabs="savedTabs"
      :active-tab-id="activeTabId"
      :is-tab-limit-reached="isTabLimitReached"
      @select="selectTab"
      @create="handleCreateTab"
      @rename="renameTab"
      @delete="deleteTab"
      @restore="restoreTab"
      @rebase="rebaseTab"
      @reorder="reorderTabs"
    />

    <!-- Search + Filter toggle + view mode -->
    <div class="flex flex-wrap items-center gap-2 mb-5">
      <BaseInput
        v-model="searchInput"
        type="text"
        placeholder="Buscar por nombre o notas..."
        data-testid="recurring-search-input"
        class="w-full sm:max-w-xs"
      />
      <UiFilterToggleButton
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
      <AccountingExportButton section="recurring" :params="exportParams" />
      <BaseSegmented
        v-model="viewMode"
        :options="viewModeOptions"
        size="sm"
        class="w-full panel-portrait:ml-auto panel-portrait:w-auto"
        data-testid="recurring-view-mode"
      />
      <!-- Divider, not a third segment: this opens a modal, it is not another
           way of listing the table. -->
      <span class="hidden h-6 w-px bg-border-muted panel-portrait:block" aria-hidden="true" />
      <BaseButton
        variant="secondary"
        size="sm"
        class="flex-1 panel-portrait:flex-none"
        data-testid="recurring-charts-button"
        :disabled="isArchivedScope"
        disabled-reason="Los archivados no forman parte del presupuesto ni de sus gráficos."
        @click="showChartsModal = true"
      >
        <BaseActionIcon action="stats" />
        <span>Gráfico</span>
      </BaseButton>
    </div>

    <!-- Filter panel -->
    <AccountingFilterPanel
      :fields="filterFields"
      :model-value="currentFilters"
      :is-open="isFilterPanelOpen"
      :results-count="filteredRows.length"
      :search-value="currentFilters.search"
      @update:model-value="Object.assign(currentFilters, $event)"
      @reset="resetFilters"
      @clear-search="searchInput = ''"
    />

    <!-- Error -->
    <AccountingErrorState
      v-if="store.error === 'fetch_failed'"
      title="No se pudieron cargar los pagos recurrentes"
      :retrying="store.isLoading"
      @retry="loadRecords"
    />

    <!-- Empty -->
    <BaseEmptyState
      v-else-if="!store.isLoading && filteredRows.length === 0"
      :title="emptyTitle"
      :description="emptyDescription"
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
        <BaseButton
          v-else-if="!isArchivedScope"
          variant="primary"
          size="sm"
          @click="openCreateModal"
        >
          <BaseActionIcon action="create" />
          <span>Nuevo pago recurrente</span>
        </BaseButton>
      </template>
    </BaseEmptyState>

    <template v-else>
      <p
        v-if="!isArchivedScope && isGrouped && groupedWeightSort && !store.isLoading"
        class="text-xs text-text-subtle mb-2"
        data-testid="recurring-weight-sort-hint"
      >
        Orden por peso activo: quítalo para reordenar arrastrando.
      </p>
      <p
        v-else-if="!isArchivedScope && isGrouped && !canReorder && !store.isLoading"
        class="text-xs text-text-subtle mb-2"
        data-testid="recurring-reorder-hint"
      >
        Limpia la búsqueda y los filtros para poder reordenar arrastrando.
      </p>

      <RecurringGroupedTable
        v-if="isGrouped"
        v-model:selected="selectedIds"
        :selectable="!isArchivedScope"
        :loading="store.isLoading"
        :highlight-id="lastMutatedId"
        :columns="groupedColumns"
        :groups="displayGroups"
        :highlight-query="currentFilters.search"
        :drag-enabled="canReorder"
        :collapsed-ids="collapsedGroupIds"
        :weight-sort="groupedWeightSort"
        :show-default-actions="false"
        row-actions-layout="menu-start"
        :sort-column-key="isArchivedScope ? '' : 'monthly_cop_cost'"
        @reorder="handleReorder"
        @toggle-group="toggleGroup"
        @toggle-weight-sort="toggleGroupedWeightSort"
      >
        <template #row-actions="{ row }">
          <RecurringRowActionsButton
            :row="row"
            :busy="duplicatingId === row.id"
            @open="openActions"
          />
        </template>
        <template #cell-price="{ row }">
          <span class="tabular-nums">{{ formatMoney(Number(row.price), row.currency) }}</span>
        </template>
        <template #cell-monthly_price="{ row }">
          <span class="tabular-nums">{{ formatMonthlyPrice(row) }}</span>
        </template>
        <template #cell-monthly_cop_cost="{ row }">
          <span class="tabular-nums">{{ formatMonthlyCop(row.monthly_cop_cost) }}</span>
          <span
            class="block text-xs text-text-subtle tabular-nums"
            :data-testid="`recurring-weight-${row.id}`"
            title="Peso sobre el total mensual COP de pagos activos"
          >
            {{ formatPercent(row.weight_pct) }}
          </span>
        </template>
        <template #cell-billing_day="{ row }">
          {{ row.billing_day || '—' }}
        </template>
        <template #cell-cost_type_label="{ row }">
          <span
            class="text-xs px-2.5 py-1 rounded-full font-medium"
            :class="row.cost_type === 'variable'
              ? 'bg-warning-soft text-warning-strong'
              : 'bg-surface-raised text-text-muted'"
          >
            {{ row.cost_type_label }}
          </span>
        </template>
        <template #cell-is_active="{ row }">
          <span
            class="text-xs px-2.5 py-1 rounded-full font-medium"
            :class="recurringStateClass(row)"
          >
            {{ recurringStateLabel(row) }}
          </span>
        </template>
      </RecurringGroupedTable>

      <template v-else>
        <AccountingTable
          v-model:selected="selectedIds"
          :selectable="!isArchivedScope"
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
            <RecurringRowActionsButton
              :row="row"
              :busy="duplicatingId === row.id"
              @open="openActions"
            />
          </template>
          <template #cell-price="{ row }">
            <span class="tabular-nums">{{ formatMoney(Number(row.price), row.currency) }}</span>
          </template>
          <template #cell-monthly_price="{ row }">
            <span class="tabular-nums">{{ formatMonthlyPrice(row) }}</span>
          </template>
          <template #cell-monthly_cop_cost="{ row }">
            <span class="tabular-nums">{{ formatMonthlyCop(row.monthly_cop_cost) }}</span>
            <span
              class="block text-xs text-text-subtle tabular-nums"
              :data-testid="`recurring-weight-${row.id}`"
              title="Peso sobre el total mensual COP de pagos activos"
            >
              {{ formatPercent(row.weight_pct) }}
            </span>
          </template>
          <template #cell-category_name="{ row }">
            <span
              class="text-xs px-2.5 py-1 rounded-full font-medium bg-surface-raised text-text-muted"
            >
              {{ row.category_name || 'Sin categoría' }}
            </span>
          </template>
          <template #cell-billing_day="{ row }">
            {{ row.billing_day || '—' }}
          </template>
          <template #cell-cost_type_label="{ row }">
            <span
              class="text-xs px-2.5 py-1 rounded-full font-medium"
              :class="row.cost_type === 'variable'
                ? 'bg-warning-soft text-warning-strong'
                : 'bg-surface-raised text-text-muted'"
            >
              {{ row.cost_type_label }}
            </span>
          </template>
          <template #cell-is_active="{ row }">
            <span
              class="text-xs px-2.5 py-1 rounded-full font-medium"
              :class="recurringStateClass(row)"
            >
              {{ recurringStateLabel(row) }}
            </span>
          </template>
        </AccountingTable>

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
    </template>

    <RecurringBulkActionBar
      v-if="!isArchivedScope"
      v-model:selected="selectedIds"
      :rows="store.recurringPayments"
      :filtered-ids="filteredIds"
      :busy="store.isUpdating"
      @submit="applyBulkRecurringAction"
    />

    <!-- First modal on purpose: its close must patch before the dialog it
         opens (form, history, note, mute, confirmation), or the two trade
         focus traps and the page loses its scroll lock. -->
    <RecurringActionsModal
      :open="actionsOpen"
      :record="actionsRow"
      @close="actionsOpen = false"
      @history="historyRow = $event"
      @notes="noteRow = $event"
      @edit="openEditModal"
      @duplicate="duplicateRecurring"
      @toggle-state="toggleRecurringState"
      @toggle-mute="toggleRecurringMute"
      @archive="confirmArchiveRecurring"
      @restore="restoreRecurring"
      @delete="confirmPermanentDelete"
    />

    <!-- Create / edit modal -->
    <RecurringPaymentFormModal
      :open="showFormModal"
      :record="editingRecord"
      :seed="seedRecord"
      :saving="store.isUpdating"
      :categories="store.recurringCategories"
      :usd-exchange-rate="store.metaFor('recurring').usd_exchange_rate"
      @close="closeFormModal"
      @submit="submitRecurringForm"
    />

    <!-- Charts -->
    <RecurringChartsModal
      :open="showChartsModal"
      :rows="filteredRows"
      :categories="store.recurringCategories"
      :usd-exchange-rate="store.metaFor('recurring').usd_exchange_rate"
      :inherited-chips="inheritedChartChips"
      @close="showChartsModal = false"
      @clear-filters="resetFilters"
    />

    <!-- Category catalog -->
    <RecurringCategoriesModal
      :open="showCategoriesModal"
      :categories="store.recurringCategories"
      :saving="store.isUpdating"
      @close="showCategoriesModal = false"
      @create="createCategory"
      @rename="renameCategory"
      @delete="confirmDeleteCategory"
      @reorder="reorderCategories"
    />

    <EntityHistoryRecordModal
      :open="historyRow !== null"
      entity-type="recurring"
      :record="historyRow"
      @close="historyRow = null"
    />

    <AccountingNoteModal
      :open="noteRow !== null"
      :subtitle="noteRow?.name || ''"
      :notes="noteRow?.notes ?? ''"
      :highlight-query="currentFilters.search"
      @close="noteRow = null"
    />

    <RecurringMuteModal
      :open="muteModalOpen"
      :record="mutingRecord"
      :saving="store.isUpdating"
      @close="closeMuteModal"
      @submit="submitRecurringMute"
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
import { computed, onMounted, ref, watch } from 'vue';
import AccountingSubnav from '~/components/accounting/AccountingSubnav.vue';
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';
import AccountingStatCard from '~/components/accounting/AccountingStatCard.vue';
import AccountingTable from '~/components/accounting/AccountingTable.vue';
import RecurringGroupedTable from '~/components/accounting/RecurringGroupedTable.vue';
import RecurringCategoriesModal from '~/components/accounting/RecurringCategoriesModal.vue';
import RecurringChartsModal from '~/components/accounting/stats/RecurringChartsModal.vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import AccountingFilterPanel from '~/components/accounting/AccountingFilterPanel.vue';
import AccountingExportButton from '~/components/accounting/AccountingExportButton.vue';
import RecurringPaymentFormModal from '~/components/accounting/RecurringPaymentFormModal.vue';
import RecurringActionsModal from '~/components/accounting/RecurringActionsModal.vue';
import RecurringBulkActionBar from '~/components/accounting/RecurringBulkActionBar.vue';
import RecurringMuteModal from '~/components/accounting/RecurringMuteModal.vue';
import RecurringRowActionsButton from '~/components/accounting/RecurringRowActionsButton.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import UiFilterToggleButton from '~/components/ui/FilterToggleButton.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useAccountingCrudPage } from '~/composables/useAccountingCrudPage';
import { useRecurringViewMode } from '~/composables/useRecurringViewMode';
import { useRowSelection } from '~/composables/useRowSelection';
import {
  useAccountingFilters,
  matchBooleanIncludes,
  matchIncludes,
  matchNumberRange,
} from '~/composables/useAccountingFilters';
import { useAccountingStore } from '~/stores/accounting';
import { buildExportParams } from '~/utils/accountingExportParams';
import { formatMoney } from '~/utils/formatMoney';
import { addWeightPct, formatPercent } from '~/utils/percent';
import {
  FREQUENCY_OPTIONS,
  formatMonthlyCop,
  formatMonthlyPrice,
  groupByCategory,
  withGroupWeights,
} from '~/utils/recurring';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const store = useAccountingStore();
const notify = usePanelNotify();
const archiveScope = ref('current');
const archiveScopeOptions = [
  { value: 'current', label: 'Vigentes' },
  { value: 'archived', label: 'Archivados' },
];
const isArchivedScope = computed(() => archiveScope.value === 'archived');

// -------------------------------------------------------------------
// Filters
// -------------------------------------------------------------------

const {
  currentFilters,
  searchInput,
  savedTabs,
  activeTabId,
  isFilterPanelOpen,
  activeFilterCount,
  hasActiveFilters,
  isTabLimitReached,
  applyFilters,
  resetFilters,
  selectTab,
  saveTab,
  deleteTab,
  renameTab,
  restoreTab,
  rebaseTab,
  reorderTabs,
} = useAccountingFilters({
  viewName: 'accounting_recurring',
  defaults: {
    category: [],
    frequency: [],
    payment_method: [],
    currency: [],
    cost_type: [],
    price_min: '',
    price_max: '',
    is_active: [],
  },
  matchers: {
    category: matchIncludes('category', 'category'),
    frequency: matchIncludes('frequency', 'frequency'),
    payment_method: matchIncludes('payment_method', 'payment_method'),
    currency: matchIncludes('currency', 'currency'),
    cost_type: matchIncludes('cost_type', 'cost_type'),
    priceRange: matchNumberRange('price', 'price_min', 'price_max'),
    isActive: matchBooleanIncludes('is_active', 'is_active'),
  },
  searchFields: ['name', 'notes'],
});

const filterFields = computed(() => [
  {
    kind: 'multi',
    key: 'category',
    label: 'Categoría',
    options: store.recurringCategories.map((category) => ({
      value: category.id,
      label: category.name,
    })),
  },
  {
    kind: 'multi',
    key: 'frequency',
    label: 'Frecuencia',
    // "Personalizada" matches every custom cycle, whatever its month count.
    options: FREQUENCY_OPTIONS,
  },
  {
    kind: 'multi',
    key: 'payment_method',
    label: 'Método de pago',
    options: [
      { value: 'cash', label: 'Efectivo' },
      { value: 'credit_card', label: 'T.C' },
    ],
  },
  {
    kind: 'segmented',
    key: 'currency',
    label: 'Moneda',
    options: [
      { value: '', label: 'Todas' },
      { value: 'COP', label: 'COP' },
      { value: 'USD', label: 'USD' },
    ],
  },
  {
    kind: 'segmented',
    key: 'cost_type',
    label: 'Tipo',
    options: [
      { value: '', label: 'Todos' },
      { value: 'fixed', label: 'Fijo' },
      { value: 'variable', label: 'Variable' },
    ],
  },
  { kind: 'range', minKey: 'price_min', maxKey: 'price_max', label: 'Precio', type: 'money' },
  {
    kind: 'segmented',
    key: 'is_active',
    label: 'Estado',
    options: [
      { value: '', label: 'Todos' },
      { value: 'true', label: 'Activos' },
      { value: 'false', label: 'Inactivos' },
    ],
  },
]);

const EXPORT_MAPPING = {
  category: 'category',
  frequency: 'frequency',
  payment_method: 'payment_method',
  currency: 'currency',
  cost_type: 'cost_type',
  price_min: 'amount_min',
  price_max: 'amount_max',
  is_active: 'is_active',
  search: 'q',
};

const exportParams = computed(() => ({
  ...buildExportParams(currentFilters, EXPORT_MAPPING),
  archive_scope: archiveScope.value,
}));

// -------------------------------------------------------------------
// Data + table
// -------------------------------------------------------------------

// Shared by both views. The two monthly columns are derived server-side and
// read-only: they answer "what does this actually cost me per month", which
// the raw price cannot when periodicities differ.
// The three amounts are variants of one number, so `group: 'money'` draws them
// together and puts the wider gap before Frecuencia, which is another kind of
// information. `size` is only declared where the format cannot imply it: Tipo
// and Estado render badges through slots, not `format: 'badge'`.
// `hideBelow` collapses the least load-bearing columns first — name, monthly
// equivalent and status survive every width.
const SHARED_COLUMNS = [
  {
    key: 'name', label: 'Nombre', size: 'name', sortable: true,
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'price', label: 'Precio', align: 'right', size: 'money', group: 'money', hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'monthly_price', label: 'Precio mensual', align: 'right', size: 'money', group: 'money', hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'monthly_cop_cost', label: 'Equiv. COP mensual', format: 'money', group: 'money', sortable: true,
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'frequency_label', label: 'Frecuencia', hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'payment_method_label', label: 'Método', hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'billing_day', label: 'Día', align: 'center', size: 'tiny', sortable: true, hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  // Preformatted by the API (like frequency_label), so both view modes render
  // it as plain text and neither has to format a date.
  {
    key: 'next_charge_label', label: 'Próximo cobro', size: 'text', hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'cost_type_label', label: 'Tipo', size: 'badge', hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'is_active', label: 'Estado', size: 'badge',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
];

// Classic view needs the category as a column; the grouped view has it as a
// group header, so repeating it in every row would be noise.
const columns = [
  SHARED_COLUMNS[0],
  {
    key: 'category_name', label: 'Categoría', hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  ...SHARED_COLUMNS.slice(1),
];

const groupedColumns = SHARED_COLUMNS.map(({ sortable, ...col }) => col);

const filteredRows = computed(() => applyFilters(store.recurringPayments));
const filteredIds = computed(() => filteredRows.value.map((row) => row.id));
const { selectedIds, clearSelection, dropIds } = useRowSelection(
  () => store.recurringPayments,
);

const emptyTitle = computed(() => {
  if (hasActiveFilters.value) return 'Sin resultados con esos filtros';
  return isArchivedScope.value
    ? 'No hay pagos recurrentes archivados'
    : 'No hay pagos recurrentes aún';
});
const emptyDescription = computed(() => {
  if (hasActiveFilters.value) return 'Ajusta o limpia los filtros para ver más registros.';
  return isArchivedScope.value
    ? 'Los servicios que archives aparecerán aquí y conservarán su información.'
    : 'Registra la primera suscripción o costo operativo.';
});

// Contribution to the weight base: only active rows count, matching the
// server's monthly_cop_total meta. Inactive rows show 0% and stay out of the
// base, so the active ones read as a 100% composition. The grouped subtotal
// and footer use that same budget predicate: an inactive or archived service
// stays visible for management without inflating what is actually being paid.
function activeMonthlyCop(row) {
  return row.is_active && !row.is_archived ? Number(row.monthly_cop_cost) || 0 : 0;
}

const weightedRows = computed(() => addWeightPct(filteredRows.value, activeMonthlyCop));

const activeBase = computed(() =>
  filteredRows.value.reduce((total, row) => total + activeMonthlyCop(row), 0),
);

function recurringStateLabel(row) {
  if (row.is_archived) return 'Archivado';
  return row.is_active ? 'Activo' : 'Inactivo';
}

function recurringStateClass(row) {
  if (row.is_archived) return 'bg-surface-raised text-text-muted';
  return row.is_active
    ? 'bg-success-soft text-success-strong'
    : 'bg-warning-soft text-warning-strong';
}

// -------------------------------------------------------------------
// View mode, grouping and manual order
// -------------------------------------------------------------------

const { viewMode } = useRecurringViewMode();
const isGrouped = computed(() => viewMode.value === 'grouped');

const viewModeOptions = [
  { value: 'grouped', label: 'Agrupado' },
  { value: 'table', label: 'Clásico' },
];

const collapsedGroupIds = ref([]);
const showCategoriesModal = ref(false);
const showChartsModal = ref(false);

/**
 * Human labels for whatever the table is filtering by.
 *
 * The charts modal reads the same filtered rows the table shows, so its total
 * can legitimately differ from the "Costo mensual (COP)" card. Spelling the
 * filters out as chips is what turns that from a discrepancy into a caption.
 */
const inheritedChartChips = computed(() => {
  const chips = [];

  if (activeTabId.value !== 'all') {
    const tab = savedTabs.value.find((saved) => String(saved.id) === String(activeTabId.value));
    if (tab) chips.push(`Vista: ${tab.name}`);
  }
  if (currentFilters.search) chips.push(`Búsqueda: "${currentFilters.search}"`);

  filterFields.value.forEach((field) => {
    if (field.kind === 'range') {
      const min = currentFilters[field.minKey];
      const max = currentFilters[field.maxKey];
      if (min || max) {
        chips.push(`${field.label}: ${min ? money(min) : '—'} a ${max ? money(max) : '—'}`);
      }
      return;
    }
    const labelFor = (value) =>
      field.options.find((option) => String(option.value) === String(value))?.label
      ?? String(value);
    const current = currentFilters[field.key];
    if (Array.isArray(current)) {
      if (current.length) chips.push(`${field.label}: ${current.map(labelFor).join(', ')}`);
    } else if (current !== '' && current != null) {
      chips.push(`${field.label}: ${labelFor(current)}`);
    }
  });

  return chips;
});

const groups = computed(() =>
  withGroupWeights(
    groupByCategory(weightedRows.value, store.recurringCategories),
    activeBase.value,
  ),
);

// Temporary weight-sort for the grouped view: '' | 'desc' | 'asc'. It only
// reorders what is DISPLAYED — the persisted manual order is never written.
const groupedWeightSort = ref('');

function toggleGroupedWeightSort() {
  groupedWeightSort.value =
    groupedWeightSort.value === '' ? 'desc'
      : groupedWeightSort.value === 'desc' ? 'asc' : '';
}

// Groups AND the rows inside them sort by weight while the toggle is on:
// the point is scanning "what weighs most", which a catalog-ordered list of
// groups would break. Copies only — clearing the sort falls back to the
// untouched manual order.
const displayGroups = computed(() => {
  if (!groupedWeightSort.value) return groups.value;
  const direction = groupedWeightSort.value === 'desc' ? -1 : 1;
  return [...groups.value]
    .sort((a, b) => direction * (a.groupWeightPct - b.groupWeightPct))
    .map((group) => ({
      ...group,
      rows: [...group.rows].sort((a, b) => direction * (a.weight_pct - b.weight_pct)),
    }));
});

/**
 * Dragging is only offered on the complete list in its manual order.
 * Reordering a filtered view would let the operator arrange rows around
 * neighbours they cannot see, and a weight-sorted view would persist an
 * order they meant as a temporary reading.
 */
const canReorder = computed(() =>
  !isArchivedScope.value
  && isGrouped.value
  && !hasActiveFilters.value
  && !groupedWeightSort.value,
);

function toggleGroup(id) {
  collapsedGroupIds.value = collapsedGroupIds.value.includes(id)
    ? collapsedGroupIds.value.filter((groupId) => groupId !== id)
    : [...collapsedGroupIds.value, id];
}

async function handleReorder(items) {
  const result = await store.reorderRecurring(items);
  if (!result.success) {
    notify.error({
      title: 'No se pudo guardar el nuevo orden',
      detail: result.message || '',
    });
  }
}

const {
  isModalOpen: showFormModal,
  editingRecord,
  seedRecord,
  openCreateModal,
  lastMutatedId,
  openEditModal,
  openSeededModal,
  closeModal: closeFormModal,
  handleSubmit: submitForm,
  confirmState,
  handleConfirmed,
  handleCancelled,
  requestConfirm,
  runMutation,
  currentPage,
  totalPages,
  totalItems,
  rangeFrom,
  rangeTo,
  pagedRecords: pagedRows,
  prevPage: prev,
  nextPage: next,
  goToPage: goTo,
  handleCreateFilterTab: handleCreateTab,
  sortKey,
  sortDir,
  toggleSort,
} = useAccountingCrudPage({
  entity: 'recurring',
  resetPageOn: currentFilters,
  store,
  filteredRecords: weightedRows,
  labels: {
    created: 'Pago recurrente creado',
    duplicated: 'Pago recurrente duplicado',
    updated: 'Pago recurrente actualizado',
    deleted: 'Pago recurrente eliminado',
    saveErrorTitle: (editing) =>
      editing
        ? 'No se pudo actualizar el pago recurrente'
        : 'No se pudo crear el pago recurrente',
    deleteErrorTitle: 'No se pudo eliminar el pago recurrente',
    deleteTitle: 'Eliminar pago recurrente',
    deleteMessage: (record) =>
      `Esto eliminará "${record.name}" de forma permanente. ` +
      'Esta acción no se puede deshacer.',
  },
  // Refetch: the monthly COP total meta is computed server-side, and the
  // per-category payment counts shift whenever a record moves group.
  onAfterMutation: loadAll,
  // Sorting the COP column sorts by weight: identical order for active rows
  // (the % is monotonic on the value), inactive rows (0%) sink to the end.
  sortAccessors: { monthly_cop_cost: 'weight_pct' },
  sortDefaults: { monthly_cop_cost: 'desc' },
  saveTab,
  isFilterPanelOpen,
});

const monthlyCopTotal = computed(() => store.metaFor('recurring').monthly_cop_total ?? 0);

const monthlyUsdTotal = computed(() => {
  const value = store.metaFor('recurring').monthly_usd_total;
  return value == null ? null : Number(value);
});

const usdKpiSub = computed(() => {
  const meta = store.metaFor('recurring');
  const parts = [];
  if (meta.usd_exchange_rate != null) {
    parts.push(`Tasa: ${formatMoney(Number(meta.usd_exchange_rate), 'COP')}/USD`);
  }
  if (Number(meta.usd_native_total ?? 0) > 0) {
    parts.push(`Nativos USD: ${formatMoney(Number(meta.usd_native_total), 'USD')}`);
  }
  return parts.join(' · ');
});
const breakdownView = ref('category');
const breakdownOptions = [
  { value: 'category', label: 'Categoría' },
  { value: 'frequency', label: 'Frecuencia' },
  { value: 'payment_method', label: 'Método' },
];

// Every breakdown is monthly, so all three add up to the "Costo mensual (COP)"
// card above them.
const breakdownEntries = computed(() => {
  if (breakdownView.value === 'category') {
    return store.recurringTotalsByCategory.map((entry) => [entry.name, entry.total]);
  }
  return Object.entries(store.recurringMonthlyTotalsBy(breakdownView.value));
});

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

// -------------------------------------------------------------------
// Row and bulk lifecycle actions
// -------------------------------------------------------------------

const actionsOpen = ref(false);
const actionsRow = ref(null);
// Opened from the row menu: the leading track only fits the kebab.
const historyRow = ref(null);
// «Ver nota» is a menu entry only when the payment has one.
const noteRow = ref(null);
const duplicatingId = ref(null);
const muteModalOpen = ref(false);
const mutingRecord = ref(null);

function openActions(row) {
  actionsRow.value = row;
  actionsOpen.value = true;
}

async function duplicateRecurring(row) {
  if (duplicatingId.value !== null) return;
  duplicatingId.value = row.id;
  let result;
  try {
    result = await store.fetchRecurringDuplicateDraft(row.id);
  } finally {
    duplicatingId.value = null;
  }
  if (!result.success) {
    notify.error({
      title: 'No se pudo preparar el duplicado',
      detail: result.message || '',
    });
    return;
  }
  openSeededModal(result.data);
}

async function submitRecurringForm(payload) {
  const isCreating = !editingRecord.value;
  const result = await submitForm(payload);
  if (result.success && isCreating && isArchivedScope.value) {
    archiveScope.value = 'current';
  }
}

async function toggleRecurringState(row) {
  const activating = !row.is_active;
  await runMutation(
    () => store.setRecurringActive(row.id, activating),
    {
      successTitle: activating
        ? 'Pago recurrente activado'
        : 'Pago recurrente desactivado',
      errorTitle: activating
        ? 'No se pudo activar el pago recurrente'
        : 'No se pudo desactivar el pago recurrente',
      flashId: row.id,
    },
  );
}

function confirmArchiveRecurring(row) {
  requestConfirm({
    title: 'Archivar pago recurrente',
    message: `“${row.name}” se desactivará y pasará a Archivados. `
      + 'Su configuración y su trazabilidad se conservarán.',
    variant: 'warning',
    confirmText: 'Archivar',
    cancelText: 'Cancelar',
    onConfirm: () => runMutation(
      () => store.archiveRecurring(row.id),
      {
        successTitle: 'Pago recurrente archivado',
        errorTitle: 'No se pudo archivar el pago recurrente',
      },
    ),
  });
}

async function restoreRecurring(row) {
  await runMutation(
    () => store.restoreRecurring(row.id),
    {
      successTitle: 'Pago recurrente restaurado como inactivo',
      errorTitle: 'No se pudo restaurar el pago recurrente',
    },
  );
}

function toggleRecurringMute(row) {
  if (row.reminders_effectively_muted) {
    runMutation(
      () => store.muteRecurringReminders(row.id, { muted: false, until: null }),
      {
        successTitle: 'Avisos reactivados',
        errorTitle: 'No se pudieron reactivar los avisos',
        flashId: row.id,
      },
    );
    return;
  }
  mutingRecord.value = row;
  muteModalOpen.value = true;
}

function closeMuteModal() {
  muteModalOpen.value = false;
  mutingRecord.value = null;
}

async function submitRecurringMute(payload) {
  if (!mutingRecord.value) return;
  const result = await runMutation(
    () => store.muteRecurringReminders(mutingRecord.value.id, payload),
    {
      successTitle: 'Avisos silenciados',
      errorTitle: 'No se pudieron silenciar los avisos',
      flashId: mutingRecord.value.id,
    },
  );
  if (result.success) closeMuteModal();
}

function confirmPermanentDelete(row) {
  requestConfirm({
    title: 'Eliminar definitivamente',
    message: `Esto borrará “${row.name}” de forma permanente. `
      + 'Usa esta opción solo para registros que nunca debieron existir.',
    variant: 'danger',
    confirmText: 'Eliminar definitivamente',
    cancelText: 'Cancelar',
    requireTypeText: 'ELIMINAR',
    onConfirm: () => runMutation(
      () => store.deleteRecord('recurring', row.id),
      {
        successTitle: 'Pago recurrente eliminado definitivamente',
        errorTitle: 'No se pudo eliminar el pago recurrente',
      },
    ),
  });
}

const BULK_ACTION_COPY = {
  activate: {
    success: 'Pagos recurrentes activados',
    error: 'No se pudieron activar los pagos recurrentes',
  },
  deactivate: {
    success: 'Pagos recurrentes desactivados',
    error: 'No se pudieron desactivar los pagos recurrentes',
  },
  archive: {
    success: 'Pagos recurrentes archivados',
    error: 'No se pudieron archivar los pagos recurrentes',
  },
};

async function applyBulkRecurringAction({ ids, action }) {
  const copy = BULK_ACTION_COPY[action];
  const result = await runMutation(
    () => store.bulkRecurringAction(ids, action),
    {
      successTitle: copy.success,
      successDetail: (response) => (
        `${response.data?.updated ?? 0} registro(s) modificado(s).`
      ),
      errorTitle: copy.error,
    },
  );
  if (result.success) {
    clearSelection();
    return;
  }
  if (result.missingIds?.length) {
    dropIds(result.missingIds);
    await loadRecords();
  }
}

// -------------------------------------------------------------------
// Category catalog
// -------------------------------------------------------------------

async function createCategory(name) {
  await runMutation(
    () => store.createRecord('recurringCategories', { name }),
    {
      successTitle: 'Categoría creada',
      errorTitle: 'No se pudo crear la categoría',
    },
  );
}

async function renameCategory({ id, name }) {
  await runMutation(
    () => store.updateRecord('recurringCategories', id, { name }),
    {
      successTitle: 'Categoría actualizada',
      errorTitle: 'No se pudo renombrar la categoría',
    },
  );
}

function confirmDeleteCategory(category) {
  requestConfirm({
    title: 'Eliminar categoría',
    message: `Esto eliminará "${category.name}". Los recurrentes que la usen deben moverse antes.`,
    variant: 'danger',
    confirmText: 'Eliminar',
    cancelText: 'Cancelar',
    onConfirm: () => runMutation(
      () => store.deleteRecord('recurringCategories', category.id),
      {
        successTitle: 'Categoría eliminada',
        errorTitle: 'No se pudo eliminar la categoría',
      },
    ),
  });
}

async function reorderCategories(ids) {
  const result = await store.reorderRecurringCategories(ids);
  if (!result.success) {
    notify.error({
      title: 'No se pudo guardar el orden de las categorías',
      detail: result.message || '',
    });
  }
}

async function loadCategories() {
  const result = await store.fetchRecords('recurringCategories');
  if (!result.success) {
    notify.error({ title: 'No se pudieron cargar las categorías', detail: result.message });
  }
}

async function loadRecords() {
  const result = await store.fetchRecords('recurring', {
    archive_scope: archiveScope.value,
  });
  if (!result.success) {
    notify.error({ title: 'No se pudieron cargar los pagos recurrentes', detail: result.message });
  }
}

async function loadAll() {
  // Categories first: grouping and the category filter both read them.
  await loadCategories();
  await loadRecords();
}

watch(archiveScope, async () => {
  clearSelection();
  collapsedGroupIds.value = [];
  groupedWeightSort.value = '';
  showChartsModal.value = false;
  goTo(1);
  await loadRecords();
});

onMounted(loadAll);
usePanelRefresh(loadAll);
</script>
