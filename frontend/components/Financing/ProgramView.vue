<script setup>
import PublicDocumentAction from '~/components/PublicDocumentAction.vue'
import PublicDocumentShareButton from '~/components/PublicDocumentShareButton.vue'
import { computed, nextTick, ref, toRef, watch } from 'vue'

import ExplainerVideoCard from '~/components/ExplainerVideoCard.vue'
import FinancingOnboarding from '~/components/Financing/Onboarding.vue'
import { useExplainerVideo } from '~/composables/useExplainerVideos'
import { useFinancingTheme } from '~/composables/useFinancingTheme'
import { usePublicDocumentEntrance } from '~/composables/usePublicDocumentEntrance'

const props = defineProps({
  program: { type: Object, required: true },
  downloadUrl: { type: String, default: '' },
  language: { type: String, default: 'es' },
  floatingActions: { type: Boolean, default: true },
  /** The panel preview renders the explainer card separately; it disables this one. */
  showExplainer: { type: Boolean, default: true },
})

const emit = defineEmits(['change-language'])
const { t } = useI18n()
const { isDark, toggle: toggleTheme } = useFinancingTheme()
const documentRef = ref(null)
usePublicDocumentEntrance(documentRef)
const explainer = useExplainerVideo('financing', toRef(props, 'language'), computed(() => props.program?.explainer_video))
// The panel switch arrives in the public payload; a missing flag counts as visible.
const explainerVisible = computed(() => (
  props.showExplainer
  && props.program?.show_explainer_video !== false
  && Boolean(explainer.value)
))
const onboardingRef = ref(null)
const guideStarted = ref(false)

// The guided tour only lives on the public view (floatingActions); the panel
// preview reuses this component without it.
watch([() => props.program, onboardingRef], async ([program, onboarding]) => {
  if (!program || !onboarding || !props.floatingActions || guideStarted.value) return
  guideStarted.value = true
  await nextTick()
  onboarding.start()
}, { immediate: true, flush: 'post' })
const expandedTerms = ref(new Set())
const isDownloading = ref(false)
const downloadError = ref(false)

const conditions = computed(() => props.program?.conditions || [])
const options = computed(() => props.program?.options || [])
const terms = computed(() => props.program?.legal_terms || [])

function toggleTerm(termId) {
  const next = new Set(expandedTerms.value)
  if (next.has(termId)) next.delete(termId)
  else next.add(termId)
  expandedTerms.value = next
}

function responseFilename(response) {
  const disposition = response.headers.get('content-disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  return match?.[1] || (props.language === 'en' ? 'partnership-program.pdf' : 'programa-de-alianza.pdf')
}

async function downloadPdf() {
  if (!props.downloadUrl || isDownloading.value) return
  isDownloading.value = true
  downloadError.value = false
  try {
    const response = await fetch(props.downloadUrl, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(`PDF request failed: ${response.status}`)
    const objectUrl = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = responseFilename(response)
    link.click()
    URL.revokeObjectURL(objectUrl)
  } catch {
    downloadError.value = true
  } finally {
    isDownloading.value = false
  }
}
</script>

<template>
  <article
    ref="documentRef"
    class="public-document-theme public-document-canvas min-h-screen w-full text-text-default"
    :class="{ 'public-document-view': floatingActions }"
    :data-theme="isDark ? 'dark' : 'light'"
    data-testid="financing-program"
  >
    <header data-document-enter class="relative overflow-hidden px-4 pb-14 pt-12 sm:px-6 sm:pb-20 sm:pt-16">
      <div class="public-document-hero-glow pointer-events-none absolute inset-0 opacity-70" aria-hidden="true">
        <div class="absolute -right-24 -top-24 h-80 w-80 rounded-full bg-primary-soft blur-3xl" />
        <div class="absolute -bottom-32 -left-20 h-80 w-80 rounded-full bg-accent-soft blur-3xl" />
      </div>

      <div class="relative mx-auto max-w-[1200px]">
        <div class="mb-12 flex flex-wrap items-center justify-between gap-3">
          <p class="text-sm font-medium uppercase tracking-[0.18em] text-text-brand">Project App.</p>
          <div class="flex flex-wrap items-center gap-2">
            <BaseSegmented
              :model-value="language"
              :options="[
                { value: 'es', label: t('financing.spanish'), testId: 'financing-language-es' },
                { value: 'en', label: t('financing.english'), testId: 'financing-language-en' },
              ]"
              data-testid="financing-language"
              @update:model-value="emit('change-language', $event)"
            />
            <BaseButton
              v-if="!floatingActions"
              variant="secondary"
              icon-only
              :aria-label="t('financing.toggleTheme')"
              :aria-pressed="isDark"
              data-testid="financing-theme-toggle"
              @click="toggleTheme"
            >
              <span aria-hidden="true">{{ isDark ? '☀️' : '🌙' }}</span>
            </BaseButton>
          </div>
        </div>

        <div class="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-end">
          <div>
            <p class="text-sm font-medium uppercase tracking-[0.18em] text-text-brand">
              {{ program.hero.eyebrow }}
            </p>
            <h1 class="mt-4 max-w-4xl text-balance text-4xl font-light tracking-tight text-text-brand sm:text-6xl lg:text-7xl">
              {{ program.hero.title }}
            </h1>
            <p class="mt-6 max-w-3xl text-base leading-8 text-text-muted sm:text-lg">
              {{ program.hero.subtitle }}
            </p>
            <ExplainerVideoCard
              v-if="explainerVisible"
              :video="explainer"
              i18n-namespace="financing"
              variant="hero"
              test-id="financing-explainer"
              class="financing-explainer mt-8 max-w-3xl"
            />
            <div class="mt-8 flex flex-wrap gap-3">
              <BaseButton
                as="a"
                :to="program.cta.whatsapp_url"
                target="_blank"
                rel="noopener noreferrer"
                size="lg"
                data-testid="financing-whatsapp-hero"
              >
                {{ program.cta.button }}
              </BaseButton>
              <BaseButton
                v-if="downloadUrl"
                variant="secondary"
                size="lg"
                :loading="isDownloading"
                data-testid="financing-download-pdf"
                @click="downloadPdf"
              >
                {{ t('financing.downloadPdf') }}
              </BaseButton>
            </div>
            <BaseAlert v-if="downloadError" class="mt-4 max-w-xl" variant="danger">
              {{ t('financing.pdfError') }}
            </BaseAlert>
          </div>

          <aside class="rounded-3xl border border-border-default bg-surface/90 p-6 shadow-raised backdrop-blur">
            <BaseBadge variant="success">{{ program.eligibility.badge }}</BaseBadge>
            <h2 class="mt-4 text-xl font-medium text-text-brand">{{ program.eligibility.title }}</h2>
            <p class="mt-3 text-sm leading-7 text-text-muted">{{ program.eligibility.summary }}</p>
          </aside>
        </div>

        <p class="mt-12 max-w-4xl border-l-2 border-primary pl-5 text-base italic leading-7 text-text-subtle">
          {{ program.hero.trust_note }}
        </p>
      </div>
    </header>

    <main class="mx-auto w-full max-w-[1200px] px-4 py-14 sm:px-6 sm:py-20">
      <section data-document-enter aria-labelledby="financing-options-title">
        <div class="max-w-3xl">
          <h2 id="financing-options-title" class="text-3xl font-light text-text-brand sm:text-4xl">
            {{ t('financing.optionsTitle') }}
          </h2>
          <p class="mt-4 text-base leading-7 text-text-muted">{{ t('financing.optionsIntro') }}</p>
        </div>

        <div class="mt-8 grid gap-5 lg:grid-cols-2">
          <article
            v-for="option in options"
            :key="option.id"
            class="relative overflow-hidden rounded-3xl border bg-surface p-6 shadow-card sm:p-8"
            :class="option.recommended ? 'border-text-brand' : 'border-border-default'"
            :data-testid="`financing-option-${option.id}`"
          >
            <div class="flex flex-wrap items-center justify-between gap-3">
              <BaseBadge :variant="option.recommended ? 'success' : 'neutral'">{{ option.badge }}</BaseBadge>
              <span class="text-sm font-medium text-text-brand">
                {{ t('financing.years', { count: option.exclusivity_years }) }}
              </span>
            </div>
            <h3 class="mt-5 text-2xl font-medium text-text-brand">{{ option.name }}</h3>
            <p class="mt-3 text-sm leading-7 text-text-muted">{{ option.summary }}</p>
            <ul class="mt-6 space-y-3">
              <li v-for="highlight in option.highlights" :key="highlight" class="flex gap-3 text-sm leading-6 text-text-subtle">
                <span class="mt-1 text-text-brand" aria-hidden="true">✓</span>
                <span>{{ highlight }}</span>
              </li>
            </ul>
            <div class="mt-6 rounded-2xl bg-surface-muted p-4 text-sm font-medium text-text-brand">
              {{ option.hour_package_included ? t('financing.packageIncluded') : t('financing.packageNotIncluded') }}
            </div>
          </article>
        </div>
      </section>

      <section data-document-enter class="pt-20" aria-labelledby="financing-conditions-title">
        <div class="max-w-3xl">
          <h2 id="financing-conditions-title" class="text-3xl font-light text-text-brand sm:text-4xl">
            {{ t('financing.conditionsTitle') }}
          </h2>
          <p class="mt-4 text-base leading-7 text-text-muted">{{ t('financing.conditionsIntro') }}</p>
        </div>

        <nav class="financing-conditions-nav mt-7 flex gap-2 overflow-x-auto pb-2 sm:flex-wrap" :aria-label="t('financing.conditionsTitle')">
          <a
            v-for="condition in conditions"
            :key="condition.id"
            :href="`#financing-${condition.id}`"
            class="min-h-11 shrink-0 rounded-full border border-border-default bg-surface px-4 py-2.5 text-sm font-medium text-text-default transition-colors hover:border-primary focus:outline-none focus:ring-2 focus:ring-focus-ring/40"
          >
            {{ condition.number }} · {{ condition.title }}
          </a>
        </nav>

        <div class="mt-8 grid gap-5 lg:grid-cols-2">
          <article
            v-for="condition in conditions"
            :id="`financing-${condition.id}`"
            :key="condition.id"
            class="scroll-mt-24 rounded-3xl border border-border-default bg-surface p-6 shadow-card sm:p-8"
            :data-testid="`financing-condition-${condition.id}`"
          >
            <div class="flex items-start justify-between gap-4">
              <span class="text-sm font-medium tracking-[0.18em] text-text-brand">{{ condition.number }}</span>
              <span class="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-soft text-xl text-text-brand" aria-hidden="true">
                {{ condition.icon }}
              </span>
            </div>
            <h3 class="mt-5 text-2xl font-medium text-text-brand">{{ condition.title }}</h3>
            <p class="mt-3 text-sm leading-7 text-text-muted">{{ condition.summary }}</p>
            <div class="mt-6 rounded-2xl bg-surface-muted p-5">
              <h4 class="text-sm font-medium uppercase tracking-[0.12em] text-text-brand">{{ t('financing.whyItWorks') }}</h4>
              <p class="mt-3 text-sm leading-7 text-text-subtle">{{ condition.commercial_reason }}</p>
            </div>
            <ul class="mt-6 space-y-3">
              <li v-for="highlight in condition.highlights" :key="highlight" class="flex gap-3 text-sm leading-6 text-text-subtle">
                <span class="mt-1 text-text-brand" aria-hidden="true">•</span>
                <span>{{ highlight }}</span>
              </li>
            </ul>
          </article>
        </div>
      </section>

      <section data-document-enter class="pt-20" aria-labelledby="financing-calculator-title">
        <div class="rounded-3xl border border-border-default bg-surface-raised p-6 shadow-card sm:p-10">
          <p class="text-sm font-medium uppercase tracking-[0.18em] text-text-brand">{{ program.calculator.eyebrow }}</p>
          <h2 id="financing-calculator-title" class="mt-4 max-w-4xl text-3xl font-light text-text-brand sm:text-4xl">
            {{ program.calculator.title }}
          </h2>
          <p class="mt-4 max-w-4xl text-base leading-7 text-text-muted">{{ program.calculator.summary }}</p>

          <div class="mt-8 grid gap-5 lg:grid-cols-2" data-testid="financing-calculator-input-output">
            <article
              v-for="part in [program.calculator.input, program.calculator.output]"
              :key="part.title"
              class="rounded-2xl border border-border-default bg-surface p-6"
            >
              <h3 class="text-xl font-medium text-text-brand">{{ part.title }}</h3>
              <ul class="mt-5 space-y-3">
                <li v-for="item in part.items" :key="item" class="flex gap-3 text-sm leading-7 text-text-subtle">
                  <span class="text-text-brand" aria-hidden="true">→</span>
                  <span>{{ item }}</span>
                </li>
              </ul>
            </article>
          </div>
          <p class="mt-5 text-sm leading-6 text-text-muted">{{ program.calculator.disclaimer }}</p>
        </div>
      </section>

      <section data-document-enter class="pt-20" aria-labelledby="financing-package-title">
        <div class="grid gap-7 rounded-3xl border border-primary bg-primary-soft p-6 sm:p-10 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-center">
          <div>
            <BaseBadge variant="success">{{ program.package.included_label }}</BaseBadge>
            <h2 id="financing-package-title" class="mt-5 text-3xl font-light text-text-brand sm:text-4xl">
              {{ program.package.name }} · {{ program.package.hours }} h
            </h2>
            <p class="mt-4 text-base leading-7 text-text-subtle">{{ program.package.summary }}</p>
          </div>
          <dl class="grid gap-3" data-testid="financing-package-facts">
            <div class="rounded-2xl border border-border-default bg-surface p-4">
              <dt class="text-xs uppercase tracking-[0.12em] text-text-muted">{{ t('financing.packageFacts') }}</dt>
              <dd class="mt-2 font-medium text-text-brand">{{ program.package.renewal_label }}</dd>
            </div>
            <div class="rounded-2xl border border-border-default bg-surface p-4">
              <dt class="text-xs uppercase tracking-[0.12em] text-text-muted">{{ program.package.rollover_label }}</dt>
              <dd class="mt-2 font-medium text-text-brand">{{ program.package.availability_label }}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section data-document-enter class="pt-20" aria-labelledby="financing-terms-title">
        <div class="max-w-3xl">
          <h2 id="financing-terms-title" class="text-3xl font-light text-text-brand sm:text-4xl">
            {{ t('financing.termsTitle') }}
          </h2>
          <p class="mt-4 text-base leading-7 text-text-muted">{{ t('financing.termsIntro') }}</p>
        </div>

        <div class="financing-terms mt-8 space-y-3">
          <article
            v-for="term in terms"
            :key="term.id"
            class="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card"
            :data-testid="`financing-term-${term.id}`"
          >
            <BaseButton
              unstyled
              type="button"
              class="flex min-h-16 w-full items-center gap-4 p-5 text-left transition-colors hover:bg-surface-raised"
              :aria-expanded="expandedTerms.has(term.id)"
              :aria-controls="`financing-term-panel-${term.id}`"
              :aria-label="t(expandedTerms.has(term.id) ? 'financing.collapseTerm' : 'financing.expandTerm', { title: term.title })"
              :data-testid="`financing-term-trigger-${term.id}`"
              @click="toggleTerm(term.id)"
            >
              <span class="min-w-0 flex-1">
                <span class="block text-lg font-medium text-text-brand">{{ term.title }}</span>
                <span class="mt-1 block text-sm leading-6 text-text-muted">{{ term.summary }}</span>
              </span>
              <span class="shrink-0 text-xl text-text-brand" aria-hidden="true">{{ expandedTerms.has(term.id) ? '−' : '+' }}</span>
            </BaseButton>
            <div
              v-show="expandedTerms.has(term.id)"
              :id="`financing-term-panel-${term.id}`"
              class="border-t border-border-default bg-surface-raised p-5 sm:px-7"
            >
              <ul class="space-y-3">
                <li v-for="item in term.items" :key="item" class="flex gap-3 text-sm leading-7 text-text-subtle">
                  <span class="text-text-brand" aria-hidden="true">•</span>
                  <span>{{ item }}</span>
                </li>
              </ul>
            </div>
          </article>
        </div>
      </section>

      <section data-document-enter class="pt-20">
        <div class="rounded-3xl bg-primary p-7 text-on-primary sm:p-12">
          <p class="text-sm font-medium uppercase tracking-[0.18em] opacity-80">{{ program.cta.eyebrow }}</p>
          <h2 class="mt-4 max-w-3xl text-3xl font-light sm:text-5xl">{{ program.cta.title }}</h2>
          <p class="mt-5 max-w-3xl text-base leading-7 opacity-85">{{ program.cta.body }}</p>
          <BaseButton
            as="a"
            :to="program.cta.whatsapp_url"
            target="_blank"
            rel="noopener noreferrer"
            variant="accent"
            size="lg"
            class="mt-7"
            data-testid="financing-whatsapp-cta"
          >
            {{ program.cta.button }}
          </BaseButton>
        </div>
        <p class="mx-auto mt-6 max-w-4xl text-center text-xs leading-5 text-text-muted">{{ program.disclaimer }}</p>
      </section>
    </main>

    <template v-if="floatingActions">
      <PublicDocumentAction
        v-if="downloadUrl"
        action="pdf"
        :loading="isDownloading"
        :label="isDownloading ? t('financing.generatingPdf') : t('financing.downloadPdf')"
        data-testid="financing-download-pdf-floating"
        @click="downloadPdf"
      />
      <PublicDocumentShareButton
        :is-dark="isDark"
        namespace="financing"
        test-id-prefix="financing"
        trigger-test-id="financing-share"
        trigger-class="financing-share-btn share-btn"
      />
      <PublicDocumentAction
        action="guide"
        class="financing-restart-guide restart-tutorial-btn"
        :label="t('financing.restartGuide')"
        data-testid="financing-guide-restart"
        @click="onboardingRef?.forceStart()"
      />
      <PublicDocumentAction
        action="theme"
        class="financing-theme-toggle dark-mode-toggle"
        :label="t('financing.toggleTheme')"
        :is-dark="isDark"
        data-testid="financing-theme-toggle"
        @click="toggleTheme"
      />
      <FinancingOnboarding ref="onboardingRef" :is-dark="isDark" />
    </template>
  </article>
</template>
