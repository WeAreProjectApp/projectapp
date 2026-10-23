<template>
  <section ref="sectionRef" class="timeline py-16 md:py-24 bg-surface">
    <div class="container mx-auto px-6 md:px-12 lg:px-24 max-w-5xl">
      <div class="section-header mb-12">
        <div data-animate="fade-up" class="flex items-baseline gap-4 mb-10">
          <span class="text-text-muted font-light tracking-[0.25em] text-xs md:text-sm">
            {{ index }}
          </span>
          <h2 class="text-text-brand font-light leading-tight text-4xl md:text-6xl">
            {{ title }}
          </h2>
        </div>
      </div>

      <div class="timeline-intro mb-12">
        <div data-animate="fade-up" class="text-text-default/80 font-light leading-relaxed text-lg md:text-xl mb-6" v-html="linkify(introText, text_formats?.['/introText'])" />
        <div data-animate="fade-up" class="duration-summary bg-primary-soft p-6 rounded-xl inline-block">
          <div class="flex items-center">
            <svg class="w-8 h-8 text-text-brand mr-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
            </svg>
            <div>
              <div class="text-sm text-green-light">Duración Total Estimada</div>
              <div class="text-2xl font-bold text-text-brand">{{ totalDuration }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="timeline-container relative">
        <div class="absolute left-8 top-0 bottom-0 w-1 bg-gradient-to-b from-esmerald via-esmerald/60 to-green-light/10 hidden md:block"></div>

        <div data-animate="fade-up-stagger" class="space-y-8">
          <div v-for="(phase, index) in phases" :key="index"
               class="timeline-item relative">
            <div class="flex flex-col sm:flex-row items-start gap-4 sm:gap-0">
              <div class="flex-shrink-0 sm:mr-8 relative z-10">
                <div class="w-12 h-12 sm:w-16 sm:h-16 rounded-full flex items-center justify-center shadow-raised bg-primary">
                  <span class="text-xl sm:text-2xl font-bold text-accent">{{ index + 1 }}</span>
                </div>
              </div>

              <div class="flex-1 bg-surface p-5 sm:p-8 rounded-2xl border border-border-default shadow-card hover:shadow-raised transition-shadow">
                <div class="flex flex-col md:flex-row md:items-center md:justify-between mb-4">
                  <div>
                    <h3 class="text-2xl font-bold text-text-brand mb-2">{{ phase.title }}</h3>
                    <div class="flex items-center text-sm text-green-light">
                      <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
                      </svg>
                      <span>{{ phase.duration }}</span>
                    </div>
                  </div>
                  <div v-if="phase.weeks" class="mt-4 md:mt-0">
                    <span class="inline-block px-4 py-2 rounded-full text-sm font-medium bg-primary-soft text-text-brand">
                      {{ typeof phase.weeks === 'string' ? phase.weeks : 'Semanas: ' + (Array.isArray(phase.weeks) ? phase.weeks.join(', ') : phase.weeks) }}
                    </span>
                  </div>
                </div>

                <BaseRichTextContent class="text-text-default/70 font-light leading-relaxed mb-6" :source="phase.description" :format="phase.text_formats?.['/description'] || 'plain'" />

                <div class="tasks-list space-y-3">
                  <div v-for="(task, idx) in phase.tasks" :key="idx"
                       class="task-item flex items-start p-3 bg-esmerald/5 rounded-lg hover:bg-primary-soft transition-colors">
                    <svg class="w-5 h-5 text-text-brand mr-3 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                    </svg>
                    <span class="text-sm text-text-default/80">{{ task }}</span>
                  </div>
                </div>

                <div v-if="phase.milestone" class="milestone-badge mt-6 pt-6 border-t border-border-muted">
                  <div class="flex items-center">
                    <svg class="w-6 h-6 text-accent mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                    </svg>
                    <span class="font-bold text-text-brand">Hito: {{ phase.milestone }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
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
  index: {
    type: String,
    default: '8'
  },
  title: {
    type: String,
    default: 'Cronograma del Proyecto'
  },
  introText: {
    type: String,
    default: 'Este cronograma detalla cada fase del proyecto con tiempos realistas. Mantenemos flexibilidad para ajustes según tus necesidades, pero nos comprometemos a cumplir los plazos acordados.'
  },
  totalDuration: {
    type: String,
    default: '12 Semanas'
  },
  phases: {
    type: Array,
    default: () => [
      {
        title: 'Discovery & Strategy',
        duration: 'Semana 1-2',
        weeks: '2 semanas',
        circleColor: 'bg-blue-600',
        statusColor: 'bg-blue-100 text-blue-700',
        description: 'Fase inicial de investigación y planificación estratégica.',
        tasks: [
          'Reunión de kickoff y alineación de objetivos',
          'Investigación de mercado y análisis competitivo',
          'Definición de buyer personas y user journeys',
          'Creación de arquitectura de información',
          'Wireframes de baja fidelidad'
        ],
        milestone: 'Aprobación de Estrategia y Wireframes'
      },
      {
        title: 'Design & Prototyping',
        duration: 'Semana 3-5',
        weeks: '3 semanas',
        circleColor: 'bg-purple-600',
        statusColor: 'bg-purple-100 text-purple-700',
        description: 'Diseño visual completo y creación de prototipos interactivos.',
        tasks: [
          'Desarrollo de moodboard y paleta de colores',
          'Diseño de página principal en alta fidelidad',
          'Diseño de páginas internas clave',
          'Creación de prototipo interactivo',
          'Guía de estilo y sistema de diseño'
        ],
        milestone: 'Aprobación de Diseños Finales'
      },
      {
        title: 'Development',
        duration: 'Semana 6-9',
        weeks: '4 semanas',
        circleColor: 'bg-green-600',
        statusColor: 'bg-green-100 text-green-700',
        description: 'Desarrollo del sitio con código limpio y optimizado.',
        tasks: [
          'Setup de ambiente de desarrollo',
          'Desarrollo frontend responsive',
          'Implementación de backend y base de datos',
          'Integración de CMS y funcionalidades',
          'Optimización de performance y SEO técnico'
        ],
        milestone: 'Demo de Sitio Funcional'
      },
      {
        title: 'Testing & QA',
        duration: 'Semana 10-11',
        weeks: '2 semanas',
        circleColor: 'bg-orange-600',
        statusColor: 'bg-orange-100 text-orange-700',
        description: 'Pruebas exhaustivas y corrección de bugs.',
        tasks: [
          'Testing cross-browser y responsive',
          'Pruebas de funcionalidades y formularios',
          'Optimización final de velocidad',
          'Testing de seguridad y vulnerabilidades',
          'User Acceptance Testing (UAT)'
        ],
        milestone: 'Aprobación Final del Cliente'
      },
      {
        title: 'Launch & Training',
        duration: 'Semana 12',
        weeks: '1 semana',
        circleColor: 'bg-pink-600',
        statusColor: 'bg-pink-100 text-pink-700',
        description: 'Lanzamiento en producción y capacitación.',
        tasks: [
          'Migración a servidor de producción',
          'Configuración de dominio y SSL',
          'Sesión de capacitación en vivo',
          'Entrega de documentación y videos',
          'Monitoreo post-lanzamiento'
        ],
        milestone: 'Go Live! 🚀'
      }
    ]
  },
});
</script>

<style scoped>
.task-item {
  transition: all 0.3s ease;
}

.calendar-week {
  transition: all 0.3s ease;
}

.calendar-week:hover {
  transform: scale(1.05);
}
</style>
