<script setup>
import { computed } from 'vue';
import { useI18n } from '#imports';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import BaseBadge from '~/components/base/BaseBadge.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { usePanelNotify } from '~/composables/usePanelNotify';

const props = defineProps({
  publicPaths: { type: Object, default: () => ({}) },
  pdfPaths: { type: Object, default: () => ({}) },
});
const { t } = useI18n();
const notify = usePanelNotify();
const { copyText, feedbackFor } = useClipboardFeedback();
const publicUrls = computed(() => ['es', 'en'].map((language) => ({
  language,
  label: t(`buildingOnDemandAdmin.distribution.${language === 'es' ? 'spanishUrl' : 'englishUrl'}`),
  url: new URL(props.publicPaths[language] || `/${language === 'es' ? 'es-co' : 'en-us'}/building-on-demand`, 'https://projectapp.co').href,
  pdfUrl: props.pdfPaths[language] || `/api/building-on-demand/public/pdf/?lang=${language}`,
})));

async function copyPublicUrl(item) {
  const copied = await copyText({
    key: item.language,
    text: item.url,
    successLabel: t('buildingOnDemandAdmin.distribution.copiedUrl'),
    errorLabel: t('buildingOnDemandAdmin.distribution.copyError'),
    onError: () => notify.error({ title: t('buildingOnDemandAdmin.distribution.copyError') }),
  });
  if (copied) notify.success({ title: t('buildingOnDemandAdmin.distribution.copiedUrl') });
}
</script>

<template>
  <section class="min-w-0 rounded-2xl border border-border-default bg-surface p-5 shadow-card panel-portrait:p-6" aria-labelledby="building-on-demand-admin-distribution-title" data-testid="building-on-demand-admin-distribution">
    <div class="flex flex-wrap items-center gap-2">
      <h2 id="building-on-demand-admin-distribution-title" class="text-xl font-medium text-text-brand">{{ t('buildingOnDemandAdmin.distribution.title') }}</h2>
      <BaseBadge variant="success">{{ t('buildingOnDemandAdmin.distribution.publicBadge') }}</BaseBadge>
      <BaseBadge variant="neutral">{{ t('buildingOnDemandAdmin.distribution.indexableBadge') }}</BaseBadge>
    </div>
    <p class="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{{ t('buildingOnDemandAdmin.distribution.description') }}</p>
    <div class="mt-5 space-y-5">
      <div v-for="item in publicUrls" :key="item.language" class="min-w-0">
        <p :id="`building-on-demand-admin-url-label-${item.language}`" class="text-sm font-medium text-text-default">{{ item.label }}</p>
        <div class="mt-2 flex min-w-0 items-center gap-2">
          <p class="min-w-0 flex-1 break-all rounded-xl border border-input-border bg-surface-raised px-4 py-3 text-sm text-text-default" :data-testid="`building-on-demand-admin-public-url-${item.language}`">{{ item.url }}</p>
          <BaseActionButton
            action="copy"
            :label="`${t('buildingOnDemandAdmin.distribution.copyUrl')}: ${item.label}`"
            :tooltip="t('buildingOnDemandAdmin.distribution.copyUrl')"
            :status-label="feedbackFor(item.language).label"
            :status-tone="feedbackFor(item.language).tone"
            :data-testid="`building-on-demand-admin-copy-public-url-${item.language}`"
            :aria-describedby="`building-on-demand-admin-url-label-${item.language}`"
            @click="copyPublicUrl(item)"
          />
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <BaseButton as="a" :to="item.url" target="_blank" rel="noopener noreferrer" :data-testid="`building-on-demand-admin-open-public-${item.language}`">
            <BaseActionIcon action="open-external" />
            <span>{{ t('buildingOnDemandAdmin.distribution.openPublic') }} · {{ item.language.toUpperCase() }}</span>
          </BaseButton>
          <PanelDownloadLink
            :url="item.pdfUrl"
            :filename="`building-on-demand-${item.language}.pdf`"
            :label="`${t('buildingOnDemandAdmin.distribution.downloadPdf')} · ${item.language.toUpperCase()}`"
            size="md"
            :data-testid="`building-on-demand-admin-download-pdf-${item.language}`"
          />
        </div>
      </div>
    </div>
  </section>
</template>
