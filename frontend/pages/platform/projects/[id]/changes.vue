<template>
  <ProjectShell>
    <div id="platform-changes">
    <!-- Loading -->
    <div v-if="crStore.isLoading && !crStore.changeRequests.length" class="py-20 text-center">
      <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-esmerald dark:border-t-lemon" />
    </div>

    <template v-else>
      <!-- Header -->
      <div class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between" data-enter>
        <div>
          <h1 class="text-xl font-bold text-text-default sm:text-2xl">Solicitudes de cambio</h1>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <!-- Phase selector -->
          <BaseDropdown
            v-if="phaseOptions.length > 0"
            :items="phaseDropdownItems"
            align="left"
            width="w-56"
          >
            <template #trigger>
              <BaseButton variant="secondary" size="sm">
                <span class="max-w-[140px] truncate">{{ selectedPhaseLabel }}</span>
                <svg class="h-3 w-3 shrink-0 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </BaseButton>
            </template>
          </BaseDropdown>
          <!-- Admin bulk tools -->
          <template v-if="authStore.isAdmin">
            <BaseButton variant="secondary" size="sm" :disabled="!filteredRequests.length" @click="exportResponsesJson">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
              Exportar solicitudes
            </BaseButton>
            <BaseButton variant="accent" size="md" @click="openImportModal">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
              Importar respuestas
            </BaseButton>
          </template>
          <!-- Client create button -->
          <BaseButton variant="accent" size="md" v-else :disabled="!projectRequirements.length" :title="projectRequirements.length ? '' : 'El equipo aún no ha cargado el tablero del proyecto.'" @click="openCreateModal">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
            Nueva solicitud
          </BaseButton>
        </div>
      </div>

      <!-- Status filter tabs -->
      <div class="mb-5 flex gap-1.5 overflow-x-auto pb-1" data-enter>
        <!-- design-tokens: allow-raw-button (native status filter tabs select the current list) -->
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          type="button"
          class="shrink-0 rounded-full px-3.5 py-1.5 text-xs font-medium transition"
          :class="activeFilter === tab.value
            ? 'bg-primary text-white dark:bg-accent dark:text-text-default'
            : 'text-green-light hover:bg-surface-muted/50 dark:hover:bg-white/10'"
          @click="activeFilter = tab.value"
        >
          {{ tab.label }}
          <span v-if="tab.count !== undefined" class="ml-1 opacity-60">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Table (md+) / Cards (mobile) -->
      <template v-if="filteredRequests.length">
      <div v-if="!isMobile" class="overflow-x-auto rounded-2xl border border-border-default bg-surface" data-enter>
        <table class="min-w-full text-left text-sm">
          <thead class="bg-surface-muted/40 text-xs font-medium uppercase tracking-wider text-green-light/70">
            <tr>
              <th class="px-4 py-3">Solicitud</th>
              <th class="px-4 py-3">Estado</th>
              <th class="px-4 py-3">Prioridad</th>
              <th class="px-4 py-3">Solicitado por</th>
              <th class="px-4 py-3">Fecha</th>
              <th class="w-10 px-2"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="cr in filteredRequests"
              :key="cr.id"
              class="border-t border-border-muted"
              :class="cr.is_archived ? 'opacity-70' : ''"
            >
              <td class="px-4 py-3">
                <div class="flex items-start gap-2">
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-1.5">
                    <BaseButton variant="link" size="sm" class="min-w-0 truncate text-left" @click="openDetailModal(cr)">{{ cr.title }}</BaseButton>
                      <span v-if="cr.is_urgent" class="rounded-full bg-red-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-red-600 dark:text-red-400">Urgente</span>
                      <span v-if="cr.is_archived" class="rounded-full bg-surface-raised px-1.5 py-0.5 text-[9px] font-semibold uppercase text-text-muted dark:text-text-subtle">Archivada</span>
                      <span v-if="cr.linked_requirement_id" class="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-semibold text-text-brand">Convertida</span>
                    </div>
                    <p v-if="cr.source_requirement" class="mt-0.5 line-clamp-1 text-[10px] text-teal-600 dark:text-teal-300">
                      Sobre: {{ cr.source_requirement.title }}
                    </p>
                    <p v-else-if="cr.module_or_screen" class="mt-0.5 line-clamp-1 text-[10px] text-green-light/60">{{ cr.module_or_screen }}</p>
                  </div>
                </div>
              </td>
              <td class="px-4 py-3">
                <select
                  v-if="authStore.isAdmin && !cr.is_archived"
                  :value="cr.status"
                  class="rounded-full border border-border-default bg-surface-muted/40 px-2 py-1 text-[10px] font-medium text-text-default outline-none focus:border-border-default dark:bg-primary-strong dark:text-white dark:focus:border-lemon/40"
                  @click.stop
                  @change="onQuickStatus(cr, $event.target.value)"
                >
                  <option value="pending">Pendiente</option>
                  <option value="evaluating">En evaluación</option>
                  <option value="approved">Aprobada</option>
                  <option value="rejected">Rechazada</option>
                  <option value="needs_clarification">Requiere aclaración</option>
                  <option value="out_of_scope">Fuera de alcance</option>
                </select>
                <span
                  v-else
                  class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase"
                  :class="statusBadgeClass(cr.status)"
                >
                  {{ statusLabel(cr.status) }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="priorityBadgeClass(cr.suggested_priority)">
                  {{ priorityLabel(cr.suggested_priority) }}
                </span>
              </td>
              <td class="px-4 py-3 text-xs text-green-light">{{ cr.created_by_name }}</td>
              <td class="px-4 py-3 text-xs text-green-light/70">{{ formatDate(cr.created_at) }}</td>
              <td class="px-2 py-3 text-right text-green-light/40">›</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Cards (mobile) -->
      <div v-else class="space-y-3" data-enter>
        <!-- design-tokens: allow-raw-button (selectable ticket card opens the detail dialog in place) -->
        <button
          v-for="cr in filteredRequests"
          :key="cr.id"
          type="button"
          class="block w-full rounded-2xl border border-border-default bg-surface p-4 text-left transition hover:bg-primary-soft"
          :class="cr.is_archived ? 'opacity-70' : ''"
          @click="openDetailModal(cr)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-1.5">
                <p class="font-medium text-text-default">{{ cr.title }}</p>
                <span v-if="cr.is_urgent" class="rounded-full bg-red-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-red-600 dark:text-red-400">Urgente</span>
                <span v-if="cr.is_archived" class="rounded-full bg-surface-raised px-1.5 py-0.5 text-[9px] font-semibold uppercase text-text-muted dark:text-text-subtle">Archivada</span>
                <span v-if="cr.linked_requirement_id" class="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-semibold text-text-brand">Convertida</span>
              </div>
              <p v-if="cr.source_requirement" class="mt-0.5 line-clamp-1 text-[10px] text-teal-600 dark:text-teal-300">Sobre: {{ cr.source_requirement.title }}</p>
              <p v-else-if="cr.module_or_screen" class="mt-0.5 line-clamp-1 text-[10px] text-green-light/60">{{ cr.module_or_screen }}</p>
            </div>
            <span class="shrink-0 text-green-light/40">›</span>
          </div>
          <div class="mt-3 flex flex-wrap items-center gap-2">
            <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="statusBadgeClass(cr.status)">{{ statusLabel(cr.status) }}</span>
            <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="priorityBadgeClass(cr.suggested_priority)">{{ priorityLabel(cr.suggested_priority) }}</span>
          </div>
          <div class="mt-2 flex items-center justify-between gap-2 text-xs text-green-light/70">
            <span class="truncate">{{ cr.created_by_name }}</span>
            <span class="shrink-0">{{ formatDate(cr.created_at) }}</span>
          </div>
        </button>
      </div>
      </template>

      <!-- Empty state -->
      <div v-else class="py-16 text-center" data-enter>
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-muted/50 dark:bg-white/5">
          <svg class="h-8 w-8 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
        </div>
        <p class="text-sm text-green-light">
          {{ activeFilter === 'all' ? 'No hay solicitudes de cambio aún.' : 'No hay solicitudes con este estado.' }}
        </p>
        <BaseButton variant="accent" size="md" class="mt-4" v-if="!authStore.isAdmin" @click="openCreateModal">
          Crear primera solicitud
        </BaseButton>
      </div>
</template>

    <!-- Create modal (client only) -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div
          v-if="isCreateOpen && !authStore.isAdmin"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm"
          @click.self="isCreateOpen = false"
        >
          <Transition name="modal-content" appear>
            <div v-if="isCreateOpen" class="w-full max-w-md rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <h2 class="mb-5 text-lg font-bold text-text-default">Nueva solicitud de cambio</h2>

              <form class="space-y-4" @submit.prevent="handleCreate">
                <IssueSourcePicker v-model="createForm.source_requirement_id" :options="projectRequirements" id="change-source" required />
                <p v-if="sourceError" role="alert" class="text-xs text-danger-strong">{{ sourceError }}</p>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Título <span class="text-red-400">*</span></label>
                  <input v-model="createForm.title" type="text" required placeholder="¿Qué cambio necesitas?" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Descripción</label>
                  <textarea v-model="createForm.description" rows="3" placeholder="Describe el cambio con el mayor detalle posible..." class="w-full resize-none rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Módulo / Pantalla</label>
                    <input v-model="createForm.module_or_screen" type="text" placeholder="Ej: Catálogo" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                  </div>
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Prioridad sugerida</label>
                    <select v-model="createForm.suggested_priority" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default dark:bg-primary-strong dark:text-white dark:focus:border-lemon/40">
                      <option value="low">Baja</option>
                      <option value="medium">Media</option>
                      <option value="high">Alta</option>
                      <option value="critical">Crítica</option>
                    </select>
                  </div>
                </div>
                <label class="flex items-center gap-2 text-xs text-green-light">
                  <input v-model="createForm.is_urgent" type="checkbox" class="rounded border-border-default" />
                  Marcar como urgente
                </label>

                <!-- Screenshot upload -->
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Pantallazo (opcional)</label>
                  <div
                    class="relative flex min-h-[80px] cursor-pointer items-center justify-center rounded-xl border-2 border-dashed border-border-default bg-surface-muted/20 transition hover:border-border-default dark:hover:border-white/20"
                    @click="$refs.screenshotInput.click()"
                    @dragover.prevent
                    @drop.prevent="handleScreenshotDrop"
                  >
                    <input ref="screenshotInput" type="file" accept="image/*" class="hidden" @change="handleScreenshotSelect" />
                    <div v-if="!screenshotPreview" class="py-4 text-center">
                      <svg class="mx-auto mb-1.5 h-6 w-6 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                      <p class="text-[11px] text-green-light/50">Arrastra o haz clic para subir</p>
                    </div>
                    <div v-else class="relative w-full p-2">
                      <img :src="screenshotPreview" alt="Preview" class="mx-auto max-h-32 rounded-lg object-contain" />
                      <BaseButton unstyled icon-only type="button" aria-label="Quitar pantallazo" class="absolute right-3 top-3 flex h-6 w-6 items-center justify-center rounded-full bg-black/50 text-white transition hover:bg-black/70" @click.stop="removeScreenshot">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                      </BaseButton>
                    </div>
                  </div>
                </div>

                <p v-if="crStore.error" role="alert" class="text-xs text-danger-strong">{{ crStore.error }}</p>
                <div class="flex justify-end gap-3 pt-2">
                  <BaseButton variant="ghost" size="md" @click="isCreateOpen = false">Cancelar</BaseButton>
                  <BaseButton variant="accent" size="md" type="submit" :disabled="!createForm.title.trim() || crStore.isUpdating">
                    {{ crStore.isUpdating ? 'Creando...' : 'Crear solicitud' }}
                  </BaseButton>
                </div>
              </form>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>

    <!-- Import responses modal (admin) -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div
          v-if="isImportOpen"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm"
          @click.self="closeImportModal"
        >
          <Transition name="modal-content" appear>
            <div v-if="isImportOpen" class="w-full max-w-2xl rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <div class="mb-5 flex items-start justify-between gap-4">
                <div>
                  <h2 class="text-lg font-bold text-text-default">Importar respuestas (JSON)</h2>
                  <p class="mt-1 text-xs text-green-light/70">
                    Pega un array con `id` + los campos a actualizar (`status`, `admin_response`, `estimated_time`, `estimated_cost`).
                    Los ítems se aplican por id, los demás se ignoran.
                  </p>
                </div>
                <BaseButton unstyled icon-only type="button" aria-label="Cerrar importación" class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-green-light transition hover:bg-surface-muted hover:text-text-default dark:hover:bg-white/10 dark:hover:text-white" @click="closeImportModal">
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </BaseButton>
              </div>

              <form class="space-y-4" @submit.prevent="handleImportResponses">
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">JSON</label>
                  <textarea
                    v-model="importJson"
                    rows="14"
                    spellcheck="false"
                    placeholder='[{"id": 1, "status": "approved", "admin_response": "...", "estimated_time": "2 semanas", "estimated_cost": 500000}]'
                    class="w-full resize-y rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 font-mono text-xs text-text-default outline-none transition placeholder:text-green-light/40 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/20 dark:focus:border-lemon/40"
                  />
                </div>

                <p v-if="importError" class="rounded-xl border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-600 dark:text-red-400">
                  {{ importError }}
                </p>

                <div class="flex justify-end gap-3 pt-2">
                  <BaseButton variant="ghost" size="md" @click="closeImportModal">Cancelar</BaseButton>
                  <BaseButton variant="accent" size="md" type="submit" :disabled="!importJson.trim() || importLoading">
                    {{ importLoading ? 'Aplicando...' : 'Aplicar respuestas' }}
                  </BaseButton>
                </div>
              </form>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>

    <!-- Detail modal -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div
          v-if="detailCR"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm"
          @click.self="detailCR = null"
        >
          <Transition name="modal-content" appear>
            <div v-if="detailCR" class="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <!-- Header -->
              <div class="mb-5 flex items-start justify-between gap-4">
                <div class="flex-1">
                  <div class="mb-2 flex flex-wrap items-center gap-2">
                    <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase" :class="statusBadgeClass(detailCR.status)">{{ statusLabel(detailCR.status) }}</span>
                    <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="priorityBadgeClass(detailCR.suggested_priority)">{{ priorityLabel(detailCR.suggested_priority) }}</span>
                    <span v-if="detailCR.is_archived" class="rounded-full bg-surface-raised px-2 py-0.5 text-[10px] font-semibold uppercase text-text-muted dark:text-text-subtle">Archivado</span>
                    <span v-if="detailCR.is_urgent" class="rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold uppercase text-red-600 dark:text-red-400">Urgente</span>
                  </div>
                  <p v-if="detailCR.is_archived && detailCR.archived_at" class="mb-1 text-[10px] text-green-light/60">
                    Archivado el {{ formatDate(detailCR.archived_at) }}
                  </p>
                  <h2 class="text-lg font-bold text-text-default">{{ detailCR.title }}</h2>
                </div>
                <BaseButton unstyled icon-only type="button" aria-label="Cerrar detalle" class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-green-light transition hover:bg-surface-muted hover:text-text-default dark:hover:bg-white/10 dark:hover:text-white" @click="detailCR = null">
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </BaseButton>
              </div>

              <!-- Source requirement -->
              <div v-if="detailCR.source_requirement" class="mb-5 rounded-xl border border-teal-500/20 bg-teal-500/5 p-4">
                <p class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-teal-600 dark:text-teal-300">Sobre el requerimiento</p>
                <p class="text-sm font-medium text-text-default">{{ detailCR.source_requirement.title }}</p>
                <p v-if="detailCR.source_requirement.phase_title" class="mt-0.5 text-[11px] text-green-light/70">
                  Fase: {{ detailCR.source_requirement.phase_title }}
                </p>
                <NuxtLink
                  :to="localePath(`/platform/projects/${projectId}/delivery?stage=${detailCR.source_requirement.stage_id}#requirement-${detailCR.source_requirement.id}`)"
                  class="mt-2 inline-flex items-center gap-1 text-xs font-medium text-text-brand underline decoration-text-brand/30 transition hover:decoration-text-brand dark:text-accent dark:decoration-accent/30 dark:hover:decoration-accent"
                >
                  {{ t('platformDelivery.seeDelivery') }}
                  <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7-7 7M5 12h16" /></svg>
                </NuxtLink>
              </div>

              <IssueHistory :ticket="detailCR" />

              <!-- Description -->
              <div v-if="detailCR.description" class="mb-5 rounded-xl border border-border-muted bg-surface-muted/20 p-4 text-sm leading-relaxed text-green-light">
                {{ detailCR.description }}
              </div>

              <!-- Screenshot -->
              <div v-if="detailCR.screenshot_url" class="mb-5">
                <!-- icon-interaction-feedback: allow-custom -- full screenshot preview link, not an icon control. -->
                <a :href="detailCR.screenshot_url" target="_blank" class="block overflow-hidden rounded-xl border border-border-default transition hover:border-border-default dark:hover:border-white/15">
                  <img :src="detailCR.screenshot_url" alt="Pantallazo" class="w-full object-contain" style="max-height: 300px" />
                </a>
              </div>

              <!-- Meta -->
              <div class="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Módulo</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ detailCR.module_or_screen || '—' }}</p>
                </div>
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Solicitado por</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ detailCR.created_by_name }}</p>
                </div>
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Fecha</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ formatDate(detailCR.created_at) }}</p>
                </div>
              </div>

              <!-- Admin response -->
              <div v-if="detailCR.admin_response" class="mb-5 rounded-xl border-l-2 border-l-esmerald/30 bg-surface-muted/20 p-4 dark:border-l-lemon/40">
                <p class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-esmerald/60 dark:text-lemon/60">Respuesta del equipo</p>
                <p class="text-sm leading-relaxed text-green-light">{{ detailCR.admin_response }}</p>
                <div v-if="detailCR.estimated_time || detailCR.estimated_cost" class="mt-3 flex flex-wrap gap-3">
                  <span v-if="detailCR.estimated_time" class="flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-[10px] font-semibold text-text-default dark:bg-white/10 dark:text-white">
                    <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="1.5" /><path d="M12 6v6l4 2" stroke-width="1.5" /></svg>
                    {{ detailCR.estimated_time }}
                  </span>
                  <span v-if="detailCR.estimated_cost !== null && detailCR.estimated_cost !== undefined" class="flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-[10px] font-semibold text-text-default dark:bg-white/10 dark:text-white">
                    ${{ Number(detailCR.estimated_cost).toLocaleString('es-CO') }}
                  </span>
                </div>
              </div>

              <!-- Linked requirement -->
              <div v-if="detailCR.linked_requirement_id" class="mb-5 flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
                <svg class="h-4 w-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span class="text-xs font-medium text-text-brand">Convertida en requerimiento #{{ detailCR.linked_requirement_id }}</span>
              </div>

              <!-- Admin actions -->
              <div v-if="authStore.isAdmin" class="mb-5 space-y-3">
                <div v-if="detailCR.is_archived" class="rounded-xl border border-border-default px-4 py-3 text-xs text-green-light/70">
                  Esta solicitud está archivada.
                </div>
                <template v-else>
                  <div v-if="showEvaluateForm" class="rounded-xl border border-border-default p-4">
                    <p class="mb-3 text-xs font-semibold uppercase tracking-wider text-green-light/60">Evaluar solicitud</p>
                    <div class="space-y-3">
                      <div>
                        <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Estado</label>
                        <select v-model="evalForm.status" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none focus:border-border-default dark:bg-primary-strong dark:text-white dark:focus:border-lemon/40">
                          <option value="pending">Pendiente</option>
                          <option value="evaluating">En evaluación</option>
                          <option value="approved">Aprobada</option>
                          <option value="rejected">Rechazada</option>
                          <option value="needs_clarification">Requiere aclaración</option>
                          <option value="out_of_scope">Fuera de alcance</option>
                        </select>
                      </div>
                      <div>
                        <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Respuesta</label>
                        <textarea v-model="evalForm.admin_response" rows="2" :placeholder="t('platformIssues.responsePlaceholder')" class="w-full resize-none rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                      </div>
                      <IssueEvidenceFields v-model="responseEvidence" :project-id="projectId" kind="change" :ticket-id="detailCR.id" admin id="change-response-evidence" />
                      <p v-if="crStore.error" role="alert" class="text-xs text-danger-strong">{{ crStore.error }}</p>
                      <div class="grid grid-cols-2 gap-3">
                        <div>
                          <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Tiempo estimado</label>
                          <input v-model="evalForm.estimated_time" type="text" placeholder="Ej: 2 semanas" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                        </div>
                        <div>
                          <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Costo estimado</label>
                          <input v-model.number="evalForm.estimated_cost" type="number" min="0" step="1000" placeholder="0" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                        </div>
                      </div>
                      <div class="flex justify-end gap-2">
                        <BaseButton variant="ghost" size="sm" @click="showEvaluateForm = false">Cancelar</BaseButton>
                        <BaseButton variant="accent" size="sm" :disabled="crStore.isUpdating" @click="handleEvaluate">
                          {{ crStore.isUpdating ? 'Guardando...' : 'Guardar evaluación' }}
                        </BaseButton>
                      </div>
                    </div>
                  </div>

                  <div v-else class="flex flex-wrap gap-2">
                    <BaseButton variant="secondary" size="sm" @click="openEvaluateForm">
                      Evaluar
                    </BaseButton>
                    <BaseButton variant="primary" size="sm" v-if="detailCR.status === 'approved' && !detailCR.linked_requirement_id" :disabled="crStore.isUpdating" @click="openConvert">
                      {{ t('platformDelivery.convert') }}
                    </BaseButton>
                    <BaseButton variant="danger-ghost" size="sm" :disabled="crStore.isUpdating" @click="handleDelete">
                      Archivar
                    </BaseButton>
                  </div>
                </template>
              </div>

              <!-- Comments -->
              <div class="mb-4">
                <p class="mb-3 text-xs font-semibold uppercase tracking-wider text-green-light/60">
                  Comentarios{{ detailCR.comments ? ` (${detailCR.comments.length})` : '' }}
                </p>

                <div v-if="detailCR.comments && detailCR.comments.length" class="mb-4 space-y-3">
                  <div
                    v-for="comment in detailCR.comments"
                    :key="comment.id"
                    class="rounded-xl border border-border-muted p-3"
                    :class="comment.is_internal ? 'border-l-2 border-l-amber-400' : ''"
                  >
                    <div class="mb-1 flex items-center justify-between">
                      <span class="text-xs font-medium text-text-default">{{ comment.user_name }}</span>
                      <span class="text-[10px] text-green-light/40">{{ formatDate(comment.created_at) }}</span>
                    </div>
                    <p class="text-sm leading-relaxed text-green-light">{{ comment.content }}</p>
                    <IssueAttachments :attachments="comment.attachments" />
                    <span v-if="comment.is_internal" class="mt-1 inline-block text-[9px] font-semibold uppercase tracking-wider text-amber-500">Interno</span>
                  </div>
                </div>

                <!-- Add comment -->
                <form class="flex gap-2" @submit.prevent="handleAddComment">
                  <input
                    v-model="newComment"
                    type="text"
                    placeholder="Escribe un comentario..."
                    class="flex-1 rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40"
                  />
                  <BaseButton variant="accent" size="md" type="submit" :disabled="!newComment.trim()">
                    Enviar
                  </BaseButton>
                </form>
                <IssueEvidenceFields v-if="!detailCR.is_archived" v-model="commentEvidence" :project-id="projectId" kind="change" :ticket-id="detailCR.id" id="change-comment-evidence" />
                <p v-if="crStore.error && !showEvaluateForm" role="alert" class="mt-2 text-xs text-danger-strong">{{ crStore.error }}</p>
                <label v-if="authStore.isAdmin" class="mt-2 flex items-center gap-2 text-xs text-green-light/60">
                  <input v-model="commentInternal" type="checkbox" class="rounded border-border-default" />
                  Comentario interno (solo admins)
                </label>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>
  </div>
    <BaseModal v-model="isConvertOpen" kind="form">
      <form class="space-y-5 p-4 sm:p-6" @submit.prevent="handleConvert">
        <h2 class="text-lg font-semibold text-text-default">{{ t('platformDelivery.convert') }}</h2>
        <p class="text-sm text-text-muted">{{ t('platformDelivery.selectDraftStage') }}</p>
        <BaseAlert v-if="convertError" variant="danger" role="alert">{{ convertError }}</BaseAlert>
        <BaseFormField :label="t('platformDelivery.draftStage')" for="change-request-stage" required>
          <BaseSelect id="change-request-stage" v-model="convertStageId" :options="draftStageOptions" :placeholder="t('platformDelivery.select')" />
        </BaseFormField>
        <BaseModalActions><BaseButton variant="ghost" @click="isConvertOpen = false">{{ t('platformDelivery.cancel') }}</BaseButton><BaseButton type="submit" :loading="crStore.isUpdating">{{ t('platformDelivery.convert') }}</BaseButton></BaseModalActions>
      </form>
    </BaseModal>
  </ProjectShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { useIsMobile } from '~/composables/useIsMobile'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformChangeRequestsStore } from '~/stores/platform-change-requests'
import { usePlatformProjectsStore } from '~/stores/platform-projects'
import { usePlatformIssueReportsStore } from '~/stores/platform-issue-reports'
import { issueSourcePayload, prefillIssueGuide } from '~/utils/issue-reports'
import IssueSourcePicker from '~/components/platform/issues/IssueSourcePicker.vue'
import IssueHistory from '~/components/platform/issues/IssueHistory.vue'
import IssueAttachments from '~/components/platform/issues/IssueAttachments.vue'
import IssueEvidenceFields from '~/components/platform/issues/IssueEvidenceFields.vue'
import { usePlatformDeliveryStore } from '~/stores/platform-delivery'
import { formatDate } from '~/utils/formatDate'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'

definePageMeta({
  layout: 'platform',
  middleware: ['platform-auth'],
})

usePageEntrance('#platform-changes')

const route = useRoute()
const localePath = useLocalePath()
const { t } = useI18n()
const authStore = usePlatformAuthStore()
const crStore = usePlatformChangeRequestsStore()
const projectsStore = usePlatformProjectsStore()
const issueStore = usePlatformIssueReportsStore()
const sourceError = ref('')
const responseEvidence = ref({ contract_id: null, document_ids: [] })
const commentEvidence = ref({ document_ids: [] })
const deliveryStore = usePlatformDeliveryStore()
const isConvertOpen = ref(false)
const convertStageId = ref('')
const convertError = ref('')
const draftStageOptions = computed(() => deliveryStore.scopes
  .filter((scope) => !detailCR.value?.origin_context?.contract_id || scope.contract_id === detailCR.value.origin_context.contract_id)
  .flatMap((scope) => scope.phases.flatMap((phase) => phase.stages))
  .filter((stage) => stage.editorial_status === 'draft' && stage.status !== 'approved')
  .map((stage) => ({ value: stage.id, label: stage.title })))

const { isMobile } = useIsMobile()

const projectRequirements = ref([])

const projectId = computed(() => route.params.id)
const projectName = computed(() => projectsStore.currentProject?.name || 'Proyecto')

const activeFilter = ref('all')

const statusTabs = computed(() => [
  { value: 'all', label: 'Todas', count: crStore.changeRequests.length },
  { value: 'pending', label: 'Pendientes', count: crStore.pendingCount },
  { value: 'evaluating', label: 'En evaluación', count: crStore.evaluatingCount },
  { value: 'approved', label: 'Aprobadas', count: crStore.approvedCount },
  { value: 'rejected', label: 'Rechazadas', count: crStore.rejectedCount },
  { value: 'needs_clarification', label: 'Requiere aclaración' },
  { value: 'out_of_scope', label: 'Fuera de alcance' },
])

const selectedPhaseId = ref(null)
const phaseOptions = computed(() => [...new Map(projectRequirements.value
  .filter((requirement) => requirement.phase_id)
  .map((requirement) => [requirement.phase_id, { id: requirement.phase_id, title: requirement.phase_title }])).values()])
const selectedPhaseLabel = computed(() => phaseOptions.value.find((phase) => phase.id === selectedPhaseId.value)?.title || 'Todas las fases')
const phaseDropdownItems = computed(() => [
  { label: 'Todas las fases', onClick: () => { selectedPhaseId.value = null } },
  ...phaseOptions.value.map((phase) => ({ label: phase.title, onClick: () => { selectedPhaseId.value = phase.id } })),
])

const filteredRequests = computed(() => {
  let list = crStore.filteredByStatus(activeFilter.value)
  if (selectedPhaseId.value) {
    list = list.filter((cr) => cr.source_requirement?.phase_id === selectedPhaseId.value)
  }
  return list
})

const isImportOpen = ref(false)
const importJson = ref('')
const importError = ref('')
const importLoading = ref(false)

const isCreateOpen = ref(false)
const createForm = reactive({
  title: '',
  description: '',
  module_or_screen: '',
  suggested_priority: 'medium',
  is_urgent: false,
  source_requirement_id: null,
})

const screenshotFile = ref(null)
const screenshotPreview = ref(null)

const detailCR = ref(null)
const newComment = ref('')
const commentInternal = ref(false)
const showEvaluateForm = ref(false)
const evalForm = reactive({
  status: 'evaluating',
  admin_response: '',
  estimated_time: '',
  estimated_cost: null,
})

function statusBadgeClass(s) {
  const map = {
    pending: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    evaluating: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
    approved: 'bg-emerald-500/15 text-text-brand',
    rejected: 'bg-red-500/15 text-red-600 dark:text-red-400',
    needs_clarification: 'bg-purple-500/15 text-purple-600 dark:text-purple-400',
    out_of_scope: 'bg-surface-raised text-text-muted',
  }
  return map[s] || map.pending
}

function statusLabel(s) {
  const map = {
    pending: 'Pendiente',
    evaluating: 'En evaluación',
    approved: 'Aprobada',
    rejected: 'Rechazada',
    needs_clarification: 'Requiere aclaración',
    out_of_scope: 'Fuera de alcance',
  }
  return map[s] || s
}

function priorityBadgeClass(p) {
  const map = {
    critical: 'bg-red-500/15 text-red-600 dark:text-red-400',
    high: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    medium: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
    low: 'bg-surface-raised text-text-muted',
  }
  return map[p] || map.medium
}

function priorityLabel(p) {
  const map = { critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja' }
  return map[p] || p
}

function openCreateModal() {
  crStore.error = ''
  if (!projectRequirements.value.length) return
  createForm.title = ''
  createForm.description = ''
  createForm.module_or_screen = ''
  createForm.suggested_priority = 'medium'
  createForm.is_urgent = false
  createForm.source_requirement_id = null
  screenshotFile.value = null
  screenshotPreview.value = null
  // Honor ?from_req=X&title=Y from delivery.vue deep-link
  const fromReq = Number(route.query.from_req)
  if (fromReq && projectRequirements.value.some((r) => r.id === fromReq)) {
    createForm.source_requirement_id = fromReq
  }
  if (typeof route.query.title === 'string') {
    createForm.title = route.query.title
  }
  isCreateOpen.value = true
}

function handleScreenshotSelect(event) {
  const file = event.target.files?.[0]
  if (!file) return
  setScreenshot(file)
}

function handleScreenshotDrop(event) {
  const file = event.dataTransfer.files?.[0]
  if (!file || !file.type.startsWith('image/')) return
  setScreenshot(file)
}

function setScreenshot(file) {
  screenshotFile.value = file
  screenshotPreview.value = URL.createObjectURL(file)
}

function removeScreenshot() {
  screenshotFile.value = null
  if (screenshotPreview.value) URL.revokeObjectURL(screenshotPreview.value)
  screenshotPreview.value = null
}

async function handleCreate() {
  if (!createForm.title.trim() || !createForm.source_requirement_id) return
  let payload
  if (screenshotFile.value) {
    payload = new FormData()
    payload.append('title', createForm.title)
    payload.append('description', createForm.description)
    payload.append('module_or_screen', createForm.module_or_screen)
    payload.append('suggested_priority', createForm.suggested_priority)
    payload.append('is_urgent', createForm.is_urgent)
    payload.append('source_requirement_id', String(createForm.source_requirement_id))
    payload.append('screenshot', screenshotFile.value)
  } else {
    payload = { ...createForm }
  }
  const source = issueSourcePayload(projectRequirements.value.find((row) => row.id === createForm.source_requirement_id))
  if (payload instanceof FormData) {
    Object.entries(source).forEach(([key, value]) => payload.set(key, String(value)))
    payload.set('request_id', crypto.randomUUID())
  } else {
    Object.assign(payload, source, { request_id: crypto.randomUUID() })
  }
  const result = await crStore.createChangeRequest(projectId.value, payload)
  if (result.success) {
    if (screenshotPreview.value) URL.revokeObjectURL(screenshotPreview.value)
    isCreateOpen.value = false
  }
}

async function openDetailModal(cr) {
  detailCR.value = cr
  newComment.value = ''
  commentInternal.value = false
  showEvaluateForm.value = false
  const result = await crStore.fetchChangeRequest(projectId.value, cr.id)
  if (result.success) detailCR.value = result.data
}

function openEvaluateForm() {
  evalForm.status = detailCR.value?.status || 'evaluating'
  evalForm.admin_response = ''
  responseEvidence.value = { contract_id: detailCR.value?.origin_context?.contract_id || null, document_ids: [] }
  evalForm.estimated_time = detailCR.value?.estimated_time || ''
  evalForm.estimated_cost = detailCR.value?.estimated_cost || null
  showEvaluateForm.value = true
}

async function handleEvaluate() {
  if (!detailCR.value) return
  const payload = { ...evalForm, ...responseEvidence.value, expected_version: detailCR.value.version, request_id: crypto.randomUUID() }
  if (!payload.estimated_cost) payload.estimated_cost = null
  const result = await crStore.evaluateChangeRequest(projectId.value, detailCR.value.id, payload)
  if (result.success) {
    detailCR.value = result.data
    showEvaluateForm.value = false
  }
}

async function openConvert() {
  convertStageId.value = ''
  convertError.value = ''
  const result = await deliveryStore.fetchDelivery(projectId.value)
  if (!result.success) { convertError.value = result.message || t('platformDelivery.loadError') }
  isConvertOpen.value = true
}

async function handleConvert() {
  if (!detailCR.value) return
  if (!convertStageId.value) { convertError.value = t('platformDelivery.fieldRequired'); return }
  const result = await crStore.convertToRequirement(projectId.value, detailCR.value.id, { stage_id: Number(convertStageId.value), expected_version: deliveryStore.version, issue_version: detailCR.value.version, request_id: crypto.randomUUID() })
  if (result.success) {
    detailCR.value = result.data
    isConvertOpen.value = false
  } else {
    convertError.value = result.message || t('platformDelivery.actionError')
  }
}

async function handleDelete() {
  if (!detailCR.value) return
  if (!window.confirm('¿Archivar esta solicitud de cambio? Podrás verla otra vez activando "Mostrar archivados".')) return
  const result = await crStore.deleteChangeRequest(projectId.value, detailCR.value.id)
  if (result.success) {
    detailCR.value = null
  }
}


async function loadChangeRequests() {
  await crStore.fetchChangeRequests(projectId.value, null, false)
}

async function loadProjectRequirements() {
  const r = await issueStore.contextOptions(projectId.value, {
    ...(route.query.from_pub ? { source_publication_id: Number(route.query.from_pub), source_requirement_id: Number(route.query.from_req) } : {}),
  })
  projectRequirements.value = r.success ? (r.data.requirements || []) : []
  sourceError.value = r.success ? '' : r.message
}

async function onQuickStatus(cr, newStatus) {
  if (!newStatus || newStatus === cr.status) return
  const result = await crStore.evaluateChangeRequest(projectId.value, cr.id, { status: newStatus, expected_version: cr.version, request_id: crypto.randomUUID() })
  if (!result.success) {
    window.alert(result.message || 'No pudimos actualizar el estado.')
  }
}

function exportResponsesJson() {
  const rows = filteredRequests.value.map((cr) => ({
    id: cr.id,
    title: cr.title,
    status: cr.status,
    admin_response: cr.admin_response || '',
    estimated_time: cr.estimated_time || '',
    estimated_cost: cr.estimated_cost ?? null,
  }))
  const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const tab = activeFilter.value === 'all' ? 'todas' : activeFilter.value
  a.download = `solicitudes-${projectId.value}-${tab}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function openImportModal() {
  importJson.value = ''
  importError.value = ''
  isImportOpen.value = true
}

function closeImportModal() {
  isImportOpen.value = false
  importError.value = ''
}

async function handleImportResponses() {
  importError.value = ''
  let items
  try {
    items = JSON.parse(importJson.value)
  } catch {
    importError.value = 'JSON inválido. Verificá la sintaxis.'
    return
  }
  if (!Array.isArray(items)) {
    importError.value = 'El JSON debe ser un array de objetos.'
    return
  }
  if (items.length === 0) {
    importError.value = 'El array está vacío.'
    return
  }
  if (items.some((it) => !it || typeof it !== 'object' || it.id == null)) {
    importError.value = 'Cada ítem debe tener el campo "id".'
    return
  }

  importLoading.value = true
  try {
    const result = await crStore.bulkEvaluateChangeRequests(projectId.value, items)
    if (result.success) {
      await loadChangeRequests()
      const { updated, errors } = result.data || {}
      if (errors && errors.length) {
        importError.value = `Se aplicaron ${updated || 0}. ${errors.length} con error: ${JSON.stringify(errors).slice(0, 200)}`
      } else {
        closeImportModal()
      }
    } else {
      importError.value = result.message
    }
  } finally {
    importLoading.value = false
  }
}

async function handleAddComment() {
  if (!newComment.value.trim() || !detailCR.value) return
  const result = await crStore.addComment(projectId.value, detailCR.value.id, newComment.value.trim(), commentInternal.value, { document_ids: commentEvidence.value.document_ids, expected_version: detailCR.value.version, request_id: crypto.randomUUID() })
  if (result.success) {
    newComment.value = ''
    commentInternal.value = false
    commentEvidence.value = { document_ids: [] }
    const updated = await crStore.fetchChangeRequest(projectId.value, detailCR.value.id)
    if (updated.success) detailCR.value = updated.data
  }
}

watch(() => createForm.source_requirement_id, (id) => {
  prefillIssueGuide(createForm, projectRequirements.value.find((row) => row.id === id))
})

onMounted(async () => {
  await Promise.all([
    loadChangeRequests(),
    loadProjectRequirements(),
    projectsStore.currentProject?.id !== Number(projectId.value)
      ? projectsStore.fetchProject(projectId.value)
      : Promise.resolve(),
  ])
  // Deep-link from deliveries: ?from_req=X&title=Y → auto-open create modal (client only)
  if (!authStore.isAdmin && route.query.from_req && projectRequirements.value.length) {
    openCreateModal()
  }
})

watch(projectId, () => {
  loadChangeRequests()
  loadProjectRequirements()
})
</script>

<style scoped>
.modal-overlay-enter-active,
.modal-overlay-leave-active { transition: opacity 0.25s ease; }
.modal-overlay-enter-from,
.modal-overlay-leave-to { opacity: 0; }
.modal-content-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-content-leave-active { transition: all 0.2s ease-in; }
.modal-content-enter-from { opacity: 0; transform: scale(0.95) translateY(10px); }
.modal-content-leave-to { opacity: 0; transform: scale(0.97); }
</style>
