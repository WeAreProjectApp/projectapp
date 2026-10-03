<template>
  <div :class="PAGE_MAX_WIDTH" data-testid="clients-page">
    <ProposalApprovalModal
      :visible="Boolean(approvalProposal)"
      :proposal="approvalProposal || {}"
      :accept-proposal="approvalAccept"
      @close="approvalProposal = null"
      @completed="handleClientApprovalCompleted"
    />
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Clientes</h1>
        <p class="text-sm text-text-subtle mt-1">
          Perfiles de clientes para propuestas y plataforma. Los huérfanos pueden eliminarse.
        </p>
      </div>
      <BaseButton
        variant="primary"
        size="md"
        data-testid="clients-new-button"
        @click="openCreateModal"
      >
        <BaseActionIcon action="create" />
        <span>Nuevo cliente</span>
      </BaseButton>
    </div>

    <!-- Level 1: business module. It groups the subfilters below; the cut
         itself happens at level 2. -->
    <ClientModuleTabs
      v-if="!isCompact"
      :model-value="activeModule"
      @update:model-value="selectModule"
    >
      <template #trailing>
        <!-- design-tokens: allow-raw-button -->
        <button
          data-testid="clients-tab-config"
          :class="[
            'ml-auto px-4 py-2 rounded-xl text-sm font-medium transition-colors',
            isConfigOpen
              ? 'bg-primary text-white'
              : 'bg-surface-raised text-text-muted hover:bg-border-muted',
          ]"
          @click="isConfigOpen = !isConfigOpen"
        >
          Configuraciones
        </button>
      </template>
    </ClientModuleTabs>

    <!-- Settings tab replaces the list area -->
    <BaseButton
      v-if="isCompact && isConfigOpen"
      variant="secondary"
      kind="form"
      class="mb-4 w-full"
      @click="isConfigOpen = false"
    >
      Volver al listado de clientes
    </BaseButton>

    <ViewSettingsPanel
      v-if="isConfigOpen"
      :filter-views="[{ value: 'client', label: 'Clientes' }]"
      @reset="reloadFilterTabs"
    >
      <section class="bg-surface border border-border-muted rounded-xl shadow-sm p-5 sm:p-6">
        <h2 class="text-lg font-bold text-text-default mb-1">Defaults del panel</h2>
        <p class="text-sm text-text-muted mb-4">
          Los valores por defecto de propuestas y diagnósticos (que afectan a
          los clientes) se administran en el panel de defaults.
        </p>
        <BaseButton as="NuxtLink" variant="secondary" size="sm" :to="localePath('/panel/defaults')">
          Abrir defaults
        </BaseButton>
      </section>
    </ViewSettingsPanel>

    <template v-if="!isConfigOpen">
    <!-- Level 2: the subfilters of the selected module, plus its saved tabs -->
    <ProposalFilterTabs
      v-if="!isCompact"
      :tabs="displayTabs"
      :active-tab-id="filterTabId"
      :counts="subfilterCounts"
      :is-tab-limit-reached="isTabLimitReached"
      count-title="Clientes que cumplen este filtro"
      @select="onSelectFilterTab"
      @create="handleCreateFilterTab"
      @rename="renameFilterTab"
      @delete="deleteFilterTab"
      @restore="restoreFilterTab"
      @rebase="rebaseFilterTab"
      @reorder="reorderFilterTabs"
    />

    <!-- Search + client status + Filter toggle. Status sits here, next to the
         search box, because it qualifies the register itself and combines with
         any module rather than competing with them for the row above. -->
    <div class="flex flex-wrap items-center gap-2 mb-5">
      <BaseInput
        v-model="search"
        type="text"
        placeholder="Buscar por nombre, email o empresa..."
        data-testid="clients-search-input"
        class="w-full sm:max-w-xs"
        @input="onSearchInput"
      />
      <BaseButton
        v-if="isCompact"
        variant="secondary"
        size="md"
        class="w-full justify-between panel-portrait:w-auto"
        data-testid="clients-mobile-filters"
        aria-haspopup="dialog"
        :aria-expanded="showMobileFilters"
        @click="showMobileFilters = true"
      >
        <span class="min-w-0 truncate">{{ mobileFilterSummary }}</span>
        <BaseBadge v-if="mobileFilterCount" variant="primary" size="sm">
          {{ mobileFilterCount }}
        </BaseBadge>
      </BaseButton>
      <BaseSegmented
        v-else
        :model-value="clientStatus"
        :options="clientStatusOptions"
        size="sm"
        data-testid="clients-status-selector"
        @update:model-value="setClientStatus"
      />
      <UiFilterToggleButton
        v-if="!isCompact"
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        data-testid="clients-filter-toggle"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
    </div>

    <!-- Filter panel -->
    <ClientFilterPanel
      v-if="!isCompact"
      :model-value="currentFilters"
      :is-open="isFilterPanelOpen"
      :filter-count="activeFilterCount"
      @update:model-value="onFiltersUpdate"
      @reset="handleResetFilters"
    />

    <!-- Loading -->
    <div v-if="clientsStore.isLoading" class="text-center py-16 text-text-subtle text-sm">
      Cargando clientes...
    </div>

    <!-- Empty -->
    <div
      v-else-if="filteredClients.length === 0"
      class="text-center py-16 text-text-subtle text-sm"
    >
      {{ search || hasActiveFilters ? 'No se encontraron clientes con ese criterio.' : 'No hay clientes aún.' }}
    </div>

    <!-- Client list -->
    <div v-else class="space-y-3">
      <div
        v-for="client in pagedClients"
        :key="client.id"
        :data-testid="`client-row-${client.id}`"
        class="bg-surface rounded-xl shadow-sm border border-border-muted overflow-hidden"
      >
        <!-- Client row header (drop target for proposal/diagnostic reassignment) -->
        <div
          :data-testid="`client-header-${client.id}`"
          class="px-5 py-4 flex flex-col sm:flex-row sm:flex-wrap sm:items-center sm:justify-between gap-3 cursor-pointer hover:bg-surface-raised transition-colors"
          :class="{ 'ring-2 ring-inset ring-focus-ring bg-primary-soft': dragOverClientId === client.id }"
          @click="toggleClient(client)"
          @dragover="onClientDragOver($event, client)"
          @dragleave="onClientDragLeave(client)"
          @drop.prevent="onClientDrop(client)"
        >
          <div class="flex items-center gap-4 flex-1 min-w-0 w-full sm:w-auto">
            <!-- Avatar -->
            <div
              class="w-10 h-10 rounded-full bg-primary-soft flex items-center justify-center flex-shrink-0"
            >
              <span class="text-text-brand font-bold text-sm">{{ initials(client.name) }}</span>
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <p
                  class="min-w-0 max-w-full text-sm font-semibold text-text-default"
                  :class="isCompact ? 'whitespace-normal [overflow-wrap:anywhere]' : 'truncate'"
                  :title="client.name"
                >{{ client.name }}</p>
                <span class="text-xs text-text-subtle tabular-nums">#{{ client.id }}</span>
                <span
                  v-if="client.is_email_placeholder"
                  class="text-[10px] px-1.5 py-0.5 rounded-full bg-warning-soft text-warning-strong font-medium uppercase tracking-wide"
                  title="Email pendiente — automatizaciones de correo pausadas para este cliente"
                >
                  📧 placeholder
                </span>
                <span
                  v-if="client.is_orphan"
                  class="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-raised text-text-muted font-medium uppercase tracking-wide"
                  title="Sin propuestas, proyectos, diagnósticos, ingresos ni hostings — puede eliminarse"
                >
                  Huérfano
                </span>
                <span
                  v-if="client.is_archived"
                  class="text-[10px] px-1.5 py-0.5 rounded-full bg-warning-soft text-warning-strong font-medium uppercase tracking-wide"
                  title="Cliente archivado — oculto de los demás tabs"
                >
                  Archivado
                </span>
              </div>
              <p
                class="mt-0.5 min-w-0 max-w-full text-xs text-text-subtle"
                :class="isCompact ? 'whitespace-normal [overflow-wrap:anywhere]' : 'truncate'"
                :title="client.company
                  ? `${client.is_email_placeholder ? 'Email pendiente' : client.email} · ${client.company}`
                  : (client.is_email_placeholder ? 'Email pendiente' : client.email)"
              >
                {{ client.is_email_placeholder ? 'Email pendiente' : client.email }}
                <span v-if="client.company" class="text-text-subtle">· {{ client.company }}</span>
              </p>
            </div>
          </div>

          <div v-if="isCompact" class="w-full">
            <dl class="grid grid-cols-3 gap-2 rounded-lg bg-surface-muted p-3 text-center">
              <div>
                <dt class="text-2xs uppercase tracking-wide text-text-subtle">Propuestas</dt>
                <dd class="mt-1 text-sm font-semibold tabular-nums text-text-default">{{ client.total_proposals }}</dd>
              </div>
              <div>
                <dt class="text-2xs uppercase tracking-wide text-text-subtle">Proyectos</dt>
                <dd class="mt-1 text-sm font-semibold tabular-nums text-text-default">{{ client.projects_count }}</dd>
              </div>
              <div>
                <dt class="text-2xs uppercase tracking-wide text-text-subtle">Diagnósticos</dt>
                <dd class="mt-1 text-sm font-semibold tabular-nums text-text-default">{{ client.diagnostics_count }}</dd>
              </div>
            </dl>
            <div class="mt-3 flex items-center justify-between gap-2">
              <span class="min-w-0 max-w-full text-xs font-medium text-text-muted [overflow-wrap:anywhere]">
                {{ compactContextLabel(client) }}
              </span>
              <div class="flex shrink-0 items-center gap-2">
                <BaseButton
                  variant="secondary"
                  size="md"
                  class="min-h-11"
                  :data-testid="`client-actions-${client.id}`"
                  :aria-label="`Acciones de ${client.name}`"
                  @click.stop="openClientActions(client)"
                >
                  Acciones
                </BaseButton>
                <BaseActionIcon
                  :action="expandedClients.has(client.id) ? 'collapse' : 'expand'"
                  class="h-5 w-5 text-text-subtle"
                />
              </div>
            </div>
          </div>

          <div v-else class="flex items-center justify-end gap-3 flex-shrink-0 w-full sm:w-auto">
            <!-- Stats pills -->
            <span
              class="text-xs px-2.5 py-1 rounded-full bg-surface-raised text-text-muted font-medium"
            >
              {{ client.total_proposals }} propuesta{{ client.total_proposals !== 1 ? 's' : '' }}
            </span>

            <!-- Hosting count, only while a hosting preset is applied. Doubles
                 as the jump into Hostings already filtered by this client. -->
            <!-- design-tokens: allow-raw-button -->
            <button
              v-if="showsHostingCount(client) && canOpenHostings"
              type="button"
              :data-testid="`client-hostings-${client.id}`"
              class="text-xs px-2.5 py-1 rounded-full bg-info-soft text-info-strong font-medium hover:bg-primary-soft transition-colors"
              :title="`Ver los hostings de ${client.name} en Contabilidad`"
              @click.stop="goToClientHostings(client)"
            >
              {{ client.hostings_count }} hosting{{ client.hostings_count !== 1 ? 's' : '' }}
            </button>
            <span
              v-else-if="showsHostingCount(client)"
              :data-testid="`client-hostings-${client.id}`"
              class="text-xs px-2.5 py-1 rounded-full bg-info-soft text-info-strong font-medium"
            >
              {{ client.hostings_count }} hosting{{ client.hostings_count !== 1 ? 's' : '' }}
            </span>

            <!-- Documentos: cuántos tiene + fecha del último, sólo con el
                 módulo activo. Salta al gestor ya filtrado por el cliente.
                 Sin gate de superuser: documentos comparte el gate admin de
                 esta misma página. -->
            <!-- design-tokens: allow-raw-button -->
            <button
              v-if="documentsPillFor(client)"
              type="button"
              :data-testid="`${documentsPillFor(client).testid}-${client.id}`"
              class="text-xs px-2.5 py-1 rounded-full bg-info-soft text-info-strong font-medium hover:bg-primary-soft transition-colors"
              :title="`Ver los documentos de ${client.name}`"
              @click.stop="goToClientDocuments(client)"
            >
              {{ documentsPillFor(client).label }}<span v-if="documentsPillFor(client).showsDate && client.last_document_at"> · {{ formatDate(client.last_document_at) }}</span>
            </button>

            <!-- El histórico conversacional vive en su propio módulo y esta
                 relación es el acceso inverso desde el cliente. -->
            <NuxtLink
              v-if="Number(client.communications_count || 0) > 0"
              :to="{ path: '/panel/communications', query: { client: String(client.id) } }"
              :data-testid="`client-communications-${client.id}`"
              class="text-xs px-2.5 py-1 rounded-full bg-primary-soft text-text-brand font-medium hover:opacity-80 transition-opacity"
              :title="`Ver las comunicaciones de ${client.name}`"
              @click.stop
            >
              {{ client.communications_count }} hilo{{ client.communications_count !== 1 ? 's' : '' }}
              <template v-if="client.last_communication_at"> · {{ formatDate(client.last_communication_at) }}</template>
            </NuxtLink>

            <!-- Emails: the count plus when we last wrote, which is what turns
                 the list into a reading of contact and not just a filter.
                 Opens the same modal the ficha does. -->
            <!-- design-tokens: allow-raw-button -->
            <button
              v-if="showsEmailCount(client)"
              type="button"
              :data-testid="`client-emails-${client.id}`"
              class="text-xs px-2.5 py-1 rounded-full bg-info-soft text-info-strong font-medium hover:bg-primary-soft transition-colors"
              :title="`Ver los correos de ${client.name}`"
              @click.stop="openEmails(client)"
            >
              {{ client.emails_sent_count }} correo{{ client.emails_sent_count !== 1 ? 's' : '' }}
              <template v-if="client.last_email_at"> · {{ formatDate(client.last_email_at) }}</template>
            </button>

            <BaseActionButton
              v-if="client.accepted_count > 0"
              action="open-platform"
              label="Ver cliente en plataforma"
              :data-testid="`client-platform-${client.id}`"
              class="p-1.5 rounded-lg text-text-subtle hover:text-text-brand hover:bg-primary-soft transition-colors"
              :disabled="isBridging"
              @click.stop="goToPlatform('/platform/clients/' + client.user_id)"
            />

            <!-- Edit button -->
            <BaseActionButton
              action="edit"
              label="Editar cliente"
              :data-testid="`client-edit-${client.id}`"
              class="p-1.5 rounded-lg text-text-subtle hover:text-text-brand hover:bg-primary-soft transition-colors"
              @click.stop="openEditModal(client)"
            />

            <!-- Archive toggle button -->
            <BaseActionButton
              :action="client.is_archived ? 'restore' : 'archive'"
              :label="client.is_archived ? 'Desarchivar cliente' : 'Archivar cliente'"
              :tooltip="client.is_archived ? 'Desarchivar' : 'Archivar'"
              :data-testid="`client-toggle-archived-${client.id}`"
              class="p-1.5 rounded-lg text-text-subtle hover:text-warning-strong hover:bg-warning-soft transition-colors"
              @click.stop="openArchiveModal(client)"
            />

            <!-- Trash button -->
            <BaseActionButton
              action="delete"
              label="Eliminar cliente"
              variant="danger-ghost"
              size="sm"
              :data-testid="`client-delete-${client.id}`"
              @click.stop="confirmDelete(client)"
            />

            <!-- Expand chevron -->
            <BaseActionIcon
              :action="expandedClients.has(client.id) ? 'collapse' : 'expand'"
              class="text-text-subtle"
            />
          </div>
        </div>

        <!-- Expanded: proposals, projects, and diagnostics -->
        <div
          v-if="expandedClients.has(client.id)"
          class="border-t border-border-muted bg-surface-raised"
        >
          <div v-if="loadingDetails.has(client.id)" class="px-5 py-4 text-sm text-text-subtle">
            Cargando...
          </div>
          <template v-else>
            <!-- Reachable without going through the filter: filtering is for
                 finding who, the ficha is where you already are when the
                 question "what did we send them?" comes up. -->
            <div class="px-5 pt-4 flex flex-wrap justify-end gap-2">
              <BaseButton
                variant="secondary"
                size="sm"
                :data-testid="`client-view-communications-${client.id}`"
                @click.stop="goToClientCommunications(client)"
              >
                Ver comunicaciones
              </BaseButton>
              <BaseButton
                variant="secondary"
                size="sm"
                :data-testid="`client-view-emails-${client.id}`"
                @click.stop="openEmails(client)"
              >
                Ver correos
              </BaseButton>
            </div>

            <EntityHistorySection entity-type="client" :object-id="client.id" class="mx-5" />
            <!-- Proposals (drop target for proposal reassignment) -->
            <div
              :data-testid="`client-proposals-zone-${client.id}`"
              :class="{ 'ring-2 ring-inset ring-focus-ring bg-primary-soft': dragOverZoneKey === `${client.id}:proposal` }"
              @dragover="onZoneDragOver($event, client, 'proposal')"
              @dragleave="onZoneDragLeave($event, client, 'proposal')"
              @drop.prevent="onZoneDrop(client, 'proposal')"
            >
              <div class="px-5 pt-4 pb-1">
                <p class="text-xs font-semibold text-text-subtle uppercase tracking-wider mb-2">Propuestas</p>
              </div>
              <div
                v-if="(detailCache[client.id]?.proposals || []).length === 0"
                class="px-5 pb-4 text-sm text-text-subtle"
              >
                Sin propuestas.
              </div>
              <div v-else :class="isCompact ? 'overflow-visible' : 'overflow-x-auto'">
                <table class="w-full text-sm" :class="isCompact ? 'client-detail-cards' : 'min-w-[600px]'">
                  <thead>
                    <tr
                      class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider"
                    >
                      <th class="px-5 py-3">Propuesta</th>
                      <th class="px-4 py-3">Estado</th>
                      <th class="px-4 py-3">Inversión</th>
                      <th class="px-4 py-3 text-center">Vistas</th>
                      <th class="px-4 py-3">Enviada</th>
                      <th class="px-4 py-3 text-right">Acciones</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border-muted">
                    <tr
                      v-for="p in detailCache[client.id].proposals"
                      :key="p.id"
                      :draggable="!isCompact"
                      :data-testid="`client-proposal-row-${p.id}`"
                      class="hover:bg-surface-raised transition-colors bg-surface cursor-grab active:cursor-grabbing select-none"
                      :class="{ 'opacity-50': draggingItem?.type === 'proposal' && draggingItem?.id === p.id }"
                      @dragstart="onRowDragStart($event, client, 'proposal', p)"
                      @dragend="onRowDragEnd"
                    >
                      <td class="px-5 py-3" data-label="Propuesta" data-card-full>
                        <NuxtLink
                          :to="localePath(`/panel/proposals/${p.id}/edit`)"
                          draggable="false"
                          class="block min-w-0 max-w-[22rem] whitespace-normal font-medium text-text-default [overflow-wrap:anywhere] hover:text-text-brand transition-colors"
                          :title="p.title"
                        >
                          {{ p.title }}
                        </NuxtLink>
                      </td>
                      <td class="px-4 py-3" data-label="Estado">
                        <ProposalStatusSelect
                          :proposal="p"
                          :updating="updatingProposalStatusId === p.id"
                          @change="(s) => onProposalStatusSelect(client, p, s)"
                        />
                        <BaseButton
                          v-if="p.project_review_required"
                          variant="link"
                          size="sm"
                          :data-testid="`client-approval-review-${p.id}`"
                          @click.stop="openClientApproval(client, p, false)"
                        >
                          {{ approvalText.pending }}
                        </BaseButton>
                      </td>
                      <td class="px-4 py-3 text-text-muted/60 tabular-nums" data-label="Inversión">
                        ${{ Number(p.total_investment).toLocaleString() }} {{ p.currency }}
                      </td>
                      <td class="px-4 py-3 text-center text-text-muted/60" data-label="Vistas">{{ p.view_count }}</td>
                      <td class="px-4 py-3 text-text-muted text-xs" data-label="Enviada">
                        {{ p.sent_at ? formatDate(p.sent_at) : '—' }}
                      </td>
                      <td class="px-4 py-3 text-right" data-label="Acciones" data-card-full>
                        <BaseButton
                          v-if="isCompact"
                          variant="secondary"
                          size="sm"
                          :data-testid="`client-proposal-move-${p.id}`"
                          @click.stop="openTouchReassign(client, 'proposal', p)"
                        >
                          Mover
                        </BaseButton>
                        <BaseActionButton
                          action="delete"
                          label="Eliminar propuesta"
                          variant="danger-ghost"
                          size="sm"
                          :class="isCompact ? 'min-h-11 min-w-11' : ''"
                          :data-testid="`client-proposal-delete-${p.id}`"
                          @click.stop="confirmDeleteProposal(client, p)"
                        />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Platform projects -->
            <template v-if="(detailCache[client.id]?.projects || []).length > 0">
              <div class="px-5 pt-4 pb-1 border-t border-border-muted mt-2">
                <p class="text-xs font-semibold text-text-subtle uppercase tracking-wider mb-2">Proyectos de plataforma</p>
              </div>
              <div :class="isCompact ? 'overflow-visible' : 'overflow-x-auto'">
                <table class="w-full text-sm" :class="isCompact ? 'client-detail-cards' : 'min-w-[500px]'">
                  <thead>
                    <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
                      <th class="px-5 py-3">Proyecto</th>
                      <th class="px-4 py-3">Estado</th>
                      <th class="px-4 py-3 text-center">Progreso</th>
                      <th class="px-4 py-3">Inicio</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border-muted">
                    <tr
                      v-for="proj in detailCache[client.id].projects"
                      :key="proj.id"
                      class="hover:bg-surface-raised transition-colors bg-surface"
                    >
                      <td class="px-5 py-3 font-medium text-text-default" data-label="Proyecto" data-card-full>
                        <span class="block min-w-0 max-w-[22rem] [overflow-wrap:anywhere]" :title="proj.name">{{ proj.name }}</span>
                      </td>
                      <td class="px-4 py-3" data-label="Estado">
                        <span class="inline-flex min-w-0 max-w-full flex-wrap rounded-full px-2.5 py-1 text-xs font-medium [overflow-wrap:anywhere]" :class="statusClass(proj.status)">
                          {{ proj.status }}
                        </span>
                      </td>
                      <td class="px-4 py-3 text-center text-text-muted/60" data-label="Progreso">{{ proj.progress }}%</td>
                      <td class="px-4 py-3 text-text-muted text-xs" data-label="Inicio" data-card-full>
                        {{ proj.start_date ? formatDate(proj.start_date) : '—' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>

            <!-- Web diagnostics (drop target for diagnostic reassignment) -->
            <div
              v-if="(detailCache[client.id]?.diagnostics || []).length > 0"
              :data-testid="`client-diagnostics-zone-${client.id}`"
              :class="{ 'ring-2 ring-inset ring-focus-ring bg-primary-soft': dragOverZoneKey === `${client.id}:diagnostic` }"
              @dragover="onZoneDragOver($event, client, 'diagnostic')"
              @dragleave="onZoneDragLeave($event, client, 'diagnostic')"
              @drop.prevent="onZoneDrop(client, 'diagnostic')"
            >
              <div class="px-5 pt-4 pb-1 border-t border-border-muted mt-2">
                <p class="text-xs font-semibold text-text-subtle uppercase tracking-wider mb-2">Diagnósticos web</p>
              </div>
              <div :class="isCompact ? 'overflow-visible' : 'overflow-x-auto'">
                <table class="w-full text-sm" :class="isCompact ? 'client-detail-cards' : 'min-w-[500px]'">
                  <thead>
                    <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
                      <th class="px-5 py-3">Diagnóstico</th>
                      <th class="px-4 py-3">Estado</th>
                      <th class="px-4 py-3">Creado</th>
                      <th class="px-4 py-3 text-right">Acciones</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border-muted">
                    <tr
                      v-for="diag in detailCache[client.id].diagnostics"
                      :key="diag.id"
                      :draggable="!isCompact"
                      :data-testid="`client-diagnostic-row-${diag.id}`"
                      class="hover:bg-surface-raised transition-colors bg-surface cursor-grab active:cursor-grabbing select-none"
                      :class="{ 'opacity-50': draggingItem?.type === 'diagnostic' && draggingItem?.id === diag.id }"
                      @dragstart="onRowDragStart($event, client, 'diagnostic', diag)"
                      @dragend="onRowDragEnd"
                    >
                      <td class="px-5 py-3 font-medium text-text-default" data-label="Diagnóstico" data-card-full>
                        <span class="block min-w-0 max-w-[22rem] [overflow-wrap:anywhere]" :title="diag.title">{{ diag.title }}</span>
                      </td>
                      <td class="px-4 py-3" data-label="Estado">
                        <span class="inline-flex min-w-0 max-w-full flex-wrap rounded-full px-2.5 py-1 text-xs font-medium [overflow-wrap:anywhere]" :class="statusClass(diag.status)">
                          {{ diag.status }}
                        </span>
                      </td>
                      <td class="px-4 py-3 text-text-muted text-xs" data-label="Creado">
                        {{ diag.created_at ? formatDate(diag.created_at) : '—' }}
                      </td>
                      <td class="px-4 py-3 text-right" data-label="Acciones" data-card-full>
                        <BaseButton
                          v-if="isCompact"
                          variant="secondary"
                          size="sm"
                          :data-testid="`client-diagnostic-move-${diag.id}`"
                          @click.stop="openTouchReassign(client, 'diagnostic', diag)"
                        >
                          Mover
                        </BaseButton>
                        <BaseActionButton
                          action="delete"
                          label="Eliminar diagnóstico"
                          variant="danger-ghost"
                          size="sm"
                          :class="isCompact ? 'min-h-11 min-w-11' : ''"
                          :data-testid="`client-diagnostic-delete-${diag.id}`"
                          @click.stop="confirmDeleteDiagnostic(client, diag)"
                        />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Accounting: what this client costs and pays -->
            <div v-if="detailCache[client.id]?.hostings?.length">
              <div class="px-5 pt-4 pb-1 border-t border-border-muted mt-2 flex items-center justify-between gap-3">
                <p class="text-xs font-semibold text-text-subtle uppercase tracking-wider">Hostings</p>
                <p class="text-xs text-text-muted tabular-nums">
                  {{ formatMoney(detailCache[client.id].hostings_monthly_total) }} /mes activos
                </p>
              </div>
              <div :class="isCompact ? 'overflow-visible' : 'overflow-x-auto'">
                <table class="w-full text-sm" :class="isCompact ? 'client-detail-cards' : 'min-w-[500px]'">
                  <thead>
                    <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
                      <th class="px-5 py-3">Hosting</th>
                      <th class="px-4 py-3">Proyecto</th>
                      <th class="px-4 py-3">Valor/mes</th>
                      <th class="px-4 py-3">Vence</th>
                      <th class="px-4 py-3">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="hosting in detailCache[client.id].hostings"
                      :key="hosting.id"
                      class="border-t border-border-muted"
                      :data-testid="`client-hosting-${hosting.id}`"
                    >
                      <td class="px-5 py-3 text-text-default" data-label="Hosting" data-card-full>
                        <span
                          class="block min-w-0 max-w-[22rem] [overflow-wrap:anywhere]"
                          :title="hosting.domain_url || hosting.client_name"
                        >{{ hosting.domain_url || hosting.client_name }}</span>
                      </td>
                      <td
                        class="px-4 py-3 text-text-muted text-xs"
                        data-label="Proyecto"
                        :data-testid="`client-hosting-project-${hosting.id}`"
                      >
                        <span class="block min-w-0 max-w-[22rem] [overflow-wrap:anywhere]" :title="hosting.project_name || ''">
                          {{ hosting.project_name || '—' }}
                        </span>
                      </td>
                      <td class="px-4 py-3 tabular-nums text-text-muted" data-label="Valor por mes">
                        {{ formatMoney(hosting.monthly_value) }}
                      </td>
                      <td class="px-4 py-3 text-text-muted text-xs" data-label="Vence">
                        {{ hosting.valid_to ? formatDate(hosting.valid_to) : '—' }}
                      </td>
                      <td class="px-4 py-3" data-label="Estado" data-card-full>
                        <span
                          class="inline-flex min-w-0 max-w-full flex-wrap rounded-full px-2.5 py-1 text-xs font-medium [overflow-wrap:anywhere]"
                          :class="hosting.is_active
                            ? 'bg-success-soft text-success-strong'
                            : 'bg-surface-raised text-text-muted'"
                        >
                          {{ hosting.is_active ? 'Vigente' : 'Inactivo' }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="detailCache[client.id]?.incomes?.length">
              <div class="px-5 pt-4 pb-1 border-t border-border-muted mt-2">
                <p class="text-xs font-semibold text-text-subtle uppercase tracking-wider">Ingresos</p>
              </div>
              <div :class="isCompact ? 'overflow-visible' : 'overflow-x-auto'">
                <table class="w-full text-sm" :class="isCompact ? 'client-detail-cards' : 'min-w-[500px]'">
                  <thead>
                    <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
                      <th class="px-5 py-3">Concepto</th>
                      <th class="px-4 py-3">Proyecto</th>
                      <th class="px-4 py-3">Mes</th>
                      <th class="px-4 py-3">Total</th>
                      <th class="px-4 py-3">Cobro</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="income in detailCache[client.id].incomes"
                      :key="income.id"
                      class="border-t border-border-muted"
                      :data-testid="`client-income-${income.id}`"
                    >
                      <td class="px-5 py-3 text-text-default" data-label="Concepto" data-card-full>
                        <span class="block min-w-0 max-w-[22rem] [overflow-wrap:anywhere]" :title="income.concept">{{ income.concept }}</span>
                      </td>
                      <td
                        class="px-4 py-3 text-text-muted text-xs"
                        data-label="Proyecto"
                        :data-testid="`client-income-project-${income.id}`"
                      >
                        <span class="block min-w-0 max-w-[22rem] [overflow-wrap:anywhere]" :title="income.project_name || ''">
                          {{ income.project_name || '—' }}
                        </span>
                      </td>
                      <td class="px-4 py-3 text-text-muted text-xs" data-label="Mes">{{ income.period_label }}</td>
                      <td class="px-4 py-3 tabular-nums text-text-muted" data-label="Total">
                        {{ formatMoney(income.total_amount) }}
                      </td>
                      <td class="px-4 py-3 text-text-muted text-xs" data-label="Cobro" data-card-full>
                        <span class="block min-w-0 max-w-[22rem] [overflow-wrap:anywhere]">
                          {{ income.payment_status_label || income.kind_label }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Los últimos 5 documentos del cliente; "Ver todos" entra al
                 módulo ya filtrado — la relación sirve en las dos direcciones. -->
            <div v-if="detailCache[client.id]?.documents?.length">
              <div class="px-5 pt-4 pb-1 border-t border-border-muted mt-2 flex items-center justify-between gap-3">
                <p class="text-xs font-semibold text-text-subtle uppercase tracking-wider">Documentos</p>
                <!-- design-tokens: allow-raw-button -->
                <button
                  type="button"
                  :data-testid="`client-documents-all-${client.id}`"
                  class="text-xs text-text-brand hover:underline"
                  @click.stop="goToClientDocuments(client)"
                >
                  Ver todos ({{ detailCache[client.id].documents_total }})
                </button>
              </div>
              <div :class="isCompact ? 'overflow-visible' : 'overflow-x-auto'">
                <table class="w-full text-sm" :class="isCompact ? 'client-detail-cards' : 'min-w-[500px]'">
                  <thead>
                    <tr class="bg-surface-raised text-left text-xs text-text-muted uppercase tracking-wider">
                      <th class="px-5 py-3">Documento</th>
                      <th class="px-4 py-3">Proyecto</th>
                      <th class="px-4 py-3">Estado</th>
                      <th class="px-4 py-3">Creado</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="doc in detailCache[client.id].documents"
                      :key="doc.id"
                      class="border-t border-border-muted"
                      :data-testid="`client-document-row-${doc.id}`"
                    >
                      <td class="px-5 py-3" data-label="Documento" data-card-full>
                        <NuxtLink
                          :to="localePath(`/panel/documents/${doc.id}/edit`)"
                          class="block min-w-0 max-w-[22rem] whitespace-normal text-text-default [overflow-wrap:anywhere] hover:text-text-brand hover:underline"
                          :title="doc.title"
                          @click.stop
                        >
                          {{ doc.title }}
                        </NuxtLink>
                      </td>
                      <td class="px-4 py-3 text-text-muted text-xs" data-label="Proyecto">
                        <span class="block min-w-0 max-w-[22rem] [overflow-wrap:anywhere]" :title="doc.project_name || ''">
                          {{ doc.project_name || '—' }}
                        </span>
                      </td>
                      <td class="px-4 py-3 text-text-muted text-xs" data-label="Estado">
                        <span class="block min-w-0 max-w-full [overflow-wrap:anywhere]">{{ documentStatusLabel(doc.status) }}</span>
                      </td>
                      <td class="px-4 py-3 text-text-muted text-xs" data-label="Creado" data-card-full>{{ formatDate(doc.created_at) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <BasePagination
      v-if="!clientsStore.isLoading && filteredClients.length > 0"
      :current-page="clientsPage"
      :total-pages="clientsTotalPages"
      :total-items="clientsTotalItems"
      :range-from="clientsRangeFrom"
      :range-to="clientsRangeTo"
      class="mt-4"
      @prev="clientsPrev"
      @next="clientsNext"
      @go="clientsGoTo"
    />
    </template>

    <BaseDrawer
      v-model="showMobileFilters"
      placement="bottom"
      title="Filtros de clientes"
      test-id="clients-filters-drawer"
    >
      <div class="space-y-5 p-4 panel-portrait:p-6">
        <BaseFormField label="Estado del cliente">
          <BaseSelect
            :model-value="clientStatus"
            :options="clientStatusOptions"
            data-testid="clients-status-selector-mobile"
            @update:model-value="setClientStatus"
          />
        </BaseFormField>

        <BaseFormField label="Módulo de negocio">
          <BaseSelect
            :model-value="activeModule"
            :options="mobileModuleOptions"
            data-testid="clients-module-selector-mobile"
            @update:model-value="selectModule"
          />
        </BaseFormField>

        <BaseFormField label="Filtro guardado">
          <BaseSelect
            :model-value="String(filterTabId)"
            :options="mobileSubfilterOptions"
            data-testid="clients-subfilter-selector-mobile"
            @update:model-value="onSelectFilterTab"
          />
        </BaseFormField>

        <div>
          <h3 class="mb-2 text-sm font-semibold text-text-default">Filtros avanzados</h3>
          <ClientFilterPanel
            :model-value="currentFilters"
            :is-open="true"
            :filter-count="activeFilterCount"
            @update:model-value="onFiltersUpdate"
            @reset="handleResetFilters"
          />
        </div>

        <BaseButton
          variant="secondary"
          size="md"
          class="w-full"
          data-testid="clients-mobile-settings"
          @click="openMobileSettings"
        >
          Configuraciones de la vista
        </BaseButton>
      </div>

      <template #footer>
        <div class="flex items-center justify-between gap-3">
          <BaseButton variant="ghost" size="md" @click="clearMobileFilters">
            Limpiar
          </BaseButton>
          <BaseButton
            variant="primary"
            size="md"
            data-testid="clients-mobile-filter-results"
            @click="showMobileFilters = false"
          >
            Ver {{ filteredClients.length }} {{ filteredClients.length === 1 ? 'cliente' : 'clientes' }}
          </BaseButton>
        </div>
      </template>
    </BaseDrawer>

    <BaseDrawer
      v-model="showClientActions"
      placement="bottom"
      :title="clientActionTarget?.name || 'Acciones del cliente'"
      test-id="client-actions-drawer"
    >
      <div v-if="clientActionTarget" class="space-y-2 p-4 panel-portrait:p-6">
        <BaseButton variant="secondary" size="md" class="min-h-11 w-full justify-start" @click="editClientFromActions">
          Editar cliente
        </BaseButton>
        <BaseButton variant="secondary" size="md" class="min-h-11 w-full justify-start" @click="emailsFromActions">
          Ver correos
        </BaseButton>
        <BaseButton variant="secondary" size="md" class="min-h-11 w-full justify-start" @click="communicationsFromActions">
          Ver comunicaciones
        </BaseButton>
        <BaseButton
          v-if="Number(clientActionTarget.documents_count || 0) > 0"
          variant="secondary"
          size="md"
          class="min-h-11 w-full justify-start"
          @click="documentsFromActions"
        >
          Ver documentos
        </BaseButton>
        <BaseButton
          v-if="canOpenHostings && Number(clientActionTarget.hostings_count || 0) > 0"
          variant="secondary"
          size="md"
          class="min-h-11 w-full justify-start"
          @click="hostingsFromActions"
        >
          Ver hostings
        </BaseButton>
        <BaseButton
          v-if="clientActionTarget.accepted_count > 0"
          variant="secondary"
          size="md"
          class="min-h-11 w-full justify-start"
          @click="platformFromActions"
        >
          Ver en plataforma
        </BaseButton>
        <BaseButton variant="secondary" size="md" class="min-h-11 w-full justify-start" @click="openArchiveModalFromActions">
          {{ clientActionTarget.is_archived ? 'Desarchivar cliente' : 'Archivar cliente' }}
        </BaseButton>
        <BaseButton variant="danger-ghost" size="md" class="min-h-11 w-full justify-start" @click="deleteClientFromActions">
          Eliminar cliente
        </BaseButton>
      </div>
    </BaseDrawer>

    <ClientReassignModal
      v-model="showTouchReassign"
      :item="touchReassignItem"
      :busy="isTouchReassigning"
      @confirm="confirmTouchReassign"
    />

    <!-- New client modal -->
    <BaseModal
      :model-value="showCreateModal"
      kind="form"
      title-id="clients-create-title"
      @close="closeCreateModal"
    >
        <div class="px-6 pt-6 pb-2">
          <h3 id="clients-create-title" class="text-lg font-bold text-text-default">Nuevo cliente</h3>
          <p class="mt-1 text-sm text-text-muted">
            Crea un perfil sin propuesta. Si no agregas email, generaremos uno temporal y las
            automatizaciones quedarán pausadas para este cliente.
          </p>
        </div>
        <form :id="modalFormId" novalidate @submit.prevent="submitCreate">
          <div class="space-y-4 px-6 py-4">
          <ClientFormFields
            :model-value="createForm"
            testid-prefix="clients-new"
            :errors="createFieldErrors"
            show-archived
            @update:model-value="Object.assign(createForm, $event)"
            @clear-error="clearCreateFieldError"
          />
          <BaseAlert v-if="createError" variant="danger">{{ createError }}</BaseAlert>
          </div>
        </form>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="ghost" size="md" @click="closeCreateModal">
            Cancelar
          </BaseButton>
          <BaseButton variant="primary" size="md" type="submit" :form="modalFormId" :loading="clientsStore.isUpdating" data-testid="clients-new-submit">
            Crear cliente
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>

    <!-- Edit client modal -->
    <BaseModal
      :model-value="Boolean(editingClient)"
      kind="form"
      title-id="clients-edit-title"
      @close="closeEditModal"
    >
        <div class="px-6 pt-6 pb-2">
          <h3 id="clients-edit-title" class="text-lg font-bold text-text-default">Editar cliente</h3>
          <p class="mt-1 text-sm text-text-muted">
            Los cambios se propagarán a todas las propuestas vinculadas a este cliente.
          </p>
        </div>
        <form :id="modalFormId2" novalidate @submit.prevent="submitEdit">
          <div class="space-y-4 px-6 py-4">
          <ClientFormFields
            :model-value="editForm"
            testid-prefix="clients-edit"
            :errors="editFieldErrors"
            show-archived
            editing
            @update:model-value="Object.assign(editForm, $event)"
            @clear-error="clearEditFieldError"
            @request-archive="openArchiveModal(editingClient)"
          />
          <BaseAlert v-if="editError" variant="danger">{{ editError }}</BaseAlert>
          </div>
        </form>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="ghost" size="md" @click="closeEditModal">
            Cancelar
          </BaseButton>
          <BaseButton variant="primary" size="md" type="submit" :form="modalFormId2" :loading="clientsStore.isUpdating" data-testid="clients-edit-submit">
            Guardar cambios
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>

    <!-- Archive, with the project cascade shown before it happens. Reached
         from the row icon, the mobile action sheet and the edit form alike:
         one reviewed path, no shortcut. -->
    <ClientArchiveModal
      :open="Boolean(archiveTarget)"
      :client="archiveTarget"
      @close="closeArchiveModal"
      @changed="onArchiveChanged"
    />

    <!-- The client's emails, and the viewer for one of them. Siblings rather
         than nested: BaseModal has no stacking manager, so DOM order is what
         decides which one paints on top. -->
    <ClientEmailsModal
      :open="emailsModalOpen"
      :client="emailsClient"
      :preview-open="emailBodyOpen"
      @close="closeEmails"
      @view-body="openEmailBody"
    />
    <EmailBodyModal
      :open="emailBodyOpen"
      :entry="emailBodyEntry"
      :fetcher="fetchEmailBody"
      @close="emailBodyOpen = false"
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
  </div>
</template>

<script setup>
import EntityHistorySection from '~/components/history/EntityHistorySection.vue';
import { useId, ref, reactive, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { formatDate } from '~/utils/formatDate';
import { documentStatusLabel } from '~/utils/documentStatus';
import { formatMoney as formatMoneyRaw } from '~/utils/formatMoney';
import { clientFormPayload, emptyClientForm } from '~/utils/billingCode';
import ConfirmModal from '~/components/ConfirmModal.vue';
import ClientFilterPanel from '~/components/clients/ClientFilterPanel.vue';
import ClientArchiveModal from '~/components/clients/ClientArchiveModal.vue';
import ClientFormFields from '~/components/clients/ClientFormFields.vue';
import ClientModuleTabs from '~/components/clients/ClientModuleTabs.vue';
import ClientReassignModal from '~/components/clients/ClientReassignModal.vue';
import ClientEmailsModal from '~/components/clients/ClientEmailsModal.vue';
import EmailBodyModal from '~/components/accounting/EmailBodyModal.vue';
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue';
import ViewSettingsPanel from '~/components/panel/ViewSettingsPanel.vue';
import BasePagination from '~/components/base/BasePagination.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import ProposalApprovalModal from '~/components/BusinessProposal/admin/ProposalApprovalModal.vue';
import { useProposalApproval } from '~/composables/useProposalApproval';
import ProposalStatusSelect from '~/components/panel/proposal/ProposalStatusSelect.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { useProposalStatusChange } from '~/composables/useProposalStatusChange';
import { useAccountingFilters } from '~/composables/useAccountingFilters';
import {
  CLIENT_FILTERS_CONFIG,
  CLIENT_MODULES,
  clientModuleName,
  clientSubfiltersFor,
  documentsPill,
  findClientSubfilter,
  matchesSubfilter,
} from '~/constants/clientFilters';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelToPlatformBridge } from '~/composables/usePanelToPlatformBridge';
import { usePagination } from '~/composables/usePagination';
import { useIsMobile } from '~/composables/useIsMobile';
import { PANEL_BREAKPOINTS } from '~/config/responsive';
import { useProposalClientsStore } from '~/stores/proposal_clients';
import { useProposalStore } from '~/stores/proposals';
import { useDiagnosticsStore } from '~/stores/diagnostics';
import { PAGE_MAX_WIDTH } from '~/utils/tableLayout';

const localePath = useLocalePath();
const { goToPlatform, isBridging } = usePanelToPlatformBridge();
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const clientsStore = useProposalClientsStore();
const { isMobile: isCompact } = useIsMobile(PANEL_BREAKPOINTS.landscape - 1);
const showMobileFilters = ref(false);

/** COP money from the API's string amounts. */
function formatMoney(value) {
  return formatMoneyRaw(Number(value ?? 0), 'COP');
}
const proposalStore = useProposalStore();
const diagnosticsStore = useDiagnosticsStore();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } =
  useConfirmModal();
const notify = usePanelNotify();

// Inline status change for the nested proposal rows. No onNegotiate here:
// natural negotiating PATCHes directly; the contract flow lives in the
// proposal edit view.
const { approvalText, approvalProposal, approvalAccept, openApproval, approvalCompleted } = useProposalApproval();
const approvalClientId = ref(null);
const { updatingId: updatingProposalStatusId, changeStatus: changeProposalStatus } =
  useProposalStatusChange({ requestConfirm, onAccept: (proposal) => openApproval(proposal, true) });

function openClientApproval(client, proposal, accept = true) {
  approvalClientId.value = client.id;
  openApproval(proposal, accept);
}

async function handleClientApprovalCompleted(result) {
  const sourceClientId = approvalClientId.value;
  const selectedClientId = result.client?.profile_id;
  approvalCompleted(result);
  if (sourceClientId != null) await refreshClientDetail(sourceClientId);
  // A proposal may be linked to another existing client. Refresh that visible
  // cache as well, without editing either client's global identity fields.
  if (selectedClientId && selectedClientId !== sourceClientId && detailCache[selectedClientId]) {
    const refreshed = await clientsStore.fetchClient(selectedClientId);
    if (refreshed.success) detailCache[selectedClientId] = refreshed.data;
  }
}

async function onProposalStatusSelect(client, proposal, newStatus) {
  approvalClientId.value = client.id;
  const result = await changeProposalStatus(proposal, newStatus);
  // Refresh on success AND failure: the nested row may be stale either way.
  if (result) await refreshClientDetail(client.id);
}

// Migrated off the old useClientFilters (its pre-generalization ancestor) so
// the predefined filters ride the same `builtinTabs` mechanism the accounting
// subviews already use. The configuration itself lives in ~/constants/
// clientFilters so this page and its tests never drift apart.
const {
  currentFilters,
  displayTabs,
  activeTabId: filterTabId,
  activeModule,
  selectModule,
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
  reloadTabs: reloadFilterTabs,
} = useAccountingFilters(CLIENT_FILTERS_CONFIG);

const filteredClients = computed(() => applyFilters(clientsStore.clients));

const mobileModuleOptions = CLIENT_MODULES.map((module) => ({
  value: module.id,
  label: module.name,
}));

const mobileSubfilterOptions = computed(() => [
  { value: 'all', label: 'Todos los clientes del módulo' },
  ...displayTabs.value
    .filter((tab) => !tab.is_hidden)
    .map((tab) => {
      const count = subfilterCounts.value[String(tab.id)];
      return {
        value: String(tab.id),
        label: `${tab.name}${typeof count === 'number' ? ` (${count})` : ''}`,
      };
    }),
]);

/**
 * The per-row hosting count only earns its space while the Hosting module is
 * the one being read — that is the moment the question "cuántos" is being
 * asked, whichever of its subfilters is applied.
 */
function showsHostingCount(client) {
  return activeModule.value === 'hosting' && Number(client.hostings_count || 0) > 0;
}

function showsEmailCount(client) {
  return activeModule.value === 'emails' && Number(client.emails_sent_count || 0) > 0;
}

// The emails modal, reachable two ways: the row pill while the Emails module
// is being read, and the "Ver correos" button on the expanded card — filtering
// is for finding who, the ficha is where you already are when the question
// comes up. One modal serves both.
const emailsClient = ref(null);
const emailsModalOpen = ref(false);
const emailBodyEntry = ref(null);
const emailBodyOpen = ref(false);

function openEmails(client) {
  emailsClient.value = client;
  emailsModalOpen.value = true;
}

function closeEmails() {
  emailsModalOpen.value = false;
  emailsClient.value = null;
}

function openEmailBody(entry) {
  emailBodyEntry.value = entry;
  emailBodyOpen.value = true;
}

function fetchEmailBody(logId) {
  return clientsStore.fetchClientEmailBody(emailsClient.value?.id, logId);
}

/**
 * /panel/clients only requires admin, but /panel/accounting/* is behind the
 * superuser-only middleware. Without this guard a staff non-superuser would
 * click the pill straight into a redirect.
 */
const canOpenHostings = computed(() => proposalStore.isSuperuser);

const clientActionTarget = ref(null);
const showClientActions = computed({
  get: () => Boolean(clientActionTarget.value),
  set: (isOpen) => {
    if (!isOpen) clientActionTarget.value = null;
  },
});

function openClientActions(client) {
  clientActionTarget.value = client;
}

function takeClientAction(callback) {
  const client = clientActionTarget.value;
  clientActionTarget.value = null;
  if (client) callback(client);
}

function editClientFromActions() {
  takeClientAction(openEditModal);
}

function emailsFromActions() {
  takeClientAction(openEmails);
}

function communicationsFromActions() {
  takeClientAction(goToClientCommunications);
}

function documentsFromActions() {
  takeClientAction(goToClientDocuments);
}

function hostingsFromActions() {
  takeClientAction(goToClientHostings);
}

function platformFromActions() {
  takeClientAction((client) => goToPlatform(`/platform/clients/${client.user_id}`));
}

function openArchiveModalFromActions() {
  takeClientAction(openArchiveModal);
}

function deleteClientFromActions() {
  takeClientAction(confirmDelete);
}

function goToClientHostings(client) {
  navigateTo({
    path: '/panel/accounting/hostings',
    query: { client: String(client.id) },
  });
}

/**
 * A diferencia del pill de hostings, sin guard de superuser: /panel/documents
 * comparte el gate admin de esta misma página. Qué contador muestra depende
 * del CORTE activo, no sólo del módulo (ver `documentsPill`).
 */
function documentsPillFor(client) {
  if (activeModule.value !== 'documents') return null;
  return documentsPill(client, filterTabId.value);
}

function goToClientDocuments(client) {
  navigateTo({
    path: '/panel/documents',
    query: { client: String(client.id) },
  });
}

function goToClientCommunications(client) {
  navigateTo({
    path: '/panel/communications',
    query: { client: String(client.id) },
  });
}

/**
 * Matches per subfilter of the active module, read straight off the loaded
 * rows so the number is visible without applying the filter. Counted before
 * the panel's advanced filters — a badge should not move as you tweak
 * unrelated controls — but after the status selector and search, which is what
 * "lo que obtendrías si lo presionas ahora" means here.
 *
 * Always a number, never absent: an empty set is information, and hiding the
 * zero would force the user to press the filter to find out.
 */
const subfilterCounts = computed(() => {
  const counts = {};
  for (const sub of clientSubfiltersFor(activeModule.value)) {
    counts[sub.id] = clientsStore.clients.filter((c) => matchesSubfilter(sub, c)).length;
  }
  return counts;
});

/**
 * Presses on the active subfilter turn it off (requisito: "al presionarlo de
 * nuevo, la lista vuelve a todos los clientes"). Gated to subfilter ids on
 * purpose: re-clicking a saved tab has always been an idempotent reload of
 * its filters, and toggling those off would be a silent behavior change.
 */
function onSelectFilterTab(tabId) {
  const key = String(tabId);
  if (findClientSubfilter(key) && key === String(filterTabId.value)) {
    selectFilterTab('all');
    return;
  }
  selectFilterTab(tabId);
}

/**
 * Tab, chip and panel are three views of one state, so they have to move
 * together: the panel owns the whole filter object, and once an edit from it
 * (typically removing a chip) leaves the highlighted subfilter's own values no
 * longer set, that highlight is a lie and has to go.
 *
 * Only the highlight is dropped, not the filters: the user may well have other
 * cuts applied, and clearing one chip must not take them down with it. Saved
 * tabs are left alone — editing one is how you modify it, and the composable
 * already tracks that as "modificada" with its own restore.
 */
function onFiltersUpdate(next) {
  Object.assign(currentFilters, next);

  const active = findClientSubfilter(filterTabId.value);
  if (active && !subfilterStillApplied(active)) {
    filterTabId.value = 'all';
  }
}

/** Whether every value the subfilter stands for is still set in the panel. */
function subfilterStillApplied(subfilter) {
  return Object.entries(subfilter.filters).every(([key, value]) => {
    const current = currentFilters[key];
    if (Array.isArray(value)) {
      return Array.isArray(current)
        && current.length === value.length
        && value.every((v) => current.includes(v));
    }
    return current === value;
  });
}

const {
  currentPage: clientsPage,
  totalPages: clientsTotalPages,
  totalItems: clientsTotalItems,
  rangeFrom: clientsRangeFrom,
  rangeTo: clientsRangeTo,
  paginatedItems: pagedClients,
  goTo: clientsGoTo,
  next: clientsNext,
  prev: clientsPrev,
  reset: clientsResetPage,
} = usePagination(filteredClients, { pageSize: 10 });

watch(filteredClients, () => clientsResetPage(), { deep: false });

/**
 * Client status: the state of the register itself, orthogonal to every module,
 * so it lives next to the search box and combines with any of them. Applied
 * server-side, which is why its counts come from their own endpoint.
 */
const CLIENT_STATUSES = [
  { id: 'all', label: 'Todos' },
  { id: 'active', label: 'Activos' },
  { id: 'orphans', label: 'Huérfanos' },
  { id: 'archived', label: 'Archivados' },
];
const route = useRoute();
const router = useRouter();
const VALID_STATUSES = CLIENT_STATUSES.map((s) => s.id);
const initialStatus = String(route.query.status || 'all');
const clientStatus = ref(VALID_STATUSES.includes(initialStatus) ? initialStatus : 'all');
const isConfigOpen = ref(false);

const clientStatusOptions = computed(() =>
  CLIENT_STATUSES.map(({ id, label }) => {
    const count = clientsStore.statusCounts?.[id];
    return {
      value: id,
      // Same treatment as the subfilter counts: in parentheses, always shown,
      // zero included.
      label: count == null ? label : `${label} (${count})`,
      testId: `clients-status-${id}`,
    };
  }),
);

const mobileFilterCount = computed(() => (
  activeFilterCount.value
  + (activeModule.value === 'all' ? 0 : 1)
  + (String(filterTabId.value) === 'all' ? 0 : 1)
  + (clientStatus.value === 'all' ? 0 : 1)
));

const mobileFilterSummary = computed(() => {
  const parts = [];
  if (clientStatus.value !== 'all') {
    parts.push(CLIENT_STATUSES.find((status) => status.id === clientStatus.value)?.label);
  }
  if (activeModule.value !== 'all') parts.push(clientModuleName(activeModule.value));
  if (String(filterTabId.value) !== 'all') {
    const tab = displayTabs.value.find((entry) => String(entry.id) === String(filterTabId.value));
    if (tab) parts.push(tab.name);
  }
  return parts.filter(Boolean).join(' · ') || 'Filtros';
});

function clearMobileFilters() {
  resetFilters();
  selectModule('all');
  selectFilterTab('all');
  setClientStatus('all');
}

function openMobileSettings() {
  showMobileFilters.value = false;
  isConfigOpen.value = true;
}

const search = ref('');
const expandedClients = ref(new Set());
const loadingDetails = ref(new Set());
const detailCache = reactive({});

let searchTimer = null;

// -------------------------------------------------------------------
// Data loading
// -------------------------------------------------------------------

async function loadClients({ silent = false } = {}) {
  let orphans = null;
  if (clientStatus.value === 'orphans') orphans = true;
  else if (clientStatus.value === 'active') orphans = false;
  const search_ = search.value.trim();
  await Promise.all([
    clientsStore.fetchClients({
      search: search_,
      orphans,
      // The endpoint does not paginate and every filter on this page — the
      // subfilters and their counts included — runs over whatever was loaded,
      // so ask for the endpoint's hard cap instead of the default 100. Past 500
      // clients this needs real server-side pagination.
      limit: 500,
      archived: clientStatus.value === 'archived',
      silent,
    }),
    // Same search, so the numbers in the selector describe the same table the
    // list is showing.
    clientsStore.fetchStatusCounts({ search: search_ }),
  ]);
}

/**
 * Full refresh bound to the global panel refresh button.
 *
 * Besides reloading the top-level rows, it invalidates the per-client
 * detail cache and refetches the rows that are still expanded. Without
 * this, renaming a proposal or reassigning it to another client would
 * not show up after refresh because the nested proposals are served from
 * `detailCache`, which is only populated once on expand.
 */
async function refreshAll() {
  await loadClients();
  const expandedIds = Array.from(expandedClients.value);
  Object.keys(detailCache).forEach((key) => { delete detailCache[key]; });
  await Promise.all(
    expandedIds.map(async (id) => {
      const result = await clientsStore.fetchClient(id);
      if (result.success) detailCache[id] = result.data;
    }),
  );
}

/**
 * The applied status travels in the URL so the link can be saved and survives
 * a reload, and is dropped again when it goes back to the default instead of
 * staying glued there.
 */
function setClientStatus(status) {
  if (status === clientStatus.value) return;
  clientStatus.value = status;
  const query = { ...route.query };
  if (status === 'all') delete query.status;
  else query.status = status;
  router.replace({ query });
  clientsResetPage();
  loadClients();
}

const archiveTarget = ref(null);

// The row icon used to PATCH straight away. It now opens the same modal the
// edit form does: archiving suspends the client's projects and cancels their
// future billing, and that is not something a single unlabelled click should
// be able to do.
function openArchiveModal(client) {
  archiveTarget.value = client;
}

function closeArchiveModal() {
  archiveTarget.value = null;
}

async function onArchiveChanged({ archived }) {
  const name = archiveTarget.value?.name || 'El cliente';
  notify.success(archived ? `"${name}" archivado.` : `"${name}" desarchivado.`);
  closeEditModal();
  await loadClients();
}

function compactContextLabel(client) {
  if (activeModule.value === 'hosting') {
    return `${client.hostings_count || 0} hosting${client.hostings_count === 1 ? '' : 's'}`;
  }
  if (activeModule.value === 'documents') {
    return documentsPillFor(client)?.label || 'Sin documentos';
  }
  if (activeModule.value === 'emails') {
    return `${client.emails_sent_count || 0} correo${client.emails_sent_count === 1 ? '' : 's'}`;
  }
  if (activeModule.value === 'accounting') {
    return `${client.incomes_count || 0} ingreso${client.incomes_count === 1 ? '' : 's'}`;
  }
  if (activeModule.value === 'projects') {
    return `${client.active_projects_count || 0} proyecto${client.active_projects_count === 1 ? '' : 's'} activo${client.active_projects_count === 1 ? '' : 's'}`;
  }
  if (activeModule.value === 'diagnostics') {
    return `${client.diagnostics_count || 0} diagnóstico${client.diagnostics_count === 1 ? '' : 's'}`;
  }
  if (activeModule.value === 'proposals') {
    return `${client.accepted_count || 0} propuesta${client.accepted_count === 1 ? '' : 's'} aceptada${client.accepted_count === 1 ? '' : 's'}`;
  }
  return `${client.incomes_count || 0} ingresos · ${client.hostings_count || 0} hostings`;
}

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(loadClients, 250);
}

function handleCreateFilterTab(name) {
  saveTab(name);
  isFilterPanelOpen.value = true;
}

function handleResetFilters() {
  resetFilters();
  isFilterPanelOpen.value = false;
}

function handleEditEscape(e) {
  if (e.key === 'Escape' && editingClient.value) closeEditModal();
}

onMounted(async () => {
  document.addEventListener('keydown', handleEditEscape);
  await loadClients();
  applyHighlightFromQuery();
});

/**
 * ?highlight=<profileId>: llega desde el enlace "Ver cliente" de un documento
 * — expande la ficha y hace scroll a la fila. Param de un solo uso (espejo de
 * ?highlight= en /panel/projects): se limpia de la URL y degrada sin ruido si
 * el cliente no está entre las filas cargadas o quedó en otra página.
 */
function applyHighlightFromQuery() {
  const targetId = Number.parseInt(route.query.highlight, 10);
  if (!Number.isFinite(targetId)) return;
  const query = { ...route.query };
  delete query.highlight;
  router.replace({ query });
  const target = clientsStore.clients.find((c) => c.id === targetId);
  if (!target) return;
  toggleClient(target);
  nextTick(() => {
    document.querySelector(`[data-testid="client-row-${targetId}"]`)
      ?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  });
}

usePanelRefresh(refreshAll);
onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer);
  document.removeEventListener('keydown', handleEditEscape);
});

// -------------------------------------------------------------------
// Row expand → fetch nested proposals on demand
// -------------------------------------------------------------------

async function toggleClient(client) {
  const id = client.id;
  if (expandedClients.value.has(id)) {
    expandedClients.value.delete(id);
    expandedClients.value = new Set(expandedClients.value);
    return;
  }
  expandedClients.value.add(id);
  expandedClients.value = new Set(expandedClients.value);

  if (!detailCache[id]) {
    loadingDetails.value.add(id);
    loadingDetails.value = new Set(loadingDetails.value);
    const result = await clientsStore.fetchClient(id);
    if (result.success) {
      detailCache[id] = result.data;
    }
    loadingDetails.value.delete(id);
    loadingDetails.value = new Set(loadingDetails.value);
  }
}

// -------------------------------------------------------------------
// Create modal
// -------------------------------------------------------------------

const showCreateModal = ref(false);
const createForm = reactive(emptyClientForm());
const createError = ref('');
const createFieldErrors = ref({});

function clientFieldErrors(errors) {
  if (!errors || typeof errors !== 'object') return {};
  const fields = ['name', 'email', 'phone', 'company', 'nit', 'cedula', 'address', 'billing_code'];
  const normalized = Object.fromEntries(fields.flatMap((field) => {
    const value = errors[field];
    const message = Array.isArray(value) ? value[0] : value;
    return typeof message === 'string' && message.trim() ? [[field, message]] : [];
  }));
  if (errors.error === 'invalid_billing_code' && errors.message) {
    normalized.billing_code = errors.message;
  }
  return normalized;
}

function clearCreateFieldError(field) {
  const nextErrors = { ...createFieldErrors.value };
  delete nextErrors[field];
  createFieldErrors.value = nextErrors;
}

function openCreateModal() {
  Object.assign(createForm, emptyClientForm());
  createError.value = '';
  createFieldErrors.value = {};
  showCreateModal.value = true;
}

function closeCreateModal() {
  showCreateModal.value = false;
}

async function submitCreate() {
  createError.value = '';
  createFieldErrors.value = {};
  if (!createForm.name.trim()) {
    createFieldErrors.value = { name: 'Escribe el nombre del cliente.' };
    return;
  }
  const result = await clientsStore.createClient(clientFormPayload(createForm));
  if (result.success) {
    // Born archived: a brand-new client has no projects, so the cascade is
    // empty and there is nothing to preview. It still goes through the archive
    // endpoint so the audit row exists from the start, like every other
    // archive.
    if (createForm.is_archived) {
      await clientsStore.archiveClient(result.data.id, []);
    }
    closeCreateModal();
    await loadClients();
  } else {
    createFieldErrors.value = clientFieldErrors(result.errors);
    if (!Object.keys(createFieldErrors.value).length) {
      createError.value = result.errors?.message
        || result.errors?.error
        || 'No se pudo crear el cliente. Verifica los datos e intenta nuevamente.';
    }
  }
}

// -------------------------------------------------------------------
// Edit modal
// -------------------------------------------------------------------

const editingClient = ref(null);
const editForm = reactive(emptyClientForm());
const editError = ref('');
const editFieldErrors = ref({});

function clearEditFieldError(field) {
  const nextErrors = { ...editFieldErrors.value };
  delete nextErrors[field];
  editFieldErrors.value = nextErrors;
}

function openEditModal(client) {
  editingClient.value = client;
  editForm.name = client.name || '';
  editForm.email = client.is_email_placeholder ? '' : (client.email || '');
  editForm.phone = client.phone || '';
  editForm.company = client.company || '';
  editForm.nit = client.nit || '';
  editForm.cedula = client.cedula || '';
  editForm.identification_type = client.nit ? 'NIT' : (client.cedula ? 'CC' : 'NIT');
  editForm.address = client.address || '';
  editForm.billing_code = client.billing_code || '';
  editForm.is_archived = Boolean(client.is_archived);
  editError.value = '';
  editFieldErrors.value = {};
}

function closeEditModal() {
  editingClient.value = null;
  editError.value = '';
}

async function submitEdit() {
  editError.value = '';
  editFieldErrors.value = {};
  if (!editForm.name.trim()) {
    editFieldErrors.value = { name: 'Escribe el nombre del cliente.' };
    return;
  }
  const result = await clientsStore.updateClient(
    editingClient.value.id, clientFormPayload(editForm),
  );
  if (result.success) {
    closeEditModal();
  } else {
    editFieldErrors.value = clientFieldErrors(result.errors);
    if (!Object.keys(editFieldErrors.value).length) {
      editError.value = result.errors?.message
        || result.errors?.error
        || 'Error al actualizar el cliente.';
    }
  }
}

// -------------------------------------------------------------------
// Delete
// -------------------------------------------------------------------

function buildBlockedMessage(client) {
  const parts = [];
  const proposals = client.total_proposals || 0;
  const projects = client.projects_count || 0;
  const diagnostics = client.diagnostics_count || 0;
  const incomes = client.incomes_count || 0;
  const hostings = client.hostings_count || 0;
  if (proposals > 0) parts.push(`${proposals} propuesta${proposals === 1 ? '' : 's'}`);
  if (projects > 0) parts.push(`${projects} proyecto${projects === 1 ? '' : 's'} de plataforma`);
  if (diagnostics > 0) parts.push(`${diagnostics} diagnóstico${diagnostics === 1 ? '' : 's'} web`);
  if (incomes > 0) parts.push(`${incomes} ingreso${incomes === 1 ? '' : 's'} contable${incomes === 1 ? '' : 's'}`);
  if (hostings > 0) parts.push(`${hostings} hosting${hostings === 1 ? '' : 's'}`);
  const reason = parts.length > 0 ? parts.join(', ') : 'elementos asociados';
  return `No se puede eliminar a "${client.name}" porque tiene ${reason}. Elimina o archiva esos elementos antes de borrar el cliente.`;
}

function confirmDelete(client) {
  if (!client.is_orphan) {
    requestConfirm({
      title: 'No se puede eliminar',
      message: buildBlockedMessage(client),
      variant: 'info',
      hideCancel: true,
      confirmText: 'Entendido',
    });
    return;
  }

  requestConfirm({
    title: 'Eliminar cliente',
    message: `Esto eliminará a "${client.name}" y su cuenta de plataforma de forma permanente. Esta acción no se puede deshacer.`,
    variant: 'danger',
    confirmText: 'Eliminar',
    cancelText: 'Cancelar',
    requireTypeText: 'DELETE',
    onConfirm: async () => {
      const result = await clientsStore.deleteClient(client.id);
      if (!result.success) {
        // Refresh in case the orphan flag was stale.
        await loadClients();
      }
    },
  });
}

async function refreshClientDetail(clientId) {
  const result = await clientsStore.fetchClient(clientId);
  if (result.success) detailCache[clientId] = result.data;
  // Counts and the orphan badge live on the list rows, not the detail payload.
  await loadClients();
}

// -------------------------------------------------------------------
// Drag & drop: reassign proposals/diagnostics between clients
// -------------------------------------------------------------------

const draggingItem = ref(null); // { type, id, title, sourceClientId, sourceClientName }
const dragOverClientId = ref(null);
const dragOverZoneKey = ref(null); // `${clientId}:${type}` for the proposals/diagnostics zones
const touchReassignItem = ref(null);
const isTouchReassigning = ref(false);
const showTouchReassign = computed({
  get: () => Boolean(touchReassignItem.value),
  set: (isOpen) => {
    if (!isOpen && !isTouchReassigning.value) touchReassignItem.value = null;
  },
});

function openTouchReassign(client, type, item) {
  touchReassignItem.value = {
    type,
    id: item.id,
    title: item.title,
    sourceClientId: client.id,
    sourceClientName: client.name,
  };
}

async function confirmTouchReassign(target) {
  const dragged = touchReassignItem.value;
  if (!dragged) return;
  isTouchReassigning.value = true;
  await reassignItem(dragged, target);
  isTouchReassigning.value = false;
  touchReassignItem.value = null;
}

function onRowDragStart(event, client, type, item) {
  draggingItem.value = {
    type,
    id: item.id,
    title: item.title,
    sourceClientId: client.id,
    sourceClientName: client.name,
  };
  // Sin setData, Firefox no inicia el drag nativo (no dispara dragover/drop).
  event.dataTransfer.setData('text/plain', `${type}:${item.id}`);
  event.dataTransfer.effectAllowed = 'move';
}

function onRowDragEnd() {
  draggingItem.value = null;
  dragOverClientId.value = null;
  dragOverZoneKey.value = null;
}

function onClientDragOver(event, client) {
  if (!draggingItem.value || client.id === draggingItem.value.sourceClientId) return;
  event.preventDefault(); // required so the browser allows the drop
  event.dataTransfer.dropEffect = 'move';
  dragOverClientId.value = client.id;
}

function onClientDragLeave(client) {
  if (dragOverClientId.value === client.id) dragOverClientId.value = null;
}

async function onClientDrop(targetClient) {
  dragOverClientId.value = null;
  dragOverZoneKey.value = null;
  const dragged = draggingItem.value;
  draggingItem.value = null;
  if (!dragged || dragged.sourceClientId === targetClient.id) return;
  await reassignItem(dragged, { targetClientId: targetClient.id, targetName: targetClient.name });
}

// Zone variants: the proposals/diagnostics areas of an expanded client accept
// only items of their own type; the client header keeps accepting both.
function onZoneDragOver(event, client, zoneType) {
  if (!draggingItem.value || draggingItem.value.type !== zoneType) return;
  if (client.id === draggingItem.value.sourceClientId) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  dragOverZoneKey.value = `${client.id}:${zoneType}`;
}

function onZoneDragLeave(event, client, zoneType) {
  // dragleave also fires when moving between the zone's own children.
  if (event.relatedTarget && event.currentTarget.contains(event.relatedTarget)) return;
  if (dragOverZoneKey.value === `${client.id}:${zoneType}`) dragOverZoneKey.value = null;
}

async function onZoneDrop(client, zoneType) {
  if (draggingItem.value?.type !== zoneType) {
    dragOverZoneKey.value = null;
    return;
  }
  await onClientDrop(client);
}

async function reassignItem(dragged, { targetClientId, targetName }) {
  const result = dragged.type === 'proposal'
    ? await proposalStore.updateProposal(dragged.id, { client_id: targetClientId })
    : await diagnosticsStore.update(dragged.id, { client_id: targetClientId });
  if (!result.success) {
    notify.error(`No se pudo mover ${dragged.type === 'proposal' ? 'la propuesta' : 'el diagnóstico'} "${dragged.title}".`);
    return;
  }
  await refreshAfterReassign(dragged.sourceClientId, targetClientId);
  notify.success({
    title: `"${dragged.title}" movido a ${targetName}.`,
    action: {
      label: 'Deshacer',
      handler: () => reassignItem(
        { ...dragged, sourceClientId: targetClientId, sourceClientName: targetName },
        { targetClientId: dragged.sourceClientId, targetName: dragged.sourceClientName },
      ),
    },
  });
}

// Unlike refreshClientDetail, this refreshes BOTH affected clients and the
// list once (the source/target orphan state may flip tabs). Everything runs
// silently and in-place: expanded details are overwritten only when the fresh
// payload arrives, and the list skips the loading skeleton, so the page does
// not visually "reload" after a drop.
async function refreshAfterReassign(...clientIds) {
  await Promise.all([
    ...clientIds.map(async (id) => {
      if (!expandedClients.value.has(id)) {
        delete detailCache[id]; // refetched on next expand
        return;
      }
      const result = await clientsStore.fetchClient(id);
      if (result.success) detailCache[id] = result.data;
    }),
    loadClients({ silent: true }),
  ]);
}

function confirmDeleteProposal(client, proposal) {
  requestConfirm({
    title: 'Eliminar propuesta',
    message: `Esto eliminará la propuesta "${proposal.title}" de forma permanente. Esta acción no se puede deshacer.`,
    variant: 'danger',
    confirmText: 'Eliminar',
    cancelText: 'Cancelar',
    requireTypeText: 'DELETE',
    onConfirm: async () => {
      const result = await proposalStore.deleteProposal(proposal.id);
      if (result.success) {
        await refreshClientDetail(client.id);
        notify.success('Propuesta eliminada.');
      } else {
        notify.error(result.error || 'No se pudo eliminar la propuesta.');
      }
    },
  });
}

function confirmDeleteDiagnostic(client, diagnostic) {
  requestConfirm({
    title: 'Eliminar diagnóstico',
    message: `Esto eliminará el diagnóstico "${diagnostic.title}" de forma permanente. Esta acción no se puede deshacer.`,
    variant: 'danger',
    confirmText: 'Eliminar',
    cancelText: 'Cancelar',
    requireTypeText: 'DELETE',
    onConfirm: async () => {
      const result = await diagnosticsStore.remove(diagnostic.id);
      if (result.success) await refreshClientDetail(client.id);
    },
  });
}

// -------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------

function initials(name) {
  return (name || '?')
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('');
}

function statusClass(s) {
  const map = {
    draft: 'bg-surface-raised text-text-muted',
    sent: 'bg-info-soft text-info-strong',
    viewed: 'bg-success-soft text-success-strong',
    accepted: 'bg-primary-soft text-text-brand',
    finished: 'bg-primary-soft text-text-brand',
    rejected: 'bg-danger-soft text-danger-strong',
    expired: 'bg-warning-soft text-warning-strong',
    negotiating: 'bg-primary-soft text-text-brand',
    active: 'bg-success-soft text-success-strong',
    suspended: 'bg-warning-soft text-warning-strong',
    completed: 'bg-primary-soft text-text-brand',
    archived: 'bg-surface-raised text-text-muted',
  };
  return map[s] || 'bg-surface-raised text-text-muted';
}

const modalFormId = useId();
const modalFormId2 = useId();
</script>

<style scoped>
.client-detail-cards {
  display: block;
  min-width: 0;
}

.client-detail-cards thead {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.client-detail-cards tbody {
  display: grid;
  gap: 0.75rem;
  width: 100%;
  padding: 0 1.25rem 1rem;
}

.client-detail-cards tbody tr {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  overflow: hidden;
  border: 1px solid var(--color-border-muted);
  border-radius: 0.75rem;
  background: var(--color-surface);
}

.client-detail-cards tbody td {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
  padding: 0.625rem 0.75rem;
  text-align: left;
  overflow-wrap: anywhere;
}

.client-detail-cards tbody td[data-card-full] {
  grid-column: 1 / -1;
}

.client-detail-cards tbody td::before {
  content: attr(data-label);
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--color-text-subtle);
}

.client-detail-cards tbody td[data-label='Acciones'] {
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
}

.client-detail-cards tbody td[data-label='Acciones']::before {
  width: 100%;
}
</style>
