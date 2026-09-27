<template>
  <div class="flex min-h-0 flex-1 flex-col" data-testid="doc-markdown-editor">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-3">
        <label :for="textareaId" class="block text-sm font-medium text-text-default">
          {{ label }}
          <span v-if="required" class="text-danger-strong">*</span>
        </label>
        <BaseSegmented
          v-model="view"
          size="sm"
          :options="viewOptions"
          aria-label="Modo del editor"
        />
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span v-if="modelValue" class="text-xs text-text-subtle tabular-nums">
          {{ modelValue.length.toLocaleString() }} caracteres
        </span>
        <slot name="tools" />
      </div>
    </div>

    <!-- v-show, no v-if: al alternar se conservan el historial de deshacer,
         el cursor y el scroll de lo que se está escribiendo. -->
    <textarea
      v-show="view === 'edit'"
      :id="textareaId"
      ref="textareaRef"
      :value="modelValue"
      :placeholder="placeholder"
      class="w-full px-4 py-3 border border-border-default rounded-xl text-sm font-mono leading-relaxed bg-surface text-text-default placeholder:text-text-subtle
             focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none resize-none"
      :class="paneClass"
      @input="emit('update:modelValue', $event.target.value)"
    ></textarea>
    <!-- Ocupa la misma caja que el editor y se monta sólo al pedirla: la vista
         previa en paralelo parseaba el documento entero en cada tecla. -->
    <div
      v-if="view === 'preview'"
      class="w-full overflow-y-auto rounded-xl border border-border-default bg-surface"
      :class="paneClass"
      data-testid="doc-markdown-preview-pane"
    >
      <DocumentMarkdownBody
        v-if="modelValue.trim()"
        :markdown="modelValue"
        :theme="theme"
        class="mx-auto w-full max-w-3xl px-5 py-4"
      />
      <div
        v-else
        class="flex items-center justify-center h-64 text-sm text-text-subtle"
      >
        Escribe markdown para ver la vista previa...
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue';
import DocumentMarkdownBody from '~/components/panel/documents/DocumentMarkdownBody.vue';
import { oneOf } from '~/components/base/propValidators';

/**
 * Markdown content of a document, edited at full width with an
 * Editar / Vista previa switch; the preview takes the editor's own box.
 * Shared by the create and edit pages, which add their tools via #tools.
 */
const props = defineProps({
  modelValue: { type: String, default: '' },
  textareaId: { type: String, required: true },
  label: { type: String, required: true },
  /** Same required marker as BaseFormField, for forms that demand content. */
  required: { type: Boolean, default: false },
  placeholder: { type: String, default: '' },
  theme: { type: String, default: 'friendly', validator: oneOf(['friendly', 'professional']) },
  /** Size of the editor box, shared by the textarea and the preview. */
  paneClass: { type: String, default: 'min-h-[24rem] panel-desktop:h-[calc(100vh-18rem)]' },
});

const emit = defineEmits(['update:modelValue']);

const viewOptions = [
  { value: 'edit', label: 'Editar', testId: 'doc-editor-view-edit' },
  { value: 'preview', label: 'Vista previa', testId: 'doc-editor-view-preview' },
];

const view = ref('edit');
const textareaRef = ref(null);

// Reemplaza la selección (o inserta en el cursor) y deja el cursor justo
// después de lo insertado. Desde la vista previa vuelve primero al editor:
// lo pegado tiene que quedar a la vista.
function insertAtCursor(text) {
  const textarea = textareaRef.value;
  const current = props.modelValue;
  const start = textarea ? textarea.selectionStart : current.length;
  const end = textarea ? textarea.selectionEnd : current.length;
  view.value = 'edit';
  emit('update:modelValue', current.slice(0, start) + text + current.slice(end));
  if (!textarea) return;
  const cursor = start + text.length;
  nextTick(() => {
    textarea.focus();
    textarea.setSelectionRange(cursor, cursor);
  });
}

defineExpose({ insertAtCursor });
</script>
