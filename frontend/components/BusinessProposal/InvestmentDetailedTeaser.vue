<template>
  <div class="mt-6 bg-surface border-2 border-esmerald/20 rounded-2xl p-5 sm:p-6 text-center shadow-sm">
    <div class="mb-3">
      <span class="text-2xl">🔍</span>
    </div>
    <h4 class="text-text-brand font-bold text-sm sm:text-base mb-2">
      {{ t.title }}
    </h4>
    <BaseRichTextContent class="text-text-default/60 font-light text-xs sm:text-sm leading-relaxed max-w-md mx-auto mb-4" :source="t.description" :format="t.text_formats?.['/description'] || 'plain'" />
    <button
      type="button"
      class="switch-to-detailed-btn inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-accent rounded-xl
             font-bold text-xs sm:text-sm hover:bg-esmerald/90 transition-all shadow-md"
      @click="$emit('switchToDetailed')"
    >
      {{ t.cta }}
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  language: {
    type: String,
    default: 'es',
  },
});

defineEmits(['switchToDetailed']);

const i18n = {
  es: {
    title: 'Hay más por descubrir',
    description:
      'En la Propuesta Completa encontrarás el detalle de cada elemento incluido en tu proyecto, además de funcionalidades adicionales opcionales que podrías incorporar.',
    cta: 'Ver Propuesta Completa',
  },
  en: {
    title: 'There\'s more to discover',
    description:
      'In the Full Proposal you\'ll find the details of every element included in your project, plus optional additional features you could incorporate.',
    cta: 'View Full Proposal',
  },
};

const t = computed(() => i18n[props.language] || i18n.es);
</script>
