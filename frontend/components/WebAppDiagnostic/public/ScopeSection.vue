<template>
  <section>
    <SectionHeader :index="content.index" :title="content.title" fallback="Alcance y Consideraciones" />
    <ul class="space-y-2.5 text-text-brand/80 dark:text-text-brand/80 leading-relaxed">
      <li v-for="(c, idx) in content.considerations" :key="idx" class="flex gap-3">
        <span class="mt-1.5 flex-none w-1.5 h-1.5 rounded-full bg-primary dark:bg-accent-soft" />
        <BaseRichTextContent :source="c" :format="content.text_formats?.['/considerations/' + idx] || 'plain'" />
      </li>
    </ul>
  </section>
</template>

<script setup>
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import SectionHeader from './SectionHeader.vue';
defineProps({ content: { type: Object, required: true } });
</script>
