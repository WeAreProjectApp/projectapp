<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import VideoResourceManager from '~/components/resources/VideoResourceManager.vue'
import { useExplainerVideosStore } from '~/stores/explainer_videos'
import ExplainerVideoCard from '~/components/ExplainerVideoCard.vue'
import ExplainerVisibilityToggle from '~/components/ExplainerVisibilityToggle.vue'
import { useExplainerVideo } from '~/composables/useExplainerVideos'
import { usePanelNotify } from '~/composables/usePanelNotify'
import { useFinancingAgreementsStore } from '~/stores/financing_agreements'
import { get_request } from '~/stores/services/request_http'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })

const { locale, t } = useI18n()
const localePath = useLocalePath()
const switchLocalePath = useSwitchLocalePath()
const route = useRoute()
const router = useRouter()
const notify = usePanelNotify()
const agreementsStore = useFinancingAgreementsStore()

const allowedTabs = new Set(['program', 'agreements', 'settings'])
const activeSection = ref(allowedTabs.has(route.query.tab) ? route.query.tab : 'program')
const isEnglish = computed(() => locale.value.startsWith('en'))
const language = computed(() => (isEnglish.value ? 'en' : 'es'))
const videoSettings = useExplainerVideosStore()
const explainer = useExplainerVideo('financing', language, computed(() => videoSettings.settings?.resources?.[`financing:${language.value}`]))
const program = ref(null)
const isLoadingProgram = ref(false)
const programLoadError = ref(false)
const filters = ref({ q: '', status: '', modality: '', archived: 'false' })

const sectionOptions = computed(() => [
  { value: 'program', label: t('financing.programTab'), testId: 'financing-tab-program' },
  { value: 'agreements', label: t('financing.agreementsTab'), testId: 'financing-tab-agreements' },
  { value: 'settings', label: t('financing.settingsTab'), testId: 'financing-tab-settings' },
])
const publicPath = computed(() => (
  isEnglish.value ? '/en-us/partnership-program' : '/es-co/partnership-program'
))
const publicUrl = computed(() => `https://projectapp.co${publicPath.value}`)
const pdfUrl = computed(() => `/api/financing/public/pdf/?lang=${language.value}`)
const rows = computed(() => agreementsStore.agreements)
const statusOptions = computed(() => [
  { value: '', label: t('financing.agreement.filters.allStatuses') },
  { value: 'draft', label: t('financing.agreement.status.draft') },
  { value: 'ready', label: t('financing.agreement.status.ready') },
  { value: 'active', label: t('financing.agreement.status.active') },
  { value: 'completed', label: t('financing.agreement.status.completed') },
  { value: 'cancelled', label: t('financing.agreement.status.cancelled') },
])
const modalityOptions = computed(() => [
  { value: '', label: t('financing.agreement.filters.allModalities') },
  { value: 'five_year', label: t('financing.agreement.form.fiveYearOption') },
  { value: 'three_year', label: t('financing.agreement.form.threeYearOption') },
])
const archiveOptions = computed(() => [
  { value: 'false', label: t('financing.agreement.filters.current') },
  { value: 'true', label: t('financing.agreement.filters.archived') },
  { value: 'all', label: t('financing.agreement.filters.all') },
])

async function loadProgram() {
  isLoadingProgram.value = true
  programLoadError.value = false
  try {
    const response = await get_request(`financing/public/?lang=${language.value}`)
    program.value = response.data
  } catch {
    programLoadError.value = true
  } finally {
    isLoadingProgram.value = false
  }
}

async function loadAgreements() {
  await agreementsStore.fetchAgreements(filters.value)
}

onMounted(async () => {
  await Promise.all([
    loadProgram(),
    loadAgreements(),
    agreementsStore.fetchSettings(),
  ])
})
watch(language, loadProgram)
watch(activeSection, (value) => {
  router.replace({ query: { ...route.query, tab: value === 'program' ? undefined : value } })
})

async function handlePolicyPublished() {
  await Promise.all([loadProgram(), loadAgreements()])
}

async function copyPublicUrl() {
  try {
    await navigator.clipboard.writeText(publicUrl.value)
    notify.success({ title: t('financing.copiedPublicUrl') })
  } catch {
    notify.error({ title: t('financing.shareFailed') })
  }
}

async function changeLanguage(nextLanguage) {
  if (nextLanguage === language.value) return
  const path = switchLocalePath(nextLanguage === 'en' ? 'en-us' : 'es-co')
  if (path) await navigateTo(path)
}

function formatMoney(value, currency = 'COP') {
  return new Intl.NumberFormat(isEnglish.value ? 'en-US' : 'es-CO', {
    style: 'currency', currency, maximumFractionDigits: 0,
  }).format(Number(value || 0))
}

function formatDate(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(isEnglish.value ? 'en-US' : 'es-CO', { dateStyle: 'medium' }).format(new Date(`${value}T12:00:00`))
}

function modalityLabel(value, fallback = '') {
  if (value === 'five_year') return t('financing.agreement.fiveYearLabel')
  if (value === 'three_year') return t('financing.agreement.threeYearLabel')
  return fallback || value
}
</script>

<template>
  <BasePageShell width="panel">
    <header class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h1 class="text-2xl font-light text-text-default">{{ t('financing.panelTitle') }}</h1>
        <p class="mt-2 max-w-3xl text-sm leading-6 text-text-subtle">{{ t('financing.panelDescription') }}</p>
      </div>
      <BaseButton
        v-if="activeSection === 'agreements'"
        as="NuxtLink"
        :to="localePath('/panel/partnership-program/new')"
        data-testid="financing-new-agreement"
      >{{ t('financing.agreement.newButton') }}</BaseButton>
    </header>

    <BaseSegmented v-model="activeSection" :options="sectionOptions" />

    <template v-if="activeSection === 'program'">
      <section class="mt-6 rounded-2xl border border-border-default bg-surface p-5 shadow-card sm:p-6" aria-labelledby="financing-distribution-title">
        <div class="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <h2 id="financing-distribution-title" class="text-xl font-medium text-text-brand">{{ t('financing.distributionTitle') }}</h2>
              <BaseBadge variant="success">{{ t('financing.publicBadge') }}</BaseBadge>
              <BaseBadge variant="neutral">{{ t('financing.indexableBadge') }}</BaseBadge>
            </div>
            <p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{{ t('financing.distributionDescription') }}</p>
            <label class="mt-5 block text-sm font-medium text-text-default" for="financing-public-url">{{ t('financing.publicUrlLabel') }}</label>
            <BaseInput id="financing-public-url" class="mt-2" :model-value="publicUrl" readonly data-testid="financing-public-url" />
          </div>
          <div class="flex flex-wrap gap-2">
            <BaseButton variant="secondary" data-testid="financing-copy-public-url" @click="copyPublicUrl">{{ t('financing.copyPublicUrl') }}</BaseButton>
            <BaseButton as="NuxtLink" :to="publicPath" target="_blank" rel="noopener noreferrer" data-testid="financing-open-public">{{ t('financing.openPublicView') }}</BaseButton>
            <BaseButton as="a" :to="pdfUrl" variant="secondary" data-testid="financing-panel-download-pdf">{{ t('financing.downloadPdf') }}</BaseButton>
          </div>
        </div>
      </section>

      <div class="mt-5 space-y-3">
        <ExplainerVisibilityToggle
          module="financing"
          i18n-namespace="financing"
          test-id="financing-explainer"
        />
        <ExplainerVideoCard
          v-if="explainer"
          :video="explainer"
          i18n-namespace="financing"
          variant="compact"
          test-id="financing-explainer"
        />
      </div>

      <BaseAlert v-if="program && !program.package.catalog_synced" class="mt-5" variant="warning" data-testid="financing-package-warning">
        <p class="font-medium">{{ t('financing.catalogWarningTitle') }}</p>
        <p class="mt-1 text-sm">{{ t('financing.catalogWarningBody') }}</p>
      </BaseAlert>
      <div v-if="isLoadingProgram && !program" class="flex min-h-64 items-center justify-center" role="status"><span class="h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-primary" /></div>
      <div v-else-if="programLoadError && !program" class="mt-6 rounded-xl border border-danger-strong/30 bg-danger-soft p-6 text-center" role="alert">
        <p class="font-medium text-danger-strong">{{ t('financing.loadError') }}</p>
        <BaseButton class="mt-4" variant="secondary" @click="loadProgram">{{ t('financing.retry') }}</BaseButton>
      </div>
      <section v-else-if="program" class="mt-8 overflow-hidden rounded-2xl border border-border-default" aria-labelledby="financing-preview-title">
        <h2 id="financing-preview-title" class="border-b border-border-default bg-surface px-5 py-4 text-lg font-medium text-text-brand">{{ t('financing.previewTitle') }}</h2>
        <FinancingProgramView :program="program" :download-url="pdfUrl" :language="language" :floating-actions="false" :show-explainer="false" @change-language="changeLanguage" />
      </section>
    </template>

    <template v-else-if="activeSection === 'settings'">
      <VideoResourceManager module="financing" :language="language" />
      <BaseAlert
        v-if="agreementsStore.settingsError && !agreementsStore.financingSettings"
        class="mt-6"
        variant="danger"
        role="alert"
      >
        <p class="font-medium">{{ t('financing.settings.loadError') }}</p>
        <BaseButton class="mt-3" size="sm" variant="secondary" @click="agreementsStore.fetchSettings()">{{ t('financing.settings.retry') }}</BaseButton>
      </BaseAlert>
      <FinancingPolicySettings
        v-else
        :settings="agreementsStore.financingSettings"
        @published="handlePolicyPublished"
      />
    </template>

    <template v-else>
      <div class="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <article class="rounded-xl border border-border-default bg-surface p-4"><p class="text-xs text-text-subtle">{{ t('financing.agreement.stats.activeRecords') }}</p><p class="mt-1 text-2xl font-light text-text-brand">{{ agreementsStore.stats.total_active_records || 0 }}</p></article>
        <article class="rounded-xl border border-border-default bg-surface p-4"><p class="text-xs text-text-subtle">{{ t('financing.agreement.stats.drafts') }}</p><p class="mt-1 text-2xl font-light text-text-brand">{{ agreementsStore.stats.by_status?.draft || 0 }}</p></article>
        <article class="rounded-xl border border-border-default bg-surface p-4"><p class="text-xs text-text-subtle">{{ t('financing.agreement.stats.active') }}</p><p class="mt-1 text-2xl font-light text-text-brand">{{ agreementsStore.stats.by_status?.active || 0 }}</p></article>
        <article class="rounded-xl border border-border-default bg-surface p-4"><p class="text-xs text-text-subtle">{{ t('financing.agreement.stats.archived') }}</p><p class="mt-1 text-2xl font-light text-text-brand">{{ agreementsStore.stats.archived || 0 }}</p></article>
      </div>

      <section class="mt-5 rounded-2xl border border-border-default bg-surface p-4 sm:p-5">
        <form class="grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(14rem,1fr)_12rem_12rem_10rem_auto]" @submit.prevent="loadAgreements">
          <BaseInput v-model="filters.q" :placeholder="t('financing.agreement.searchPlaceholder')" data-testid="financing-agreement-search" />
          <BaseSelect v-model="filters.status" :options="statusOptions" />
          <BaseSelect v-model="filters.modality" :options="modalityOptions" />
          <BaseSelect v-model="filters.archived" :options="archiveOptions" />
          <BaseButton type="submit" variant="secondary" :loading="agreementsStore.isLoading">{{ t('financing.agreement.filters.submit') }}</BaseButton>
        </form>
      </section>

      <div v-if="agreementsStore.error" class="mt-5 rounded-xl bg-danger-soft p-4 text-sm text-danger-strong" role="alert">{{ t('financing.agreement.loadError') }}</div>
      <div v-else-if="agreementsStore.isLoading && !rows.length" class="flex min-h-56 items-center justify-center" role="status"><span class="h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-primary" /></div>
      <section v-else-if="!rows.length" class="mt-5 rounded-2xl border border-dashed border-border-default bg-surface p-10 text-center" data-testid="financing-agreements-empty">
        <h2 class="text-lg font-medium text-text-default">{{ t('financing.agreement.emptyTitle') }}</h2>
        <p class="mt-2 text-sm text-text-subtle">{{ t('financing.agreement.emptyBody') }}</p>
        <BaseButton as="NuxtLink" class="mt-5" :to="localePath('/panel/partnership-program/new')">{{ t('financing.agreement.create') }}</BaseButton>
      </section>
      <div v-else class="mt-5 overflow-hidden rounded-2xl border border-border-default bg-surface">
        <div class="hidden overflow-x-auto md:block">
          <table class="min-w-full divide-y divide-border-default text-left text-sm">
            <thead class="bg-surface-raised text-xs uppercase tracking-wide text-text-subtle"><tr><th class="px-4 py-3">{{ t('financing.agreement.table.addendum') }}</th><th class="px-4 py-3">{{ t('financing.agreement.table.clientProject') }}</th><th class="px-4 py-3">{{ t('financing.agreement.table.modality') }}</th><th class="px-4 py-3">{{ t('financing.agreement.table.balance') }}</th><th class="px-4 py-3">{{ t('financing.agreement.table.status') }}</th><th class="px-4 py-3">{{ t('financing.agreement.table.updated') }}</th></tr></thead>
            <tbody class="divide-y divide-border-muted">
              <tr v-for="row in rows" :key="row.id" class="hover:bg-surface-raised">
                <td class="px-4 py-4"><NuxtLink :to="localePath(`/panel/partnership-program/${row.id}`)" class="font-medium text-text-brand hover:underline" :data-testid="`financing-agreement-row-${row.id}`">{{ row.number || t('financing.agreement.unnumberedDraft') }}</NuxtLink><p class="mt-1 text-xs text-text-subtle">{{ t('financing.agreement.cycle', { number: row.cycle_number }) }}</p></td>
                <td class="px-4 py-4"><p class="font-medium text-text-default">{{ row.client_name }}</p><p class="mt-1 text-xs text-text-subtle">{{ row.project_name }}</p></td>
                <td class="px-4 py-4">{{ modalityLabel(row.modality, row.modality_label) }}</td>
                <td class="px-4 py-4">{{ formatMoney(row.financed_balance, row.currency) }}</td>
                <td class="px-4 py-4"><FinancingAgreementStatusBadge :status="row.status" :label="row.status_label" :archived="row.is_archived" /></td>
                <td class="px-4 py-4 text-text-subtle">{{ formatDate(row.updated_at?.slice(0, 10)) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="divide-y divide-border-muted md:hidden">
          <NuxtLink v-for="row in rows" :key="row.id" :to="localePath(`/panel/partnership-program/${row.id}`)" class="block p-4" :data-testid="`financing-agreement-card-${row.id}`">
            <div class="flex items-start justify-between gap-3"><div><p class="font-medium text-text-brand">{{ row.number || t('financing.agreement.unnumberedDraft') }}</p><p class="mt-1 text-sm text-text-default">{{ row.client_name }}</p></div><FinancingAgreementStatusBadge :status="row.status" :label="row.status_label" :archived="row.is_archived" /></div>
            <p class="mt-3 text-xs text-text-subtle">{{ row.project_name }} · {{ t('financing.agreement.cycle', { number: row.cycle_number }) }} · {{ formatMoney(row.financed_balance, row.currency) }}</p>
          </NuxtLink>
        </div>
      </div>
    </template>
  </BasePageShell>
</template>
