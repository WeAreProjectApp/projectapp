<template>
  <BaseModal
    :model-value="modelValue && !!folder"
    kind="confirm"
    @update:model-value="(v) => !v && close()"
  >
    <div v-if="folder" class="px-6 pt-6 pb-2">
      <div class="flex items-start gap-4">
        <div
          class="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
          :class="isEmpty ? 'bg-danger-soft' : 'bg-warning-soft'"
        >
          <ExclamationCircleIcon
            class="w-5 h-5"
            :class="isEmpty ? 'text-danger-strong' : 'text-warning-strong'"
          />
        </div>
        <div class="flex-1 min-w-0">
          <template v-if="isEmpty">
            <h3 class="text-lg font-bold text-text-default break-words">Eliminar "{{ folder.name }}"</h3>
            <p class="mt-1 text-sm text-text-muted leading-relaxed">
              Esta acción no se puede deshacer.
            </p>
          </template>
          <template v-else>
            <h3 class="text-lg font-bold text-text-default">Esta carpeta no se puede eliminar</h3>
            <p class="mt-1 text-sm text-text-muted leading-relaxed break-words">
              "{{ folder.name }}" todavía tiene contenido.
            </p>
          </template>

          <!-- Inventario: qué contiene la carpeta hoy -->
          <div
            class="mt-4 rounded-lg border border-border-muted bg-surface-muted px-3 py-2.5"
            data-testid="delete-folder-inventory"
          >
            <p class="text-xs font-semibold uppercase tracking-wider text-text-muted">Contenido</p>
            <p v-if="isEmpty" class="mt-1.5 text-sm text-text-default">
              Esta carpeta está vacía: no se eliminará ningún documento ni subcarpeta.
            </p>
            <template v-else>
              <ul class="mt-1.5 space-y-1" role="list">
                <li
                  v-for="child in childFolders"
                  :key="child.id"
                  class="flex items-center gap-2 text-sm text-text-default"
                >
                  <svg class="w-3.5 h-3.5 text-amber-500 dark:text-amber-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
                  </svg>
                  <span class="truncate">{{ child.name }}</span>
                </li>
                <li v-if="documentCount" class="flex items-center gap-2 text-sm text-text-default">
                  <svg class="w-3.5 h-3.5 text-text-subtle flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span>{{ documentCount }} {{ documentCount === 1 ? 'documento' : 'documentos' }}</span>
                </li>
                <!-- Se lista aparte porque no se ve en la carpeta: sin esta
                     línea, una carpeta «vacía» que igual no se puede borrar no
                     tendría explicación. -->
                <li
                  v-if="archivedCount"
                  class="flex items-center gap-2 text-sm text-text-muted"
                  data-testid="delete-folder-archived-line"
                >
                  <svg class="w-3.5 h-3.5 text-text-subtle flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                  </svg>
                  <span>{{ archivedCount }} {{ archivedCount === 1 ? 'elemento archivado' : 'elementos archivados' }}</span>
                </li>
              </ul>
              <p class="mt-2 text-xs text-text-muted">
                Archívala: saldrá de la vista con todo su contenido y podrás restaurarla cuando quieras.
              </p>
            </template>
          </div>

          <!--
            La salida va ANTES del campo de confirmación: es una salida, no un
            paso adicional, así que tiene que verse antes de escribir la palabra.
          -->
          <div
            v-if="isEmpty"
            class="mt-3 rounded-lg border border-border-muted bg-surface-muted px-3 py-2"
            data-testid="delete-folder-archive-hint"
          >
            <p class="text-xs text-text-muted leading-relaxed">
              ¿No quieres perderla? Archivarla la saca de la vista y de los contadores, pero la conserva.
            </p>
          </div>

          <!-- Confirmación escrita — mismo contrato que ConfirmModal: exacto y sensible a mayúsculas -->
          <div v-if="isEmpty" class="mt-4">
            <label class="block text-xs text-text-muted mb-1.5" :for="typeInputId">
              Escribe <span class="font-mono font-bold text-text-default">{{ CONFIRM_WORD }}</span> para confirmar
            </label>
            <input
              :id="typeInputId"
              ref="typeInputRef"
              v-model="typedValue"
              type="text"
              autocomplete="off"
              spellcheck="false"
              data-testid="delete-folder-type-input"
              :placeholder="CONFIRM_WORD"
              class="w-full px-3 py-2 text-sm font-mono text-input-text bg-input-bg border border-input-border placeholder:text-text-subtle rounded-lg focus:outline-none focus:ring-2 focus:ring-danger-strong/40 focus:border-danger-strong/60"
              @keyup.enter="confirmDelete"
            />
          </div>

          <p
            v-if="errorMsg"
            class="mt-3 text-xs text-danger-strong bg-danger-soft px-3 py-2 rounded-lg"
            data-testid="delete-folder-error"
          >
            {{ errorMsg }}
          </p>
        </div>
      </div>
    </div>

    <template #footer>
      <BaseModalActions>
        <BaseButton variant="ghost" size="md" :disabled="isBusy" @click="close">Cancelar</BaseButton>
        <!--
          Con contenido, archivar es la acción principal: un botón destructivo
          permanentemente deshabilitado ES el callejón sin salida, así que ahí
          directamente no se renderiza.
        -->
        <BaseButton
          :variant="isEmpty ? 'secondary' : 'primary'"
          size="md"
          data-testid="delete-folder-archive"
          :disabled="isDeleting"
          :loading="isArchiving"
          @click="confirmArchive"
        >
          {{ isEmpty ? 'Archivar en su lugar' : 'Archivar carpeta' }}
        </BaseButton>
        <BaseButton
          v-if="isEmpty"
          variant="danger"
          size="md"
          data-testid="delete-folder-confirm"
          :disabled="!canConfirm"
          :loading="isDeleting"
          @click="confirmDelete"
        >
          Eliminar carpeta
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue';
import { ExclamationCircleIcon } from '@heroicons/vue/24/outline';

const CONFIRM_WORD = 'DELETE';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  folder: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue', 'deleted', 'archived']);

const folderStore = useDocumentFolderStore();

const typedValue = ref('');
const errorMsg = ref('');
const isDeleting = ref(false);
const isArchiving = ref(false);
const typeInputRef = ref(null);
const typeInputId = useId();

const childFolders = computed(() => (props.folder ? folderStore.childrenOf(props.folder.id) : []));

// El contador del servidor manda cuando el store aún no trajo las subcarpetas.
const childCount = computed(() => Math.max(childFolders.value.length, props.folder?.children_count || 0));
const documentCount = computed(() => props.folder?.document_count || 0);
const archivedCount = computed(() => folderStore.archivedContentCount(props.folder));

// El 409 del backend cuenta TODO el contenido, archivado incluido. Mirar sólo
// lo activo ofrecía el borrado de una carpeta que después no se podía borrar.
const isEmpty = computed(
  () => documentCount.value === 0 && childCount.value === 0 && archivedCount.value === 0,
);

const isBusy = computed(() => isDeleting.value || isArchiving.value);
const canConfirm = computed(() => isEmpty.value && typedValue.value === CONFIRM_WORD && !isBusy.value);

watch(() => props.modelValue, (open) => {
  typedValue.value = '';
  errorMsg.value = '';
  if (open && props.folder && isEmpty.value) {
    nextTick(() => typeInputRef.value?.focus());
  }
});

function close() {
  emit('update:modelValue', false);
}

async function confirmDelete() {
  if (!canConfirm.value || !props.folder) return;
  isDeleting.value = true;
  errorMsg.value = '';
  const result = await folderStore.deleteFolder(props.folder.id);
  isDeleting.value = false;
  if (result.success) {
    emit('deleted', props.folder);
    close();
    return;
  }
  // El backend responde 409 con copy en español; si no llega, texto genérico.
  errorMsg.value = result.errors?.detail || 'No se pudo eliminar la carpeta.';
}

async function confirmArchive() {
  if (isBusy.value || !props.folder) return;
  isArchiving.value = true;
  errorMsg.value = '';
  const result = await folderStore.archiveFolder(props.folder.id);
  isArchiving.value = false;
  if (result.success) {
    emit('archived', {
      folder: props.folder,
      folders: result.archivedFolders,
      documents: result.archivedDocuments,
    });
    close();
    return;
  }
  errorMsg.value = result.errors?.detail || 'No se pudo archivar la carpeta.';
}
</script>
