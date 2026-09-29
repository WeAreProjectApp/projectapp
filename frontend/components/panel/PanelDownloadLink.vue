<script setup>
import { watch } from 'vue';
import { useI18n } from '#imports';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import { usePanelDownload } from '~/composables/usePanelDownload';

const props = defineProps({
  url: { type: String, required: true },
  filename: { type: String, default: '' },
  label: { type: String, default: '' },
  expectedType: { type: String, default: 'application/pdf' },
  as: { type: String, default: 'a' },
  variant: { type: String, default: 'secondary' },
  size: { type: String, default: 'sm' },
});
const { t } = useI18n();
const { loading, download, cancel } = usePanelDownload();
watch(() => props.url, cancel);
</script>

<template>
  <BaseButton
    :as="as"
    :to="url"
    :download="as === 'a' ? filename : undefined"
    :variant="variant"
    :size="size"
    :loading="loading"
    :aria-busy="loading"
    :aria-disabled="loading || undefined"
    @click.prevent="download(url, filename, expectedType)"
  >
    <BaseActionIcon v-if="!loading" action="download" />
    <span>{{ loading ? t('pwa.download.loading') : (label || t('pwa.download.pdf')) }}</span>
  </BaseButton>
</template>
