<template>
  <section ref="sectionRef" class="context-diagnostic min-h-screen w-full bg-surface flex items-center">
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

        <div class="grid lg:grid-cols-5 gap-10 items-start">
          <div data-animate="fade-up" class="lg:col-span-3 space-y-6">
            <div
              v-for="(paragraph, idx) in content.paragraphs?.slice(0, 2)"
              :key="idx"
              class="text-text-default/80 font-light leading-relaxed text-lg md:text-xl"
              v-html="linkify(paragraph, content.text_formats?.['/paragraphs/' + idx])"
            />

            <div v-if="content.opportunity" class="pt-2">
              <h3 class="text-text-brand font-light text-base md:text-lg tracking-wide mb-3" v-html="linkify(content.opportunityTitle, content.text_formats?.['/opportunityTitle'])" />
              <div class="text-text-default/80 font-light leading-relaxed text-lg md:text-xl" v-html="linkify(content.opportunity, content.text_formats?.['/opportunity'])" />
            </div>
          </div>

          <aside v-if="content.issues?.length" data-animate="fade-up" class="lg:col-span-2">
            <div class="rounded-3xl bg-primary p-6 md:p-8">
              <h3 class="text-accent font-light text-base md:text-lg tracking-wide mb-5">
                {{ content.issuesTitle }}
              </h3>
              <ul class="space-y-4">
                <li v-for="(item, idx) in content.issues" :key="idx" class="flex gap-3">
                  <span class="mt-3 h-1.5 w-1.5 rounded-full bg-surface flex-shrink-0"></span>
                  <div class="text-white font-light leading-relaxed" v-html="linkify(item, content.text_formats?.['/issues/' + idx])" />
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
      index: '2',
      title: 'Contexto y diagnóstico',
      paragraphs: [
        'Actualmente, el proyecto está en una etapa donde es clave fortalecer la presencia digital y mostrar el perfil de forma profesional para generar confianza desde el primer contacto 🌐✅.',
        'Hoy, cuando una persona busca un servicio, normalmente compara opciones en internet y toma decisiones rápidas con base en señales como: claridad del servicio, credibilidad, facilidad para contactar y presentación general.'
      ],
      issuesTitle: 'Sin una landing page bien estructurada, pueden ocurrir estos problemas ⚠️',
      issues: [
        'Se pierde confianza: si no hay un sitio formal, algunos prospectos pueden percibir el servicio como “poco establecido” o informal.',
        'Se pierden oportunidades: personas interesadas no saben cómo contactarte rápido o no encuentran información suficiente y se van.',
        'Mensaje disperso: los servicios no quedan claros (qué haces, para quién, cómo trabajas), lo que reduce la intención de solicitar asesoría.'
      ],
      opportunityTitle: 'La oportunidad 🎯',
      opportunity: 'Crear una landing clara, directa y profesional que comunique la propuesta de valor en pocos segundos, muestre los servicios de forma ordenada y facilite el contacto inmediato (WhatsApp / formulario), elevando la confianza y aumentando las conversaciones de asesoría.'
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
