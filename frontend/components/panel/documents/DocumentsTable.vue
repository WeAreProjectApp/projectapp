<script setup>
import {
  formatDocumentDate, folderRowSummary,
  archivedAgeLabel, isManagedFolderKind,
} from '~/utils/documentStatus'
import { computed, ref } from 'vue'
import { formatDateTime } from '~/utils/formatDate'
import { isPlainActivation } from '~/utils/rowNavigation'
import BaseActionButton from '~/components/base/BaseActionButton.vue'
import BaseActionIcon from '~/components/base/BaseActionIcon.vue'
import FolderArchivedBadge from '~/components/panel/documents/FolderArchivedBadge.vue'
import DocumentStateList from '~/components/panel/documents/DocumentStateList.vue'
import BaseOverflowText from '~/components/base/BaseOverflowText.vue'
import BaseResizeHandle from '~/components/base/BaseResizeHandle.vue'
import { usePanelViewportProfile } from '~/composables/usePanelViewportProfile'
import { useResizableTableColumns } from '~/composables/useResizableTableColumns'

const props = defineProps({
  documents: { type: Array, default: () => [] },
  subfolders: { type: Array, default: () => [] },
  editToFor: { type: Function, default: () => null },
  // Dirección de una subcarpeta (`?folder=`). Devuelve null cuando entrar no es
  // navegar por URL — en plena búsqueda, por ejemplo — y ahí el nombre deja de
  // fingir que es un enlace.
  folderToFor: { type: Function, default: () => null },
  draggingDocId: { type: [Number, String], default: null },
  dragOverFolderId: { type: [Number, String], default: null },
  newlyCreatedId: { type: [Number, String], default: null },
  // El scope sólo decide el encabezado de columna. Todo lo demás (insignia,
  // fecha, arrastre) lo decide `is_archived` de cada fila: con `scope='all'` y
  // con la búsqueda global la lista es mixta.
  scope: { type: String, default: 'active' },
  dateOrder: {
    type: String,
    default: 'recent',
    validator: (value) => ['recent', 'oldest'].includes(value),
  },
  sorting: { type: Boolean, default: false },
  // Mutación en vuelo: los botones de restaurar giran y quedan inertes.
  updating: { type: Boolean, default: false },
  // Inventario de una fila de subcarpeta. Llega como función y no se consulta
  // el store acá porque este componente es presentacional: sus specs lo montan
  // sin Pinia. El default conserva el conteo directo de siempre; la página lo
  // reemplaza por el que suma el subárbol.
  folderSummary: { type: Function, default: folderRowSummary },
})

const emit = defineEmits([
  'open', 'action', 'thread', 'select-folder', 'unarchive-folder', 'view-archived-folder',
  'doc-dragstart', 'doc-dragend',
  'folder-dragstart', 'folder-dragend', 'folder-dragover', 'folder-dragleave',
  'drop-on-folder', 'sort-date',
])

function isDocumentDraggable(document) {
  if (document.is_archived || document.is_generated_snapshot || document.is_contract_mirror || document.movable === false) return false
  return !(
    document.document_type_code === 'collection_account'
    && document.commercial_status !== 'draft'
  )
}

const dateHeader = computed(() => {
  if (props.scope === 'archived') return 'Archivado'
  return props.scope === 'all' ? 'Fecha' : 'Creado'
})
const dateAriaSort = computed(() => (
  props.dateOrder === 'oldest' ? 'ascending' : 'descending'
))
const nextDateOrder = computed(() => (
  props.dateOrder === 'oldest' ? 'recent' : 'oldest'
))
const dateOrderAction = computed(() => (
  props.dateOrder === 'oldest' ? 'sort-ascending' : 'sort-descending'
))
const dateOrderButtonLabel = computed(() => {
  const current = props.dateOrder === 'oldest'
    ? 'más antiguos primero'
    : 'más nuevos primero'
  const next = nextDateOrder.value === 'oldest'
    ? 'más antiguos primero'
    : 'más nuevos primero'
  return `${dateHeader.value}: ${current}. Ordenar con ${next}.`
})

/**
 * Scope con que se cuenta el inventario de una fila de carpeta.
 *
 * En `all` la lista es mixta y cada fila habla de su propio estado. En los
 * otros dos manda el scope de la VISTA: en archivado se listan también carpetas
 * activas que guardan archivados, y contarlas por su estado haría que
 * anunciaran su inventario activo — justo lo que el modo pide esconder.
 */
function folderSummaryScope(sub) {
  if (props.scope === 'all') return sub.is_archived ? 'archived' : 'active'
  return props.scope
}

const DOCUMENT_TABLE_WIDTH_KEY = 'projectapp-table-widths:documents-list'
// Production inventory on 2026-08-28: the widest of 40 titles needs 496 px
// including cell padding and safety. 520 px fits that boundary without tying
// the limit to a percentage of the table; disclosure remains the future fallback.
const DOCUMENT_TITLE_WIDTH = Object.freeze({ min: 240, default: 320, max: 520 })
const tableContainerRef = ref(null)
const { profile: viewportProfile } = usePanelViewportProfile()

// Column order and responsive behavior are one business contract. The table is
// not rendered below landscape, but compact/portrait stay declared so the card
// representation follows the same keep/group priority explicitly.
const widthColumns = [
  {
    key: 'actions',
    responsive: {
      compact: 'keep', portrait: 'keep', landscape: 'keep', desktop: 'keep', wide: 'keep',
    },
    columnWidth: { min: 56, default: 56, max: 56, fixed: true },
  },
  {
    key: 'title',
    responsive: {
      primary: true,
      compact: 'keep', portrait: 'keep', landscape: 'keep', desktop: 'keep', wide: 'keep',
    },
    columnWidth: { ...DOCUMENT_TITLE_WIDTH, resizable: true },
  },
  {
    key: 'states',
    responsive: {
      compact: 'keep', portrait: 'keep', landscape: 'keep', desktop: 'keep', wide: 'keep',
    },
    columnWidth: { min: 224, default: 224, max: 224, fixed: true },
  },
  {
    key: 'date',
    responsive: {
      compact: 'keep', portrait: 'keep', landscape: 'keep', desktop: 'keep', wide: 'keep',
    },
    columnWidth: { min: 112, default: 128, max: 640, shrinkPriority: 3, fillPriority: 3 },
  },
  {
    key: 'client',
    responsive: {
      compact: 'group', portrait: 'group', landscape: 'group', desktop: 'keep', wide: 'keep',
    },
    columnWidth: { min: 128, default: 176, max: 240, shrinkPriority: 2, fillPriority: 2 },
  },
  {
    // Revisit this low priority after PA-55 backfills historical project links.
    key: 'project',
    responsive: {
      compact: 'group', portrait: 'group', landscape: 'group', desktop: 'keep', wide: 'keep',
    },
    columnWidth: { min: 112, default: 160, max: 224, shrinkPriority: 1, fillPriority: 1 },
  },
]

const visibleWidthKeys = computed(() => widthColumns
  .filter((column) => column.responsive[viewportProfile.value] === 'keep')
  .map((column) => column.key))

const {
  columnStyle,
  draggingKey: resizingColumn,
  onPointerEnd: endColumnResize,
  onPointerMove: moveColumnResize,
  onPointerStart: startColumnResize,
  preferredWidth,
  reset: resetColumnWidth,
  resizeTo: resizeColumnTo,
  tableStyle: documentTableStyle,
} = useResizableTableColumns({
  columns: widthColumns,
  containerRef: tableContainerRef,
  storageKey: DOCUMENT_TABLE_WIDTH_KEY,
  visibleKeys: visibleWidthKeys,
})

function archivedContentCount(folder) {
  return (folder.archived_document_count || 0) + (folder.archived_children_count || 0)
}

/**
 * El nombre de la carpeta es un enlace por los gestos del navegador —
 * ctrl+clic, rueda, «copiar dirección» —, pero el clic simple se lo queda la
 * página: entrar a una carpeta pasa por el store, que además tiene su propio
 * camino cuando hay una búsqueda en curso.
 */
function onFolderLink(event, sub) {
  if (!isPlainActivation(event)) return
  event.preventDefault()
  emit('select-folder', sub.id)
}
</script>

<template>
  <div
    ref="tableContainerRef"
    class="overflow-x-auto rounded-xl border border-border-muted bg-surface shadow-sm"
    :class="resizingColumn ? 'select-none' : ''"
  >
    <table class="w-full" :style="documentTableStyle">
      <caption class="sr-only">Documentos y subcarpetas de la carpeta actual</caption>
      <thead>
        <tr class="border-b border-border-muted text-left">
          <th
            :style="columnStyle('actions')"
            class="w-14 min-w-14 max-w-14 px-1.5 py-3 text-center"
            data-testid="documents-column-actions"
            aria-label="Acciones"
          />
          <th
            class="relative px-6 py-3 text-xs font-medium text-text-muted uppercase tracking-wider"
            :style="columnStyle('title')"
          >
            Título
            <BaseResizeHandle
              :value="preferredWidth('title')"
              :min="DOCUMENT_TITLE_WIDTH.min"
              :max="DOCUMENT_TITLE_WIDTH.max"
              label="Ajustar el ancho de la columna Título"
              test-id="documents-title-resize-handle"
              class="absolute -right-3 top-0 z-20 h-full w-6"
              indicator-class="h-8 w-1 shadow-sm"
              @pointer-start="startColumnResize('title', $event)"
              @pointer-move="moveColumnResize('title', $event)"
              @pointer-end="endColumnResize('title')"
              @resize="resizeColumnTo('title', $event)"
              @reset="resetColumnWidth('title')"
            />
          </th>
          <th
            :style="columnStyle('states')"
            class="hidden px-6 py-3 text-xs font-medium uppercase tracking-wider text-text-muted panel-landscape:table-cell"
            data-testid="documents-column-states"
          >Estados</th>
          <th
            :style="columnStyle('date')"
            class="px-3 py-3 text-xs font-medium text-text-muted uppercase tracking-wider"
            data-testid="documents-column-date"
            :aria-sort="dateAriaSort"
          >
            <!-- design-tokens: allow-raw-button — sortable table header, not a form CTA. -->
            <button
              type="button"
              class="inline-flex min-h-8 w-full items-center gap-1.5 rounded-md px-3 text-left
                     transition-colors hover:bg-surface-raised hover:text-text-default
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/40
                     disabled:cursor-wait disabled:opacity-60"
              :aria-label="dateOrderButtonLabel"
              :disabled="sorting"
              :title="sorting ? 'Se está actualizando el orden de los documentos.' : undefined"
              data-testid="documents-date-sort"
              @click="emit('sort-date', nextDateOrder)"
            >
              <span>{{ dateHeader }}</span>
              <BaseActionIcon
                :action="dateOrderAction"
                class="h-3.5 w-3.5 flex-shrink-0"
              />
            </button>
          </th>
          <th :style="columnStyle('client')" class="hidden px-6 py-3 text-xs font-medium uppercase tracking-wider text-text-muted panel-desktop:table-cell">Cliente</th>
          <th :style="columnStyle('project')" class="hidden px-6 py-3 text-xs font-medium uppercase tracking-wider text-text-muted panel-desktop:table-cell">Proyecto</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border-muted">
        <!-- Filas de subcarpeta — fijas arriba, fuera de la paginación -->
        <tr
          v-for="sub in subfolders"
          :key="`folder-${sub.id}`"
          class="transition-colors select-none hover:bg-surface-muted cursor-pointer"
          :class="{ 'ring-2 ring-inset ring-success-strong': dragOverFolderId === sub.id }"
          :draggable="!sub.is_archived && !isManagedFolderKind(sub) && !sub.is_system_managed"
          @click="emit('select-folder', sub.id)"
          @dragstart="emit('folder-dragstart', $event, sub)"
          @dragend="emit('folder-dragend')"
          @dragover="emit('folder-dragover', $event, sub.id)"
          @dragleave="emit('folder-dragleave')"
          @drop.prevent="emit('drop-on-folder', sub.id)"
        >
          <td
            class="w-14 min-w-14 max-w-14 px-1.5 py-4 text-center"
            @click.stop
            @auxclick.stop
          >
            <BaseActionButton
              v-if="sub.is_archived"
              action="restore"
              label="Restaurar carpeta"
              size="sm"
              :loading="updating"
              :disabled="updating"
              data-testid="folder-unarchive"
              @click="emit('unarchive-folder', sub)"
            />
            <svg v-else class="mx-auto w-4 h-4 text-text-subtle" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </td>
          <td class="min-w-0 overflow-hidden px-6 py-4">
            <div class="flex min-w-0 max-w-full items-center gap-2">
              <svg class="w-4 h-4 text-amber-500 dark:text-amber-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
              </svg>
              <BaseRowLink
                :to="folderToFor(sub)"
                :data-testid="`folder-open-${sub.id}`"
                class="min-w-0 flex-1 truncate text-sm font-medium text-text-default"
                :title="sub.name"
                @click="onFolderLink($event, sub)"
              >{{ sub.name }}</BaseRowLink>
              <BaseBadge v-if="sub.folder_kind === 'project'" variant="info" size="sm">
                Proyecto · {{ sub.managed_project_state?.name || 'Sin estado' }}
              </BaseBadge>
              <!-- Sin estado detrás: los clientes no tienen catálogo de ciclo de
                   vida como los proyectos, sólo el booleano de inactividad. -->
              <BaseBadge v-else-if="sub.folder_kind === 'client'" variant="neutral" size="sm">
                Cliente
              </BaseBadge>
              <FolderArchivedBadge
                v-if="!sub.is_archived && archivedContentCount(sub)"
                :count="archivedContentCount(sub)"
                :folder-name="sub.name"
                @view="emit('view-archived-folder', sub)"
              />
            </div>
          </td>
          <td class="px-6 py-4 text-sm text-text-subtle" colspan="4">
            {{ folderSummary(sub, folderSummaryScope(sub)) }}
          </td>
        </tr>
        <!-- design-tokens: allow-clickable-row — BaseOverflowText encapsula el BaseRowLink real. -->
        <tr
          v-for="doc in documents"
          :key="doc.id"
          class="hover:bg-surface-muted transition-colors cursor-grab active:cursor-grabbing select-none"
          :class="[
            { 'opacity-50': draggingDocId === doc.id },
            { 'bg-primary-soft transition-colors duration-1000': doc.id === newlyCreatedId }
          ]"
          :draggable="isDocumentDraggable(doc)"
          :data-testid="`document-row-${doc.id}`"
          @click="emit('open', doc, $event)"
          @auxclick.middle="emit('open', doc, $event)"
          @dragstart="emit('doc-dragstart', $event, doc)"
          @dragend="emit('doc-dragend')"
        >
          <td
            class="w-14 min-w-14 max-w-14 px-1.5 py-4 text-center"
            :data-testid="`doc-actions-cell-${doc.id}`"
            @click.stop
            @auxclick.stop
          >
            <BaseActionButton
              action="more"
              class="rounded-lg text-text-subtle transition-colors hover:bg-surface-raised hover:text-text-default
                     outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/40"
              :label="`Acciones de ${doc.title}`"
              @click="emit('action', doc)"
            />
          </td>
          <!-- `relative` es el marco contra el que se estira el enlace del
               título: así toda la celda es el enlace, no sólo las letras. -->
          <td class="relative min-w-0 overflow-hidden px-6 py-4">
<div class="flex min-w-0 items-center gap-2">
            <span class="shrink-0 text-xs tabular-nums text-text-muted" data-testid="document-visible-id">#{{ doc.id }}</span>
            <BaseOverflowText
              :to="editToFor(doc)"
              :text="doc.title"
              :lines="1"
              stretch
              :test-id="`document-open-${doc.id}`"
              class="min-w-0 max-w-full"
              content-classes="text-sm font-medium leading-snug text-text-default hover:text-text-brand transition-colors"
            />
            </div>
            <!-- La metadata vive en un renglón propio. Sin carpeta se oculta
                 desde desktop para no reservar una línea vacía bajo el título. -->
            <div
              class="relative z-10 mt-2 flex min-w-0 max-w-full flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-muted"
              :class="doc.folder_name || doc.thread_summary ? '' : 'panel-desktop:hidden'"
              :data-testid="`document-title-meta-${doc.id}`"
            >
              <!-- design-tokens: allow-raw-button — el badge es la puerta al hilo -->
              <button
                v-if="doc.thread_summary"
                type="button"
                class="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/40"
                :aria-label="`Abrir el hilo ${doc.thread_summary.title}`"
                :data-testid="`document-thread-open-${doc.id}`"
                @click.stop="emit('thread', doc)"
                @auxclick.stop
              >
                <BaseBadge
                  variant="info"
                  size="sm"
                  :title="doc.thread_summary.title"
                  :data-testid="`document-thread-badge-${doc.id}`"
                >
                  Hilo · {{ doc.thread_summary.document_count }}
                </BaseBadge>
              </button>
              <span
                v-if="doc.folder_name"
                class="inline-flex min-w-0 max-w-full flex-wrap items-center gap-1 rounded bg-surface-raised px-2 py-0.5 text-2xs font-medium text-text-muted [overflow-wrap:anywhere]"
                :title="`Carpeta: ${doc.folder_name}`"
                :data-testid="`document-folder-badge-${doc.id}`"
              >
                <span aria-hidden="true">📁</span>
                <span class="min-w-0 max-w-full [overflow-wrap:anywhere]">{{ doc.folder_name }}</span>
              </span>
              <span
                v-if="doc.client_display_name || doc.client_name"
                class="min-w-0 max-w-full [overflow-wrap:anywhere] panel-desktop:hidden"
              >
                {{ doc.client_display_name || doc.client_name }}
              </span>
              <span
                v-if="doc.project_name"
                class="min-w-0 max-w-full [overflow-wrap:anywhere] panel-desktop:hidden"
              >{{ doc.project_name }}</span>
            </div>
          </td>
          <td
            class="hidden px-6 py-4 panel-landscape:table-cell"
            :data-testid="`doc-states-cell-${doc.id}`"
          >
            <BaseBadge
              v-if="doc.is_archived"
              variant="neutral"
              size="sm"
              data-testid="doc-archived-badge"
            >
              Archivado
            </BaseBadge>
            <BaseBadge
              v-else-if="doc.display_state"
              :variant="doc.display_state.variant"
              size="sm"
              :data-testid="`doc-derived-state-${doc.id}`"
            >
              {{ doc.display_state.label }}
            </BaseBadge>
            <DocumentStateList v-else :episodes="doc.active_states" :max-visible="3" />
          </td>
          <td
            class="px-6 py-4 text-sm text-text-muted tabular-nums"
            :data-testid="`doc-date-cell-${doc.id}`"
          >
            <template v-if="doc.is_archived">
              <span data-testid="doc-archived-at">{{ formatDateTime(doc.archived_at || doc.created_at) }}</span>
              <span class="block text-xs text-text-subtle">{{ archivedAgeLabel(doc.archived_at || doc.created_at) }}</span>
            </template>
            <template v-else>{{ formatDocumentDate(doc.created_at) }}</template>
          </td>
          <td class="hidden min-w-0 overflow-hidden px-6 py-4 text-sm panel-desktop:table-cell" :data-testid="`doc-client-cell-${doc.id}`">
            <span v-if="doc.client_display_name" class="block min-w-0 max-w-full text-text-default [overflow-wrap:anywhere]">{{ doc.client_display_name }}</span>
            <!-- Nombre libre heredado, sin cliente vinculado: en itálica para
                 que se note que aún no es una relación. -->
            <span
              v-else-if="doc.client_name"
              class="block min-w-0 max-w-full italic text-text-subtle [overflow-wrap:anywhere]"
              title="Nombre libre, sin cliente vinculado"
            >{{ doc.client_name }}</span>
            <span v-else class="text-text-subtle">—</span>
          </td>
          <td class="hidden min-w-0 overflow-hidden px-6 py-4 text-sm panel-desktop:table-cell" :data-testid="`doc-project-cell-${doc.id}`">
            <span v-if="doc.project_name" class="block min-w-0 max-w-full text-text-default [overflow-wrap:anywhere]">{{ doc.project_name }}</span>
            <span v-else class="text-text-subtle">—</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
