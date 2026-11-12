<template>
  <draggable
    v-model="localSiblings"
    item-key="id"
    handle=".folder-tree-handle"
    ghost-class="opacity-40"
    chosen-class="ring-2 ring-emerald-400"
    drag-class="rotate-1"
    class="space-y-1"
    :move="canMove"
    @end="onReorderEnd"
  >
    <template #item="{ element: folder }">
      <div :key="folder.id">
        <div
          class="group flex items-center gap-2 px-2 py-2 rounded-lg border transition-all"
          :class="rowClass(folder)"
          :style="{ marginLeft: `${depth * 18}px` }"
        >
          <div
            v-if="!isManagedFolderKind(folder) && !folder.is_system_managed"
            class="folder-tree-handle flex-shrink-0 w-4 flex items-center justify-center
                   text-text-subtle cursor-grab active:cursor-grabbing"
            title="Arrastrar para reordenar"
          >
            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 6a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm8 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3zM8 13.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm8 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3zM8 21a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm8 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3z" />
            </svg>
          </div>
          <div v-else class="w-4 flex-shrink-0" aria-hidden="true"></div>

          <div class="w-6 h-6 rounded-lg bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center flex-shrink-0">
            <svg class="w-3 h-3 text-amber-500 dark:text-amber-400" fill="currentColor" viewBox="0 0 24 24">
              <path d="M3 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
            </svg>
          </div>

          <span class="flex-1 min-w-0 text-sm font-medium text-text-default truncate">
            {{ folder.name }}
          </span>
          <BaseBadge v-if="folder.folder_kind === 'project'" variant="info" size="sm">
            Automática
          </BaseBadge>
          <BaseBadge v-else-if="folder.folder_kind === 'client'" variant="neutral" size="sm">
            Cliente
          </BaseBadge>

          <!-- Directo, a diferencia del panel lateral: acá el árbol se dibuja
               anidado e indentado, así que un total del subárbol pondría 12 en
               el padre y 12 en el hijo a la vez. El ojo ya hace la suma. -->
          <span class="flex-shrink-0 text-xs text-text-subtle">
            {{ folder.document_count }} doc
          </span>

          <div v-if="!isManagedFolderKind(folder) && !folder.is_system_managed" class="touch-reveal flex items-center gap-0.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
            <BaseButton
              variant="ghost"
              icon-only
              size="sm"
              title="Editar carpeta"
              aria-label="Editar carpeta"
              @click="$emit('edit', folder)"
            >
          <BaseActionIcon action="edit" />
            </BaseButton>
            <!-- Archivar entre editar y eliminar: el único sitio donde esas dos
                 ya conviven y hay espacio, a diferencia de la fila del sidebar. -->
            <BaseButton variant="ghost" icon-only size="sm" aria-label="Archivar carpeta" title="Archivar carpeta" data-testid="folder-manager-archive" @click="$emit('archive', folder)">
          <BaseActionIcon action="archive" />
            </BaseButton>
            <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar carpeta" title="Eliminar carpeta" data-testid="folder-manager-delete" @click="$emit('delete', folder)">
          <BaseActionIcon action="delete" />
            </BaseButton>
          </div>
        </div>

        <FolderManagerTree
          v-if="childrenOf(folder.id).length"
          :siblings="childrenOf(folder.id)"
          :parent-id="folder.id"
          :depth="depth + 1"
          :editing-id="editingId"
          :deleting-id="deletingId"
          class="mt-1"
          @edit="$emit('edit', $event)"
          @archive="$emit('archive', $event)"
          @delete="$emit('delete', $event)"
          @reorder="$emit('reorder', $event)"
        />
      </div>
    </template>
  </draggable>
</template>

<script setup>
import { ref, watch } from 'vue';
import draggable from 'vuedraggable';
// Auto-referencia explícita para el render recursivo del árbol.
import FolderManagerTree from '~/components/panel/documents/FolderManagerTree.vue';
import { isManagedFolderKind } from '~/utils/documentStatus';

const props = defineProps({
  siblings: { type: Array, default: () => [] },
  parentId: { type: Number, default: null },
  depth: { type: Number, default: 0 },
  editingId: { type: Number, default: null },
  deletingId: { type: Number, default: null },
});
const emit = defineEmits(['edit', 'archive', 'delete', 'reorder']);

const folderStore = useDocumentFolderStore();
const localSiblings = ref([]);

watch(() => props.siblings, (v) => {
  localSiblings.value = [...v];
}, { immediate: true });

function childrenOf(id) {
  return folderStore.childrenOf(id);
}

function rowClass(folder) {
  if (folder.id === props.editingId) {
    return 'border-primary/20 bg-primary-soft';
  }
  if (folder.id === props.deletingId) {
    return 'border-danger-strong/30 bg-danger-soft';
  }
  return 'border-border-muted hover:border-border-default '
    + 'bg-surface hover:bg-surface-muted';
}

function canMove(event) {
  const folder = event.draggedContext?.element;
  return !isManagedFolderKind(folder) && !folder?.is_system_managed;
}

// vuedraggable aísla cada lista por defecto: el reorden solo afecta este nivel.
function onReorderEnd() {
  emit('reorder', {
    parentId: props.parentId,
    orderedIds: localSiblings.value
      .filter((folder) => !isManagedFolderKind(folder) && !folder.is_system_managed)
      .map((folder) => folder.id),
  });
}
</script>
