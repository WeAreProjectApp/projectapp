<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseSegmented from '~/components/base/BaseSegmented.vue'
import PublicDocumentAction from '~/components/PublicDocumentAction.vue'
import PublicDocumentShareButton from '~/components/PublicDocumentShareButton.vue'
import Onboarding from '~/components/BuildingOnDemand/Onboarding.vue'
import TierCard from '~/components/BuildingOnDemand/TierCard.vue'
import TermSelector from '~/components/BuildingOnDemand/TermSelector.vue'
import BagEstimator from '~/components/BuildingOnDemand/BagEstimator.vue'
import { useBuildingOnDemandTheme } from '~/composables/useBuildingOnDemandTheme'
import { usePublicDocumentEntrance } from '~/composables/usePublicDocumentEntrance'
import { isBuildingOnDemandProgram } from '~/utils/buildingOnDemand'
import { listOf, safeWhatsappUrl } from '~/utils/buildingWithUs'

const props = defineProps({
  program: { type: Object, required: true },
  downloadUrl: { type: String, default: '' },
  language: { type: String, default: 'es' },
  floatingActions: { type: Boolean, default: true },
})
const emit = defineEmits(['change-language'])
const { t } = useI18n()
const { isDark, toggle: toggleTheme } = useBuildingOnDemandTheme()
const documentRef = ref(null)
usePublicDocumentEntrance(documentRef)
const onboardingRef = ref(null)
const guideStarted = ref(false)
const expandedFaq = ref(new Set())
const selectedTerm = ref('monthly')
const isDownloading = ref(false)
const downloadError = ref(false)
const tiers = computed(() => listOf(props.program.tiers?.items))
const term = computed(() => listOf(props.program.terms?.items).find((item) => item.id === selectedTerm.value)
  || listOf(props.program.terms?.items)[0] || { id: 'monthly', months: 1 })
const label = (key, params = {}) => t(`buildingOnDemand.${key}`, params, {
  locale: props.language === 'en' ? 'en-us' : 'es-co',
})

watch(() => props.program.terms, (terms) => {
  if (!listOf(terms?.items).some((item) => item.id === selectedTerm.value)) selectedTerm.value = 'monthly'
})

// A panel preview has no floating controls or automatic tour.
watch([() => props.program, onboardingRef], async ([program, onboarding]) => {
  if (!isBuildingOnDemandProgram(program) || !onboarding || !props.floatingActions || guideStarted.value) return
  guideStarted.value = true
  await nextTick()
  onboarding.start()
}, { immediate: true, flush: 'post' })

function toggleFaq(id) {
  const next = new Set(expandedFaq.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedFaq.value = next
}

function responseFilename(response) {
  const fallback = `building-on-demand-${props.language}.pdf`
  const disposition = response.headers.get('content-disposition') || ''
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim())
    } catch {
      // A malformed encoded name can still have a usable plain filename.
    }
  }
  return disposition.match(/filename="?([^";]+)"?/i)?.[1]?.trim() || fallback
}

async function downloadPdf() {
  if (!props.downloadUrl || isDownloading.value) return
  isDownloading.value = true
  downloadError.value = false
  let objectUrl
  try {
    const response = await fetch(props.downloadUrl, { credentials: 'same-origin' })
    if (!response.ok) throw new Error(`PDF request failed: ${response.status}`)
    objectUrl = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = responseFilename(response)
    document.body.appendChild(link)
    try {
      link.click()
    } finally {
      link.remove()
    }
  } catch {
    downloadError.value = true
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl)
    isDownloading.value = false
  }
}
</script>

<template>
  <article
    ref="documentRef"
    class="public-document-theme public-document-canvas min-h-screen w-full break-words text-text-default [overflow-wrap:anywhere]"
    :class="{ 'public-document-view': floatingActions }"
    :data-theme="isDark ? 'dark' : 'light'"
    data-testid="building-on-demand-program"
  >
    <header data-document-enter class="relative overflow-hidden px-4 pb-14 pt-12 sm:px-6 sm:pb-20 sm:pt-16" data-testid="building-on-demand-hero">
      <div class="public-document-hero-glow pointer-events-none absolute inset-0 opacity-70" aria-hidden="true">
        <div class="absolute -right-24 -top-24 h-80 w-80 rounded-full bg-primary-soft blur-3xl" />
        <div class="absolute -bottom-32 -left-20 h-80 w-80 rounded-full bg-accent-soft blur-3xl" />
      </div>
      <div class="relative mx-auto max-w-[1200px]">
        <div class="mb-12 flex flex-wrap items-center justify-between gap-3">
          <p class="text-sm font-medium uppercase tracking-[0.18em] text-text-brand">Project App.</p>
          <div class="flex min-w-0 flex-wrap items-center gap-2">
            <BaseSegmented
              :model-value="language"
              :options="[
                { value: 'es', label: label('spanish'), testId: 'building-on-demand-language-es' },
                { value: 'en', label: label('english'), testId: 'building-on-demand-language-en' },
              ]"
              data-testid="building-on-demand-language"
              @update:model-value="emit('change-language', $event)"
            />
            <BaseButton v-if="!floatingActions" variant="secondary" icon-only :aria-label="label('toggleTheme')" :aria-pressed="isDark" data-testid="building-on-demand-theme-toggle" @click="toggleTheme">
              <span aria-hidden="true">{{ isDark ? '☀️' : '🌙' }}</span>
            </BaseButton>
          </div>
        </div>
        <div v-if="program.hero?.title" class="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-end">
          <div class="min-w-0">
            <p v-if="program.hero.eyebrow" class="text-sm font-medium uppercase tracking-[0.18em] text-text-brand">{{ program.hero.eyebrow }}</p>
            <h1 class="mt-4 max-w-4xl text-balance text-3xl font-light tracking-tight text-text-brand sm:text-5xl lg:text-6xl">{{ program.hero.title }}</h1>
            <p v-if="program.hero.subtitle" class="mt-6 max-w-3xl text-base leading-8 text-text-muted sm:text-lg">{{ program.hero.subtitle }}</p>
            <blockquote v-if="program.hero.positioning" class="mt-6 max-w-3xl rounded-2xl border-l-4 border-primary bg-primary-soft p-5 text-base font-medium leading-7 text-text-brand" data-testid="building-on-demand-positioning">{{ program.hero.positioning }}</blockquote>
            <div class="mt-8 flex flex-wrap gap-3">
              <BaseButton as="a" to="#tiers" size="lg" data-testid="building-on-demand-view-tiers">{{ label('viewTiers') }}</BaseButton>
              <BaseButton as="a" to="#estimator" variant="secondary" size="lg" v-bind="{ textPolicy: 'wrap' }" data-testid="building-on-demand-view-estimator">{{ program.estimator?.title }}</BaseButton>
            </div>
          </div>
          <aside v-if="program.hero.note" class="min-w-0 rounded-3xl border border-border-default bg-surface/90 p-6 shadow-raised backdrop-blur" data-testid="building-on-demand-hero-aside">
            <BaseBadge variant="success">{{ label('title') }}</BaseBadge>
            <h2 class="mt-4 text-xl font-medium text-text-brand">{{ label('tagline') }}</h2>
            <p class="mt-3 text-sm leading-7 text-text-muted">{{ program.hero.note }}</p>
          </aside>
        </div>
        <BaseAlert v-if="downloadError" class="mt-4 max-w-xl" variant="danger" data-testid="building-on-demand-pdf-error">{{ label('pdfError') }}</BaseAlert>
      </div>
    </header>

    <main class="mx-auto w-full max-w-[1200px] space-y-20 px-4 py-14 sm:px-6 sm:py-20">
      <section v-if="program.cell" data-document-enter aria-labelledby="building-on-demand-cell-title" data-testid="building-on-demand-cell">
        <h2 id="building-on-demand-cell-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.cell.title }}</h2>
        <p class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.cell.summary }}</p>
        <ul class="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          <li v-for="role in listOf(program.cell.roles)" :key="role.id" class="min-w-0 rounded-3xl border border-border-default bg-surface p-6 shadow-card" :data-testid="`building-on-demand-role-${role.id}`">
            <h3 class="text-xl font-medium text-text-brand">{{ role.title }}</h3>
            <p class="mt-3 text-sm leading-7 text-text-muted">{{ role.summary }}</p>
          </li>
        </ul>
        <p v-if="program.cell.note" class="mt-6 max-w-3xl rounded-2xl bg-primary-soft p-5 text-sm leading-7 text-text-subtle">{{ program.cell.note }}</p>
      </section>

      <section v-if="program.fit" data-document-enter aria-labelledby="building-on-demand-fit-title" data-testid="building-on-demand-fit">
        <h2 id="building-on-demand-fit-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.fit.title }}</h2>
        <p class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.fit.summary }}</p>
        <div class="mt-8 grid gap-5 md:grid-cols-2">
          <div class="min-w-0 rounded-3xl border border-border-default bg-surface p-6 shadow-card" data-testid="building-on-demand-good-for">
            <h3 class="text-xl font-medium text-success-strong">{{ label('goodFor') }}</h3>
            <ul class="mt-5 space-y-5">
              <li v-for="item in listOf(program.fit.good_for)" :key="item.id" class="flex gap-3">
                <span aria-hidden="true" class="text-success-strong">✓</span>
                <div class="min-w-0"><h4 class="font-medium text-text-brand">{{ item.title }}</h4><p class="mt-2 text-sm leading-7 text-text-muted">{{ item.summary }}</p></div>
              </li>
            </ul>
          </div>
          <div class="min-w-0 rounded-3xl border border-border-default bg-surface p-6 shadow-card" data-testid="building-on-demand-not-for">
            <h3 class="text-xl font-medium text-danger-strong">{{ label('notFor') }}</h3>
            <ul class="mt-5 space-y-5">
              <li v-for="item in listOf(program.fit.not_for)" :key="item.id" class="flex gap-3">
                <span aria-hidden="true" class="text-danger-strong">✕</span>
                <div class="min-w-0"><h4 class="font-medium text-text-brand">{{ item.title }}</h4><p class="mt-2 text-sm leading-7 text-text-muted">{{ item.summary }}</p></div>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <section id="tiers" v-if="program.tiers" data-document-enter class="scroll-mt-12" aria-labelledby="building-on-demand-tiers-title" data-testid="building-on-demand-tiers">
        <h2 id="building-on-demand-tiers-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.tiers.title }}</h2>
        <p class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.tiers.summary }}</p>
        <TermSelector v-if="program.terms" v-model="selectedTerm" :terms="program.terms" class="mt-8" />
        <div class="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          <TierCard v-for="tier in tiers" :key="tier.id" :tier="tier" :term="term" :offer="program.offer" :whatsapp-base-url="program.contact?.whatsapp_base_url" :language="language" />
        </div>
      </section>

      <section v-if="program.bag" data-document-enter aria-labelledby="building-on-demand-bag-title" data-testid="building-on-demand-bag">
        <h2 id="building-on-demand-bag-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.bag.title }}</h2>
        <p class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.bag.summary }}</p>
        <ul class="mt-8 grid gap-5 md:grid-cols-2">
          <li v-for="rule in listOf(program.bag.rules)" :key="rule.id" class="min-w-0 rounded-3xl border border-border-default bg-surface p-6 shadow-card" :data-testid="`building-on-demand-bag-rule-${rule.id}`">
            <h3 class="text-xl font-medium text-text-brand">{{ rule.title }}</h3>
            <p class="mt-3 text-sm leading-7 text-text-muted">{{ rule.summary }}</p>
          </li>
        </ul>
        <p v-if="program.bag.note" class="mt-6 max-w-3xl rounded-2xl bg-primary-soft p-5 text-sm leading-7 text-text-subtle">{{ program.bag.note }}</p>
      </section>

      <BagEstimator v-if="program.estimator" :program="program" :language="language" />

      <section v-if="program.hosting" data-document-enter aria-labelledby="building-on-demand-hosting-title" data-testid="building-on-demand-hosting">
        <h2 id="building-on-demand-hosting-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.hosting.title }}</h2>
        <p class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.hosting.summary }}</p>
        <ul class="mt-8 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          <li v-for="feature in listOf(program.hosting.features)" :key="feature.id" class="min-w-0 rounded-3xl border border-border-default bg-surface p-6 shadow-card" :data-testid="`building-on-demand-hosting-${feature.id}`">
            <h3 class="text-xl font-medium text-text-brand">{{ feature.title }}</h3>
            <p class="mt-3 text-sm leading-7 text-text-muted">{{ feature.summary }}</p>
          </li>
        </ul>
        <p v-if="program.hosting.note" class="mt-6 max-w-3xl rounded-2xl bg-primary-soft p-5 text-sm leading-7 text-text-subtle">{{ program.hosting.note }}</p>
      </section>

      <section v-if="program.faq" data-document-enter aria-labelledby="building-on-demand-faq-title" data-testid="building-on-demand-faq">
        <h2 id="building-on-demand-faq-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.faq.title }}</h2>
        <div class="mt-8 space-y-3">
          <article v-for="item in listOf(program.faq.items)" :key="item.id" class="min-w-0 overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card" :data-testid="`building-on-demand-faq-${item.id}`">
            <BaseButton unstyled type="button" class="flex min-h-16 w-full items-center gap-4 p-5 text-left transition-colors hover:bg-surface-raised" :aria-expanded="expandedFaq.has(item.id)" :aria-controls="`building-on-demand-faq-panel-${item.id}`" :aria-label="label(expandedFaq.has(item.id) ? 'collapseFaq' : 'expandFaq', { question: item.question })" :data-testid="`building-on-demand-faq-trigger-${item.id}`" @click="toggleFaq(item.id)">
              <span class="min-w-0 flex-1 text-lg font-medium text-text-brand">{{ item.question }}</span>
              <span class="shrink-0 text-xl text-text-brand" aria-hidden="true">{{ expandedFaq.has(item.id) ? '−' : '+' }}</span>
            </BaseButton>
            <div v-show="expandedFaq.has(item.id)" :id="`building-on-demand-faq-panel-${item.id}`" class="border-t border-border-default bg-surface-raised p-5 text-sm leading-7 text-text-subtle sm:px-7" :data-testid="`building-on-demand-faq-panel-${item.id}`">{{ item.answer }}</div>
          </article>
        </div>
      </section>

      <section v-if="program.cta" data-document-enter aria-labelledby="building-on-demand-cta-title">
        <div class="rounded-3xl bg-primary p-7 text-on-primary sm:p-12">
          <h2 id="building-on-demand-cta-title" class="max-w-3xl text-3xl font-light sm:text-5xl">{{ program.cta.title }}</h2>
          <p class="mt-5 max-w-3xl text-base leading-7 opacity-85">{{ program.cta.body }}</p>
          <BaseButton as="a" :to="safeWhatsappUrl(program.cta.whatsapp_url)" target="_blank" rel="noopener noreferrer" variant="accent" size="lg" v-bind="{ textPolicy: 'wrap' }" class="mt-7" data-testid="building-on-demand-cta">{{ program.cta.button_label || label('whatsappCta') }}</BaseButton>
        </div>
      </section>
      <p v-if="program.legal?.disclaimer" data-document-enter class="mx-auto max-w-4xl text-center text-sm leading-6 text-text-muted" data-testid="building-on-demand-disclaimer">{{ program.legal.disclaimer }}</p>
    </main>

    <template v-if="floatingActions">
      <PublicDocumentAction v-if="downloadUrl" action="pdf" :loading="isDownloading" :label="isDownloading ? label('generatingPdf') : label('downloadPdf')" data-testid="building-on-demand-download-pdf-floating" @click="downloadPdf" />
      <PublicDocumentShareButton :is-dark="isDark" namespace="buildingOnDemand" test-id-prefix="building-on-demand" trigger-test-id="building-on-demand-share" trigger-class="building-on-demand-share-btn share-btn" />
      <PublicDocumentAction action="guide" class="building-on-demand-restart-guide restart-tutorial-btn" :label="label('restartGuide')" data-testid="building-on-demand-guide-restart" @click="onboardingRef?.forceStart()" />
      <PublicDocumentAction action="theme" class="building-on-demand-theme-toggle dark-mode-toggle" :label="label('toggleTheme')" :is-dark="isDark" data-testid="building-on-demand-theme-toggle" @click="toggleTheme" />
      <Onboarding ref="onboardingRef" :is-dark="isDark" />
    </template>
  </article>
</template>

<style scoped>
:deep([data-testid="building-on-demand-language"] [role="tab"]) {
  min-height: 2.75rem;
}
</style>
