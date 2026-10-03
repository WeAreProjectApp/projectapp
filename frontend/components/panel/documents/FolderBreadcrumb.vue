<template>
  <nav
    class="flex items-center gap-2 flex-wrap text-sm mb-4"
    aria-label="Ruta de carpetas"
  >
    <button
      type="button"
      class="touch-target px-2 py-1 rounded-lg transition-colors"
      :class="segmentClass(dragOverId === 'root')"
      data-testid="folder-breadcrumb-root"
      data-responsive-touch-target
      @click="$emit('select', rootValue)"
      @dragover="onDragOver($event, 'root')"
      @dragleave="dragOverId = null"
      @drop.prevent="onDrop('root')"
    >
      {{ rootLabel }}
    </button>

    <template v-if="activeId === 'none'">
      <span class="px-1 text-text-subtle select-none">›</span>
      <span class="px-2 py-1 font-medium text-text-default">Sin carpeta</span>
    </template>

    <template v-for="(crumb, idx) in ancestors" :key="crumb.id">
      <span class="px-1 text-text-subtle select-none">›</span>
      <button
        v-if="idx < ancestors.length - 1"
        type="button"
        class="touch-target px-2 py-1 rounded-lg transition-colors max-w-[180px] truncate"
        :class="segmentClass(dragOverId === crumb.id)"
        :data-testid="`folder-breadcrumb-${crumb.id}`"
        data-responsive-touch-target
        @click="$emit('select', crumb.id)"
        @dragover="onDragOver($event, crumb.id)"
        @dragleave="dragOverId = null"
        @drop.prevent="onDrop(crumb.id)"
      >
        {{ crumb.name }}
      </button>
      <span
        v-else
        class="px-2 py-1 font-medium text-text-default max-w-[200px] truncate"
      >
        {{ crumb.name }}
      </span>
      <!-- Navegando el archivo, el tramo archivado se marca: la ruta puede
           mezclar carpetas activas y archivadas tras una restauración por cadena. -->
      <span
        v-if="crumb.is_archived"
        class="inline-flex items-center rounded-full bg-surface-raised px-1.5 py-0.5 text-2xs font-medium text-text-muted"
      >
        Archivado
      </span>
    </template>
  </nav>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  activeId: { type: [String, Number], default: 'all' },
  draggingFolderId: { type: [String, Number], default: null },
  // La raíz cambia con el eje de estado: navegando el archivo el primer tramo
  // es «Archivados», no «Todos».
  rootLabel: { type: String, default: 'Todos' },
  rootValue: { type: [String, Number], default: 'all' },
});
const emit = defineEmits(['select', 'nest']);

const folderStore = useDocumentFolderStore();
const dragOverId = ref(null);

const ancestors = computed(() => {
  if (typeof props.activeId !== 'number') return [];
  return folderStore.ancestorsOf(props.activeId);
});

function segmentClass(isOver) {
  if (isOver) return 'bg-primary-soft text-text-brand ring-1 ring-emerald-400';
  return 'text-text-muted hover:bg-surface-muted hover:text-text-default';
}

// Un destino es válido si hay una carpeta en arrastre y el destino no es ella
// misma ni uno de sus descendientes (evita ciclos).
function isValidTarget(id) {
  if (props.draggingFolderId == null) return false;
  const destId = id === 'root' ? null : id;
  if (destId === props.draggingFolderId) return false;
  if (destId != null
    && folderStore.descendantIdsOf(props.draggingFolderId).has(destId)) {
    return false;
  }
  // Soltar algo activo dentro de una carpeta archivada lo dejaría sin
  // ubicación alcanzable, que es justo el estado que este cambio elimina.
  if (destId != null && folderStore.folderById(destId)?.is_archived) return false;
  return true;
}

function onDragOver(event, id) {
  if (!isValidTarget(id)) return;
  event.preventDefault();
  dragOverId.value = id;
}

function onDrop(id) {
  dragOverId.value = null;
  if (!isValidTarget(id)) return;
  emit('nest', {
    destId: id === 'root' ? null : id,
    draggedFolderId: props.draggingFolderId,
  });
}
</script>
