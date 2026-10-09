<script setup>
import { computed } from 'vue';
import { useI18n } from '#imports';
import { formatDateTime } from '~/utils/formatDate';

const props = defineProps({
  summary: { type: Object, default: null },
  testId: { type: String, default: '' },
});
const { t, locale } = useI18n();
const authorLabel = computed(() => {
  const author = props.summary?.author;
  return (typeof author === 'string' ? author : author?.name || author?.display_name || author?.email)
    || t('buildingWithUsAdmin.metadata.unavailable');
});
const updatedLabel = computed(() => formatDateTime(props.summary?.updated_at || props.summary?.created_at, {
  locale: locale.value.startsWith('en') ? 'en' : 'es',
  fallback: t('buildingWithUsAdmin.metadata.unavailable'),
}));
</script>

<template>
  <article class="min-w-0 rounded-xl border border-border-default bg-surface p-5" :data-testid="testId || undefined">
    <template v-if="summary">
      <p class="text-base font-medium text-text-brand">{{ t('buildingWithUsAdmin.metadata.versionValue', { version: summary.version ?? t('buildingWithUsAdmin.metadata.unavailable') }) }}</p>
      <dl class="mt-3 grid gap-3 text-sm panel-portrait:grid-cols-2">
        <div class="min-w-0">
          <dt class="text-text-subtle">{{ t('buildingWithUsAdmin.metadata.updated') }}</dt>
          <dd class="mt-1 break-words text-text-default">{{ updatedLabel }}</dd>
        </div>
        <div class="min-w-0">
          <dt class="text-text-subtle">{{ t('buildingWithUsAdmin.metadata.author') }}</dt>
          <dd class="mt-1 break-words text-text-default">{{ authorLabel }}</dd>
        </div>
        <div class="min-w-0 panel-portrait:col-span-2">
          <dt class="text-text-subtle">{{ t('buildingWithUsAdmin.metadata.changeNote') }}</dt>
          <dd class="mt-1 break-words whitespace-pre-wrap text-text-default">{{ summary.change_note || t('buildingWithUsAdmin.metadata.noChangeNote') }}</dd>
        </div>
      </dl>
    </template>
    <p v-else class="text-sm text-text-subtle">{{ t('buildingWithUsAdmin.metadata.noVersion') }}</p>
  </article>
</template>
