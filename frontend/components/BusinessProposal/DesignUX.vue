<template>
  <section ref="sectionRef" class="design-ux min-h-screen w-full bg-surface flex items-center">
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

            <div v-if="content.objective" class="pt-2">
              <h3 class="text-text-brand font-light text-base md:text-lg tracking-wide mb-3" v-html="linkify(content.objectiveTitle, content.text_formats?.['/objectiveTitle'])" />
              <div class="text-text-default/80 font-light leading-relaxed text-lg md:text-xl" v-html="linkify(content.objective, content.text_formats?.['/objective'])" />
            </div>
          </div>

          <aside v-if="content.focusItems?.length" data-animate="fade-up" class="lg:col-span-4">
            <div class="focus-card rounded-3xl bg-primary p-6 md:p-8">
              <h3 class="text-accent font-light text-base md:text-lg tracking-wide mb-5">
                {{ content.focusTitle }}
              </h3>
              <ul class="space-y-4">
                <li v-for="(item, idx) in content.focusItems" :key="idx" class="flex gap-3">
                  <span class="mt-3 h-1.5 w-1.5 rounded-full bg-accent flex-shrink-0"></span>
                  <div class="text-on-primary font-light leading-relaxed" v-html="linkify(item, content.text_formats?.['/focusItems/' + idx])" />
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
      index: '4',
      title: 'Diseño visual y experiencia de usuario',
      paragraphs: [
        'El desarrollo web será concebido como una experiencia digital de bienestar, calma y conexión interior. La página reflejará la esencia del método, transmitiendo serenidad, autenticidad y transformación personal a través de un diseño visual armónico y elegante 🌿✨.',
        'Cada sección será creada cuidadosamente para generar un recorrido fluido y emocional, donde el visitante sienta paz, confianza y curiosidad por conocer más sobre el acompañamiento terapéutico.',
        'El sitio no será una simple página informativa, sino un espacio de encuentro digital con energía, filosofía y propósito.'
      ],
      focusTitle: 'Estructura que resalta',
      focusItems: [
        '🌸 Presentación del método de Sanación Consciente.',
        '📚 Sección dedicada a libros publicados.',
        '🎥 Integración con canal de YouTube y redes sociales.',
        '💬 Espacio para agendar asesorías o sesiones terapéuticas en línea.'
      ],
      objectiveTitle: '<strong>Objetivo</strong>',
      objective: 'Inspirar una sensación de calma y confianza desde el primer momento, reflejando autenticidad y la profundidad del mensaje.'
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
  transition: all 0.2s ease;
}
:deep(.linkify-link:hover) {
  text-decoration-color: rgba(5, 150, 105, 0.8);
}

.focus-card :deep(.linkify-link) {
  color: #f0ff3d;
  text-decoration-color: rgba(240, 255, 61, 0.4);
}
.focus-card :deep(.linkify-link:hover) {
  color: #f0ff3d;
  text-decoration-color: rgba(240, 255, 61, 0.8);
}
:deep(b), :deep(strong) {
  font-weight: 700;
}
</style>
