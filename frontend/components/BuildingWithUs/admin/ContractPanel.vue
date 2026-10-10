<script setup>
import { computed } from 'vue';
import { useI18n, useLocalePath } from '#imports';
import DocumentMarkdownBody from '~/components/panel/documents/DocumentMarkdownBody.vue';
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
import { formatDateTime } from '~/utils/formatDate';
import { normalizeMirrorStatus } from '~/stores/building_with_us';
import BuildingWithUsAdminVersionSummary from './VersionSummary.vue';

const props = defineProps({
  contract: { type: Object, default: null },
  mirror: { type: Object, default: null },
  isLoading: { type: Boolean, default: false },
  error: { type: String, default: '' },
});
defineEmits(['retry']);
const { t, locale } = useI18n();
const localePath = useLocalePath();
const documentMirror = computed(() => props.mirror || props.contract?.mirror || null);
const mirrorStatus = computed(() => normalizeMirrorStatus(documentMirror.value?.status));
const badgeVariant = computed(() => {
  if (mirrorStatus.value === 'synchronized') return 'success';
  if (mirrorStatus.value === 'out_of_sync') return 'warning';
  return 'neutral';
});
const warningKey = computed(() => ({
  out_of_sync: 'outOfSync',
  not_initialized: 'notInitialized',
}[mirrorStatus.value]));
const lastSyncedLabel = computed(() => formatDateTime(documentMirror.value?.last_synced_at, {
  locale: locale.value.startsWith('en') ? 'en' : 'es',
  fallback: t('buildingWithUsAdmin.metadata.unavailable'),
}));
</script>

<template>
  <section class="min-w-0 rounded-2xl border border-border-default bg-surface p-5 panel-portrait:p-6" aria-labelledby="building-with-us-contract-title">
    <h2 id="building-with-us-contract-title" class="text-xl font-medium text-text-brand">{{ t('buildingWithUsAdmin.contract.title') }}</h2>
    <p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{{ t('buildingWithUsAdmin.contract.description') }}</p>
    <BaseAlert v-if="error" class="mt-5" variant="danger" data-testid="building-with-us-contract-error">
      <p>{{ t('buildingWithUsAdmin.contract.error') }}</p>
      <BaseButton class="mt-3" variant="secondary" :loading="isLoading" data-testid="building-with-us-contract-retry" @click="$emit('retry')">{{ t('buildingWithUsAdmin.retry') }}</BaseButton>
    </BaseAlert>
    <div v-else-if="isLoading && !contract" class="mt-5 space-y-3" role="status" :aria-label="t('buildingWithUsAdmin.loading')">
      <div class="h-6 w-1/2 animate-pulse rounded bg-surface-raised" />
      <div class="h-40 animate-pulse rounded-xl bg-surface-raised" />
    </div>
    <template v-else>
      <BuildingWithUsAdminVersionSummary v-if="contract" class="mt-5" :summary="contract" test-id="building-with-us-contract-version" />
      <p v-else class="mt-5 text-sm text-text-subtle">{{ t('buildingWithUsAdmin.contract.empty') }}</p>
      <div class="mt-5 rounded-xl border border-border-default p-4">
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="text-base font-medium text-text-default">{{ t('buildingWithUsAdmin.contract.mirrorTitle') }}</h3>
          <BaseBadge :variant="badgeVariant" data-testid="building-with-us-mirror-status">{{ t(`buildingWithUsAdmin.contract.status.${mirrorStatus}`) }}</BaseBadge>
        </div>
        <p class="mt-2 break-words text-sm text-text-subtle">{{ documentMirror?.folder_path || t('buildingWithUsAdmin.contract.mirrorFolder') }}</p>
        <p v-if="documentMirror?.title" class="mt-2 break-words text-sm text-text-default">{{ documentMirror.title }}</p>
        <p v-if="documentMirror?.version != null" class="mt-2 text-sm text-text-subtle">{{ t('buildingWithUsAdmin.contract.mirrorVersion', { version: documentMirror.version }) }}</p>
        <dl v-if="documentMirror?.last_synced_at" class="mt-2 text-sm">
          <dt class="text-text-subtle">{{ t('buildingWithUsAdmin.contract.mirrorUpdated') }}</dt>
          <dd class="mt-1 text-text-default">{{ lastSyncedLabel }}</dd>
        </dl>
        <BaseButton
          v-if="documentMirror?.document_id"
          as="NuxtLink"
          :to="localePath(`/panel/documents/${documentMirror.document_id}/edit`)"
          class="mt-4"
          variant="secondary"
          :textPolicy="'wrap'"
          data-testid="building-with-us-mirror-link"
        >{{ t('buildingWithUsAdmin.contract.mirrorLink') }}</BaseButton>
      </div>
      <BaseAlert v-if="warningKey" class="mt-4" variant="warning" data-testid="building-with-us-mirror-alert">{{ t(`buildingWithUsAdmin.contract.${warningKey}`) }}</BaseAlert>
      <PanelDownloadLink
        v-if="contract"
        class="mt-5"
        url="/api/building-with-us/admin/contract/pdf/"
        filename="building-with-us-contract.pdf"
        :label="t('buildingWithUsAdmin.contract.downloadPdf')"
        size="md"
        data-testid="building-with-us-contract-download-pdf"
      />
      <template v-if="contract">
        <h3 id="building-with-us-contract-body-title" class="mt-6 text-base font-medium text-text-default">{{ t('buildingWithUsAdmin.contract.bodyTitle') }}</h3>
        <p id="building-with-us-contract-scroll-hint" class="mt-2 text-sm text-text-subtle">{{ t('buildingWithUsAdmin.contract.scrollHint') }}</p>
        <div
          class="mt-3 min-w-0 overflow-x-auto rounded-xl border border-border-default p-4"
          role="region"
          tabindex="0"
          aria-labelledby="building-with-us-contract-body-title"
          aria-describedby="building-with-us-contract-scroll-hint"
          data-testid="building-with-us-contract-body"
        >
          <DocumentMarkdownBody :markdown="contract.markdown || ''" standard-markdown />
        </div>
      </template>
    </template>
  </section>
</template>
