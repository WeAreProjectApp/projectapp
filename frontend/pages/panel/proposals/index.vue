<template>
  <div>
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      :require-type-text="confirmState.requireTypeText"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />
    <ContractParamsModal
      :visible="showContractModal"
      :proposal="contractModalProposal || {}"
      @confirm="handleContractConfirmFromList"
      @cancel="showContractModal = false; contractModalProposal = null"
    />
    <ProposalResendModal
      :visible="Boolean(resendModalProposal)"
      :proposal="resendModalProposal || {}"
      @close="resendModalProposal = null"
      @resent="handleResendComplete"
    />
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-8">
      <h1 class="text-2xl font-light text-text-default">Propuestas</h1>
      <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:gap-3">
        <BaseButton
          as="NuxtLink"
          variant="secondary"
          size="md"
          :to="localePath('/panel/defaults?mode=proposal')"
          title="Configurar valores por defecto de las propuestas"
        >
          <BaseActionIcon action="settings" />
          Valores por Defecto
        </BaseButton>
        <BaseButton
          as="NuxtLink"
          variant="primary"
          size="md"
          :to="localePath('/panel/proposals/create')"
        >
          <BaseActionIcon action="create" />
          Nueva Propuesta
        </BaseButton>
      </div>
    </div>

    <!-- KPI Dashboard -->
    <ProposalDashboard ref="proposalDashboardRef" />

    <!-- Floating metrics manual -->
    <MetricsManual />

    <!-- Zombie proposals segment -->
    <div v-if="zombieAlerts.length" class="mb-4 bg-surface border border-border-default rounded-xl shadow-card p-4">
      <div class="flex items-center justify-between mb-3 cursor-pointer" @click="zombieExpanded = !zombieExpanded">
        <div class="flex items-center gap-2">
          <span class="text-lg">🧟</span>
          <h3 class="text-sm font-semibold text-text-default">Propuestas zombie ({{ zombieAlerts.length }})</h3>
        </div>
        <BaseActionIcon :action="zombieExpanded ? 'collapse' : 'expand'" class="text-text-subtle" />
      </div>
      <div v-if="zombieExpanded" class="space-y-2">
        <!-- Sin controles adentro: la tarjeta entera es el enlace. -->
        <BaseRowLink
          v-for="alert in zombieAlerts"
          :key="`zombie-${alert.id}-${alert.alert_type}`"
          :to="proposalHref(alert.id)"
          :data-testid="`zombie-open-${alert.id}`"
          class="flex items-center justify-between bg-surface-raised rounded-lg px-4 py-2.5 border border-border-default hover:border-focus-ring/40 transition-colors"
        >
          <span class="flex items-center gap-3">
            <span class="text-sm" aria-hidden="true">{{ alert.alert_type === 'zombie_draft' ? '📝💀' : alert.alert_type === 'zombie_sent_stale' ? '📤💀' : '💀' }}</span>
            <span>
              <span class="text-sm font-medium text-text-default">{{ alert.client_name }}</span>
              <span class="text-xs text-text-subtle ml-2">{{ alert.title }}</span>
            </span>
          </span>
          <span class="text-xs text-text-subtle font-medium">{{ alert.message }}</span>
        </BaseRowLink>
      </div>
    </div>

    <!-- Alerts panel -->
    <div v-if="activeAlerts.length || showAlertForm" class="mb-6 bg-warning-soft border border-warning-strong/30 rounded-xl overflow-hidden">
      <div class="flex items-center justify-between gap-3 px-4 py-3 border-l-4 border-l-warning-strong">
        <div class="flex items-center gap-2.5 cursor-pointer flex-1 min-w-0" @click="attentionExpanded = !attentionExpanded">
          <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-warning-strong/15 text-base" aria-hidden="true">⚠️</span>
          <h3 class="text-sm font-semibold text-warning-strong truncate">
            Propuestas que necesitan atención
            <span class="ml-1 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-warning-strong text-warning-soft text-[11px] font-bold">{{ groupedActiveAlerts.length }}</span>
          </h3>
          <BaseActionIcon :action="attentionExpanded ? 'collapse' : 'expand'" class="text-warning-strong/70" />
        </div>
        <BaseButton variant="ghost" size="sm" class="shrink-0" @click.stop="toggleAlertForm">
          <BaseActionIcon :action="showAlertForm ? 'close' : 'create'" />
          {{ showAlertForm ? 'Cancelar' : 'Crear recordatorio' }}
        </BaseButton>
      </div>
      <div class="px-4 pb-4 pt-1">

      <!-- Create alert form -->
      <div v-if="showAlertForm" class="mb-4 bg-surface rounded-lg border border-warning-soft p-4 space-y-3">
        <BaseFormRow :cols="3" :gap="3">
          <BaseFormField label="Propuesta" size="sm">
            <BaseSelect v-model="newAlert.proposal" size="sm" placeholder="Seleccionar...">
              <option value="">Seleccionar...</option>
              <option v-for="p in proposalStore.proposals" :key="p.id" :value="p.id">{{ p.client_name }} — {{ p.title }}</option>
            </BaseSelect>
          </BaseFormField>
          <BaseFormField label="Tipo" size="sm">
            <BaseSelect
              v-model="newAlert.alert_type"
              size="sm"
              :options="[
                { value: 'reminder', label: 'Recordatorio' },
                { value: 'followup', label: 'Seguimiento' },
                { value: 'call', label: 'Llamada' },
                { value: 'meeting', label: 'Reunión' },
                { value: 'custom', label: 'Personalizado' },
              ]"
            />
          </BaseFormField>
          <BaseFormField label="Fecha" size="sm">
            <BaseInput v-model="newAlert.alert_date" type="datetime-local" size="sm" />
          </BaseFormField>
        </BaseFormRow>
        <div class="flex gap-3 items-end">
          <BaseFormField label="Mensaje" size="sm" class="flex-1">
            <BaseInput v-model="newAlert.message" type="text" size="sm" placeholder="Ej: Llamar al cliente para seguimiento..." />
          </BaseFormField>
          <BaseControlGate :reasons="newAlertBlockReasons" label="Crear recordatorio no disponible" align="end">
            <template #default="{ describedBy }">
              <BaseButton
                variant="primary"
                size="md"
                :disabled="Boolean(newAlertBlockReasons.length)"
                :disabled-reason="newAlertBlockReasons.join(' ')"
                :aria-describedby="describedBy"
                @click="handleCreateAlert"
              >
                Crear
              </BaseButton>
            </template>
          </BaseControlGate>
        </div>
        <p v-if="alertError" class="text-xs text-danger-strong">{{ alertError }}</p>
      </div>

      <div v-if="attentionExpanded" class="space-y-2">
        <div v-for="group in groupedActiveAlerts" :key="group.key">
          <!-- Group header row -->
          <div
            class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 bg-surface rounded-lg px-3 sm:px-4 py-2.5 border cursor-pointer transition-colors hover:bg-surface-raised"
            :class="alertBorderClass(group.priority)"
            @click="openAlertGroup(group, $event)"
          >
            <div class="flex items-start sm:items-center gap-2.5 min-w-0 flex-1">
              <BaseActionIcon
                v-if="group.isMulti"
                :action="expandedAlertGroups.has(group.key) ? 'collapse' : 'expand'"
                class="text-text-subtle mt-1 sm:mt-0"
              />
              <span class="text-base shrink-0 mt-0.5 sm:mt-0">{{ group.icon }}</span>
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <!-- Un grupo con varias propuestas es un desplegable, no un
                       destino: sólo el de una sola tiene dirección que publicar.
                       El botón de descartar vive en esta misma fila, así que el
                       enlace se queda en el nombre y no se estira. -->
                  <BaseRowLink
                    :to="group.isMulti ? null : proposalHref(group.firstProposalId)"
                    :data-testid="`alert-group-open-${group.key}`"
                    class="text-sm font-medium text-text-default truncate"
                  >{{ group.client_name }}</BaseRowLink>
                  <span v-if="group.priority === 'critical'" class="px-1.5 py-0.5 text-[10px] font-bold uppercase rounded bg-danger-soft text-danger-strong">urgente</span>
                  <span v-if="group.alerts.length > 1" class="px-1.5 py-0.5 text-[10px] font-bold uppercase rounded bg-warning-soft text-warning-strong">
                    {{ group.alerts.length }} alertas
                  </span>
                </div>
                <span class="text-xs text-text-subtle block sm:inline mt-0.5 sm:mt-0">{{ group.subtitle }}</span>
              </div>
            </div>
            <div class="flex items-start sm:items-center justify-between sm:justify-end gap-3 pl-9 sm:pl-0 shrink-0">
              <div class="text-left sm:text-right">
                <span class="text-xs font-medium block" :class="group.priority === 'critical' ? 'text-danger-strong' : 'text-warning-strong'">{{ group.message }}</span>
                <span v-if="group.refDate" class="text-[10px] text-text-subtle">
                  {{ formatAlertDate(group.refDate) }}
                </span>
              </div>
              <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Descartar" title="Descartar" @click.stop="handleDismissAlertGroup(group)"><BaseActionIcon action="close" /></BaseButton>
            </div>
          </div>

          <!-- Sub-items for expanded multi-proposal groups -->
          <Transition
            enter-active-class="transition-[opacity,transform,max-height] duration-200 ease-out"
            leave-active-class="transition-[opacity,transform,max-height] duration-150 ease-in"
            enter-from-class="opacity-0 -translate-y-1 max-h-0"
            enter-to-class="opacity-100 translate-y-0 max-h-[1000px]"
            leave-from-class="opacity-100 translate-y-0 max-h-[1000px]"
            leave-to-class="opacity-0 -translate-y-1 max-h-0"
          >
            <PanelAlertGroupSubItems
              v-if="group.isMulti && expandedAlertGroups.has(group.key)"
              :proposals="group.proposals"
              :href-for="proposalHref"
            />
          </Transition>
        </div>
      </div>
      </div>
    </div>

    <!-- Filter Tabs -->
    <ProposalFilterTabs
      :tabs="savedTabs"
      :active-tab-id="activeTabId"
      :is-tab-limit-reached="isTabLimitReached"
      show-config-tab
      :config-active="showConfigTab"
      @select="handleSelectTab"
      @create="handleCreateTab"
      @rename="renameTab"
      @delete="deleteTab"
      @restore="restoreTab"
      @rebase="rebaseTab"
      @reorder="reorderTabs"
      @config="showConfigTab = true"
    />

    <!-- Settings tab replaces the list area -->
    <ViewSettingsPanel
      v-if="showConfigTab"
      :filter-views="[{ value: 'proposal', label: 'Propuestas' }]"
      @reset="reloadFilterTabs"
    >
      <section class="bg-surface border border-border-muted rounded-xl shadow-sm p-5 sm:p-6">
        <h2 class="text-lg font-bold text-text-default mb-1">Defaults de propuestas</h2>
        <p class="text-sm text-text-muted mb-4">
          Secciones, textos y condiciones por defecto con los que nacen las
          propuestas nuevas.
        </p>
        <BaseButton as="NuxtLink" variant="secondary" size="sm" :to="localePath('/panel/proposals/defaults')">
          Abrir defaults de propuestas
        </BaseButton>
      </section>
    </ViewSettingsPanel>

    <template v-if="!showConfigTab">
    <!-- Search + Filter toggle -->
    <div class="flex flex-col sm:flex-row gap-3 mb-4">
      <div class="relative flex-1 max-w-sm">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-subtle" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar por título o cliente..."
          class="w-full pl-10 pr-4 py-2 bg-input-bg text-text-default placeholder:text-text-subtle border border-input-border rounded-xl text-sm focus:ring-1 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
        />
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <UiFilterToggleButton :open="isFilterPanelOpen" :count="activeFilterCount" @click="toggleFilterPanel" />
      </div>
    </div>

    <!-- Filter Panel -->
    <ProposalFilterPanel
      :model-value="currentFilters"
      :is-open="isFilterPanelOpen"
      :filter-count="activeFilterCount"
      @update:model-value="Object.assign(currentFilters, $event)"
      @reset="handleResetFilters"
    />

    <!-- Loading -->
    <div v-if="proposalStore.isLoading" class="text-center py-12 text-text-subtle text-sm">
      Cargando...
    </div>

    <!-- Empty state -->
    <div v-else-if="proposals.length === 0" class="text-center py-16 text-text-subtle">
      <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-surface-raised flex items-center justify-center">
        <svg class="w-8 h-8 text-text-subtle" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <p class="text-text-muted text-sm">No hay propuestas{{ hasActiveFilters ? ' con los filtros seleccionados' : '' }}.</p>
    </div>

    <BaseBulkActionBar
      :selected-count="selectedIds.length"
      :actions="bulkActionItems"
      :busy="isBulkActing"
      testid-prefix="proposal"
      testid="batch-action-bar"
      @clear="clearSelection"
    />

    <!-- Business priority on narrow screens: client + title, status and
         investment remain visible; activity is grouped and telemetry waits. -->
    <div v-if="!proposalStore.isLoading && proposals.length > 0">
      <BaseResponsiveTable
        :columns="proposalColumns"
        :rows="paginatedProposals"
        v-model:selected="selectedIds"
        :sort-key="sortKey"
        :sort-dir="sortDir"
        :row-class="(proposal) => proposal.is_active ? '' : 'opacity-60'"
        :selection-label="(proposal) => `Seleccionar ${proposal.title || proposal.client_name}`"
        selectable
        interactive-rows
        :show-default-actions="false"
        row-actions-layout="menu-start"
        caption="Propuestas comerciales por cliente"
        test-id-prefix="proposal"
        @sort="toggleSort"
        @row-click="(proposal, event) => navigateToProposal(proposal.id, event)"
        @row-auxclick="(proposal, event) => navigateToProposal(proposal.id, event)"
      >
        <template #cell-id="{ row: proposal }">
          <span :data-testid="`proposal-row-id-${proposal.id}`">#{{ proposal.id }}</span>
        </template>

        <template #cell-client_name="{ row: proposal }">
          <BaseRowLink
            :to="proposalHref(proposal.id)"
            :data-testid="`proposal-open-${proposal.id}`"
            class="block min-w-0 max-w-full [overflow-wrap:anywhere] transition-colors hover:text-text-brand"
          >
            <span class="block text-sm font-medium text-text-default">{{ proposal.client_name }}</span>
            <span v-if="proposal.title" class="mt-0.5 block text-xs leading-snug text-text-muted">{{ proposal.title }}</span>
          </BaseRowLink>
          <div v-if="proposal.client_phone" class="mt-1 w-fit text-2xs text-text-subtle">📱 {{ proposal.client_phone }}</div>
        </template>

        <template #cell-status="{ row: proposal }">
          <ProposalStatusSelect
            :proposal="proposal"
            :updating="updatingStatusId === proposal.id"
            @change="(status) => onStatusSelect(proposal, status)"
          />
        </template>

        <template #cell-total_investment="{ row: proposal }">
          <span class="tabular-nums">${{ effectiveInvestmentTotal(proposal).toLocaleString() }} {{ proposal.currency }}</span>
        </template>

        <template #cell-last_activity_at="{ row: proposal }">
          <span v-if="isInactive(proposal)" class="inline-flex rounded-full bg-danger-soft px-1.5 py-0.5 text-2xs font-medium text-danger-strong">
            {{ inactiveDays(proposal) }}d sin actividad
          </span>
          <span v-else-if="proposal.last_activity_at">{{ timeAgo(proposal.last_activity_at) }}</span>
          <span v-else-if="proposal.created_at">{{ timeAgo(proposal.created_at) }} <span class="text-2xs text-text-subtle">(creada)</span></span>
          <span v-else class="text-text-subtle">—</span>
        </template>

        <template #cell-view_count="{ row: proposal }">
          <span class="tabular-nums">{{ proposal.view_count }}</span>
        </template>

        <template #cell-heat_score="{ row: proposal }">
          <BaseTooltip v-if="proposal.heat_score > 0 && proposal.engagement_summary" position="left" width="max-w-[260px]" minWidth="min-w-0">
            <template #trigger>
              <span class="inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white" :class="heatScoreColor(proposal.heat_score)">
                {{ proposal.heat_score }}
              </span>
            </template>
            <div class="space-y-1.5 text-xs">
              <div class="flex justify-between gap-3"><span class="text-text-subtle">Vistas</span><span class="font-medium">{{ proposal.engagement_summary.views }}</span></div>
              <div v-if="proposal.engagement_summary.last_activity" class="flex justify-between gap-3"><span class="text-text-subtle">Última visita</span><span class="font-medium">{{ proposal.engagement_summary.last_activity }}</span></div>
              <div class="flex justify-between gap-3"><span class="text-text-subtle">Inversión</span><span class="font-medium">{{ formatInvestmentTime(proposal.engagement_summary.investment_time_sec) }}</span></div>
              <div v-if="proposal.engagement_summary.technical_viewed" class="flex justify-between gap-3"><span class="text-teal-400">Det. técnico</span><span class="font-medium text-teal-300">{{ formatInvestmentTime(proposal.engagement_summary.technical_time_sec) }}</span></div>
              <div v-if="proposal.engagement_summary.unique_devices > 1" class="flex justify-between gap-3"><span class="text-text-subtle">Dispositivos</span><span class="font-medium">{{ proposal.engagement_summary.unique_devices }}</span></div>
              <div v-if="proposal.engagement_summary.skipped_sections?.length" class="border-t border-white/15 pt-1"><span class="text-text-subtle">No revisó:</span><span class="ml-1 text-amber-400">{{ proposal.engagement_summary.skipped_sections.map(sectionLabel).join(', ') }}</span></div>
            </div>
          </BaseTooltip>
          <span v-else-if="proposal.heat_score > 0" class="inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white" :class="heatScoreColor(proposal.heat_score)">{{ proposal.heat_score }}</span>
          <span v-else class="text-xs text-text-subtle">—</span>
        </template>

        <template #row-actions="{ row: proposal }">
          <BaseActionButton
            action="more"
            :label="`Acciones de ${proposal.title || proposal.client_name}`"
            :data-testid="`proposal-actions-${proposal.id}`"
            size="md"
            @click.stop="actionsModalProposal = proposal"
          />
        </template>
      </BaseResponsiveTable>

      <BaseModal v-model="actionsModalOpen" kind="confirm">
        <template v-if="actionsModalProposal">
            <div class="px-6 py-4 border-b border-border-muted flex items-center justify-between">
              <div class="min-w-0">
                <h3 class="text-base font-bold text-text-default truncate">{{ actionsModalProposal.title }}</h3>
                <p class="text-xs text-text-muted mt-0.5">{{ actionsModalProposal.client_name }}</p>
              </div>
              <BaseActionButton action="close" label="Cerrar acciones" size="md" @click="actionsModalProposal = null" />
            </div>
            <div class="p-3 space-y-1 max-h-[60vh] overflow-y-auto">
              <template v-for="action in proposalActions" :key="action.key">
                <component
                  :is="action.href ? 'a' : action.to ? NuxtLinkComponent : 'button'"
                  v-bind="action.href ? { href: action.href, target: '_blank', rel: 'noopener noreferrer' } : action.to ? { to: action.to } : {}"
                  class="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-colors group"
                  :class="action.danger ? 'hover:bg-danger-soft' : 'hover:bg-surface-raised'"
                  @click="action.onClick ? action.onClick() : null"
                >
                  <span class="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                    :class="action.danger ? 'bg-danger-soft text-danger-strong' : action.bgClass || 'bg-surface-raised'"
                  >
                    <BaseActionIcon :action="action.action" />
                  </span>
                  <div class="min-w-0 flex-1">
                    <span class="text-sm font-medium block" :class="action.danger ? 'text-danger-strong' : action.textClass || 'text-text-default'">{{ action.label }}</span>
                    <span class="mt-0.5 block text-xs leading-snug text-text-muted panel-landscape:hidden">{{ action.info }}</span>
                  </div>
                  <!-- Info tooltip -->
                  <div class="relative hidden flex-shrink-0 panel-landscape:block group/info">
                    <span class="w-6 h-6 rounded-full bg-surface-raised group-hover/info:bg-primary-soft flex items-center justify-center text-text-subtle group-hover/info:text-text-brand text-[11px] cursor-help transition-colors">?</span>
                    <div class="absolute right-full top-1/2 -translate-y-1/2 mr-2 w-52 bg-primary-strong text-white text-xs rounded-xl px-3 py-2 shadow-raised opacity-0 pointer-events-none group-hover/info:opacity-100 group-hover/info:pointer-events-auto transition-opacity z-10 leading-relaxed">
                      {{ action.info }}
                      <div class="absolute top-1/2 -translate-y-1/2 -right-1 w-2 h-2 bg-primary-strong rotate-45" />
                    </div>
                  </div>
                </component>
              </template>

              <!-- Cambiar estado -->
              <div class="mt-2 pt-3 border-t border-border-muted px-4 pb-2">
                <div class="flex items-center justify-between gap-3">
                  <div class="flex items-center gap-3 min-w-0">
                    <span class="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 bg-surface-raised"><BaseActionIcon action="change-status" /></span>
                    <div class="min-w-0">
                      <span class="text-sm font-medium block text-text-default">Cambiar estado</span>
                      <span class="text-[11px] text-text-subtle block leading-tight">Fuera del flujo normal no se envían correos ni automatizaciones.</span>
                    </div>
                  </div>
                  <ProposalStatusSelect
                    :proposal="actionsModalProposal"
                    :updating="updatingStatusId === actionsModalProposal.id"
                    @change="(s) => { const p = actionsModalProposal; actionsModalProposal = null; onStatusSelect(p, s); }"
                  />
                </div>
              </div>
            </div>
        </template>
      </BaseModal>

      <BaseModal v-model="sendConfirmOpen" kind="confirm">
        <div class="p-6 text-center">
          <div class="mb-3 text-4xl">📤</div>
          <h3 class="mb-2 text-lg font-bold text-text-default">¿Enviar esta propuesta?</h3>
          <p class="text-sm text-text-muted">Se enviará un email al cliente con el enlace de la propuesta.</p>
        </div>
        <template #footer>
          <BaseModalActions>
            <BaseButton variant="secondary" size="md" @click="sendConfirmId = null">Cancelar</BaseButton>
            <BaseButton variant="primary" size="md" :disabled="isSending" @click="confirmSend">{{ isSending ? 'Enviando...' : 'Sí, enviar' }}</BaseButton>
          </BaseModalActions>
        </template>
      </BaseModal>

      <BaseModal v-model="quickLogOpen" kind="form">
        <template v-if="quickLogProposal">
          <div class="p-6">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-base font-bold text-text-default">Registrar actividad</h3>
              <BaseActionButton action="close" label="Cerrar registro de actividad" size="md" @click="quickLogProposal = null" />
            </div>
            <p class="text-xs text-text-muted mb-4">{{ quickLogProposal.client_name }} — {{ quickLogProposal.title }}</p>
            <div class="space-y-3">
              <BaseFormField label="Tipo de actividad">
                <BaseSelect v-model="quickLogType">
                  <option value="call">📞 Llamada</option>
                  <option value="meeting">🤝 Reunión</option>
                  <option value="followup">📩 Seguimiento</option>
                  <option value="note">📝 Nota</option>
                </BaseSelect>
              </BaseFormField>
              <BaseFormField label="Descripción" required :error="quickLogError">
                <BaseInput
                  v-model="quickLogMessage"
                  :error="!!quickLogError"
                  placeholder="Ej: Llamada de seguimiento, cliente interesado"
                  data-testid="proposal-quick-log-description"
                  @update:model-value="quickLogError = ''"
                  @keyup.enter="confirmQuickLog"
                />
              </BaseFormField>
            </div>
          </div>
        </template>
        <template #footer>
          <BaseModalActions v-if="(quickLogProposal)">
            <BaseButton variant="secondary" size="md" @click="quickLogProposal = null">Cancelar</BaseButton>
            <BaseButton
              variant="primary"
              size="md"
              :loading="isQuickLogging"
              data-testid="proposal-quick-log-submit"
              @click="confirmQuickLog"
            >
              {{ isQuickLogging ? 'Guardando...' : 'Registrar' }}
            </BaseButton>
          </BaseModalActions>
        </template>
      </BaseModal>

      <!-- Pagination -->
      <BasePagination
        v-if="totalPages > 1"
        :current-page="currentPage"
        :total-pages="totalPages"
        :total-items="filteredProposals.length"
        :range-from="rangeFrom"
        :range-to="rangeTo"
        aria-label="Paginación de propuestas"
        class="px-6 border-t border-border-muted"
        @prev="goToPage(currentPage - 1)"
        @next="goToPage(currentPage + 1)"
        @go="goToPage"
      />
    </div>
    </template>
    <!-- Status/send feedback now renders via the global <PanelNotificationHost /> -->
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, resolveComponent } from 'vue';
import ProposalDashboard from '~/components/BusinessProposal/admin/ProposalDashboard.vue';
import MetricsManual from '~/components/BusinessProposal/admin/MetricsManual.vue';
import ContractParamsModal from '~/components/BusinessProposal/admin/ContractParamsModal.vue';
import ProposalResendModal from '~/components/BusinessProposal/admin/ProposalResendModal.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import ViewSettingsPanel from '~/components/panel/ViewSettingsPanel.vue';
import ProposalFilterPanel from '~/components/proposals/ProposalFilterPanel.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import ProposalStatusSelect from '~/components/panel/proposal/ProposalStatusSelect.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { useProposalStatusChange } from '~/composables/useProposalStatusChange';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useProposalFilters } from '~/composables/useProposalFilters';
import { useRowSelection } from '~/composables/useRowSelection';
import { useRowNavigation } from '~/composables/useRowNavigation';

const localePath = useLocalePath();
const { openRow } = useRowNavigation();
// Resuelto acá y no como string en `:is`: Nuxt resuelve los componentes en
// compilación, así que 'NuxtLink' en un `:is` se renderiza como el elemento
// desconocido <nuxtlink> — sin href y sin navegar. `resolveComponent` sí lo
// resuelve (mismo camino que components/base/BaseDropdown.vue).
const NuxtLinkComponent = resolveComponent('NuxtLink');
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const proposalStore = useProposalStore();
const proposals = computed(() => proposalStore.proposals);
const {
  currentFilters,
  savedTabs,
  activeTabId,
  isFilterPanelOpen,
  hasActiveFilters,
  activeFilterCount,
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
  reloadTabs: reloadFilterTabs,
} = useProposalFilters();

// Fixed trailing "Configuraciones" tab: swaps the list for the settings panel.
const showConfigTab = ref(false);

function handleSelectTab(tabId) {
  showConfigTab.value = false;
  selectTab(tabId);
}
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const notify = usePanelNotify();
const actionsModalProposal = ref(null);
const resendModalProposal = ref(null);
const copiedId = ref(null);
const sendConfirmId = ref(null);
const isSending = ref(false);
const quickLogProposal = ref(null);
const quickLogType = ref('call');
const quickLogMessage = ref('');
const quickLogError = ref('');
const isQuickLogging = ref(false);
const searchQuery = ref('');
const showAlertForm = ref(false);
const alertError = ref('');
const newAlert = reactive({
  proposal: '',
  alert_type: 'reminder',
  message: '',
  alert_date: '',
});
const newAlertBlockReasons = computed(() => [
  !newAlert.proposal ? 'Elige la propuesta del recordatorio.' : '',
  !newAlert.message.trim() ? 'Escribe el mensaje del recordatorio.' : '',
].filter(Boolean));
const sortKey = ref('created_at');
const sortDir = ref('desc');
const currentPage = ref(1);
const pageSize = 15;
const proposalColumns = [
  {
    key: 'client_name', label: 'Cliente', size: 'name', sortable: true, link: true,
    responsive: { primary: true, compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'status', label: 'Estado', size: 'badge',
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'total_investment', label: 'Inversión', size: 'money', sortable: true,
    responsive: { compact: 'keep', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'last_activity_at', label: 'Última actividad', size: 'date', sortable: true,
    responsive: { compact: 'group', portrait: 'keep', landscape: 'keep' },
  },
  {
    key: 'view_count', label: 'Vistas', size: 'tiny',
    responsive: { compact: 'hide', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'heat_score', label: 'Interés', size: 'tiny', align: 'center',
    responsive: { compact: 'hide', portrait: 'group', landscape: 'keep' },
  },
  {
    key: 'id', label: 'ID', size: 'tiny',
    responsive: { compact: 'hide', portrait: 'hide', landscape: 'hide' },
  },
];
const zombieExpanded = ref(false);
const attentionExpanded = ref(true);
const dismissedComputedAlertKeys = ref(new Set());
const expandedAlertGroups = ref(new Set());
// Fed the FULL store list, not the page: the selection spans pages, so only a
// proposal that stopped existing may drop out of it. Deleting one used to
// leave its id behind and the batch bar went on counting it.
const { selectedIds, selectedSet, clearSelection } = useRowSelection(
  () => proposalStore.proposals,
);
const selectedResendWithoutMessage = computed(() => proposalStore.proposals.filter(
  (proposal) => selectedSet.value.has(proposal.id)
    && ['sent', 'viewed'].includes(proposal.status)
    && !(proposal.email_intro || '').trim(),
));
const isBulkActing = ref(false);
const isRefreshing = ref(false);

const actionsModalOpen = computed({
  get: () => actionsModalProposal.value !== null,
  set: (open) => { if (!open) actionsModalProposal.value = null; },
});
const sendConfirmOpen = computed({
  get: () => sendConfirmId.value !== null,
  set: (open) => { if (!open) sendConfirmId.value = null; },
});
const quickLogOpen = computed({
  get: () => quickLogProposal.value !== null,
  set: (open) => { if (!open) quickLogProposal.value = null; },
});

function handleBulkAction(action) {
  const ids = [...selectedIds.value];
  if (action === 'resend' && selectedResendWithoutMessage.value.length) {
    const first = selectedResendWithoutMessage.value[0];
    notify.warning({
      title: 'Hay propuestas sin mensaje personalizado.',
      detail: 'Completa cada mensaje en la pestaña Correos antes del reenvío masivo.',
      action: {
        label: 'Completar primero',
        handler: () => router.push(localePath(`/panel/proposals/${first.id}/edit?tab=emails`)),
      },
    });
    return;
  }
  const labels = { delete: 'eliminar', expire: 'expirar', resend: 're-enviar' };
  requestConfirm({
    title: `${(labels[action] || action).charAt(0).toUpperCase() + (labels[action] || action).slice(1)} propuestas`,
    message: `¿${labels[action] || action} ${ids.length} propuesta(s)?`,
    variant: action === 'delete' ? 'danger' : 'warning',
    confirmText: labels[action] || action,
    onConfirm: async () => {
      isBulkActing.value = true;
      const result = await proposalStore.bulkAction(ids, action);
      if (result.success) {
        clearSelection();
        proposalStore.fetchProposals();
      }
      isBulkActing.value = false;
    },
  });
}

const bulkActionItems = computed(() => [
  {
    label: 'Re-enviar',
    disabled: isBulkActing.value || selectedResendWithoutMessage.value.length > 0,
    description: selectedResendWithoutMessage.value.length
      ? 'Completa el mensaje personalizado de todas las propuestas seleccionadas.'
      : (isBulkActing.value ? 'Otra acción masiva está en curso.' : ''),
    onClick: () => handleBulkAction('resend'),
  },
  { label: 'Expirar', disabled: isBulkActing.value, description: isBulkActing.value ? 'Otra acción masiva está en curso.' : '', onClick: () => handleBulkAction('expire') },
  { divider: true },
  { label: 'Eliminar', danger: true, disabled: isBulkActing.value, description: isBulkActing.value ? 'Otra acción masiva está en curso.' : '', onClick: () => handleBulkAction('delete') },
]);

const ZOMBIE_TYPES = ['zombie', 'zombie_draft', 'zombie_sent_stale'];
// Closed deals (accepted) and wrapped-up projects (finished) never "need attention".
const CLOSED_STATUSES = ['accepted', 'finished'];
const proposalStatusById = computed(() => {
  const map = new Map();
  for (const proposal of proposals.value) {
    map.set(proposal.id, proposal.status);
  }
  return map;
});
const zombieAlerts = computed(() =>
  alerts.value.filter(a => ZOMBIE_TYPES.includes(a.alert_type))
);
const activeAlerts = computed(() =>
  alerts.value.filter((a) => {
    if (ZOMBIE_TYPES.includes(a.alert_type)) return false;
    if (CLOSED_STATUSES.includes(proposalStatusById.value.get(a.id))) return false;
    if (!a.manual_alert_id && dismissedComputedAlertKeys.value.has(getComputedAlertKey(a))) return false;
    return true;
  })
);
const PRIORITY_WEIGHT = { critical: 3, high: 2, normal: 1 };
const groupedActiveAlerts = computed(() => {
  const grouped = new Map();
  for (const alert of activeAlerts.value) {
    const groupKey = getClientGroupKey(alert);
    if (!grouped.has(groupKey)) {
      grouped.set(groupKey, {
        key: groupKey,
        client_name: alert.client_name || 'Sin cliente',
        alerts: [],
      });
    }
    grouped.get(groupKey).alerts.push(alert);
  }

  return Array.from(grouped.values()).map((group) => {
    const priority = group.alerts.reduce(
      (best, alert) => ((PRIORITY_WEIGHT[alert.priority] || 0) > (PRIORITY_WEIGHT[best] || 0) ? alert.priority : best),
      'normal',
    );
    const primaryAlert = group.alerts[0];

    const proposalsMap = new Map();
    for (const alert of group.alerts) {
      if (alert.id == null) continue;
      if (!proposalsMap.has(alert.id)) {
        proposalsMap.set(alert.id, { id: alert.id, title: alert.title || 'Sin título', alerts: [] });
      }
      proposalsMap.get(alert.id).alerts.push({ ...alert, icon: alertIcon(alert.alert_type) });
    }
    const proposals = Array.from(proposalsMap.values());

    const proposalTitles = proposals.map(p => p.title).filter(t => t !== 'Sin título');
    const MAX_SUBTITLE_TITLES = 3;
    const subtitle = proposalTitles.length === 0
      ? 'Sin título'
      : proposalTitles.length <= MAX_SUBTITLE_TITLES
        ? proposalTitles.join(', ')
        : `${proposalTitles.slice(0, MAX_SUBTITLE_TITLES).join(', ')} +${proposalTitles.length - MAX_SUBTITLE_TITLES}`;

    return {
      ...group,
      icon: alertIcon(primaryAlert.alert_type),
      subtitle,
      priority,
      proposals,
      isMulti: proposals.length > 1,
      firstProposalId: primaryAlert.id,
      message: group.alerts.length > 1
        ? `${group.alerts.length} alertas en ${proposals.length || group.alerts.length} propuesta(s).`
        : primaryAlert.message,
      refDate: resolveAlertDate(primaryAlert),
    };
  });
});

function getComputedAlertKey(alert) {
  return `${alert.id}-${alert.alert_type}-${resolveAlertDate(alert)}`;
}

function getClientGroupKey(alert) {
  const normalizedName = (alert.client_name || '').trim().toLowerCase();
  if (normalizedName) return `client:${normalizedName}`;
  return `proposal:${alert.id}`;
}

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortKey.value = key;
    sortDir.value = 'desc';
  }
  currentPage.value = 1;
}

function effectiveInvestmentTotal(proposal) {
  const val = proposal?.effective_total_investment;
  return Number(val != null && val !== '' ? val : proposal?.total_investment) || 0;
}

const filteredProposals = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  let list = applyFilters(proposals.value).filter((p) => {
    if (q && !(
      (p.title || '').toLowerCase().includes(q) ||
      (p.client_name || '').toLowerCase().includes(q) ||
      (p.client_email || '').toLowerCase().includes(q)
    )) return false;
    return true;
  });
  // Sort
  const sk = sortKey.value;
  const isNumericSort = sk === 'total_investment';
  const asc = sortDir.value === 'asc';
  list.sort((a, b) => {
    let va = a[sk];
    let vb = b[sk];
    if (isNumericSort) {
      va = effectiveInvestmentTotal(a);
      vb = effectiveInvestmentTotal(b);
    }
    else { va = va || ''; vb = vb || ''; }
    if (va < vb) return asc ? -1 : 1;
    if (va > vb) return asc ? 1 : -1;
    return 0;
  });
  return list;
});

const totalPages = computed(() => Math.ceil(filteredProposals.value.length / pageSize));
const paginatedProposals = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredProposals.value.slice(start, start + pageSize);
});
const rangeFrom = computed(() => (filteredProposals.value.length === 0 ? 0 : (currentPage.value - 1) * pageSize + 1));
const rangeTo = computed(() => Math.min(currentPage.value * pageSize, filteredProposals.value.length));

function goToPage(page) {
  currentPage.value = Math.min(Math.max(1, page), totalPages.value);
}

function formatAlertDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('es', { day: 'numeric', month: 'short', year: d.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined });
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const d = new Date(dateStr);
  const diffMs = now - d;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'ahora';
  if (mins < 60) return `hace ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `hace ${days}d`;
  return d.toLocaleDateString();
}


const proposalActions = computed(() => {
  const p = actionsModalProposal.value;
  if (!p) return [];
  const actions = [];

  actions.push({
    key: 'edit',
    action: 'edit',
    label: 'Editar propuesta',
    info: 'Abre el editor para modificar secciones, precios y contenido de la propuesta.',
    // Con prefijo de idioma: i18n corre con strategy 'prefix', así que una ruta
    // sin prefijo no existe. Antes daba igual porque el enlace nunca llegaba a
    // resolverse; ahora sí navega.
    to: proposalHref(p.id),
    bgClass: 'bg-surface-raised',
    textClass: 'text-text-default',
    onClick: () => { actionsModalProposal.value = null; },
  });

  // Un <a target="_blank"> de verdad, no un botón que llame a window.open: la
  // acción existe también en pantallas táctiles, donde ctrl+clic no está.
  actions.push({
    key: 'edit-new-tab',
    action: 'open-external',
    label: 'Abrir en pestaña nueva',
    info: 'Abre el editor en otra pestaña, sin salir del listado. Igual que ctrl/cmd + clic sobre la fila.',
    href: proposalHref(p.id),
    bgClass: 'bg-surface-raised',
    textClass: 'text-text-default',
    onClick: () => { actionsModalProposal.value = null; },
  });

  actions.push({
    key: 'preview',
    action: 'view',
    label: 'Ver preview',
    info: 'Abre la propuesta tal como la ve el cliente, sin registrar vistas.',
    href: `/proposal/${p.slug || p.uuid}?preview=1`,
    bgClass: 'bg-primary-soft text-text-brand',
    textClass: 'text-text-brand',
  });

  if (p.status === 'draft') {
    actions.push({
      key: 'send',
      action: 'send',
      label: 'Enviar al cliente',
      info: 'Envía un email al cliente con el enlace de la propuesta. Cambia el estado a "enviada".',
      bgClass: 'bg-info-soft text-info-strong',
      textClass: 'text-info-strong',
      onClick: () => { actionsModalProposal.value = null; handleSend(p.id); },
    });
  }

  if (['sent', 'viewed'].includes(p.status)) {
    actions.push({
      key: 'resend',
      action: 'resend',
      label: 'Re-enviar email',
      info: 'Envía nuevamente el email al cliente. Mantiene la misma fecha de expiración.',
      bgClass: 'bg-info-soft text-info-strong',
      textClass: 'text-info-strong',
      onClick: () => { actionsModalProposal.value = null; handleResend(p.id); },
    });
  }

  actions.push({
    key: 'copy',
    action: 'copy',
    label: copiedId.value === p.id ? '¡Enlace copiado!' : 'Copiar enlace',
    info: 'Copia el enlace público de la propuesta al portapapeles para compartir manualmente.',
    bgClass: copiedId.value === p.id ? 'bg-primary-soft text-text-brand ' : 'bg-surface-raised',
    textClass: copiedId.value === p.id ? 'text-text-brand' : 'text-text-default',
    onClick: () => { handleCopyLink(p); },
  });

  actions.push({
    key: 'whatsapp',
    action: 'message',
    label: 'Enviar por WhatsApp',
    info: 'Abre WhatsApp con un mensaje pre-escrito incluyendo el enlace de la propuesta.',
    href: buildWhatsAppUrl(p),
    bgClass: 'bg-success-soft text-success-strong',
    textClass: 'text-success-strong',
  });

  actions.push({
    key: 'quick-log',
    action: 'log-activity',
    label: 'Registrar actividad',
    info: 'Registra rápidamente una llamada, reunión o nota sin entrar a la propuesta.',
    bgClass: 'bg-success-soft text-success-strong',
    textClass: 'text-success-strong',
    onClick: () => { actionsModalProposal.value = null; openQuickLog(p); },
  });

  actions.push({
    key: 'duplicate',
    action: 'duplicate',
    label: 'Duplicar propuesta',
    info: 'Crea una copia exacta de esta propuesta para reutilizar con otro cliente.',
    bgClass: 'bg-info-soft text-info-strong',
    textClass: 'text-info-strong',
    onClick: () => { actionsModalProposal.value = null; handleDuplicate(p.id); },
  });

  actions.push({
    key: 'toggle',
    action: p.is_active ? 'deactivate' : 'activate',
    label: p.is_active ? 'Desactivar' : 'Activar',
    info: p.is_active
      ? 'Desactiva la propuesta. El cliente no podrá acceder al enlace.'
      : 'Reactiva la propuesta para que el cliente pueda verla nuevamente.',
    bgClass: p.is_active ? 'bg-warning-soft text-warning-strong' : 'bg-primary-soft text-text-brand ',
    textClass: p.is_active ? 'text-warning-strong' : 'text-text-brand',
    onClick: () => { actionsModalProposal.value = null; handleToggleActive(p.id, p.is_active); },
  });

  actions.push({
    key: 'delete',
    action: 'delete',
    label: 'Eliminar',
    info: 'Elimina permanentemente la propuesta. Esta acción no se puede deshacer.',
    danger: true,
    onClick: () => { actionsModalProposal.value = null; handleDelete(p.id); },
  });

  return actions;
});

const router = useRouter();

// Fuente única de la dirección: la leen el <a> del título de la fila, el de las
// tarjetas zombie, el ítem «Abrir en pestaña nueva» del menú y el atajo de clic.
function proposalHref(id) {
  return localePath(`/panel/proposals/${id}/edit`);
}

function navigateToProposal(id, event) {
  openRow(proposalHref(id), event);
}

// Contract modal for inline negotiation
const showContractModal = ref(false);
const contractModalProposal = ref(null);

// Shared confirm + PATCH + notify flow for the status selects (inline cell
// and actions modal). Natural negotiating opens the contract modal instead.
const { updatingId: updatingStatusId, changeStatus } = useProposalStatusChange({
  requestConfirm,
  onNegotiate: (p) => {
    contractModalProposal.value = p;
    showContractModal.value = true;
  },
  resend: (proposalId) => handleResend(proposalId),
});

// Backward-compatible one-line toast used by simpler call sites (delete, etc.).
// Renders through the global <PanelNotificationHost />.
function showStatusToast(message, type) {
  notify.push({ type: type === 'success' ? 'success' : 'error', title: message });
}

// Contextual action for a failed backend result, based on its error `code`.
function actionForFailure(result, proposalId) {
  if (result?.code === 'missing_client_email' || result?.code === 'invalid_client_email_domain') {
    return { label: 'Editar propuesta', to: localePath(`/panel/proposals/${proposalId}/edit`) };
  }
  return null;
}

// Notify a failed store result using its normalized { message, hint, code }.
function notifyFailure(result, { title, proposalId } = {}) {
  notify.error({
    title: title || result?.message || 'No se pudo completar la acción',
    detail: title ? (result?.message || result?.hint || '') : (result?.hint || ''),
    action: proposalId ? actionForFailure(result, proposalId) : null,
  });
}

// When the status/send succeeded but the client email did not go out, offer a resend.
function notifyEmailFailure(proposalId, emailDelivery, successTitle) {
  notify.warning({
    title: successTitle,
    detail: emailDelivery?.detail
      || 'No se pudo enviar el correo al cliente. Verifica el correo e intenta reenviar.',
    action: { label: 'Reenviar', handler: () => handleResend(proposalId) },
  });
}

async function onStatusSelect(proposal, newStatus) {
  const result = await changeStatus(proposal, newStatus);
  // Stale-state recovery: reload the list when the backend rejected the change.
  if (result && !result.success) proposalStore.fetchProposals();
}

async function handleContractConfirmFromList(params) {
  showContractModal.value = false;
  if (!contractModalProposal.value) return;
  const result = await proposalStore.saveContractAndNegotiate(contractModalProposal.value.id, params);
  if (result.success) {
    proposalStore.fetchProposals();
  }
  contractModalProposal.value = null;
}

const alerts = ref([]);
const proposalDashboardRef = ref(null);

// Notify a load failure once, not on every refresh/poll cycle.
let alertsErrorNotified = false;
async function loadAlerts() {
  const alertResult = await proposalStore.fetchAlerts();
  if (alertResult.success) {
    alerts.value = alertResult.data || [];
    alertsErrorNotified = false;
  } else if (!alertsErrorNotified) {
    alertsErrorNotified = true;
    notify.error({ title: 'No se pudieron cargar las alertas.' });
  }
}

async function refreshData() {
  isRefreshing.value = true;
  try {
    await proposalStore.fetchProposals();
    await loadAlerts();
    // Los KPI del dashboard salen del servidor: sin esto quedaban viejos tras
    // eliminar/mutar (la guarda `fetched` no refetchea sola). Sin await — el
    // spinner de la lista no debe esperar al panel colapsable.
    proposalDashboardRef.value?.refreshIfLoaded();
  } finally {
    isRefreshing.value = false;
  }
}

usePanelRefresh(refreshData);

onMounted(async () => {
  proposalStore.fetchProposals();
  await loadAlerts();
});

const ALERT_ICON_MAP = {
  not_viewed: '👁️‍🗨️', not_responded: '⏳', expiring_soon: '🔥',
  manual_reminder: '🔔', manual_followup: '📩', manual_call: '📞',
  manual_meeting: '🤝', manual_custom: '📝',
  seller_inactive: '🏷️', zombie: '💀', late_return: '🔄',
  manual_discount_suggestion: '💰', discount_suggestion: '💰',
  manual_post_expiration_visit: '🔥🕰️', post_expiration_visit: '🔥🕰️',
  manual_engagement_decay: '📉', engagement_decay: '📉',
  manual_first_view: '👁️',
};
function alertIcon(type) {
  return ALERT_ICON_MAP[type] || '⚠️';
}

function resolveAlertDate(alert) {
  return alert.ref_date || alert.alert_date || '';
}

function alertBorderClass(priority) {
  if (priority === 'critical') return 'border-danger-strong/30 hover:border-danger-strong/60';
  if (priority === 'high') return 'border-warning-strong/30 hover:border-warning-strong/60';
  return 'border-border-default hover:border-focus-ring/40';
}

async function handleCreateAlert() {
  alertError.value = '';
  const payload = {
    proposal: newAlert.proposal,
    alert_type: newAlert.alert_type,
    message: newAlert.message,
    alert_date: newAlert.alert_date
      ? new Date(newAlert.alert_date).toISOString()
      : new Date().toISOString(),
  };
  const result = await proposalStore.createAlert(payload);
  if (result.success) {
    showAlertForm.value = false;
    newAlert.proposal = '';
    newAlert.alert_type = 'reminder';
    newAlert.message = '';
    newAlert.alert_date = '';
    await loadAlerts();
  } else {
    alertError.value = 'Error al crear el recordatorio.';
  }
}

function toggleAlertForm() {
  showAlertForm.value = !showAlertForm.value;
  if (showAlertForm.value) attentionExpanded.value = true;
}

function toggleAlertGroupExpansion(groupKey) {
  const next = new Set(expandedAlertGroups.value);
  if (next.has(groupKey)) next.delete(groupKey);
  else next.add(groupKey);
  expandedAlertGroups.value = next;
}

function openAlertGroup(group, event) {
  if (group.isMulti) {
    toggleAlertGroupExpansion(group.key);
    return;
  }
  openProposalFromAlert(group.firstProposalId, event);
}

function openProposalFromAlert(proposalId, event) {
  if (!proposalId) return;
  navigateToProposal(proposalId, event);
}

async function handleDismissAlertGroup(group) {
  if (!group?.alerts?.length) return;

  const manualIds = [...new Set(group.alerts.map(a => a.manual_alert_id).filter(Boolean))];
  const computedAlertsByKey = new Map();
  for (const alert of group.alerts) {
    if (alert.manual_alert_id) continue;
    computedAlertsByKey.set(getComputedAlertKey(alert), alert);
  }
  const computedAlerts = [...computedAlertsByKey.values()];

  const [manualResults, computedResults] = await Promise.all([
    Promise.allSettled(manualIds.map(id => proposalStore.dismissAlert(id))),
    Promise.allSettled(computedAlerts.map(alert =>
      proposalStore.dismissAlert(alert.id, {
        computed_alert_type: alert.alert_type,
        ref_date: resolveAlertDate(alert),
      })
    )),
  ]);

  const dismissedIds = manualIds.filter((_, idx) => manualResults[idx]?.status === 'fulfilled' && manualResults[idx].value?.success);
  if (dismissedIds.length) {
    alerts.value = alerts.value.filter(a => !dismissedIds.includes(a.manual_alert_id));
  }

  const computedKeys = computedAlerts
    .filter((_, idx) => computedResults[idx]?.status === 'fulfilled' && computedResults[idx].value?.success)
    .map(getComputedAlertKey);
  if (computedKeys.length) {
    const next = new Set(dismissedComputedAlertKeys.value);
    computedKeys.forEach(k => next.add(k));
    dismissedComputedAlertKeys.value = next;
  }
}

function toggleFilterPanel() {
  isFilterPanelOpen.value = !isFilterPanelOpen.value;
}

function handleCreateTab(name) {
  saveTab(name);
  isFilterPanelOpen.value = true;
}

function handleResetFilters() {
  resetFilters();
  isFilterPanelOpen.value = false;
}

function handleSend(id) {
  const proposal = proposals.value.find((item) => item.id === id);
  if (proposal && !(proposal.email_intro || '').trim()) {
    notify.warning({
      title: 'Falta el mensaje personalizado del correo.',
      detail: 'Escribe qué resuelve la propuesta antes de enviarla.',
      action: {
        label: 'Ir a Correos',
        handler: () => router.push(localePath(`/panel/proposals/${id}/edit?tab=emails`)),
      },
    });
    return;
  }
  sendConfirmId.value = id;
}

async function confirmSend() {
  if (!sendConfirmId.value) return;
  isSending.value = true;
  try {
    const proposalId = sendConfirmId.value;
    const result = await proposalStore.sendProposal(proposalId);
    sendConfirmId.value = null;
    proposalStore.fetchProposals();
    if (result.success) {
      const ed = result.email_delivery;
      if (ed && ed.ok === false) {
        notifyEmailFailure(proposalId, ed, 'Propuesta marcada como enviada');
      } else {
        notify.success({ title: 'Propuesta enviada al cliente' });
      }
    } else {
      notifyFailure(result, { title: 'No se pudo enviar la propuesta', proposalId });
    }
  } finally {
    isSending.value = false;
  }
}

function handleResend(id) {
  resendModalProposal.value = proposals.value.find((proposal) => proposal.id === id) || null;
}

function handleResendComplete(result) {
  const proposalId = resendModalProposal.value?.id;
  proposalStore.fetchProposals();
  const ed = result.email_delivery;
  if (ed && ed.ok === false) {
    notifyEmailFailure(proposalId, ed, 'Reenvío registrado');
  } else {
    notify.success({ title: 'Propuesta re-enviada al cliente' });
  }
}

function handleToggleActive(id, currentlyActive) {
  const label = currentlyActive ? 'desactivar' : 'activar';
  requestConfirm({
    title: `${label.charAt(0).toUpperCase() + label.slice(1)} propuesta`,
    message: `¿${label.charAt(0).toUpperCase() + label.slice(1)} esta propuesta?`,
    variant: 'warning',
    confirmText: label.charAt(0).toUpperCase() + label.slice(1),
    onConfirm: () => proposalStore.toggleProposalActive(id),
  });
}

async function handleDuplicate(id) {
  const result = await proposalStore.duplicateProposal(id);
  if (result.success) {
    router.push(localePath(`/panel/proposals/${result.data.id}/edit`));
  }
}

function handleCopyLink(p) {
  const url = `${window.location.origin}/proposal/${p.slug || p.uuid}`;
  navigator.clipboard.writeText(url).then(() => {
    copiedId.value = p.id;
    setTimeout(() => { copiedId.value = null; }, 1500);
  });
}

function handleDelete(id) {
  requestConfirm({
    title: 'Eliminar propuesta',
    message: 'Esto eliminará la propuesta de forma permanente. Esta acción no se puede deshacer.',
    variant: 'danger',
    confirmText: 'Eliminar',
    cancelText: 'Cancelar',
    requireTypeText: 'DELETE',
    onConfirm: async () => {
      const result = await proposalStore.deleteProposal(id);
      if (result.success) {
        await refreshData();
        showStatusToast('Propuesta eliminada.', 'success');
      } else {
        showStatusToast(
          result.error || 'No se pudo eliminar la propuesta.',
          'error',
        );
      }
    },
  });
}

function isInactive(p) {
  if (!['sent', 'viewed'].includes(p.status)) return false;
  const ref = p.last_activity_at || p.sent_at || p.created_at;
  if (!ref) return false;
  return (Date.now() - new Date(ref).getTime()) / 86400000 >= 3;
}

function inactiveDays(p) {
  const ref = p.last_activity_at || p.sent_at || p.created_at;
  if (!ref) return 0;
  return Math.floor((Date.now() - new Date(ref).getTime()) / 86400000);
}

function heatScoreColor(score) {
  if (score >= 8) return 'bg-red-500';
  if (score >= 5) return 'bg-orange-400';
  if (score >= 2) return 'bg-yellow-400 text-text-default';
  return 'bg-surface-raised text-text-default';
}

function formatInvestmentTime(seconds) {
  if (!seconds || seconds === 0) return '0s';
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function sectionLabel(sectionType) {
  const labels = {
    investment: 'Inversión',
    timeline: 'Timeline',
    functional_requirements: 'Requerimientos',
    final_note: 'Nota final',
  };
  return labels[sectionType] || sectionType;
}

function openQuickLog(p) {
  quickLogProposal.value = p;
  quickLogType.value = 'call';
  quickLogMessage.value = '';
  quickLogError.value = '';
}

async function confirmQuickLog() {
  if (!quickLogProposal.value) return;
  if (!quickLogMessage.value.trim()) {
    quickLogError.value = 'Escribe la descripción de la actividad.';
    return;
  }
  isQuickLogging.value = true;
  try {
    await proposalStore.logActivity(quickLogProposal.value.id, {
      change_type: quickLogType.value,
      description: quickLogMessage.value.trim(),
    });
    quickLogProposal.value = null;
    proposalStore.fetchProposals();
  } finally {
    isQuickLogging.value = false;
  }
}

function buildWhatsAppUrl(p) {
  const url = `${window.location.origin}/proposal/${p.slug || p.uuid}`;
  const phone = (p.client_phone || '').replace(/\D/g, '');
  const msg = encodeURIComponent(
    `Hola ${p.client_name}, te comparto la propuesta "${p.title}": ${url}\n\n¿Tienes alguna pregunta?`
  );
  return phone
    ? `https://wa.me/${phone}?text=${msg}`
    : `https://wa.me/?text=${msg}`;
}
</script>

<style scoped>
.fade-modal-enter-active,
.fade-modal-leave-active {
  transition: opacity 0.2s ease;
}
.fade-modal-enter-from,
.fade-modal-leave-to {
  opacity: 0;
}
</style>
