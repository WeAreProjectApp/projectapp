<script setup>
import { computed } from 'vue';
import { useI18n } from '#imports';
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { buildingWithUsPdfUrl, buildingWithUsPublicUrl } from '~/utils/buildingWithUs';

const props = defineProps({ language: { type: String, default: 'es' } });
const { t } = useI18n();
const notify = usePanelNotify();
const publicUrls = computed(() => [
  { language: 'es', label: t('buildingWithUsAdmin.distribution.spanishUrl'), url: buildingWithUsPublicUrl('es') },
  { language: 'en', label: t('buildingWithUsAdmin.distribution.englishUrl'), url: buildingWithUsPublicUrl('en') },
]);

async function copyPublicUrl(url) {
  try {
    await navigator.clipboard.writeText(url);
    notify.success({ title: t('buildingWithUsAdmin.distribution.copiedUrl') });
  } catch {
    notify.error({ title: t('buildingWithUsAdmin.distribution.copyError') });
  }
}
</script>

<template>
  <section class="min-w-0 rounded-2xl border border-border-default bg-surface p-5 shadow-card panel-portrait:p-6" aria-labelledby="building-with-us-distribution-title">
    <div class="flex flex-wrap items-center gap-2">
      <h2 id="building-with-us-distribution-title" class="text-xl font-medium text-text-brand">{{ t('buildingWithUsAdmin.distribution.title') }}</h2>
      <BaseBadge variant="success">{{ t('buildingWithUsAdmin.distribution.publicBadge') }}</BaseBadge>
      <BaseBadge variant="neutral">{{ t('buildingWithUsAdmin.distribution.indexableBadge') }}</BaseBadge>
    </div>
    <p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{{ t('buildingWithUsAdmin.distribution.description') }}</p>
    <div class="mt-5 space-y-4">
      <div v-for="item in publicUrls" :key="item.language" class="min-w-0">
        <p :id="`building-with-us-url-label-${item.language}`" class="text-sm font-medium text-text-default">{{ item.label }}</p>
        <div class="mt-2 flex min-w-0 flex-col gap-2 panel-portrait:flex-row panel-portrait:items-center">
          <p class="min-w-0 flex-1 break-all rounded-xl border border-input-border bg-surface-raised px-4 py-3 text-sm text-text-default" :data-testid="`building-with-us-public-url-${item.language}`">{{ item.url }}</p>
          <BaseButton
            variant="secondary"
            :data-testid="`building-with-us-copy-public-url-${item.language}`"
            :aria-describedby="`building-with-us-url-label-${item.language}`"
            @click="copyPublicUrl(item.url)"
          >{{ t('buildingWithUsAdmin.distribution.copyUrl') }}</BaseButton>
        </div>
      </div>
    </div>
    <div class="mt-5 flex flex-wrap gap-2">
      <BaseButton as="a" :to="buildingWithUsPublicUrl('es')" target="_blank" rel="noopener noreferrer" data-testid="building-with-us-open-public">{{ t('buildingWithUsAdmin.distribution.openPublic') }}</BaseButton>
      <PanelDownloadLink
        :url="buildingWithUsPdfUrl(props.language)"
        :filename="`building-with-us-${props.language}.pdf`"
        :label="t('buildingWithUsAdmin.distribution.downloadPdf')"
        size="md"
        data-testid="building-with-us-panel-download-pdf"
      />
    </div>
  </section>
</template>
