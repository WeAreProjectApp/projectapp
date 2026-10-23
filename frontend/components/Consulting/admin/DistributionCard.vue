<script setup>
import { computed } from 'vue';
import { useI18n } from '#imports';
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { consultingPdfUrl, consultingPublicUrl } from '~/utils/consulting';

const props = defineProps({ language: { type: String, default: 'es' } });
const { t } = useI18n();
const notify = usePanelNotify();
const publicUrls = computed(() => [
  { language: 'es', label: t('consultingAdmin.distribution.spanishUrl'), url: consultingPublicUrl('es') },
  { language: 'en', label: t('consultingAdmin.distribution.englishUrl'), url: consultingPublicUrl('en') },
]);

async function copyPublicUrl(url) {
  try {
    await navigator.clipboard.writeText(url);
    notify.success({ title: t('consultingAdmin.distribution.copiedUrl') });
  } catch {
    notify.error({ title: t('consultingAdmin.distribution.copyError') });
  }
}
</script>

<template>
  <section class="min-w-0 rounded-2xl border border-border-default bg-surface p-5 shadow-card panel-portrait:p-6" aria-labelledby="consulting-distribution-title">
    <div class="flex flex-wrap items-center gap-2">
      <h2 id="consulting-distribution-title" class="text-xl font-medium text-text-brand">{{ t('consultingAdmin.distribution.title') }}</h2>
      <BaseBadge variant="success">{{ t('consultingAdmin.distribution.publicBadge') }}</BaseBadge>
      <BaseBadge variant="neutral">{{ t('consultingAdmin.distribution.indexableBadge') }}</BaseBadge>
    </div>
    <p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{{ t('consultingAdmin.distribution.description') }}</p>
    <div class="mt-5 space-y-4">
      <div v-for="item in publicUrls" :key="item.language" class="min-w-0">
        <p :id="`consulting-url-label-${item.language}`" class="text-sm font-medium text-text-default">{{ item.label }}</p>
        <div class="mt-2 flex min-w-0 flex-col gap-2 panel-portrait:flex-row panel-portrait:items-center">
          <p class="min-w-0 flex-1 break-all rounded-xl border border-input-border bg-surface-raised px-4 py-3 text-sm text-text-default" :data-testid="`consulting-public-url-${item.language}`">{{ item.url }}</p>
          <BaseButton
            variant="secondary"
            :data-testid="`consulting-copy-public-url-${item.language}`"
            :aria-describedby="`consulting-url-label-${item.language}`"
            @click="copyPublicUrl(item.url)"
          >{{ t('consultingAdmin.distribution.copyUrl') }}</BaseButton>
        </div>
      </div>
    </div>
    <div class="mt-5 flex flex-wrap gap-2">
      <BaseButton as="a" :to="consultingPublicUrl('es')" target="_blank" rel="noopener noreferrer" data-testid="consulting-open-public">{{ t('consultingAdmin.distribution.openPublic') }}</BaseButton>
      <PanelDownloadLink
        :url="consultingPdfUrl(props.language)"
        :filename="`consulting-${props.language}.pdf`"
        :label="t('consultingAdmin.distribution.downloadPdf')"
        size="md"
        data-testid="consulting-panel-download-pdf"
      />
    </div>
  </section>
</template>
