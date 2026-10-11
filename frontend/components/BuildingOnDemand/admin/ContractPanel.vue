<script setup>
import { computed } from 'vue';
import { useI18n, useLocalePath } from '#imports';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseBadge from '~/components/base/BaseBadge.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import DocumentMarkdownBody from '~/components/panel/documents/DocumentMarkdownBody.vue';
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
import { formatDateTime } from '~/utils/formatDate';
import { normalizeMirrorStatus } from '~/stores/building_on_demand';
import VersionSummary from './VersionSummary.vue';

const props = defineProps({
  contract: { type: Object, default: null },
  mirror: { type: Object, default: null },
  isLoading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  unavailable: { type: Boolean, default: false },
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
  fallback: t('buildingOnDemandAdmin.metadata.unavailable'),
}));
</script>

<template>
  <section class="min-w-0 rounded-2xl border border-border-default bg-surface p-5 panel-portrait:p-6" aria-labelledby="building-on-demand-admin-contract-title" data-testid="building-on-demand-admin-contract">
    <h2 id="building-on-demand-admin-contract-title" class="text-xl font-medium text-text-brand">{{ t('buildingOnDemandAdmin.contract.title') }}</h2>
    <p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{{ t('buildingOnDemandAdmin.contract.description') }}</p>
    <p v-if="unavailable && !contract" class="mt-5 text-sm text-text-subtle" data-testid="building-on-demand-admin-contract-unavailable">{{ t('buildingOnDemandAdmin.contract.empty') }}</p>
    <BaseAlert v-else-if="error" class="mt-5" variant="danger" data-testid="building-on-demand-admin-contract-error">
      <p>{{ t('buildingOnDemandAdmin.contract.error') }}</p>
      <BaseButton class="mt-3" variant="secondary" :loading="isLoading" data-testid="building-on-demand-admin-contract-retry" @click="$emit('retry')">
        <BaseActionIcon action="retry" />
        <span>{{ t('buildingOnDemandAdmin.retry') }}</span>
      </BaseButton>
    </BaseAlert>
    <div v-else-if="isLoading && !contract" class="mt-5 space-y-3" role="status" :aria-label="t('buildingOnDemandAdmin.loading')" data-testid="building-on-demand-admin-contract-loading">
      <div class="h-6 w-1/2 animate-pulse rounded bg-surface-raised" />
      <div class="h-40 animate-pulse rounded-xl bg-surface-raised" />
    </div>
    <template v-else-if="contract">
      <VersionSummary class="mt-5" :summary="contract" test-id="building-on-demand-admin-contract-version" />
      <div class="mt-5 min-w-0 rounded-xl border border-border-default p-4" data-testid="building-on-demand-admin-contract-mirror">
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="text-base font-medium text-text-default">{{ t('buildingOnDemandAdmin.contract.mirrorTitle') }}</h3>
          <BaseBadge :variant="badgeVariant" :textPolicy="'wrap'" data-testid="building-on-demand-admin-contract-status">{{ t(`buildingOnDemandAdmin.contract.status.${mirrorStatus}`) }}</BaseBadge>
        </div>
        <p class="mt-2 text-sm text-text-subtle [overflow-wrap:anywhere]">{{ documentMirror?.folder_path || t('buildingOnDemandAdmin.contract.mirrorFolder') }}</p>
        <p v-if="documentMirror?.title" class="mt-2 text-sm text-text-default [overflow-wrap:anywhere]">{{ documentMirror.title }}</p>
        <p v-if="documentMirror?.version != null" class="mt-2 text-sm text-text-subtle">{{ t('buildingOnDemandAdmin.contract.mirrorVersion', { version: documentMirror.version }) }}</p>
        <dl v-if="documentMirror?.last_synced_at" class="mt-2 text-sm">
          <dt class="text-text-subtle">{{ t('buildingOnDemandAdmin.contract.mirrorUpdated') }}</dt>
          <dd class="mt-1 text-text-default">{{ lastSyncedLabel }}</dd>
        </dl>
        <BaseButton
          v-if="documentMirror?.document_id"
          as="NuxtLink"
          :to="localePath(`/panel/documents/${documentMirror.document_id}/edit`)"
          class="mt-4"
          variant="secondary"
          :textPolicy="'wrap'"
          data-testid="building-on-demand-admin-mirror-link"
        >{{ t('buildingOnDemandAdmin.contract.mirrorLink') }}</BaseButton>
      </div>
      <BaseAlert v-if="warningKey" class="mt-4" variant="warning" data-testid="building-on-demand-admin-mirror-alert">{{ t(`buildingOnDemandAdmin.contract.${warningKey}`) }}</BaseAlert>
      <div class="mt-5 flex flex-wrap gap-2">
        <BaseButton as="a" to="/api/building-on-demand/admin/contract/pdf/?inline=1" target="_blank" rel="noopener noreferrer" variant="secondary" data-testid="building-on-demand-admin-contract-view-pdf">
          <BaseActionIcon action="view" />
          <span>{{ t('buildingOnDemandAdmin.contract.viewPdf') }}</span>
        </BaseButton>
        <PanelDownloadLink
          url="/api/building-on-demand/admin/contract/pdf/"
          filename="building-on-demand-contract.pdf"
          :label="t('buildingOnDemandAdmin.contract.downloadPdf')"
          size="md"
          data-testid="building-on-demand-admin-contract-download-pdf"
        />
      </div>
      <h3 id="building-on-demand-admin-contract-body-title" class="mt-6 text-base font-medium text-text-default">{{ t('buildingOnDemandAdmin.contract.bodyTitle') }}</h3>
      <p id="building-on-demand-admin-contract-scroll-hint" class="mt-2 text-sm text-text-subtle">{{ t('buildingOnDemandAdmin.contract.scrollHint') }}</p>
      <div
        class="mt-3 min-w-0 max-w-full overflow-x-auto rounded-xl border border-border-default p-4"
        role="region"
        tabindex="0"
        aria-labelledby="building-on-demand-admin-contract-body-title"
        aria-describedby="building-on-demand-admin-contract-scroll-hint"
        data-testid="building-on-demand-admin-contract-body"
      >
        <DocumentMarkdownBody :markdown="contract.markdown || ''" standard-markdown />
      </div>
    </template>
    <p v-else class="mt-5 text-sm text-text-subtle" data-testid="building-on-demand-admin-contract-unavailable">{{ t('buildingOnDemandAdmin.contract.empty') }}</p>
  </section>
</template>
