<script setup>
import { computed, ref } from 'vue'
import { useAdditionalModulesPublicAccess } from '~/composables/useAdditionalModulesPublicAccess'
import { formatDateTime } from '~/utils/formatDate'

const props = defineProps({
  language: {
    type: String,
    default: 'es',
    validator: (value) => ['es', 'en'].includes(value),
  },
  stats: { type: Object, default: null },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['share', 'customize-pdf', 'tracking', 'manage'])
const { t } = useI18n()
const feedback = ref(null)

const {
  publicPath,
  publicUrl,
  isDownloading,
  copyPublicUrl,
  downloadFullPdf,
} = useAdditionalModulesPublicAccess('es')

const heading = computed(() => t(
  props.compact
    ? 'additionalModules.dashboardSectionTitle'
    : 'additionalModules.quickAccessTitle',
))
const description = computed(() => t(
  props.compact
    ? 'additionalModules.dashboardSectionDescription'
    : 'additionalModules.quickAccessDescription',
))
const lastOpened = computed(() => {
  const value = props.stats?.last_viewed_at
  if (!value) return t('additionalModules.noOpeningsYet')
  return formatDateTime(value, { locale: props.language })
})

function selectUrl(event) {
  event.target?.select?.()
}

async function handleCopy() {
  const success = await copyPublicUrl()
  feedback.value = success
    ? { variant: 'success', title: t('additionalModules.publicUrlCopied'), body: '' }
    : {
        variant: 'warning',
        title: t('additionalModules.copyFailedTitle'),
        body: t('additionalModules.copyFailedBody'),
      }
}

async function handleDownload() {
  feedback.value = null
  const success = await downloadFullPdf()
  if (!success) {
    feedback.value = {
      variant: 'danger',
      title: t('additionalModules.pdfDownloadErrorTitle'),
      body: t('additionalModules.pdfError'),
    }
  }
}
</script>

<template>
  <section
    class="rounded-2xl border border-border-default bg-surface-raised p-4 shadow-card sm:p-6"
    data-testid="additional-modules-quick-access"
  >
    <header class="flex flex-col gap-4 panel-portrait:flex-row panel-portrait:items-start panel-portrait:justify-between">
      <div class="min-w-0">
        <p class="text-xs font-medium uppercase tracking-wider text-text-brand">
          {{ t('additionalModules.quickAccessEyebrow') }}
        </p>
        <h2 class="mt-1 text-xl font-medium text-text-default">{{ heading }}</h2>
        <p class="mt-1 max-w-3xl text-sm leading-6 text-text-muted">{{ description }}</p>
      </div>
      <BaseButton
        v-if="compact"
        variant="secondary"
        size="sm"
        data-testid="additional-modules-manage"
        @click="emit('manage')"
      >
        <BaseActionIcon action="settings" />
        {{ t('additionalModules.manageCatalog') }}
      </BaseButton>
    </header>

    <dl
      v-if="stats"
      class="mt-5 grid grid-cols-2 gap-3 panel-portrait:grid-cols-4"
      data-testid="additional-modules-stats"
    >
      <div class="rounded-xl border border-border-muted bg-surface px-3 py-3">
        <dt class="text-xs text-text-muted">{{ t('additionalModules.activeModulesMetric') }}</dt>
        <dd class="mt-1 text-xl font-light tabular-nums text-text-brand" data-testid="additional-modules-active-count">
          {{ stats.active_module_count ?? 0 }}
        </dd>
      </div>
      <div class="rounded-xl border border-border-muted bg-surface px-3 py-3">
        <dt class="text-xs text-text-muted">{{ t('additionalModules.activeLinksMetric') }}</dt>
        <dd class="mt-1 text-xl font-light tabular-nums text-text-brand" data-testid="additional-modules-active-share-count">
          {{ stats.active_share_count ?? 0 }}
        </dd>
      </div>
      <div class="rounded-xl border border-border-muted bg-surface px-3 py-3">
        <dt class="text-xs text-text-muted">{{ t('additionalModules.unopenedLinksMetric') }}</dt>
        <dd class="mt-1 text-xl font-light tabular-nums text-text-brand" data-testid="additional-modules-unopened-count">
          {{ stats.unopened_active_share_count ?? 0 }}
        </dd>
      </div>
      <div class="rounded-xl border border-border-muted bg-surface px-3 py-3">
        <dt class="text-xs text-text-muted">{{ t('additionalModules.lastOpenedMetric') }}</dt>
        <dd class="mt-1 break-words text-sm font-medium text-text-default" data-testid="additional-modules-last-opened">
          {{ lastOpened }}
        </dd>
      </div>
    </dl>

    <div class="mt-5 grid grid-cols-1 gap-4 panel-desktop:grid-cols-3">
      <article class="flex min-w-0 flex-col rounded-xl border border-border-muted bg-surface p-4">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <h3 class="font-medium text-text-brand">{{ t('additionalModules.fullCatalogTitle') }}</h3>
          <div class="flex flex-wrap gap-1.5">
            <BaseBadge variant="success" size="sm">{{ t('additionalModules.publicBadge') }}</BaseBadge>
            <BaseBadge variant="info" size="sm">{{ t('additionalModules.indexableBadge') }}</BaseBadge>
            <BaseBadge variant="neutral" size="sm">{{ t('additionalModules.noTrackingBadge') }}</BaseBadge>
          </div>
        </div>
        <p class="mt-2 flex-1 text-sm leading-6 text-text-muted">
          {{ t('additionalModules.fullCatalogDescription') }}
        </p>
        <label class="mt-4 block text-xs font-medium text-text-default" for="additional-modules-public-url">
          {{ t('additionalModules.canonicalUrlLabel') }}
        </label>
        <BaseInput
          id="additional-modules-public-url"
          :model-value="publicUrl"
          class="mt-1 w-full"
          readonly
          data-testid="additional-modules-public-url"
          @focus="selectUrl"
        />
        <div class="mt-3 flex flex-wrap gap-2">
          <BaseButton
            variant="secondary"
            size="sm"
            data-testid="additional-modules-copy-public-url"
            @click="handleCopy"
          >
            <BaseActionIcon action="copy" />
            {{ t('additionalModules.copyPublicUrl') }}
          </BaseButton>
          <BaseButton
            as="a"
            :to="publicPath"
            target="_blank"
            rel="noopener noreferrer"
            variant="secondary"
            size="sm"
            data-testid="additional-modules-open-public"
          >
            <BaseActionIcon action="open-external" />
            {{ t('additionalModules.openAsClient') }}
          </BaseButton>
        </div>
      </article>

      <article class="flex min-w-0 flex-col rounded-xl border border-border-muted bg-surface p-4">
        <div class="flex flex-wrap items-start justify-between gap-2">
          <h3 class="font-medium text-text-brand">{{ t('additionalModules.selectedCatalogTitle') }}</h3>
          <div class="flex flex-wrap gap-1.5">
            <BaseBadge variant="accent" size="sm">{{ t('additionalModules.linkAccessBadge') }}</BaseBadge>
            <BaseBadge variant="neutral" size="sm">{{ t('additionalModules.noindexBadge') }}</BaseBadge>
            <BaseBadge variant="info" size="sm">{{ t('additionalModules.trackingBadge') }}</BaseBadge>
          </div>
        </div>
        <p class="mt-2 flex-1 text-sm leading-6 text-text-muted">
          {{ t('additionalModules.selectedCatalogDescription') }}
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <BaseButton
            size="sm"
            data-testid="additional-modules-create-share"
            @click="emit('share')"
          >
            <BaseActionIcon action="link" />
            {{ t('additionalModules.prepareSelection') }}
          </BaseButton>
          <BaseButton
            variant="secondary"
            size="sm"
            data-testid="additional-modules-tracking"
            @click="emit('tracking')"
          >
            <BaseActionIcon action="stats" />
            {{ t('additionalModules.viewTracking') }}
          </BaseButton>
        </div>
      </article>

      <article class="flex min-w-0 flex-col rounded-xl border border-border-muted bg-surface p-4">
        <h3 class="font-medium text-text-brand">{{ t('additionalModules.fullPdfTitle') }}</h3>
        <p class="mt-2 flex-1 text-sm leading-6 text-text-muted">
          {{ t('additionalModules.fullPdfDescription') }}
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <BaseButton
            size="sm"
            :loading="isDownloading"
            data-testid="additional-modules-download-full-pdf"
            @click="handleDownload"
          >
            <BaseActionIcon action="download" />
            {{ t('additionalModules.downloadFullPdf') }}
          </BaseButton>
          <BaseButton
            variant="secondary"
            size="sm"
            data-testid="additional-modules-customize-pdf"
            @click="emit('customize-pdf')"
          >
            <BaseActionIcon action="settings" />
            {{ t('additionalModules.customizePdf') }}
          </BaseButton>
        </div>
      </article>
    </div>

    <BaseAlert
      v-if="feedback"
      class="mt-4"
      :variant="feedback.variant"
      :title="feedback.title"
      dismissible
      @dismiss="feedback = null"
    >
      {{ feedback.body }}
    </BaseAlert>
  </section>
</template>
