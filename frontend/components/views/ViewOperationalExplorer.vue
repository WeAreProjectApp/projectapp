<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import BaseActionButton from '~/components/base/BaseActionButton.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import SidebarIcon from '~/components/platform/SidebarIcon.vue'
import ViewExplorerContextPanel from '~/components/views/ViewExplorerContextPanel.vue'
import ViewExplorerTourControls from '~/components/views/ViewExplorerTourControls.vue'
import { usePanelViewportProfile } from '~/composables/usePanelViewportProfile'
import { orbitalPosition, useOrbitalExplorer } from '~/composables/useOrbitalExplorer'
import {
  capabilityNodePath,
  capabilityViewRecords,
  descendantCapabilityViewUrls,
  explorerTourSteps,
  findCapabilityNode,
  flattenCapabilityCatalog,
  viewCapabilityCatalog,
} from '~/config/viewCapabilityCatalog'
import { viewCatalogSections } from '~/config/viewCatalog'

const props = defineProps({
  selectedNodeId: { type: String, default: null },
  selectedTourId: { type: String, default: null },
  showRelations: { type: Boolean, default: true },
})

const emit = defineEmits([
  'select',
  'update:showRelations',
  'start-tour',
  'stop-tour',
])

const { profile } = usePanelViewportProfile()
const isCompactLayout = computed(() => ['compact', 'portrait'].includes(profile.value))
const isTourRequested = computed(() => Boolean(props.selectedTourId))
const {
  angle,
  zoom,
  isManuallyPaused,
  isAutoRotating,
  prefersReducedMotion,
  rotateBy,
  zoomIn,
  zoomOut,
  resetOrbit,
  togglePause,
  startDrag,
  moveDrag,
  endDrag,
  consumeDrag,
  setHovering,
  setFocusWithin,
} = useOrbitalExplorer({ isExternallyPaused: isTourRequested })

const search = ref('')
const activeNodeId = ref(null)
const stageRef = ref(null)

const allNodes = flattenCapabilityCatalog()
const currentNode = computed(() => findCapabilityNode(props.selectedNodeId) || viewCapabilityCatalog)
const currentPath = computed(() => capabilityNodePath(currentNode.value.id))
const orbitNodes = computed(() => currentNode.value.children || [])
const previewNode = computed(() => (
  activeNodeId.value ? findCapabilityNode(activeNodeId.value) : null
))
const displayNode = computed(() => previewNode.value || currentNode.value)
const isPreviewing = computed(() => displayNode.value.id !== currentNode.value.id)

const nodePositions = computed(() => orbitNodes.value.map((node, index) => ({
  node,
  ...orbitalPosition(index, orbitNodes.value.length, angle.value, profile.value, zoom.value),
})))

const positionsById = computed(() => new Map(
  nodePositions.value.map((position) => [position.node.id, position]),
))

const visibleRelations = computed(() => {
  if (!props.showRelations) return []
  return (currentNode.value.relations || [])
    .map((relation) => ({
      ...relation,
      fromPosition: positionsById.value.get(relation.from),
      toPosition: positionsById.value.get(relation.to),
    }))
    .filter((relation) => relation.fromPosition && relation.toPosition)
})

const technicalViews = computed(() => capabilityViewRecords(displayNode.value))

function relatedViewCount(node) {
  if (node.id === viewCapabilityCatalog.id) {
    return viewCatalogSections.reduce((total, section) => total + section.views.length, 0)
  }
  return new Set(descendantCapabilityViewUrls(node)).size
}

const currentViewCount = computed(() => relatedViewCount(currentNode.value))
const displayViewCount = computed(() => relatedViewCount(displayNode.value))

const searchResults = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('es')
  if (!query) return []
  return allNodes
    .filter((node) => node.id !== viewCapabilityCatalog.id)
    .filter((node) => [node.label, node.summary, node.value, node.stage]
      .filter(Boolean)
      .some((value) => value.toLocaleLowerCase('es').includes(query)))
    .slice(0, 8)
})

function searchResultPath(nodeId) {
  return capabilityNodePath(nodeId).slice(1).map((node) => node.label).join(' / ')
}

const relationSummary = computed(() => {
  if (!activeNodeId.value) return currentNode.value.relations || []
  return (currentNode.value.relations || []).filter((relation) => (
    relation.from === activeNodeId.value || relation.to === activeNodeId.value
  ))
})

const tourSpace = computed(() => {
  const node = findCapabilityNode(props.selectedTourId)
  return node?.kind === 'space' ? node : null
})
const tourSteps = computed(() => explorerTourSteps(tourSpace.value?.id))
const tourStepIndex = computed(() => (
  tourSteps.value.findIndex((node) => node.id === currentNode.value.id)
))
const isTourActive = computed(() => Boolean(tourSpace.value) && tourStepIndex.value >= 0)
const hasPreviousTourStep = computed(() => tourStepIndex.value > 0)
const hasNextTourStep = computed(() => (
  tourStepIndex.value >= 0 && tourStepIndex.value < tourSteps.value.length - 1
))

const canGoBack = computed(() => currentPath.value.length > 1)

watch(() => props.selectedNodeId, (nodeId) => {
  activeNodeId.value = null
  if (nodeId && !findCapabilityNode(nodeId)) emit('select', null)
}, { immediate: true })

watch([tourSpace, tourStepIndex], ([spaceNode, stepIndex]) => {
  if (!spaceNode || stepIndex >= 0) return
  const firstStep = explorerTourSteps(spaceNode.id)[0]
  if (firstStep) emit('select', firstStep.id)
}, { immediate: true })

function selectNode(nodeId) {
  if (consumeDrag()) return
  search.value = ''
  activeNodeId.value = null
  emit('select', nodeId)
  nextTick(() => stageRef.value?.focus())
}

function goBack() {
  if (!canGoBack.value) return
  const parent = currentPath.value.at(-2)
  emit('select', parent.id === viewCapabilityCatalog.id ? null : parent.id)
}

function goToPreviousTourStep() {
  if (!hasPreviousTourStep.value) return
  emit('select', tourSteps.value[tourStepIndex.value - 1].id)
}

function goToNextTourStep() {
  if (!hasNextTourStep.value) return
  emit('select', tourSteps.value[tourStepIndex.value + 1].id)
}

function handleStageKeydown(event) {
  if (event.target !== event.currentTarget) return
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    rotateBy(-15)
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    rotateBy(15)
  }
  if (event.key === 'Escape') {
    event.preventDefault()
    goBack()
  }
}

function nodeStyle(position) {
  return {
    left: `${position.x}%`,
    top: `${position.y}%`,
    transform: `translate(-50%, -50%) scale(${position.scale})`,
    zIndex: position.zIndex,
  }
}

function relationIsActive(relation) {
  return activeNodeId.value
    && (relation.from === activeNodeId.value || relation.to === activeNodeId.value)
}

function nodeIsDimmed(nodeId) {
  if (!activeNodeId.value || activeNodeId.value === nodeId) return false
  const connected = (currentNode.value.relations || []).some((relation) => (
    (relation.from === activeNodeId.value && relation.to === nodeId)
    || (relation.to === activeNodeId.value && relation.from === nodeId)
  ))
  return !connected
}

function childCountLabel(node) {
  if (!node.children?.length) return ''
  const count = node.children.filter((child) => !child.secondary).length
  const label = node.kind === 'space'
    ? (count === 1 ? 'módulo' : 'módulos')
    : (count === 1 ? 'submódulo' : 'submódulos')
  return `${count} ${label}`
}
</script>

<template>
  <section class="space-y-5" data-testid="view-operational-explorer">
    <div class="rounded-2xl border border-border-muted bg-surface p-4 shadow-sm">
      <div class="flex flex-col gap-3 panel-landscape:flex-row panel-landscape:items-center panel-landscape:justify-between">
        <nav class="flex min-w-0 flex-wrap items-center gap-1.5 text-sm" aria-label="Ruta del explorador">
          <template v-for="(node, index) in currentPath" :key="node.id">
            <span v-if="index > 0" class="text-text-subtle" aria-hidden="true">/</span>
            <BaseButton
              variant="link"
              size="sm"
              class="max-w-full text-left text-text-muted"
              :class="index === currentPath.length - 1 ? 'font-medium text-text-default' : ''"
              :aria-current="index === currentPath.length - 1 ? 'page' : undefined"
              @click="selectNode(node.id === viewCapabilityCatalog.id ? null : node.id)"
            >
              {{ node.label }}
            </BaseButton>
          </template>
        </nav>

        <div class="relative w-full panel-landscape:max-w-md">
          <label for="view-explorer-search" class="sr-only">Buscar una capacidad</label>
          <input
            id="view-explorer-search"
            v-model="search"
            type="search"
            autocomplete="off"
            placeholder="Buscar un módulo, submódulo o beneficio..."
            class="w-full rounded-xl border border-input-border bg-input-bg px-4 py-2.5 text-sm text-input-text outline-none placeholder:text-text-subtle focus:border-focus-ring focus:ring-1 focus:ring-focus-ring/30"
          />
          <div
            v-if="search.trim()"
            class="absolute inset-x-0 top-full z-40 mt-2 overflow-hidden rounded-xl border border-border-default bg-surface shadow-lg"
            data-testid="view-explorer-search-results"
          >
            <!-- design-tokens: allow-raw-button — searchable capability option -->
            <button
              v-for="result in searchResults"
              :key="result.id"
              type="button"
              class="block w-full border-b border-border-muted px-4 py-3 text-left last:border-b-0 hover:bg-surface-raised focus:bg-surface-raised focus:outline-none"
              @click="selectNode(result.id)"
            >
              <span class="block text-sm font-medium text-text-default">{{ result.label }}</span>
              <span class="mt-0.5 block text-[11px] text-text-subtle">{{ searchResultPath(result.id) }}</span>
              <span class="mt-1 block text-xs text-text-muted">{{ result.summary }}</span>
            </button>
            <p v-if="searchResults.length === 0" class="px-4 py-5 text-center text-sm text-text-muted">
              No encontramos un módulo con ese término.
            </p>
          </div>
        </div>
      </div>
    </div>

    <ViewExplorerTourControls
      v-if="isTourActive"
      :space-label="tourSpace.label"
      :step-index="tourStepIndex"
      :step-count="tourSteps.length"
      :has-previous="hasPreviousTourStep"
      :has-next="hasNextTourStep"
      @previous="goToPreviousTourStep"
      @next="goToNextTourStep"
      @stop="emit('stop-tour')"
    />

    <div class="overflow-hidden rounded-3xl border border-border-muted bg-surface shadow-sm">
      <div class="flex flex-col gap-3 border-b border-border-muted p-4 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
        <div class="flex flex-wrap items-center gap-2">
          <BaseActionButton
            v-if="canGoBack"
            action="back"
            label="Volver al nivel anterior"
            data-testid="view-explorer-back"
            @click="goBack"
          />
          <span class="text-xs text-text-muted">
            {{ isCompactLayout ? 'Selecciona una tarjeta para continuar' : 'Arrastra para girar · usa las flechas para ajustar' }}
          </span>
        </div>

        <div v-if="!isCompactLayout" class="flex flex-wrap items-center gap-1" aria-label="Controles del explorador">
          <BaseActionButton action="previous" label="Girar a la izquierda" @click="rotateBy(-15)" />
          <BaseActionButton action="next" label="Girar a la derecha" @click="rotateBy(15)" />
          <BaseActionButton action="zoom-out" label="Alejar" @click="zoomOut" />
          <BaseActionButton action="zoom-in" label="Acercar" @click="zoomIn" />
          <BaseActionButton action="refresh" label="Centrar la órbita" @click="resetOrbit" />
          <BaseActionButton
            v-if="!isTourActive"
            :action="isManuallyPaused ? 'activate' : 'deactivate'"
            :label="isManuallyPaused ? 'Reanudar giro suave' : 'Pausar giro suave'"
            data-testid="view-explorer-motion-toggle"
            @click="togglePause"
          />
          <BaseActionButton
            v-if="currentNode.relations?.length"
            :action="showRelations ? 'unlink' : 'link'"
            :label="showRelations ? 'Ocultar relaciones operativas' : 'Mostrar relaciones operativas'"
            data-testid="view-explorer-relations-toggle"
            @click="emit('update:showRelations', !showRelations)"
          />
        </div>
      </div>

      <div v-if="isCompactLayout" class="space-y-4 bg-surface-raised p-4">
        <ViewExplorerContextPanel
          :node="displayNode"
          :technical-views="technicalViews"
          :related-view-count="displayViewCount"
          :is-previewing="isPreviewing"
          :is-tour-active="isTourActive"
          @select="selectNode"
          @start-tour="emit('start-tour', $event)"
        />

        <div
          ref="stageRef"
          tabindex="0"
          class="grid gap-3 outline-none focus:ring-2 focus:ring-focus-ring/40 panel-portrait:grid-cols-2"
          aria-label="Módulos disponibles"
          data-testid="view-explorer-stage"
          @keydown.esc.prevent="goBack"
          @focusin="setFocusWithin(true)"
          @focusout="setFocusWithin(false)"
        >
          <!-- panel-action-icons: allow-navigation-icon — the icon identifies a product module, not an action -->
          <BaseButton
            v-for="(node, index) in orbitNodes"
            :key="node.id"
            variant="secondary"
            textPolicy="wrap"
            class="min-h-28 w-full justify-start p-4 text-left"
            :data-testid="`view-explorer-node-${node.id}`"
            :aria-label="`${node.label}. ${node.summary}`"
            @focus="activeNodeId = node.id"
            @blur="activeNodeId = null"
            @click="selectNode(node.id)"
          >
            <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-text-brand">
              <SidebarIcon :name="node.icon" class="h-5 w-5" aria-hidden="true" />
            </span>
            <span class="min-w-0">
              <span class="block text-[10px] font-semibold uppercase tracking-widest text-text-subtle">
                {{ String(index + 1).padStart(2, '0') }}
              </span>
              <span class="mt-1 block text-sm font-medium text-text-default [overflow-wrap:anywhere]">{{ node.label }}</span>
              <span v-if="node.children?.length" class="mt-1 block text-[11px] text-text-muted">{{ childCountLabel(node) }}</span>
            </span>
          </BaseButton>
        </div>
      </div>

      <div v-else class="grid gap-4 bg-surface-raised p-4 panel-landscape:grid-cols-[minmax(0,1.55fr)_minmax(18rem,0.75fr)]">
        <div
          ref="stageRef"
          tabindex="0"
          class="relative self-start min-h-[42rem] touch-none overflow-hidden rounded-2xl border border-border-muted bg-surface outline-none focus:ring-2 focus:ring-inset focus:ring-focus-ring/40 panel-desktop:min-h-[44rem]"
          aria-label="Constelación de capacidades. Usa Tab para recorrer nodos, las flechas para girar y Escape para volver."
          data-testid="view-explorer-stage"
          @keydown="handleStageKeydown"
          @pointerdown.self="startDrag"
          @pointermove="moveDrag"
          @pointerup="endDrag"
          @pointercancel="endDrag"
          @mouseenter="setHovering(true)"
          @mouseleave="setHovering(false)"
          @focusin="setFocusWithin(true)"
          @focusout="setFocusWithin(false)"
        >
          <div class="pointer-events-none absolute inset-0 opacity-70" aria-hidden="true">
            <div class="absolute left-1/2 top-1/2 h-3/4 w-3/4 -translate-x-1/2 -translate-y-1/2 rounded-full border border-border-muted" />
            <div class="absolute left-1/2 top-1/2 h-1/2 w-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-primary/20" />
          </div>

          <svg class="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <line
              v-for="position in nodePositions"
              :key="`hierarchy-${position.node.id}`"
              x1="50"
              y1="50"
              :x2="position.x"
              :y2="position.y"
              vector-effect="non-scaling-stroke"
              class="stroke-border-default"
              stroke-width="1"
              opacity="0.7"
            />
            <line
              v-for="relation in visibleRelations"
              :key="`relation-${relation.from}-${relation.to}`"
              :x1="relation.fromPosition.x"
              :y1="relation.fromPosition.y"
              :x2="relation.toPosition.x"
              :y2="relation.toPosition.y"
              vector-effect="non-scaling-stroke"
              :class="relationIsActive(relation) ? 'stroke-accent' : 'stroke-text-subtle'"
              stroke-width="1.5"
              stroke-dasharray="5 4"
              :opacity="activeNodeId && !relationIsActive(relation) ? 0.2 : 0.75"
              data-testid="view-explorer-relation"
            />
          </svg>

          <article
            class="absolute left-1/2 top-1/2 z-30 flex w-44 -translate-x-1/2 -translate-y-1/2 flex-col items-center rounded-3xl border border-primary/30 bg-surface px-4 py-5 text-center shadow-lg panel-desktop:w-52 panel-desktop:px-5 panel-desktop:py-6"
            data-testid="view-explorer-center"
          >
            <span class="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-on-primary shadow-sm">
              <SidebarIcon :name="currentNode.icon" class="h-6 w-6" aria-hidden="true" />
            </span>
            <p class="text-[10px] font-semibold uppercase tracking-widest text-text-subtle">
              {{ currentNode.kind === 'root' ? 'Ecosistema' : currentNode.stage || 'Capacidad' }}
            </p>
            <h2 class="mt-1 text-base font-medium text-text-default">{{ currentNode.label }}</h2>
            <p class="mt-2 hidden text-xs leading-5 text-text-muted panel-desktop:line-clamp-4">{{ currentNode.summary }}</p>
            <span class="mt-3 rounded-full bg-primary-soft px-2.5 py-1 text-[11px] font-medium text-text-brand">
              {{ currentViewCount }} {{ currentViewCount === 1 ? 'vista relacionada' : 'vistas relacionadas' }}
            </span>
          </article>

          <!-- panel-action-icons: allow-navigation-icon — the icon identifies a product module, not an action -->
          <BaseButton
            v-for="(position, index) in nodePositions"
            :key="position.node.id"
            variant="secondary"
            size="sm"
            class="absolute flex min-h-20 w-24 flex-col gap-1 rounded-2xl px-2 py-2 text-center shadow-sm transition-[opacity,box-shadow,transform] duration-300 motion-reduce:transition-none panel-desktop:w-32 panel-desktop:px-2 panel-desktop:py-3"
            :class="[
              activeNodeId === position.node.id ? 'border-primary shadow-md' : '',
              nodeIsDimmed(position.node.id) ? 'opacity-40' : 'opacity-100',
            ]"
            :style="nodeStyle(position)"
            :data-testid="`view-explorer-node-${position.node.id}`"
            :aria-label="`${position.node.label}. ${position.node.summary}`"
            @mouseenter="activeNodeId = position.node.id"
            @mouseleave="activeNodeId = null"
            @focus="activeNodeId = position.node.id"
            @blur="activeNodeId = null"
            @click="selectNode(position.node.id)"
          >
            <SidebarIcon :name="position.node.icon" class="h-4 w-4 shrink-0 text-text-brand" aria-hidden="true" />
            <span class="text-[10px] font-semibold uppercase tracking-widest text-text-subtle">
              {{ String(index + 1).padStart(2, '0') }}
            </span>
            <span class="line-clamp-2 text-[11px] font-medium leading-4 text-text-default panel-desktop:text-sm">
              {{ position.node.label }}
            </span>
            <span v-if="position.node.children?.length" class="text-[10px] text-text-muted">
              {{ childCountLabel(position.node) }}
            </span>
          </BaseButton>

          <p class="sr-only" role="status" aria-live="polite">
            {{ currentNode.label }}. {{ orbitNodes.length }} nodos disponibles.
            {{ isAutoRotating ? 'Giro suave activo.' : 'Giro suave pausado.' }}
          </p>
        </div>

        <ViewExplorerContextPanel
          class="self-start panel-landscape:sticky panel-landscape:top-4"
          :node="displayNode"
          :technical-views="technicalViews"
          :related-view-count="displayViewCount"
          :is-previewing="isPreviewing"
          :is-tour-active="isTourActive"
          @select="selectNode"
          @start-tour="emit('start-tour', $event)"
        />
      </div>
    </div>

    <aside class="rounded-2xl border border-border-muted bg-surface p-5 shadow-sm">
      <div class="flex items-center justify-between gap-3">
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-widest text-text-subtle">Conexiones</p>
          <h3 class="mt-1 text-sm font-medium text-text-default">Recorrido operativo</h3>
        </div>
        <span class="rounded-full bg-surface-raised px-2.5 py-1 text-xs text-text-muted">
          {{ relationSummary.length }}
        </span>
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-4 text-xs text-text-muted">
        <span class="flex items-center gap-2"><span class="h-px w-7 bg-border-default" /> Jerarquía</span>
        <span class="flex items-center gap-2"><span class="w-7 border-t border-dashed border-text-subtle" /> Conexión operativa</span>
      </div>
      <ul v-if="relationSummary.length" class="mt-4 grid gap-2 panel-landscape:grid-cols-2">
        <li
          v-for="relation in relationSummary"
          :key="`${relation.from}-${relation.to}`"
          class="rounded-xl border border-border-muted bg-surface-raised px-3 py-2.5 text-xs leading-5 text-text-muted"
        >
          <strong class="font-medium text-text-default">{{ findCapabilityNode(relation.from)?.label }}</strong>
          <span class="mx-1 text-text-subtle">→</span>
          {{ relation.label }}
          <span class="mx-1 text-text-subtle">→</span>
          <strong class="font-medium text-text-default">{{ findCapabilityNode(relation.to)?.label }}</strong>
        </li>
      </ul>
      <p v-else class="mt-4 text-sm leading-6 text-text-muted">
        En este nivel mostramos la jerarquía. Las relaciones aparecen al entrar a uno de los tres espacios.
      </p>
      <p v-if="prefersReducedMotion" class="mt-4 rounded-lg bg-info-soft px-3 py-2 text-xs text-info-strong">
        El giro automático está desactivado por tu preferencia de movimiento reducido.
      </p>
    </aside>
  </section>
</template>
