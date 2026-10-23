<script setup>
import { onMounted } from 'vue';
import { useConsultingStore } from '~/stores/consulting';
import { consultingPdfUrl } from '~/utils/consulting';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });
const { t } = useI18n();
const store = useConsultingStore();
onMounted(() => Promise.all([store.fetchOverview(), store.fetchPreview('es'), store.fetchVersions()]));
</script>

<template>
  <BasePageShell width="panel">
    <header class="mb-6">
      <h1 class="text-2xl font-light text-text-default">{{ t('consultingAdmin.title') }}</h1>
      <p class="mt-2 max-w-3xl text-sm leading-6 text-text-subtle">{{ t('consultingAdmin.subtitle') }}</p>
    </header>
    <div class="min-w-0 space-y-5">
      <ConsultingAdminDistributionCard :language="store.previewLanguage" />
      <p class="max-w-3xl text-sm leading-6 text-text-subtle">{{ t('consultingAdmin.mcpHint') }}</p>
      <BaseAlert v-if="store.overviewError" variant="danger" data-testid="consulting-overview-error">
        <p>{{ t('consultingAdmin.overviewError') }}</p>
        <BaseButton class="mt-3" variant="secondary" @click="store.fetchOverview()">{{ t('consultingAdmin.retry') }}</BaseButton>
      </BaseAlert>
      <p v-else-if="store.isLoadingOverview" role="status">{{ t('consultingAdmin.loading') }}</p>
      <ConsultingAdminVersionSummary v-else :summary="store.programSummary" test-id="consulting-program-version" />
      <ConsultingAdminVersionHistory :versions="store.history.versions" :total="store.history.total" :is-loading="store.history.isLoading" :error="store.history.error" @load-more="store.fetchVersions({ append: true })" @retry="store.fetchVersions({ append: store.history.versions.length > 0 })" />
      <section class="min-w-0 overflow-hidden rounded-2xl border border-border-default bg-surface" aria-labelledby="consulting-preview-title" data-testid="consulting-preview">
        <h2 id="consulting-preview-title" class="border-b border-border-default px-5 py-4 text-lg font-medium text-text-brand">{{ t('consultingAdmin.previewTitle') }}</h2>
        <div class="p-5">
          <BaseSegmented :model-value="store.previewLanguage" :options="[{ value: 'es', label: 'Español', testId: 'consulting-preview-es' }, { value: 'en', label: 'English', testId: 'consulting-preview-en' }]" @update:model-value="store.fetchPreview($event)" />
        </div>
        <p v-if="store.isLoadingPreview" class="p-5" role="status">{{ t('consultingAdmin.loading') }}</p>
        <BaseAlert v-else-if="store.previewError" class="m-5" variant="danger" data-testid="consulting-preview-error">
          <p>{{ t('consultingAdmin.previewError') }}</p>
          <BaseButton class="mt-3" variant="secondary" @click="store.fetchPreview(store.previewLanguage)">{{ t('consultingAdmin.retry') }}</BaseButton>
        </BaseAlert>
        <ConsultingProgramView v-else-if="store.preview" :program="store.preview" :language="store.previewLanguage" :download-url="consultingPdfUrl(store.previewLanguage)" :floating-actions="false" @change-language="store.fetchPreview($event)" />
      </section>
    </div>
  </BasePageShell>
</template>
