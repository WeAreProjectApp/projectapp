<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { definePageMeta, useI18n, useRoute, useRouter } from '#imports';
import BuildingOnDemandAdminContractPanel from '~/components/BuildingOnDemand/admin/ContractPanel.vue';
import BuildingOnDemandAdminDistributionCard from '~/components/BuildingOnDemand/admin/DistributionCard.vue';
import BuildingOnDemandAdminEconomicsTable from '~/components/BuildingOnDemand/admin/EconomicsTable.vue';
import BuildingOnDemandAdminMcpHint from '~/components/BuildingOnDemand/admin/McpHint.vue';
import BuildingOnDemandAdminVersionHistory from '~/components/BuildingOnDemand/admin/VersionHistory.vue';
import BuildingOnDemandAdminVersionSummary from '~/components/BuildingOnDemand/admin/VersionSummary.vue';
import { useBuildingOnDemandStore } from '~/stores/building_on_demand';
import ExplainerVideoCard from '~/components/ExplainerVideoCard.vue';
import ExplainerVisibilityToggle from '~/components/ExplainerVisibilityToggle.vue';
import VideoResourceManager from '~/components/resources/VideoResourceManager.vue';
import { useExplainerVideo } from '~/composables/useExplainerVideos';
import { useExplainerVideosStore } from '~/stores/explainer_videos';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const store = useBuildingOnDemandStore();
const videoSettings = useExplainerVideosStore();
const explainer = useExplainerVideo('building-on-demand', computed(() => store.previewLanguage), computed(() => videoSettings.settings?.resources?.[`building-on-demand:${store.previewLanguage}`]));
const tabFromQuery = (value) => ['economics', 'contract'].includes(value) ? value : 'program';
const activeSection = ref(tabFromQuery(route.query.tab));
const loadedTabs = { program: false, economics: false, contract: false };
let isMounted = false;

const sectionOptions = computed(() => ['program', 'economics', 'contract'].map((kind) => ({
  value: kind,
  label: t(`buildingOnDemandAdmin.tabs.${kind}`),
  testId: `building-on-demand-panel-tab-${kind}`,
})));
const previewLanguages = computed(() => ['es', 'en'].map((language) => ({
  value: language,
  label: t(`buildingOnDemandAdmin.previewLanguages.${language}`),
  testId: `building-on-demand-panel-preview-language-${language}`,
})));

async function loadTab(kind) {
  if (loadedTabs[kind]) return;
  loadedTabs[kind] = true;
  if (kind === 'economics') return store.fetchEconomics();
  if (kind === 'contract') {
    await store.fetchContract();
    if (!store.contractUnavailable) await store.fetchVersions('contract');
    return;
  }
  await Promise.all([store.fetchPreview(store.previewLanguage), store.fetchVersions('program')]);
}

function retryHistory(kind) {
  return store.fetchVersions(kind, { append: store.history[kind].versions.length > 0 });
}

function changePreviewLanguage(language) {
  if (language !== store.previewLanguage) return store.fetchPreview(language);
}

watch(() => route.query.tab, (value) => { activeSection.value = tabFromQuery(value); });
watch(activeSection, (value) => {
  if (value !== tabFromQuery(route.query.tab)) {
    router.replace({ query: { ...route.query, tab: value === 'program' ? undefined : value } });
  }
  if (isMounted) loadTab(value);
});

onMounted(async () => {
  await store.fetchOverview();
  isMounted = true;
  await loadTab(activeSection.value);
});
</script>

<template>
  <BasePageShell width="panel" data-testid="building-on-demand-panel">
    <header class="mb-6 min-w-0">
      <h1 class="text-2xl font-light text-text-default">{{ t('buildingOnDemandAdmin.title') }}</h1>
      <p class="mt-2 max-w-3xl text-sm leading-6 text-text-subtle">{{ t('buildingOnDemandAdmin.subtitle') }}</p>
    </header>

    <BaseSegmented v-model="activeSection" :options="sectionOptions" />

    <BaseAlert v-if="store.overviewError" class="mt-5" variant="danger" data-testid="building-on-demand-panel-overview-error">
      <p>{{ t('buildingOnDemandAdmin.overviewError') }}</p>
      <BaseButton class="mt-3" variant="secondary" :loading="store.isLoadingOverview" data-testid="building-on-demand-panel-overview-retry" @click="store.fetchOverview()">{{ t('buildingOnDemandAdmin.retry') }}</BaseButton>
    </BaseAlert>

    <div class="mt-6 min-w-0 space-y-5">
      <BuildingOnDemandAdminDistributionCard v-if="activeSection === 'program'" :public-paths="store.overview?.public_paths" :pdf-paths="store.overview?.pdf_paths" />
      <BuildingOnDemandAdminMcpHint :connector="store.connector" />

      <template v-if="activeSection === 'program'">
        <ExplainerVisibilityToggle module="building-on-demand" i18n-namespace="buildingOnDemand" test-id="building-on-demand-explainer" />
        <ExplainerVideoCard v-if="explainer" :video="explainer" i18n-namespace="buildingOnDemand" variant="compact" test-id="building-on-demand-explainer" />
        <VideoResourceManager module="building-on-demand" :language="store.previewLanguage" />
        <div v-if="store.isLoadingOverview && !store.programSummary" class="h-32 animate-pulse rounded-xl bg-surface-raised" role="status" :aria-label="t('buildingOnDemandAdmin.loading')" />
        <BuildingOnDemandAdminVersionSummary v-else-if="!store.overviewError" :summary="store.programSummary" test-id="building-on-demand-admin-program-version" />
        <BuildingOnDemandAdminVersionHistory
          kind="program"
          :versions="store.history.program.versions"
          :total="store.history.program.total"
          :is-loading="store.history.program.isLoading"
          :error="store.history.program.error"
          @load-more="store.fetchVersions('program', { append: true })"
          @retry="retryHistory('program')"
        />
        <section class="min-w-0 overflow-hidden rounded-2xl border border-border-default bg-surface" aria-labelledby="building-on-demand-panel-preview-title" data-testid="building-on-demand-panel-preview">
          <div class="flex flex-wrap items-center justify-between gap-3 border-b border-border-default px-5 py-4">
            <h2 id="building-on-demand-panel-preview-title" class="text-lg font-medium text-text-brand">{{ t('buildingOnDemandAdmin.previewTitle') }}</h2>
            <BaseSegmented :model-value="store.previewLanguage" :options="previewLanguages" size="sm" :aria-label="t('buildingOnDemandAdmin.previewLanguages.label')" @update:model-value="changePreviewLanguage" />
          </div>
          <div v-if="store.isLoadingPreview" class="space-y-4 p-5" role="status" :aria-label="t('buildingOnDemandAdmin.loading')">
            <div class="h-8 w-2/3 animate-pulse rounded bg-surface-raised" />
            <div class="h-48 animate-pulse rounded-xl bg-surface-raised" />
          </div>
          <BaseAlert v-else-if="store.previewError" class="m-5" variant="danger" data-testid="building-on-demand-panel-preview-error">
            <p>{{ t('buildingOnDemandAdmin.previewError') }}</p>
            <BaseButton class="mt-3" variant="secondary" data-testid="building-on-demand-panel-preview-retry" @click="store.fetchPreview(store.previewLanguage)">{{ t('buildingOnDemandAdmin.retry') }}</BaseButton>
          </BaseAlert>
          <BuildingOnDemandProgramView
            v-else-if="store.preview"
            :program="store.preview"
            :language="store.previewLanguage"
            :floating-actions="false"
            :show-explainer="false"
          />
        </section>
      </template>

      <BuildingOnDemandAdminEconomicsTable v-else-if="activeSection === 'economics'" :economics="store.economics" :is-loading="store.isLoadingEconomics" :error="store.economicsError" @retry="store.fetchEconomics()" />

      <template v-else>
        <BuildingOnDemandAdminContractPanel :contract="store.contract" :mirror="store.mirror" :is-loading="store.isLoadingContract || store.isLoadingOverview" :error="store.contractError" :unavailable="store.contractUnavailable" @retry="store.fetchContract()" />
        <BuildingOnDemandAdminVersionHistory
          v-if="!store.contractUnavailable"
          kind="contract"
          :versions="store.history.contract.versions"
          :total="store.history.contract.total"
          :is-loading="store.history.contract.isLoading"
          :error="store.history.contract.error"
          @load-more="store.fetchVersions('contract', { append: true })"
          @retry="retryHistory('contract')"
        />
      </template>
    </div>
  </BasePageShell>
</template>
