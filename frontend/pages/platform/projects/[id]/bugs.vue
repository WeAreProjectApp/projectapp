<template>
  <ProjectShell>
    <div id="platform-bugs">
    <!-- Loading -->
    <div v-if="bugStore.isLoading && !bugStore.bugReports.length" class="py-20 text-center">
      <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-esmerald dark:border-t-lemon" />
    </div>

    <template v-else>
      <!-- Header -->
      <div class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between" data-enter>
        <div>
          <h1 class="text-xl font-bold text-text-default sm:text-2xl">Reporte de bugs</h1>
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
          <template v-if="authStore.isAdmin">
            <BaseButton variant="secondary" size="sm" :disabled="!filteredBugs.length" @click="exportResponsesJson">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
              Exportar bugs
            </BaseButton>
            <BaseButton variant="accent" size="md" @click="openImportModal">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
              Importar respuestas
            </BaseButton>
          </template>
          <BaseButton variant="accent" size="md" v-else @click="openCreateModal">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
            Reportar bug
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

      <!-- Table -->
      <template v-if="filteredBugs.length">
      <div v-if="!isMobile" class="overflow-x-auto rounded-2xl border border-border-default bg-surface" data-enter>
        <table class="min-w-full text-left text-sm">
          <thead class="bg-surface-muted/40 text-xs font-medium uppercase tracking-wider text-green-light/70">
            <tr>
              <th class="px-4 py-3">Bug</th>
              <th class="px-4 py-3">Estado</th>
              <th class="px-4 py-3">Severidad</th>
              <th class="px-4 py-3">Entorno</th>
              <th class="px-4 py-3">Reportado por</th>
              <th class="px-4 py-3">Fecha</th>
              <th class="w-10 px-2"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="bug in filteredBugs"
              :key="bug.id"
              class="border-t border-border-muted"
              :class="bug.is_archived ? 'opacity-70' : ''"
            >
              <td class="px-4 py-3">
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-1.5">
                    <BaseButton variant="link" size="sm" class="min-w-0 truncate text-left" @click="openDetailModal(bug)">{{ bug.title }}</BaseButton>
                    <span v-if="bug.is_recurring" class="rounded-full bg-purple-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-purple-600 dark:text-purple-400">Recurrente</span>
                    <span v-if="bug.is_archived" class="rounded-full bg-surface-raised px-1.5 py-0.5 text-[9px] font-semibold uppercase text-text-muted dark:text-text-subtle">Archivado</span>
                    <svg v-if="bug.screenshot_url" class="h-3 w-3 shrink-0 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                  </div>
                  <p v-if="bug.source_requirement" class="mt-0.5 line-clamp-1 text-[10px] text-teal-600 dark:text-teal-300">
                    Sobre: {{ bug.source_requirement.title }}
                  </p>
                </div>
              </td>
              <td class="px-4 py-3">
                <select
                  v-if="authStore.isAdmin && !bug.is_archived"
                  :value="bug.status"
                  class="rounded-full border border-border-default bg-surface-muted/40 px-2 py-1 text-[10px] font-medium text-text-default outline-none focus:border-border-default dark:bg-primary-strong dark:text-white dark:focus:border-lemon/40"
                  @click.stop
                  @change="onQuickStatus(bug, $event.target.value)"
                >
                  <option value="reported">Reportado</option>
                  <option value="confirmed">Confirmado</option>
                  <option value="fixing">En corrección</option>
                  <option value="qa">En QA</option>
                  <option value="resolved">{{ t('platformIssues.status.resolved') }}</option>
                  <option value="not_reproducible">No reproducible</option>
                  <option value="wont_fix">No se corregirá</option>
                  <option value="duplicate">Duplicado</option>
                </select>
                <span
                  v-else
                  class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase"
                  :class="statusBadgeClass(bug.status)"
                >
                  {{ statusLabel(bug.status) }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="severityBadgeClass(bug.severity)">
                  {{ severityLabel(bug.severity) }}
                </span>
              </td>
              <td class="px-4 py-3 text-xs text-green-light/70">{{ envLabel(bug.environment) }}</td>
              <td class="px-4 py-3 text-xs text-green-light">{{ bug.reported_by_name }}</td>
              <td class="px-4 py-3 text-xs text-green-light/70">{{ formatDate(bug.created_at) }}</td>
              <td class="px-2 py-3 text-right text-green-light/40">›</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Cards (mobile) -->
      <div v-else class="space-y-3" data-enter>
        <!-- design-tokens: allow-raw-button (selectable ticket card opens the detail dialog in place) -->
        <button
          v-for="bug in filteredBugs"
          :key="bug.id"
          type="button"
          class="block w-full rounded-2xl border border-border-default bg-surface p-4 text-left transition hover:bg-primary-soft"
          :class="bug.is_archived ? 'opacity-70' : ''"
          @click="openDetailModal(bug)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-1.5">
                <p class="font-medium text-text-default">{{ bug.title }}</p>
                <span v-if="bug.is_recurring" class="rounded-full bg-purple-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-purple-600 dark:text-purple-400">Recurrente</span>
                <span v-if="bug.is_archived" class="rounded-full bg-surface-raised px-1.5 py-0.5 text-[9px] font-semibold uppercase text-text-muted dark:text-text-subtle">Archivado</span>
                <svg v-if="bug.screenshot_url" class="h-3 w-3 shrink-0 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
              </div>
              <p v-if="bug.source_requirement" class="mt-0.5 line-clamp-1 text-[10px] text-teal-600 dark:text-teal-300">Sobre: {{ bug.source_requirement.title }}</p>
            </div>
            <span class="shrink-0 text-green-light/40">›</span>
          </div>
          <div class="mt-3 flex flex-wrap items-center gap-2">
            <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="statusBadgeClass(bug.status)">{{ statusLabel(bug.status) }}</span>
            <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="severityBadgeClass(bug.severity)">{{ severityLabel(bug.severity) }}</span>
            <span class="text-[10px] text-green-light/60">{{ envLabel(bug.environment) }}</span>
          </div>
          <div class="mt-2 flex items-center justify-between gap-2 text-xs text-green-light/70">
            <span class="truncate">{{ bug.reported_by_name }}</span>
            <span class="shrink-0">{{ formatDate(bug.created_at) }}</span>
          </div>
        </button>
      </div>
      </template>

      <!-- Empty -->
      <div v-else class="py-16 text-center" data-enter>
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-muted/50 dark:bg-white/5">
          <svg class="h-8 w-8 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>
        </div>
        <p class="text-sm text-green-light">
          {{ activeFilter === 'all' ? 'No hay bugs reportados aún.' : 'No hay bugs con este estado.' }}
        </p>
        <BaseButton variant="accent" size="md" class="mt-4" v-if="!authStore.isAdmin" @click="openCreateModal">
          Reportar primer bug
        </BaseButton>
      </div>
</template>

    <!-- Create modal (client only) -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div v-if="isCreateOpen && !authStore.isAdmin" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm" @click.self="isCreateOpen = false">
          <Transition name="modal-content" appear>
            <div v-if="isCreateOpen" class="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <h2 class="mb-5 text-lg font-bold text-text-default">Reportar bug</h2>

              <form class="space-y-4" @submit.prevent="handleCreate">
                <IssueSourcePicker v-model="createForm.source_requirement_id" :options="projectRequirements" id="bug-source" />
                <p v-if="sourceError" role="alert" class="text-xs text-danger-strong">{{ sourceError }}</p>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Título <span class="text-red-400">*</span></label>
                  <input v-model="createForm.title" type="text" required placeholder="¿Qué está fallando?" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Descripción</label>
                  <textarea v-model="createForm.description" rows="2" placeholder="Describe el error con detalle..." class="w-full resize-none rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                </div>

                <!-- Steps to reproduce -->
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Pasos para reproducir</label>
                  <div class="space-y-2">
                    <div v-for="(step, i) in createForm.steps_to_reproduce" :key="i" class="flex items-center gap-2">
                      <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-green-light dark:bg-white/10">{{ i + 1 }}</span>
                      <input v-model="createForm.steps_to_reproduce[i]" type="text" :placeholder="`Paso ${i + 1}`" class="flex-1 rounded-lg border border-border-default bg-surface-muted/40 px-3 py-2 text-sm text-text-default outline-none placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                      <BaseButton variant="danger-ghost" icon-only size="sm" class="shrink-0" aria-label="Eliminar" v-if="createForm.steps_to_reproduce.length > 1" @click="createForm.steps_to_reproduce.splice(i, 1)">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                      </BaseButton>
                    </div>
                    <button type="button" class="text-xs font-medium text-esmerald/60 transition hover:text-text-default/60 dark:hover:text-white" @click="createForm.steps_to_reproduce.push('')">
                      + Agregar paso
                    </button>
                  </div>
                </div>

                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Comportamiento esperado</label>
                    <textarea v-model="createForm.expected_behavior" rows="2" placeholder="¿Qué debería pasar?" class="w-full resize-none rounded-xl border border-border-default bg-surface-muted/40 px-3 py-2.5 text-sm text-text-default outline-none placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                  </div>
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Comportamiento actual</label>
                    <textarea v-model="createForm.actual_behavior" rows="2" placeholder="¿Qué pasa realmente?" class="w-full resize-none rounded-xl border border-border-default bg-surface-muted/40 px-3 py-2.5 text-sm text-text-default outline-none placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                  </div>
                </div>

                <div class="grid grid-cols-3 gap-3">
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Severidad</label>
                    <select v-model="createForm.severity" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-3 py-2.5 text-sm text-text-default outline-none focus:border-border-default dark:bg-primary-strong dark:text-white dark:focus:border-lemon/40">
                      <option value="low">Baja</option>
                      <option value="medium">Media</option>
                      <option value="high">Alta</option>
                      <option value="critical">Crítica</option>
                    </select>
                  </div>
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Entorno</label>
                    <select v-model="createForm.environment" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-3 py-2.5 text-sm text-text-default outline-none focus:border-border-default dark:bg-primary-strong dark:text-white dark:focus:border-lemon/40">
                      <option value="production">Producción</option>
                      <option value="staging">Staging</option>
                      <option value="dev">Desarrollo</option>
                    </select>
                  </div>
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Navegador</label>
                    <input v-model="createForm.device_browser" type="text" placeholder="Chrome / iOS" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-3 py-2.5 text-sm text-text-default outline-none placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                  </div>
                </div>

                <label class="flex items-center gap-2 text-xs text-green-light">
                  <input v-model="createForm.is_recurring" type="checkbox" class="rounded border-border-default" />
                  Es un error recurrente
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

                <p v-if="bugStore.error" role="alert" class="text-xs text-danger-strong">{{ bugStore.error }}</p>
                <div class="flex justify-end gap-3 pt-2">
                  <BaseButton variant="ghost" size="md" @click="isCreateOpen = false">Cancelar</BaseButton>
                  <BaseButton variant="accent" size="md" type="submit" :disabled="!createForm.title.trim() || bugStore.isUpdating">
                    {{ bugStore.isUpdating ? 'Reportando...' : 'Reportar bug' }}
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
                    Pega un array con `id` + los campos a actualizar (`status`, `admin_response`, `linked_bug_id`).
                    Los demás campos se ignoran.
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
                    placeholder='[{"id": 1, "status": "fixing", "admin_response": "Reproducido, en corrección."}]'
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
        <div v-if="detailBug" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm" @click.self="detailBug = null">
          <Transition name="modal-content" appear>
            <div v-if="detailBug" class="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <!-- Header -->
              <div class="mb-5 flex items-start justify-between gap-4">
                <div class="flex-1">
                  <div class="mb-2 flex flex-wrap items-center gap-2">
                    <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase" :class="statusBadgeClass(detailBug.status)">{{ statusLabel(detailBug.status) }}</span>
                    <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="severityBadgeClass(detailBug.severity)">{{ severityLabel(detailBug.severity) }}</span>
                    <span v-if="detailBug.is_archived" class="rounded-full bg-surface-raised px-2 py-0.5 text-[10px] font-semibold uppercase text-text-muted dark:text-text-subtle">Archivado</span>
                    <span v-if="detailBug.is_recurring" class="rounded-full bg-purple-500/15 px-2 py-0.5 text-[10px] font-bold uppercase text-purple-600 dark:text-purple-400">Recurrente</span>
                  </div>
                  <p v-if="detailBug.is_archived && detailBug.archived_at" class="mb-1 text-[10px] text-green-light/60">
                    Archivado el {{ formatDate(detailBug.archived_at) }}
                  </p>
                  <h2 class="text-lg font-bold text-text-default">{{ detailBug.title }}</h2>
                </div>
                <BaseButton unstyled icon-only type="button" aria-label="Cerrar detalle" class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-green-light transition hover:bg-surface-muted hover:text-text-default dark:hover:bg-white/10 dark:hover:text-white" @click="detailBug = null">
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </BaseButton>
              </div>

              <!-- Source requirement -->
              <div v-if="detailBug.source_requirement" class="mb-5 rounded-xl border border-teal-500/20 bg-teal-500/5 p-4">
                <p class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-teal-600 dark:text-teal-300">Sobre el requerimiento</p>
                <p class="text-sm font-medium text-text-default">{{ detailBug.source_requirement.title }}</p>
                <p v-if="detailBug.source_requirement.phase_title" class="mt-0.5 text-[11px] text-green-light/70">
                  Fase: {{ detailBug.source_requirement.phase_title }}
                </p>
                <NuxtLink
                  :to="localePath(`/platform/projects/${projectId}/delivery?stage=${detailBug.source_requirement.stage_id}#requirement-${detailBug.source_requirement.id}`)"
                  class="mt-2 inline-flex items-center gap-1 text-xs font-medium text-text-brand underline decoration-text-brand/30 transition hover:decoration-text-brand dark:text-accent dark:decoration-accent/30 dark:hover:decoration-accent"
                >
                  {{ t('platformDelivery.seeDelivery') }}
                  <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7-7 7M5 12h16" /></svg>
                </NuxtLink>
              </div>

              <IssueHistory :ticket="detailBug" />

              <!-- Description -->
              <div v-if="detailBug.description" class="mb-5 rounded-xl border border-border-muted bg-surface-muted/20 p-4 text-sm leading-relaxed text-green-light">
                {{ detailBug.description }}
              </div>

              <!-- Screenshot -->
              <div v-if="detailBug.screenshot_url" class="mb-5">
                <!-- icon-interaction-feedback: allow-custom -- full screenshot preview link, not an icon control. -->
                <a :href="detailBug.screenshot_url" target="_blank" class="block overflow-hidden rounded-xl border border-border-default transition hover:border-border-default dark:hover:border-white/15">
                  <img :src="detailBug.screenshot_url" alt="Pantallazo" class="w-full object-contain" style="max-height: 300px" />
                </a>
              </div>

              <!-- Steps to reproduce -->
              <div v-if="detailBug.steps_to_reproduce && detailBug.steps_to_reproduce.length" class="mb-5">
                <p class="mb-2 text-xs font-semibold uppercase tracking-wider text-green-light/60">Pasos para reproducir</p>
                <ol class="space-y-1.5">
                  <li v-for="(step, i) in detailBug.steps_to_reproduce" :key="i" class="flex items-start gap-2 text-sm text-green-light">
                    <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold dark:bg-white/10">{{ i + 1 }}</span>
                    <span>{{ step }}</span>
                  </li>
                </ol>
              </div>

              <!-- Expected vs Actual -->
              <div v-if="detailBug.expected_behavior || detailBug.actual_behavior" class="mb-5 grid grid-cols-2 gap-3">
                <div v-if="detailBug.expected_behavior" class="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
                  <p class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-brand">Esperado</p>
                  <p class="text-xs leading-relaxed text-green-light">{{ detailBug.expected_behavior }}</p>
                </div>
                <div v-if="detailBug.actual_behavior" class="rounded-xl border border-red-500/20 bg-red-500/5 p-3">
                  <p class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-red-600 dark:text-red-400">Actual</p>
                  <p class="text-xs leading-relaxed text-green-light">{{ detailBug.actual_behavior }}</p>
                </div>
              </div>

              <!-- Meta -->
              <div class="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Entorno</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ envLabel(detailBug.environment) }}</p>
                </div>
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Navegador</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ detailBug.device_browser || '—' }}</p>
                </div>
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Reportado por</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ detailBug.reported_by_name }}</p>
                </div>
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Fecha</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ formatDate(detailBug.created_at) }}</p>
                </div>
              </div>

              <!-- Admin response -->
              <div v-if="detailBug.admin_response" class="mb-5 rounded-xl border-l-2 border-l-esmerald/30 bg-surface-muted/20 p-4 dark:border-l-lemon/40">
                <p class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-esmerald/60 dark:text-lemon/60">Respuesta del equipo</p>
                <p class="text-sm leading-relaxed text-green-light">{{ detailBug.admin_response }}</p>
              </div>

              <p v-if="detailBug.status === 'resolved'" class="mb-3 text-xs text-text-muted">{{ t('platformIssues.resolvedHint') }}</p>
              <IssueReopenForm v-if="!authStore.isAdmin && detailBug.status === 'resolved' && !detailBug.is_archived" :ticket="detailBug" :project-id="projectId" @updated="detailBug = $event" />

              <!-- Admin actions -->
              <div v-if="authStore.isAdmin" class="mb-5 space-y-3">
                <div v-if="detailBug.is_archived" class="rounded-xl border border-border-default px-4 py-3 text-xs text-green-light/70">
                  Este reporte está archivado.
                </div>
                <template v-else>
                  <div v-if="showEvaluateForm" class="rounded-xl border border-border-default p-4">
                    <p class="mb-3 text-xs font-semibold uppercase tracking-wider text-green-light/60">Evaluar bug</p>
                    <div class="space-y-3">
                      <div>
                        <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Estado</label>
                        <select v-model="evalForm.status" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none focus:border-border-default dark:bg-primary-strong dark:text-white dark:focus:border-lemon/40">
                          <option value="reported">Reportado</option>
                          <option value="confirmed">Confirmado</option>
                          <option value="fixing">En corrección</option>
                          <option value="qa">En QA</option>
                          <option value="resolved">{{ t('platformIssues.status.resolved') }}</option>
                          <option value="not_reproducible">No reproducible</option>
                          <option value="wont_fix">No se corregirá</option>
                          <option value="duplicate">Duplicado</option>
                        </select>
                      </div>
                      <div>
                        <label class="mb-1 block text-xs font-medium text-esmerald/70 dark:text-white/70">Respuesta</label>
                        <textarea v-model="evalForm.admin_response" rows="2" :placeholder="t('platformIssues.responsePlaceholder')" class="w-full resize-none rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                      </div>
                      <IssueEvidenceFields v-model="responseEvidence" :project-id="projectId" kind="bug" :ticket-id="detailBug.id" admin id="bug-response-evidence" />
                      <p v-if="bugStore.error" role="alert" class="text-xs text-danger-strong">{{ bugStore.error }}</p>
                      <div class="flex justify-end gap-2">
                        <BaseButton variant="ghost" size="sm" @click="showEvaluateForm = false">Cancelar</BaseButton>
                        <BaseButton variant="accent" size="sm" :disabled="bugStore.isUpdating" @click="handleEvaluate">
                          {{ bugStore.isUpdating ? 'Guardando...' : 'Guardar' }}
                        </BaseButton>
                      </div>
                    </div>
                  </div>

                  <div v-else class="flex flex-wrap gap-2">
                    <BaseButton variant="secondary" size="sm" @click="openEvaluateForm">
                      Evaluar
                    </BaseButton>
                    <BaseButton variant="danger-ghost" size="sm" :disabled="bugStore.isUpdating" @click="handleDelete">
                      Archivar
                    </BaseButton>
                  </div>
                </template>
              </div>

              <!-- Comments -->
              <div class="mb-4">
                <p class="mb-3 text-xs font-semibold uppercase tracking-wider text-green-light/60">
                  Comentarios{{ detailBug.comments ? ` (${detailBug.comments.length})` : '' }}
                </p>

                <div v-if="detailBug.comments && detailBug.comments.length" class="mb-4 space-y-3">
                  <div
                    v-for="comment in detailBug.comments"
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

                <form class="flex gap-2" @submit.prevent="handleAddComment">
                  <input v-model="newComment" type="text" placeholder="Escribe un comentario..." class="flex-1 rounded-xl border border-border-default bg-surface-muted/40 px-4 py-2.5 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                  <BaseButton variant="accent" size="md" type="submit" :disabled="!newComment.trim()">
                    Enviar
                  </BaseButton>
                </form>
                <IssueEvidenceFields v-if="!detailBug.is_archived" v-model="commentEvidence" :project-id="projectId" kind="bug" :ticket-id="detailBug.id" id="bug-comment-evidence" />
                <p v-if="bugStore.error && !showEvaluateForm" role="alert" class="mt-2 text-xs text-danger-strong">{{ bugStore.error }}</p>
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
  </ProjectShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { useIsMobile } from '~/composables/useIsMobile'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformBugReportsStore } from '~/stores/platform-bug-reports'
import { usePlatformProjectsStore } from '~/stores/platform-projects'
import { usePlatformIssueReportsStore } from '~/stores/platform-issue-reports'
import { issueSourcePayload, prefillIssueGuide } from '~/utils/issue-reports'
import IssueSourcePicker from '~/components/platform/issues/IssueSourcePicker.vue'
import IssueHistory from '~/components/platform/issues/IssueHistory.vue'
import IssueAttachments from '~/components/platform/issues/IssueAttachments.vue'
import IssueEvidenceFields from '~/components/platform/issues/IssueEvidenceFields.vue'
import IssueReopenForm from '~/components/platform/issues/IssueReopenForm.vue'
import { formatDate } from '~/utils/formatDate'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'

definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
usePageEntrance('#platform-bugs')

const route = useRoute()
const localePath = useLocalePath()
const { t } = useI18n()
const authStore = usePlatformAuthStore()
const bugStore = usePlatformBugReportsStore()
const projectsStore = usePlatformProjectsStore()
const issueStore = usePlatformIssueReportsStore()
const sourceError = ref('')
const responseEvidence = ref({ contract_id: null, document_ids: [] })
const commentEvidence = ref({ document_ids: [] })

const { isMobile } = useIsMobile()

const projectRequirements = ref([])

const projectId = computed(() => route.params.id)
const projectName = computed(() => projectsStore.currentProject?.name || 'Proyecto')
const activeFilter = ref('all')

const statusTabs = computed(() => [
  { value: 'all', label: 'Todos', count: bugStore.bugReports.length },
  { value: 'reported', label: 'Reportados', count: bugStore.reportedCount },
  { value: 'confirmed', label: 'Confirmados', count: bugStore.confirmedCount },
  { value: 'fixing', label: 'En corrección', count: bugStore.fixingCount },
  { value: 'qa', label: 'En QA' },
  { value: 'resolved', label: t('platformIssues.status.resolved'), count: bugStore.resolvedCount },
  { value: 'not_reproducible', label: 'No reproducible' },
  { value: 'wont_fix', label: 'No se corregirá' },
  { value: 'duplicate', label: 'Duplicado' },
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

const filteredBugs = computed(() => {
  let list = bugStore.filteredByStatus(activeFilter.value)
  if (selectedPhaseId.value) {
    list = list.filter((b) => b.source_requirement?.phase_id === selectedPhaseId.value)
  }
  return list
})

const isImportOpen = ref(false)
const importJson = ref('')
const importError = ref('')
const importLoading = ref(false)

const isCreateOpen = ref(false)
const createForm = reactive({
  title: '', description: '', severity: 'medium', environment: 'production',
  device_browser: '', is_recurring: false, steps_to_reproduce: [''],
  expected_behavior: '', actual_behavior: '',
  source_requirement_id: null,
})
const screenshotFile = ref(null)
const screenshotPreview = ref(null)

const detailBug = ref(null)
const newComment = ref('')
const commentInternal = ref(false)
const showEvaluateForm = ref(false)
const evalForm = reactive({ status: 'confirmed', admin_response: '' })

function statusBadgeClass(s) {
  const map = {
    reported: 'bg-red-500/15 text-red-600 dark:text-red-400',
    confirmed: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    fixing: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
    qa: 'bg-purple-500/15 text-purple-600 dark:text-purple-400',
    resolved: 'bg-emerald-500/15 text-text-brand',
    not_reproducible: 'bg-surface-raised text-text-muted',
    wont_fix: 'bg-surface-raised text-text-muted',
    duplicate: 'bg-surface-raised text-text-muted',
  }
  return map[s] || map.reported
}

function statusLabel(s) {
  const map = {
    reported: 'Reportado', confirmed: 'Confirmado', fixing: 'En corrección',
    qa: 'En QA', resolved: t('platformIssues.status.resolved'), not_reproducible: 'No reproducible',
    wont_fix: 'No se corregirá', duplicate: 'Duplicado',
  }
  return map[s] || s
}

function severityBadgeClass(sev) {
  const map = {
    critical: 'bg-red-500/15 text-red-600 dark:text-red-400',
    high: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    medium: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
    low: 'bg-surface-raised text-text-muted',
  }
  return map[sev] || map.medium
}

function severityLabel(sev) {
  const map = { critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja' }
  return map[sev] || sev
}

function envLabel(env) {
  const map = { production: 'Producción', staging: 'Staging', dev: 'Desarrollo' }
  return map[env] || env
}

function openCreateModal() {
  bugStore.error = ''
  createForm.source_requirement_id = null
  createForm.title = ''; createForm.description = ''; createForm.severity = 'medium'
  createForm.environment = 'production'; createForm.device_browser = ''
  createForm.is_recurring = false; createForm.steps_to_reproduce = ['']
  createForm.expected_behavior = ''; createForm.actual_behavior = ''
  screenshotFile.value = null; screenshotPreview.value = null
  // Honor ?from_req=X&title=Y from delivery.vue deep-link
  const fromReq = Number(route.query.from_req)
  const req = projectRequirements.value.find((r) => r.id === fromReq)
  if (req) {
    createForm.source_requirement_id = req.id
  }
  if (typeof route.query.title === 'string') {
    createForm.title = route.query.title
  }
  isCreateOpen.value = true
}

function handleScreenshotSelect(event) {
  const file = event.target.files?.[0]
  if (file) { screenshotFile.value = file; screenshotPreview.value = URL.createObjectURL(file) }
}
function handleScreenshotDrop(event) {
  const file = event.dataTransfer.files?.[0]
  if (file?.type.startsWith('image/')) { screenshotFile.value = file; screenshotPreview.value = URL.createObjectURL(file) }
}
function removeScreenshot() {
  screenshotFile.value = null
  if (screenshotPreview.value) URL.revokeObjectURL(screenshotPreview.value)
  screenshotPreview.value = null
}

async function handleCreate() {
  if (!createForm.title.trim()) return
  const steps = createForm.steps_to_reproduce.filter((s) => s.trim())
  let payload
  if (screenshotFile.value) {
    payload = new FormData()
    if (createForm.source_requirement_id) payload.append('source_requirement_id', String(createForm.source_requirement_id))
    payload.append('title', createForm.title)
    payload.append('description', createForm.description)
    payload.append('severity', createForm.severity)
    payload.append('environment', createForm.environment)
    payload.append('device_browser', createForm.device_browser)
    payload.append('is_recurring', createForm.is_recurring)
    payload.append('expected_behavior', createForm.expected_behavior)
    payload.append('actual_behavior', createForm.actual_behavior)
    steps.forEach((s) => payload.append('steps_to_reproduce', s))
    payload.append('screenshot', screenshotFile.value)
  } else {
    payload = {
      source_requirement_id: createForm.source_requirement_id,
      title: createForm.title,
      description: createForm.description,
      severity: createForm.severity,
      environment: createForm.environment,
      device_browser: createForm.device_browser,
      is_recurring: createForm.is_recurring,
      steps_to_reproduce: steps,
      expected_behavior: createForm.expected_behavior,
      actual_behavior: createForm.actual_behavior,
    }
  }
  const source = issueSourcePayload(projectRequirements.value.find((row) => row.id === createForm.source_requirement_id))
  if (payload instanceof FormData) {
    Object.entries(source).forEach(([key, value]) => payload.set(key, String(value)))
    payload.set('request_id', crypto.randomUUID())
  } else {
    Object.assign(payload, source, { request_id: crypto.randomUUID() })
  }
  const result = await bugStore.createBugReport(projectId.value, payload)
  if (result.success) {
    if (screenshotPreview.value) URL.revokeObjectURL(screenshotPreview.value)
    isCreateOpen.value = false
  }
}

async function openDetailModal(bug) {
  detailBug.value = bug; newComment.value = ''; commentInternal.value = false; showEvaluateForm.value = false
  const result = await bugStore.fetchBugReport(projectId.value, bug.id)
  if (result.success) detailBug.value = result.data
}

function openEvaluateForm() {
  evalForm.status = detailBug.value?.status || 'confirmed'
  evalForm.admin_response = ''
  responseEvidence.value = { contract_id: detailBug.value?.origin_context?.contract_id || null, document_ids: [] }
  showEvaluateForm.value = true
}

async function handleEvaluate() {
  if (!detailBug.value) return
  const result = await bugStore.evaluateBugReport(projectId.value, detailBug.value.id, { ...evalForm, ...responseEvidence.value, expected_version: detailBug.value.version, request_id: crypto.randomUUID() })
  if (result.success) { detailBug.value = result.data; showEvaluateForm.value = false }
}

async function handleDelete() {
  if (!detailBug.value) return
  if (!window.confirm('¿Archivar este reporte de bug? Podrás verlo otra vez activando "Mostrar archivados".')) return
  const result = await bugStore.deleteBugReport(projectId.value, detailBug.value.id)
  if (result.success) detailBug.value = null
}

async function onQuickStatus(bug, newStatus) {
  if (!newStatus || newStatus === bug.status) return
  const result = await bugStore.evaluateBugReport(projectId.value, bug.id, { status: newStatus, expected_version: bug.version, request_id: crypto.randomUUID() })
  if (!result.success) {
    window.alert(result.message || 'No pudimos actualizar el estado.')
  }
}

function exportResponsesJson() {
  const rows = filteredBugs.value.map((bug) => ({
    id: bug.id,
    title: bug.title,
    status: bug.status,
    admin_response: bug.admin_response || '',
    linked_bug_id: bug.linked_bug_id ?? null,
  }))
  const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const tab = activeFilter.value === 'all' ? 'todos' : activeFilter.value
  a.download = `bugs-${projectId.value}-${tab}.json`
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
    const result = await bugStore.bulkEvaluateBugReports(projectId.value, items)
    if (result.success) {
      await loadBugsAndDeliverables()
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


async function loadBugsAndDeliverables() {
  await bugStore.fetchBugReports(projectId.value, null, false)
}

async function loadProjectRequirements() {
  const r = await issueStore.contextOptions(projectId.value, {
    ...(route.query.from_pub ? { source_publication_id: Number(route.query.from_pub), source_requirement_id: Number(route.query.from_req) } : {}),
  })
  projectRequirements.value = r.success ? (r.data.requirements || []) : []
  sourceError.value = r.success ? '' : r.message
}

async function handleAddComment() {
  if (!newComment.value.trim() || !detailBug.value) return
  const result = await bugStore.addComment(projectId.value, detailBug.value.id, newComment.value.trim(), commentInternal.value, { document_ids: commentEvidence.value.document_ids, expected_version: detailBug.value.version, request_id: crypto.randomUUID() })
  if (result.success) {
    newComment.value = ''; commentInternal.value = false; commentEvidence.value = { document_ids: [] }
    const updated = await bugStore.fetchBugReport(projectId.value, detailBug.value.id)
    if (updated.success) detailBug.value = updated.data
  }
}

watch(() => createForm.source_requirement_id, (id) => {
  prefillIssueGuide(createForm, projectRequirements.value.find((row) => row.id === id))
})

onMounted(async () => {
  await Promise.all([
    loadBugsAndDeliverables(),
    loadProjectRequirements(),
    projectsStore.currentProject?.id !== Number(projectId.value) ? projectsStore.fetchProject(projectId.value) : Promise.resolve(),
  ])
  if (!authStore.isAdmin && route.query.from_req && projectRequirements.value.length) {
    openCreateModal()
  }
})

watch(projectId, () => {
  loadBugsAndDeliverables()
  loadProjectRequirements()
})
</script>

<style scoped>
.modal-overlay-enter-active, .modal-overlay-leave-active { transition: opacity 0.25s ease; }
.modal-overlay-enter-from, .modal-overlay-leave-to { opacity: 0; }
.modal-content-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-content-leave-active { transition: all 0.2s ease-in; }
.modal-content-enter-from { opacity: 0; transform: scale(0.95) translateY(10px); }
.modal-content-leave-to { opacity: 0; transform: scale(0.97); }
</style>
