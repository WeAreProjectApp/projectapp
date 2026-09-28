<script setup>
import PublicDocumentAction from '~/components/PublicDocumentAction.vue'
import { computed, nextTick, ref, toRef, watch } from 'vue'
import { useAdditionalModulesTheme } from '~/composables/useAdditionalModulesTheme'
import { usePublicDocumentEntrance } from '~/composables/usePublicDocumentEntrance'
import { useAdditionalModulesViewMode } from '~/composables/useAdditionalModulesViewMode'
import { useExplainerVideo } from '~/composables/useExplainerVideos'
import ExplainerVideoCard from '~/components/ExplainerVideoCard.vue'
import AdditionalModulesCatalogControls from '~/components/AdditionalModules/CatalogControls.vue'
import AdditionalModulesCatalogSkeleton from '~/components/AdditionalModules/CatalogSkeleton.vue'
import AdditionalModulesModuleDetails from '~/components/AdditionalModules/ModuleDetails.vue'
import AdditionalModulesOnboarding from '~/components/AdditionalModules/Onboarding.vue'
import AdditionalModulesShareButton from '~/components/AdditionalModules/ShareButton.vue'

const props = defineProps({
  explainerResource: { type: Object, default: null },
  categories: { type: Array, default: () => [] },
  totalModules: { type: Number, default: 0 },
  downloadUrl: { type: String, default: '' },
  showHeader: { type: Boolean, default: true },
  isShared: { type: Boolean, default: false },
  language: { type: String, default: 'es' },
  /** Panel switch (and, on a shared link, its own switch) from the public payload. */
  showExplainer: { type: Boolean, default: true },
  /**
   * The catalog data is not known yet (a prerender whose API fetch failed, or
   * the live fetch still running): show a skeleton, never the empty state.
   */
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['change-language'])
const { t } = useI18n()
const { viewMode } = useAdditionalModulesViewMode('public')
const { isDark, toggle: toggleTheme } = useAdditionalModulesTheme()
const documentRef = ref(null)
usePublicDocumentEntrance(documentRef)
const explainer = useExplainerVideo('additional-modules', toRef(props, 'language'), toRef(props, 'explainerResource'))
// Until the payload arrives its switch is unknown, so a hidden video never flashes.
const explainerVisible = computed(() => (
  !props.loading && props.showExplainer && Boolean(explainer.value)
))
const selectedModule = ref(null)
const detailOpen = ref(false)
const opener = ref(null)
const isDownloading = ref(false)
const downloadError = ref(false)
const expandedModuleSlug = ref('')
const onboardingRef = ref(null)
const guideStarted = ref(false)

const hasModules = computed(() => (
  !props.loading && props.totalModules > 0 && props.categories.length > 0
))

function openModule(module, event) {
  selectedModule.value = module
  opener.value = event?.currentTarget || null
  detailOpen.value = true
}

function closeDetail() {
  detailOpen.value = false
}

function toggleAccordion(slug) {
  expandedModuleSlug.value = expandedModuleSlug.value === slug ? '' : slug
}

function responseFilename(response) {
  const disposition = response.headers.get('content-disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  return match?.[1] || 'additional-modules-catalog.pdf'
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

watch(detailOpen, async (isOpen) => {
  if (isOpen) return
  selectedModule.value = null
  await nextTick()
  opener.value?.focus?.()
})

watch([hasModules, onboardingRef], async ([modulesAvailable, onboarding]) => {
  if (!modulesAvailable || !onboarding || guideStarted.value) return
  guideStarted.value = true
  await nextTick()
  onboarding.start()
}, { immediate: true, flush: 'post' })
</script>

<template>
  <div
    ref="documentRef"
    class="public-document-theme public-document-view public-document-canvas min-h-screen w-full text-text-default"
    :data-theme="isDark ? 'dark' : 'light'"
    data-testid="additional-modules-catalog"
  >
    <header v-if="showHeader" data-document-enter class="px-4 pb-12 pt-12 sm:px-6 sm:pb-16 sm:pt-16">
      <div class="mx-auto max-w-[1400px] text-center">
        <p class="mb-3 text-sm font-medium uppercase tracking-[0.18em] text-text-brand">
          {{ t('additionalModules.eyebrow') }}
        </p>
        <h1 class="text-balance text-4xl font-light tracking-tight text-text-brand sm:text-6xl lg:text-7xl">
          {{ t('additionalModules.title') }}
        </h1>
        <p class="mx-auto mt-5 max-w-3xl text-base leading-7 text-text-muted sm:text-lg">
          {{ t('additionalModules.subtitle') }}
        </p>
        <ExplainerVideoCard
          v-if="explainerVisible"
          :video="explainer"
          i18n-namespace="additionalModules"
          variant="hero"
          test-id="additional-modules-explainer"
          class="additional-modules-explainer mx-auto mt-8 max-w-4xl"
        />
        <p
          v-if="isShared"
          class="mx-auto mt-5 w-fit rounded-full border border-border-default bg-surface px-4 py-2 text-sm text-text-muted"
        >
          {{ t('additionalModules.sharedNotice') }}
        </p>
        <div v-if="hasModules" class="mt-7 flex flex-wrap items-center justify-center gap-3">
          <span class="text-sm font-medium text-text-muted">
            {{ t('additionalModules.moduleCount', { count: totalModules }) }}
          </span>
          <BaseButton
            v-if="downloadUrl"
            variant="secondary"
            :loading="isDownloading"
            data-testid="additional-modules-download-pdf"
            @click="downloadPdf"
          >
            {{ t('additionalModules.downloadPdf') }}
          </BaseButton>
        </div>
        <BaseAlert
          v-if="downloadError"
          class="mx-auto mt-4 max-w-xl text-left"
          variant="danger"
        >
          {{ t('additionalModules.pdfError') }}
        </BaseAlert>
      </div>
    </header>

    <div v-if="hasModules" class="mx-auto w-full max-w-[1400px] px-4 sm:px-6">
      <AdditionalModulesCatalogControls
        v-model="viewMode"
        :language="language"
        class="additional-modules-controls mb-8"
        @change-language="emit('change-language', $event)"
      />

      <nav
        class="additional-modules-category-nav mb-10 flex snap-x gap-2 overflow-x-auto pb-2 sm:flex-wrap sm:justify-center sm:overflow-visible"
        :aria-label="t('additionalModules.title')"
      >
        <a
          v-for="category in categories"
          :key="category.slug"
          :href="`#category-${category.slug}`"
          class="min-h-11 shrink-0 snap-start rounded-full border border-border-default bg-surface px-4 py-2.5 text-sm font-medium text-text-default transition-colors hover:border-primary hover:text-text-brand focus:outline-none focus:ring-2 focus:ring-focus-ring/40"
        >
          {{ category.name }}
        </a>
      </nav>

      <section
        v-for="category in categories"
        :id="`category-${category.slug}`"
        :key="category.slug"
        data-document-enter
        class="scroll-mt-24 pb-14"
        :aria-labelledby="`category-title-${category.slug}`"
      >
        <div class="mb-6 flex items-end justify-between gap-4 pb-4">
          <h2
            :id="`category-title-${category.slug}`"
            class="text-2xl font-light text-text-brand sm:text-3xl"
          >
            {{ category.name }}
          </h2>
          <span class="shrink-0 text-sm text-text-muted">{{ category.modules.length }}</span>
        </div>

        <div v-if="viewMode === 'cards'" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <!-- design-tokens: allow-raw-button — selectable catalog card opens inline detail. -->
          <button
            v-for="module in category.modules"
            :id="`module-${module.slug}`"
            :key="module.slug"
            type="button"
            class="additional-module-entry group min-h-52 rounded-2xl border border-border-default bg-surface p-5 text-left shadow-card transition duration-200 motion-safe:hover:-translate-y-0.5 hover:border-text-brand hover:shadow-raised focus:outline-none focus:ring-2 focus:ring-focus-ring/40 motion-reduce:transition-none"
            :aria-label="t('additionalModules.openDetail', { name: module.name })"
            :data-testid="`additional-module-card-${module.slug}`"
            @click="openModule(module, $event)"
          >
            <span class="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-primary-soft text-2xl" aria-hidden="true">
              {{ module.icon || '＋' }}
            </span>
            <span class="block text-lg font-medium leading-6 text-text-brand">
              {{ module.name }}
            </span>
            <span class="mt-3 block text-sm leading-6 text-text-muted">
              {{ module.summary }}
            </span>
            <span class="mt-5 inline-flex items-center gap-2 text-sm font-medium text-text-brand">
              {{ t('additionalModules.viewDetails') }}
              <span aria-hidden="true" class="transition-transform motion-safe:group-hover:translate-x-1 motion-reduce:transition-none">→</span>
            </span>
          </button>
        </div>

        <div v-else-if="viewMode === 'list'" class="space-y-3">
          <article
            v-for="module in category.modules"
            :id="`module-${module.slug}`"
            :key="module.slug"
            class="additional-module-entry flex min-w-0 flex-col gap-4 rounded-2xl border border-border-default bg-surface p-4 shadow-card sm:flex-row sm:items-center"
            :data-testid="`additional-module-list-${module.slug}`"
          >
            <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-xl" aria-hidden="true">
              {{ module.icon || '＋' }}
            </span>
            <div class="min-w-0 flex-1">
              <h3 class="break-words text-lg font-medium text-text-brand">{{ module.name }}</h3>
              <p class="mt-1 break-words text-sm leading-6 text-text-muted">{{ module.summary }}</p>
            </div>
            <BaseButton
              variant="secondary"
              size="sm"
              class="self-start sm:self-center"
              :aria-label="t('additionalModules.openDetail', { name: module.name })"
              @click="openModule(module, $event)"
            >
              {{ t('additionalModules.viewDetails') }}
            </BaseButton>
          </article>
        </div>

        <div v-else class="space-y-3">
          <article
            v-for="module in category.modules"
            :id="`module-${module.slug}`"
            :key="module.slug"
            class="additional-module-entry overflow-hidden rounded-2xl border border-border-default bg-surface shadow-card"
            :data-testid="`additional-module-accordion-${module.slug}`"
          >
            <!-- design-tokens: allow-raw-button — disclosure header owns aria-expanded. -->
            <button
              type="button"
              class="flex min-h-16 w-full min-w-0 items-center gap-3 p-4 text-left outline-none transition-colors hover:bg-surface-raised focus:ring-2 focus:ring-inset focus:ring-focus-ring/40"
              :aria-expanded="expandedModuleSlug === module.slug"
              :aria-controls="`additional-module-accordion-panel-${module.slug}`"
              :data-testid="`additional-module-accordion-trigger-${module.slug}`"
              @click="toggleAccordion(module.slug)"
            >
              <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-xl" aria-hidden="true">
                {{ module.icon || '＋' }}
              </span>
              <span class="min-w-0 flex-1">
                <span class="block break-words text-lg font-medium text-text-brand">{{ module.name }}</span>
                <span class="mt-1 block break-words text-sm leading-6 text-text-muted">{{ module.summary }}</span>
              </span>
              <span class="shrink-0 text-xl text-text-brand" aria-hidden="true">
                {{ expandedModuleSlug === module.slug ? '−' : '+' }}
              </span>
            </button>
            <div
              v-show="expandedModuleSlug === module.slug"
              :id="`additional-module-accordion-panel-${module.slug}`"
              class="public-document-canvas border-t border-border-default p-4 sm:p-6"
            >
              <AdditionalModulesModuleDetails :module="module" />
            </div>
          </article>
        </div>
      </section>
    </div>

    <AdditionalModulesCatalogSkeleton v-else-if="loading" />

    <div v-else class="mx-auto max-w-2xl px-4 py-24 text-center sm:px-6">
      <h2 class="text-2xl font-medium text-text-brand">{{ t('additionalModules.emptyTitle') }}</h2>
      <p class="mt-3 text-text-muted">{{ t('additionalModules.emptyBody') }}</p>
    </div>

    <BaseModal
      v-model="detailOpen"
      kind="detail"
      padding="none"
      :theme="isDark ? 'dark' : 'light'"
      theme-class="public-document-theme"
      @close="closeDetail"
    >
      <div
        v-if="selectedModule"
        class="public-document-theme public-document-canvas flex min-h-0 flex-col"
        :data-theme="isDark ? 'dark' : 'light'"
        data-testid="additional-module-detail-modal"
      >
        <header class="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-border-default bg-surface px-5 py-5 sm:px-7">
          <div class="min-w-0">
            <span class="mb-3 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary-soft text-2xl" aria-hidden="true">
              {{ selectedModule.icon || '＋' }}
            </span>
            <h2 class="text-balance text-2xl font-light text-text-brand sm:text-3xl">
              {{ selectedModule.name }}
            </h2>
            <p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted sm:text-base">
              {{ selectedModule.summary }}
            </p>
          </div>
          <BaseButton
            variant="ghost"
            icon-only
            :aria-label="t('additionalModules.close')"
            @click="closeDetail"
          >
            <span aria-hidden="true" class="text-xl">×</span>
          </BaseButton>
        </header>

        <div class="overflow-y-auto p-5 sm:p-7">
          <AdditionalModulesModuleDetails :module="selectedModule" />
        </div>
      </div>
    </BaseModal>

    <template v-if="hasModules">
      <AdditionalModulesShareButton :is-dark="isDark" />

      <PublicDocumentAction
        v-if="downloadUrl"
        action="pdf"
        class="additional-modules-pdf-fab pdf-download"
        :loading="isDownloading"
        :label="isDownloading ? t('additionalModules.generatingPdf') : t('additionalModules.downloadPdf')"
        data-testid="additional-modules-download-pdf-floating"
        @click="downloadPdf"
      />
      <PublicDocumentAction
        action="guide"
        class="additional-modules-restart-guide restart-tutorial-btn"
        :label="t('additionalModules.restartGuide')"
        data-testid="additional-modules-guide-restart"
        @click="onboardingRef?.forceStart()"
      />
      <PublicDocumentAction
        action="theme"
        class="additional-modules-theme-toggle dark-mode-toggle"
        :label="t('additionalModules.toggleTheme')"
        :is-dark="isDark"
        data-testid="additional-modules-theme-toggle"
        @click="toggleTheme"
      />

      <AdditionalModulesOnboarding
        ref="onboardingRef"
        :is-dark="isDark"
      />
    </template>
  </div>
</template>
