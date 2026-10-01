<template>
  <div :class="PAGE_MAX_WIDTH" data-testid="projects-page">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Proyectos</h1>
        <p class="text-sm text-text-subtle mt-1">
          El producto entregado a cada cliente: lo que hostings, ingresos y
          cuentas de cobro referencian.
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <BaseButton
          as="NuxtLink"
          to="/panel/projects/statuses"
          variant="secondary"
          size="md"
          data-testid="projects-manage-states"
        >
          Administrar estados
        </BaseButton>
        <BaseButton
          variant="primary"
          size="md"
          data-testid="projects-new-button"
          @click="openCreate"
        >
          <BaseActionIcon action="create" />
          <span>Nuevo proyecto</span>
        </BaseButton>
      </div>
    </div>

    <!-- Indicators: two compact summaries, business groups on larger screens. -->
    <section class="mb-6" aria-label="Indicadores de proyectos">
      <div
        v-if="isCompact"
        class="grid grid-cols-2 gap-3"
        data-testid="projects-indicators-compact"
      >
        <AccountingStatCard
          label="Estados"
          :value="String(store.meta.total ?? store.records.length)"
          :sub="stateSummarySupport"
          action="list"
          action-label="Ver proyectos por estado"
          help-label="Ayuda sobre el resumen de estados"
          help-position="bottom"
          help-test-id="project-states-summary-help"
          data-testid="panel-projects-stat-states-summary"
          @click="statesDrawerOpen = true"
        >
          <template #help>
            <p class="font-semibold">Estados del proyecto</p>
            <p>Distribuye el total según el ciclo administrable vigente.</p>
            <p>Abre el detalle para ver y filtrar incluso los estados con cero proyectos.</p>
          </template>
        </AccountingStatCard>
        <AccountingStatCard
          label="Pendientes"
          :value="String(pendingCategoryCount)"
          :sub="pendingSummarySupport"
          :tone="pendingCategoryCount > 0 ? 'warning' : 'success'"
          action="list"
          action-label="Ver pendientes operativos"
          help-label="Ayuda sobre los pendientes operativos"
          help-position="left"
          help-test-id="project-pending-summary-help"
          data-testid="panel-projects-stat-pending-summary"
          @click="pendingDrawerOpen = true"
        >
          <template #help>
            <p class="font-semibold">Pendientes operativos</p>
            <p>Cuenta categorías con trabajo pendiente, no suma entidades de tipos distintos.</p>
            <p>Abre el detalle para revisar proyectos, clientes y registros contables.</p>
          </template>
        </AccountingStatCard>
      </div>

      <div v-else class="space-y-5" data-testid="projects-indicators-expanded">
        <section v-if="nonZeroProjectStates.length" aria-labelledby="project-state-indicators-title">
          <h2
            id="project-state-indicators-title"
            class="mb-2 text-xs font-semibold uppercase tracking-wider text-text-subtle"
          >
            Ciclo del proyecto
          </h2>
          <div class="grid grid-cols-4 gap-3 panel-wide:grid-cols-5">
            <AccountingStatCard
              v-for="state in nonZeroProjectStates"
              :key="state.state_id"
              :label="state.name"
              :value="String(state.count)"
              :tone="statTone(state.color)"
              layout="compact-horizontal"
              action="filter"
              :action-label="`Filtrar proyectos en estado ${state.name}`"
              :help-label="`Ayuda sobre el estado ${state.name}`"
              help-position="left"
              :help-test-id="`project-stat-state-help-${state.state_id}`"
              :data-testid="`panel-projects-stat-state-${state.state_id}`"
              @click="applyProjectScope(`state:${state.state_id}`)"
            >
              <template #help>
                <p class="font-semibold">{{ state.name }}</p>
                <p>{{ stateDescription(state) }}</p>
                <p><strong>Implica:</strong> {{ stateImplications(state) }}</p>
              </template>
            </AccountingStatCard>
          </div>
        </section>

        <section v-if="nonZeroPendingIndicators.length" aria-labelledby="project-pending-indicators-title">
          <h2
            id="project-pending-indicators-title"
            class="mb-2 text-xs font-semibold uppercase tracking-wider text-text-subtle"
          >
            Pendientes operativos
          </h2>
          <div class="grid grid-cols-4 gap-3 panel-wide:grid-cols-5">
            <AccountingStatCard
              v-for="indicator in nonZeroPendingIndicators"
              :key="indicator.key"
              :label="indicator.label"
              :value="String(indicator.value)"
              :sub="indicator.support"
              tone="warning"
              layout="compact-horizontal"
              :action="indicator.action"
              :action-label="indicator.actionLabel"
              :help-label="`Ayuda sobre ${indicator.label}`"
              help-position="left"
              :help-test-id="`project-stat-${indicator.key}-help`"
              :data-testid="indicator.testId"
              @click="activatePendingIndicator(indicator.key)"
            >
              <template #help>
                <p class="font-semibold">{{ indicator.label }}</p>
                <p>{{ indicator.help }}</p>
              </template>
            </AccountingStatCard>
          </div>
        </section>
      </div>
    </section>

    <!-- Search + scope -->
    <div class="flex flex-col sm:flex-row sm:items-center gap-2 mb-5">
      <BaseInput
        v-model="searchInput"
        type="text"
        placeholder="Buscar por proyecto o cliente..."
        data-testid="projects-search-input"
        class="w-full sm:max-w-xs"
      />
      <BaseSelect
        v-model="scope"
        :options="scopeOptions"
        size="sm"
        aria-label="Estado de los proyectos"
        data-testid="projects-state-filter"
        class="w-full sm:max-w-xs"
      />
      <ProjectStateHelpBadge
        v-if="selectedScopeState"
        :state="selectedScopeState"
        position="bottom"
        test-id="project-filter-state-help"
      />
    </div>

    <!-- Error -->
    <AccountingErrorState
      v-if="store.error === 'fetch_failed'"
      title="No se pudieron cargar los proyectos"
      :retrying="store.isLoading"
      @retry="loadRecords"
    />

    <!-- Empty -->
    <BaseEmptyState
      v-else-if="!store.isLoading && filteredRecords.length === 0"
      :title="hasActiveFilters ? 'Sin resultados con esos filtros' : 'No hay proyectos aún'"
      :description="hasActiveFilters
        ? 'Ajusta la búsqueda o cambia de pestaña para ver más registros.'
        : 'Registra el primer proyecto de un cliente.'"
    >
      <template #actions>
        <BaseButton
          v-if="hasActiveFilters"
          variant="secondary"
          size="sm"
          @click="clearFilters"
        >
          Limpiar filtros
        </BaseButton>
        <BaseButton v-else variant="primary" size="sm" @click="openCreate">
          <BaseActionIcon action="create" />
          <span>Nuevo proyecto</span>
        </BaseButton>
      </template>
    </BaseEmptyState>

    <!-- Table -->
    <template v-else>
      <div v-if="isCompact" class="space-y-4">
        <div class="grid grid-cols-[minmax(0,1fr)_auto] gap-2 rounded-xl border border-border-muted bg-surface p-3">
          <BaseSelect
            :model-value="sortKey"
            :options="MOBILE_SORT_OPTIONS"
            size="sm"
            aria-label="Ordenar proyectos por"
            data-testid="projects-sort-mobile"
            @update:model-value="setMobileSortKey"
          />
          <BaseButton
            variant="secondary"
            size="md"
            :disabled="!sortKey"
            disabled-reason="Elige primero el criterio para ordenar los proyectos."
            :aria-label="sortDir === 'asc' ? 'Orden ascendente' : 'Orden descendente'"
            data-testid="projects-sort-direction"
            @click="toggleMobileSortDirection"
          >
          <BaseActionIcon :action="sortDir === 'asc' ? 'sort-ascending' : 'sort-descending'" />
          {{ sortDir === 'asc' ? 'A a Z' : 'Z a A' }}
          </BaseButton>
        </div>

        <div class="grid grid-cols-1 gap-4 panel-portrait:grid-cols-2" data-testid="projects-card-list">
          <ProjectCard
            v-for="row in pagedRecords"
            :key="row.id"
            :project="row"
            :is-superuser="isSuperuser"
            :highlighted="row.id === (lastMutatedId ?? queryHighlightId)"
            @assign="openAssign"
            @actions="projectActionTarget = $event"
            @change-state="openStateTransition"
          />
        </div>
      </div>

      <AccountingTable
        v-else
        :show-default-actions="false"
        row-actions-layout="menu-start"
        :loading="store.isLoading"
        :highlight-id="lastMutatedId ?? queryHighlightId"
        :columns="columns"
        :rows="pagedRecords"
        :highlight-query="searchInput"
        :sort-key="sortKey"
        :sort-dir="sortDir"
        @sort="toggleSort"
      >
        <template #cell-status_label="{ row }">
          <span class="inline-flex items-center gap-1.5">
            <BaseBadge :variant="stateBadgeVariant(row.current_state)">
              {{ row.status_label }}
            </BaseBadge>
            <ProjectStateHelpBadge
              v-if="row.current_state"
              :state="row.current_state"
              position="bottom"
              :test-id="`project-table-state-help-${row.id}`"
            />
          </span>
        </template>
        <template #cell-client_name="{ row }">
          <span class="inline-flex flex-col items-start">
            <HighlightText :text="row.client_name" :query="searchInput" />
            <span v-if="row.client_company" class="text-xs text-text-subtle">
              <HighlightText :text="row.client_company" :query="searchInput" />
            </span>
            <!-- Terminal states keep their history but receive no new rows. -->
            <BaseButton
              v-if="unlinkedTotal(row) > 0 && !isTerminal(row)"
              variant="ghost"
              size="sm"
              class="!px-1.5 !py-0.5 text-xs text-warning-strong"
              :title="`${unlinkedTotal(row)} registros de este cliente sin proyecto — asignar`"
              :data-testid="`project-assign-unlinked-${row.id}`"
              @click.stop="openAssign(row)"
            >
              {{ unlinkedTotal(row) }} sin proyecto
            </BaseButton>
          </span>
        </template>
        <template #cell-created_at="{ row }">
          <span class="text-text-muted text-xs whitespace-nowrap">
            {{ formatDate(row.created_at) }}
          </span>
        </template>
        <!-- Counts jump into the accounting tabs pre-filtered by this project.
             Superuser-gated links: the target pages are superuser-only. -->
        <template #cell-hostings_count="{ row }">
          <NuxtLink
            v-if="isSuperuser && row.hostings_count > 0"
            :to="{ path: '/panel/accounting/hostings', query: { project: row.id } }"
            class="text-text-brand hover:underline tabular-nums"
            :data-testid="`project-hostings-link-${row.id}`"
            @click.stop
          >
            {{ row.hostings_count }}
          </NuxtLink>
          <span v-else class="tabular-nums text-text-muted">{{ row.hostings_count }}</span>
        </template>
        <template #cell-incomes_count="{ row }">
          <NuxtLink
            v-if="isSuperuser && row.incomes_count > 0"
            :to="{
              path: '/panel/accounting/incomes',
              query: { accounting_incomeTab: 'all', project: row.id },
            }"
            class="text-text-brand hover:underline tabular-nums"
            :data-testid="`project-incomes-link-${row.id}`"
            @click.stop
          >
            {{ row.incomes_count }}
          </NuxtLink>
          <span v-else class="tabular-nums text-text-muted">{{ row.incomes_count }}</span>
        </template>
        <template #row-actions="{ row }">
          <BaseActionButton
            action="more"
            variant="ghost"
            size="sm"
            :label="$t('projectAccess.projectActions.label', { name: row.name })"
            :data-testid="`project-actions-${row.id}`"
            @click.stop="projectActionTarget = row"
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

    <BaseDrawer
      v-model="statesDrawerOpen"
      placement="bottom"
      title="Estados de los proyectos"
      test-id="project-states-indicator-drawer"
    >
      <div class="space-y-2 p-4 panel-portrait:p-6">
        <!-- design-tokens: allow-raw-button — selectable detail row. -->
        <button
          v-for="state in projectStates"
          :key="state.state_id"
          type="button"
          class="flex min-h-11 w-full items-start gap-3 rounded-xl border border-border-muted bg-surface-raised p-3 text-left transition-colors hover:border-border-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          :aria-label="`Filtrar proyectos en estado ${state.name}`"
          :data-testid="`project-state-detail-${state.state_id}`"
          @click="applyProjectScope(`state:${state.state_id}`)"
        >
          <span class="min-w-0 flex-1">
            <span class="flex items-center justify-between gap-3">
              <span class="font-medium text-text-default">{{ state.name }}</span>
              <span class="tabular-nums text-text-muted">{{ state.count ?? 0 }}</span>
            </span>
            <span class="mt-1 block text-xs text-text-subtle">{{ stateDescription(state) }}</span>
            <span class="mt-1 block text-xs text-text-muted">
              <strong>Implica:</strong> {{ stateImplications(state) }}
            </span>
          </span>
          <BaseActionIcon action="filter" class="mt-1 text-text-subtle" />
        </button>
      </div>
    </BaseDrawer>

    <BaseDrawer
      v-model="pendingDrawerOpen"
      placement="bottom"
      title="Pendientes operativos"
      test-id="project-pending-indicator-drawer"
    >
      <div class="space-y-3 p-4 panel-portrait:p-6">
        <!-- design-tokens: allow-raw-button — selectable detail row. -->
        <button
          type="button"
          class="flex min-h-11 w-full items-center gap-3 rounded-xl border border-border-muted bg-surface-raised p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          data-testid="project-pending-review-action"
          @click="applyProjectScope('review')"
        >
          <span class="min-w-0 flex-1">
            <span class="flex items-center justify-between gap-3 font-medium text-text-default">
              <span>Por revisar</span>
              <span class="tabular-nums">{{ store.meta.review_required ?? 0 }}</span>
            </span>
            <span class="mt-1 block text-xs text-text-subtle">Proyectos heredados cuya clasificación aún debe confirmarse.</span>
          </span>
          <BaseActionIcon action="filter" class="text-text-subtle" />
        </button>

        <!-- design-tokens: allow-raw-button — selectable detail row. -->
        <button
          type="button"
          class="flex min-h-11 w-full items-center gap-3 rounded-xl border border-border-muted bg-surface-raised p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          data-testid="project-pending-clients-action"
          @click="openOrphansFromIndicators"
        >
          <span class="min-w-0 flex-1">
            <span class="flex items-center justify-between gap-3 font-medium text-text-default">
              <span>Clientes sin proyecto</span>
              <span class="tabular-nums">{{ store.meta.clients_without_projects ?? 0 }}</span>
            </span>
            <span class="mt-1 block text-xs text-text-subtle">Clientes activos que todavía no tienen ninguna ficha de proyecto.</span>
          </span>
          <BaseActionIcon action="list" class="text-text-subtle" />
        </button>

        <section class="rounded-xl border border-border-muted bg-surface-raised p-3" data-testid="project-pending-records-detail">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="font-medium text-text-default">Registros sin proyecto</h3>
              <p class="mt-1 text-xs text-text-subtle">Hostings e ingresos que ya tienen cliente, pero aún no proyecto.</p>
            </div>
            <span class="tabular-nums text-text-default">{{ store.meta.records_without_project ?? 0 }}</span>
          </div>
          <div v-if="isSuperuser" class="mt-3 grid grid-cols-1 gap-2 panel-portrait:grid-cols-2">
            <BaseButton
              as="NuxtLink"
              :to="{ path: '/panel/accounting/hostings', query: { accounting_hostingTab: 'no-project' } }"
              variant="secondary"
              size="md"
              class="min-h-11 justify-center"
              data-testid="project-unlinked-hostings-link"
            >
              Ver hostings
              <BaseActionIcon action="forward" />
            </BaseButton>
            <BaseButton
              as="NuxtLink"
              :to="{ path: '/panel/accounting/incomes', query: { accounting_incomeTab: 'no-project' } }"
              variant="secondary"
              size="md"
              class="min-h-11 justify-center"
              data-testid="project-unlinked-incomes-link"
            >
              Ver ingresos
              <BaseActionIcon action="forward" />
            </BaseButton>
          </div>
          <p v-else class="mt-3 text-xs text-text-muted">
            El detalle contable está disponible para usuarios con acceso de superusuario.
          </p>
        </section>
      </div>
    </BaseDrawer>

    <ProjectActionsModal
      :project="projectActionTarget"
      @close="projectActionTarget = null"
      @action="handleProjectAction"
    />
    <ProjectDeleteModal
      :project="deleteProjectTarget"
      @close="deleteProjectTarget = null"
      @deleted="onProjectDeleted"
      @change-state="deleteProjectTarget = null; openStateTransition($event)"
    />

    <!-- Create/edit modal -->
    <ProjectFormModal
      :open="isModalOpen"
      :record="editingRecord"
      :saving="store.isUpdating"
      :seed-client="seedClient"
      :existing-projects="store.records"
      :field-errors="projectFormErrors"
      @close="closeModal"
      @submit="onFormSubmit"
      @change-client="openChangeClient"
      @clear-error="clearProjectFormError"
    />

    <!-- Guided cascade: the only path that moves a project between clients -->
    <ProjectChangeClientModal
      :open="changeClientOpen"
      :project="changeClientProject"
      @close="closeChangeClient"
      @changed="onClientChanged"
    />

    <ProjectStateTransitionModal
      :open="stateTransitionOpen"
      :project="stateProject"
      @close="closeStateTransition"
      @changed="onStateChanged"
    />

    <ProjectStateHistoryModal
      v-model="stateHistoryOpen"
      :project="historyProject"
    />

    <ProjectBrandModal v-if="brandProject" :key="brandProject.id" :project="brandProject" @close="brandProject = null" />

    <ProjectAccessModal
      :open="accessDetailOpen"
      :project="accessProject"
      @close="closeAccessDetail"
    />

    <!-- Assign the client's unlinked records to a project (PA-51) -->
    <ProjectAssignUnlinkedModal
      :open="assignOpen"
      :project="assignProject"
      @close="closeAssign"
      @assigned="closeAssign"
    />

    <!-- Clients without a project -->
    <BaseModal
      :model-value="orphansOpen"
      kind="detail"
      title-id="projects-orphans-title"
      @close="orphansOpen = false"
    >
      <div class="px-6 pt-6 pb-2">
        <h3 id="projects-orphans-title" class="text-lg font-bold text-text-default">
          Clientes sin proyecto
        </h3>
        <p class="text-sm text-text-subtle mt-1">
          Cada uno debería tener registrado el producto que se le entrega.
        </p>
      </div>
      <div class="px-6 py-4" data-testid="panel-projects-orphans">
        <p v-if="store.isLoadingClientsWithoutProjects" class="text-sm text-text-subtle">
          Cargando clientes...
        </p>
        <p
          v-else-if="store.clientsWithoutProjects.length === 0"
          class="text-sm text-text-subtle"
          data-testid="panel-projects-orphans-empty"
        >
          Todos los clientes visibles tienen al menos un proyecto.
        </p>
        <ul v-else class="divide-y divide-border-muted">
          <li
            v-for="client in store.clientsWithoutProjects"
            :key="client.id"
            class="flex items-center justify-between gap-3 py-2.5"
          >
            <div class="min-w-0">
              <p class="max-w-full truncate text-sm text-text-default" :title="client.name || client.email">{{ client.name || client.email }}</p>
              <p v-if="client.company" class="max-w-full truncate text-xs text-text-subtle" :title="client.company">
                {{ client.company }}
              </p>
            </div>
            <BaseButton
              variant="secondary"
              size="sm"
              :data-testid="`projects-orphan-create-${client.id}`"
              @click="openCreateFromOrphan(client)"
            >
              Crear proyecto
            </BaseButton>
          </li>
        </ul>
      </div>
    </BaseModal>

  </div>
</template>

<script setup>
import { PAGE_MAX_WIDTH } from '~/utils/tableLayout';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import AccountingTable from '~/components/accounting/AccountingTable.vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import AccountingStatCard from '~/components/accounting/AccountingStatCard.vue';
import HighlightText from '~/components/ui/HighlightText.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import ProjectAssignUnlinkedModal from '~/components/panel/projects/ProjectAssignUnlinkedModal.vue';
import ProjectBrandModal from '~/components/panel/projects/ProjectBrandModal.vue';
import ProjectAccessModal from '~/components/panel/projects/ProjectAccessModal.vue';
import ProjectCard from '~/components/panel/projects/ProjectCard.vue';
import ProjectChangeClientModal from '~/components/panel/projects/ProjectChangeClientModal.vue';
import ProjectFormModal from '~/components/panel/projects/ProjectFormModal.vue';
import ProjectActionsModal from '~/components/panel/projects/ProjectActionsModal.vue';
import ProjectDeleteModal from '~/components/panel/projects/ProjectDeleteModal.vue';
import { usePanelToPlatformBridge } from '~/composables/usePanelToPlatformBridge';
import ProjectStateHelpBadge from '~/components/panel/projects/ProjectStateHelpBadge.vue';
import ProjectStateHistoryModal from '~/components/panel/projects/ProjectStateHistoryModal.vue';
import ProjectStateTransitionModal from '~/components/panel/projects/ProjectStateTransitionModal.vue';
import { useAccountingCrudPage } from '~/composables/useAccountingCrudPage';
import { useIsMobile } from '~/composables/useIsMobile';
import { PANEL_BREAKPOINTS } from '~/config/responsive';
import { usePanelProjectsStore } from '~/stores/panel_projects';
import { useProposalStore } from '~/stores/proposals';
import { normalizeName } from '~/utils/clientMatch';
import { stateBadgeVariant } from '~/utils/documentState';
import { formatDate } from '~/utils/formatDate';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const store = usePanelProjectsStore();
const notify = usePanelNotify();
const { isMobile: isCompact } = useIsMobile(PANEL_BREAKPOINTS.landscape - 1);
// The count links point at superuser-only accounting pages; hide them from
// plain admins (same flag the sidebar uses).
const proposalStore = useProposalStore();
const isSuperuser = computed(() => proposalStore.isSuperuser);

const projectStates = computed(() => store.meta.by_state || []);
const nonZeroProjectStates = computed(() => (
  projectStates.value.filter((state) => Number(state.count) > 0)
));
const pendingIndicators = computed(() => [
  {
    key: 'review',
    label: 'Por revisar',
    value: Number(store.meta.review_required ?? 0),
    support: 'Clasificación pendiente',
    action: 'filter',
    actionLabel: 'Filtrar proyectos por revisar',
    help: 'Proyectos heredados cuya clasificación todavía debe confirmarse.',
    testId: 'panel-projects-stat-review',
  },
  {
    key: 'orphans',
    label: 'Clientes sin proyecto',
    value: Number(store.meta.clients_without_projects ?? 0),
    support: 'Por registrar de forma deliberada',
    action: 'list',
    actionLabel: 'Ver clientes sin proyecto',
    help: 'Clientes activos que no tienen ninguna ficha Project registrada.',
    testId: 'panel-projects-stat-orphans',
  },
  {
    key: 'unlinked',
    label: 'Registros sin proyecto',
    value: Number(store.meta.records_without_project ?? 0),
    support: 'Hostings e ingresos por asignar',
    action: 'forward',
    actionLabel: 'Ver registros sin proyecto',
    help: 'Suma hostings e ingresos con cliente vinculado y proyecto todavía vacío.',
    testId: 'panel-projects-stat-unlinked',
  },
]);
const nonZeroPendingIndicators = computed(() => (
  pendingIndicators.value.filter((indicator) => indicator.value > 0)
));
const pendingCategoryCount = computed(() => nonZeroPendingIndicators.value.length);
const stateSummarySupport = computed(() => {
  const count = nonZeroProjectStates.value.length;
  return count === 1 ? '1 estado con proyectos' : `${count} estados con proyectos`;
});
const pendingSummarySupport = computed(() => {
  const count = pendingCategoryCount.value;
  if (count === 0) return 'Sin pendientes operativos';
  return count === 1 ? '1 frente por atender' : `${count} frentes por atender`;
});

const statesDrawerOpen = ref(false);
const pendingDrawerOpen = ref(false);

function stateDescription(state) {
  return state?.description?.trim() || 'Estado administrable del ciclo del proyecto.';
}

function stateImplications(state) {
  return state?.operational_effect_help?.trim()
    || 'Consulta las consecuencias antes de confirmar un cambio de estado.';
}

async function applyProjectScope(nextScope) {
  scope.value = nextScope;
  statesDrawerOpen.value = false;
  pendingDrawerOpen.value = false;
  await nextTick();
  if (typeof document !== 'undefined') {
    document.querySelector('[data-testid="projects-state-filter"]')?.focus();
  }
}

function activatePendingIndicator(key) {
  if (key === 'review') {
    applyProjectScope('review');
    return;
  }
  if (key === 'orphans') {
    openOrphansPanel();
    return;
  }
  pendingDrawerOpen.value = true;
}

function openOrphansFromIndicators() {
  pendingDrawerOpen.value = false;
  openOrphansPanel();
}

// ── State + search. The options come from the administrable catalog, so a
//    newly created state immediately becomes a real filter. ──

const scopeOptions = computed(() => [
  { value: 'all', label: 'Todos los estados' },
  ...(store.meta.by_state || []).map((state) => ({
    value: `state:${state.state_id}`,
    label: `${state.name} (${state.count})`,
  })),
  ...(store.meta.review_required
    ? [{ value: 'review', label: `Por revisar (${store.meta.review_required})` }]
    : []),
]);

const MOBILE_SORT_OPTIONS = [
  { value: '', label: 'Orden original' },
  { value: 'name', label: 'Nombre del proyecto' },
  { value: 'client_name', label: 'Cliente' },
  { value: 'status_label', label: 'Estado' },
  { value: 'created_at', label: 'Fecha de creación' },
  { value: 'hostings_count', label: 'Cantidad de hostings' },
  { value: 'incomes_count', label: 'Cantidad de ingresos' },
];

const scope = ref('all');
const searchInput = ref('');
const selectedScopeState = computed(() => {
  if (!scope.value.startsWith('state:')) return null;
  const stateId = Number(scope.value.slice(6));
  const state = (store.meta.by_state || []).find(
    (item) => item.state_id === stateId,
  );
  return state ? { ...state, id: state.state_id } : null;
});

const hasActiveFilters = computed(
  () => Boolean(searchInput.value.trim()) || scope.value !== 'all',
);

function clearFilters() {
  searchInput.value = '';
  scope.value = 'all';
}

/** Rows flattened for the table: the client object becomes sortable columns. */
const displayRecords = computed(() => store.records.map((record) => ({
  ...record,
  client_name: record.client?.name || '',
  client_company: record.client?.company || '',
})));

const filteredRecords = computed(() => {
  const term = normalizeName(searchInput.value);
  return displayRecords.value.filter((record) => {
    if (scope.value === 'review' && !record.state_review_required) return false;
    if (scope.value.startsWith('state:')) {
      const stateId = Number(scope.value.slice(6));
      if (record.current_state?.id !== stateId) return false;
    }
    if (!term) return true;
    return [record.name, record.client_name, record.client_company]
      .some((field) => normalizeName(field).includes(term));
  });
});

// ── Table controller: modal, confirm, mutation flow, sorting, pagination ──

const {
  isModalOpen,
  editingRecord,
  openCreateModal,
  openEditModal,
  closeModal,
  handleSubmit,
  lastMutatedId,
  sortKey,
  sortDir,
  toggleSort,
  currentPage,
  totalPages,
  totalItems,
  rangeFrom,
  rangeTo,
  pagedRecords,
  prevPage,
  nextPage,
  goToPage,
} = useAccountingCrudPage({
  entity: 'projects',
  store,
  filteredRecords,
  labels: {
    created: 'Proyecto creado',
    updated: 'Proyecto actualizado',
    saveErrorTitle: (editing) => (editing
      ? 'No se pudo actualizar el proyecto'
      : 'No se pudo crear el proyecto'),
  },
  suppressFieldErrorNotification: true,
});

const columns = computed(() => [
  { key: 'name', label: 'Proyecto', sortable: true, size: 'name' },
  { key: 'client_name', label: 'Cliente', sortable: true, size: 'name' },
  {
    key: 'status_label',
    label: 'Estado',
    format: 'badge',
    sortable: true,
    size: 'badge',
    badgeTones: Object.fromEntries((store.meta.by_state || []).map((state) => [
      state.name,
      stateBadgeVariant({ color: state.color }),
    ])),
  },
  { key: 'created_at', label: 'Creado', sortable: true, size: 'date' },
  { key: 'hostings_count', label: 'Hostings', sortable: true, size: 'text', align: 'right' },
  { key: 'incomes_count', label: 'Ingresos', sortable: true, size: 'text', align: 'right' },
]);

function setMobileSortKey(key) {
  sortKey.value = key;
  sortDir.value = 'asc';
}

function toggleMobileSortDirection() {
  if (!sortKey.value) return;
  sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
}

function statTone(color) {
  return {
    emerald: 'success',
    yellow: 'warning',
    orange: 'warning',
    red: 'danger',
    blue: 'brand',
    purple: 'brand',
  }[color] || 'default';
}

function isTerminal(project) {
  return ['completed', 'decommissioned'].includes(
    project.current_state?.operational_effect,
  );
}

const projectActionTarget = ref(null);
const deleteProjectTarget = ref(null);
const { goToPlatform } = usePanelToPlatformBridge();
const { t } = useI18n();

function handleProjectAction(action, row) {
  projectActionTarget.value = null;
  const handlers = {
    ideas: () => navigateTo(projectIdeasLocalePath(`/panel/projects/${row.id}/ideas`)),
    brand: () => { brandProject.value = row; },
    detail: () => openAccessDetail(row),
    space: () => goToPlatform(`/platform/projects/${row.id}`),
    edit: () => openEditModal(row),
    communications: () => navigateTo({ path: '/panel/communications', query: { project: String(row.id) } }),
    state: () => openStateTransition(row),
    history: () => openStateHistory(row),
    delete: () => { deleteProjectTarget.value = row; },
  };
  handlers[action]?.();
}

function onProjectDeleted(result) {
  deleteProjectTarget.value = null;
  notify.success({ title: t('projectAccess.deletion.success') });
  if (result.refreshFailed) {
    notify.warning({ title: t('projectAccess.deletion.refreshError') });
  }
}

// ── Secure access detail ──

const accessDetailOpen = ref(false);
const accessProject = ref(null);
const brandProject = ref(null);

function openAccessDetail(project) {
  accessProject.value = project;
  accessDetailOpen.value = true;
}

function closeAccessDetail() {
  accessDetailOpen.value = false;
  accessProject.value = null;
}

// ── Lifecycle transition + immutable history ──

const stateTransitionOpen = ref(false);
const stateProject = ref(null);
const stateHistoryOpen = ref(false);
const historyProject = ref(null);

function openStateTransition(project) {
  stateProject.value = project;
  stateTransitionOpen.value = true;
}

function closeStateTransition() {
  stateTransitionOpen.value = false;
  stateProject.value = null;
}

async function onStateChanged(project) {
  await store.refreshAfterExternalMutation();
  notify.success({
    title: 'Estado actualizado',
    detail: `${project.name} ahora está ${project.status_label}.`,
  });
}

function openStateHistory(project) {
  historyProject.value = project;
  stateHistoryOpen.value = true;
}

watch(stateHistoryOpen, (open) => {
  if (!open) historyProject.value = null;
});

// ── Assign the client's unlinked records (PA-51) ──

const assignOpen = ref(false);
const assignProject = ref(null);

function unlinkedTotal(row) {
  return (row.unlinked_hostings_count ?? 0)
    + (row.unlinked_incomes_count ?? 0)
    + (row.unlinked_documents_count ?? 0);
}

function openAssign(row) {
  assignProject.value = row;
  assignOpen.value = true;
}

function closeAssign() {
  assignOpen.value = false;
  assignProject.value = null;
}

// ── Change-client cascade (opened from the edit form's ghost button) ──

const changeClientOpen = ref(false);
const changeClientProject = ref(null);

function openChangeClient() {
  if (!editingRecord.value) return;
  changeClientProject.value = editingRecord.value;
  changeClientOpen.value = true;
}

function closeChangeClient() {
  changeClientOpen.value = false;
  changeClientProject.value = null;
}

function onClientChanged() {
  // The store already refetched projects and the loaded accounting lists;
  // closing both modals is all that is left — the table under them is fresh.
  closeChangeClient();
  closeModal();
}

/**
 * Create/update passthrough that, after a CREATE, offers the assign modal
 * when the new project's client has records without a project. Offering,
 * never doing: the modal is itself the confirmation step.
 */
async function onFormSubmit(payload) {
  const wasEditing = Boolean(editingRecord.value);
  const result = await handleSubmit(payload);
  projectFormErrors.value = result?.success ? {} : (result?.fieldErrors || {});
  if (!wasEditing && result?.success && unlinkedTotal(result.data) > 0) {
    openAssign(result.data);
  }
}

// ── Clients without a project (the deliberate-gap indicator) ──

const orphansOpen = ref(false);
const seedClient = ref(null);
const projectFormErrors = ref({});

function clearProjectFormError(field) {
  if (!projectFormErrors.value[field]) return;
  const nextErrors = { ...projectFormErrors.value };
  delete nextErrors[field];
  projectFormErrors.value = nextErrors;
}

function openOrphansPanel() {
  orphansOpen.value = true;
  store.fetchClientsWithoutProjects();
}

function openCreate() {
  seedClient.value = null;
  openCreateModal();
}

function openCreateFromOrphan(client) {
  orphansOpen.value = false;
  seedClient.value = client;
  openCreateModal();
}

// The seed belongs to one modal opening; a later plain "Nuevo proyecto"
// must not inherit it.
watch(isModalOpen, (open) => {
  projectFormErrors.value = {};
  if (!open) seedClient.value = null;
});

async function loadRecords() {
  await store.fetchProjects();
}

// ── Deep link from the platform space (PA-50 return path) ──

const route = useRoute();
const projectIdeasLocalePath = useLocalePath();
const queryHighlightId = Number.parseInt(route.query.highlight, 10) || null;

/**
 * Make the linked row visible no matter the scope or page: widen to "Todos"
 * and seed the search with the project's name. Degrades harmlessly when the
 * id is gone (full listing) — the point is never landing on an empty view.
 */
function applyHighlightDeepLink() {
  if (!queryHighlightId) return;
  const row = store.records.find((record) => record.id === queryHighlightId);
  if (!row) return;
  scope.value = 'all';
  searchInput.value = row.name;
}

onMounted(async () => {
  await loadRecords();
  applyHighlightDeepLink();
});
</script>
