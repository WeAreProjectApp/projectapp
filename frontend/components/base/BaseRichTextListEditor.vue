<script setup>
import { ref, watch } from 'vue';
import BaseRichTextEditor from './BaseRichTextEditor.vue';
import { sourceToHtml } from '~/utils/editorialFormat';
const props = defineProps({
  modelValue: { type: String, default: '' },
  formats: { type: Object, default: () => ({}) },
  formatPath: { type: String, required: true },
  label: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  error: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue', 'update:formats']);
const { t } = useI18n();
let nextId = 0;
let publishedValue = props.modelValue;
let publishedFormats = JSON.stringify(props.formats);
const currentFormats = ref({ ...props.formats });
function entries(value) {
  return (value ? value.split('\n') : ['']).map((source, index) => ({
    id: nextId++, source, stored: source, format: props.formats[`${props.formatPath}/${index}`] || 'plain',
    declared: Object.hasOwn(props.formats, `${props.formatPath}/${index}`),
  }));
}
const items = ref(entries(props.modelValue));
watch([() => props.modelValue, () => props.formats], ([value, formats]) => {
  if (value === publishedValue && JSON.stringify(formats) === publishedFormats) return;
  // An echo of our normalized storage must not replace the active source or
  // reset the child's undo history. An external load does replace the draft.
  if (value !== publishedValue) items.value = entries(value);
  else items.value.forEach((item, index) => {
    item.format = formats[`${props.formatPath}/${index}`] || 'plain';
    item.declared = Object.hasOwn(formats, `${props.formatPath}/${index}`);
  });
  currentFormats.value = { ...formats };
  publishedValue = value;
  publishedFormats = JSON.stringify(formats);
}, { deep: true });
function publish() {
  const formats = Object.fromEntries(Object.entries(currentFormats.value).filter(([path]) => !path.startsWith(`${props.formatPath}/`)));
  items.value.forEach((item, index) => { if (item.declared) formats[`${props.formatPath}/${index}`] = item.format; });
  currentFormats.value = formats;
  publishedValue = items.value.map(item => item.stored).join('\n');
  publishedFormats = JSON.stringify(formats);
  emit('update:formats', formats);
  emit('update:modelValue', publishedValue);
}
function update(index, source) {
  const item = items.value[index];
  item.source = source;
  // One physical line per historical array entry. Inline spaces are content;
  // only actual line breaks are encoded, including breaks inside code blocks.
  try {
    item.stored = item.format === 'plain' ? source : sourceToHtml(source).replace(/\n/g, '&#10;');
  } catch {
    // Preserve an invalid source for repair and let the child show its error.
    // The server validates this same vocabulary before it can be persisted.
    item.stored = source.replace(/\n/g, '&#10;');
  }
  publish();
}
function remove(index) {
  items.value.splice(index, 1);
  publish();
}
function add() {
  items.value.push({ id: nextId++, source: '', stored: '', format: 'plain', declared: false });
  publish();
}
</script>

<template>
  <div class="min-w-0 space-y-3">
    <div v-for="(item, index) in items" :key="item.id" class="min-w-0 space-y-1">
      <BaseRichTextEditor :model-value="item.source" :format="item.format" :label="`${label} ${index + 1}`" :disabled="disabled" :error="error" @update:format="item.format = $event; item.declared = true" @update:model-value="update(index, $event)" />
      <button v-if="items.length > 1" type="button" class="text-xs text-danger-strong underline" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @click="remove(index)">{{ t('richText.removeItem') }}</button>
    </div>
    <button type="button" class="rounded-lg border border-border-default px-3 py-2 text-sm" :title="disabled ? t('richText.readOnly') : undefined" :disabled="disabled" @click="add">{{ t('richText.addItem') }}</button>
  </div>
</template>
