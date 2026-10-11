<script setup>
import { computed } from 'vue';
import { useI18n } from '#imports';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import VersionSummary from './VersionSummary.vue';

const props = defineProps({
  kind: { type: String, required: true, validator: (value) => ['program', 'contract'].includes(value) },
  versions: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  isLoading: { type: Boolean, default: false },
  error: { type: String, default: '' },
});
defineEmits(['load-more', 'retry']);
const { t } = useI18n();
const title = computed(() => t(`buildingOnDemandAdmin.history.${props.kind}Title`));
</script>

<template>
  <section class="min-w-0 rounded-2xl border border-border-default bg-surface p-5 panel-portrait:p-6" :data-testid="`building-on-demand-admin-${kind}-history`" :aria-labelledby="`building-on-demand-admin-${kind}-history-title`">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 :id="`building-on-demand-admin-${kind}-history-title`" class="text-lg font-medium text-text-brand">{{ title }}</h2>
      <p class="text-sm text-text-subtle" :data-testid="`building-on-demand-admin-${kind}-history-count`">{{ t('buildingOnDemandAdmin.history.count', { shown: versions.length, total }) }}</p>
    </div>
    <BaseAlert v-if="error" class="mt-4" variant="danger" :data-testid="`building-on-demand-admin-${kind}-history-error`">
      <p>{{ t('buildingOnDemandAdmin.history.error') }}</p>
      <BaseButton class="mt-3" variant="secondary" :loading="isLoading" :data-testid="`building-on-demand-admin-${kind}-history-retry`" @click="$emit('retry')">
        <BaseActionIcon action="retry" />
        <span>{{ t('buildingOnDemandAdmin.retry') }}</span>
      </BaseButton>
    </BaseAlert>
    <ol v-if="versions.length" class="mt-4 space-y-3">
      <li v-for="version in versions" :key="version.version_id" :data-testid="`building-on-demand-admin-${kind}-version-${version.version_id}`">
        <VersionSummary :summary="version" />
        <p v-if="version.restored_from_version != null" class="mt-2 text-sm text-text-subtle [overflow-wrap:anywhere]">{{ t('buildingOnDemandAdmin.history.restoredFrom', { version: version.restored_from_version }) }}</p>
      </li>
    </ol>
    <p v-else-if="!isLoading && !error" class="mt-4 text-sm text-text-subtle" :data-testid="`building-on-demand-admin-${kind}-history-empty`">{{ t('buildingOnDemandAdmin.history.empty') }}</p>
    <p v-if="isLoading" class="mt-4 text-sm text-text-subtle" role="status">{{ t('buildingOnDemandAdmin.loading') }}</p>
    <BaseButton
      v-if="versions.length < total && !error"
      class="mt-4"
      variant="secondary"
      :loading="isLoading"
      :data-testid="`building-on-demand-admin-${kind}-history-more`"
      @click="$emit('load-more')"
    >{{ t('buildingOnDemandAdmin.history.more') }}</BaseButton>
  </section>
</template>
