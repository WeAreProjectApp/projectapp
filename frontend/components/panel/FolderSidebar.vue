<template>
  <aside class="bg-surface rounded-xl shadow-sm border border-border-muted flex flex-col">
    <div class="shrink-0 border-b border-border-muted px-4 py-3">
      <h2 class="text-xs font-semibold uppercase tracking-wider text-text-muted">Navegar por</h2>
      <EntityNavigationModeSwitch
        class="mt-3"
        :model-value="navigationMode"
        :disabled="navigationSaving"
        :aria-label="`Agrupar ${itemLabel}`"
        :test-id-prefix="`${testIdPrefix}-mode`"
        @update:model-value="$emit('update:navigation-mode', $event)"
      />
    </div>

    <div class="shrink-0 border-b border-border-muted p-3">
      <BaseInput
        v-model="navigationSearch"
        size="sm"
        :placeholder="navigationMode === 'project' ? 'Buscar proyecto...' : 'Buscar cliente...'"
        :aria-label="navigationMode === 'project' ? 'Buscar proyecto' : 'Buscar cliente'"
        :data-testid="`${testIdPrefix}-navigation-search`"
      />
    </div>

    <div
      class="flex shrink-0 items-center justify-between gap-2 border-b border-border-muted px-3 py-2.5 transition-colors"
      :class="showInactiveProjects ? 'bg-warning-soft' : ''"
      data-testid="inactive-projects-control"
    >
      <span class="flex items-center gap-2 min-w-0">
        <span class="text-sm truncate" :class="showInactiveProjects ? 'font-medium text-text-default' : 'text-text-muted'">
          {{ lifecycleToggleLabel }}
        </span>
      </span>
      <BaseToggle
        :model-value="showInactiveProjects"
        size="sm"
        :aria-label="lifecycleToggleLabel"
        data-testid="inactive-projects-toggle"
        @update:model-value="$emit('toggle-inactive-projects', $event)"
      />
    </div>

    <ul class="p-2 space-y-1 flex-1 overflow-y-auto" role="list" data-testid="folder-list">
      <li role="presentation">
        <!-- design-tokens: allow-raw-button — cabecera de sección plegable, no una acción -->
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-muted transition-colors hover:bg-surface-muted"
          :class="touchMode ? 'min-h-11' : ''"
          :aria-expanded="sidebarSections.entities"
          :aria-controls="entitiesSectionId"
          data-testid="entities-section-toggle"
          @click="toggleSidebarSection('entities')"
        >
          <span class="flex items-center gap-2">
            <BaseActionIcon :action="sidebarSections.entities ? 'collapse' : 'expand'" />
            {{ entitiesSectionLabel }}
          </span>
        </button>
        <BaseCollapse :id="entitiesSectionId" :open="sidebarSections.entities">
          <ul class="space-y-1" role="list">
            <li>
        <!-- design-tokens: allow-raw-button — selectable navigation row, not an action -->
        <button
          type="button"
          class="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition-all"
          :class="[navigationEntryClass('all'), touchMode ? 'min-h-11' : 'min-h-10']"
          :aria-current="navigationAriaCurrent('all')"
          :data-testid="`${testIdPrefix}-navigation-all`"
          @click="$emit('select-entity', 'all')"
        >
          <span>Todos</span>
          <span class="flex shrink-0 items-center gap-2 text-xs text-text-subtle">
            <span class="flex items-center gap-0.5" :aria-label="`${navigationAllCounts.folders} carpetas`">
              <!-- panel-action-icons: allow-status-glyph — identifies the adjacent folder inventory. -->
              <FolderIcon class="h-3 w-3" aria-hidden="true" />
              {{ navigationAllCounts.folders }}
            </span>
            <span class="flex items-center gap-0.5" :aria-label="`${navigationAllCounts.documents} ${itemLabel}`">
              <!-- panel-action-icons: allow-status-glyph — identifies the adjacent document inventory. -->
              <DocumentTextIcon class="h-3 w-3" aria-hidden="true" />
              {{ navigationAllCounts.documents }}
            </span>
          </span>
        </button>
      </li>

      <li>
        <!-- design-tokens: allow-raw-button — selectable navigation row, not an action -->
        <button
          type="button"
          class="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition-all"
          :class="[navigationEntryClass('none'), touchMode ? 'min-h-11' : 'min-h-10']"
          :aria-current="navigationAriaCurrent('none')"
          :data-testid="`${testIdPrefix}-navigation-unassigned`"
          @click="$emit('select-entity', 'none')"
        >
          <span>{{ navigationMode === 'project' ? 'Sin proyecto' : 'Sin cliente' }}</span>
          <span class="flex shrink-0 items-center gap-2 text-xs text-text-subtle">
            <span class="flex items-center gap-0.5" :aria-label="`${navigationUnassignedCounts.folders} carpetas`">
              <!-- panel-action-icons: allow-status-glyph — identifies the adjacent folder inventory. -->
              <FolderIcon class="h-3 w-3" aria-hidden="true" />
              {{ navigationUnassignedCounts.folders }}
            </span>
            <span class="flex items-center gap-0.5" :aria-label="`${navigationUnassignedCounts.documents} ${itemLabel}`">
              <!-- panel-action-icons: allow-status-glyph — identifies the adjacent document inventory. -->
              <DocumentTextIcon class="h-3 w-3" aria-hidden="true" />
              {{ navigationUnassignedCounts.documents }}
            </span>
          </span>
        </button>
      </li>

      <li v-for="entry in visibleActiveNavigationEntries" :key="entry.id">
        <!-- design-tokens: allow-raw-button — selectable navigation row, not an action -->
        <button
          type="button"
          class="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition-all"
          :class="[navigationEntryClass(entry.id), touchMode ? 'min-h-11' : 'min-h-10']"
          :aria-current="navigationAriaCurrent(entry.id)"
          :aria-label="navigationRowLabel(entry)"
          :data-testid="`${testIdPrefix}-navigation-${navigationMode}-${entry.id}`"
          @click="$emit('select-entity', entry.id)"
        >
          <span class="min-w-0 flex-1">
            <span class="block truncate" :title="entry.name">{{ entry.name }}</span>
            <span v-if="entry.unavailable" class="block text-2xs text-warning-strong">
              No disponible; quita esta selección para continuar.
            </span>
            <span v-else-if="navigationEntrySubtitle(entry)" class="block truncate text-2xs text-text-subtle">
              {{ navigationEntrySubtitle(entry) }}
            </span>
          </span>
          <span class="flex shrink-0 items-center gap-2 text-xs text-text-subtle">
            <span class="flex items-center gap-0.5">
              <!-- panel-action-icons: allow-status-glyph — identifies the adjacent folder inventory. -->
              <FolderIcon class="h-3 w-3" aria-hidden="true" />
              {{ navigationCounts(entry.counts).folders }}
            </span>
            <span class="flex items-center gap-0.5">
              <!-- panel-action-icons: allow-status-glyph — identifies the adjacent document inventory. -->
              <DocumentTextIcon class="h-3 w-3" aria-hidden="true" />
              {{ navigationCounts(entry.counts).documents }}
            </span>
          </span>
        </button>
      </li>

      <li v-if="visibleArchivedNavigationEntries.length" role="presentation">
        <details open :data-testid="`${testIdPrefix}-navigation-archived-group`">
          <summary class="flex cursor-pointer items-center justify-between gap-2 rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-muted hover:bg-surface-muted">
            <span>{{ navigationArchivedGroupLabel }}</span>
            <span class="font-normal normal-case text-text-subtle">{{ visibleArchivedNavigationEntries.length }}</span>
          </summary>
          <ul class="mt-1 space-y-1" role="list">
            <li v-for="entry in visibleArchivedNavigationEntries" :key="entry.id">
              <!-- design-tokens: allow-raw-button — selectable navigation row, not an action -->
              <button
                type="button"
                class="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm transition-all"
                :class="[navigationEntryClass(entry.id), touchMode ? 'min-h-11' : 'min-h-10']"
                :aria-current="navigationAriaCurrent(entry.id)"
                :aria-label="navigationRowLabel(entry)"
                :data-testid="`${testIdPrefix}-navigation-${navigationMode}-${entry.id}`"
                @click="$emit('select-entity', entry.id)"
              >
                <span class="min-w-0 flex-1">
                  <span class="block truncate" :title="entry.name">{{ entry.name }}</span>
                  <span v-if="entry.unavailable" class="block text-2xs text-warning-strong">
                    No disponible; quita esta selección para continuar.
                  </span>
                  <span v-else-if="navigationEntrySubtitle(entry)" class="block truncate text-2xs text-text-subtle">
                    {{ navigationEntrySubtitle(entry) }}
                  </span>
                </span>
                <span class="flex shrink-0 items-center gap-2 text-xs text-text-subtle">
                  <span class="flex items-center gap-0.5">
                    <!-- panel-action-icons: allow-status-glyph — identifies the adjacent folder inventory. -->
                    <FolderIcon class="h-3 w-3" aria-hidden="true" />
                    {{ navigationCounts(entry.counts).folders }}
                  </span>
                  <span class="flex items-center gap-0.5">
                    <!-- panel-action-icons: allow-status-glyph — identifies the adjacent document inventory. -->
                    <DocumentTextIcon class="h-3 w-3" aria-hidden="true" />
                    {{ navigationCounts(entry.counts).documents }}
                  </span>
                </span>
              </button>
            </li>
          </ul>
        </details>
      </li>

      <li v-if="navigationLoading" class="px-3 py-4 text-center text-xs text-text-subtle">
        Cargando {{ navigationMode === 'project' ? 'proyectos' : 'clientes' }}…
      </li>
      <li
        v-else-if="!visibleActiveNavigationEntries.length && !visibleArchivedNavigationEntries.length"
        class="px-3 py-4 text-center text-xs text-text-subtle"
        :data-testid="navigationMode === 'project' ? 'project-empty-fallback' : undefined"
      >
        {{ navigationEmptyMessage }}
      </li>
      <li v-if="navigationError" class="rounded-lg bg-danger-soft px-3 py-2 text-xs text-text-default">
        <p>{{ navigationError }}</p>
        <button
          type="button"
          class="mt-1 font-medium text-text-brand hover:text-text-default"
          :data-testid="`${testIdPrefix}-navigation-retry`"
          @click="$emit('retry-navigation')"
        >
          Reintentar
        </button>
            </li>
          </ul>
        </BaseCollapse>
      </li>

      <li
        class="flex items-center justify-between gap-2 border-y border-border-muted px-3 py-2.5 transition-colors"
        :class="archivedMode ? 'bg-warning-soft' : ''"
        data-testid="document-archive-control"
      >
        <span class="flex min-w-0 items-center gap-2">
          <svg class="h-3.5 w-3.5 shrink-0 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
          </svg>
          <span class="truncate text-sm" :class="archivedMode ? 'font-medium text-text-default' : 'text-text-muted'">
            Ver {{ itemLabel }} archivados
          </span>
          <span class="shrink-0 text-xs text-text-subtle" data-testid="folder-archived-count">{{ archivedCount }}</span>
        </span>
        <BaseToggle
          :model-value="archivedMode"
          :disabled="scopeLocked"
          size="sm"
          :aria-label="`Ver ${itemLabel} archivados`"
          disabled-reason="La búsqueda recorre activos y archivados."
          data-testid="folder-archived-entry"
          @update:model-value="$emit('toggle-archived', $event)"
        />
      </li>

      <li role="presentation" data-testid="manual-folder-section">
        <div>
          <!-- design-tokens: allow-raw-button — cabecera de sección plegable, no una acción -->
          <button
            type="button"
            class="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-muted transition-colors hover:bg-surface-muted"
            :class="touchMode ? 'min-h-11' : ''"
            :aria-expanded="sidebarSections.manual"
            :aria-controls="manualSectionId"
            data-testid="manual-folder-section-toggle"
            @click="toggleSidebarSection('manual')"
          >
            <span class="flex items-center gap-2">
              <BaseActionIcon :action="sidebarSections.manual ? 'collapse' : 'expand'" />
              Carpetas propias
            </span>
            <span class="font-normal normal-case text-text-subtle" data-testid="manual-folder-section-count">
              {{ sectionInventory(manualFolders) }}
            </span>
          </button>
          <BaseCollapse :id="manualSectionId" :open="sidebarSections.manual">
          <div class="flex items-center justify-end px-3 py-1">
            <button
              type="button"
              class="text-xs font-medium text-text-brand hover:text-text-default"
              @click="$emit('manage')"
            >
              Gestionar
            </button>
          </div>
          <ul class="space-y-1" role="list">
            <li>
              <!-- design-tokens: allow-raw-button — selectable list row, not an action -->
              <button
                type="button"
                class="flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-all"
                :class="[entryClass('none'), dropZoneClass('none'), touchMode ? 'min-h-11' : '']"
                :aria-current="ariaCurrent('none')"
                @click="$emit('select', 'none')"
                @dragover.prevent="dragOverId = 'none'"
                @dragleave="dragOverId = null"
                @drop.prevent="onDrop(null)"
              >
                <span>Sin carpeta</span>
                <BaseActionIcon v-if="isDragging" action="move" class="text-text-subtle" />
                <span v-else class="text-xs text-text-subtle">{{ unfiledCount }}</span>
              </button>
            </li>
          </ul>
          <p v-if="!manualFolders.length" class="px-3 py-2 text-xs text-text-subtle">
            No hay carpetas propias en este ámbito.
          </p>

      <!-- Folder entries — draggable to reorder, also drop targets for documents -->
      <draggable
        v-else
        v-model="localFolders"
        item-key="id"
        handle=".folder-drag-handle"
        ghost-class="opacity-40"
        chosen-class="ring-1 ring-emerald-300"
        :disabled="isDragging"
        tag="div"
        @start="isFolderDragging = true"
        @end="handleFolderReorder"
      >
        <template #item="{ element: folder }">
          <li :key="folder.id" class="group">
            <div
              class="flex items-center rounded-lg transition-all"
              :class="[entryClass(folder.id), dropZoneClass(folder)]"
              @dragover.prevent="onFolderDragOver(folder)"
              @dragleave="dragOverId = null"
              @drop.prevent="onFolderDrop(folder)"
            >
              <!--
                Comparte padding, radio y tamaño con Todos/Sin carpeta para que
                la columna entera lea sobre un único eje.

                Dos cifras: las subcarpetas que verás al entrar (directas) y los
                documentos que la carpeta guarda EN TOTAL, contando lo que vive
                en sus subcarpetas. Un contador directo de documentos decía cero
                de una carpeta llena y mandaba a buscar al lugar equivocado.
                Los íconos van `aria-hidden` y el rótulo del botón lleva el
                inventario en palabras: dos números pelados no dicen nada leídos.
              -->
              <!-- design-tokens: allow-raw-button — selectable list row, not an action -->
              <button
                type="button"
                class="flex-1 min-w-0 flex items-center gap-1 px-3 py-2 text-sm text-left"
                :class="touchMode ? 'min-h-11' : ''"
                :aria-current="ariaCurrent(folder.id)"
                :aria-label="rowLabel(folder)"
                @click="$emit('select', folder.id)"
              >
                <!-- El cliente va debajo del nombre y sólo si la carpeta lo
                     tiene: es la línea que dice de quién es sin abrirla.
                     `block` y no `flex`, y con piso de ancho: sumar el ícono de
                     editar dejó la fila sin holgura y el nombre se encogía
                     hasta desaparecer. Con `min-w-16` siempre se lee algo, y lo
                     que sobra trunca — el `title` lo recupera. -->
                <span class="flex-1 min-w-16 block">
                  <span class="block truncate" :title="folder.name">{{ folder.name }}</span>
                  <span
                    v-if="folder.client_display_name"
                    class="block truncate text-2xs text-text-subtle"
                    :data-testid="`folder-client-${folder.id}`"
                    :title="folder.client_display_name"
                  >{{ folder.client_display_name }}</span>
                </span>
                <!-- Directa a propósito, a diferencia del contador de al lado:
                     la insignia promete «clic para verlos» y ese clic entra a
                     ESTA carpeta, cuyo listado no es recursivo. -->
                <FolderArchivedBadge
                  v-if="folderStore.archivedContentCount(folder)"
                  :count="folderStore.archivedContentCount(folder)"
                  :folder-name="folder.name"
                  @view="$emit('view-archived', folder)"
                />
                <template v-if="!isDragging || dragOverId !== folder.id">
                  <span
                    v-if="rowCounts(folder).subs"
                    class="flex items-center gap-0.5 text-xs text-text-subtle flex-shrink-0"
                    data-testid="folder-subfolder-count"
                  >
                    <!-- panel-action-icons: allow-status-glyph — identifies the adjacent subfolder count. -->
                    <FolderIcon class="h-3 w-3" aria-hidden="true" />
                    {{ rowCounts(folder).subs }}
                  </span>
                  <span
                    class="flex items-center gap-0.5 text-xs text-text-subtle flex-shrink-0"
                    data-testid="folder-document-count"
                  >
                    <!-- panel-action-icons: allow-status-glyph — identifies the adjacent document count. -->
                    <DocumentTextIcon class="h-3 w-3" aria-hidden="true" />
                    {{ rowCounts(folder).docs }}
                  </span>
                </template>
                <BaseActionIcon v-else action="move" class="text-success-strong" />
              </button>

              <!-- Clúster derecho: reordenar (hover) + archivar + eliminar. -->
              <div v-if="!folder.is_system_managed" class="flex items-center flex-shrink-0 pr-1.5">
                <div
                  class="folder-drag-handle touch-reveal touch-drag-handle flex cursor-grab items-center justify-center text-text-subtle transition-opacity active:cursor-grabbing dark:text-text-muted"
                  :class="[
                    touchMode ? 'w-8 min-h-11 opacity-100' : 'w-5 opacity-0 group-hover:opacity-100',
                    { invisible: isDragging },
                  ]"
                  title="Arrastrar para reordenar"
                >
                  <BaseActionIcon action="sort" />
                </div>

                <!-- Editar vive acá por lo mismo que archivar y eliminar: es
                     igual de frecuente, y hasta ahora era la única de las tres
                     que había que ir a buscar al modal de NUEVA carpeta. -->
                <BaseActionButton
                  action="edit"
                  variant="ghost"
                  size="sm"
                  :label="`Editar carpeta ${folder.name}`"
                  tooltip="Editar carpeta"
                  :class="['opacity-70 hover:opacity-100 focus-visible:opacity-100 transition-opacity', touchMode ? 'min-h-11 min-w-11' : '']"
                  data-testid="folder-edit"
                  @click="$emit('edit', folder)"
                />

                <!-- Archivar vive acá y no sólo en el gestor de carpetas: es la
                     salida para una carpeta con contenido, que no se puede
                     eliminar. Por eso está siempre habilitado. -->
                <BaseActionButton
                  action="archive"
                  variant="ghost"
                  size="sm"
                  :label="`Archivar carpeta ${folder.name}`"
                  tooltip="Archivar carpeta"
                  :class="['opacity-70 hover:opacity-100 focus-visible:opacity-100 transition-opacity', touchMode ? 'min-h-11 min-w-11' : '']"
                  data-testid="folder-archive"
                  @click="$emit('archive', folder)"
                />

                <!-- Eliminar sólo se ofrece cuando de verdad se puede: el
                     backend responde 409 con cualquier contenido, archivado
                     incluido, así que el conteo tiene que mirarlo todo. -->
                <BaseActionButton
                  action="delete"
                  variant="danger-ghost"
                  size="sm"
                  :disabled="hasContent(folder)"
                  :disabled-reason="deleteTooltip(folder)"
                  :label="`Eliminar carpeta ${folder.name}`"
                  :tooltip="deleteTooltip(folder)"
                  :class="['opacity-70 hover:opacity-100 focus-visible:opacity-100 transition-opacity', touchMode ? 'min-h-11 min-w-11' : '']"
                  data-testid="folder-delete"
                  @click="$emit('delete', folder)"
                />
              </div>
            </div>
          </li>
        </template>
          </draggable>
          </BaseCollapse>
        </div>
      </li>
    </ul>

    <div class="p-3 border-t border-border-muted flex-shrink-0">
      <BaseButton variant="secondary" size="md" class="w-full" @click="$emit('manage')">
        <BaseActionIcon action="create" />
        Nueva carpeta
      </BaseButton>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref, useId, watch } from 'vue';
import { DocumentTextIcon, FolderIcon } from '@heroicons/vue/24/outline';
import draggable from 'vuedraggable';
import EntityNavigationModeSwitch from '~/components/panel/EntityNavigationModeSwitch.vue';
import FolderArchivedBadge from '~/components/panel/documents/FolderArchivedBadge.vue';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import BaseCollapse from '~/components/base/BaseCollapse.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import { usePanelSidebarSections } from '~/composables/usePanelSidebarSections';
import { folderRowLabel, folderRowSummary, isManagedFolderKind, scopedCounts } from '~/utils/documentStatus';

const props = defineProps({
  adapter: { type: Object, required: true },
  testIdPrefix: { type: String, default: 'documents' },
  unassignedManualOnly: { type: Boolean, default: true },
  itemLabel: { type: String, default: 'documentos' },
  itemShortLabel: { type: String, default: 'docs' },
  storageKey: { type: String, default: 'projectapp-documents-sidebar-sections' },
  folders: { type: Array, default: () => [] },
  activeId: { type: [String, Number], default: 'all' },
  archiveScope: { type: String, default: 'active' },
  archivedCount: { type: Number, default: 0 },
  showInactiveProjects: { type: Boolean, default: false },
  unfiledCount: { type: Number, default: 0 },
  navigationMode: { type: String, default: 'project' },
  navigationSelection: { type: [String, Number], default: 'all' },
  navigationFacets: {
    type: Object,
    default: () => ({
      totals: {},
      unassigned: { project: {}, client: {} },
      projects: [],
      clients: [],
    }),
  },
  navigationLoading: { type: Boolean, default: false },
  navigationSaving: { type: Boolean, default: false },
  navigationError: { type: String, default: '' },
  isDragging: { type: Boolean, default: false },
  draggingFolderId: { type: [String, Number], default: null },
  // La búsqueda recorre los dos estados, así que el interruptor queda inerte
  // mientras hay consulta — misma regla que el control de la barra, porque dos
  // mandos del mismo eje que se comportan distinto vuelven a mentir.
  scopeLocked: { type: Boolean, default: false },
  touchMode: { type: Boolean, default: false },
});

const emit = defineEmits([
  'select', 'manage', 'folder-drop', 'edit', 'delete', 'archive', 'view-archived',
  'toggle-archived', 'toggle-inactive-projects', 'update:navigation-mode',
  'select-entity', 'retry-navigation',
]);

const folderStore = props.adapter;
const dragOverId = ref(null);
const localFolders = ref([]);
const isFolderDragging = ref(false);
const navigationSearch = ref('');

// El panel se monta dos veces a la vez —fijo y dentro del drawer táctil—, así
// que el estado abierto/cerrado se comparte (vive en el composable) pero los
// `id` de `aria-controls` NO pueden: dos nodos con el mismo id romperían la
// relación del trigger con su cuerpo.
const { sections: sidebarSections, toggle: toggleSidebarSection } = usePanelSidebarSections(props.storageKey, { entities: true, manual: true });
const sectionUid = useId();
const entitiesSectionId = `documents-sidebar-entities-${sectionUid}`;
const manualSectionId = `documents-sidebar-manual-${sectionUid}`;

const entitiesSectionLabel = computed(() => (
  props.navigationMode === 'project' ? 'Proyectos' : 'Clientes'
));

// «Propia» es la raíz sin NINGUNA marca de pertenencia. Las condiciones son
// redundantes a propósito: un payload parcial que perdiera una todavía deja
// fuera de esta sección lo que ya tiene su propio espacio.
//
// `isManagedFolderKind` centraliza qué clases posee el sistema, así que sumar
// una tercera es una sola edición y no siete comparaciones repartidas.
const manualFolders = computed(() => props.folders
  .filter((folder) => (
    folder.parent == null
    && !isManagedFolderKind(folder)
    && folder.managed_project == null
    && folder.managed_client == null
    && (!props.unassignedManualOnly || (folder.project == null && folder.client == null))
  )));

const baseNavigationEntries = computed(() => (
  props.navigationMode === 'project'
    ? props.navigationFacets.projects || []
    : props.navigationFacets.clients || []
));

const navigationEntries = computed(() => {
  const rows = [...baseNavigationEntries.value];
  const selected = props.navigationSelection;
  if (
    typeof selected === 'number'
    && !rows.some((entry) => entry.id === selected)
  ) {
    rows.unshift({
      id: selected,
      name: `${props.navigationMode === 'project' ? 'Proyecto' : 'Cliente'} #${selected}`,
      unavailable: true,
      is_visible: true,
      catalog_bucket: 'active',
      counts: {},
    });
  }
  return rows;
});

const searchedNavigationEntries = computed(() => {
  const query = navigationSearch.value.trim().toLocaleLowerCase('es');
  if (!query) return navigationEntries.value;
  return navigationEntries.value.filter(
    (entry) => entry.name.toLocaleLowerCase('es').includes(query),
  );
});

function isArchivedNavigationEntry(entry) {
  if (entry.catalog_bucket) return entry.catalog_bucket === 'archived';
  return props.navigationMode === 'client'
    ? Boolean(entry.is_archived)
    : entry.is_visible === false;
}

const activeNavigationEntries = computed(() => searchedNavigationEntries.value
  .filter((entry) => !isArchivedNavigationEntry(entry)));
const archivedNavigationEntries = computed(() => searchedNavigationEntries.value
  .filter(isArchivedNavigationEntry));
// El interruptor de ciclo de vida es EXCLUYENTE, no aditivo: encendido deja
// ver sólo los no activos, apagado sólo los activos. Los dos computed son las
// dos caras de la misma condición, por eso se leen juntos.
//
// Gobierna los DOS modos. Antes sólo aplicaba a proyectos y los clientes
// archivados se listaban siempre, así que el mismo panel se comportaba de dos
// maneras según el modo — y archivar un cliente no lo sacaba de la vista.
const visibleActiveNavigationEntries = computed(() => (
  props.showInactiveProjects ? [] : activeNavigationEntries.value
));
const visibleArchivedNavigationEntries = computed(() => (
  props.showInactiveProjects ? archivedNavigationEntries.value : []
));
const lifecycleToggleLabel = computed(() => (
  props.navigationMode === 'project'
    ? 'Ver proyectos no activos'
    : 'Ver clientes archivados'
));
const navigationArchivedGroupLabel = computed(() => (
  props.navigationMode === 'project' ? 'Proyectos archivados' : 'Clientes archivados'
));
const navigationEmptyMessage = computed(() => {
  if (navigationSearch.value.trim()) return 'No hay coincidencias.';
  if (props.showInactiveProjects) {
    return props.navigationMode === 'project'
      ? 'No hay proyectos no activos.'
      : 'No hay clientes archivados.';
  }
  return `No hay ${props.navigationMode === 'project' ? 'proyectos' : 'clientes'} disponibles.`;
});

const navigationAllCounts = computed(() => navigationCounts(props.navigationFacets.totals));
const navigationUnassignedCounts = computed(() => navigationCounts(
  props.navigationFacets.unassigned?.[props.navigationMode],
));

watch(() => props.navigationMode, () => {
  navigationSearch.value = '';
});

watch(manualFolders, (v) => {
  localFolders.value = [...v];
}, { immediate: true });

const ACTIVE_CLASS = 'bg-primary-soft text-text-brand font-medium';
const INACTIVE_CLASS = 'text-text-default hover:bg-surface-muted';

function entryClass(id) {
  return props.activeId === id ? ACTIVE_CLASS : INACTIVE_CLASS;
}

function navigationIsSelected(id) {
  return String(props.navigationSelection) === String(id);
}

function navigationEntryClass(id) {
  return navigationIsSelected(id) ? ACTIVE_CLASS : INACTIVE_CLASS;
}

function navigationAriaCurrent(id) {
  return navigationIsSelected(id) ? 'page' : undefined;
}

function navigationCounts(counts = {}) {
  const active = counts?.active || {};
  const archived = counts?.archived || {};
  if (props.archiveScope === 'archived') {
    return {
      folders: archived.folders || 0,
      documents: archived.documents || 0,
    };
  }
  if (props.archiveScope === 'all') {
    return {
      folders: (active.folders || 0) + (archived.folders || 0),
      documents: (active.documents || 0) + (archived.documents || 0),
    };
  }
  return {
    folders: active.folders || 0,
    documents: active.documents || 0,
  };
}

function navigationEntrySubtitle(entry) {
  if (props.navigationMode === 'project') return entry.state?.name || 'Sin estado';
  return entry.is_archived ? 'Cliente inactivo' : '';
}

function navigationRowLabel(entry) {
  const counts = navigationCounts(entry.counts);
  const unavailable = entry.unavailable ? ', no disponible' : '';
  return `${entry.name}${unavailable}, ${counts.folders} carpetas, ${counts.documents} ${props.itemLabel}`;
}

// El resaltado de la fila de carpeta vive en el div contenedor (comparte la
// caja con los íconos de acción), así que la marca semántica va en el botón:
// es el único gancho estable para «dónde dice el panel que estoy».
function ariaCurrent(id) {
  return props.activeId === id ? 'page' : undefined;
}

/**
 * Las dos cifras de la fila: subcarpetas DIRECTAS y documentos del subárbol.
 *
 * Las subcarpetas se quedan directas porque responden «qué voy a ver si entro»,
 * y entrar lista `childrenOf(id, scope)` — un total recursivo prometería filas
 * que ese clic no muestra.
 */
function rowCounts(folder) {
  return {
    subs: scopedCounts(folder, props.archiveScope).subs,
    docs: folderStore.recursiveDocumentCount(folder, props.archiveScope),
  };
}

function rowLabel(folder) {
  return folderRowLabel(folder.name, rowCounts(folder)).replace(/documentos/g, props.itemLabel);
}

function sectionInventory(folders) {
  const totals = folders.reduce((result, folder) => {
    const counts = folderStore.rollupOf(folder, props.archiveScope);
    result.docs += counts.docs;
    result.folders += 1 + counts.subs;
    return result;
  }, { docs: 0, folders: 0 });
  return `${totals.folders} carp. · ${totals.docs} ${props.itemShortLabel}`;
}

// Ojo: `hasContent` y `deleteTooltip` se quedan con el conteo DIRECTO a
// propósito. Espejan el 409 de `delete_document_folder`, que cuenta
// `folder.documents` y `folder.children` de un salto y sin excluir archivados;
// un tooltip recursivo diría «contiene 12 documentos» donde el servidor
// responde «tiene 1 subcarpeta». No unificar con el contador de la fila.
function hasContent(folder) {
  return folderStore.totalContentCount(folder) > 0;
}

function deleteTooltip(folder) {
  if (!hasContent(folder)) return 'Eliminar carpeta';
  return `No se puede eliminar: contiene ${folderRowSummary(folder, 'all').replace(/documentos/g, props.itemLabel)}. `
    + 'Archívala en su lugar.';
}

// El interruptor sólo está encendido en el scope archivado puro. Con 'all' la
// lista mezcla los dos estados, y encenderlo ahí diría que se está viendo sólo
// el archivo; ese caso lo declara el rótulo de la cabecera del listado.
const archivedMode = computed(() => props.archiveScope === 'archived');

function dropZoneClass(folder) {
  if (folder?.is_system_managed) return '';
  const id = folder?.id ?? folder;
  // Acepta documentos (props.isDragging) o carpetas en arrastre para anidar.
  const anyDrag = props.isDragging || props.draggingFolderId != null;
  if (!anyDrag || isFolderDragging.value) return '';
  if (dragOverId.value === id) {
    return 'ring-2 ring-emerald-400 bg-primary-soft !text-text-brand dark:!text-emerald-300';
  }
  return 'ring-1 ring-dashed ring-border-default';
}

function onDrop(folderId) {
  dragOverId.value = null;
  emit('folder-drop', folderId);
}

function onFolderDragOver(folder) {
  if (!folder.is_system_managed && !isFolderDragging.value) {
    dragOverId.value = folder.id;
  }
}

function onFolderDrop(folder) {
  if (!folder.is_system_managed && !isFolderDragging.value) onDrop(folder.id);
}

async function handleFolderReorder() {
  isFolderDragging.value = false;
  const newIds = localFolders.value
    .filter((folder) => !folder.is_system_managed)
    .map((folder) => folder.id);
  const previousIds = manualFolders.value
    .filter((folder) => !folder.is_system_managed)
    .map((folder) => folder.id);
  const unchanged = newIds.every((id, i) => id === previousIds[i]);
  if (unchanged) return;
  const result = await folderStore.reorderFolders(newIds);
  if (!result.success) {
    await folderStore.fetchFolders();
  }
}
</script>
