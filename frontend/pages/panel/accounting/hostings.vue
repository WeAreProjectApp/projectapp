<template>
  <BasePageShell>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Hostings</h1>
        <p class="text-sm text-text-subtle mt-1">
          Servicios de hosting cobrados a clientes y su ingreso mensual.
        </p>
      </div>
      <BaseButton
        variant="primary"
        size="md"
        class="w-full panel-portrait:w-auto"
        data-testid="hostings-new-button"
        @click="openCreateModal"
      >
        <BaseActionIcon action="create" />
        <span>Nuevo hosting</span>
      </BaseButton>
    </div>

    <AccountingSubnav active="hostings" />

    <!-- Meta cards -->
    <AccountingIndicatorGroup :columns="6" :secondary-count="3">
      <template #primary>
        <AccountingStatCard
          label="Por vencer en 30 días"
          :value="String(hostingsMeta.expiring_soon_count ?? 0)"
          :tone="(hostingsMeta.expiring_soon_count ?? 0) > 0 ? 'warning' : 'default'"
          sub="Activos con vigencia próxima"
        />
        <AccountingStatCard
          label="Ingreso mensual"
          :value="formatMoney(hostingsMeta.monthly_income ?? 0)"
          tone="success"
        />
        <AccountingStatCard
          label="Hostings activos"
          :value="String(hostingsMeta.active_count ?? 0)"
          tone="brand"
        />
      </template>
      <template #secondary>
        <AccountingStatCard
          label="Total pagado histórico"
          :value="formatMoney(hostingsMeta.total_paid ?? 0)"
        />
        <AccountingStatCard
          label="Sin cliente"
          :value="String(hostingsMeta.without_client_count ?? 0)"
          :tone="(hostingsMeta.without_client_count ?? 0) > 0 ? 'warning' : 'default'"
          sub="Pendientes de vincular"
        />
        <AccountingStatCard
          label="Sin proyecto"
          :value="String(hostingsMeta.without_project_count ?? 0)"
          :tone="(hostingsMeta.without_project_count ?? 0) > 0 ? 'warning' : 'default'"
          sub="Con cliente, pendientes de proyecto"
        />
      </template>
    </AccountingIndicatorGroup>

    <!-- Saved filter tabs -->
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

    <!-- Search + Filter toggle -->
    <div class="flex flex-wrap items-center gap-2 mb-5">
      <BaseInput
        v-model="searchInput"
        type="text"
        placeholder="Buscar por cliente o dominio..."
        data-testid="hostings-search-input"
        class="w-full sm:max-w-xs"
      />
      <UiFilterToggleButton
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
      <AccountingExportButton section="hosting" :params="exportParams" />
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

    <!-- Error -->
    <AccountingErrorState
      v-if="store.error === 'fetch_failed'"
      title="No se pudieron cargar los hostings"
      :retrying="store.isLoading"
      @retry="loadRecords"
    />

    <!-- Empty -->
    <BaseEmptyState
      v-else-if="!store.isLoading && filteredRecords.length === 0"
      :title="hasActiveFilters ? 'Sin resultados con esos filtros' : 'No hay hostings aún'"
      :description="hasActiveFilters
        ? 'Ajusta o limpia los filtros para ver más registros.'
        : 'Registra el primer contrato de hosting de un cliente.'"
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
          <span>Nuevo hosting</span>
        </BaseButton>
      </template>
    </BaseEmptyState>

    <!-- Table -->
    <template v-else>
      <AccountingTable
        v-model:selected="selectedIds"
        selectable
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
        <!-- The relation, not the free-text label. `client_name` held the
             house convention `Persona - Marca` ("German - Kore"), fusing two
             different facts into one editable cell; it is now the billing
             snapshot and lives in the form. -->
        <template #cell-client_display_name="{ row }">
          <!-- Wraps so a narrow column drops the badge to its own line instead
               of breaking the client name letter by letter. -->
          <span class="inline-flex flex-wrap items-center gap-1.5">
            <HighlightText
              v-if="row.client_display_name"
              :text="row.client_display_name"
              :query="currentFilters.search"
            />
            <!-- Nothing linked yet: show the legacy label so the row is
                 still recognizable while it is completed. -->
            <span v-else class="text-text-subtle italic">{{ row.client_name }}</span>
            <span
              v-if="!row.client"
              class="text-[10px] px-1.5 py-0.5 rounded-full bg-warning-soft text-warning-strong font-semibold uppercase tracking-wider whitespace-nowrap"
              title="Sin cliente vinculado — el cobro y los totales por cliente no lo cuentan"
              :data-testid="`hosting-unlinked-${row.id}`"
            >
              sin vincular
            </span>
          </span>
        </template>
        <template #cell-project_name="{ row }">
          <span v-if="row.project_name" class="inline-flex items-center gap-1">
            <HighlightText
              :text="row.project_name"
              :query="currentFilters.search"
            />
            <ProjectSpaceLink
              :project-id="row.project"
              :data-testid="`hosting-project-space-${row.id}`"
            />
          </span>
          <span
            v-else
            class="text-text-subtle"
            title="Sin proyecto vinculado"
            :data-testid="`hosting-no-project-${row.id}`"
          >—</span>
        </template>
        <!-- El conteo de ciclos es la dirección del histórico: un enlace de
             verdad, no sólo la entrada «Ciclos de pago» del menú de la fila. -->
        <template #cell-cycles_count="{ row }">
          <BaseRowLink
            :to="hostingCyclesTo(row.id)"
            stretch
            :data-testid="`hosting-open-cycles-${row.id}`"
            class="block tabular-nums hover:text-text-brand transition-colors"
            :title="`Ciclos de pago de ${row.client_display_name || row.client_name || row.domain_url}`"
          >
            {{ row.cycles_count }}
          </BaseRowLink>
        </template>
        <template #cell-domain_url="{ row }">
          <AccountingInlineCell
            :value="row.domain_url"
            :saving="inlineSavingKey === `${row.id}:domain_url`"
            @save="saveInline(row, 'domain_url', $event)"
          >
            <a
              v-if="row.domain_url"
              :href="row.domain_url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-text-brand hover:underline truncate inline-block max-w-[180px] align-middle"
              :title="row.domain_url"
              @click.stop
            >
              {{ row.domain_url }}
            </a>
            <span v-else class="text-text-subtle">—</span>
          </AccountingInlineCell>
        </template>
        <template #cell-monthly_value="{ row }">
          <AccountingInlineCell
            type="money"
            :value="row.monthly_value"
            :saving="inlineSavingKey === `${row.id}:monthly_value`"
            @save="saveInline(row, 'monthly_value', $event)"
          >
            <span class="tabular-nums">{{ formatMoney(row.monthly_value, 'COP') }}</span>
            <span
              class="block text-xs text-text-subtle tabular-nums"
              :data-testid="`hosting-weight-${row.id}`"
              title="Peso sobre el ingreso mensual de hostings activos"
            >
              {{ formatPercent(row.weight_pct) }}
            </span>
          </AccountingInlineCell>
        </template>
        <template #cell-validity="{ row }">
          <span class="text-text-muted text-xs whitespace-nowrap">
            {{ row.valid_from || row.valid_to ? `${row.valid_from || '—'} → ${row.valid_to || '—'}` : '—' }}
          </span>
        </template>
        <template #cell-is_active="{ row }">
          <!-- Wraps so the «Cobro enviado» chip drops below the status select
               instead of pushing the last column past a phone's edge. -->
          <div class="flex flex-wrap items-center gap-2">
            <AccountingStatusSelect
              :value="row.is_active"
              :updating="statusUpdatingId === row.id"
              aria-label="Cambiar estado del hosting"
              @change="changeStatus(row, $event)"
            />
            <span
              v-if="row.billing_requested_at"
              class="text-[10px] px-2 py-0.5 rounded-full font-medium bg-info-soft text-info-strong whitespace-nowrap"
              title="Cuenta de cobro enviada para el período actual"
            >
              Cobro enviado
            </span>
          </div>
        </template>
        <!-- One kebab at every width: the cycles, billing, emails, edit and
             delete actions, and the record history, all live in its menu. -->
        <template #row-actions="{ row }">
          <AccountingRowActionsButton
            :label="`Acciones de ${hostingLabel(row)}`"
            :test-id="`hosting-actions-${row.id}`"
            :busy="billingId === row.id"
            busy-label="Enviando cuenta de cobro"
            @open="hostingActionsRow = row"
          />
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

    <!--
      Bulk client assignment: the completion path for unlinked hostings.
      Below the table and sticky (shared bar, same as incomes); outside the
      error/empty/table chain, because a selection whose rows the filter just
      hid still needs its actions.
    -->
    <BulkAssignBar
      v-model:selected="selectedIds"
      :rows="store.hostings"
      :filtered-ids="filteredIds"
      :entity="HOSTING_ENTITY"
      testid-prefix="hostings"
      :record-label="hostingLabel"
      :busy="store.isUpdating"
      project-enabled
      @submit="applyClientToSelection"
      @submit-project="applyProjectToSelection"
    />

    <!-- First modal on purpose: its close must patch before the dialog it
         opens (form, cycles, history, note, confirmation), or the two trade
         focus traps and the page loses its scroll lock. -->
    <HostingActionsModal
      :open="hostingActionsRow !== null"
      :record="hostingActionsRow"
      :billing-busy="billingId === hostingActionsRow?.id"
      @close="hostingActionsRow = null"
      @history="historyRow = $event"
      @notes="noteRow = $event"
      @cycles="openCyclesModal"
      @send-billing="askSendBilling"
      @emails="goToHostingEmails"
      @edit="openEditModal"
      @delete="confirmDeleteRecord"
    />

    <!-- Create/edit modal -->
    <HostingFormModal
      :open="isModalOpen"
      :record="editingRecord"
      :saving="store.isUpdating"
      @close="closeModal"
      @submit="handleSubmit"
      @project-created="onProjectCreated"
    />

    <!-- Post-create offer: a project created inline may have a backlog of
         the client's older records; the same PA-51 modal closes it here. -->
    <ProjectAssignUnlinkedModal
      :open="assignOfferOpen"
      :project="pendingAssignProject"
      @close="dismissAssignOffer"
      @assigned="onUnlinkedAssigned"
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

    <HostingCyclesModal
      :open="cyclesModalOpen"
      :record="cyclesRecord"
      @close="closeCyclesModal"
      @changed="onCyclesChanged"
    />

    <EntityHistoryRecordModal
      :open="historyRow !== null"
      entity-type="hosting"
      :record="historyRow"
      @close="historyRow = null"
    />

    <AccountingNoteModal
      :open="noteRow !== null"
      :subtitle="noteRow ? hostingLabel(noteRow) : ''"
      :notes="noteRow?.notes ?? ''"
      :highlight-query="currentFilters.search"
      @close="noteRow = null"
    />

    <ConfirmModal
      v-model="billingConfirmOpen"
      title="Enviar cuenta de cobro"
      :message="billingConfirmMessage"
      confirm-text="Enviar al cliente"
      cancel-text="Cancelar"
      variant="primary"
      @confirm="sendBilling"
      @cancel="billingRow = null"
    />
  </BasePageShell>
</template>

<script setup>
import EntityHistoryRecordModal from '~/components/history/EntityHistoryRecordModal.vue';
import { computed, onMounted, ref, watch } from 'vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';
import AccountingRowActionsButton from '~/components/accounting/AccountingRowActionsButton.vue';
import AccountingSubnav from '~/components/accounting/AccountingSubnav.vue';
import AccountingTable from '~/components/accounting/AccountingTable.vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import HighlightText from '~/components/ui/HighlightText.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import AccountingFilterPanel from '~/components/accounting/AccountingFilterPanel.vue';
import AccountingExportButton from '~/components/accounting/AccountingExportButton.vue';
import AccountingIndicatorGroup from '~/components/accounting/AccountingIndicatorGroup.vue';
import AccountingStatCard from '~/components/accounting/AccountingStatCard.vue';
import AccountingStatusSelect from '~/components/accounting/AccountingStatusSelect.vue';
import AccountingInlineCell from '~/components/accounting/AccountingInlineCell.vue';
import HostingCyclesModal from '~/components/accounting/HostingCyclesModal.vue';
import HostingActionsModal from '~/components/accounting/HostingActionsModal.vue';
import HostingFormModal from '~/components/accounting/HostingFormModal.vue';
import BulkAssignBar from '~/components/accounting/BulkAssignBar.vue';
import ProjectAssignUnlinkedModal from '~/components/panel/projects/ProjectAssignUnlinkedModal.vue';
import ProjectSpaceLink from '~/components/panel/projects/ProjectSpaceLink.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useAccountingCrudPage } from '~/composables/useAccountingCrudPage';
import { useRowSelection } from '~/composables/useRowSelection';
import { useDetailQueryParam } from '~/composables/useDetailQueryParam';
import {
  useAccountingFilters,
  matchDateRange,
  matchNumberRange,
  matchIncludes,
  matchBooleanIncludes,
} from '~/composables/useAccountingFilters';
import { useAccountingStore } from '~/stores/accounting';
import { usePanelProjectsStore } from '~/stores/panel_projects';
import { buildExportParams } from '~/utils/accountingExportParams';
import { describeAssignmentResult } from '~/utils/clientAssignment';
import { describeProjectAssignmentResult } from '~/utils/projectAssignment';
import { formatMoney } from '~/utils/formatMoney';
import { historySendsLink } from '~/utils/historyDeepLink';
import { clientLabelOf } from '~/utils/incomeClients';
import { addWeightPct, formatPercent } from '~/utils/percent';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const store = useAccountingStore();
const projectsStore = usePanelProjectsStore();
const notify = usePanelNotify();
// Row menu and the dialogs it opens: history and note live in the menu too,
// since the leading track holds nothing but the kebab.
const hostingActionsRow = ref(null);
const historyRow = ref(null);
const noteRow = ref(null);

/** Noun the bulk client bar uses in its confirmation and result copy. */
const HOSTING_ENTITY = { singular: 'hosting', plural: 'hostings' };

/**
 * What the Cliente cell shows and sorts by.
 *
 * Not `clientLabelOf`: that one buckets every unlinked row under "Sin
 * cliente" for the filter list, which is right for a bucket and wrong for a
 * cell — the legacy snapshot has to stay readable until the link is
 * resolved. The "sin vincular" badge beside it is what marks the gap.
 */
const clientNameOf = (row) => row?.client_display_name || row?.client_name || '';

// -------------------------------------------------------------------
// Filters
// -------------------------------------------------------------------

// Sentinel shared with the backend filter: 'none' = still unassigned.
const NO_CLIENT_KEY = 'none';
const NO_CLIENT_LABEL = 'Sin cliente';

const matchClients = (record, value) => {
  if (!Array.isArray(value) || value.length === 0) return true;
  if (record.client == null) return value.includes(NO_CLIENT_KEY);
  return value.includes(record.client);
};
matchClients.keys = ['clients'];

const NO_PROJECT_KEY = 'none';

const matchProjects = (record, value) => {
  if (!Array.isArray(value) || value.length === 0) return true;
  if (record.project == null) return value.includes(NO_PROJECT_KEY);
  return value.includes(record.project);
};
matchProjects.keys = ['projects'];

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
  viewName: 'accounting_hosting',
  // Ambos siembran un filtro: la URL los conserva mientras ese filtro esté
  // puesto y los suelta en cuanto se limpia.
  ephemeralParams: [
    { name: 'project', boundTo: 'projects' },
    { name: 'client', boundTo: 'clients' },
  ],
  builtinTabs: [
    {
      id: 'no-client',
      name: 'Sin cliente',
      filters: { clients: [NO_CLIENT_KEY] },
    },
    {
      id: 'no-project',
      name: 'Sin proyecto',
      filters: { projects: [NO_PROJECT_KEY] },
    },
  ],
  defaults: {
    clients: [],
    projects: [],
    modalities: [],
    valueMin: '',
    valueMax: '',
    validToAfter: '',
    validToBefore: '',
    isActive: [],
  },
  matchers: {
    clients: matchClients,
    projects: matchProjects,
    modalities: matchIncludes('payment_modality', 'modalities'),
    value: matchNumberRange('monthly_value', 'valueMin', 'valueMax'),
    validTo: matchDateRange('valid_to', 'validToAfter', 'validToBefore'),
    isActive: matchBooleanIncludes('is_active', 'isActive'),
  },
  searchFields: [
    'client_name', 'client_display_name', 'project_name', 'domain_url', 'notes',
  ],
});

const clientFilterOptions = computed(() => {
  // Derived from the loaded rows (the dropdown is a flat checkbox list),
  // plus the sentinel for the records still pending assignment.
  const seen = new Map();
  store.hostings.forEach((row) => {
    if (row.client != null && !seen.has(row.client)) {
      seen.set(row.client, clientLabelOf(row));
    }
  });
  const options = [...seen.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
  return [{ value: NO_CLIENT_KEY, label: NO_CLIENT_LABEL }, ...options];
});

/**
 * Full catalog first (history.vue pattern): a project with zero linked rows
 * must still be selectable — that gap is exactly what the filter reveals.
 * Row-derived entries survive as a defensive union for projects the catalog
 * no longer lists. Numeric ids: `matchProjects` compares `record.project`.
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
  store.hostings.forEach((row) => {
    if (row.project != null && !seen.has(row.project)) {
      seen.set(row.project, row.project_name || `Proyecto #${row.project}`);
    }
  });
  const options = [...seen.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
  return [{ value: NO_PROJECT_KEY, label: 'Sin proyecto' }, ...options];
});

const filterFields = computed(() => [
  {
    kind: 'multi',
    key: 'clients',
    label: 'Cliente',
    options: clientFilterOptions.value,
  },
  {
    kind: 'multi',
    key: 'projects',
    label: 'Proyecto',
    options: projectFilterOptions.value,
  },
  {
    kind: 'multi',
    key: 'modalities',
    label: 'Modalidad',
    options: [
      { value: 'quarterly', label: 'Trimestral' },
      { value: 'semiannual', label: 'Semestral' },
      { value: 'nine_month', label: 'Cada 9 meses' },
    ],
  },
  { kind: 'range', label: 'Valor/mes', minKey: 'valueMin', maxKey: 'valueMax', type: 'money' },
  { kind: 'daterange', label: 'Vencimiento', minKey: 'validToAfter', maxKey: 'validToBefore' },
  {
    kind: 'segmented',
    key: 'isActive',
    label: 'Estado',
    options: [
      { value: '', label: 'Todos' },
      { value: 'true', label: 'Vigentes' },
      { value: 'false', label: 'Inactivos' },
    ],
  },
]);

// validTo range has no server-side equivalent (list filters valid_from)
// No `projects` key: the project is a relation with no server-side choice
// filter, so the Proyecto multi-select narrows the loaded rows client-side.
const EXPORT_MAPPING = {
  clients: 'client',
  valueMin: 'amount_min',
  valueMax: 'amount_max',
  modalities: 'payment_modality',
  isActive: 'is_active',
  search: 'q',
};

const exportParams = computed(() =>
  buildExportParams(currentFilters, EXPORT_MAPPING),
);

// -------------------------------------------------------------------
// Data + CRUD controller (modal, delete confirm, pagination)
// -------------------------------------------------------------------

const hostingsMeta = computed(() => store.metaFor('hostings'));

const filteredRecords = computed(() => applyFilters(store.hostings));

// Weight over the filtered ACTIVE monthly income: inactive hostings show 0%
// and stay out of the base, so the active ones read as a 100% composition.
const weightedRecords = computed(() =>
  addWeightPct(filteredRecords.value, (row) =>
    (row.is_active ? Number(row.monthly_value) || 0 : 0)),
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
  runMutation,
  sortKey,
  sortDir,
  toggleSort,
} = useAccountingCrudPage({
  entity: 'hostings',
  resetPageOn: currentFilters,
  store,
  filteredRecords: weightedRecords,
  saveTab,
  resetFilters,
  isFilterPanelOpen,
  labels: {
    entityName: 'hosting',
    created: 'Hosting creado',
    updated: 'Hosting actualizado',
    deleted: 'Hosting eliminado',
    saveErrorTitle: 'No se pudo guardar',
    deleteErrorTitle: 'No se pudo eliminar',
    deleteTitle: 'Eliminar hosting',
    deleteMessage: (record) =>
      `Esto eliminará el hosting de "${record.display_label || record.client_name}" de forma permanente. Esta acción no se puede deshacer.`,
  },
  // Refresh meta (active_count / monthly_income) after changes.
  onAfterMutation: () => loadRecords(),
  // Sorting "Valor/mes" sorts by weight: identical order for active rows
  // (the % is monotonic on the value), and inactive rows (0%) sink to the
  // end — the composition reading this column is for.
  // Cliente sorts by the label the cell actually shows: the linked client's
  // name, falling back to the legacy snapshot for the rows still unlinked.
  sortAccessors: { monthly_value: 'weight_pct', client_name: clientNameOf },
  sortDefaults: { monthly_value: 'desc', total_paid: 'desc' },
});

const columns = [
  {
    key: 'client_display_name', label: 'Cliente', size: 'name', sortable: true,
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'project_name', label: 'Proyecto', size: 'name', sortable: true, hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'domain_url', label: 'Dominio',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    // Grouped on a phone: checkbox, kebab, Cliente, Valor/mes and the Estado
    // select did not fit 412px, and the client name was squeezed to one
    // letter per line. It keeps its column from the portrait tablet up.
    key: 'monthly_value', label: 'Valor/mes', format: 'money', sortable: true,
    responsive: { compact: 'group', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'payment_modality_label', label: 'Modalidad',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'validity', label: 'Vigencia',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  // `link: true`: el conteo de ciclos ES lo que el detalle despliega, así que
  // ahí va el enlace al histórico.
  {
    key: 'cycles_count', label: 'Ciclos', align: 'center', link: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'total_paid', label: 'Total pagado', format: 'money', sortable: true,
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'is_active', label: 'Estado',
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
];

// Fed the FULL store list, not the filtered rows: the selection is meant to
// survive a filter change, so only "this hosting no longer exists" may drop an
// id from it.
const { selectedIds, clearSelection, dropIds } = useRowSelection(() => store.hostings);

const filteredIds = computed(() => filteredRecords.value.map((row) => row.id));

/** What identifies a hosting: in the bulk confirmation list and the row menu. */
const hostingLabel = (row) =>
  row.domain_url || row.display_label || `Hosting #${row.id}`;

async function applyClientToSelection({ ids, client, mode, plan }) {
  const result = await runMutation(
    () => store.bulkAssignHostingClient(ids, client),
    {
      successTitle: mode === 'unlink'
        ? 'Cliente desvinculado de los hostings'
        : 'Cliente asignado a los hostings',
      // The server skips rows already on the target, so the count it returns
      // is what actually changed — not what was selected.
      successDetail: (r) => describeAssignmentResult(
        plan, r.data?.updated ?? 0, { entity: HOSTING_ENTITY },
      ),
      errorTitle: mode === 'unlink'
        ? 'No se pudo desvincular el cliente'
        : 'No se pudo asignar el cliente',
    },
  );
  if (result.success) {
    clearSelection();
    return;
  }
  // Same reconciliation as incomes: the ids the server says are gone leave the
  // selection, and the reload puts the rest of the view back in agreement.
  if (result.missingIds?.length) {
    dropIds(result.missingIds);
    await loadRecords();
  }
}

async function applyProjectToSelection({ ids, project, mode, plan }) {
  const result = await runMutation(
    () => store.bulkAssignHostingProject(ids, project),
    {
      successTitle: mode === 'unlink'
        ? 'Proyecto quitado de los hostings'
        : 'Proyecto asignado a los hostings',
      successDetail: (r) => describeProjectAssignmentResult(
        plan, r.data?.updated ?? 0, { entity: HOSTING_ENTITY },
      ),
      errorTitle: mode === 'unlink'
        ? 'No se pudo quitar el proyecto'
        : 'No se pudo asignar el proyecto',
    },
  );
  if (result.success) {
    clearSelection();
    // Cross-module courtesy: the projects page reads per-project counts; if
    // its store already holds data, refresh it so a later visit agrees.
    if (projectsStore.records.length) projectsStore.fetchProjects();
    return;
  }
  // `records_not_found` and `client_mismatch` both name exact ids: drop
  // them, keep the rest of the selection, and rebuild the view.
  if (result.missingIds?.length) {
    dropIds(result.missingIds);
    await loadRecords();
  }
}

async function loadRecords() {
  await store.fetchRecords('hostings');
}

// -------------------------------------------------------------------
// Post-create assign offer (the Vástago gap)
// -------------------------------------------------------------------

const pendingAssignProject = ref(null);
const assignOfferOpen = ref(false);

function onProjectCreated(project) {
  const backlog = (project.unlinked_hostings_count ?? 0)
    + (project.unlinked_incomes_count ?? 0);
  pendingAssignProject.value = backlog > 0 ? project : null;
}

// The offer waits for the form to close: the preview it loads is
// server-fresh, so a record just saved by that form is already (correctly)
// absent from it — and the project outlives a cancelled form on purpose.
watch(isModalOpen, (open) => {
  if (!open && pendingAssignProject.value) {
    assignOfferOpen.value = true;
  }
});

function dismissAssignOffer() {
  assignOfferOpen.value = false;
  pendingAssignProject.value = null;
}

async function onUnlinkedAssigned() {
  dismissAssignOffer();
  await loadRecords();
}

// -------------------------------------------------------------------
// Inline edits: estado dropdown + double-click cells
// -------------------------------------------------------------------

const statusUpdatingId = ref(null);

async function changeStatus(row, isActive) {
  statusUpdatingId.value = row.id;
  const result = await store.updateRecord('hostings', row.id, { is_active: isActive });
  statusUpdatingId.value = null;
  if (result.success) {
    notify.success({ title: isActive ? 'Hosting activado' : 'Hosting desactivado' });
    loadRecords();
  } else {
    notify.error({ title: 'No se pudo cambiar el estado', detail: result.message });
  }
}

const inlineSavingKey = ref(null);

async function saveInline(row, field, value) {
  inlineSavingKey.value = `${row.id}:${field}`;
  const result = await store.updateRecord('hostings', row.id, { [field]: value });
  inlineSavingKey.value = null;
  if (result.success) {
    notify.success({ title: 'Hosting actualizado' });
    loadRecords();
  } else {
    notify.error({ title: 'No se pudo actualizar', detail: result.message });
  }
}

// -------------------------------------------------------------------
// Cycle history modal
// -------------------------------------------------------------------

// El historial de ciclos es el detalle de un hosting, así que el parámetro
// nombra al hosting (`?hosting=`) y no a un ciclo. Con dirección propia, el
// dominio de la fila puede publicarla en un enlace y la URL se puede compartir.
const {
  openRow: cyclesRecord,
  isOpen: cyclesModalOpen,
  toFor: hostingCyclesTo,
  open: openCyclesById,
  close: closeCyclesModal,
} = useDetailQueryParam('hosting', { rows: () => store.hostings });

function openCyclesModal(row) {
  openCyclesById(row.id);
}

function goToHostingEmails(row) {
  navigateTo(historySendsLink('hosting', row.id));
}

async function onCyclesChanged() {
  // Ya no hay que reponer la fila a mano: `cyclesRecord` es un computed sobre
  // el store, así que recargar la lista la vuelve a resolver sola.
  await loadRecords();
}

// -------------------------------------------------------------------
// Cuenta de cobro (collection account) action
// -------------------------------------------------------------------

const billingConfirmOpen = ref(false);
const billingRow = ref(null);
const billingId = ref(null);

const billingConfirmMessage = computed(() => {
  const row = billingRow.value;
  if (!row) return '';
  return (
    `Se emitirá la cuenta de cobro por ${formatMoney(row.payment_per_cycle, 'COP')} ` +
    `y se enviará con el PDF adjunto a ${row.billing_email}. ` +
    'Los avisos de vencimiento de este hosting se pausan hasta la próxima renovación.'
  );
});

function askSendBilling(row) {
  billingRow.value = row;
  billingConfirmOpen.value = true;
}

async function sendBilling() {
  const row = billingRow.value;
  billingRow.value = null;
  if (!row) return;
  billingId.value = row.id;
  const result = await store.sendHostingCollectionAccount(row.id);
  billingId.value = null;
  if (result.success) {
    const number = result.data?.document?.public_number || '';
    if (result.data?.email_sent) {
      notify.success({
        title: 'Cuenta de cobro enviada',
        detail: number ? `Documento ${number} enviado a ${row.billing_email}.` : '',
        action: { label: 'Ver en Cuentas de cobro', to: '/panel/accounting/collections' },
      });
    } else {
      notify.warning({
        title: 'Cuenta de cobro emitida, pero el correo falló',
        detail: 'Reenvíala desde el tab Cuentas de cobro.',
      });
    }
    loadRecords();
  } else {
    notify.error({ title: 'No se pudo enviar la cuenta de cobro', detail: result.message });
  }
}


/**
 * Entry point for "ver los hostings de este cliente" from /panel/clients.
 * Seeds the client multi-select so the deep link lands already filtered.
 * The id must be a Number: `matchClients` compares against `record.client`,
 * which the API serializes numerically. The landing tab here is 'all', so
 * nothing filters the incoming rows back out.
 */
function applyClientFromQuery() {
  const raw = consumeParam('client');
  if (!raw) return;
  const clientId = Number(raw);
  if (!Number.isFinite(clientId)) return;
  currentFilters.clients = [clientId];
  isFilterPanelOpen.value = true;
}

onMounted(() => {
  // ?project=<id> — deep link from the /panel/projects counts. Seeded before
  // the load; the `projects` matcher above already speaks this key.
  const projectParam = Number(consumeParam('project'));
  if (Number.isInteger(projectParam) && projectParam > 0) {
    currentFilters.projects = [projectParam];
  }
  applyClientFromQuery();
  // Project filter options come from the full catalog (history.vue
  // pattern); the store swallows failures, so an error just means a
  // smaller dropdown, never a blocked page.
  projectsStore.fetchProjects();
  return loadRecords();
});
usePanelRefresh(loadRecords);
</script>
