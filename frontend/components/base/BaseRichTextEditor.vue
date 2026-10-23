<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, useAttrs, watch } from 'vue';
import { Editor, EditorContent } from '@tiptap/vue-3';
import { DOMParser as SchemaParser } from '@tiptap/pm/model';
import { editorialExtensions } from '~/utils/editorialExtensions';
import { escapeHtml, htmlToSource, sourceToHtml } from '~/utils/editorialFormat';

defineOptions({ inheritAttrs: false });
const props = defineProps({
  modelValue: { type: String, default: '' },
  profile: { type: String, default: 'document' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  error: { type: Boolean, default: false },
  rows: { type: [Number, String], default: 4 },
  label: { type: String, default: '' },
  initialMode: { type: String, default: 'visual' },
  format: { type: String, default: 'markdown_html_v1' },
});
const emit = defineEmits(['update:modelValue', 'update:format', 'validity-change']);
const attrs = useAttrs();
const containerAttrs = computed(() => Object.fromEntries(Object.entries(attrs).filter(([key]) => key !== 'id' && key !== 'aria-label')));
const { t } = useI18n();
const field = inject('editorialField', null);
const editor = shallowRef(null);
const mode = ref(props.initialMode);
const draft = ref(props.modelValue);
const effectiveFormat = ref(props.format);
const problem = ref('');
const invalid = computed(() => Boolean(props.error || problem.value || field?.error.value));
const describedBy = computed(() => field?.error.value ? field.errorId : attrs['aria-describedby']);
const contentLabel = computed(() => props.label || attrs['aria-label'] || field?.label.value || props.placeholder || t('richText.content'));
const visualAttributes = computed(() => ({
  ...(attrs.id ? { id: attrs.id } : {}), role: 'textbox', 'aria-multiline': 'true',
  'aria-label': contentLabel.value, 'data-testid': 'rich-text-visual-input',
  'data-editorial-active': mode.value === 'visual' ? 'true' : 'false',
  'aria-invalid': invalid.value ? 'true' : 'false',
  'aria-describedby': describedBy.value || '',
}));
const sourceInput = ref(null);
const linkOpen = ref(false);
const linkValue = ref('');
const revision = ref(0);
let syncing = false;
let history = [{ source: props.modelValue, format: props.format }];
let historyIndex = 0;
const modeOptions = computed(() => [
  { value: 'visual', label: t('richText.visual') },
  { value: 'source', label: t('richText.source') },
]);
const basicTools = computed(() => [
  ['bold', 'B', 'toggleBold'], ['italic', 'I', 'toggleItalic'],
  ...props.profile === 'whatsapp' ? [] : [['underline', 'U', 'toggleUnderline']],
  ['strike', 'S', 'toggleStrike'], ['bulletList', '•', 'toggleBulletList'],
  ['orderedList', '1.', 'toggleOrderedList'], ['blockquote', '❝', 'toggleBlockquote'], ['code', '<>', 'toggleCode'],
]);
const isActive = (name, attrs) => { void revision.value; return editor.value?.isActive(name, attrs) || false; };

function publish(value, record = true, format = props.profile === 'whatsapp' ? 'whatsapp_v1' : 'markdown_html_v1') {
  if (value === draft.value && value === props.modelValue) return;
  draft.value = value;
  effectiveFormat.value = format;
  emit('update:format', format);
  if (record && (value !== history[historyIndex].source || format !== history[historyIndex].format)) {
    history = history.slice(0, historyIndex + 1).concat({ source: value, format });
    while (history.length > 50 || history.reduce((total, entry) => total + entry.source.length, 0) > 2_000_000 && history.length > 1) history.shift();
    historyIndex = history.length - 1;
  }
  emit('update:modelValue', value);
}

function report(error) {
  problem.value = error ? t('richText.invalidSource') : '';
  emit('validity-change', !error);
}

function importSource(value) {
  const html = effectiveFormat.value === 'plain' ? `<p>${escapeHtml(value).replace(/\n/g, '<br>')}</p>` : sourceToHtml(value, props.profile);
  const el = document.createElement('div'); el.innerHTML = html;
  const parsed = SchemaParser.fromSchema(editor.value.schema).parse(el);
  // The serializer must represent every node the schema accepted before we
  // replace the visual draft. Unsupported source stays available for repair.
  const source = htmlToSource(html, props.profile);
  const check = document.createElement('div'); check.innerHTML = sourceToHtml(source, props.profile);
  const restored = SchemaParser.fromSchema(editor.value.schema).parse(check);
  if (!parsed.eq(restored)) throw new Error('lossy-source-conversion');
  syncing = true;
  editor.value.commands.setContent(parsed.toJSON(), { emitUpdate: false });
  syncing = false;
}

function changeMode(value) {
  if (!editor.value || value === mode.value) return;
  if (value === 'visual') {
    try { importSource(draft.value); report(null); } catch (error) { report(error); return; }
  }
  mode.value = value;
}

function sourceChanged(event) {
  const value = event.target.value;
  publish(value);
  try { sourceToHtml(value, props.profile); report(null); } catch (error) { report(error); }
}

function run(command, argument) {
  if (props.disabled) return;
  editor.value?.chain().focus()[command](argument).run();
  revision.value++;
}

function restoreHistory(direction) {
  if (props.disabled) return;
  const index = historyIndex + direction;
  if (index < 0 || index >= history.length) return;
  historyIndex = index;
  publish(history[index].source, false, history[index].format);
  try { importSource(draft.value); report(null); } catch (error) { report(error); mode.value = 'source'; }
}

function historyKey(event) {
  if (!(event.ctrlKey || event.metaKey) || !['z', 'y'].includes(event.key.toLowerCase())) return;
  event.preventDefault();
  restoreHistory(event.key.toLowerCase() === 'y' || event.shiftKey ? 1 : -1);
}

function saveLink() {
  if (props.disabled) return;
  try {
    sourceToHtml(`<p><a href="${linkValue.value.replace(/&/g, '&amp;').replace(/"/g, '&quot;')}">link</a></p>`);
    run('setLink', { href: linkValue.value });
    linkOpen.value = false;
  } catch (error) { report(error); }
}

function insertAtCursor(value) {
  if (mode.value === 'visual' && editor.value) {
    try { editor.value.chain().focus().insertContent(sourceToHtml(value, props.profile)).run(); } catch (error) { report(error); }
  } else {
    const input = sourceInput.value;
    const start = input?.selectionStart ?? draft.value.length;
    const end = input?.selectionEnd ?? start;
    publish(draft.value.slice(0, start) + value + draft.value.slice(end));
    nextTick(() => { input?.focus(); input?.setSelectionRange(start + value.length, start + value.length); });
  }
}

onMounted(() => {
  editor.value = new Editor({
    extensions: editorialExtensions(props.profile, props.placeholder),
    editable: !props.disabled,
    editorProps: {
      attributes: visualAttributes.value,
      handlePaste(view, event) {
        const html = event.clipboardData?.getData('text/html');
        if (!html) return false;
        event.preventDefault();
        // Pasted markup is reduced to the declared vocabulary; source editing
        // instead rejects unsupported input and keeps the complete draft.
        const clean = sourceToHtml(html, props.profile, { strict: false, inputHtml: true });
        try { editor.value.commands.insertContent(clean); } catch (error) { report(error); }
        return true;
      },
    },
    onSelectionUpdate: () => { revision.value++; },
    onUpdate: ({ editor: instance }) => {
      if (syncing) return;
      try {
        const source = htmlToSource(instance.getHTML(), props.profile);
        const el = document.createElement('div'); el.innerHTML = sourceToHtml(source, props.profile);
        const restored = SchemaParser.fromSchema(instance.schema).parse(el);
        if (!instance.state.doc.eq(restored)) throw new Error('lossy-visual-conversion');
        publish(source); report(null);
      } catch (error) {
        publish(instance.getHTML());
        report(error);
        mode.value = 'source';
      }
      revision.value++;
    },
  });
  try { importSource(draft.value); } catch (error) { report(error); mode.value = 'source'; }
});

watch(() => props.modelValue, (value) => {
  if (value === draft.value) return;
  draft.value = value;
  effectiveFormat.value = props.format;
  history = [{ source: value, format: props.format }]; historyIndex = 0;
  if (editor.value && mode.value === 'visual') {
    try { importSource(value); report(null); } catch (error) { report(error); mode.value = 'source'; }
  }
});
watch(visualAttributes, (attributes) => editor.value?.setOptions({ editorProps: { attributes } }));
watch(() => props.disabled, (value) => editor.value?.setEditable(!value));
watch(() => props.format, (value) => { effectiveFormat.value = value; });
onBeforeUnmount(() => editor.value?.destroy());
defineExpose({ insertAtCursor, focus: () => mode.value === 'visual' ? editor.value?.commands.focus() : sourceInput.value?.focus() });
</script>

<template>
  <div v-bind="containerAttrs" class="editorial-editor min-w-0 rounded-xl border border-border-default bg-input-bg text-input-text" :class="{ 'border-danger-strong': invalid }" @keydown="historyKey">
    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-border-default p-2">
      <BaseSegmented :model-value="mode" :options="modeOptions" size="sm" :aria-label="t('richText.mode')" @update:model-value="changeMode" />
      <div class="flex gap-1">
        <button type="button" class="editor-tool" :aria-label="t('richText.undo')" :title="disabled ? t('richText.readOnly') : t('richText.noUndo')" :disabled="disabled || historyIndex === 0" @click="restoreHistory(-1)">↶</button>
        <button type="button" class="editor-tool" :aria-label="t('richText.redo')" :title="disabled ? t('richText.readOnly') : t('richText.noRedo')" :disabled="disabled || historyIndex >= history.length - 1" @click="restoreHistory(1)">↷</button>
      </div>
    </div>
    <div v-show="mode === 'visual'" class="flex flex-wrap items-center gap-1 border-b border-border-default p-2" role="toolbar" :aria-label="t('richText.formatting')">
      <button v-for="[name, icon, command] in basicTools" :key="name" type="button" class="editor-tool" :aria-label="t(`richText.${name}`)" :title="t(`richText.${name}`)" :aria-pressed="isActive(name)" :disabled="disabled || !editor" @click="run(command)">{{ icon }}</button>
      <button v-for="[name, command] in [['indent','sinkListItem'],['outdent','liftListItem']]" :key="name" type="button" class="editor-tool" :aria-label="t(`richText.${name}`)" :title="disabled ? t('richText.readOnly') : t('richText.listSelection')" :disabled="disabled || !editor?.can()[command]('listItem')" @click="run(command, 'listItem')">{{ name === 'indent' ? '⇥' : '⇤' }}</button>
      <template v-if="profile !== 'whatsapp'">
        <select class="rounded-lg border border-border-default bg-surface px-2 py-1 text-sm" :aria-label="t('richText.heading')" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @change="$event.target.value === 'p' ? run('setParagraph') : run('toggleHeading', { level: Number($event.target.value) })">
          <option value="p">{{ t('richText.paragraph') }}</option><option v-for="level in [1,2,3,4,5,6]" :key="level" :value="level">H{{ level }}</option>
        </select>
        <label class="editor-tool cursor-pointer" :title="t('richText.color')"><span aria-hidden="true">A</span><input type="color" class="h-5 w-5" :aria-label="t('richText.color')" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @input="run('setColor', $event.target.value)" /></label>
        <label class="editor-tool cursor-pointer" :title="t('richText.highlight')"><span aria-hidden="true">▰</span><input type="color" value="#fff59d" class="h-5 w-5" :aria-label="t('richText.highlight')" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @input="run('setHighlight', { color: $event.target.value })" /></label>
        <button v-for="alignment in ['left','center','right','justify']" :key="alignment" type="button" class="editor-tool" :aria-label="t(`richText.${alignment}`)" :aria-pressed="isActive({ textAlign: alignment })" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @click="run('setTextAlign', alignment)">{{ { left: '≡←', center: '≡', right: '→≡', justify: '☰' }[alignment] }}</button>
        <button type="button" class="editor-tool" :aria-label="t('richText.link')" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @click="linkOpen = !linkOpen">↗</button>
        <button type="button" class="editor-tool" :aria-label="t('richText.table')" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @click="run('insertTable', { rows: 3, cols: 3, withHeaderRow: true })">▦</button>
        <template v-if="isActive('table')">
          <button v-for="command in ['addRowAfter','deleteRow','addColumnAfter','deleteColumn','toggleHeaderRow','deleteTable']" :key="command" type="button" class="editor-tool text-xs" :aria-label="t(`richText.${command}`)" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @click="run(command)">{{ t(`richText.${command}`) }}</button>
        </template>
        <button type="button" class="editor-tool text-xs" :aria-label="t('richText.clear')" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @click="editor?.chain().focus().unsetAllMarks().clearNodes().resetAttributes(['paragraph','heading'], 'textAlign').run()">{{ t('richText.clear') }}</button>
      </template>
    </div>
    <div v-if="linkOpen" class="flex flex-wrap gap-2 border-b border-border-default p-2">
      <input v-model="linkValue" :disabled="disabled" :title="disabled ? t('richText.readOnly') : undefined" type="url" class="min-w-0 flex-1 rounded-lg border border-border-default bg-surface p-2 text-sm" :aria-label="t('richText.linkUrl')" placeholder="https://" @keydown.enter.prevent="saveLink" />
      <button type="button" class="editor-tool text-xs" :disabled="disabled" :title="disabled ? t('richText.readOnly') : undefined" @click="saveLink">{{ t('richText.apply') }}</button>
      <button type="button" class="editor-tool text-xs" :disabled="disabled" :title="disabled ? t('richText.readOnly') : undefined" @click="run('unsetLink'); linkOpen = false">{{ t('richText.removeLink') }}</button>
    </div>
    <EditorContent v-show="mode === 'visual'" :editor="editor" class="editorial-body" :class="{ 'opacity-60': disabled }" />
    <textarea v-show="mode === 'source'" ref="sourceInput" :id="attrs.id ? `${attrs.id}-source` : undefined" data-testid="rich-text-source-input" :value="draft" :rows="rows" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" :placeholder="placeholder" :aria-label="contentLabel" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy" :data-editorial-active="mode === 'source' ? 'true' : undefined" class="block min-h-32 w-full resize-y rounded-b-xl bg-transparent p-3 font-mono text-sm outline-none focus:ring-2 focus:ring-focus-ring/30" @input="sourceChanged" />
    <p v-if="problem" role="alert" class="p-3 text-sm text-danger-strong">{{ problem }}</p>
    <p v-if="mode === 'source' && profile !== 'whatsapp'" class="px-3 pb-2 text-xs text-text-subtle">{{ t('richText.sourceHelp') }}</p>
  </div>
</template>

<style scoped>
.editor-tool { display: inline-flex; min-height: 2rem; min-width: 2rem; align-items: center; justify-content: center; gap: .25rem; border-radius: .5rem; padding: .25rem .5rem; }
.editor-tool:hover:not(:disabled), .editor-tool[aria-pressed='true'] { background: var(--color-surface-muted, #e6efef); color: var(--color-text-default, #002921); }
.editor-tool:focus-visible { outline: 2px solid var(--color-focus-ring, #059669); outline-offset: 2px; }
.editor-tool:disabled { opacity: .4; cursor: not-allowed; }
.editorial-body :deep(.tiptap) { min-height: 8rem; padding: .75rem; outline: none; overflow-wrap: anywhere; }
.editorial-body :deep([style*="text-align: justify"]) { white-space: normal; }
.editorial-body :deep(p) { margin: .4em 0; }
.editorial-body :deep(ul) { list-style: disc; padding-left: 1.5rem; }
.editorial-body :deep(ol) { list-style: decimal; padding-left: 1.5rem; }
.editorial-body :deep(h1) { font-size: 1.75em; font-weight: 700; }
.editorial-body :deep(h2) { font-size: 1.5em; font-weight: 700; }
.editorial-body :deep(h3) { font-size: 1.25em; font-weight: 700; }
.editorial-body :deep(blockquote) { border-left: 3px solid currentColor; padding-left: 1rem; margin: .75rem 0; }
.editorial-body :deep(pre) { white-space: pre-wrap; padding: .75rem; border: 1px solid currentColor; border-radius: .5rem; }
.editorial-body :deep(table) { border-collapse: collapse; width: 100%; table-layout: fixed; }
.editorial-body :deep(td), .editorial-body :deep(th) { border: 1px solid currentColor; padding: .5rem; vertical-align: top; }
.editorial-body :deep(.selectedCell) { outline: 2px solid var(--color-focus-ring, #059669); }
.editorial-body :deep(a) { text-decoration: underline; }
.editorial-body :deep([data-callout])::before { content: attr(data-callout); font-weight: 700; }
.editorial-body :deep(p.is-editor-empty:first-child)::before { color: var(--color-text-subtle, #6b7280); content: attr(data-placeholder); float: left; height: 0; pointer-events: none; }
</style>
