<template>
  <section>
    <SectionHeader :index="content.index" :title="content.title" fallback="Resumen Ejecutivo" />
    <BaseRichTextContent v-if="content.intro" class="text-text-brand/80 dark:text-text-brand/80 mb-6" :source="content.intro" :format="content.text_formats?.['/intro'] || 'plain'" />

    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div
        v-for="(count, key) in counts"
        :key="key"
        class="bg-surface dark:bg-primary-soft border border-input-border rounded-2xl p-4 text-center shadow-sm"
      >
        <div
          class="text-3xl font-semibold"
          :class="levelColor(key)"
        >{{ count }}</div>
        <div class="text-xs font-medium text-text-brand/55 dark:text-text-brand/60 uppercase mt-1 tracking-wide">{{ labelFor(key) }}</div>
      </div>
    </div>

    <BaseRichTextContent v-if="content.narrative" class="text-text-brand/80 dark:text-text-brand/80 leading-relaxed whitespace-pre-line" :source="content.narrative" :format="content.text_formats?.['/narrative'] || 'plain'" />

    <ul v-if="content.highlights?.length" class="mt-4 list-disc pl-5 space-y-1 text-text-brand/80 dark:text-text-brand/80">
      <li v-for="(h, idx) in content.highlights" :key="idx"><BaseRichTextContent :source="h" :format="content.text_formats?.['/highlights/' + idx] || 'plain'" /></li>
    </ul>
  </section>
</template>

<script setup>
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import { computed } from 'vue';
import SectionHeader from './SectionHeader.vue';

const props = defineProps({ content: { type: Object, required: true } });

const counts = computed(() => ({
  critico: props.content.severityCounts?.critico ?? 0,
  alto: props.content.severityCounts?.alto ?? 0,
  medio: props.content.severityCounts?.medio ?? 0,
  bajo: props.content.severityCounts?.bajo ?? 0,
}));

function labelFor(key) {
  return { critico: 'Crítico', alto: 'Alto', medio: 'Medio', bajo: 'Bajo' }[key] || key;
}
function levelColor(key) {
  return {
    critico: 'text-rose-600 dark:text-rose-300',
    alto: 'text-amber-600 dark:text-amber-300',
    medio: 'text-yellow-600 dark:text-yellow-300',
    bajo: 'text-text-brand dark:text-accent',
  }[key] || 'text-text-brand/60 dark:text-text-brand/60';
}
</script>
