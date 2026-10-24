<script setup>
import { computed, onMounted, ref } from 'vue';
import { escapeHtml, sourceToHtml } from '~/utils/editorialFormat';
const props = defineProps({
  source: { type: [String, Number], default: '' },
  format: { type: String, default: 'plain' },
  profile: { type: String, default: 'document' },
});
const mounted = ref(false);
onMounted(() => { mounted.value = true; });
const html = computed(() => {
  const source = String(props.source ?? '');
  if (!mounted.value || props.format === 'plain') return escapeHtml(source).replace(/\n/g, '<br>');
  try { return sourceToHtml(source, props.profile === 'whatsapp' || props.format === 'whatsapp_v1' ? 'whatsapp' : 'document', { strict: false }); }
  catch { return escapeHtml(source).replace(/\n/g, '<br>'); }
});
</script>

<template><div class="editorial-content min-w-0 [overflow-wrap:anywhere]" v-html="html" /></template>

<style scoped>
.editorial-content :deep(p) { margin: .4em 0; }
.editorial-content :deep(ul) { list-style: disc; padding-left: 1.5rem; }
.editorial-content :deep(ol) { list-style: decimal; padding-left: 1.5rem; }
.editorial-content :deep(h1) { font-size: 1.75em; font-weight: 700; }
.editorial-content :deep(h2) { font-size: 1.5em; font-weight: 700; }
.editorial-content :deep(h3) { font-size: 1.25em; font-weight: 700; }
.editorial-content :deep(blockquote) { border-left: 3px solid currentColor; padding-left: 1rem; margin: .75rem 0; }
.editorial-content :deep(pre) { overflow: auto; white-space: pre-wrap; padding: .75rem; border: 1px solid currentColor; }
.editorial-content :deep(table) { border-collapse: collapse; width: 100%; }
.editorial-content :deep(td), .editorial-content :deep(th) { border: 1px solid currentColor; padding: .5rem; vertical-align: top; }
.editorial-content :deep(a) { text-decoration: underline; }
</style>
