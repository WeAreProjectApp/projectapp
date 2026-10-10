<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import PublicDocumentAction from '~/components/PublicDocumentAction.vue'
import PublicDocumentShareButton from '~/components/PublicDocumentShareButton.vue'
import BuildingWithUsOnboarding from '~/components/BuildingWithUs/Onboarding.vue'
import { useBuildingWithUsTheme } from '~/composables/useBuildingWithUsTheme'
import { usePublicDocumentEntrance } from '~/composables/usePublicDocumentEntrance'
import { isBuildingWithUsProgram, listOf, safeWhatsappUrl } from '~/utils/buildingWithUs'

const props = defineProps({
  program: { type: Object, required: true },
  downloadUrl: { type: String, default: '' },
  language: { type: String, default: 'es' },
  floatingActions: { type: Boolean, default: true },
})
const emit = defineEmits(['change-language'])
const { t } = useI18n()
const { isDark, toggle: toggleTheme } = useBuildingWithUsTheme()
const documentRef = ref(null)
usePublicDocumentEntrance(documentRef)
const onboardingRef = ref(null)
const guideStarted = ref(false)
const expandedFaq = ref(new Set())
const isDownloading = ref(false)
const downloadError = ref(false)

const hasSection = (section) => Boolean(section && Object.keys(section).length)
const roles = computed(() => [
  { id: 'contribution', section: props.program.contribution },
  { id: 'expert', section: props.program.expert_profile },
].filter(({ section }) => hasSection(section)))
const models = computed(() => listOf(props.program.participation_models?.items))

// Start after the public document and its targets have entered the DOM.
// A panel preview has neither floating controls nor a tour instance.
watch([() => props.program, onboardingRef], async ([program, onboarding]) => {
  if (!isBuildingWithUsProgram(program) || !onboarding || !props.floatingActions || guideStarted.value) return
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
  const fallback = `building-with-us-${props.language}.pdf`
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
    data-testid="building-with-us-program"
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
                { value: 'es', label: t('buildingWithUs.spanish'), testId: 'building-with-us-language-es' },
                { value: 'en', label: t('buildingWithUs.english'), testId: 'building-with-us-language-en' },
              ]"
              data-testid="building-with-us-language"
              @update:model-value="emit('change-language', $event)"
            />
            <BaseButton
              v-if="!floatingActions"
              variant="secondary"
              icon-only
              :aria-label="t('buildingWithUs.toggleTheme')"
              :aria-pressed="isDark"
              data-testid="building-with-us-theme-toggle"
              @click="toggleTheme"
            >
              <span aria-hidden="true">{{ isDark ? '☀️' : '🌙' }}</span>
            </BaseButton>
          </div>
        </div>

        <div v-if="program.hero?.title" class="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-end">
          <div class="min-w-0">
            <p v-if="program.hero.eyebrow" class="text-sm font-medium uppercase tracking-[0.18em] text-text-brand">
              {{ program.hero.eyebrow }}
            </p>
            <h1 class="mt-4 max-w-4xl text-balance text-4xl font-light tracking-tight text-text-brand sm:text-6xl lg:text-7xl">
              {{ program.hero.title }}
            </h1>
            <p v-if="program.hero.subtitle" class="mt-6 max-w-3xl text-base leading-8 text-text-muted sm:text-lg">
              {{ program.hero.subtitle }}
            </p>
            <div class="mt-8 flex flex-wrap gap-3">
              <BaseButton
                v-if="program.cta"
                as="a"
                :to="safeWhatsappUrl(program.cta.whatsapp_url)"
                target="_blank"
                rel="noopener noreferrer"
                size="lg"
                data-testid="building-with-us-whatsapp-hero"
              >
                {{ t('buildingWithUs.whatsappCta') }}
              </BaseButton>
              <BaseButton
                v-if="downloadUrl"
                variant="secondary"
                size="lg"
                :loading="isDownloading"
                data-testid="building-with-us-download-pdf"
                @click="downloadPdf"
              >
                {{ isDownloading ? t('buildingWithUs.generatingPdf') : t('buildingWithUs.downloadPdf') }}
              </BaseButton>
            </div>
          </div>
          <aside
            v-if="program.hero.note"
            class="rounded-3xl border border-border-default bg-surface/90 p-6 shadow-raised backdrop-blur"
            data-testid="building-with-us-hero-aside"
          >
            <BaseBadge variant="success">{{ t('buildingWithUs.title') }}</BaseBadge>
            <h2 class="mt-4 text-xl font-medium text-text-brand">{{ t('buildingWithUs.tagline') }}</h2>
            <p class="mt-3 text-sm leading-7 text-text-muted">{{ program.hero.note }}</p>
          </aside>
        </div>
        <BaseAlert v-if="downloadError" class="mt-4 max-w-xl" variant="danger" data-testid="building-with-us-pdf-error">
          {{ t('buildingWithUs.pdfError') }}
        </BaseAlert>
      </div>
    </header>

    <main class="mx-auto w-full max-w-[1200px] space-y-20 px-4 py-14 sm:px-6 sm:py-20">
      <section
        v-if="hasSection(program.origin)"
        data-document-enter
        aria-labelledby="building-with-us-origin-title"
        data-testid="building-with-us-origin"
      >
        <h2 id="building-with-us-origin-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.origin.title }}</h2>
        <p v-if="program.origin.summary" class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.origin.summary }}</p>
        <div v-if="listOf(program.origin.industries).length" class="mt-6 flex flex-wrap gap-2" data-testid="building-with-us-industries" :aria-label="t('buildingWithUs.industriesLabel')">
          <BaseBadge v-for="industry in listOf(program.origin.industries)" :key="industry" variant="neutral">{{ industry }}</BaseBadge>
        </div>
        <ul v-if="listOf(program.origin.points).length" class="mt-6 space-y-3">
          <li v-for="point in listOf(program.origin.points)" :key="point" class="flex gap-3 text-sm leading-7 text-text-subtle">
            <span class="text-text-brand" aria-hidden="true">✓</span><span>{{ point }}</span>
          </li>
        </ul>
      </section>

      <div v-if="roles.length" class="building-with-us-roles grid gap-5 lg:grid-cols-2">
        <section
          v-for="role in roles"
          :key="role.id"
          data-document-enter
          class="min-w-0 rounded-3xl border border-border-default bg-surface p-6 shadow-card sm:p-8"
          :aria-labelledby="`building-with-us-${role.id}-title`"
          :data-testid="`building-with-us-${role.id}`"
        >
          <h2 :id="`building-with-us-${role.id}-title`" class="text-3xl font-light text-text-brand">{{ role.section.title }}</h2>
          <p v-if="role.section.summary" class="mt-4 text-base leading-7 text-text-muted">{{ role.section.summary }}</p>
          <ul class="mt-6 space-y-5">
            <li v-for="item in listOf(role.section.items)" :key="item.id" class="rounded-2xl bg-surface-muted p-5">
              <h3 class="text-lg font-medium text-text-brand">{{ item.title }}</h3>
              <p v-if="item.summary" class="mt-2 text-sm leading-7 text-text-subtle">{{ item.summary }}</p>
            </li>
          </ul>
        </section>
      </div>

      <section v-if="hasSection(program.participation_models)" data-document-enter aria-labelledby="building-with-us-models-title" data-testid="building-with-us-models">
        <h2 id="building-with-us-models-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.participation_models.title }}</h2>
        <p v-if="program.participation_models.summary" class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.participation_models.summary }}</p>
        <nav v-if="models.length" class="building-with-us-models-nav mt-7 flex gap-2 overflow-x-auto pb-2 sm:flex-wrap" :aria-label="t('buildingWithUs.modelsNavLabel')">
          <a
            v-for="model in models"
            :key="model.id"
            :href="`#building-with-us-model-${model.id}`"
            class="min-h-11 shrink-0 rounded-full border border-border-default bg-surface px-4 py-2.5 text-sm font-medium text-text-default transition-colors hover:border-primary focus:outline-none focus:ring-2 focus:ring-focus-ring/40"
          >{{ model.name }}</a>
        </nav>
        <div class="mt-8 grid gap-5 lg:grid-cols-3">
          <article
            v-for="model in models"
            :id="`building-with-us-model-${model.id}`"
            :key="model.id"
            class="min-w-0 scroll-mt-24 rounded-3xl border border-border-default bg-surface p-6 shadow-card"
            :data-testid="`building-with-us-model-${model.id}`"
          >
            <BaseBadge v-if="model.badge" variant="success">{{ model.badge }}</BaseBadge>
            <h3 class="mt-5 text-2xl font-medium text-text-brand">{{ model.name }}</h3>
            <p v-if="model.summary" class="mt-3 text-sm leading-7 text-text-muted">{{ model.summary }}</p>
            <div v-if="model.ideal_for" class="mt-5 rounded-2xl bg-surface-muted p-4 text-sm leading-7 text-text-subtle">
              <p class="font-medium text-text-brand">{{ t('buildingWithUs.idealFor') }}</p>
              <p>{{ model.ideal_for }}</p>
            </div>
            <div v-for="party in ['expert', 'projectapp']" :key="party" class="mt-6">
              <h4 class="text-sm font-medium text-text-brand">{{ t(party === 'expert' ? 'buildingWithUs.expertContributes' : 'buildingWithUs.projectappContributes') }}</h4>
              <ul class="mt-3 space-y-3">
                <li v-for="item in listOf(model[`${party}_contributes`])" :key="item" class="flex gap-3 text-sm leading-6 text-text-subtle">
                  <span class="text-text-brand" aria-hidden="true">✓</span><span>{{ item }}</span>
                </li>
              </ul>
            </div>
          </article>
        </div>
      </section>

      <section v-if="hasSection(program.incubation_periods)" data-document-enter aria-labelledby="building-with-us-periods-title" data-testid="building-with-us-periods">
        <h2 id="building-with-us-periods-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.incubation_periods.title }}</h2>
        <p v-if="program.incubation_periods.summary" class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.incubation_periods.summary }}</p>
        <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <article v-for="(period, index) in listOf(program.incubation_periods.items)" :key="period.id" class="rounded-3xl border border-border-default bg-surface p-6 shadow-card" :data-testid="`building-with-us-period-${index}`">
            <p class="text-5xl font-light text-text-brand">{{ period.months }}</p>
            <h3 class="mt-4 text-xl font-medium text-text-brand">{{ period.title }}</h3>
            <p v-if="period.summary" class="mt-3 text-sm leading-7 text-text-muted">{{ period.summary }}</p>
          </article>
        </div>
      </section>

      <section v-if="hasSection(program.scope)" data-document-enter aria-labelledby="building-with-us-scope-title" data-testid="building-with-us-scope">
        <h2 id="building-with-us-scope-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.scope.title }}</h2>
        <p v-if="program.scope.summary" class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.scope.summary }}</p>
        <div class="mt-8 grid gap-5 lg:grid-cols-2">
          <article v-for="item in listOf(program.scope.items)" :key="item.id" class="rounded-3xl border border-border-default bg-surface p-6 shadow-card">
            <h3 class="text-xl font-medium text-text-brand">{{ item.title }}</h3>
            <p v-if="item.summary" class="mt-3 text-sm leading-7 text-text-muted">{{ item.summary }}</p>
          </article>
        </div>
      </section>

      <section v-if="hasSection(program.milestones)" data-document-enter aria-labelledby="building-with-us-milestones-title" data-testid="building-with-us-milestones">
        <h2 id="building-with-us-milestones-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.milestones.title }}</h2>
        <p v-if="program.milestones.summary" class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.milestones.summary }}</p>
        <ol class="mt-8 space-y-5 border-l-2 border-primary pl-5">
          <li v-for="(item, index) in listOf(program.milestones.items)" :key="item.id" class="flex gap-4 rounded-2xl border border-border-default bg-surface p-5 shadow-card">
            <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-lg font-medium text-text-brand">{{ index + 1 }}</span>
            <div class="min-w-0">
              <h3 class="text-xl font-medium text-text-brand">{{ item.title }}</h3>
              <p v-if="item.summary" class="mt-2 text-sm leading-7 text-text-muted">{{ item.summary }}</p>
            </div>
          </li>
        </ol>
        <p v-if="program.milestones.note" class="mt-6 max-w-4xl rounded-2xl bg-primary-soft p-5 text-sm leading-7 text-text-subtle">{{ program.milestones.note }}</p>
      </section>

      <section v-if="hasSection(program.agreement)" data-document-enter aria-labelledby="building-with-us-agreement-title" data-testid="building-with-us-agreement">
        <h2 id="building-with-us-agreement-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.agreement.title }}</h2>
        <p v-if="program.agreement.summary" class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.agreement.summary }}</p>
        <div class="mt-8 grid gap-5 lg:grid-cols-2">
          <article v-for="item in listOf(program.agreement.items)" :key="item.id" class="rounded-3xl border border-border-default bg-surface p-6 shadow-card">
            <h3 class="text-xl font-medium text-text-brand">{{ item.title }}</h3>
            <p v-if="item.summary" class="mt-3 text-sm leading-7 text-text-muted">{{ item.summary }}</p>
          </article>
        </div>
      </section>

      <section v-if="hasSection(program.process)" data-document-enter aria-labelledby="building-with-us-process-title" data-testid="building-with-us-process">
        <h2 id="building-with-us-process-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.process.title }}</h2>
        <ol class="mt-8 grid gap-5 sm:grid-cols-2">
          <li v-for="(step, index) in listOf(program.process.items)" :key="step.id" class="flex gap-4 rounded-3xl border border-border-default bg-surface p-6 shadow-card">
            <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-lg font-medium text-text-brand">{{ index + 1 }}</span>
            <div class="min-w-0">
              <h3 class="text-xl font-medium text-text-brand">{{ step.title }}</h3>
              <p v-if="step.summary" class="mt-3 text-sm leading-7 text-text-muted">{{ step.summary }}</p>
            </div>
          </li>
        </ol>
      </section>

      <section v-if="hasSection(program.faq)" data-document-enter aria-labelledby="building-with-us-faq-title" class="building-with-us-faq" data-testid="building-with-us-faq">
        <h2 id="building-with-us-faq-title" class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.faq.title }}</h2>
        <div class="mt-8 space-y-3">
          <article v-for="(item, index) in listOf(program.faq.items)" :key="item.id" class="overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card" :data-testid="`building-with-us-faq-${index}`">
            <BaseButton
              unstyled
              type="button"
              class="flex min-h-16 w-full items-center gap-4 p-5 text-left transition-colors hover:bg-surface-raised"
              :aria-expanded="expandedFaq.has(index)"
              :aria-controls="`building-with-us-faq-panel-${index}`"
              :aria-label="t(expandedFaq.has(index) ? 'buildingWithUs.collapseFaq' : 'buildingWithUs.expandFaq', { question: item.question })"
              :data-testid="`building-with-us-faq-trigger-${index}`"
              @click="toggleFaq(index)"
            >
              <span class="min-w-0 flex-1 text-lg font-medium text-text-brand">{{ item.question }}</span>
              <span class="shrink-0 text-xl text-text-brand" aria-hidden="true">{{ expandedFaq.has(index) ? '−' : '+' }}</span>
            </BaseButton>
            <div v-show="expandedFaq.has(index)" :id="`building-with-us-faq-panel-${index}`" class="border-t border-border-default bg-surface-raised p-5 text-sm leading-7 text-text-subtle sm:px-7" :data-testid="`building-with-us-faq-panel-${index}`">
              {{ item.answer }}
            </div>
          </article>
        </div>
      </section>

      <section v-if="hasSection(program.cta)" data-document-enter>
        <div class="rounded-3xl bg-primary p-7 text-on-primary sm:p-12">
          <h2 v-if="program.cta.title" class="max-w-3xl text-3xl font-light sm:text-5xl">{{ program.cta.title }}</h2>
          <p v-if="program.cta.body" class="mt-5 max-w-3xl text-base leading-7 opacity-85">{{ program.cta.body }}</p>
          <BaseButton as="a" :to="safeWhatsappUrl(program.cta.whatsapp_url)" target="_blank" rel="noopener noreferrer" variant="accent" size="lg" v-bind="{ textPolicy: 'wrap' }" class="mt-7" data-testid="building-with-us-whatsapp-cta">
            {{ program.cta.button_label || t('buildingWithUs.whatsappCta') }}
          </BaseButton>
        </div>
      </section>
      <p v-if="program.legal?.disclaimer" data-document-enter class="mx-auto max-w-4xl text-center text-xs leading-5 text-text-muted" data-testid="building-with-us-disclaimer">{{ program.legal.disclaimer }}</p>
    </main>

    <template v-if="floatingActions">
      <PublicDocumentAction v-if="downloadUrl" action="pdf" :loading="isDownloading" :label="isDownloading ? t('buildingWithUs.generatingPdf') : t('buildingWithUs.downloadPdf')" data-testid="building-with-us-download-pdf-floating" @click="downloadPdf" />
      <PublicDocumentShareButton :is-dark="isDark" namespace="buildingWithUs" test-id-prefix="building-with-us" trigger-test-id="building-with-us-share" trigger-class="building-with-us-share-btn share-btn" />
      <PublicDocumentAction action="guide" class="building-with-us-restart-guide restart-tutorial-btn" :label="t('buildingWithUs.restartGuide')" data-testid="building-with-us-guide-restart" @click="onboardingRef?.forceStart()" />
      <PublicDocumentAction action="theme" class="building-with-us-theme-toggle dark-mode-toggle" :label="t('buildingWithUs.toggleTheme')" :is-dark="isDark" data-testid="building-with-us-theme-toggle" @click="toggleTheme" />
      <BuildingWithUsOnboarding ref="onboardingRef" :is-dark="isDark" />
    </template>
  </article>
</template>
