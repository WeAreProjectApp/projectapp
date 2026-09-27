<template>
  <Teleport to="body">
    <Transition name="fade-modal">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-[9990] flex items-stretch justify-stretch bg-black/50 p-0 backdrop-blur-sm panel-portrait:items-center panel-portrait:justify-center panel-portrait:p-4"
        @click.self="close"
      >
        <div class="flex h-dvh w-full flex-col overflow-hidden bg-surface shadow-overlay panel-portrait:h-auto panel-portrait:max-h-[90dvh] panel-portrait:rounded-2xl panel-portrait:max-w-xl">

          <div class="min-h-0 flex-1 overflow-y-auto" data-modal-body>
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-5 border-b border-border-muted flex-shrink-0">
              <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-xl bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center">
                  <svg class="w-5 h-5 text-amber-500 dark:text-amber-400" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
                  </svg>
                </div>
                <div>
                  <h3 class="text-base font-semibold text-text-default">Gestionar carpetas</h3>
                  <p class="text-xs text-text-muted mt-0.5">Las raíces de proyecto son automáticas; sus subcarpetas y las propias se gestionan aquí</p>
                </div>
              </div>
              <BaseButton variant="ghost" icon-only size="md" aria-label="Cerrar" title="Cerrar" @click="close">
                <BaseActionIcon action="close" />
              </BaseButton>
            </div>

            <!-- New folder form -->
            <div class="px-6 pt-5 pb-4 flex-shrink-0 space-y-3">
              <form class="space-y-3" novalidate @submit.prevent="handleCreate">
                <BaseFormField label="Nombre" required :error="newNameError">
                  <BaseInput
                    v-model="newName"
                    type="text"
                    placeholder="Nombre de la nueva carpeta"
                    :error="!!newNameError"
                    data-testid="folder-manager-new-name"
                    @update:model-value="newNameError = ''"
                  />
                </BaseFormField>
                <BaseFormField label="Dentro de">
                  <BaseSelect v-model="newParent" data-testid="folder-manager-parent">
                    <option value="">Ninguna (carpeta raíz)</option>
                    <option v-for="opt in createOptions" :key="opt.id" :value="String(opt.id)">
                      {{ opt.label }}
                    </option>
                  </BaseSelect>
                </BaseFormField>
                <div class="flex justify-end">
                  <BaseButton
                    type="submit"
                    variant="primary"
                    :loading="folderStore.isUpdating"
                  >
                    Crear
                  </BaseButton>
                </div>
              </form>
            </div>

            <div v-if="folderStore.activeFolders.length" class="px-6 pb-2 flex-shrink-0">
              <div class="flex items-center gap-2">
                <span class="text-[11px] font-semibold text-text-subtle uppercase tracking-wider">
                  {{ folderStore.activeFolders.length }} carpeta{{ folderStore.activeFolders.length !== 1 ? 's' : '' }}
                </span>
                <div class="flex-1 h-px bg-surface-raised"></div>
                <span class="text-2xs text-text-subtle flex items-center gap-1">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4" />
                  </svg>
                  Arrastra para reordenar (por nivel)
                </span>
              </div>
            </div>

            <!-- Folder tree -->
            <div class="flex-1 overflow-y-auto px-6 pb-2">
              <div v-if="!folderStore.activeFolders.length" class="flex flex-col items-center justify-center py-12 text-center">
                <div class="w-14 h-14 rounded-2xl bg-surface-raised flex items-center justify-center mb-3">
                  <svg class="w-7 h-7 text-text-subtle" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
                  </svg>
                </div>
                <p class="text-sm font-medium text-text-muted">Sin carpetas todavía</p>
                <p class="text-xs text-text-subtle mt-1">Usa el campo de arriba para crear la primera.</p>
              </div>

              <FolderManagerTree
                v-else
                :siblings="folderStore.rootFolders"
                :parent-id="null"
                :depth="0"
                :editing-id="editingFolder?.id ?? null"
                :deleting-id="deletingFolder?.id ?? null"
                class="py-1"
                @edit="startEdit"
                @archive="askArchive"
                @delete="askDelete"
                @reorder="handleReorder"
              />
            </div>

            <div v-if="errorMsg" class="px-6 pb-2 flex-shrink-0">
              <p class="text-xs text-danger-strong bg-danger-soft px-3 py-2 rounded-lg">{{ errorMsg }}</p>
            </div>


            <!-- Footer -->
          </div>
          <BaseModalActions class="pb-[max(1rem,env(safe-area-inset-bottom))]">
            <BaseButton variant="ghost" @click="close">
              Cerrar
            </BaseButton>
          </BaseModalActions>

        </div>
      </div>
    </Transition>

    <!--
      Un solo contrato de borrado de carpeta en toda la app: este modal delega
      en DeleteFolderModal en vez de repetir un panel inline sin reja de
      confirmación. Anidado sin conflicto: este Teleport va a z-[9990] y
      BaseModal a z-[9999], y el focus trap vive sólo en BaseModal.
    -->
    <DeleteFolderModal
      v-model="showDeleteFolder"
      :folder="deletingFolder"
      @deleted="onFolderDeleted"
      @archived="onFolderArchived"
    />

    <!--
      Y el mismo criterio para editar: un solo formulario de carpeta en toda la
      app. Antes vivía acá como panel inline, que era además el ÚNICO camino
      para editar algo ya existente — dentro del modal de crear.
    -->
    <FolderFormModal
      v-model="showFolderForm"
      :folder="editingFolder"
      @saved="onFolderSaved"
      @change-client="$emit('change-client', $event)"
    />
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import FolderManagerTree from '~/components/panel/documents/FolderManagerTree.vue';
import DeleteFolderModal from '~/components/panel/documents/DeleteFolderModal.vue';
import FolderFormModal from '~/components/panel/documents/FolderFormModal.vue';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initialParent: { type: Number, default: null },
});
const emit = defineEmits([
  'update:modelValue', 'changed', 'archived', 'change-client',
]);

const folderStore = useDocumentFolderStore();
const newName = ref('');
const newParent = ref('');
const editingFolder = ref(null);
const showFolderForm = ref(false);
const deletingFolder = ref(null);
const showDeleteFolder = ref(false);
const errorMsg = ref('');
const newNameError = ref('');

watch(() => props.modelValue, async (open) => {
  if (open) {
    errorMsg.value = '';
    newNameError.value = '';
    deletingFolder.value = null;
    showDeleteFolder.value = false;
    editingFolder.value = null;
    showFolderForm.value = false;
    newName.value = '';
    newParent.value = props.initialParent == null ? '' : String(props.initialParent);
    await folderStore.fetchFolders();
  }
});

// Lista plana e indentada de carpetas para los <select> de carpeta padre.
function buildFolderOptions(excludeId) {
  const exclude = new Set();
  if (excludeId != null) {
    exclude.add(excludeId);
    folderStore.descendantIdsOf(excludeId).forEach((id) => exclude.add(id));
  }
  const options = [];
  const walk = (parentId, depth) => {
    folderStore.childrenOf(parentId)
      .filter((f) => !exclude.has(f.id))
      .forEach((f) => {
        options.push({ id: f.id, label: `${'   '.repeat(depth)}${f.name}` });
        walk(f.id, depth + 1);
      });
  };
  walk(null, 0);
  return options;
}

const createOptions = computed(() => buildFolderOptions(null));

function close() {
  emit('update:modelValue', false);
}

async function handleCreate() {
  const name = newName.value.trim();
  if (!name) {
    newNameError.value = 'Escribe el nombre de la carpeta.';
    return;
  }
  errorMsg.value = '';
  // Crear dentro de una carpeta con dueño hereda su asociación: es el mismo
  // default que propone el formulario completo, no una atadura.
  const parentId = newParent.value === '' ? null : Number(newParent.value);
  const parent = parentId == null ? null : folderStore.folderById(parentId);
  const result = await folderStore.createFolder({
    name,
    parent: parentId,
    client: parent?.client ?? null,
    project: parent?.project ?? null,
  });
  if (result.success) {
    newName.value = '';
    newParent.value = props.initialParent == null ? '' : String(props.initialParent);
    emit('changed');
  } else {
    newNameError.value = Array.isArray(result.errors?.name)
      ? result.errors.name.join(' ')
      : (result.errors?.name || '');
    errorMsg.value = newNameError.value
      ? ''
      : (formatErr(result.errors) || 'No se pudo crear la carpeta.');
  }
}

function startEdit(folder) {
  editingFolder.value = folder;
  deletingFolder.value = null;
  showFolderForm.value = true;
}

async function onFolderSaved() {
  editingFolder.value = null;
  await folderStore.fetchFolders();
  emit('changed');
}

function askDelete(folder) {
  deletingFolder.value = folder;
  editingFolder.value = null;
  showDeleteFolder.value = true;
}

// Archivar desde el árbol abre el mismo modal: con contenido presenta archivar
// como la acción disponible, así que no hace falta una confirmación aparte.
function askArchive(folder) {
  askDelete(folder);
}

async function onFolderDeleted() {
  deletingFolder.value = null;
  await folderStore.fetchFolders();
  emit('changed');
}

async function onFolderArchived(payload) {
  deletingFolder.value = null;
  await folderStore.fetchFolders();
  emit('archived', payload);
  emit('changed');
}

async function handleReorder({ orderedIds }) {
  const result = await folderStore.reorderFolders(orderedIds);
  if (!result.success) {
    errorMsg.value = 'Error al reordenar. Vuelve a intentarlo.';
  }
  await folderStore.fetchFolders();
}

function formatErr(errors) {
  if (!errors) return '';
  if (typeof errors === 'string') return errors;
  return Object.values(errors).flat().join(' · ');
}
</script>
