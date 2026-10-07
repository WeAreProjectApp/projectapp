<template>
  <ProjectShell>
    <div id="platform-deliverables">
    <!-- Loading -->
    <div v-if="store.isLoading && !store.deliverables.length" class="py-20 text-center">
      <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-esmerald dark:border-t-lemon" />
    </div>

    <template v-else>
      <!-- Header -->
      <div class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between" data-enter>
        <div>
          <h1 class="text-xl font-bold text-text-default sm:text-2xl">Recursos</h1>
          <p class="mt-1 text-xs text-green-light/70">Archivos compartidos del proyecto.</p>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <span class="rounded-full border border-border-default px-3 py-1.5 text-xs font-semibold text-green-light">
            {{ store.totalCount }} archivos
          </span>
          <BaseButton variant="accent" size="md" @click="openCreateModal">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
            Subir recurso
          </BaseButton>
        </div>
      </div>

      <!-- Category filter -->
      <div class="mb-5 flex gap-1.5 overflow-x-auto pb-1" data-enter>
        <button
          v-for="tab in categoryTabs"
          :key="tab.value"
          type="button"
          class="shrink-0 rounded-full px-3.5 py-1.5 text-xs font-medium transition"
          :class="activeCategory === tab.value
            ? 'bg-primary text-white dark:bg-accent dark:text-text-default'
            : 'text-green-light hover:bg-surface-muted/50 dark:hover:bg-white/10'"
          @click="activeCategory = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Table -->
      <template v-if="filteredItems.length">
      <div v-if="!isMobile" class="overflow-x-auto rounded-2xl border border-border-default bg-surface" data-enter>
        <table class="min-w-full text-left text-sm">
          <thead class="bg-surface-muted/40 text-xs font-medium uppercase tracking-wider text-green-light/70">
            <tr>
              <th class="px-4 py-3">Recurso</th>
              <th class="px-4 py-3">Categoría</th>
              <th class="px-4 py-3">Subido por</th>
              <th class="px-4 py-3">Tamaño</th>
              <th class="px-4 py-3">Versión</th>
              <th class="px-4 py-3">Actualizado</th>
              <th class="w-10 px-2"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="d in filteredItems"
              :key="d.id"
              class="cursor-pointer border-t border-border-muted transition hover:bg-primary-soft"
              :class="d.is_archived ? 'opacity-70' : ''"
              @click="openDetailModal(d)"
            >
              <td class="px-4 py-3">
                <div class="flex items-center gap-3">
                  <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" :class="categoryIconBg(d.category)">
                    <span class="text-base">{{ categoryIcon(d.category) }}</span>
                  </span>
                  <div class="min-w-0">
                    <p class="truncate font-medium text-text-default">{{ d.title }}</p>
                    <p class="truncate text-[11px] text-green-light/60">{{ d.file_name || '—' }}</p>
                  </div>
                </div>
              </td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="categoryBadgeClass(d.category)">
                  {{ categoryLabel(d.category) }}
                </span>
                <span v-if="d.is_archived" class="ml-1 rounded-full bg-surface-raised px-2 py-0.5 text-[10px] font-semibold uppercase text-text-muted dark:text-text-subtle">
                  Archivado
                </span>
              </td>
              <td class="px-4 py-3 text-xs text-green-light">{{ d.uploaded_by_name }}</td>
              <td class="px-4 py-3 text-xs text-green-light/70">{{ formatBytes(d.file_size) }}</td>
              <td class="px-4 py-3 text-xs text-green-light/70">v{{ d.current_version }}</td>
              <td class="px-4 py-3 text-xs text-green-light/70">{{ formatDate(d.updated_at) }}</td>
              <td class="px-2 py-3 text-right text-green-light/40">›</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Cards (mobile) -->
      <div v-else class="space-y-3" data-enter>
        <button
          v-for="d in filteredItems"
          :key="d.id"
          type="button"
          class="block w-full rounded-2xl border border-border-default bg-surface p-4 text-left transition hover:bg-primary-soft"
          :class="d.is_archived ? 'opacity-70' : ''"
          @click="openDetailModal(d)"
        >
          <div class="flex items-center gap-3">
            <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" :class="categoryIconBg(d.category)">
              <span class="text-base">{{ categoryIcon(d.category) }}</span>
            </span>
            <div class="min-w-0 flex-1">
              <p class="truncate font-medium text-text-default">{{ d.title }}</p>
              <p class="truncate text-[11px] text-green-light/60">{{ d.file_name || '—' }}</p>
            </div>
            <span class="shrink-0 text-green-light/40">›</span>
          </div>
          <div class="mt-3 flex flex-wrap items-center gap-2">
            <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase" :class="categoryBadgeClass(d.category)">{{ categoryLabel(d.category) }}</span>
            <span v-if="d.is_archived" class="rounded-full bg-surface-raised px-2 py-0.5 text-[10px] font-semibold uppercase text-text-muted dark:text-text-subtle">Archivado</span>
            <span class="text-[10px] text-green-light/60">{{ formatBytes(d.file_size) }} · v{{ d.current_version }}</span>
          </div>
          <div class="mt-2 flex items-center justify-between gap-2 text-xs text-green-light/70">
            <span class="truncate">{{ d.uploaded_by_name }}</span>
            <span class="shrink-0">{{ formatDate(d.updated_at) }}</span>
          </div>
        </button>
      </div>
      </template>

      <!-- Empty -->
      <div v-else class="py-16 text-center" data-enter>
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-muted/50 dark:bg-white/5">
          <svg class="h-8 w-8 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>
        </div>
        <p class="text-sm text-green-light">No hay recursos aún.</p>
        <BaseButton variant="accent" size="md" class="mt-4" @click="openCreateModal">
          Subir primer recurso
        </BaseButton>
      </div>
</template>

    <!-- Create modal -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div v-if="isCreateOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm" @click.self="isCreateOpen = false">
          <Transition name="modal-content" appear>
            <div v-if="isCreateOpen" class="w-full max-w-md rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <h2 class="mb-5 text-lg font-bold text-text-default">Subir recurso</h2>
              <form class="space-y-4" @submit.prevent="handleCreate">
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Título <span class="text-red-400">*</span></label>
                  <input v-model="createForm.title" type="text" required placeholder="Nombre del recurso" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Descripción</label>
                  <textarea v-model="createForm.description" rows="2" placeholder="Descripción opcional..." class="w-full resize-none rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-green-light/50 focus:border-border-default dark:bg-primary-strong dark:text-white dark:placeholder:text-white/30 dark:focus:border-lemon/40" />
                </div>
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Categoría</label>
                  <select v-model="createForm.category" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none focus:border-border-default dark:bg-primary-strong dark:text-white dark:focus:border-lemon/40" @change="onCategoryChange">
                    <option v-for="opt in uploadableCategories" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                  <p v-if="!authStore.isAdmin" class="mt-1 text-[10px] text-green-light/60">
                    Contrato, otrosí, anexo legal y diseños los sube el equipo.
                  </p>
                </div>
                <!-- File upload -->
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">
                    Archivo <span class="text-red-400">*</span>
                    <span class="ml-1 font-normal text-green-light/60">({{ acceptedExtensionLabel }})</span>
                  </label>
                  <div
                    class="relative flex min-h-[80px] cursor-pointer items-center justify-center rounded-xl border-2 border-dashed border-border-default bg-surface-muted/20 transition hover:border-border-default dark:hover:border-white/20"
                    @click="$refs.fileInput.click()"
                    @dragover.prevent
                    @drop.prevent="handleFileDrop"
                  >
                    <input ref="fileInput" type="file" class="hidden" :accept="acceptedExtension" @change="handleFileSelect" />
                    <div v-if="!selectedFile" class="py-4 text-center">
                      <svg class="mx-auto mb-1.5 h-6 w-6 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                      <p class="text-[11px] text-green-light/50">Arrastra o haz clic para subir</p>
                      <p class="mt-1 text-[10px] text-green-light/40">Se acepta {{ acceptedExtensionLabel }}</p>
                    </div>
                    <div v-else class="flex w-full items-center gap-3 px-4 py-3">
                      <svg class="h-5 w-5 shrink-0 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                      <span class="flex-1 truncate text-sm text-text-default">{{ selectedFile.name }}</span>
                      <BaseButton variant="danger-ghost" icon-only size="sm" class="shrink-0" aria-label="Quitar" @click.stop="selectedFile = null">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                      </BaseButton>
                    </div>
                  </div>
                </div>
                <p v-if="createError" class="rounded-xl border border-red-500/30 bg-red-500/5 px-3 py-2 text-xs text-red-600 dark:text-red-400">
                  {{ createError }}
                </p>

                <div class="flex justify-end gap-3 pt-2">
                  <BaseButton variant="ghost" size="md" @click="isCreateOpen = false">Cancelar</BaseButton>
                  <BaseButton variant="accent" size="md" type="submit" :disabled="!createForm.title.trim() || !selectedFile || store.isUpdating">
                    {{ store.isUpdating ? 'Subiendo...' : 'Subir' }}
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
        <div v-if="detailItem" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm" @click.self="detailItem = null">
          <Transition name="modal-content" appear>
            <div v-if="detailItem" class="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <div class="mb-5 flex items-start justify-between gap-4">
                <div class="flex-1">
                  <div class="mb-2 flex flex-wrap items-center gap-2">
                    <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase" :class="categoryBadgeClass(detailItem.category)">{{ categoryLabel(detailItem.category) }}</span>
                    <span class="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-green-light dark:bg-white/10">v{{ detailItem.current_version }}</span>
                    <span v-if="detailItem.is_archived" class="rounded-full bg-surface-raised px-2 py-0.5 text-[10px] font-semibold uppercase text-text-muted dark:text-text-subtle">
                      Archivado
                    </span>
                  </div>
                  <p v-if="detailItem.is_archived && detailItem.archived_at" class="mb-1 text-[10px] text-green-light/70">
                    Archivado el {{ formatDate(detailItem.archived_at) }}
                  </p>
                  <h2 class="text-lg font-bold text-text-default">{{ detailItem.title }}</h2>
                </div>
                <BaseButton unstyled icon-only type="button" aria-label="Cerrar detalle" class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-green-light transition hover:bg-surface-muted hover:text-text-default dark:hover:bg-white/10 dark:hover:text-white" @click="detailItem = null">
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </BaseButton>
              </div>

              <div v-if="detailItem.description" class="mb-5 rounded-xl border border-border-muted bg-surface-muted/20 p-4 text-sm leading-relaxed text-green-light">
                {{ detailItem.description }}
              </div>

              <!-- Download current -->
              <BaseButton unstyled type="button"
                v-if="detailItem.file_url"
                :disabled="Boolean(downloadingFile)"
                :aria-busy="downloadingFile === detailItem.file_url"
                class="mb-5 flex w-full items-center gap-3 rounded-xl border border-border-default bg-surface-muted/20 p-4 text-left transition hover:border-border-default disabled:opacity-60 dark:hover:border-white/15"
                @click="downloadResource(detailItem)"
              >
                <svg class="h-5 w-5 shrink-0 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                <div class="flex-1 min-w-0">
                  <p class="truncate text-sm font-medium text-text-default">{{ detailItem.file_name }}</p>
                  <p class="text-[10px] text-green-light/60">Versión {{ detailItem.current_version }} · {{ detailItem.uploaded_by_name }} · {{ formatDate(detailItem.updated_at) }}</p>
                </div>
                <span class="text-xs font-medium text-text-brand">{{ downloadingFile === detailItem.file_url ? 'Descargando…' : 'Descargar' }}</span>
              </BaseButton>

              <p v-if="downloadError" role="alert" class="mb-5 text-sm text-red-500">{{ downloadError }}</p>

              <ProposalApprovalFiles
                :project-id="projectId"
                :files="detailItem.approval_files || []"
              />

              <!-- Meta -->
              <div class="mb-5 grid grid-cols-3 gap-3">
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Categoría</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ categoryLabel(detailItem.category) }}</p>
                </div>
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Subido por</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ detailItem.uploaded_by_name }}</p>
                </div>
                <div class="rounded-xl border border-border-muted p-3">
                  <p class="text-[10px] font-medium uppercase tracking-wider text-green-light/60">Versiones</p>
                  <p class="mt-1 text-xs font-semibold text-text-default">{{ detailItem.versions_count || detailItem.current_version }}</p>
                </div>
              </div>

              <!-- Version history -->
              <div v-if="detailItem.versions && detailItem.versions.length" class="mb-5">
                <p class="mb-3 text-xs font-semibold uppercase tracking-wider text-green-light/60">Historial de versiones</p>
                <div class="space-y-2">
                  <BaseButton unstyled type="button"
                    v-for="v in detailItem.versions"
                    :key="v.id"
                    :disabled="!v.file_url || Boolean(downloadingFile)"
                    :aria-busy="downloadingFile === v.file_url"
                    class="flex w-full items-center gap-3 rounded-xl border border-border-muted p-3 text-left transition hover:border-border-default disabled:opacity-60 dark:hover:border-white/12"
                    @click="downloadResource(v)"
                  >
                    <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-green-light dark:bg-white/10">v{{ v.version_number }}</span>
                    <div class="flex-1 min-w-0">
                      <p class="truncate text-xs font-medium text-text-default">{{ v.file_name }}</p>
                      <p class="text-[10px] text-green-light/60">{{ v.uploaded_by_name }} · {{ formatDate(v.created_at) }}</p>
                    </div>
                    <svg class="h-4 w-4 shrink-0 text-green-light/30" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 10v6m0 0l-3-3m3 3l3-3" /></svg>
                  </BaseButton>
                </div>
              </div>

              <!-- Admin actions -->
              <div v-if="authStore.isAdmin && !detailItem.is_archived" class="flex flex-wrap gap-2">
                <BaseButton variant="secondary" size="sm" @click="openUploadVersion">
                  Subir nueva versión
                </BaseButton>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>

    <!-- Upload new version modal -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div v-if="isVersionUploadOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm" @click.self="isVersionUploadOpen = false">
          <Transition name="modal-content" appear>
            <div v-if="isVersionUploadOpen" class="w-full max-w-sm rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8">
              <h2 class="mb-4 text-lg font-bold text-text-default">Nueva versión</h2>
              <p class="mb-1 text-xs text-green-light">Será la versión {{ (detailItem?.current_version || 0) + 1 }} de "{{ detailItem?.title }}"</p>
              <p class="mb-4 text-[11px] text-green-light/60">Se acepta {{ versionAcceptedExtensionLabel }}</p>
              <div
                class="relative mb-4 flex min-h-[80px] cursor-pointer items-center justify-center rounded-xl border-2 border-dashed border-border-default bg-surface-muted/20 transition hover:border-border-default dark:hover:border-white/20"
                @click="$refs.versionFileInput.click()"
                @dragover.prevent
                @drop.prevent="handleVersionDrop"
              >
                <input ref="versionFileInput" type="file" class="hidden" :accept="versionAcceptedExtension" @change="handleVersionSelect" />
                <div v-if="!versionFile" class="py-4 text-center">
                  <svg class="mx-auto mb-1.5 h-6 w-6 text-green-light/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                  <p class="text-[11px] text-green-light/50">Selecciona el archivo</p>
                </div>
                <div v-else class="flex w-full items-center gap-3 px-4 py-3">
                  <span class="flex-1 truncate text-sm text-text-default">{{ versionFile.name }}</span>
                  <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Quitar" @click.stop="versionFile = null">
                    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                  </BaseButton>
                </div>
              </div>
              <div class="flex justify-end gap-3">
                <BaseButton variant="ghost" size="md" @click="isVersionUploadOpen = false">Cancelar</BaseButton>
                <BaseButton variant="accent" size="md" :disabled="!versionFile || store.isUpdating" @click="handleUploadVersion">
                  {{ store.isUpdating ? 'Subiendo...' : 'Subir versión' }}
                </BaseButton>
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
import { usePlatformDeliverablesStore } from '~/stores/platform-deliverables'
import { usePlatformProjectsStore } from '~/stores/platform-projects'
import { formatDate } from '~/utils/formatDate'
import ProposalApprovalFiles from '~/components/platform/projects/ProposalApprovalFiles.vue'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'

definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
usePageEntrance('#platform-deliverables')

const route = useRoute()
const localePath = useLocalePath()
const authStore = usePlatformAuthStore()
const store = usePlatformDeliverablesStore()
const projectsStore = usePlatformProjectsStore()

const { isMobile } = useIsMobile()

const projectId = computed(() => route.params.id)
const projectName = computed(() => projectsStore.currentProject?.name || 'Proyecto')
const activeCategory = ref('all')

const categoryTabs = [
  { value: 'all', label: 'Todos' },
  { value: 'designs', label: 'Diseños' },
  { value: 'documents', label: 'Documentos' },
  { value: 'contract', label: 'Contrato' },
  { value: 'amendment', label: 'Otrosí' },
  { value: 'legal_annex', label: 'Anexo legal' },
  { value: 'other', label: 'Otros' },
]

const ADMIN_ONLY_CATEGORIES = ['designs', 'contract', 'amendment', 'legal_annex']

const uploadableCategories = computed(() => {
  const all = [
    { value: 'documents', label: 'Documentos' },
    { value: 'designs', label: 'Diseños' },
    { value: 'contract', label: 'Contrato' },
    { value: 'amendment', label: 'Otrosí' },
    { value: 'legal_annex', label: 'Anexo legal' },
    { value: 'other', label: 'Otros' },
  ]
  if (authStore.isAdmin) return all
  return all.filter((c) => !ADMIN_ONLY_CATEGORIES.includes(c.value))
})

const filteredItems = computed(() => {
  const groups = store.groupedByCategory || []
  const flat = []
  for (const g of groups) {
    if (activeCategory.value !== 'all' && g.category !== activeCategory.value) continue
    for (const d of g.items) flat.push(d)
  }
  return flat
})

function categoryAcceptInfo(cat) {
  if (cat === 'designs') return { accept: '.zip,application/zip', label: '.zip' }
  return { accept: '.pdf,application/pdf', label: '.pdf' }
}

const acceptedExtension = computed(() => categoryAcceptInfo(createForm.category).accept)
const acceptedExtensionLabel = computed(() => categoryAcceptInfo(createForm.category).label)
const versionAcceptedExtension = computed(() => categoryAcceptInfo(detailItem.value?.category).accept)
const versionAcceptedExtensionLabel = computed(() => categoryAcceptInfo(detailItem.value?.category).label)

const isCreateOpen = ref(false)
const createForm = reactive({ title: '', description: '', category: 'other' })
const selectedFile = ref(null)
const createError = ref('')

const detailItem = ref(null)
const downloadingFile = ref('')
const downloadError = ref('')
const isVersionUploadOpen = ref(false)
const versionFile = ref(null)

function categoryLabel(cat) {
  const map = {
    designs: 'Diseños', documents: 'Documentos',
    contract: 'Contrato', amendment: 'Otrosí', legal_annex: 'Anexo legal',
    other: 'Otros',
  }
  return map[cat] || cat
}
function categoryIconBg(cat) {
  const map = {
    designs: 'bg-purple-500/10', documents: 'bg-blue-500/10',
    contract: 'bg-teal-500/10', amendment: 'bg-orange-500/10', legal_annex: 'bg-indigo-500/10',
    other: 'bg-surface-raised',
  }
  return map[cat] || 'bg-surface-raised'
}
function categoryIcon(cat) {
  const map = {
    designs: '🎨', documents: '📄', contract: '📜', amendment: '✏️',
    legal_annex: '⚖️', other: '📦',
  }
  return map[cat] || '📦'
}
function categoryBadgeClass(cat) {
  const map = {
    designs: 'bg-purple-500/15 text-purple-600 dark:text-purple-400',
    documents: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
    contract: 'bg-teal-500/15 text-teal-600 dark:text-teal-400',
    amendment: 'bg-orange-500/15 text-orange-600 dark:text-orange-400',
    legal_annex: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-400',
    other: 'bg-surface-raised text-text-muted',
  }
  return map[cat] || map.other
}
function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let val = bytes
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024
    i++
  }
  return `${val.toFixed(val >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}

function openCreateModal() {
  createForm.title = ''; createForm.description = ''; createForm.category = 'other'
  selectedFile.value = null; createError.value = ''; isCreateOpen.value = true
}
function handleFileSelect(event) { selectedFile.value = event.target.files?.[0] || null; createError.value = '' }
function handleFileDrop(event) { selectedFile.value = event.dataTransfer.files?.[0] || null; createError.value = '' }
function onCategoryChange() {
  selectedFile.value = null
  createError.value = ''
}

async function handleCreate() {
  if (!createForm.title.trim() || !selectedFile.value) return
  createError.value = ''
  const fd = new FormData()
  fd.append('title', createForm.title)
  fd.append('description', createForm.description)
  fd.append('category', createForm.category)
  fd.append('file', selectedFile.value)
  const result = await store.createDeliverable(projectId.value, fd)
  if (result.success) {
    isCreateOpen.value = false
  } else {
    createError.value = result.message
  }
}

async function openDetailModal(d) {
  const requestedProjectId = projectId.value
  downloadError.value = ''
  detailItem.value = d
  const result = await store.fetchDeliverable(requestedProjectId, d.id)
  if (result.success && requestedProjectId === projectId.value && detailItem.value?.id === d.id) {
    detailItem.value = result.data
  }
}

async function downloadResource(file) {
  if (downloadingFile.value) return
  const requestedProjectId = projectId.value
  const requestedDetailId = detailItem.value?.id
  downloadError.value = ''
  downloadingFile.value = file.file_url
  try {
    const result = await store.downloadFile(file)
    if (!result.success && requestedProjectId === projectId.value && detailItem.value?.id === requestedDetailId) {
      downloadError.value = result.message
    }
  } finally {
    downloadingFile.value = ''
  }
}

function openUploadVersion() { versionFile.value = null; isVersionUploadOpen.value = true }
function handleVersionSelect(event) { versionFile.value = event.target.files?.[0] || null }
function handleVersionDrop(event) { versionFile.value = event.dataTransfer.files?.[0] || null }

async function handleUploadVersion() {
  if (!versionFile.value || !detailItem.value) return
  const fd = new FormData()
  fd.append('file', versionFile.value)
  const result = await store.uploadNewVersion(projectId.value, detailItem.value.id, fd)
  if (result.success) { detailItem.value = result.data; isVersionUploadOpen.value = false }
}

async function loadDeliverables() {
  await store.fetchDeliverables(projectId.value, null, false)
}

onMounted(async () => {
  await Promise.all([
    loadDeliverables(),
    projectsStore.currentProject?.id !== Number(projectId.value) ? projectsStore.fetchProject(projectId.value) : Promise.resolve(),
  ])
})

watch(projectId, () => {
  detailItem.value = null
  downloadError.value = ''
  loadDeliverables()
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
