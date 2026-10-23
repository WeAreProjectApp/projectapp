<template>
  <section ref="sectionRef" class="final-note py-16 md:py-24 bg-surface">
    <div class="container mx-auto max-w-7xl px-6 md:px-12">
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

      <div data-testid="final-note-columns" class="grid items-stretch gap-8 xl:grid-cols-2 xl:gap-10">
        <div data-testid="commitment-column" class="flex flex-col gap-5">
          <div data-animate="fade-up" class="note-content flex-1 rounded-2xl bg-surface-raised p-5 shadow-sm sm:p-8">
            <div class="quote-icon mb-6">
              <svg class="w-12 h-12 text-text-brand opacity-50" fill="currentColor" viewBox="0 0 24 24">
                <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z"/>
              </svg>
            </div>

            <div class="message-text space-y-6 text-lg text-text-default leading-relaxed">
              <div v-html="linkify(message, text_formats?.['/message'])" />
              <div v-if="personalNote" class="italic text-text-muted" v-html="linkify(personalNote, text_formats?.['/personalNote'])" />
            </div>

            <div class="signature mt-10 pt-7 border-t border-border-default">
              <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p class="text-xl font-bold text-text-default mb-2">{{ teamName }}</p>
                  <p class="text-text-muted">{{ teamRole }}</p>
                  <p class="text-sm text-text-subtle mt-2">{{ contactEmail }}</p>
                </div>
                <img v-if="signature" :src="signature" alt="Firma" class="h-16 mt-6 sm:mt-0" />
              </div>
            </div>
          </div>

          <div data-animate="fade-up-stagger" class="commitment-badges grid sm:grid-cols-3 gap-3">
            <div v-for="(badge, badgeIndex) in commitmentBadges" :key="badgeIndex"
                 class="badge-card bg-primary-soft p-4 rounded-xl border border-border-default text-center hover:shadow-md transition-shadow">
              <div class="text-2xl mb-2">{{ badge.icon }}</div>
              <h4 class="font-bold text-text-default text-sm mb-1">{{ badge.title }}</h4>
              <BaseRichTextContent class="text-xs text-text-muted leading-relaxed" :source="badge.description" :format="badge.text_formats?.['/description'] || 'plain'" />
            </div>
          </div>
        </div>

        <div
          v-if="kickoffPlan?.length || nextSteps?.length"
          data-animate="fade-up"
          data-testid="kickoff-card"
          class="kickoff-card rounded-2xl border border-border-default bg-primary-soft p-5 shadow-sm sm:p-8"
        >
          <template v-if="kickoffPlan?.length">
            <h3 class="text-2xl font-bold text-text-brand mb-2">{{ kickoffTitle }}</h3>
            <p class="text-sm text-text-muted mb-8">{{ kickoffSubtitle }}</p>
            <div class="relative">
              <div class="absolute left-6 top-0 bottom-0 w-0.5 bg-primary/20"></div>
              <div v-for="(step, kIdx) in kickoffPlan" :key="kIdx" class="relative flex items-start gap-4 mb-6 last:mb-0">
                <div class="relative z-10 flex-shrink-0 w-12 h-12 bg-primary text-accent rounded-full flex items-center justify-center font-bold text-sm shadow-md">
                  {{ step.day || `D${kIdx + 1}` }}
                </div>
                <div class="pt-1">
                  <h4 class="font-bold text-text-brand text-sm sm:text-base">{{ step.title }}</h4>
                  <BaseRichTextContent class="text-xs sm:text-sm text-text-muted leading-relaxed mt-1" :source="step.description" :format="step.text_formats?.['/description'] || 'plain'" />
                </div>
              </div>
            </div>
          </template>

          <details
            v-if="nextSteps?.length"
            data-testid="next-steps-disclosure"
            class="next-steps-disclosure mt-8 rounded-xl border border-border-default bg-surface overflow-hidden"
          >
            <summary class="flex items-center justify-between gap-3 px-5 py-4 cursor-pointer font-semibold text-text-brand">
              <span>{{ nextStepsDisclosureTitle }}</span>
              <span aria-hidden="true" class="disclosure-icon text-lg">⌄</span>
            </summary>
            <div class="px-5 pb-5 border-t border-border-default">
              <div v-if="nextStepsIntro" class="text-sm text-text-default/75 leading-relaxed py-4" v-html="linkify(nextStepsIntro, text_formats?.['/nextStepsIntro'])" />
              <ol class="space-y-3">
                <li v-for="(step, sIdx) in nextSteps" :key="sIdx" class="flex items-start gap-3">
                  <span class="w-7 h-7 rounded-full bg-primary text-accent text-xs font-bold flex items-center justify-center shrink-0">{{ sIdx + 1 }}</span>
                  <div>
                    <h4 class="text-sm font-bold text-text-brand">{{ step.title }}</h4>
                    <BaseRichTextContent class="text-xs text-text-muted leading-relaxed mt-0.5" :source="step.description" :format="step.text_formats?.['/description'] || 'plain'" />
                  </div>
                </li>
              </ol>
            </div>
          </details>
        </div>
      </div>

    </div>
  </section>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useSectionAnimations } from '~/composables/useSectionAnimations';
import { linkify } from '~/composables/useLinkify';

const sectionRef = ref(null);
useSectionAnimations(sectionRef);

const props = defineProps({
  text_formats: { type: Object, default: () => ({}) },
  index: {
    type: String,
    default: '10'
  },
  title: {
    type: String,
    default: 'Nota Final'
  },
  message: {
    type: String,
    default: 'Creemos firmemente que esta propuesta representa una oportunidad excepcional para transformar tu presencia digital y alcanzar tus objetivos de negocio. Cada elemento ha sido cuidadosamente diseñado pensando en tus necesidades específicas y en los resultados que buscas lograr. Estamos comprometidos no solo con entregar un proyecto excepcional, sino con construir una relación de largo plazo donde tu éxito sea nuestro éxito.'
  },
  personalNote: {
    type: String,
    default: 'Estamos emocionados por la posibilidad de trabajar contigo y ayudarte a llevar tu negocio al siguiente nivel. Esta propuesta es solo el comienzo de lo que podemos lograr juntos.'
  },
  teamName: {
    type: String,
    default: 'El equipo de Project App'
  },
  teamRole: {
    type: String,
    default: 'Tu socio en transformación digital'
  },
  contactEmail: {
    type: String,
    default: 'hola@projectapp.com'
  },
  signature: {
    type: String,
    default: null
  },
  commitmentBadges: {
    type: Array,
    default: () => [
      {
        icon: '🤝',
        title: 'Compromiso Total',
        description: 'Dedicación completa a tu proyecto hasta lograr resultados excepcionales'
      },
      {
        icon: '💯',
        title: 'Garantía de Calidad',
        description: 'Revisiones ilimitadas hasta tu completa satisfacción'
      },
      {
        icon: '🎯',
        title: 'Enfoque en Resultados',
        description: 'Medimos nuestro éxito por el impacto en tu negocio'
      }
    ]
  },
  validityMessage: {
    type: String,
    default: ''
  },
  thankYouMessage: {
    type: String,
    default: ''
  },
  nextSteps: {
    type: Array,
    default: () => []
  },
  nextStepsIntro: {
    type: String,
    default: ''
  },
  kickoffPlan: {
    type: Array,
    default: () => []
  },
  language: {
    type: String,
    default: 'es'
  }
});

const kickoffTitle = computed(() => {
  return props.language === 'en' ? 'Kickoff Plan' : 'Plan de Kickoff';
});

const kickoffSubtitle = computed(() => {
  return props.language === 'en'
    ? 'What happens in the first days after you approve'
    : 'Qué sucede en los primeros días después de aprobar';
});

const nextStepsDisclosureTitle = computed(() => (
  props.language === 'en'
    ? 'Information required to activate the schedule'
    : 'Información necesaria para activar el cronograma'
));
</script>

<style scoped>
.badge-card {
  transition: all 0.3s ease;
}

.badge-card:hover {
  transform: translateY(-4px);
}

.message-text p {
  text-align: justify;
}

.next-steps-disclosure[open] .disclosure-icon {
  transform: rotate(180deg);
}

.disclosure-icon {
  transition: transform 0.2s ease;
}
</style>
