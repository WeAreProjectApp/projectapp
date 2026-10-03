<template>
  <Teleport to="body">
    <Transition name="fade-modal">
      <div
        v-if="modelValue && document"
        class="fixed inset-0 z-[9990] flex items-stretch justify-stretch bg-black/40 p-0 backdrop-blur-sm panel-portrait:items-center panel-portrait:justify-center panel-portrait:p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="move-document-title"
        @click.self="close"
      >
        <div class="flex h-dvh w-full flex-col overflow-hidden bg-surface shadow-overlay panel-portrait:h-auto panel-portrait:max-h-[90dvh] panel-portrait:rounded-2xl panel-portrait:max-w-sm">

          <div class="min-h-0 flex-1 overflow-y-auto" data-modal-body>
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-border-muted">
              <div class="flex items-center gap-2.5">
                <div class="w-8 h-8 rounded-lg bg-info-soft flex items-center justify-center">
                  <BaseActionIcon action="move" class="text-info-strong" />
                </div>
                <div class="min-w-0">
                  <h3 id="move-document-title" class="text-base font-semibold text-text-default">Mover documento</h3>
                  <p class="text-xs text-text-muted truncate max-w-[200px]">{{ document.title }}</p>
                </div>
              </div>
              <BaseButton variant="ghost" icon-only size="md" aria-label="Cerrar" title="Cerrar" @click="close">
                <BaseActionIcon action="close" />
              </BaseButton>
            </div>

            <!-- Folder options -->
            <div class="p-4 space-y-1.5 max-h-72 overflow-y-auto">
              <!-- No folder option -->
              <!-- design-tokens: allow-raw-button — selectable list row, not an action -->
              <button
                type="button"
                :disabled="isMoving"
                class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all text-left disabled:opacity-50"
                :class="document.folder === null
                ? 'border-info-strong/30 bg-info-soft'
                : 'border-border-muted hover:border-border-default hover:bg-surface-muted'"
                @click="moveToFolder(null)"
              >
                <div class="w-7 h-7 rounded-lg bg-surface-raised flex items-center justify-center flex-shrink-0">
                  <BaseActionIcon action="unlink" class="text-text-subtle" />
                </div>
                <span class="flex-1 text-sm font-medium text-text-default">Sin carpeta</span>
                <!-- panel-action-icons: allow-status-glyph — marks the currently selected destination. -->
                <CheckIcon
                  v-if="document.folder === null"
                  class="w-4 h-4 text-info-strong flex-shrink-0"
                  aria-hidden="true"
                />
              </button>

              <!-- Folder entries -->
              <!-- design-tokens: allow-raw-button — selectable list row, not an action -->
              <button
                v-for="folder in orderedFolders"
                :key="folder.id"
                :data-testid="`move-folder-option-${folder.id}`"
                type="button"
                :disabled="isMoving"
                class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all text-left disabled:opacity-50"
                :class="document.folder === folder.id
                ? 'border-info-strong/30 bg-info-soft'
                : 'border-border-muted hover:border-border-default hover:bg-surface-muted'"
                :style="{ paddingLeft: `${12 + folder.depth * 18}px` }"
                @click="moveToFolder(folder.id)"
              >
                <div class="w-7 h-7 rounded-lg bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center flex-shrink-0">
                  <BaseActionIcon action="folders" class="text-amber-500 dark:text-amber-400" />
                </div>
                <span class="flex-1 min-w-0 whitespace-normal [overflow-wrap:anywhere] text-sm font-medium text-text-default">{{ folder.name }}</span>
                <!-- Directo: el selector lista muchos niveles a la vez e indentados
                   (igual que el gestor), y para elegir destino «cuánto hay acá»
                   significa esta carpeta, no su rama entera. -->
                <span class="flex-shrink-0 text-xs text-text-subtle">{{ folder.document_count }}</span>
                <!-- panel-action-icons: allow-status-glyph — marks the currently selected destination. -->
                <CheckIcon
                  v-if="document.folder === folder.id"
                  class="w-4 h-4 text-info-strong flex-shrink-0"
                  aria-hidden="true"
                />
              </button>

              <div v-if="!folderStore.activeFolders.length" class="text-center py-4">
                <p class="text-sm text-text-muted">No hay carpetas creadas.</p>
              </div>
            </div>

            <!--
            La carpeta destino es de otro cliente. No se decide por el
            operador: un documento PUEDE pertenecer a un cliente distinto al de
            su carpeta (una cuenta de cobro emitida no puede cambiar de dueño y
            aun así tiene que poder guardarse donde corresponda), así que
            conservar es el default y adoptar es una respuesta explícita.
          -->
            <div
              v-if="pendingMove"
              class="px-4 pb-3 space-y-2"
              data-testid="move-folder-client-choice"
            >
              <p class="text-xs text-text-muted">
                "{{ pendingMove.folderName }}" es de
                <strong>{{ pendingMove.folderClientName }}</strong>, y este
                documento es de otro cliente. ¿Qué hacemos?
              </p>
              <div class="flex flex-wrap gap-2">
                <BaseButton
                  variant="primary"
                  size="sm"
                  :loading="isMoving"
                  data-testid="move-folder-keep-client"
                  @click="commitPendingMove(false)"
                >
                  Conservar su cliente
                </BaseButton>
                <BaseButton
                  variant="secondary"
                  size="sm"
                  :loading="isMoving"
                  data-testid="move-folder-adopt-client"
                  @click="commitPendingMove(true)"
                >
                  Adoptar el de la carpeta
                </BaseButton>
              </div>
            </div>

            <!-- Error -->
            <div v-if="errorMsg" class="px-4 pb-2">
              <p class="text-xs text-danger-strong bg-danger-soft px-3 py-2 rounded-lg">{{ errorMsg }}</p>
            </div>

            <!-- Footer -->
          </div>
          <BaseModalActions class="pb-[max(1rem,env(safe-area-inset-bottom))]">
            <BaseButton variant="ghost" @click="close">
              Cancelar
            </BaseButton>
          </BaseModalActions>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref } from 'vue';
import { CheckIcon } from '@heroicons/vue/24/outline';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  document: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue', 'changed']);

const documentStore = useDocumentStore();
const folderStore = useDocumentFolderStore();
const isMoving = ref(false);
const errorMsg = ref('');
// Movimiento a la espera de que el operador decida qué pasa con el cliente.
const pendingMove = ref(null);

// Carpetas aplanadas en orden depth-first, con su nivel de profundidad.
const orderedFolders = computed(() => {
  const result = [];
  const walk = (parentId, depth) => {
    folderStore.childrenOf(parentId).forEach((f) => {
      result.push({ ...f, depth });
      walk(f.id, depth + 1);
    });
  };
  walk(null, 0);
  return result;
});

function close() {
  emit('update:modelValue', false);
}

async function moveToFolder(folderId) {
  if (!props.document) return;
  if (props.document.folder === folderId) {
    close();
    return;
  }
  const target = folderId == null ? null : folderStore.folderById?.(folderId)
    ?? orderedFolders.value.find((folder) => folder.id === folderId);
  const docClient = props.document.client ?? null;
  // Sólo hay algo que preguntar cuando adoptar PISARÍA un cliente ya elegido.
  // Sin cliente propio, heredar el de la carpeta no le quita nada a nadie y lo
  // resuelve el backend por su cuenta.
  if (!props.document.is_contract_mirror && target?.client && docClient && docClient !== target.client) {
    pendingMove.value = {
      folderId,
      folderName: target.name,
      folderClientName: target.client_display_name || 'otro cliente',
    };
    return;
  }
  await sendMove(folderId, false);
}

function commitPendingMove(adopt) {
  const { folderId } = pendingMove.value;
  return sendMove(folderId, adopt);
}

async function sendMove(folderId, adopt) {
  isMoving.value = true;
  errorMsg.value = '';
  const payload = { folder_id: folderId };
  if (adopt) payload.adopt_folder_client = true;
  const result = await documentStore.updateDocument(props.document.id, payload);
  isMoving.value = false;
  pendingMove.value = null;
  if (result.success) {
    emit('changed');
    close();
  } else {
    errorMsg.value = 'No se pudo mover el documento.';
  }
}
</script>
