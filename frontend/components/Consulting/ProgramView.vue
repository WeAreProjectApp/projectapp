<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import PublicDocumentAction from '~/components/PublicDocumentAction.vue'
import PublicDocumentShareButton from '~/components/PublicDocumentShareButton.vue'
import ConsultingOnboarding from '~/components/Consulting/Onboarding.vue'
import { useConsultingTheme } from '~/composables/useConsultingTheme'
import { usePublicDocumentEntrance } from '~/composables/usePublicDocumentEntrance'
import { isConsultingProgram, consultingListOf, safeConsultingWhatsappUrl } from '~/utils/consulting'

const props = defineProps({
  program: { type: Object, required: true },
  downloadUrl: { type: String, default: '' },
  language: { type: String, default: 'es' },
  floatingActions: { type: Boolean, default: true },
})
const emit = defineEmits(['change-language'])
const { t } = useI18n()
const { isDark, toggle: toggleTheme } = useConsultingTheme()
const documentRef = ref(null)
usePublicDocumentEntrance(documentRef)
const onboardingRef = ref(null)
const guideStarted = ref(false)
const expandedFaq = ref(new Set())
const isDownloading = ref(false)
const downloadError = ref(false)

const hasSection = (section) => Boolean(section && Object.keys(section).length)
const sectionKeys = ['areas', 'impact', 'measurement', 'deliverable', 'process', 'implementation', 'diagnostic']
const sections = computed(() => sectionKeys.filter((key) => hasSection(props.program[key])))
const implementationLinks = computed(() => ({
  cells: `/${props.language === 'en' ? 'en-us' : 'es-co'}/building-on-demand`,
  'building-with-us': `/${props.language === 'en' ? 'en-us' : 'es-co'}/building-with-us`,
}))

// Start after the public document and its targets have entered the DOM.
// A panel preview has neither floating controls nor a tour instance.
watch([() => props.program, onboardingRef], async ([program, onboarding]) => {
  if (!isConsultingProgram(program) || !onboarding || !props.floatingActions || guideStarted.value) return
  guideStarted.value = true
  await nextTick()
  onboarding.start()
}, { immediate: true, flush: 'post' })

function toggleFaq(index) {
  const next = new Set(expandedFaq.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  expandedFaq.value = next
}

function responseFilename(response) {
  const fallback = `consulting-${props.language}.pdf`
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
    class="public-document-theme public-document-canvas min-h-screen w-full text-text-default"
    :class="{ 'public-document-view': floatingActions }"
    :data-theme="isDark ? 'dark' : 'light'"
    data-testid="consulting-program"
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
                { value: 'es', label: t('consulting.spanish'), testId: 'consulting-language-es' },
                { value: 'en', label: t('consulting.english'), testId: 'consulting-language-en' },
              ]"
              data-testid="consulting-language"
              @update:model-value="emit('change-language', $event)"
            />
            <BaseButton
              v-if="!floatingActions"
              variant="secondary"
              icon-only
              :aria-label="t('consulting.toggleTheme')"
              :aria-pressed="isDark"
              data-testid="consulting-theme-toggle"
              @click="toggleTheme"
            >
              <span aria-hidden="true">{{ isDark ? '☀️' : '🌙' }}</span>
            </BaseButton>
          </div>
        </div>

        <div v-if="program.hero?.title" class="max-w-4xl">
          <p class="text-sm font-medium uppercase tracking-[0.18em] text-text-brand">{{ program.hero.eyebrow }}</p>
          <h1 class="mt-4 text-balance text-4xl font-light tracking-tight text-text-brand sm:text-6xl">{{ program.hero.title }}</h1>
          <p class="mt-6 text-base leading-8 text-text-muted sm:text-lg">{{ program.hero.subtitle }}</p>
          <p class="mt-6 rounded-2xl border border-border-default bg-surface p-5 text-sm leading-7 text-text-muted" data-testid="consulting-hero-aside">{{ program.hero.note }}</p>
          <BaseButton v-if="program.cta" as="a" :to="safeConsultingWhatsappUrl(program.cta.whatsapp_url)" target="_blank" rel="noopener noreferrer" size="lg" class="mt-7" data-testid="consulting-whatsapp-hero">{{ program.cta.button_label }}</BaseButton>
        </div>
      </div>
    </header>

    <BaseAlert v-if="downloadError" variant="danger" class="mx-auto max-w-4xl" data-testid="consulting-pdf-error">{{ t('consulting.pdfError') }}</BaseAlert>
    <main class="mx-auto w-full max-w-[1200px] space-y-20 px-4 py-14 sm:px-6 sm:py-20">
      <section v-for="key in sections" :key="key" data-document-enter :aria-labelledby="`consulting-${key}-title`" :data-testid="`consulting-${key}`">
        <h2 :id="`consulting-${key}-title`" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program[key].title }}</h2>
        <p class="mt-4 max-w-4xl text-base leading-8 text-text-muted">{{ program[key].summary }}</p>
        <div class="mt-8 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          <article v-for="(item, index) in consultingListOf(program[key].items)" :key="item.id" class="min-w-0 rounded-3xl border border-border-default bg-surface p-6 shadow-card" :data-testid="`consulting-${key}-${item.id}`">
            <p class="mb-3 text-sm font-medium text-text-brand" aria-hidden="true">{{ String(index + 1).padStart(2, '0') }}</p>
            <h3 class="text-xl font-medium text-text-brand">{{ item.title }}</h3>
            <p class="mt-3 text-sm leading-7 text-text-muted">{{ item.summary }}</p>
            <BaseButton v-if="key === 'implementation' && implementationLinks[item.id]" as="a" :to="implementationLinks[item.id]" variant="secondary" class="mt-5">{{ t('consulting.learnMore') }}: {{ item.title }}</BaseButton>
          </article>
        </div>
      </section>

      <section v-if="hasSection(program.faq)" data-document-enter aria-labelledby="consulting-faq-title" class="consulting-faq" data-testid="consulting-faq">
        <h2 id="consulting-faq-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.faq.title }}</h2>
        <div class="mt-8 space-y-3">
          <article v-for="(item, index) in consultingListOf(program.faq.items)" :key="item.id" class="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card" :data-testid="`consulting-faq-${index}`">
            <BaseButton
              unstyled
              type="button"
              class="flex min-h-16 w-full items-center gap-4 p-5 text-left transition-colors hover:bg-surface-raised"
              :aria-expanded="expandedFaq.has(index)"
              :aria-controls="`consulting-faq-panel-${index}`"
              :aria-label="t(expandedFaq.has(index) ? 'consulting.collapseFaq' : 'consulting.expandFaq', { question: item.question })"
              :data-testid="`consulting-faq-trigger-${index}`"
              @click="toggleFaq(index)"
            >
              <span class="min-w-0 flex-1 text-lg font-medium text-text-brand">{{ item.question }}</span>
              <span class="shrink-0 text-xl text-text-brand" aria-hidden="true">{{ expandedFaq.has(index) ? '−' : '+' }}</span>
            </BaseButton>
            <div v-show="expandedFaq.has(index)" :id="`consulting-faq-panel-${index}`" class="border-t border-border-default bg-surface-raised p-5 text-sm leading-7 text-text-subtle sm:px-7" :data-testid="`consulting-faq-panel-${index}`">
              {{ item.answer }}
            </div>
          </article>
        </div>
      </section>

      <section v-if="hasSection(program.cta)" data-document-enter>
        <div class="rounded-3xl bg-primary p-7 text-on-primary sm:p-12">
          <h2 v-if="program.cta.title" class="max-w-3xl text-3xl font-light sm:text-5xl">{{ program.cta.title }}</h2>
          <p v-if="program.cta.body" class="mt-5 max-w-3xl text-base leading-7 opacity-85">{{ program.cta.body }}</p>
          <BaseButton as="a" :to="safeConsultingWhatsappUrl(program.cta.whatsapp_url)" target="_blank" rel="noopener noreferrer" variant="accent" size="lg" v-bind="{ textPolicy: 'wrap' }" class="mt-7" data-testid="consulting-whatsapp-cta">
            {{ program.cta.button_label || t('consulting.whatsappCta') }}
          </BaseButton>
        </div>
      </section>
      <p v-if="program.legal?.disclaimer" data-document-enter class="mx-auto max-w-4xl text-center text-xs leading-5 text-text-muted" data-testid="consulting-disclaimer">{{ program.legal.disclaimer }}</p>
    </main>

    <template v-if="floatingActions">
      <PublicDocumentAction v-if="downloadUrl" action="pdf" :loading="isDownloading" :label="isDownloading ? t('consulting.generatingPdf') : t('consulting.downloadPdf')" data-testid="consulting-download-pdf-floating" @click="downloadPdf" />
      <PublicDocumentShareButton :is-dark="isDark" namespace="consulting" test-id-prefix="consulting" trigger-test-id="consulting-share" trigger-class="consulting-share-btn share-btn" />
      <PublicDocumentAction action="guide" class="consulting-restart-guide restart-tutorial-btn" :label="t('consulting.restartGuide')" data-testid="consulting-guide-restart" @click="onboardingRef?.forceStart()" />
      <PublicDocumentAction action="theme" class="consulting-theme-toggle dark-mode-toggle" :label="t('consulting.toggleTheme')" :is-dark="isDark" data-testid="consulting-theme-toggle" @click="toggleTheme" />
      <ConsultingOnboarding ref="onboardingRef" :is-dark="isDark" />
    </template>
  </article>
</template>
