<template>
  <section>
    <SectionHeader :index="content.index" :title="content.title" fallback="Estructura de la Entrega" />
    <BaseRichTextContent v-if="content.intro" class="text-text-brand/80 dark:text-text-brand/80 mb-6" :source="content.intro" :format="content.text_formats?.['/intro'] || 'plain'" />

    <div class="grid md:grid-cols-3 gap-4">
      <div
        v-for="(b, idx) in content.blocks"
        :key="idx"
        class="bg-surface dark:bg-primary-soft border border-input-border rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-input-border dark:hover:border-input-border transition"
      >
        <h3 class="font-semibold text-text-brand dark:text-text-brand mb-2">{{ b.title }}</h3>
        <BaseRichTextContent v-for="(p, i) in b.paragraphs" :key="i" class="text-sm text-text-brand/75 dark:text-text-brand/75 leading-relaxed" :source="p" :format="b.text_formats?.['/paragraphs/' + i] || 'plain'" />
        <blockquote v-if="b.example" class="mt-3 border-l-2 border-input-border pl-3 text-xs italic text-text-brand/80 dark:text-text-brand/80">
          Ejemplo: <BaseRichTextContent :source="b.example" :format="b.text_formats?.['/example'] || 'plain'" />
        </blockquote>
      </div>
    </div>
  </section>
</template>

<script setup>
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import SectionHeader from './SectionHeader.vue';
defineProps({ content: { type: Object, required: true } });
</script>
