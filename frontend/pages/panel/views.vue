<template>
  <div>
    <div class="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="mb-2 text-xs font-semibold uppercase tracking-widest text-text-muted">
          Ecosistema
        </p>
        <h1 class="text-2xl font-light text-text-default">Mapa de vistas</h1>
        <p v-if="viewMode === 'explorer' && activeSection === 'catalog'" class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
          Recorre el Panel interno, la Plataforma de clientes y las experiencias públicas. Señala un módulo para descubrir su contexto o inicia un recorrido guiado.
        </p>
        <p v-else class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
          Inventario de vistas de la aplicacion, agrupadas por contexto. Las URLs dinamicas usan parametros como <code class="font-mono text-xs text-text-brand">:id</code>, <code class="font-mono text-xs text-text-brand">:uuid</code> o <code class="font-mono text-xs text-text-brand">:slug</code>.
        </p>
      </div>

      <div class="flex w-full flex-wrap items-end gap-3 sm:w-auto sm:justify-end">
        <BaseSegmented v-model="activeSection" size="sm" :options="sectionOptions" />
        <template v-if="activeSection === 'catalog'">
          <BaseSegmented
            v-model="viewMode"
            size="sm"
            :options="viewModeOptions"
            nowrap
          />
          <div class="rounded-xl border border-border-muted bg-surface px-4 py-3 text-sm shadow-sm">
            <span class="block text-xs text-text-subtle">Total</span>
            <div class="flex items-baseline gap-1">
              <strong class="text-2xl font-light text-text-brand">{{ viewMode === 'explorer' ? totalViews : filteredViewCount }}</strong>
              <span v-if="viewMode !== 'explorer' && isFiltering" class="text-sm text-text-subtle">/ {{ totalViews }}</span>
              <span class="ml-1 text-text-muted">vistas</span>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- ══════════════ Configuración ══════════════ -->
    <div v-if="activeSection === 'config'" class="space-y-6 max-w-2xl">
      <section class="bg-surface rounded-xl shadow-sm border border-border-muted p-6">
        <h2 class="text-sm font-medium text-text-default mb-1">Vista por defecto</h2>
        <p class="text-xs text-text-subtle mb-4">
          Modo con el que abre el mapa de vistas al entrar a esta página.
        </p>
        <BaseSegmented
          :model-value="defaultViewMode"
          :options="viewModeOptions"
          data-testid="view-map-default-mode"
          @update:model-value="saveDefaultViewMode"
        />
      </section>

      <section class="bg-surface rounded-xl shadow-sm border border-border-muted p-6">
        <h2 class="text-sm font-medium text-text-default mb-1">Filtros por defecto</h2>
        <p class="text-xs text-text-subtle mb-4">
          Filtros que se aplican al abrir esta vista con la pestaña "Todas" activa.
          Se guardan automáticamente al cambiarlos.
        </p>
        <ViewMapFilterPanel
          :model-value="configFilters"
          :is-open="true"
          :filter-count="configFilterCount"
          @update:model-value="Object.assign(configFilters, $event)"
          @reset="resetConfigFilters"
        />
      </section>
    </div>

    <!-- ══════════════ Catálogo ══════════════ -->
    <template v-else>
    <ViewOperationalExplorer
      v-if="viewMode === 'explorer'"
      :selected-node-id="selectedExplorerNodeId"
      :selected-tour-id="selectedExplorerTourId"
      :show-relations="showRelations"
      @select="selectExplorerNode"
      @start-tour="startExplorerTour"
      @stop-tour="stopExplorerTour"
      @update:show-relations="showRelations = $event"
    />

    <template v-else>
    <!-- Filter tabs -->
    <ProposalFilterTabs
      :tabs="savedTabs"
      :active-tab-id="activeTabId"
      :is-tab-limit-reached="isTabLimitReached"
      @select="selectTab"
      @create="saveTab"
      @rename="renameTab"
      @delete="deleteTab"
      @restore="restoreTab"
      @rebase="rebaseTab"
      @reorder="reorderTabs"
    />

    <!-- Search bar + filter toggle -->
    <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
      <div class="relative flex-1">
        <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-subtle" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          v-model="search"
          type="text"
          placeholder="Buscar vista por nombre, URL, referencia o archivo..."
          class="w-full rounded-xl border border-input-border bg-input-bg py-2.5 pl-10 pr-4 text-sm text-input-text outline-none transition-colors placeholder:text-text-subtle focus:border-focus-ring focus:ring-1 focus:ring-focus-ring/30"
        />
        <BaseActionButton
          v-if="search"
          action="clear"
          label="Limpiar búsqueda"
          class="absolute right-0 top-1/2 -translate-y-1/2"
          @click="search = ''"
        />
      </div>
      <FilterToggleButton
        :open="isFilterPanelOpen"
        :count="activeFilterCount"
        @click="isFilterPanelOpen = !isFilterPanelOpen"
      />
    </div>

    <!-- Filter panel -->
    <ViewMapFilterPanel
      v-model="currentFilters"
      :is-open="isFilterPanelOpen"
      :filter-count="activeFilterCount"
      @reset="resetFilters"
    />

    <!-- Proposal reference guide (list mode only) -->
    <section v-if="viewMode === 'list'" class="mb-8 rounded-xl border border-primary/20 bg-primary-soft p-5">
      <h2 class="text-base font-medium text-text-brand">Como referirse a las vistas de propuestas</h2>
      <p class="mt-2 text-sm leading-6 text-text-muted">
        Si dices "detalle de propuesta" puede confundirse la pantalla interna del panel con el enlace publico del cliente. Usa el contexto, el tipo de identificador y la URL.
      </p>

      <div class="mt-4 grid gap-3 lg:grid-cols-3">
        <article
          v-for="item in proposalGuide"
          :key="item.url"
          class="rounded-lg border border-primary/20 bg-surface p-4 shadow-sm"
        >
          <p class="text-xs font-semibold uppercase tracking-widest text-green-light">{{ item.label }}</p>
          <h3 class="mt-2 text-sm font-semibold text-text-default">{{ item.recommendedName }}</h3>
          <p class="mt-2 font-mono text-xs text-text-brand">{{ item.url }}</p>
          <p class="mt-2 text-xs leading-5 text-text-muted">{{ item.description }}</p>
          <p class="mt-2 break-all font-mono text-[11px] text-text-subtle">{{ item.file }}</p>
        </article>
      </div>
    </section>

    <!-- Map mode: module grid with drill-down -->
    <template v-if="viewMode === 'map' && filteredSections.length > 0">
      <ViewMapLegend />
      <ViewModuleDetail
        v-if="selectedSection"
        :section="selectedSection"
        @back="clearModule"
      />
      <ViewModuleGrid
        v-else
        :sections="filteredSections"
        @select="selectModule"
      />
    </template>

    <!-- List mode: view catalog -->
    <div v-else-if="viewMode === 'list' && filteredSections.length > 0" class="space-y-6">
      <details
        v-for="section in filteredSections"
        :key="section.id"
        open
        class="group overflow-hidden rounded-xl border border-border-muted bg-surface shadow-sm"
      >
        <summary class="flex items-center justify-between gap-3 border-b border-border-muted px-5 py-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
          <div class="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 class="text-base font-medium text-text-default">{{ section.label }}</h2>
              <p class="mt-1 text-sm text-text-muted">{{ section.description }}</p>
            </div>
            <span class="inline-flex w-fit items-center rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-text-brand">
              {{ section.views.length }} vistas
            </span>
          </div>
          <BaseActionIcon action="expand" class="text-text-subtle transition-transform duration-300 group-open:rotate-180" />
        </summary>

        <div class="divide-y divide-border-muted">
          <article
            v-for="view in section.views"
            :key="`${section.id}-${view.url}-${view.file}`"
            class="grid gap-3 px-5 py-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)_minmax(0,1.2fr)_2.5rem] lg:items-start"
          >
            <div class="min-w-0 max-w-full">
              <h3 class="min-w-0 max-w-full text-sm font-medium text-text-default [overflow-wrap:anywhere]">{{ view.label }}</h3>
              <p class="mt-1 min-w-0 max-w-full text-xs text-text-muted [overflow-wrap:anywhere]">{{ view.reference }}</p>
              <p v-if="view.notes" class="mt-2 min-w-0 max-w-full text-xs leading-5 text-warning-strong [overflow-wrap:anywhere]">{{ view.notes }}</p>
            </div>

            <div>
              <p class="mb-1 text-[10px] font-semibold uppercase tracking-widest text-text-subtle">URL</p>
              <code class="block break-all font-mono text-xs text-text-brand">{{ view.url }}</code>
            </div>

            <div>
              <p class="mb-1 text-[10px] font-semibold uppercase tracking-widest text-text-subtle">Archivo</p>
              <code class="block break-all font-mono text-[11px] text-text-subtle">{{ view.file }}</code>
            </div>

            <div class="flex items-start justify-center lg:pt-1">
              <BaseActionButton
                action="copy"
                class="rounded-lg p-1.5 text-text-subtle transition-colors hover:bg-surface-raised hover:text-text-brand"
                :label="copyFeedback(section, view).label || 'Copiar referencia'"
                :status-label="copyFeedback(section, view).label"
                :status-tone="copyFeedback(section, view).tone"
                @click="copyReference(section, view)"
              />
            </div>
          </article>
        </div>
      </details>
    </div>

    <!-- Empty state -->
    <div v-else class="rounded-xl border border-border-muted bg-surface px-6 py-12 text-center shadow-sm">
      <svg class="mx-auto h-10 w-10 text-text-subtle" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <p class="mt-3 text-sm text-text-muted">No se encontraron vistas con los filtros actuales.</p>
      <button
        type="button"
        class="mt-3 text-sm font-medium text-text-brand transition-colors hover:underline"
        @click="clearAll"
      >
        Limpiar filtros y busqueda
      </button>
    </div>
    </template>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import {
  countCatalogViews,
  getViewCopyReference,
  proposalViewReferenceGuide,
  viewCatalogSections,
} from '~/config/viewCatalog'
import { useViewMapStore } from '~/stores/view_map'
import { usePanelNotify } from '~/composables/usePanelNotify'
import { useClipboardFeedback } from '~/composables/useClipboardFeedback'
import { useViewMapFilters } from '~/composables/useViewMapFilters'
import { useViewMapMode } from '~/composables/useViewMapMode'
import ViewMapFilterPanel from '~/components/views/ViewMapFilterPanel.vue'
import ViewMapLegend from '~/components/views/ViewMapLegend.vue'
import ViewModuleDetail from '~/components/views/ViewModuleDetail.vue'
import ViewModuleGrid from '~/components/views/ViewModuleGrid.vue'
import ViewOperationalExplorer from '~/components/views/ViewOperationalExplorer.vue'
import ProposalFilterTabs from '~/components/proposals/ProposalFilterTabs.vue'
import FilterToggleButton from '~/components/ui/FilterToggleButton.vue'
import BaseSegmented from '~/components/base/BaseSegmented.vue'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })

const sections = viewCatalogSections
const proposalGuide = proposalViewReferenceGuide
const totalViews = countCatalogViews(sections)

const {
  currentFilters,
  savedTabs,
  activeTabId,
  isFilterPanelOpen,
  activeFilterCount,
  hasActiveFilters,
  isTabLimitReached,
  applyDefaultFilters,
  applyFilters,
  resetFilters,
  selectTab,
  saveTab,
  deleteTab,
  renameTab,
  restoreTab,
  rebaseTab,
  reorderTabs,
} = useViewMapFilters()

const {
  viewMode,
  selectedModuleId,
  selectedExplorerNodeId,
  selectedExplorerTourId,
  showRelations,
  applyDefaultMode,
  selectModule,
  clearModule,
  selectExplorerNode,
  startExplorerTour,
  stopExplorerTour,
} = useViewMapMode()

const viewMapStore = useViewMapStore()
const notify = usePanelNotify()
const clipboardFeedback = useClipboardFeedback()

const sectionOptions = [
  { value: 'catalog', label: 'Catálogo', testId: 'view-map-section-catalog' },
  { value: 'config', label: 'Configuración', testId: 'view-map-section-config' },
]

const viewModeOptions = [
  { value: 'list', label: 'Lista', testId: 'view-mode-list' },
  { value: 'map', label: 'Mapa', testId: 'view-mode-map' },
  { value: 'explorer', label: 'Explorador', testId: 'view-mode-explorer' },
]

const activeSection = ref('catalog')

const search = ref('')

// ── Configuración: defaults persistidos en ViewMapSettings ──
const configFilters = reactive({ categories: [], audiences: [], viewTypes: [] })
let configHydrated = false
let configSaveTimer = null

const defaultViewMode = computed(() => viewMapStore.settings?.default_view_mode ?? 'list')

const configFilterCount = computed(() =>
  [configFilters.categories, configFilters.audiences, configFilters.viewTypes]
    .filter((values) => values.length > 0).length,
)

onMounted(async () => {
  const result = await viewMapStore.fetchSettings()
  if (!result.success) return
  applyDefaultMode(result.data.default_view_mode)
  applyDefaultFilters(result.data.default_filters)
  Object.assign(configFilters, { categories: [], audiences: [], viewTypes: [] }, result.data.default_filters || {})
  await nextTick()
  configHydrated = true
})

async function saveDefaultViewMode(mode) {
  const result = await viewMapStore.updateSettings({ default_view_mode: mode })
  if (result.success) {
    notify.success('Vista por defecto guardada.')
  } else {
    notify.error('No se pudo guardar la vista por defecto.')
  }
}

watch(configFilters, () => {
  if (!configHydrated) return
  clearTimeout(configSaveTimer)
  configSaveTimer = setTimeout(async () => {
    const result = await viewMapStore.updateSettings({ default_filters: { ...configFilters } })
    if (result.success) {
      notify.success('Filtros por defecto guardados.')
    } else {
      notify.error('No se pudieron guardar los filtros por defecto.')
    }
  }, 600)
}, { deep: true })

function resetConfigFilters() {
  Object.assign(configFilters, { categories: [], audiences: [], viewTypes: [] })
}

const filteredSections = computed(() => {
  let result = applyFilters(sections)

  const q = search.value.trim().toLowerCase()
  if (q) {
    result = result
      .map((s) => ({
        ...s,
        views: s.views.filter((v) =>
          v.label.toLowerCase().includes(q)
          || v.url.toLowerCase().includes(q)
          || v.reference.toLowerCase().includes(q)
          || v.file.toLowerCase().includes(q),
        ),
      }))
      .filter((s) => s.views.length > 0)
  }

  return result
})

const filteredViewCount = computed(() => countCatalogViews(filteredSections.value))

const selectedSection = computed(() =>
  selectedModuleId.value
    ? filteredSections.value.find((s) => s.id === selectedModuleId.value) || null
    : null,
)

const isFiltering = computed(() => hasActiveFilters.value || search.value.trim().length > 0)

async function copyReference(section, view) {
  const text = getViewCopyReference(section.label, view)
  const key = `${section.id}-${view.url}`
  await clipboardFeedback.copyText({
    key,
    text,
    successLabel: 'Copiado: referencia',
    errorLabel: 'No se pudo copiar la referencia',
    onError: () => notify.error({
      title: 'No se pudo copiar la referencia',
      detail: 'Tu navegador bloqueó el acceso al portapapeles.',
    }),
  })
}

function copyFeedback(section, view) {
  return clipboardFeedback.feedbackFor(`${section.id}-${view.url}`)
}

function clearAll() {
  resetFilters()
  search.value = ''
}

</script>
