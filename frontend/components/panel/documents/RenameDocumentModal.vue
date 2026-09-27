<template>
  <Teleport to="body">
    <Transition name="fade-modal">
      <div
        v-if="modelValue && document"
        class="fixed inset-0 z-[9990] flex items-stretch justify-stretch bg-black/40 p-0 backdrop-blur-sm panel-portrait:items-center panel-portrait:justify-center panel-portrait:p-4"
        @click.self="close"
      >
        <div class="flex h-dvh w-full flex-col overflow-hidden bg-surface shadow-overlay panel-portrait:h-auto panel-portrait:max-h-[90dvh] panel-portrait:max-w-sm panel-portrait:rounded-2xl">

          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-border-muted">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center">
                <BaseActionIcon action="rename" class="text-amber-600 dark:text-amber-400" />
              </div>
              <h3 class="text-base font-semibold text-text-default">Renombrar documento</h3>
            </div>
            <BaseButton variant="ghost" icon-only size="md" aria-label="Cerrar" title="Cerrar" @click="close">
              <BaseActionIcon action="close" />
            </BaseButton>
          </div>

          <!-- Body -->
          <form class="flex min-h-0 flex-1 flex-col" @submit.prevent="submit">
            <div class="min-h-0 flex-1 space-y-4 overflow-y-auto p-6" data-modal-body>
              <div>
                <label class="block text-xs text-text-muted mb-1.5">Nuevo nombre</label>
                <input
                  ref="inputRef"
                  v-model="editingTitle"
                  type="text"
                  placeholder="Nombre del documento"
                  class="bg-input-bg w-full px-3 py-2 border border-border-default rounded-lg text-sm text-text-default focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                  :disabled="isSaving"
                  @keyup.esc="close"
                />
              </div>

              <p v-if="errorMsg" class="text-xs text-danger-strong bg-danger-soft px-3 py-2 rounded-lg">
                {{ errorMsg }}
              </p>

            </div>
            <BaseModalActions class="pb-[max(1rem,env(safe-area-inset-bottom))]">
              <BaseButton variant="ghost" @click="close">
                Cancelar
              </BaseButton>
              <BaseButton
                type="submit"
                variant="primary"
                :disabled="!canSubmit"
                :loading="isSaving"
              >
                Guardar cambios
              </BaseButton>
            </BaseModalActions>
          </form>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  document: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue', 'changed']);

const documentStore = useDocumentStore();

const editingTitle = ref('');
const isSaving = ref(false);
const errorMsg = ref('');
const inputRef = ref(null);

const canSubmit = computed(() => editingTitle.value.trim().length > 0);

watch(
  () => [props.modelValue, props.document],
  async ([open, doc]) => {
    if (open && doc) {
      editingTitle.value = doc.title || '';
      errorMsg.value = '';
      await nextTick();
      inputRef.value?.focus();
      inputRef.value?.select();
    }
  },
  { immediate: true },
);

function close() {
  emit('update:modelValue', false);
}

async function submit() {
  if (!canSubmit.value || !props.document) return;
  const newTitle = editingTitle.value.trim();
  if (newTitle === props.document.title) {
    close();
    return;
  }
  isSaving.value = true;
  errorMsg.value = '';
  const result = await documentStore.updateDocument(props.document.id, { title: newTitle });
  isSaving.value = false;
  if (result.success) {
    emit('changed');
    close();
  } else {
    errorMsg.value = 'No se pudo renombrar el documento.';
  }
}
</script>
