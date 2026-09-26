<template>
  <BasePageShell>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <div class="flex items-center gap-1">
          <h1 class="text-2xl font-light text-text-default">Ingresos</h1>
          <ReceivableLegend />
        </div>
        <p class="text-sm text-text-subtle mt-1">
          Ingresos esperados y líquidos del negocio, con su reparto entre socios.
        </p>
      </div>
      <div class="flex w-full flex-wrap items-center gap-2 panel-portrait:w-auto">
        <BaseButton
          variant="secondary"
          size="md"
          class="flex-1 panel-portrait:flex-none"
          data-testid="incomes-client-totals-button"
          @click="openTotalsModal"
        >
          Totales por cliente
        </BaseButton>
        <BaseButton
          variant="primary"
          size="md"
          class="flex-1 panel-portrait:flex-none"
          data-testid="incomes-new-button"
          @click="openCreateModal"
        >
          <BaseActionIcon action="create" />
          <span>Nuevo ingreso</span>
        </BaseButton>
      </div>
    </div>

    <AccountingSubnav active="incomes" />

    <!-- KPI cards: two compact summaries, four business cards from landscape. -->
    <section class="mb-2 sm:mb-6" aria-label="Indicadores de ingresos">
      <div
        v-if="isCompact"
        class="grid grid-cols-2 gap-3"
        data-testid="income-indicators-compact"
      >
        <AccountingStatCard
          label="Resultado anual"
          :value="money(incomesMeta.liquid_total)"
          :sub="incomesMeta.received_pct != null ? `${incomesMeta.received_pct}% recibido` : ''"
          tone="success"
          action="list"
          action-label="Ver detalle del resultado anual"
          help-label="Ayuda sobre el resultado anual"
          help-position="bottom"
          help-test-id="income-result-summary-help"
          data-testid="income-stat-result-summary"
          @click="annualIndicatorsOpen = true"
        >
          <template #help>
            <p class="font-semibold">Resultado anual</p>
            <p>Agrupa los totales esperado, líquido y perdido del año en curso.</p>
            <p>Abre el detalle para aplicar cada filtro sobre el listado.</p>
          </template>
        </AccountingStatCard>
        <AccountingStatCard
          label="Detalle operativo"
          :value="money(incomesMeta.current_month_liquid)"
          :sub="incomeOperationalSupport"
          :tone="incomePendingTotal > 0 ? 'warning' : 'brand'"
          action="list"
          action-label="Ver detalle operativo de ingresos"
          help-label="Ayuda sobre el detalle operativo"
          help-position="left"
          help-test-id="income-operational-summary-help"
          data-testid="income-stat-operational-summary"
          @click="operationalIndicatorsOpen = true"
        >
          <template #help>
            <p class="font-semibold">Detalle operativo</p>
            <p>La cifra principal es lo recibido este mes.</p>
            <p>El detalle reúne el mayor ingreso y los registros que aún necesitan cliente o proyecto.</p>
          </template>
        </AccountingStatCard>
      </div>

      <div
        v-else
        class="grid grid-cols-4 gap-3"
        data-testid="income-indicators-expanded"
      >
        <AccountingStatCard
          label="Total esperado (año)"
          :value="money(incomesMeta.expected_total)"
          sub="Año en curso"
          action="filter"
          action-label="Filtrar ingresos esperados del año"
          help-label="Ayuda sobre el total esperado anual"
          help-test-id="income-expected-help"
          data-testid="income-stat-expected"
          @click="activateIncomeIndicator('expected')"
        >
          <template #help>
            <p class="font-semibold">Total esperado</p>
            <p>Ingresos previstos dentro del año en curso, incluidos los que ya recibieron abonos.</p>
          </template>
        </AccountingStatCard>
        <AccountingStatCard
          label="Total líquido (año)"
          :value="money(incomesMeta.liquid_total)"
          :sub="incomesMeta.received_pct != null ? `${incomesMeta.received_pct}% recibido` : ''"
          tone="success"
          action="filter"
          action-label="Filtrar ingresos líquidos del año"
          help-label="Ayuda sobre el total líquido anual"
          help-test-id="income-liquid-help"
          data-testid="income-stat-liquid"
          @click="activateIncomeIndicator('liquid')"
        >
          <template #help>
            <p class="font-semibold">Total líquido</p>
            <p>Dinero efectivamente recibido durante el año en curso.</p>
          </template>
        </AccountingStatCard>
        <AccountingStatCard
          label="Perdido (año)"
          :value="money(incomesMeta.lost_total)"
          sub="Año en curso"
          :tone="Number(incomesMeta.lost_total) > 0 ? 'danger' : 'default'"
          action="filter"
          action-label="Filtrar ingresos perdidos del año"
          help-label="Ayuda sobre los ingresos perdidos"
          help-test-id="income-lost-help"
          data-testid="income-stat-lost"
          @click="activateIncomeIndicator('lost')"
        >
          <template #help>
            <p class="font-semibold">Ingresos perdidos</p>
            <p>Valores dados de baja durante el año y conservados para trazabilidad.</p>
          </template>
        </AccountingStatCard>
        <AccountingStatCard
          label="Detalle operativo"
          :value="money(incomesMeta.current_month_liquid)"
          :sub="incomeOperationalSupport"
          :tone="incomePendingTotal > 0 ? 'warning' : 'brand'"
          action="list"
          action-label="Ver detalle operativo de ingresos"
          help-label="Ayuda sobre el detalle operativo"
          help-test-id="income-operational-help"
          data-testid="income-stat-operational"
          @click="operationalIndicatorsOpen = true"
        >
          <template #help>
            <p class="font-semibold">Detalle operativo</p>
            <p>Resume lo recibido este mes y abre los indicadores de contexto y vinculación.</p>
          </template>
        </AccountingStatCard>
      </div>
    </section>

    <!-- Quick + saved filter tabs -->
    <ProposalFilterTabs
      :tabs="displayTabs"
      :counts="tabCounts"
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
        placeholder="Buscar por concepto, notas o cliente..."
        data-testid="incomes-search-input"
        class="w-full sm:max-w-xs"
      />
      <UiFilterToggleButton
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
      <AccountingExportButton section="income" :params="exportParams" />
      <BaseSegmented
        v-model="viewMode"
        :options="viewModeOptions"
        size="sm"
        class="w-full panel-portrait:ml-auto panel-portrait:w-auto"
        data-testid="incomes-view-mode"
      />
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
        class="text-xs px-2.5 py-1 rounded-full bg-surface-raised text-text-muted font-medium tabular-nums"
        data-testid="incomes-total-expected"
      >
        Total esperado: {{ formatMoney(totalExpected) }}
      </span>
      <span
        class="text-xs px-2.5 py-1 rounded-full bg-success-soft text-success-strong font-medium tabular-nums"
        data-testid="incomes-total-liquid"
      >
        Total líquido: {{ formatMoney(totalLiquid) }}
      </span>
      <span
        v-if="totalLost > 0"
        class="text-xs px-2.5 py-1 rounded-full bg-danger-soft text-danger-strong font-medium tabular-nums"
        data-testid="incomes-total-lost"
      >
        Total perdido: {{ formatMoney(totalLost) }}
      </span>
    </div>

    <!-- Error -->
    <AccountingErrorState
      v-if="store.error === 'fetch_failed'"
      title="No se pudieron cargar los ingresos"
      :retrying="store.isLoading"
      @retry="loadRecords"
    />

    <!-- Empty -->
    <BaseEmptyState
      v-else-if="!store.isLoading && filteredRecords.length === 0"
      :title="hasActiveFilters ? 'Sin resultados con esos filtros' : 'No hay ingresos aún'"
      :description="hasActiveFilters
        ? 'Ajusta o limpia los filtros para ver más registros.'
        : 'Registra el primer ingreso esperado o líquido del negocio.'"
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
          <span>Nuevo ingreso</span>
        </BaseButton>
      </template>
    </BaseEmptyState>

    <!-- Table: grouped by client (landing mode set in Configuración) or classic -->
    <template v-else>
      <IncomeGroupedTable
        v-if="isGrouped"
        v-model:selected="selectedIds"
        selectable
        :loading="store.isLoading"
        :highlight-id="lastMutatedId"
        :columns="groupedColumns"
        :groups="clientGroups"
        :highlight-query="currentFilters.search"
        :collapsed-ids="collapsedGroupIds"
        :sort-key="sortKey"
        :sort-dir="sortDir"
        :show-default-actions="false"
        row-actions-layout="menu-start"
        @edit="openEditModal"
        @delete="confirmDeleteRecord"
        @sort="toggleSort"
        @toggle-group="toggleGroup"
      >
        <template #row-actions="{ row }">
          <IncomeRowActionsButton
            :row="row"
            :busy="duplicatingId === row.id"
            @open="openActions"
          />
        </template>
        <!-- Sin `stretch`: la celda de la grilla trunca (overflow hidden) y
             recortaría el área estirada. El enlace cubre el texto. -->
        <template #cell-concept="{ row }">
          <BaseRowLink
            :to="incomeDetailTo(row.id)"
            :data-testid="`income-open-${row.id}`"
            class="hover:text-text-brand transition-colors"
          >
            <HighlightText :text="row.concept" :query="currentFilters.search" />
          </BaseRowLink>
        </template>
        <template #cell-kind_label="{ row }">
          <BaseBadge
            :variant="incomeKindBadgeVariant(row.kind)"
            :data-testid="`income-kind-${row.id}`"
          >
            {{ row.kind_label }}
          </BaseBadge>
        </template>
        <template #cell-payment_status="{ row }">
          <IncomePaymentStateCell :row="row" />
        </template>
        <template #cell-collection_confidence="{ row }">
          <ReceivableStateControl
            :row="row"
            :busy="store.receivableUpdatingIds.includes(row.id)"
            @change="updateIncomeReceivable(row, $event)"
          />
        </template>
        <template #cell-project_name="{ row }">
          <span v-if="row.project_name" class="inline-flex items-center gap-1">
            <HighlightText
              :text="row.project_name"
              :query="currentFilters.search"
            />
            <ProjectSpaceLink
              :project-id="row.project"
              :data-testid="`income-project-space-${row.id}`"
            />
          </span>
          <span v-else class="text-text-subtle">—</span>
        </template>
      </IncomeGroupedTable>

      <!-- Column sort and pagination stay classic-only affordances; the
           grouped view always renders the whole filtered set, and its own
           checkboxes feed the same selection (and the same bulk bar). -->
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
          :row-tone="incomeRowTone"
          :show-default-actions="false"
          row-actions-layout="menu-start"
          @edit="openEditModal"
          @delete="confirmDeleteRecord"
          @sort="toggleSort"
        >
          <template #row-actions="{ row }">
            <IncomeRowActionsButton
              :row="row"
              :busy="duplicatingId === row.id"
              @open="openActions"
            />
          </template>
          <!-- El concepto es la dirección del detalle: un enlace de verdad, no
               sólo el ojo del kebab. -->
          <template #cell-concept="{ row }">
            <BaseRowLink
              :to="incomeDetailTo(row.id)"
              stretch
              :data-testid="`income-open-${row.id}`"
              class="block truncate hover:text-text-brand transition-colors"
              :title="row.concept"
            >
              <HighlightText :text="row.concept" :query="currentFilters.search" />
            </BaseRowLink>
          </template>
          <template #cell-kind_label="{ row }">
            <BaseBadge
              :variant="incomeKindBadgeVariant(row.kind)"
              :data-testid="`income-kind-${row.id}`"
            >
              {{ row.kind_label }}
            </BaseBadge>
          </template>
          <!-- An empty client cell hides the completion debt; the pill makes
               it actionable, same as the hostings table. Grouped view needs
               none: its "Sin cliente" bucket already carries the flag. -->
          <template #cell-client_name="{ row }">
            <HighlightText
              v-if="row.client_name"
              :text="row.client_name"
              :query="currentFilters.search"
            />
            <BaseBadge
              v-else
              variant="warning"
              size="sm"
              class="font-semibold uppercase tracking-wider"
              title="Sin cliente vinculado — los totales por cliente no lo cuentan"
              :data-testid="`income-unlinked-${row.id}`"
            >
              sin vincular
            </BaseBadge>
          </template>
          <!-- Collection state gets its own column: sharing the Tipo cell with
               the kind badge wrapped the pills and doubled the row height. -->
          <template #cell-payment_status="{ row }">
            <IncomePaymentStateCell :row="row" />
          </template>
          <template #cell-collection_confidence="{ row }">
            <ReceivableStateControl
              :row="row"
              :busy="store.receivableUpdatingIds.includes(row.id)"
              @change="updateIncomeReceivable(row, $event)"
            />
          </template>
          <template #cell-project_name="{ row }">
            <span v-if="row.project_name" class="inline-flex items-center gap-1">
              <HighlightText
                :text="row.project_name"
                :query="currentFilters.search"
              />
              <ProjectSpaceLink
                :project-id="row.project"
                :data-testid="`income-project-space-${row.id}`"
              />
            </span>
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
    </template>

    <BaseDrawer
      v-model="annualIndicatorsOpen"
      placement="bottom"
      title="Resultado anual"
      test-id="income-annual-indicators-drawer"
    >
      <div class="space-y-2 p-4 panel-portrait:p-6">
        <!-- design-tokens: allow-raw-button — selectable detail row. -->
        <button
          v-for="indicator in annualIndicatorDetails"
          :key="indicator.key"
          type="button"
          class="flex min-h-11 w-full items-center gap-3 rounded-xl border border-border-muted bg-surface-raised p-3 text-left transition-colors hover:border-border-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          :data-testid="`income-indicator-detail-${indicator.key}`"
          @click="activateIncomeIndicator(indicator.key)"
        >
          <span class="min-w-0 flex-1">
            <span class="flex items-center justify-between gap-3">
              <span class="font-medium text-text-default">{{ indicator.label }}</span>
              <span class="tabular-nums" :class="indicator.toneClass">{{ indicator.value }}</span>
            </span>
            <span class="mt-1 block text-xs text-text-subtle">{{ indicator.help }}</span>
          </span>
          <BaseActionIcon action="filter" class="text-text-subtle" />
        </button>
      </div>
    </BaseDrawer>

    <BaseDrawer
      v-model="operationalIndicatorsOpen"
      placement="bottom"
      title="Detalle operativo"
      test-id="income-operational-indicators-drawer"
    >
      <div class="space-y-2 p-4 panel-portrait:p-6">
        <!-- design-tokens: allow-raw-button — selectable detail row. -->
        <button
          v-for="indicator in operationalIndicatorDetails"
          :key="indicator.key"
          type="button"
          class="flex min-h-11 w-full items-center gap-3 rounded-xl border border-border-muted bg-surface-raised p-3 text-left transition-colors hover:border-border-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="indicator.disabled"
          :title="indicator.disabled ? indicator.help : undefined"
          :data-testid="`income-indicator-detail-${indicator.key}`"
          @click="activateIncomeIndicator(indicator.key)"
        >
          <span class="min-w-0 flex-1">
            <span class="flex items-center justify-between gap-3">
              <span class="font-medium text-text-default">{{ indicator.label }}</span>
              <span class="tabular-nums" :class="indicator.toneClass">{{ indicator.value }}</span>
            </span>
            <span class="mt-1 block text-xs text-text-subtle">{{ indicator.help }}</span>
          </span>
          <BaseActionIcon :action="indicator.action" class="text-text-subtle" />
        </button>
      </div>
    </BaseDrawer>

    <!--
      Bulk client assignment: the completion path for rows without client.
      Below the table and sticky, so it stays reachable after selecting at the
      bottom of the grouped view; outside the error/empty/table chain, because
      a selection whose rows the filter just hid still needs its actions.
    -->
    <BulkAssignBar
      v-model:selected="selectedIds"
      :rows="store.incomes"
      :filtered-ids="filteredIds"
      :entity="INCOME_ENTITY"
      testid-prefix="incomes"
      :record-label="incomeLabel"
      :busy="store.isUpdating"
      project-enabled
      settle-enabled
      @submit="applyClientToSelection"
      @submit-project="applyProjectToSelection"
      @submit-settle="openBulkSettle"
    />

    <!-- Row actions: one list for both view modes, opened from the kebab.
         First modal on purpose: its close must patch before the dialog it
         opens, or the two trade focus traps and the page loses its scroll
         lock. -->
    <IncomeActionsModal
      :open="actionsOpen"
      :record="actionsRow"
      @close="actionsOpen = false"
      @detail="openIncomeDetail"
      @notes="noteRow = $event"
      @edit="openEditModal"
      @duplicate="duplicateIncome"
      @liquidate="openLiquidateModal"
      @generate-collection="openCollectionModal"
      @view-collection="goToCollectionAccount"
      @view-emails="goToIncomeEmails"
      @toggle-mute="toggleMute"
      @write-off="confirmWriteOff"
      @delete="confirmDeleteRecord"
    />

    <!-- Create/edit modal (also the duplicate form, seeded and creating) -->
    <IncomeFormModal
      :open="isModalOpen"
      :record="editingRecord"
      :seed="seedRecord"
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

    <!-- The note is searched but has no column: the menu opens it here. -->
    <AccountingNoteModal
      :open="noteRow !== null"
      :subtitle="noteRow?.concept || ''"
      :notes="noteRow?.notes ?? ''"
      :highlight-query="currentFilters.search"
      @close="noteRow = null"
    />

    <!-- Detalle del ingreso, reutilizando el modal de cuentas de cobro -->
    <IncomeDetailModal
      :open="detailOpen"
      :income-id="detailIncomeId"
      @close="closeIncomeDetail"
      @duplicate="duplicateIncome"
    />

    <!-- Liquidate modal: settles an expected income into a linked liquid one -->
    <IncomeLiquidateModal
      :open="isLiquidateModalOpen"
      :record="liquidatingRecord"
      :saving="store.isUpdating"
      @close="closeLiquidateModal"
      @submit="handleLiquidateSubmit"
    />

    <!-- Abono: one payment distributed across the selected expected incomes -->
    <IncomeBulkSettleModal
      :open="bulkSettleOpen"
      :records="bulkSettleRecords"
      :excluded-count="bulkSettleExcluded"
      :saving="store.isUpdating"
      @close="closeBulkSettle"
      @submit="handleBulkSettleSubmit"
    />

    <IncomeMuteModal
      :open="muteModalOpen"
      :record="mutingRecord"
      :saving="store.isUpdating"
      @close="muteModalOpen = false"
      @submit="submitMute"
    />

    <!-- Totales por cliente sobre las filas filtradas -->
    <IncomeClientTotalsModal
      :open="totalsModalOpen"
      :rows="filteredRecords"
      :hosting-rows="store.hostings"
      @close="totalsModalOpen = false"
    />

    <!-- Generar cuenta de cobro desde el ingreso (preseleccionado) -->
    <CollectionAccountFormModal
      :open="collectionModalOpen"
      :income="collectionIncome"
      @close="collectionModalOpen = false"
      @created="onCollectionCreated"
    />

    <!-- Confirm modal for delete / write-off -->
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
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import IncomeActionsModal from '~/components/accounting/IncomeActionsModal.vue';
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';
import IncomeRowActionsButton from '~/components/accounting/IncomeRowActionsButton.vue';
import IncomeDetailModal from '~/components/accounting/IncomeDetailModal.vue';
import IncomeMuteModal from '~/components/accounting/IncomeMuteModal.vue';
import IncomePaymentStateCell from '~/components/accounting/IncomePaymentStateCell.vue';
import ReceivableLegend from '~/components/accounting/ReceivableLegend.vue';
import ReceivableStateControl from '~/components/accounting/ReceivableStateControl.vue';
import HighlightText from '~/components/ui/HighlightText.vue';
import CollectionAccountFormModal from '~/components/accounting/CollectionAccountFormModal.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import AccountingSubnav from '~/components/accounting/AccountingSubnav.vue';
import AccountingTable from '~/components/accounting/AccountingTable.vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import AccountingStatCard from '~/components/accounting/AccountingStatCard.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import AccountingFilterPanel from '~/components/accounting/AccountingFilterPanel.vue';
import AccountingExportButton from '~/components/accounting/AccountingExportButton.vue';
import IncomeFormModal from '~/components/accounting/IncomeFormModal.vue';
import IncomeClientTotalsModal from '~/components/accounting/IncomeClientTotalsModal.vue';
import IncomeGroupedTable from '~/components/accounting/IncomeGroupedTable.vue';
import BulkAssignBar from '~/components/accounting/BulkAssignBar.vue';
import IncomeBulkSettleModal from '~/components/accounting/IncomeBulkSettleModal.vue';
import IncomeLiquidateModal from '~/components/accounting/IncomeLiquidateModal.vue';
import ProjectAssignUnlinkedModal from '~/components/panel/projects/ProjectAssignUnlinkedModal.vue';
import ProjectSpaceLink from '~/components/panel/projects/ProjectSpaceLink.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import BaseBadge from '~/components/base/BaseBadge.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useIsMobile } from '~/composables/useIsMobile';
import { useIncomeViewMode } from '~/composables/useIncomeViewMode';
import { useAccountingCrudPage } from '~/composables/useAccountingCrudPage';
import { useRowSelection } from '~/composables/useRowSelection';
import { useDetailQueryParam } from '~/composables/useDetailQueryParam';
import {
  useAccountingFilters,
  matchDateRange,
  matchNumberRange,
  matchIncludes,
  matchBooleanIncludes,
  matchAnyToken,
} from '~/composables/useAccountingFilters';
import { useAccountingStore } from '~/stores/accounting';
import { usePanelProjectsStore } from '~/stores/panel_projects';
import { buildExportParams } from '~/utils/accountingExportParams';
import { describeAssignmentResult } from '~/utils/clientAssignment';
import { describeBulkSettleResult } from '~/utils/settleAllocation';
import { describeProjectAssignmentResult } from '~/utils/projectAssignment';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';
import { historySendsLink } from '~/utils/historyDeepLink';
import { PANEL_BREAKPOINTS } from '~/config/responsive';
import {
  clientLabelOf,
  groupByClient,
  withClientWeights,
} from '~/utils/incomeClients';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const store = useAccountingStore();
const notify = usePanelNotify();
const projectsStore = usePanelProjectsStore();
const { isMobile: isCompact } = useIsMobile(PANEL_BREAKPOINTS.landscape - 1);

/** Noun the bulk client bar uses in its confirmation and result copy. */
const INCOME_ENTITY = { singular: 'ingreso', plural: 'ingresos' };

const incomesMeta = computed(() => store.metaFor('incomes'));

const annualIndicatorsOpen = ref(false);
const operationalIndicatorsOpen = ref(false);
const incomePendingTotal = computed(() => (
  Number(incomesMeta.value.without_client_count ?? 0)
  + Number(incomesMeta.value.without_project_count ?? 0)
));
const incomeOperationalSupport = computed(() => (
  incomePendingTotal.value === 0
    ? 'Sin registros por completar'
    : `${incomePendingTotal.value} por completar`
));

const annualIndicatorDetails = computed(() => [
  {
    key: 'expected',
    label: 'Total esperado (año)',
    value: money(incomesMeta.value.expected_total),
    toneClass: 'text-text-default',
    help: 'Ingresos previstos dentro del año en curso.',
  },
  {
    key: 'liquid',
    label: 'Total líquido (año)',
    value: money(incomesMeta.value.liquid_total),
    toneClass: 'text-success-strong',
    help: incomesMeta.value.received_pct != null
      ? `${incomesMeta.value.received_pct}% de lo esperado ya fue recibido.`
      : 'Dinero efectivamente recibido durante el año en curso.',
  },
  {
    key: 'lost',
    label: 'Perdido (año)',
    value: money(incomesMeta.value.lost_total),
    toneClass: Number(incomesMeta.value.lost_total) > 0
      ? 'text-danger-strong'
      : 'text-text-default',
    help: 'Valores dados de baja durante el año y conservados para trazabilidad.',
  },
]);

const operationalIndicatorDetails = computed(() => [
  {
    key: 'current-month',
    label: 'Mes actual (líquido)',
    value: money(incomesMeta.value.current_month_liquid),
    toneClass: 'text-text-default',
    help: 'Dinero líquido recibido durante el mes en curso.',
    action: 'filter',
    disabled: false,
  },
  {
    key: 'top-income',
    label: 'Mayor ingreso del año',
    value: incomesMeta.value.top_income ? money(incomesMeta.value.top_income.amount) : '—',
    toneClass: 'text-text-brand',
    help: incomesMeta.value.top_income?.concept || 'No hay un ingreso líquido para destacar.',
    action: 'search',
    disabled: !incomesMeta.value.top_income,
  },
  {
    key: 'no-client',
    label: 'Sin cliente',
    value: String(incomesMeta.value.without_client_count ?? 0),
    toneClass: Number(incomesMeta.value.without_client_count) > 0
      ? 'text-warning-strong'
      : 'text-text-default',
    help: 'Registros pendientes de vincular con un cliente.',
    action: 'filter',
    disabled: false,
  },
  {
    key: 'no-project',
    label: 'Sin proyecto',
    value: String(incomesMeta.value.without_project_count ?? 0),
    toneClass: Number(incomesMeta.value.without_project_count) > 0
      ? 'text-warning-strong'
      : 'text-text-default',
    help: 'Registros con cliente que todavía necesitan un proyecto.',
    action: 'filter',
    disabled: false,
  },
]);

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

// -------------------------------------------------------------------
// Filters
// -------------------------------------------------------------------

// Sentinels shared with the backend filters: 'none' means "not set".
const NO_CLIENT_KEY = 'none';
const NO_CLIENT_LABEL = 'Sin cliente';
const NO_ORIGIN_KEY = 'none';

const matchClients = (record, value) => {
  if (!Array.isArray(value) || value.length === 0) return true;
  // Compared as strings on purpose: `clients` holds numeric ids in memory but
  // arrives as text from the URL and from a saved tab's JSON. A number/string
  // mismatch does not throw — it just returns nothing, which reads as "no hay
  // datos" instead of "el filtro está roto".
  const selected = new Set(value.map(String));
  if (record.client == null) return selected.has(NO_CLIENT_KEY);
  return selected.has(String(record.client));
};
matchClients.keys = ['clients'];

const NO_PROJECT_KEY = 'none';
const NO_PROJECT_LABEL = 'Sin proyecto';

const matchProjects = (record, value) => {
  if (!Array.isArray(value) || value.length === 0) return true;
  const selected = new Set(value.map(String));
  if (record.project == null) return selected.has(NO_PROJECT_KEY);
  return selected.has(String(record.project));
};
matchProjects.keys = ['projects'];

const matchOrigin = (record, value) => {
  if (!Array.isArray(value) || value.length === 0) return true;
  if (!record.origin) return value.includes(NO_ORIGIN_KEY);
  return value.includes(record.origin);
};
matchOrigin.keys = ['origin'];

/**
 * `partner` is not a column: each token reads a different field, and two
 * tokens can hold at once on a record split between both socios. Marking
 * Gustavo + Carlos therefore has to be a union, which is what matchAnyToken
 * gives; the old if/elif could only ever answer for the first value.
 */
const PARTNER_PREDICATES = {
  gustavo: (record) => Number(record.gustavo_amount) > 0,
  carlos: (record) => Number(record.carlos_amount) > 0,
  projectapp: (record) =>
    record.destination === 'pocket' || Number(record.company_amount) > 0,
};

const matchPartner = matchAnyToken('partner', PARTNER_PREDICATES);

const {
  currentFilters,
  searchInput,
  displayTabs,
  activeTabId: filterTabId,
  isFilterPanelOpen,
  hasActiveFilters,
  activeFilterCount,
  isTabLimitReached,
  countTabs,
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
  viewName: 'accounting_income',
  // `project` siembra un filtro y acompaña a la vista mientras siga puesto;
  // `focus` sólo destaca una fila una vez y sale de la URL al montar.
  ephemeralParams: [{ name: 'project', boundTo: 'projects' }, 'focus'],
  // Fixed presets: unlike the seeded saved tabs, editing a filter here never
  // rewrites the tab, which is what the landing tab needs.
  builtinTabs: [
    {
      // "Sin pagos" alone hid every expected record that had received an abono,
      // even though a partially paid record is exactly what is still por cobrar
      // — the tab that was supposed to answer "what do they owe me" was the one
      // making the answer disappear. The id stays: it lives in the URL.
      id: 'expected-pending',
      name: 'Esperados por cobrar',
      filters: { kind: ['expected'], paymentStatus: ['pending', 'partial'] },
    },
    {
      id: 'hosting-expected',
      name: 'Hosting esperados',
      filters: {
        kind: ['expected'],
        paymentStatus: ['pending', 'partial'],
        search: 'hosting',
      },
    },
    { id: 'lost', name: 'Perdidos', filters: { kind: ['lost'] } },
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
  // The day-to-day question is what is still uncollected, not the full ledger.
  defaultTabId: 'expected-pending',
  defaults: {
    periodAfter: '',
    periodBefore: '',
    amountMin: '',
    amountMax: '',
    kind: [],
    paymentStatus: [],
    partner: [],
    ledger: [],
    clients: [],
    projects: [],
    origin: [],
    muted: [],
  },
  matchers: {
    period: matchDateRange('period_date', 'periodAfter', 'periodBefore'),
    amount: matchNumberRange('total_amount', 'amountMin', 'amountMax'),
    kind: matchIncludes('kind', 'kind'),
    // Liquid and lost rows carry `payment_status: null`, so any active
    // value here already narrows the list down to expected records —
    // deliberately no `nullAs`, which would let them back in.
    paymentStatus: matchIncludes('payment_status', 'paymentStatus'),
    partner: matchPartner,
    ledger: matchIncludes('ledger', 'ledger'),
    clients: matchClients,
    projects: matchProjects,
    origin: matchOrigin,
    muted: matchBooleanIncludes('reminders_muted', 'muted'),
  },
  // client_name mirrors the server-side q filter, which also reaches the
  // linked client's name — see the income entity's search_fields.
  searchFields: ['concept', 'notes', 'client_name', 'project_name'],
  // A multi-value cut is worth sharing ("todo lo que le falta por cobrar a
  // este cliente"), and it only survives a paste if it is in the URL.
  syncFiltersToUrl: true,
});

function toIsoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

const indicatorToday = new Date();
const indicatorYear = indicatorToday.getFullYear();
const currentYearFilters = Object.freeze({
  periodAfter: `${indicatorYear}-01-01`,
  periodBefore: `${indicatorYear}-12-31`,
});
const currentMonthFilters = Object.freeze({
  periodAfter: toIsoDate(new Date(indicatorYear, indicatorToday.getMonth(), 1)),
  periodBefore: toIsoDate(new Date(indicatorYear, indicatorToday.getMonth() + 1, 0)),
});

async function focusIncomeList() {
  await nextTick();
  if (typeof document === 'undefined') return;
  const input = document.querySelector('[data-testid="incomes-search-input"]');
  input?.scrollIntoView?.({ block: 'center' });
  input?.focus?.();
}

async function applyIncomeIndicatorFilters(filters) {
  resetFilters();
  Object.assign(currentFilters, filters);
  annualIndicatorsOpen.value = false;
  operationalIndicatorsOpen.value = false;
  await focusIncomeList();
}

async function activateIncomeIndicator(key) {
  if (key === 'no-client' || key === 'no-project') {
    selectFilterTab(key);
    annualIndicatorsOpen.value = false;
    operationalIndicatorsOpen.value = false;
    await focusIncomeList();
    return;
  }

  const filtersByIndicator = {
    expected: { ...currentYearFilters, kind: ['expected'] },
    liquid: { ...currentYearFilters, kind: ['liquid'] },
    lost: { ...currentYearFilters, kind: ['lost'] },
    'current-month': { ...currentMonthFilters, kind: ['liquid'] },
    'top-income': {
      ...currentYearFilters,
      kind: ['liquid'],
      search: incomesMeta.value.top_income?.concept || '',
    },
  };
  if (!filtersByIndicator[key]) return;
  await applyIncomeIndicatorFilters(filtersByIndicator[key]);
}

const clientFilterOptions = computed(() => {
  // Derived from the loaded rows, not the full client catalog: the dropdown
  // is a flat checkbox list, so bounding it by what is actually on screen
  // keeps it usable however many clients exist.
  const seen = new Map();
  store.incomes.forEach((row) => {
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
  store.incomes.forEach((row) => {
    if (row.project != null && !seen.has(row.project)) {
      seen.set(row.project, row.project_name || `Proyecto #${row.project}`);
    }
  });
  const options = [...seen.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
  return [{ value: NO_PROJECT_KEY, label: NO_PROJECT_LABEL }, ...options];
});

const filterFields = computed(() => [
  { kind: 'daterange', label: 'Mes', minKey: 'periodAfter', maxKey: 'periodBefore' },
  { kind: 'range', label: 'Total', minKey: 'amountMin', maxKey: 'amountMax', type: 'money' },
  {
    kind: 'segmented',
    key: 'kind',
    label: 'Tipo',
    options: [
      { value: '', label: 'Todos' },
      { value: 'expected', label: 'Esperado' },
      { value: 'liquid', label: 'Líquido' },
      { value: 'lost', label: 'Pérdidas' },
    ],
  },
  {
    kind: 'segmented',
    key: 'paymentStatus',
    label: 'Cobro',
    options: [
      { value: '', label: 'Todos' },
      { value: 'pending', label: 'Sin pagos' },
      { value: 'partial', label: 'Parcial' },
      { value: 'paid', label: 'Pagado' },
    ],
  },
  {
    kind: 'segmented',
    key: 'muted',
    label: 'Avisos',
    options: [
      { value: '', label: 'Todos' },
      { value: 'true', label: 'Silenciados' },
      { value: 'false', label: 'Con aviso' },
    ],
  },
  {
    kind: 'segmented',
    key: 'partner',
    label: 'Socio',
    options: [
      { value: '', label: 'Todos' },
      { value: 'gustavo', label: 'Gustavo' },
      { value: 'carlos', label: 'Carlos' },
      { value: 'projectapp', label: 'ProjectApp' },
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
    key: 'origin',
    label: 'Origen',
    options: [
      { value: 'development', label: 'Desarrollo' },
      { value: 'hosting', label: 'Hosting' },
      { value: 'diagnostic', label: 'Diagnóstico' },
      { value: 'other', label: 'Otro' },
      { value: NO_ORIGIN_KEY, label: 'Sin clasificar' },
    ],
  },
]);

const EXPORT_MAPPING = {
  periodAfter: 'date_from',
  periodBefore: 'date_to',
  amountMin: 'amount_min',
  amountMax: 'amount_max',
  kind: 'kind',
  paymentStatus: 'payment_status',
  partner: 'partner',
  ledger: 'ledger',
  clients: 'client',
  origin: 'origin',
  search: 'q',
};

const exportParams = computed(() =>
  buildExportParams(currentFilters, EXPORT_MAPPING),
);

// -------------------------------------------------------------------
// Data + CRUD controller (modal, delete confirm, pagination)
// -------------------------------------------------------------------

const filteredRecords = computed(() => applyFilters(store.incomes));

const INCOME_SORT_BASELINE = { key: 'period_label', dir: 'desc' };
const INCOME_SORT_STORAGE_KEY = 'projectapp-accounting-incomes-sort';
const INCOME_SORT_KEYS = [
  'concept',
  'client_name',
  'project_name',
  'period_label',
  'total_amount',
];

/**
 * Each tab badges its own cut of the whole ledger, not of the current one: the
 * number answers "how many would I see there", so it ignores the live filters.
 * `displayTabs` rather than the default (saved tabs only) because the landing
 * tab is a builtin — badging every tab except the one you are standing on
 * would be the odd omission.
 */
const tabCounts = computed(() => countTabs(store.incomes, displayTabs.value));

const {
  isModalOpen,
  editingRecord,
  seedRecord,
  openCreateModal,
  lastMutatedId,
  openEditModal,
  openSeededModal,
  closeModal,
  handleSubmit,
  confirmDeleteRecord,
  confirmState,
  handleConfirmed,
  handleCancelled,
  currentPage,
  sortedRecords,
  pageSize: PAGE_SIZE,
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
  requestConfirm,
  runMutation,
} = useAccountingCrudPage({
  entity: 'incomes',
  // Narrowing the working set sends the reader back to page 1; deleting or
  // editing a row must leave them where they were.
  resetPageOn: currentFilters,
  // A liquidation creates a CHILD row, so the parent expected row's
  // payment state is computed server-side from data the response doesn't
  // carry. Without a refetch its badge and tint stay stale. A settlement can
  // also book deductions, so the cached expenses list is dropped too.
  onAfterMutation: () => {
    store.expenses = [];
    // A settlement into the pocket books a movement: drop the cached ledger
    // so /panel/accounting/pocket refetches (the mirror of what that page
    // does to store.incomes after its own mutations).
    store.pocketMovements = [];
    return store.fetchRecords('incomes');
  },
  // The month column shows the localized label but sorts by the ISO date.
  sortAccessors: { period_label: 'period_date' },
  sortDefaults: {
    period_label: 'desc',
    total_amount: 'desc',
    gustavo_amount: 'desc',
    carlos_amount: 'desc',
  },
  baselineSort: INCOME_SORT_BASELINE,
  sortStorageKey: INCOME_SORT_STORAGE_KEY,
  sortAllowedKeys: INCOME_SORT_KEYS,
  store,
  filteredRecords,
  saveTab,
  resetFilters,
  isFilterPanelOpen,
  labels: {
    entityName: 'ingreso',
    created: 'Ingreso creado',
    duplicated: 'Ingreso duplicado',
    updated: 'Ingreso actualizado',
    deleted: 'Ingreso eliminado',
    saveErrorTitle: 'No se pudo guardar',
    deleteErrorTitle: 'No se pudo eliminar',
    deleteTitle: 'Eliminar ingreso',
    deleteMessage: (record) =>
      `Esto eliminará el ingreso "${record.concept}" de forma permanente. Esta acción no se puede deshacer.`,
  },
});

const totalExpected = computed(() =>
  filteredRecords.value
    .filter((r) => r.kind === 'expected')
    .reduce((sum, r) => sum + (Number(r.total_amount) || 0), 0),
);

const totalLiquid = computed(() =>
  filteredRecords.value
    .filter((r) => r.kind === 'liquid')
    .reduce((sum, r) => sum + (Number(r.total_amount) || 0), 0),
);

const totalLost = computed(() =>
  filteredRecords.value
    .filter((r) => r.kind === 'lost')
    .reduce((sum, r) => sum + (Number(r.total_amount) || 0), 0),
);

function incomeKindBadgeVariant(kind) {
  return { liquid: 'success', lost: 'danger' }[kind] || 'neutral';
}

// A soft fill would vanish: `incomeRowTone` already paints the whole row in
// that same tint. The chip sits on the plain surface with a colored outline so
// it reads on the tinted row and on the untinted one alike.
const PAYMENT_BADGE_CLASSES = {
  paid: 'bg-surface text-success-strong ring-1 ring-inset ring-success-strong/30',
  partial: 'bg-surface text-warning-strong ring-1 ring-inset ring-warning-strong/30',
};

/** Green once collected, amber while partially collected. */
const incomeRowTone = (row) => {
  if (row.kind !== 'expected') return null;
  if (row.payment_status === 'paid') return 'success';
  if (row.payment_status === 'partial') return 'warning';
  return null;
};

// -------------------------------------------------------------------
// Row actions: liquidate an expected income / write it off
// -------------------------------------------------------------------

const isLiquidateModalOpen = ref(false);
const liquidatingRecord = ref(null);

function openLiquidateModal(record) {
  liquidatingRecord.value = record;
  isLiquidateModalOpen.value = true;
}

function closeLiquidateModal() {
  isLiquidateModalOpen.value = false;
  liquidatingRecord.value = null;
}

async function handleLiquidateSubmit(payload) {
  const incomeId = liquidatingRecord.value?.id;
  const result = await runMutation(
    () => store.settleIncome(incomeId, payload),
    {
      successTitle: 'Ingreso liquidado',
      errorTitle: 'No se pudo liquidar',
      // Flash the expected row: it is the one whose state just changed.
      flashId: incomeId,
    },
  );
  if (result.success) closeLiquidateModal();
}

function confirmWriteOff(record) {
  requestConfirm({
    title: 'Marcar como perdido',
    message:
      `"${record.concept}" (${formatMoney(Number(record.total_amount))}) se `
      + 'contará como pérdida: sale del total esperado y deja de aparecer '
      + 'en la lista salvo que filtres por Pérdidas. No afecta la utilidad.',
    variant: 'danger',
    confirmText: 'Marcar como perdido',
    cancelText: 'Cancelar',
    onConfirm: () => runMutation(
      () => store.updateRecord('incomes', record.id, {
        kind: 'lost',
        destination: 'partners',
      }),
      {
        successTitle: 'Ingreso marcado como perdido',
        errorTitle: 'No se pudo marcar como perdido',
      },
    ),
  });
}

const muteModalOpen = ref(false);
const mutingRecord = ref(null);

function openMuteModal(record) {
  mutingRecord.value = record;
  muteModalOpen.value = true;
}

function submitMute(payload) {
  const record = mutingRecord.value;
  if (!record) return;
  const detail = payload.until
    ? `Los avisos de "${record.concept}" se reanudan el ${formatDate(payload.until)}.`
    : `No se enviarán avisos de "${record.concept}" hasta que los reactives.`;
  runMutation(
    () => store.muteIncomeReminders(record.id, payload),
    {
      successTitle: 'Avisos silenciados',
      successDetail: detail,
      errorTitle: 'No se pudieron silenciar los avisos',
      flashId: record.id,
    },
  ).then((result) => {
    if (result?.success) {
      muteModalOpen.value = false;
      mutingRecord.value = null;
    }
  });
}

// No confirmation: reactivating is non-destructive and instantly reversible.
function unmuteIncome(record) {
  runMutation(
    () => store.muteIncomeReminders(record.id, { muted: false }),
    {
      successTitle: 'Avisos reactivados',
      successDetail: `"${record.concept}" vuelve al correo diario.`,
      errorTitle: 'No se pudieron reactivar los avisos',
      flashId: record.id,
    },
  );
}

// Concepto gets the widest floor; Concepto, Total, Tipo and Cobro survive
// every width and the period collapses first. The ledger is filter-only: it
// earned no column of its own next to what the row is actually about.
// The partner splits left the table — with six to eight actions per row the
// grid had no room left for what the operator actually scans by. The whole
// split (Gustavo, Carlos and la empresa) lives in the income detail modal.
const columns = [
  // `link: true`: acá va el enlace al detalle, y la celda se vuelve `relative`
  // para que se estire a todo su ancho.
  {
    key: 'concept', label: 'Concepto', size: 'name', sortable: true, link: true,
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'client_name', label: 'Cliente', size: 'name', sortable: true, hideBelow: 'md',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'project_name', label: 'Proyecto', size: 'name', sortable: true, hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'kind_label', label: 'Tipo', size: 'badge',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'payment_status', label: 'Cobro', size: 'text',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'collection_confidence', label: 'Previsión', size: 'name',
    responsive: { compact: 'group', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'period_label', label: 'Mes', sortable: true, hideBelow: 'lg',
    responsive: { compact: 'group', portrait: 'group', landscape: 'group' },
  },
  {
    key: 'total_amount', label: 'Total', format: 'money', sortable: true,
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
];

// ── Vista agrupada por cliente ──

const { viewMode, isGrouped, initFromSettings } = useIncomeViewMode(store);

const viewModeOptions = [
  { value: 'grouped', label: 'Agrupado' },
  { value: 'classic', label: 'Clásico' },
];

const collapsedGroupIds = ref([]);

function toggleGroup(id) {
  collapsedGroupIds.value = collapsedGroupIds.value.includes(id)
    ? collapsedGroupIds.value.filter((groupId) => groupId !== id)
    : [...collapsedGroupIds.value, id];
}

/** Grouped over the WHOLE sorted + filtered set (no pagination), like the totals modal. */
const clientGroups = computed(() =>
  withClientWeights(groupByClient(sortedRecords.value)),
);

// The group header already names the client. The remaining sortable columns
// order rows INSIDE each group; groupByClient keeps its billed-desc client
// ranking and the trailing unassigned bucket. Proyecto stays: inside one
// client's group it is exactly what tells rows apart.
const groupedColumns = columns
  .filter((col) => col.key !== 'client_name');

async function updateIncomeReceivable(row, payload) {
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

// ── Selección múltiple + asignación masiva de cliente ──

// Fed the FULL store list, not the filtered rows: the selection is meant to
// survive a filter change, so only "this income no longer exists" may drop an
// id from it.
const { selectedIds, clearSelection, dropIds } = useRowSelection(() => store.incomes);
const totalsModalOpen = ref(false);

const filteredIds = computed(() => filteredRecords.value.map((row) => row.id));

/** What identifies an income in the bulk confirmation list. */
const incomeLabel = (row) => row.concept || `Ingreso #${row.id}`;

async function applyClientToSelection({ ids, client, mode, plan }) {
  const result = await runMutation(
    () => store.bulkAssignIncomeClient(ids, client),
    {
      successTitle: mode === 'unlink'
        ? 'Cliente desvinculado de los ingresos'
        : 'Cliente asignado a los ingresos',
      // The server skips rows already on the target, so the count it returns
      // is what actually changed — not what was selected.
      successDetail: (r) => describeAssignmentResult(
        plan, r.data?.updated ?? 0, { entity: INCOME_ENTITY },
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
  // The server refused the batch because some of it no longer exists. Drop
  // those ids first — that holds even if the reload below fails — then rebuild
  // the list so the counters, the groups and the KPI meta agree with it.
  if (result.missingIds?.length) {
    dropIds(result.missingIds);
    await loadRecords();
  }
}

async function applyProjectToSelection({ ids, project, mode, plan }) {
  const result = await runMutation(
    () => store.bulkAssignIncomeProject(ids, project),
    {
      successTitle: mode === 'unlink'
        ? 'Proyecto quitado de los ingresos'
        : 'Proyecto asignado a los ingresos',
      successDetail: (r) => describeProjectAssignmentResult(
        plan, r.data?.updated ?? 0, { entity: INCOME_ENTITY },
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

// ── Abono sobre la selección (bulk settle) ──

const bulkSettleOpen = ref(false);
const bulkSettleRecords = ref([]);
const bulkSettleExcluded = ref(0);

function openBulkSettle({ ids, excludedCount }) {
  const byId = new Map(store.incomes.map((row) => [row.id, row]));
  bulkSettleRecords.value = ids.map((id) => byId.get(id)).filter(Boolean);
  bulkSettleExcluded.value = excludedCount;
  bulkSettleOpen.value = true;
}

function closeBulkSettle() {
  bulkSettleOpen.value = false;
  bulkSettleRecords.value = [];
  bulkSettleExcluded.value = 0;
}

async function handleBulkSettleSubmit(payload) {
  // markMutated takes ONE static id, so the flash goes to the row whose
  // state is the least obvious afterwards: the partial one, predictable
  // from the payload. Full covers flash nothing — flashing one of N
  // equally-changed rows would mislead.
  const byId = new Map(bulkSettleRecords.value.map((row) => [row.id, row]));
  const partial = payload.allocations.find((entry) => {
    const row = byId.get(entry.income_id);
    return row && entry.amount < Number(row.pending_amount);
  });
  const result = await runMutation(
    () => store.bulkSettleIncomes(payload),
    {
      successTitle: 'Abono registrado',
      successDetail: (r) => describeBulkSettleResult(r.data?.results ?? []),
      errorTitle: 'No se pudo registrar el abono',
      flashId: partial?.income_id,
    },
  );
  if (result.success) {
    closeBulkSettle();
    clearSelection();
    return;
  }
  // A stale selection names its ids: drop exactly those, close (their rows
  // are gone) and rebuild. An ordinary 400 keeps the modal open with the
  // backend message in the error toast.
  if (result.missingIds?.length) {
    dropIds(result.missingIds);
    closeBulkSettle();
    await loadRecords();
  }
}

// ── Cuenta de cobro desde el ingreso ──

const collectionModalOpen = ref(false);
const collectionIncome = ref(null);

function openCollectionModal(row) {
  collectionIncome.value = row;
  collectionModalOpen.value = true;
}

async function openTotalsModal() {
  totalsModalOpen.value = true;
  // Hostings live in another tab: fetch them once so the per-client view
  // can show both halves of what a client costs and pays.
  if (!store.hostings.length) await store.fetchRecords('hostings');
}

function onCollectionCreated() {
  collectionModalOpen.value = false;
  collectionIncome.value = null;
  // Reload so the row swaps to the "Ver cuenta de cobro" action.
  loadRecords();
}

function goToCollectionAccount(row) {
  navigateTo({
    path: '/panel/accounting/collections',
    query: { focus: row.collection_account_id },
  });
}

function goToIncomeEmails(row) {
  navigateTo(historySendsLink('income', row.id));
}

// ── Acciones de fila: un solo menú para las dos vistas ──
//
// The two view modes each carried their own copy of the action block and had
// already drifted: the classic table had silently lost silenciar avisos. One
// component makes that impossible.

const actionsOpen = ref(false);
const actionsRow = ref(null);
// «Ver nota» is a menu entry only when the income has one.
const noteRow = ref(null);

function openActions(row) {
  actionsRow.value = row;
  actionsOpen.value = true;
}

// El detalle del ingreso tiene dirección propia (`?income=`): así la fila puede
// publicarla en un enlace, y recargar o compartir la URL reabre la capa.
// Deliberadamente NO es un ephemeralParam — esos se borran en el setup, que es
// por qué `?focus=` no sobrevive a una recarga.
const {
  openId: detailIncomeId,
  isOpen: detailOpen,
  toFor: incomeDetailTo,
  open: openDetailById,
  close: closeIncomeDetail,
} = useDetailQueryParam('income');

function openIncomeDetail(row) {
  openDetailById(row.id);
}

/** Row whose duplicate prefill is being fetched, so its kebab can say so. */
const duplicatingId = ref(null);

/**
 * Open the next period of a recurring income: the server builds the prefill
 * (always expected, with the hosting cycle's date when it can work it out)
 * and the form opens on it. Nothing is written until Guardar, which is the
 * point — the date almost always needs a look first.
 */
async function duplicateIncome(row) {
  // One at a time. The action menu closes on click, so nothing on screen
  // would otherwise say the first request is still running, and a second
  // click would race a second draft into the same form.
  if (duplicatingId.value) return;
  duplicatingId.value = row.id;
  let result;
  try {
    result = await store.fetchIncomeDuplicateDraft(row.id);
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
  closeIncomeDetail();
  openSeededModal(result.data);
}

function toggleMute(row) {
  if (row.reminders_muted) unmuteIncome(row);
  else openMuteModal(row);
}

async function loadRecords() {
  await store.fetchRecords('incomes');
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

onMounted(async () => {
  // ?project=<id> — deep link from the /panel/projects counts; the URL pins
  // accounting_incomeTab=all because the landing tab hides settled rows.
  const projectParam = Number(consumeParam('project'));
  if (Number.isInteger(projectParam) && projectParam > 0) {
    currentFilters.projects = [projectParam];
  }
  // Project filter options come from the full catalog (history.vue
  // pattern); the store swallows failures, so an error just means a
  // smaller dropdown, never a blocked page.
  projectsStore.fetchProjects();
  // Sequential on purpose: the landing mode must be known before rows render
  // (no mode flash), and fetchSettings shares store.isLoading with the rows
  // fetch — in parallel, whichever finishes first would flash the empty state.
  await initFromSettings();
  await loadRecords();
  // ?focus=<id> reveals the row (navigation back from Cuentas de cobro).
  // Flashing alone was not enough: with PAGE_SIZE rows per page the target
  // is often not rendered at all, and even when it is the operator has no
  // idea where on the page it landed.
  await revealFocusedRow(Number(consumeParam('focus')));
});

/**
 * Bring the deep-linked row into view: jump to the page holding it, scroll
 * to it, then flash it.
 */
async function revealFocusedRow(focusId) {
  if (!focusId) return;
  const index = sortedRecords.value.findIndex((row) => row.id === focusId);
  if (index === -1) return;
  // The grouped view renders the whole filtered set, so it never paginates.
  if (!isGrouped.value) {
    currentPage.value = Math.floor(index / PAGE_SIZE) + 1;
  }
  lastMutatedId.value = focusId;
  await nextTick();
  if (typeof document === 'undefined') return;
  const element = document.querySelector(`[data-testid="accounting-row-${focusId}"]`);
  if (element && typeof element.scrollIntoView === 'function') {
    element.scrollIntoView({ block: 'center' });
  }
  setTimeout(() => {
    if (lastMutatedId.value === focusId) lastMutatedId.value = null;
  }, 2500);
}
usePanelRefresh(loadRecords);
</script>
