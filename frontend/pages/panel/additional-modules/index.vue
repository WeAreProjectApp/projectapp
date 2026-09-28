<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { get_request } from '~/stores/services/request_http'
import { useAdditionalModulesStore } from '~/stores/additional_modules'
import { useAdditionalModulesViewMode } from '~/composables/useAdditionalModulesViewMode'
import { usePanelNotify } from '~/composables/usePanelNotify'
import { useExplainerVideo } from '~/composables/useExplainerVideos'
import { useExplainerVideosStore } from '~/stores/explainer_videos'
import VideoResourceManager from '~/components/resources/VideoResourceManager.vue'
import BaseResponsiveTabs from '~/components/base/BaseResponsiveTabs.vue'
import ExplainerVideoCard from '~/components/ExplainerVideoCard.vue'
import ExplainerVisibilityToggle from '~/components/ExplainerVisibilityToggle.vue'
import AdditionalModulesAdminModuleActions from '~/components/AdditionalModules/AdminModuleActions.vue'
import AdditionalModulesCatalogControls from '~/components/AdditionalModules/CatalogControls.vue'
import AdditionalModulesModuleDetails from '~/components/AdditionalModules/ModuleDetails.vue'
import AdditionalModulesQuickAccess from '~/components/AdditionalModules/QuickAccess.vue'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })

const { locale, t } = useI18n()
const switchLocalePath = useSwitchLocalePath()
const route = useRoute()
const router = useRouter()
const store = useAdditionalModulesStore()
const explainerVideos = useExplainerVideosStore()
const notify = usePanelNotify()
const { viewMode } = useAdditionalModulesViewMode('panel')

const moduleFormOpen = ref(false)
const editingModule = ref(null)
const moduleError = ref('')
const categoriesOpen = ref(false)
const categoryManager = ref(null)
const categoryError = ref('')
const orderOpen = ref(false)
const orderError = ref('')
const selectionOpen = ref(false)
const selectionMode = ref('share')
const selectionError = ref('')
const generatedUrl = ref('')
const historyOpen = ref(false)
const clients = ref([])
const detailOpen = ref(false)
const detailModule = ref(null)
const detailOpener = ref(null)
const expandedModuleId = ref(null)
const activeSection = ref(route.query.tab === 'resources' ? 'resources' : 'catalog')

const isEnglish = computed(() => locale.value.startsWith('en'))
const language = computed(() => (isEnglish.value ? 'en' : 'es'))
const explainer = useExplainerVideo('additional-modules', language, computed(() => explainerVideos.settings?.resources?.[`additional-modules:${language.value}`]))
const catalogVideoVisible = computed(() => explainerVideos.isVisible('additional-modules'))
const orderedCategories = computed(() => [...store.categories].sort((a, b) => a.order - b.order))
const groupedModules = computed(() => orderedCategories.value.map((category) => ({
  ...category,
  modules: store.modules.filter((module) => module.category === category.id),
})).filter((category) => category.modules.length > 0))
const activeCategoryIds = computed(() => new Set(
  store.categories.filter((category) => category.is_active).map((category) => category.id),
))
const activeModuleIds = computed(() => new Set(
  store.modules
    .filter((module) => module.is_active && activeCategoryIds.value.has(module.category))
    .map((module) => module.id),
))
const usableShareLinks = computed(() => store.shareLinks.filter((link) => (
  link.is_active
  && link.selected_modules.some((module) => activeModuleIds.value.has(module.id))
)))
const quickAccessStats = computed(() => ({
  active_module_count: activeModuleIds.value.size,
  active_share_count: usableShareLinks.value.length,
  unopened_active_share_count: usableShareLinks.value.filter(
    (link) => !link.first_viewed_at,
  ).length,
  last_viewed_at: store.shareLinks.reduce((latest, link) => {
    if (!link.last_viewed_at) return latest
    if (!latest) return link.last_viewed_at
    return new Date(link.last_viewed_at) > new Date(latest) ? link.last_viewed_at : latest
  }, null),
}))

const localized = (value, field) => value?.[`${field}_${isEnglish.value ? 'en' : 'es'}`] || ''
const localizedModule = (module) => ({
  ...module,
  name: localized(module, 'name'),
  summary: localized(module, 'summary'),
  what_is: localized(module, 'what_is'),
  purpose: localized(module, 'purpose'),
  problems_solved: module?.[`problems_solved_${language.value}`] || [],
  integrations: module?.[`integrations_${language.value}`] || [],
  implementation_requirements: module?.[`implementation_requirements_${language.value}`] || [],
})
const localizedDetailModule = computed(() => (
  detailModule.value ? localizedModule(detailModule.value) : null
))

function humanError(errors, fallbackKey = 'additionalModules.saveError') {
  if (!errors) return t(fallbackKey)
  if (typeof errors === 'string') return errors
  if (errors.detail) return Array.isArray(errors.detail) ? errors.detail[0] : errors.detail
  const value = Object.values(errors)[0]
  if (Array.isArray(value)) return value[0]
  if (typeof value === 'object') return humanError(value, fallbackKey)
  return String(value || t(fallbackKey))
}

onMounted(async () => {
  await Promise.all([store.fetchCatalog(), store.fetchShareLinks()])
  try {
    const response = await get_request('proposals/client-profiles/?limit=100')
    clients.value = response.data.results || response.data
  } catch {
    clients.value = []
  }

  const requestedAction = Array.isArray(route.query.action)
    ? route.query.action[0]
    : route.query.action
  if (requestedAction === 'share' || requestedAction === 'pdf') {
    openSelection(requestedAction)
  } else if (requestedAction === 'tracking') {
    await openHistory()
  }
})

async function retryCatalog() {
  await store.fetchCatalog()
}

function openCreateModule() {
  editingModule.value = null
  moduleError.value = ''
  moduleFormOpen.value = true
}

function openEditModule(module) {
  editingModule.value = module
  moduleError.value = ''
  moduleFormOpen.value = true
}

async function saveModule(payload) {
  moduleError.value = ''
  const result = await store.saveModule(editingModule.value?.id, payload)
  if (!result.success) {
    moduleError.value = humanError(result.errors)
    return
  }
  moduleFormOpen.value = false
  notify.success({ title: t('additionalModules.saveSuccess') })
}

async function changeModuleStatus(module) {
  const action = module.is_active ? 'retire' : 'restore'
  const result = await store.setModuleStatus(module.id, action)
  if (!result.success) {
    notify.error({ title: humanError(result.errors) })
    return
  }
  notify.success({ title: t('additionalModules.saveSuccess') })
}

async function saveCategory({ id, payload }) {
  categoryError.value = ''
  const result = await store.saveCategory(id, payload)
  if (!result.success) {
    categoryError.value = humanError(result.errors)
    return
  }
  categoryManager.value?.closeForm?.()
  notify.success({ title: t('additionalModules.saveSuccess') })
}

async function changeCategoryStatus({ category, action }) {
  categoryError.value = ''
  const result = await store.setCategoryStatus(category.id, action)
  if (!result.success) categoryError.value = humanError(result.errors)
}

async function saveOrder(payload) {
  orderError.value = ''
  const result = await store.reorderCatalog(payload)
  if (!result.success) {
    orderError.value = result.errors?.code === 'stale_catalog_revision'
      ? t('additionalModules.staleOrder')
      : humanError(result.errors)
    return
  }
  orderOpen.value = false
  notify.success({ title: t('additionalModules.saveSuccess') })
}

function openSelection(mode) {
  selectionMode.value = mode
  selectionError.value = ''
  generatedUrl.value = ''
  selectionOpen.value = true
}

async function submitSelection(payload) {
  selectionError.value = ''
  if (selectionMode.value === 'share') {
    const result = await store.createShareLink(payload)
    if (!result.success) {
      selectionError.value = humanError(result.errors)
      return
    }
    generatedUrl.value = `${window.location.origin}${result.data.public_path}`
    return
  }

  const result = await store.downloadPdf(payload)
  if (!result.success) {
    selectionError.value = humanError(result.errors)
    return
  }
  const objectUrl = URL.createObjectURL(new Blob([result.data], { type: 'application/pdf' }))
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = payload.language === 'en'
    ? 'additional-modules-catalog.pdf'
    : 'catalogo-modulos-adicionales.pdf'
  link.click()
  URL.revokeObjectURL(objectUrl)
  await updateSelectionOpen(false)
}

async function openHistory() {
  await store.fetchShareLinks()
  historyOpen.value = true
}

async function clearRequestedAction() {
  if (!route.query.action) return
  const { action: _action, ...query } = route.query
  await router.replace({ query })
}

async function updateSelectionOpen(value) {
  selectionOpen.value = value
  if (!value) await clearRequestedAction()
}

async function updateHistoryOpen(value) {
  historyOpen.value = value
  if (!value) await clearRequestedAction()
}

async function changeShareStatus({ link, action }) {
  const result = await store.setShareLinkStatus(link.uuid, action)
  if (!result.success) notify.error({ title: humanError(result.errors) })
}

async function changeShareVideo({ link, value }) {
  const result = await store.setShareLinkVideo(link.uuid, value)
  if (!result.success) {
    notify.error({ title: t('additionalModules.shareVideoError') })
    return
  }
  notify.success({
    title: t(value ? 'additionalModules.shareVideoShown' : 'additionalModules.shareVideoHidden', {
      label: link.recipient_label,
    }),
  })
}

async function copyShare(link) {
  try {
    await navigator.clipboard.writeText(`${window.location.origin}${link.public_path}`)
    notify.success({ title: t('additionalModules.copied') })
  } catch {
    notify.error({ title: t('additionalModules.saveError') })
  }
}

function openDetail(module, event) {
  detailModule.value = module
  detailOpener.value = event?.currentTarget || null
  detailOpen.value = true
}

function toggleAccordion(moduleId) {
  expandedModuleId.value = expandedModuleId.value === moduleId ? null : moduleId
}

async function changeLanguage(nextLanguage) {
  if (nextLanguage === language.value) return
  const path = switchLocalePath(nextLanguage === 'en' ? 'en-us' : 'es-co')
  if (path) await navigateTo(path)
}

async function closeDetail() {
  detailOpen.value = false
  detailModule.value = null
  await nextTick()
  detailOpener.value?.focus?.()
}
</script>

<template>
  <BasePageShell width="panel">
    <header class="mb-7 flex flex-col gap-5 panel-portrait:flex-row panel-portrait:items-start panel-portrait:justify-between">
      <div class="min-w-0">
        <h1 class="text-2xl font-light text-text-default">{{ t('additionalModules.panelTitle') }}</h1>
        <p class="mt-1 max-w-3xl text-sm text-text-subtle">{{ t('additionalModules.panelDescription') }}</p>
        <p class="mt-2 text-xs font-medium text-text-brand">{{ t('additionalModules.noPriceNotice') }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <BaseButton size="sm" data-testid="additional-module-new" @click="openCreateModule">{{ t('additionalModules.addModule') }}</BaseButton>
        <BaseButton variant="secondary" size="sm" @click="categoriesOpen = true">{{ t('additionalModules.manageCategories') }}</BaseButton>
        <BaseButton variant="secondary" size="sm" @click="orderOpen = true">{{ t('additionalModules.reorder') }}</BaseButton>
      </div>
    </header>

    <AdditionalModulesQuickAccess
      class="mb-8"
      :language="language"
      :stats="quickAccessStats"
      @share="openSelection('share')"
      @customize-pdf="openSelection('pdf')"
      @tracking="openHistory"
    />

    <BaseResponsiveTabs v-model="activeSection" :tabs="[{ id: 'catalog', label: 'Catálogo' }, { id: 'resources', label: 'Recursos' }]" />
    <VideoResourceManager v-if="activeSection === 'resources'" module="additional-modules" :language="language" />

    <div v-show="activeSection === 'catalog'">
    <div class="mb-8 space-y-3">
      <ExplainerVisibilityToggle
        module="additional-modules"
        i18n-namespace="additionalModules"
        test-id="additional-modules-explainer"
      />
      <ExplainerVideoCard
        v-if="explainer"
        :video="explainer"
        i18n-namespace="additionalModules"
        variant="compact"
        test-id="additional-modules-explainer"
      />
    </div>

    <div v-if="store.isLoading && !store.modules.length" class="flex min-h-64 items-center justify-center" role="status">
      <span class="h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-primary" />
    </div>

    <div
      v-else-if="store.error && !store.modules.length"
      class="rounded-xl border border-danger-strong/30 bg-danger-soft p-6 text-center"
      role="alert"
    >
      <p class="font-medium text-danger-strong">{{ t('additionalModules.loadError') }}</p>
      <BaseButton class="mt-4" variant="secondary" @click="retryCatalog">
        {{ t('additionalModules.retry') }}
      </BaseButton>
    </div>

    <BaseEmptyState
      v-else-if="!store.modules.length"
      :title="t('additionalModules.emptyTitle')"
      :description="t('additionalModules.emptyBody')"
    />

    <div v-else class="space-y-10">
      <AdditionalModulesCatalogControls
        v-model="viewMode"
        :language="language"
        @change-language="changeLanguage"
      />

      <nav class="flex gap-2 overflow-x-auto pb-2 panel-portrait:flex-wrap" :aria-label="t('additionalModules.title')">
        <a
          v-for="category in groupedModules"
          :key="category.id"
          :href="`#panel-additional-category-${category.slug}`"
          class="min-h-11 shrink-0 rounded-full border border-border-default bg-surface px-4 py-2.5 text-sm font-medium text-text-default hover:border-primary focus:outline-none focus:ring-2 focus:ring-focus-ring/40"
        >{{ localized(category, 'name') }}</a>
      </nav>

      <section
        v-for="category in groupedModules"
        :id="`panel-additional-category-${category.slug}`"
        :key="category.id"
        class="scroll-mt-20"
      >
        <div class="mb-4 flex flex-wrap items-center gap-2 border-b border-border-default pb-3">
          <h2 class="text-xl font-medium text-text-brand">{{ localized(category, 'name') }}</h2>
          <BaseBadge v-if="!category.is_active" variant="neutral">{{ t('additionalModules.retired') }}</BaseBadge>
          <span class="ml-auto text-sm text-text-muted">{{ category.modules.length }}</span>
        </div>
        <div v-if="viewMode === 'cards'" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          <article
            v-for="module in category.modules"
            :key="module.id"
            class="flex min-h-64 flex-col rounded-xl border border-border-default bg-surface p-5 shadow-card"
            :class="!module.is_active ? 'opacity-70' : ''"
            :data-testid="`additional-admin-module-${module.id}`"
          >
            <div class="flex items-start justify-between gap-3">
              <span class="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-soft text-xl" aria-hidden="true">{{ module.icon || '＋' }}</span>
              <BaseBadge :variant="module.is_active ? 'success' : 'neutral'">
                {{ module.is_active ? t('additionalModules.active') : t('additionalModules.retired') }}
              </BaseBadge>
            </div>
            <h3 class="mt-4 text-lg font-medium leading-6 text-text-brand">{{ localized(module, 'name') }}</h3>
            <p class="mt-2 flex-1 text-sm leading-6 text-text-muted">{{ localized(module, 'summary') }}</p>
            <AdditionalModulesAdminModuleActions
              class="mt-5"
              :module="module"
              @detail="openDetail(module, $event)"
              @edit="openEditModule(module)"
              @status="changeModuleStatus(module)"
            />
          </article>
        </div>

        <div
          v-else-if="viewMode === 'list'"
          class="space-y-3"
          :data-testid="`additional-admin-list-${category.slug}`"
        >
          <article
            v-for="module in category.modules"
            :key="module.id"
            class="flex min-w-0 flex-col gap-4 rounded-xl border border-border-default bg-surface p-4 shadow-card panel-portrait:flex-row panel-portrait:items-center"
            :class="!module.is_active ? 'opacity-70' : ''"
            :data-testid="`additional-admin-module-${module.id}`"
          >
            <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-xl" aria-hidden="true">
              {{ module.icon || '＋' }}
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <h3 class="break-words text-lg font-medium text-text-brand">{{ localized(module, 'name') }}</h3>
                <BaseBadge :variant="module.is_active ? 'success' : 'neutral'">
                  {{ module.is_active ? t('additionalModules.active') : t('additionalModules.retired') }}
                </BaseBadge>
              </div>
              <p class="mt-1 break-words text-sm leading-6 text-text-muted">{{ localized(module, 'summary') }}</p>
            </div>
            <AdditionalModulesAdminModuleActions
              class="shrink-0"
              :module="module"
              @detail="openDetail(module, $event)"
              @edit="openEditModule(module)"
              @status="changeModuleStatus(module)"
            />
          </article>
        </div>

        <div
          v-else
          class="space-y-3"
          :data-testid="`additional-admin-accordion-${category.slug}`"
        >
          <article
            v-for="module in category.modules"
            :key="module.id"
            class="overflow-hidden rounded-xl border border-border-default bg-surface shadow-card"
            :class="!module.is_active ? 'opacity-70' : ''"
            :data-testid="`additional-admin-module-${module.id}`"
          >
            <!-- design-tokens: allow-raw-button — disclosure header owns aria-expanded. -->
            <!-- panel-action-icons: allow-disclosure — the module icon and state marker describe this content row. -->
            <button
              type="button"
              class="flex min-h-16 w-full min-w-0 items-center gap-3 p-4 text-left outline-none transition-colors hover:bg-surface-raised focus:ring-2 focus:ring-inset focus:ring-focus-ring/40"
              :aria-expanded="expandedModuleId === module.id"
              :aria-controls="`additional-admin-accordion-panel-${module.id}`"
              :data-testid="`additional-admin-accordion-trigger-${module.id}`"
              @click="toggleAccordion(module.id)"
            >
              <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-xl" aria-hidden="true">
                {{ module.icon || '＋' }}
              </span>
              <span class="min-w-0 flex-1">
                <span class="flex flex-wrap items-center gap-2">
                  <span class="break-words text-lg font-medium text-text-brand">{{ localized(module, 'name') }}</span>
                  <BaseBadge :variant="module.is_active ? 'success' : 'neutral'">
                    {{ module.is_active ? t('additionalModules.active') : t('additionalModules.retired') }}
                  </BaseBadge>
                </span>
                <span class="mt-1 block break-words text-sm leading-6 text-text-muted">{{ localized(module, 'summary') }}</span>
              </span>
              <span class="shrink-0 text-xl text-text-brand" aria-hidden="true">
                {{ expandedModuleId === module.id ? '−' : '+' }}
              </span>
            </button>
            <div
              v-show="expandedModuleId === module.id"
              :id="`additional-admin-accordion-panel-${module.id}`"
              class="space-y-5 border-t border-border-default p-4 sm:p-6"
            >
              <AdditionalModulesModuleDetails :module="localizedModule(module)" />
              <AdditionalModulesAdminModuleActions
                :module="module"
                @detail="openDetail(module, $event)"
                @edit="openEditModule(module)"
                @status="changeModuleStatus(module)"
              />
            </div>
          </article>
        </div>
      </section>
    </div>

    </div>

    <AdditionalModulesModuleFormModal
      v-model="moduleFormOpen"
      :module="editingModule"
      :categories="store.categories"
      :saving="store.isUpdating"
      :error-message="moduleError"
      @save="saveModule"
    />
    <AdditionalModulesCategoryManagerModal
      ref="categoryManager"
      v-model="categoriesOpen"
      :categories="store.categories"
      :saving="store.isUpdating"
      :error-message="categoryError"
      @save="saveCategory"
      @status="changeCategoryStatus"
    />
    <AdditionalModulesCatalogOrderModal
      v-model="orderOpen"
      :categories="store.categories"
      :modules="store.modules"
      :saving="store.isUpdating"
      :error-message="orderError"
      @save="saveOrder"
    />
    <AdditionalModulesCatalogSelectionModal
      :model-value="selectionOpen"
      :mode="selectionMode"
      :categories="store.categories"
      :modules="store.modules"
      :clients="clients"
      :saving="store.isUpdating"
      :error-message="selectionError"
      :generated-url="generatedUrl"
      :catalog-video-visible="catalogVideoVisible"
      @update:model-value="updateSelectionOpen"
      @submit="submitSelection"
    />
    <AdditionalModulesShareHistoryModal
      :model-value="historyOpen"
      :links="store.shareLinks"
      :saving="store.isUpdating"
      :catalog-video-visible="catalogVideoVisible"
      @update:model-value="updateHistoryOpen"
      @status="changeShareStatus"
      @copy="copyShare"
      @video="changeShareVideo"
    />

    <BaseModal v-model="detailOpen" kind="detail" padding="none" @close="closeDetail">
      <div v-if="localizedDetailModule" class="flex min-h-0 flex-col">
        <header class="flex items-start justify-between gap-4 border-b border-border-default px-5 py-5 sm:px-7">
          <div>
            <span class="text-2xl" aria-hidden="true">{{ localizedDetailModule.icon }}</span>
            <h2 class="mt-2 text-2xl font-light text-text-brand">{{ localizedDetailModule.name }}</h2>
            <p class="mt-2 text-sm leading-6 text-text-muted">{{ localizedDetailModule.summary }}</p>
          </div>
          <BaseActionButton
            action="close"
            :label="t('additionalModules.close')"
            @click="closeDetail"
          />
        </header>
        <div class="overflow-y-auto p-5 sm:p-7">
          <AdditionalModulesModuleDetails :module="localizedDetailModule" />
        </div>
      </div>
    </BaseModal>
  </BasePageShell>
</template>
