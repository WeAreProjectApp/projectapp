<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { SquaresPlusIcon, UserGroupIcon, QuestionMarkCircleIcon } from '@heroicons/vue/24/outline'
import PublicGuidedTour from '~/components/PublicGuidedTour.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import { useProposalDarkMode } from '~/composables/useProposalDarkMode'

const props = defineProps({ language: { type: String, default: 'es' } })
const { isDark } = useProposalDarkMode()
const tour = ref(null)
const localePath = computed(() => props.language === 'en' ? '/en-us' : '/es-co')
const es = {
  video: ['Tu propuesta en un minuto', 'Mira este video para conocer la propuesta antes de elegir cómo explorarla.'],
  executive: ['Vista ejecutiva', 'Lo esencial para decidir: qué incluye tu proyecto, su inversión y los tiempos.'],
  detailed: ['Propuesta completa', 'Explora el contexto, la solución, los requerimientos y el proceso de trabajo.'],
  technical: ['Detalle técnico', 'Consulta la arquitectura, las tecnologías y los requerimientos técnicos de tu proyecto.'],
  legal: ['Contrato y condiciones', 'Revisa el borrador del contrato y las condiciones del servicio.'],
  modules: ['Módulos adicionales', 'Conoce opciones para ampliar tu proyecto. El catálogo completo se abre en otra pestaña.'],
  alliance: ['Programa de alianza', 'Descubre cómo podemos trabajar juntos con el programa de alianza. Se abre en otra pestaña.'],
  restart: ['Volver a ver la guía', 'Puedes repetir este recorrido cuando lo necesites.'],
  skip: 'Omitir', back: 'Anterior', next: 'Siguiente', done: 'Entendido',
}
const en = {
  video: ['Your proposal in a minute', 'Watch this video before choosing how to explore your proposal.'],
  executive: ['Executive view', 'The essentials for your decision: project scope, investment and timeline.'],
  detailed: ['Full proposal', 'Explore the context, solution, requirements and work process.'],
  technical: ['Technical details', 'Review your project’s architecture, technologies and technical requirements.'],
  legal: ['Contract and terms', 'Review the draft contract and service terms.'],
  modules: ['Additional modules', 'Discover ways to expand your project. The full catalog opens in another tab.'],
  alliance: ['Partnership program', 'Explore how we can work together through our partnership program. Opens in another tab.'],
  restart: ['Restart guide', 'You can repeat this walkthrough whenever you need it.'],
  skip: 'Skip', back: 'Back', next: 'Next', done: 'Got it',
}
const t = computed(() => props.language === 'en' ? en : es)
const steps = computed(() => [
  ['[data-testid="proposal-explainer-card"]', 'video'],
  ['[data-testid="gateway-executive-card"]', 'executive'],
  ['[data-testid="gateway-detailed-card"]', 'detailed'],
  ['[data-testid="gateway-technical-card"]', 'technical'],
  ['[data-testid="gateway-legal-card"]', 'legal'],
  ['[data-testid="gateway-modules-link"]', 'modules'],
  ['[data-testid="gateway-alliance-link"]', 'alliance'],
  ['[data-testid="gateway-restart-guide"]', 'restart'],
].map(([target, key]) => ({ target, title: t.value[key][0], description: t.value[key][1], prefer: key === 'modules' || key === 'alliance' ? 'left' : 'bottom' })))
onMounted(async () => { await nextTick(); tour.value?.start() })
</script>

<template>
  <nav :aria-label="language === 'en' ? 'Explore more' : 'Explora más'" class="fixed bottom-[4.75rem] right-4 z-40 flex flex-col gap-3">
    <BaseButton as="a" unstyled icon-only :to="`${localePath}/additional-modules`" target="_blank" rel="noopener noreferrer" data-testid="gateway-modules-link" :aria-label="t.modules[0]" :title="t.modules[0]" class="flex h-12 w-12 items-center justify-center rounded-full border border-border-default bg-surface text-text-brand shadow-raised transition-colors hover:bg-surface-muted">
      <SquaresPlusIcon class="h-6 w-6" aria-hidden="true" />
    </BaseButton>
    <BaseButton as="a" unstyled icon-only :to="`${localePath}/partnership-program`" target="_blank" rel="noopener noreferrer" data-testid="gateway-alliance-link" :aria-label="t.alliance[0]" :title="t.alliance[0]" class="flex h-12 w-12 items-center justify-center rounded-full border border-border-default bg-surface text-text-brand shadow-raised transition-colors hover:bg-surface-muted">
      <UserGroupIcon class="h-6 w-6" aria-hidden="true" />
    </BaseButton>
  </nav>
  <BaseButton unstyled icon-only data-testid="gateway-restart-guide" :aria-label="t.restart[0]" :title="t.restart[0]" class="fixed bottom-4 left-4 z-40 flex h-11 w-11 items-center justify-center rounded-full border border-border-default bg-surface text-text-brand shadow-raised hover:bg-surface-muted sm:bottom-6 sm:left-6" @click="tour?.forceStart()">
    <QuestionMarkCircleIcon class="h-5 w-5" aria-hidden="true" />
  </BaseButton>
  <PublicGuidedTour ref="tour" :steps="steps" :labels="t" storage-key="projectapp-proposal-gateway-guide-v1" test-id-prefix="gateway-guide" :is-dark="isDark" />
</template>
