<template>
  <section>
    <SectionHeader :index="content.index" :title="content.title" fallback="Cronograma" />
    <BaseRichTextContent v-if="content.intro" class="text-text-brand/80 dark:text-text-brand/80 leading-relaxed" :source="content.intro" :format="content.text_formats?.['/intro'] || 'plain'" />

    <p v-if="durationLabel" class="mt-3 text-text-brand/80 dark:text-text-brand/80">
      Duración estimada: <strong class="text-text-brand dark:text-text-brand">{{ durationLabel }}</strong>.
    </p>

    <h3 v-if="content.distributionTitle" class="text-lg font-semibold text-text-brand dark:text-text-brand mt-6 mb-4">
      {{ content.distributionTitle }}
    </h3>

    <ol class="space-y-4">
      <li
        v-for="(d, idx) in content.distribution"
        :key="idx"
        class="flex gap-4 items-start"
      >
        <span
          class="flex-none w-9 h-9 rounded-full
                 bg-primary dark:bg-accent-soft text-accent dark:text-text-brand text-sm font-semibold
                 flex items-center justify-center leading-none shadow-sm
                 ring-4 ring-esmerald/10 dark:ring-lemon/15"
        >
          {{ idx + 1 }}
        </span>
        <div class="flex-1 min-w-0 border-l-2 border-input-border pl-4 pb-2">
          <div class="font-semibold text-text-brand dark:text-text-brand">{{ d.dayRange }}</div>
          <BaseRichTextContent class="text-sm text-text-brand/70 dark:text-text-brand/70 leading-relaxed mt-0.5" :source="d.description" :format="d.text_formats?.['/description'] || 'plain'" />
        </div>
      </li>
    </ol>
  </section>
</template>

<script setup>
import BaseRichTextContent from '~/components/base/BaseRichTextContent.vue';
import { computed } from 'vue';
import SectionHeader from './SectionHeader.vue';

const props = defineProps({
  content: { type: Object, required: true },
  diagnostic: { type: Object, required: true },
});

const durationLabel = computed(() => props.diagnostic?.duration_label || '');
</script>
