<template>
  <section class="min-h-screen bg-surface px-4 py-12 sm:px-8 sm:py-16">
    <div class="mx-auto w-full max-w-5xl">
      <div class="mb-8">
        <BaseBadge variant="warning" class="mb-4">
          {{ copy.draftLabel }}
        </BaseBadge>
        <h1 class="mb-4 text-3xl font-light leading-tight text-text-brand sm:text-5xl">
          {{ copy.title }}
        </h1>
        <BaseRichTextContent
          data-testid="contract-terms-description"
          class="text-base font-light leading-relaxed text-text-muted sm:text-lg"
         :source="copy.description" :format="copy.text_formats?.['/description'] || 'plain'" />
      </div>

      <BaseAlert variant="warning" :title="copy.noticeTitle" class="mb-10">
        {{ copy.notice }}
      </BaseAlert>

      <div v-if="loading" class="space-y-4" aria-live="polite">
        <p class="text-sm text-text-muted">{{ copy.loading }}</p>
        <div v-for="index in 6" :key="index" class="h-14 animate-pulse rounded-xl bg-surface-raised" />
      </div>

      <div v-else-if="error" class="rounded-2xl border border-danger-strong/30 bg-danger-soft p-6">
        <h2 class="mb-2 text-lg font-semibold text-danger-strong">{{ copy.errorTitle }}</h2>
        <p class="mb-5 text-sm text-danger-strong">{{ copy.error }}</p>
        <BaseButton variant="secondary" data-testid="contract-terms-retry" @click="$emit('retry')">
          {{ copy.retry }}
        </BaseButton>
      </div>

      <div v-else-if="clauses.length">
        <div class="mb-5 flex items-end justify-between gap-4">
          <div>
            <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-warning-strong">
              {{ copy.indexEyebrow }}
            </p>
            <h2 class="text-2xl font-semibold text-text-brand sm:text-3xl">{{ copy.indexTitle }}</h2>
          </div>
          <span class="text-sm text-text-muted">{{ copy.clauseCount(clauses.length) }}</span>
        </div>

        <nav
          :aria-label="copy.indexTitle"
          data-testid="contract-terms-index"
          class="grid gap-3 md:grid-cols-2"
        >
          <button
            v-for="clause in clauses"
            :key="clause.id"
            type="button"
            class="group flex items-start gap-4 rounded-xl border border-border-default bg-surface-raised p-4 text-left transition-colors hover:border-warning-strong focus:outline-none focus:ring-2 focus:ring-focus-ring/40"
            :data-testid="`contract-clause-link-${clause.id}`"
            @click="$emit('navigate', clause.id)"
          >
            <span class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-warning-soft text-xs font-bold text-warning-strong">
              {{ clause.number }}
            </span>
            <span class="pt-1 text-sm font-medium leading-snug text-text-default group-hover:text-text-brand">
              {{ clause.title }}
            </span>
          </button>
        </nav>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  terms: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  language: { type: String, default: 'es' },
});

defineEmits(['navigate', 'retry']);

const translations = {
  es: {
    draftLabel: 'Borrador informativo',
    title: 'Contrato y condiciones',
    description: 'Revisa de forma transparente el borrador del contrato de prestación de servicios que acompañaría la ejecución del proyecto. Aquí encontrarás el alcance, entregables, pagos, garantías, responsabilidades, propiedad intelectual, tratamiento de datos, terminación, soporte y hosting.',
    noticeTitle: 'Documento para revisión',
    notice: 'Este borrador no contiene firmas ni datos reales. Refleja la plantilla global vigente y puede actualizarse antes de la formalización definitiva.',
    loading: 'Preparando el borrador del contrato…',
    errorTitle: 'No pudimos cargar el borrador',
    error: 'El contenido no está disponible temporalmente. Puedes intentarlo de nuevo.',
    retry: 'Reintentar',
    indexEyebrow: 'Contenido del contrato',
    indexTitle: 'Índice de cláusulas',
    clauseCount: count => `${count} cláusulas`,
  },
  en: {
    draftLabel: 'Informational draft',
    title: 'Contract and terms',
    description: 'Review the current draft service agreement and its main conditions.',
    noticeTitle: 'Document for review',
    notice: 'This draft has no signatures or real personal data and may change before execution.',
    loading: 'Preparing the contract draft…',
    errorTitle: 'We could not load the draft',
    error: 'The content is temporarily unavailable. Please try again.',
    retry: 'Try again',
    indexEyebrow: 'Contract contents',
    indexTitle: 'Clause index',
    clauseCount: count => `${count} clauses`,
  },
};

const copy = computed(() => translations[props.language] || translations.es);
const clauses = computed(() => props.terms?.clauses || []);
</script>
