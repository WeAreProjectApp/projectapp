<template>
  <section ref="sectionRef" class="executive-summary min-h-screen w-full bg-surface flex items-center">
    <div class="w-full px-6 md:px-12 lg:px-24 py-12 md:py-6">
      <div class="max-w-7xl mx-auto">
        <div data-animate="fade-up" class="flex items-baseline gap-4 mb-10">
          <span class="text-text-muted font-light tracking-[0.25em] text-xs md:text-sm">
            {{ content.index }}
          </span>
          <h2 class="text-text-brand font-light leading-tight text-4xl md:text-6xl">
            {{ content.title }}
          </h2>
        </div>

        <div class="grid lg:grid-cols-12 gap-10 items-start">
          <div data-animate="fade-up" class="lg:col-span-8 space-y-6">
            <div
              v-for="(paragraph, idx) in content.paragraphs?.slice(0, 2)"
              :key="idx"
              class="text-text-default/80 font-light leading-relaxed text-lg md:text-xl"
              v-html="linkify(paragraph, content.text_formats?.['/paragraphs/' + idx])"
            />
          </div>

          <aside v-if="content.highlights?.length" data-animate="fade-up" class="lg:col-span-4">
            <div class="rounded-3xl bg-primary p-6 md:p-8">
              <h3 class="text-accent font-light text-base md:text-lg tracking-wide mb-5">
                {{ content.highlightsTitle }}
              </h3>
              <ul class="space-y-4">
                <li v-for="(item, idx) in content.highlights" :key="idx" class="flex gap-3">
                  <span class="mt-3 h-1.5 w-1.5 rounded-full bg-surface flex-shrink-0"></span>
                  <div class="text-white font-light leading-relaxed" v-html="linkify(item, content.text_formats?.['/highlights/' + idx])" />
                </li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue';
import { useSectionAnimations } from '~/composables/useSectionAnimations';
import { linkify } from '~/composables/useLinkify';

const sectionRef = ref(null);
useSectionAnimations(sectionRef);

const props = defineProps({
  text_formats: { type: Object, default: () => ({}) },
  content: {
    type: Object,
    default: () => ({
      index: '1',
      title: 'Resumen ejecutivo',
      paragraphs: [
        'Crearemos una landing page profesional enfocada en presentar tu perfil y portafolio de servicios, y facilitar que los visitantes te contacten de forma rápida.',
        'La página incluirá llamados a la acción visibles (por ejemplo: “Escríbeme por WhatsApp” o “Solicitar asesoría”), para que cualquier persona sepa exactamente qué hacer y cómo comunicarse, sin fricción.',
        'Además, integraremos un módulo de autogestión para que puedas cambiar imágenes y/o videos cuando lo necesites, sin depender de desarrollo.'
      ],
      highlightsTitle: 'Incluye',
      highlights: [
        'Mensajes y botones de contacto siempre visibles',
        'Estructura clara orientada a conversión',
        'Autogestión de contenido (imágenes / videos)'
      ]
    })
  }
});
</script>

<style scoped>
:deep(.linkify-link) {
  color: #059669;
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: rgba(5, 150, 105, 0.3);
  transition: text-decoration-color 0.2s ease;
}
:deep(.linkify-link:hover) {
  text-decoration-color: rgba(5, 150, 105, 0.8);
}
:deep(b), :deep(strong) {
  font-weight: 700;
}
</style>
