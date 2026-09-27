<template>
  <section class="proposal-gateway min-h-screen flex items-center justify-center bg-surface px-4 py-12 sm:py-16">
    <div class="max-w-6xl w-full mx-auto">
      <!-- Header -->
      <div class="gateway-header text-center mb-10 sm:mb-14">
        <h2 class="text-text-brand font-light leading-tight text-3xl sm:text-4xl md:text-5xl mb-3">
          {{ t.heading }}
        </h2>
        <p class="text-green-light font-light text-base sm:text-lg max-w-2xl mx-auto leading-relaxed">
          {{ t.subheading }}
        </p>
      </div>

      <ExplainerVideoCard
        v-if="showExplainerVideo && showTechnical && showLegal && explainerVideo"
        ref="explainerCard"
        :video="explainerVideo"
        i18n-namespace="proposalExplainer"
        content-locale="es-co"
        :content-messages="explainerMessages"
        test-id="proposal-explainer"
        class="mx-auto mb-8 max-w-3xl sm:mb-10"
      />

      <!-- Cards -->
      <div
        class="grid grid-cols-1 gap-5 sm:gap-6"
        :class="gatewayGridClass"
      >
        <!-- Executive card -->
        <button
          type="button"
          data-testid="gateway-executive-card"
          class="gateway-card group relative bg-primary rounded-2xl sm:rounded-3xl p-6 sm:p-8 text-left
                 border-2 border-transparent hover:border-lemon transition-all duration-300
                 shadow-lg hover:shadow-2xl cursor-pointer"
          @click="selectMode('executive')"
        >
          <div class="flex items-center gap-3 mb-4">
            <div class="w-12 h-12 bg-accent rounded-xl flex items-center justify-center flex-shrink-0">
              <span class="text-2xl">⚡</span>
            </div>
            <div>
              <h3 class="text-white font-bold text-lg sm:text-xl leading-tight">{{ t.executiveTitle }}</h3>
              <span class="text-white/80 text-xs font-medium uppercase tracking-wider">{{ t.executiveTime }}</span>
            </div>
          </div>
          <p class="text-white/90 font-light text-sm sm:text-base leading-relaxed mb-6">
            {{ t.executiveSub }}
          </p>
          <div class="flex items-center gap-2 text-white font-medium text-sm group-hover:gap-3 transition-all">
            <span>{{ t.executiveCta }}</span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </button>

        <!-- Complete card -->
        <button
          type="button"
          data-testid="gateway-detailed-card"
          class="gateway-card group relative bg-surface rounded-2xl sm:rounded-3xl p-6 sm:p-8 text-left
                 border-2 border-esmerald/15 hover:border-border-default transition-all duration-300
                 shadow-lg hover:shadow-2xl cursor-pointer"
          @click="selectMode('detailed')"
        >
          <div class="flex items-center gap-3 mb-4">
            <div class="w-12 h-12 bg-esmerald/10 rounded-xl flex items-center justify-center flex-shrink-0">
              <span class="text-2xl">📋</span>
            </div>
            <div>
              <h3 class="text-text-brand font-bold text-lg sm:text-xl leading-tight">{{ t.detailedTitle }}</h3>
              <span class="text-green-light text-xs font-medium uppercase tracking-wider">{{ t.detailedTime }}</span>
            </div>
          </div>
          <p class="text-text-default/70 font-light text-sm sm:text-base leading-relaxed mb-6">
            {{ t.detailedSub }}
          </p>
          <div class="flex items-center gap-2 text-text-brand font-medium text-sm group-hover:gap-3 transition-all">
            <span>{{ t.detailedCta }}</span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </button>

        <!-- Technical card -->
        <button
          v-if="showTechnical"
          type="button"
          data-testid="gateway-technical-card"
          class="gateway-card group relative bg-surface rounded-2xl sm:rounded-3xl p-6 sm:p-8 text-left
                 border-2 border-teal-500/25 hover:border-teal-600 transition-all duration-300
                 shadow-lg hover:shadow-2xl cursor-pointer sm:col-span-2 lg:col-span-1"
          @click="selectMode('technical')"
        >
          <div class="flex items-center gap-3 mb-4">
            <div class="w-12 h-12 bg-teal-500/10 rounded-xl flex items-center justify-center flex-shrink-0">
              <span class="text-2xl">🔧</span>
            </div>
            <div>
              <h3 class="text-text-brand font-bold text-lg sm:text-xl leading-tight">{{ t.technicalTitle }}</h3>
              <span class="text-teal-600/70 text-xs font-medium uppercase tracking-wider">{{ t.technicalTime }}</span>
            </div>
          </div>
          <p class="text-text-default/70 font-light text-sm sm:text-base leading-relaxed mb-6">
            {{ t.technicalSub }}
          </p>
          <div class="flex items-center gap-2 text-teal-700 font-medium text-sm group-hover:gap-3 transition-all">
            <span>{{ t.technicalCta }}</span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </button>

        <!-- Contract terms card -->
        <button
          v-if="showLegal"
          type="button"
          data-testid="gateway-legal-card"
          class="gateway-card group relative bg-surface rounded-2xl sm:rounded-3xl p-6 sm:p-8 text-left
                 border-2 border-warning-strong/30 hover:border-warning-strong transition-all duration-300
                 shadow-lg hover:shadow-2xl cursor-pointer"
          @click="selectMode('legal')"
        >
          <div class="flex items-center gap-3 mb-4">
            <div class="w-12 h-12 bg-warning-soft rounded-xl flex items-center justify-center flex-shrink-0">
              <span class="text-2xl">⚖️</span>
            </div>
            <div>
              <h3 class="text-text-brand font-bold text-lg sm:text-xl leading-tight">{{ t.legalTitle }}</h3>
              <span class="text-warning-strong text-xs font-medium uppercase tracking-wider">{{ t.legalTime }}</span>
            </div>
          </div>
          <p class="text-text-default/70 font-light text-sm sm:text-base leading-relaxed mb-6">
            {{ t.legalSub }}
          </p>
          <div class="flex items-center gap-2 text-warning-strong font-medium text-sm group-hover:gap-3 transition-all">
            <span>{{ t.legalCta }}</span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import ExplainerVideoCard from '~/components/ExplainerVideoCard.vue';
import { useExplainerVideo } from '~/composables/useExplainerVideos';
import { TECH_READING_TIME } from '~/utils/technicalProposalPanels';
import proposalExplainerEs from '~/locales/proposalExplainer/es';

const props = defineProps({
  showExplainerVideo: { type: Boolean, default: false },
  language: {
    type: String,
    default: 'es',
  },
  clientName: {
    type: String,
    default: '',
  },
  showTechnical: {
    type: Boolean,
    default: false,
  },
  showLegal: {
    type: Boolean,
    default: false,
  },
});

// The Spanish document must not depend on the browser locale loading first.
const explainerMessages = { 'es-co': { proposalExplainer: proposalExplainerEs } };
const emit = defineEmits(['select']);
const explainerCard = ref(null);
const explainerVideo = useExplainerVideo('proposal', computed(() => props.language));
function selectMode(mode) {
  explainerCard.value?.pause();
  emit('select', mode);
}

const i18n = {
  es: {
    heading: '¿Cómo prefieres explorar esta propuesta?',
    subheading: 'Elige el nivel de detalle que mejor se adapte a tu tiempo y necesidad.',
    executiveTitle: 'Vista Ejecutiva',
    executiveSub: 'Lo esencial para tomar tu decisión: qué incluye, cuánto cuesta y cuándo lo tienes.',
    executiveTime: '~2 min de lectura',
    executiveCta: 'Ir al resumen',
    detailedTitle: 'Propuesta Completa',
    detailedSub: 'La propuesta completa: contexto del proyecto, propuesta de valor, estrategia comercial, requerimientos y proceso de trabajo.',
    detailedTime: '~8 min de lectura',
    detailedCta: 'Ver todo el detalle',
    technicalTitle: 'Detalle técnico',
    technicalSub: 'Documentación técnica completa: arquitectura del sistema, stack tecnológico, modelo de datos, módulos y especificaciones de requerimientos.',
    technicalTime: TECH_READING_TIME.es,
    technicalCta: 'Ver detalle técnico',
    legalTitle: 'Contrato y condiciones',
    legalSub: 'Consulta de forma transparente el borrador del contrato, sus cláusulas, garantías, pagos, responsabilidades y condiciones del servicio.',
    legalTime: '~10 min de lectura',
    legalCta: 'Revisar el borrador',
  },
  en: {
    heading: 'How would you like to explore this proposal?',
    subheading: 'Choose the level of detail that best fits your time and needs.',
    executiveTitle: 'Executive View',
    executiveSub: 'The essentials to make your decision: what\'s included, how much it costs, and when you\'ll have it.',
    executiveTime: '~2 min read',
    executiveCta: 'Go to summary',
    detailedTitle: 'Full Proposal',
    detailedSub: 'The complete proposal: project context, value proposition, commercial strategy, requirements, and work process.',
    detailedTime: '~8 min read',
    detailedCta: 'See all the details',
    technicalTitle: 'Technical detail',
    technicalSub: 'Full technical documentation: system architecture, tech stack, data model, product modules, and requirement specifications.',
    technicalTime: TECH_READING_TIME.en,
    technicalCta: 'View technical detail',
    legalTitle: 'Contract and terms',
    legalSub: 'Review the draft service agreement and its main conditions.',
    legalTime: '~10 min read',
    legalCta: 'Review the draft',
  },
};

const t = computed(() => i18n[props.language] || i18n.es);
const gatewayGridClass = computed(() => {
  const visibleCards = 2 + Number(props.showTechnical) + Number(props.showLegal);
  return visibleCards === 3
    ? 'sm:grid-cols-2 lg:grid-cols-3'
    : 'sm:grid-cols-2';
});
</script>

<style scoped>
@keyframes gatewayItemIn {
  from {
    opacity: 0;
    transform: translateY(22px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.gateway-header {
  animation: gatewayItemIn 0.65s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: 0.08s;
}

.gateway-card {
  animation: gatewayItemIn 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
}
.gateway-card:nth-child(1) { animation-delay: 0.18s; }
.gateway-card:nth-child(2) { animation-delay: 0.36s; }
.gateway-card:nth-child(3) { animation-delay: 0.54s; }
.gateway-card:nth-child(4) { animation-delay: 0.72s; }

.gateway-card:hover {
  transform: translateY(-4px);
}
</style>
