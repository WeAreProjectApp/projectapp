<script setup>
import { computed } from 'vue';
import { useI18n } from '#imports';
import ConsultingAdminVersionSummary from './VersionSummary.vue';

const props = defineProps({
  kind: { type: String, default: 'program', validator: (value) => value === 'program' },
  versions: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  isLoading: { type: Boolean, default: false },
  error: { type: String, default: '' },
});
defineEmits(['load-more', 'retry']);
const { t } = useI18n();
const title = computed(() => t(`consultingAdmin.history.${props.kind}Title`));
</script>

<template>
  <section class="min-w-0 rounded-2xl border border-border-default bg-surface p-5 panel-portrait:p-6" :data-testid="`consulting-${kind}-history`" :aria-labelledby="`consulting-${kind}-history-title`">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 :id="`consulting-${kind}-history-title`" class="text-lg font-medium text-text-brand">{{ title }}</h2>
      <p class="text-sm text-text-subtle">{{ t('consultingAdmin.history.count', { shown: versions.length, total }) }}</p>
    </div>
    <BaseAlert v-if="error" class="mt-4" variant="danger" :data-testid="`consulting-${kind}-history-error`">
      <p>{{ t('consultingAdmin.history.error') }}</p>
      <BaseButton class="mt-3" variant="secondary" :loading="isLoading" :data-testid="`consulting-${kind}-history-retry`" @click="$emit('retry')">{{ t('consultingAdmin.retry') }}</BaseButton>
    </BaseAlert>
    <ol v-if="versions.length" class="mt-4 space-y-3">
      <li v-for="version in versions" :key="version.version_id" :data-testid="`consulting-${kind}-version-${version.version_id}`">
        <ConsultingAdminVersionSummary :summary="version" />
        <p v-if="version.restored_from_version != null" class="mt-2 break-words text-sm text-text-subtle">{{ t('consultingAdmin.history.restoredFrom', { version: version.restored_from_version }) }}</p>
      </li>
    </ol>
    <p v-else-if="!isLoading && !error" class="mt-4 text-sm text-text-subtle">{{ t('consultingAdmin.history.empty') }}</p>
    <p v-if="isLoading" class="mt-4 text-sm text-text-subtle" role="status">{{ t('consultingAdmin.loading') }}</p>
    <BaseButton
      v-if="versions.length < total && !error"
      class="mt-4"
      variant="secondary"
      :loading="isLoading"
      :data-testid="`consulting-${kind}-history-more`"
      @click="$emit('load-more')"
    >{{ t('consultingAdmin.history.more') }}</BaseButton>
  </section>
</template>
