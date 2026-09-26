<template>
  <BasePageShell>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Cuentas de cobro</h1>
        <p class="text-sm text-text-subtle mt-1">
          Crea, envía y da seguimiento a las cuentas de cobro: desde aquí, desde un ingreso o desde Hostings.
        </p>
      </div>
      <BaseButton
        variant="primary"
        class="w-full panel-portrait:w-auto"
        data-testid="collection-create-button"
        @click="openCreateModal"
      >
        Nueva cuenta de cobro
      </BaseButton>
    </div>

    <AccountingSubnav active="collections" />

    <!-- Status counters -->
    <AccountingIndicatorGroup :columns="4" :secondary-count="1">
      <template #primary>
        <AccountingStatCard
          label="Vencidas"
          :value="String(overdueCount)"
          :tone="overdueCount > 0 ? 'warning' : 'default'"
          sub="Emitidas con fecha límite pasada"
        />
        <AccountingStatCard
          label="Emitidas"
          :value="String(meta.issued_count ?? 0)"
          :sub="`Por cobrar: ${money(meta.issued_total)}`"
          tone="brand"
        />
        <AccountingStatCard
          label="Pagadas"
          :value="String(meta.paid_count ?? 0)"
          :sub="`Recaudado: ${money(meta.paid_total)}`"
          tone="success"
        />
      </template>
      <template #secondary>
        <AccountingStatCard
          label="Anuladas"
          :value="String(meta.cancelled_count ?? 0)"
        />
      </template>
    </AccountingIndicatorGroup>

    <!-- Quick + saved filter tabs -->
    <ProposalFilterTabs
      :tabs="displayTabs"
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

    <!-- Search + filter toggle -->
    <div class="flex flex-wrap items-center gap-2 mb-5">
      <BaseInput
        v-model="searchInput"
        type="text"
        placeholder="Buscar por número, cliente, proyecto o concepto..."
        data-testid="collections-search-input"
        class="w-full sm:max-w-xs"
      />
      <UiFilterToggleButton
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
      <!-- The status bar stays out of the panel: it is the day-to-day
           control and the panel is collapsed by default. -->
      <BaseSegmentedMulti
        v-model="currentFilters.status"
        :options="statusOptions"
        label="Estado"
        test-id-prefix="collections-status"
        size="sm"
        class="w-full panel-portrait:w-auto"
      />
      <div class="flex flex-wrap items-center gap-2 w-full panel-portrait:ml-auto panel-portrait:w-auto">
        <BaseSegmented
          :model-value="viewMode"
          :options="viewModeOptions"
          :disabled="isSavingViewPreferences"
          size="sm"
          aria-label="Vista de cuentas de cobro"
          data-testid="collections-view-mode"
          @update:model-value="changeViewMode"
        />
        <BaseSegmented
          v-if="isGrouped"
          :model-value="groupBy"
          :options="groupByOptions"
          :disabled="isSavingViewPreferences"
          size="sm"
          aria-label="Agrupar cuentas de cobro por"
          data-testid="collections-group-by"
          @update:model-value="changeGroupBy"
        />
      </div>
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
      title="No se pudieron cargar las cuentas de cobro"
      :retrying="store.isLoading"
      @retry="loadRecords"
    />

    <!-- Empty -->
    <BaseEmptyState
      v-else-if="!store.isLoading && filteredRows.length === 0"
      :title="hasActiveFilters ? 'Sin resultados con esos filtros' : 'Sin cuentas de cobro'"
      :description="hasActiveFilters
        ? 'Ajusta o limpia los filtros para ver más registros.'
        : `Crea la primera con 'Nueva cuenta de cobro', desde un ingreso en el tab Ingresos, o desde Hostings con 'Enviar cuenta de cobro'.`"
    >
      <BaseButton variant="primary" data-testid="collection-empty-create" @click="openCreateModal">
        Nueva cuenta de cobro
      </BaseButton>
    </BaseEmptyState>

    <!-- Table -->
    <template v-else>
      <component
        :is="activeTableComponent"
        v-bind="activeTableProps"
        v-on="activeTableListeners"
      >
        <!-- El número es la dirección del detalle: un enlace de verdad, no sólo
             el ojo de la columna de acciones. -->
        <template #cell-public_number="{ row }">
          <BaseRowLink
            :to="accountDetailTo(row.id)"
            :stretch="!isGrouped"
            :data-testid="`collection-open-${row.id}`"
            class="block font-medium text-text-default hover:text-text-brand transition-colors"
            :title="row.billing_concept"
          >
            {{ row.public_number || `#${row.id}` }}
          </BaseRowLink>
        </template>
        <template #cell-origin="{ row }">
          <BaseBadge
            :variant="originBadgeVariant(row.origin)"
            size="sm"
            class="font-semibold uppercase tracking-wider"
          >
            {{ originLabel(row.origin) }}
          </BaseBadge>
        </template>
        <template #cell-client_display_name="{ row }">
          <span class="inline-flex min-w-0 flex-wrap items-center gap-1.5">
            <span class="min-w-0 break-words text-text-default">
              {{ row.client_display_name || row.customer_name || '—' }}
            </span>
            <BaseBadge
              v-if="!row.client"
              variant="warning"
              size="sm"
              title="Sin cliente vinculado — el nombre viene del documento emitido"
              :data-testid="`collection-unlinked-${row.id}`"
            >
              sin vincular
            </BaseBadge>
          </span>
        </template>
        <template #cell-project_name="{ row }">
          <span v-if="row.project_name" class="inline-flex min-w-0 flex-wrap items-center gap-1 text-text-default">
            <span class="min-w-0 break-words">{{ row.project_name }}</span>
            <!-- Only documents whose live FK survives get the jump; older
                 rows keep the frozen snapshot text with no link (by design). -->
            <ProjectSpaceLink
              :project-id="row.project_id"
              :data-testid="`collection-project-space-${row.id}`"
            />
          </span>
          <!-- Empty is a legitimate state here (a cobro por diagnóstico has
               no project yet), so it gets no debt pill — unlike the client. -->
          <span
            v-else
            class="text-text-subtle"
            title="Sin proyecto — típico de un cobro por diagnóstico"
            :data-testid="`collection-no-project-${row.id}`"
          >—</span>
        </template>
        <template #cell-commercial_status="{ row }">
          <BaseBadge
            :variant="collectionStatusBadgeVariant(row)"
            :data-testid="`collection-status-${row.id}`"
          >
            {{ row.is_overdue ? 'Vencida' : row.commercial_status_label }}
          </BaseBadge>
        </template>
        <template #row-actions="{ row }">
          <div class="flex items-center justify-center">
            <BaseActionButton
              action="more"
              variant="ghost"
              size="sm"
              class="h-11 w-11 shrink-0"
              :label="`Acciones de ${row.public_number || `cuenta ${row.id}`}`"
              :disabled="busyId === row.id"
              :data-testid="`collection-actions-${row.id}`"
              @click.stop="actionsRow = row"
            />
          </div>
        </template>
      </component>
    </template>

    <CollectionActionsModal
      :open="actionsRow !== null"
      :record="actionsRow"
      :busy="busyId === actionsRow?.id"
      @close="actionsRow = null"
      @detail="openDetail"
      @notes="notesRow = $event"
      @download="downloadPdf"
      @emails="goToCollectionEmails"
      @resend="askResend"
      @mark-paid="askMarkPaid"
      @cancel="askCancel"
      @delete="askDelete"
    />

    <ConfirmModal
      v-model="confirmOpen"
      :title="confirmTitle"
      :message="confirmMessage"
      :confirm-text="confirmText"
      cancel-text="Cancelar"
      :variant="confirmVariant"
      :require-type-text="confirmTypeText"
      @confirm="handleConfirmed"
      @cancel="pendingAction = null"
    >
      <!-- Eliminar es el único irreversible: nombra el documento que se va
           antes de pedir la palabra, para que el consecutivo, el cliente y el
           monto se puedan contrastar sin cerrar el modal. -->
      <dl v-if="deletingRow" class="text-sm space-y-1">
        <div class="flex justify-between gap-4">
          <dt class="text-text-muted">Consecutivo</dt>
          <dd class="font-mono font-semibold text-text-default">
            {{ deletingRow.public_number || `#${deletingRow.id}` }}
          </dd>
        </div>
        <div class="flex justify-between gap-4">
          <dt class="text-text-muted">Cliente</dt>
          <dd class="text-text-default">
            {{ deletingRow.client_display_name || deletingRow.customer_name || 'Sin cliente' }}
          </dd>
        </div>
        <div class="flex justify-between gap-4">
          <dt class="text-text-muted">Monto</dt>
          <dd class="font-semibold text-text-default">{{ money(deletingRow.total) }}</dd>
        </div>
      </dl>
    </ConfirmModal>

    <!-- Internal notes, read-only: written in the create form, never sent.
         Same note dialog as every accounting menu, plus who can read it. -->
    <AccountingNoteModal
      :open="notesRow !== null"
      :title="`Notas internas · ${notesRow?.public_number || `#${notesRow?.id}`}`"
      hint="Sólo para ti: no se muestran al cliente ni viajan en el PDF o el correo."
      :notes="notesRow?.notes ?? ''"
      @close="notesRow = null"
    />

    <!-- Create modal: form → preview del correo/PDF → confirmar y enviar -->
    <CollectionAccountFormModal
      :open="createOpen"
      @close="createOpen = false"
      @created="onCreated"
    />

    <!-- Detalle: el ingreso vinculado y el documento, sin salir del tab -->
    <CollectionAccountDetailModal
      :open="detailOpen"
      :record="detailRow"
      @close="closeDetail"
      @download="downloadPdf"
      @go-to-income="goToIncome"
    />

    <!-- Marking an expected-linked cuenta as paid routes through Liquidar:
         settling the income is what flips the cuenta (backend sync). -->
    <IncomeLiquidateModal
      :open="liquidateOpen"
      :record="liquidatingIncome"
      :saving="store.isUpdating"
      @close="closeLiquidate"
      @submit="handleLiquidateSubmit"
    />
  </BasePageShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import AccountingSubnav from '~/components/accounting/AccountingSubnav.vue';
import AccountingIndicatorGroup from '~/components/accounting/AccountingIndicatorGroup.vue';
import AccountingStatCard from '~/components/accounting/AccountingStatCard.vue';
import AccountingTable from '~/components/accounting/AccountingTable.vue';
import CollectionAccountsGroupedTable from '~/components/accounting/CollectionAccountsGroupedTable.vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import AccountingFilterPanel from '~/components/accounting/AccountingFilterPanel.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import CollectionAccountFormModal from '~/components/accounting/CollectionAccountFormModal.vue';
import CollectionAccountDetailModal from '~/components/accounting/CollectionAccountDetailModal.vue';
import CollectionActionsModal from '~/components/accounting/CollectionActionsModal.vue';
import IncomeLiquidateModal from '~/components/accounting/IncomeLiquidateModal.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import BaseBadge from '~/components/base/BaseBadge.vue';
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseSegmentedMulti from '~/components/base/BaseSegmentedMulti.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import ProjectSpaceLink from '~/components/panel/projects/ProjectSpaceLink.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useCollectionAccountsViewPreferences } from '~/composables/useCollectionAccountsViewPreferences';
import {
  useAccountingFilters,
  matchDateRange,
  matchNumberRange,
  matchAnyToken,
} from '~/composables/useAccountingFilters';
import { useTableSort } from '~/composables/useTableSort';
import { useDetailQueryParam } from '~/composables/useDetailQueryParam';
import { useAccountingStore } from '~/stores/accounting';
import { usePanelProjectsStore } from '~/stores/panel_projects';
import { get_request } from '~/stores/services/request_http';
import { downloadBlob, filenameFromDisposition } from '~/utils/downloadFile';
import { formatMoney } from '~/utils/formatMoney';
import { historySendsLink } from '~/utils/historyDeepLink';
import {
  NO_COLLECTION_GROUP_KEY,
  groupCollectionAccounts,
  sumCollectionAccountGroups,
} from '~/utils/collectionAccounts';
import { originLabel } from '~/utils/collectionStatus';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const store = useAccountingStore();
const projectsStore = usePanelProjectsStore();
const notify = usePanelNotify();
const actionsRow = ref(null);

const meta = computed(() => store.collectionAccountsMeta || {});

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

function originBadgeVariant(origin) {
  return { hosting: 'info', income: 'primary' }[origin] || 'neutral';
}

function collectionStatusBadgeVariant(row) {
  if (row?.is_overdue) return 'warning';
  return {
    draft: 'neutral', issued: 'info', paid: 'success', cancelled: 'danger',
  }[row?.commercial_status] || 'neutral';
}

const statusOptions = [
  { value: '', label: 'Todas' },
  { value: 'issued', label: 'Emitidas' },
  { value: 'overdue', label: 'Vencidas' },
  { value: 'paid', label: 'Pagadas' },
  { value: 'cancelled', label: 'Anuladas' },
];

const viewModeOptions = [
  { value: 'grouped', label: 'Agrupado', testId: 'collections-view-grouped' },
  { value: 'classic', label: 'Clásico', testId: 'collections-view-classic' },
];

const groupByOptions = [
  { value: 'client', label: 'Cliente', testId: 'collections-group-client' },
  { value: 'project', label: 'Proyecto', testId: 'collections-group-project' },
];

const collectionGroupMetrics = [
  { key: 'emitted', label: 'Emitido', format: 'money', tone: 'muted' },
  { key: 'pending', label: 'Por cobrar', format: 'money', tone: 'warning' },
  { key: 'collected', label: 'Recaudado', format: 'money', tone: 'success' },
  { key: 'cancelled', label: 'Anulado', format: 'money', tone: 'danger' },
];

const collectionStatusDefinitions = [
  { key: 'draft', label: 'Borradores', tone: 'muted' },
  { key: 'issued', label: 'Emitidas', tone: 'brand' },
  { key: 'overdue', label: 'Vencidas', tone: 'warning' },
  { key: 'paid', label: 'Pagadas', tone: 'success' },
  { key: 'cancelled', label: 'Anuladas', tone: 'danger' },
];

const NO_CLIENT_KEY = 'none';
const NO_PROJECT_KEY = 'none';

const matchClients = (record, value) => {
  if (!Array.isArray(value) || value.length === 0) return true;
  if (record.client == null) return value.includes(NO_CLIENT_KEY);
  return value.includes(record.client);
};
matchClients.keys = ['clients'];

// The live FK is the filter key — same contract as hostings/incomes, so one
// project id selects the same work everywhere. The frozen snapshot name only
// answers for legacy rows whose project was deleted (SET_NULL); a row with
// neither never had a project. The CELL follows the same rule since F7:
// `project_name` arrives live from the FK (snapshot only as FK-null
// fallback), so cell and filter can no longer contradict each other. The
// frozen snapshot stays the PDF's truth, untouched.
const matchProjects = (record, value) => {
  if (!Array.isArray(value) || value.length === 0) return true;
  if (record.project_id != null) return value.includes(record.project_id);
  if (record.project_name) return value.includes(record.project_name);
  return value.includes(NO_PROJECT_KEY);
};
matchProjects.keys = ['projects'];

// `overdue` is a computed serializer field, not a commercial_status value, so
// it cannot be an equality test. It also OVERLAPS `issued` — a vencida is an
// emitida that passed its date — which is why the tokens have to union rather
// than fall through an if/elif that only ever answers for the first one.
const matchCommercialStatus = matchAnyToken('status', {
  overdue: (record) => Boolean(record.is_overdue),
  issued: (record) => record.commercial_status === 'issued',
  paid: (record) => record.commercial_status === 'paid',
  cancelled: (record) => record.commercial_status === 'cancelled',
});

const {
  currentFilters,
  searchInput,
  displayTabs,
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
  consumeParam,
} = useAccountingFilters({
  viewName: 'accounting_collections',
  ephemeralParams: ['focus'],
  builtinTabs: [
    // "Por cobrar" used to mean `issued` alone, which quietly left the vencidas
    // out of the one tab whose name promises everything still owed — the same
    // omission "Solo esperados" made with the parciales.
    { id: 'open', name: 'Por cobrar', filters: { status: ['issued', 'overdue'] } },
    { id: 'overdue', name: 'Vencidas', filters: { status: ['overdue'] } },
    { id: 'no-project', name: 'Sin proyecto', filters: { projects: [NO_PROJECT_KEY] } },
  ],
  // 'all', never a narrowing builtin: this is the page other tabs deep-link
  // INTO, and Ingresos landing on its own builtin is exactly what made a
  // focused row arrive filtered out of its own list.
  defaultTabId: 'all',
  defaults: {
    clients: [],
    projects: [],
    status: [],
    issueAfter: '',
    issueBefore: '',
    totalMin: '',
    totalMax: '',
  },
  matchers: {
    clients: matchClients,
    projects: matchProjects,
    status: matchCommercialStatus,
    issue: matchDateRange('issue_date', 'issueAfter', 'issueBefore'),
    total: matchNumberRange('total', 'totalMin', 'totalMax'),
  },
  searchFields: [
    'public_number', 'client_display_name', 'project_name',
    'billing_concept', 'customer_name',
  ],
});

// ?focus=<id> flashes a row (bidirectional navigation from Ingresos). Se lee
// por `consumeParam` y no por `route.query`: el param siembra la vista una vez
// y sale de la URL, en vez de quedarse re-encendiendo el destello en cada F5.
const focusParam = consumeParam('focus');
const highlightId = ref(focusParam ? Number(focusParam) : null);

const filteredRows = computed(() => applyFilters(store.collectionAccounts));

const {
  viewMode,
  groupBy,
  isGrouped,
  isSaving: isSavingViewPreferences,
  initFromSettings,
  setViewMode,
  setGroupBy,
} = useCollectionAccountsViewPreferences(store);

const collapsedGroupIds = ref([]);

function toggleGroup(id) {
  collapsedGroupIds.value = collapsedGroupIds.value.includes(id)
    ? collapsedGroupIds.value.filter((groupId) => groupId !== id)
    : [...collapsedGroupIds.value, id];
}

async function changeViewMode(mode) {
  const result = await setViewMode(mode);
  if (!result.success && !result.busy) {
    notify.error({
      title: 'No se pudo guardar la vista',
      detail: result.message || 'La preferencia anterior sigue activa.',
    });
  }
}

async function changeGroupBy(criterion) {
  const result = await setGroupBy(criterion);
  if (result.success) {
    collapsedGroupIds.value = [];
    return;
  }
  if (!result.busy) {
    notify.error({
      title: 'No se pudo guardar la agrupación',
      detail: result.message || 'El criterio anterior sigue activo.',
    });
  }
}

const collectionGroups = computed(
  () => groupCollectionAccounts(filteredRows.value, groupBy.value),
);
const collectionTotals = computed(
  () => sumCollectionAccountGroups(collectionGroups.value),
);

/** Derived from the loaded rows, like every other accounting tab. */
const clientFilterOptions = computed(() => {
  const seen = new Map();
  store.collectionAccounts.forEach((row) => {
    if (row.client != null && !seen.has(row.client)) {
      seen.set(row.client, row.client_display_name || `Cliente #${row.client}`);
    }
  });
  const options = [...seen.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
  return [{ value: NO_CLIENT_KEY, label: 'Sin cliente' }, ...options];
});

/**
 * Catalog ids first (history.vue pattern) so a project with zero cuentas is
 * still selectable, defensively unioned with row-derived ids the catalog no
 * longer lists. Legacy snapshot-only rows (FK lost) keep their name entries,
 * marked "(histórico)" — they no longer bucket under "Sin proyecto", because
 * they never lacked one.
 */
const projectFilterOptions = computed(() => {
  const catalog = projectsStore.records ?? [];
  const nameCounts = new Map();
  catalog.forEach((project) => {
    nameCounts.set(project.name, (nameCounts.get(project.name) ?? 0) + 1);
  });
  const seen = new Map();
  catalog.forEach((project) => {
    const ambiguous = (nameCounts.get(project.name) ?? 0) > 1
      && project.client?.name;
    seen.set(
      project.id,
      ambiguous ? `${project.name} — ${project.client.name}` : project.name,
    );
  });
  const legacyNames = new Set();
  store.collectionAccounts.forEach((row) => {
    if (row.project_id != null) {
      if (!seen.has(row.project_id)) {
        seen.set(row.project_id, row.project_name || `Proyecto #${row.project_id}`);
      }
    } else if (row.project_name) {
      legacyNames.add(row.project_name);
    }
  });
  const options = [...seen.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
  const legacy = [...legacyNames]
    .map((name) => ({ value: name, label: `${name} (histórico)` }))
    .sort((a, b) => a.label.localeCompare(b.label));
  return [{ value: NO_PROJECT_KEY, label: 'Sin proyecto' }, ...options, ...legacy];
});

const filterFields = computed(() => [
  {
    kind: 'multi', key: 'clients', label: 'Cliente',
    options: clientFilterOptions.value,
  },
  {
    kind: 'multi', key: 'projects', label: 'Proyecto',
    options: projectFilterOptions.value,
  },
  {
    kind: 'daterange', label: 'Emisión',
    minKey: 'issueAfter', maxKey: 'issueBefore',
  },
  {
    kind: 'range', label: 'Total',
    minKey: 'totalMin', maxKey: 'totalMax', type: 'money',
  },
]);

function handleCreateFilterTab(name) {
  return saveTab(name);
}

function handleResetFilters() {
  resetFilters();
}

const overdueCount = computed(
  () => store.collectionAccounts.filter((row) => row.is_overdue).length,
);

// Cliente and Proyecto are two facts, so they get two columns. `Origen`
// shrinks to a badge: it used to smuggle the hosting's client / the income's
// concept into its label, and both now have a column of their own.
const columns = [
  {
    key: 'public_number', label: 'Número', size: 'text', sortable: true, link: true,
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'origin', label: 'Origen', size: 'badge', hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'client_display_name', label: 'Cliente', size: 'name', sortable: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'project_name', label: 'Proyecto', size: 'name', sortable: true, hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'total', label: 'Total', format: 'money', sortable: true,
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'issue_date', label: 'Emisión', format: 'date', sortable: true, hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'due_date', label: 'Vence', format: 'date', sortable: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'commercial_status', label: 'Estado',
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
];

const { sortKey, sortDir, toggleSort, sortedRecords: sortedRows } = useTableSort(
  filteredRows,
  {
    sortDefaults: {
      total: 'desc',
      issue_date: 'desc',
      due_date: 'desc',
      public_number: 'desc',
      client_display_name: 'asc',
      // An empty project sorts first ascending, which clusters the
      // diagnóstico cobros together on purpose.
      project_name: 'asc',
    },
  },
);

const groupedColumns = computed(() => columns
  .filter((column) => (
    groupBy.value === 'client'
      ? column.key !== 'client_display_name'
      : column.key !== 'project_name'
  ))
  .map(({ sortable, ...column }) => column));

const activeTableComponent = computed(
  () => (isGrouped.value ? CollectionAccountsGroupedTable : AccountingTable),
);

const activeTableProps = computed(() => {
  const common = {
    loading: store.isLoading,
    showActions: true,
    showDefaultActions: false,
    rowActionsLayout: 'menu-start',
    highlightId: highlightId.value,
    highlightQuery: currentFilters.search,
  };
  if (!isGrouped.value) {
    return {
      ...common,
      columns,
      rows: sortedRows.value,
      sortKey: sortKey.value,
      sortDir: sortDir.value,
    };
  }
  return {
    ...common,
    columns: groupedColumns.value,
    groups: collectionGroups.value,
    summaryTotals: collectionTotals.value,
    groupMetrics: collectionGroupMetrics,
    footerMetrics: collectionGroupMetrics,
    statusDefinitions: collectionStatusDefinitions,
    collapsedIds: collapsedGroupIds.value,
    unassignedKey: NO_COLLECTION_GROUP_KEY,
  };
});

const activeTableListeners = computed(() => (
  isGrouped.value ? { 'toggle-group': toggleGroup } : { sort: toggleSort }
));

async function loadRecords() {
  await store.fetchCollectionAccounts();
}

// ── Internal notes ──
//
// They never reach the client (not in the PDF, not in the email), so the panel
// is the only place they can be read back — a note you write and can never
// reopen is the same as no note. A modal and not a tooltip: the table wrapper
// is `overflow-x-auto`, which clips anything positioned absolutely inside a row.

const notesRow = ref(null);

// ── Row actions ──

const busyId = ref(null);

async function downloadPdf(row) {
  try {
    const response = await get_request(
      `accounting/collection-accounts/${row.id}/pdf/`,
      { responseType: 'blob' },
    );
    const filename =
      filenameFromDisposition(response.headers?.['content-disposition'])
      || `${row.public_number || row.id}.pdf`;
    downloadBlob(response.data, filename);
  } catch (error) {
    notify.error({ title: 'No se pudo descargar el PDF' });
    console.error('Error downloading collection account PDF:', error);
  }
}

async function resend(row) {
  busyId.value = row.id;
  const result = await store.resendCollectionAccount(row.id);
  busyId.value = null;
  if (result.success) {
    notify.success({ title: 'Cuenta de cobro reenviada al cliente' });
  } else {
    notify.error({ title: 'No se pudo reenviar', detail: result.message });
  }
}

// Sending mail to a client is not undoable, so it asks first — the same
// treatment anular and marcar pagada already had, and that Hostings already
// gives its equivalent send action.
function askResend(row) {
  pendingAction.value = { kind: 'resend', row };
  confirmOpen.value = true;
}

const confirmOpen = ref(false);
const pendingAction = ref(null);

const CONFIRM_COPY = {
  paid: { title: 'Marcar como pagada', text: 'Marcar pagada', variant: 'info' },
  resend: { title: 'Reenviar cuenta de cobro', text: 'Reenviar', variant: 'info' },
  cancel: { title: 'Anular cuenta de cobro', text: 'Anular', variant: 'danger' },
  delete: { title: 'Eliminar cuenta de cobro', text: 'Eliminar', variant: 'danger' },
};

// El borrado es físico: es la única acción de la tabla que no se puede
// deshacer, así que es la única que pide teclear la palabra.
const deletingRow = computed(
  () => (pendingAction.value?.kind === 'delete' ? pendingAction.value.row : null),
);
const confirmTypeText = computed(() => (deletingRow.value ? 'ELIMINAR' : ''));

const confirmTitle = computed(
  () => CONFIRM_COPY[pendingAction.value?.kind]?.title ?? '',
);
const confirmText = computed(
  () => CONFIRM_COPY[pendingAction.value?.kind]?.text ?? '',
);
// 'primary' is not in ConfirmModal's variant validator (warning|danger|info),
// so it warned in dev and silently fell back to warning styling.
const confirmVariant = computed(
  () => CONFIRM_COPY[pendingAction.value?.kind]?.variant ?? 'warning',
);
const confirmMessage = computed(() => {
  const action = pendingAction.value;
  if (!action?.row) return '';
  const number = action.row.public_number || `#${action.row.id}`;
  if (action.kind === 'paid') return `Se marcará la cuenta ${number} como pagada.`;
  if (action.kind === 'resend') {
    return `Se reenviará ${number} con el PDF adjunto a ${action.row.customer_email || 'el cliente'}.`;
  }
  if (action.kind === 'delete') {
    return 'Se eliminará permanentemente y no se puede deshacer. El consecutivo '
      + 'no se reutiliza: queda un hueco en la numeración. Si la cuenta viene '
      + 'de un ingreso, ese ingreso vuelve a quedar disponible para facturar.';
  }
  return `Se anulará la cuenta ${number}. Si viene de un hosting, los avisos de vencimiento se reactivan.`;
});

// ── Create modal ──

const createOpen = ref(false);

function openCreateModal() {
  createOpen.value = true;
}

function onCreated() {
  createOpen.value = false;
  loadRecords();
}

// ── Detalle de la cuenta (reemplaza el salto al tab de Ingresos) ──

// La cuenta de cobro tiene dirección propia (`?account=`): así el número de la
// fila puede publicarla en un enlace, y recargar o compartir la URL reabre el
// detalle. No es un ephemeralParam a propósito — esos se borran en el setup.
const {
  openRow: detailRow,
  isOpen: detailOpen,
  toFor: accountDetailTo,
  open: openDetailById,
  close: closeDetail,
} = useDetailQueryParam('account', { rows: sortedRows });

function openDetail(row) {
  openDetailById(row.id);
}

// ── Bidirectional navigation ──

/**
 * The modal's optional exit. Ingresos lands on its builtin "Solo esperados"
 * tab unless `accounting_incomeTab` says otherwise, so without it a cuenta
 * linked to a liquid — or to an already-paid expected — arrived at a list
 * that had filtered its own target out.
 */
function goToIncome(incomeId) {
  navigateTo({
    path: '/panel/accounting/incomes',
    query: { focus: incomeId, accounting_incomeTab: 'all' },
  });
}

function goToCollectionEmails(row) {
  navigateTo(historySendsLink('collection_account', row.id));
}

// ── Mark paid: expected-linked cuentas route through Liquidar ──

const liquidateOpen = ref(false);
const liquidatingIncome = ref(null);

function closeLiquidate() {
  liquidateOpen.value = false;
  liquidatingIncome.value = null;
}

async function handleLiquidateSubmit(payload) {
  const incomeId = liquidatingIncome.value?.id;
  const result = await store.settleIncome(incomeId, payload);
  if (result.success) {
    closeLiquidate();
    notify.success({
      title: 'Ingreso liquidado',
      detail: 'Si el ingreso quedó pagado al 100%, la cuenta pasó a Pagada.',
    });
    loadRecords();
  } else {
    notify.error({ title: 'No se pudo liquidar', detail: result.message });
  }
}

async function askMarkPaid(row) {
  // Never settle silently: an expected income with pending balance goes
  // through the Liquidar modal; the backend sync marks the cuenta paid.
  if (row.income_record_id) {
    try {
      const response = await get_request(
        `accounting/incomes/${row.income_record_id}/`,
      );
      const income = response.data;
      if (income?.kind === 'expected' && income?.payment_status !== 'paid') {
        liquidatingIncome.value = income;
        liquidateOpen.value = true;
        return;
      }
    } catch (error) {
      // Falling through here used to settle the cuenta as a plain mark-paid,
      // silently skipping the Liquidar routing this guard exists to enforce.
      console.error('Error fetching linked income:', error);
      notify.error({
        title: 'No se pudo verificar el ingreso vinculado',
        detail: 'Intenta de nuevo antes de marcar la cuenta como pagada.',
      });
      return;
    }
  }
  pendingAction.value = { kind: 'paid', row };
  confirmOpen.value = true;
}

function askCancel(row) {
  pendingAction.value = { kind: 'cancel', row };
  confirmOpen.value = true;
}

function askDelete(row) {
  pendingAction.value = { kind: 'delete', row };
  confirmOpen.value = true;
}

const MUTATIONS = {
  paid: { call: (id) => store.markCollectionAccountPaid(id), title: 'Cuenta marcada como pagada' },
  cancel: { call: (id) => store.cancelCollectionAccount(id), title: 'Cuenta anulada' },
  delete: { call: (id) => store.deleteCollectionAccount(id), title: 'Cuenta de cobro eliminada' },
};

async function handleConfirmed() {
  const action = pendingAction.value;
  pendingAction.value = null;
  if (!action) return;
  if (action.kind === 'resend') {
    await resend(action.row);
    return;
  }
  const mutation = MUTATIONS[action.kind];
  if (!mutation) return;
  busyId.value = action.row.id;
  const result = await mutation.call(action.row.id);
  busyId.value = null;
  if (result.success) {
    notify.success({ title: mutation.title });
    // Refetch, not just the local row drop: los contadores de cabecera y el
    // conteo de resultados salen del mismo endpoint del listado.
    loadRecords();
  } else {
    notify.error({ title: 'No se pudo completar la acción', detail: result.message });
  }
}

onMounted(async () => {
  // Project filter options come from the full catalog (history.vue
  // pattern); the store swallows failures, so an error just means a
  // smaller dropdown, never a blocked page.
  projectsStore.fetchProjects();
  const preferenceResult = await initFromSettings();
  if (!preferenceResult.success) {
    notify.error({
      title: 'No se pudieron cargar las preferencias de vista',
      detail: 'Se usará la vista agrupada por cliente en esta visita.',
    });
  }
  await loadRecords();
});
usePanelRefresh(loadRecords);
</script>
