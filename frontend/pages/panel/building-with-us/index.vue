<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { definePageMeta, useI18n, useRoute, useRouter } from '#imports';
import BuildingWithUsAdminContractPanel from '~/components/BuildingWithUs/admin/ContractPanel.vue';
import BuildingWithUsAdminDistributionCard from '~/components/BuildingWithUs/admin/DistributionCard.vue';
import BuildingWithUsAdminVersionHistory from '~/components/BuildingWithUs/admin/VersionHistory.vue';
import BuildingWithUsAdminVersionSummary from '~/components/BuildingWithUs/admin/VersionSummary.vue';
import { useBuildingWithUsStore } from '~/stores/building_with_us';
import { buildingWithUsPdfUrl } from '~/utils/buildingWithUs';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const store = useBuildingWithUsStore();
const tabFromQuery = (value) => value === 'contract' ? 'contract' : 'program';
const activeSection = ref(tabFromQuery(route.query.tab));
const loadedTabs = { program: false, contract: false };
let isMounted = false;

const sectionOptions = computed(() => [
  { value: 'program', label: t('buildingWithUsAdmin.tabs.program'), testId: 'building-with-us-tab-program' },
  { value: 'contract', label: t('buildingWithUsAdmin.tabs.contract'), testId: 'building-with-us-tab-contract' },
]);

async function loadTab(kind) {
  if (loadedTabs[kind]) return;
  loadedTabs[kind] = true;
  await Promise.all([
    kind === 'contract' ? store.fetchContract() : store.fetchPreview('es'),
    store.fetchVersions(kind),
  ]);
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
  isMounted = true;
  await Promise.all([store.fetchOverview(), loadTab(activeSection.value)]);
});
</script>

<template>
  <BasePageShell width="panel">
    <header class="mb-6 flex flex-col gap-4 panel-portrait:flex-row panel-portrait:items-start panel-portrait:justify-between">
      <div class="min-w-0">
        <h1 class="text-2xl font-light text-text-default">{{ t('buildingWithUsAdmin.title') }}</h1>
        <p class="mt-2 max-w-3xl text-sm leading-6 text-text-subtle">{{ t('buildingWithUsAdmin.subtitle') }}</p>
      </div>
    </header>

    <BaseSegmented v-model="activeSection" :options="sectionOptions" />

    <BaseAlert v-if="store.overviewError" class="mt-5" variant="danger" data-testid="building-with-us-overview-error">
      <p>{{ t('buildingWithUsAdmin.overviewError') }}</p>
      <BaseButton class="mt-3" variant="secondary" :loading="store.isLoadingOverview" data-testid="building-with-us-overview-retry" @click="store.fetchOverview()">{{ t('buildingWithUsAdmin.retry') }}</BaseButton>
    </BaseAlert>

    <div v-if="activeSection === 'program'" class="mt-6 min-w-0 space-y-5">
      <BuildingWithUsAdminDistributionCard :language="store.previewLanguage" />
      <p class="max-w-3xl text-sm leading-6 text-text-subtle" data-testid="building-with-us-mcp-hint">{{ t('buildingWithUsAdmin.mcpHint') }}</p>
      <div v-if="store.isLoadingOverview && !store.programSummary" class="h-32 animate-pulse rounded-xl bg-surface-raised" role="status" :aria-label="t('buildingWithUsAdmin.loading')" />
      <BuildingWithUsAdminVersionSummary v-else-if="!store.overviewError" :summary="store.programSummary" test-id="building-with-us-program-version" />
      <BuildingWithUsAdminVersionHistory
        kind="program"
        :versions="store.history.program.versions"
        :total="store.history.program.total"
        :is-loading="store.history.program.isLoading"
        :error="store.history.program.error"
        @load-more="store.fetchVersions('program', { append: true })"
        @retry="retryHistory('program')"
      />
      <section class="min-w-0 rounded-2xl border border-border-default bg-surface" aria-labelledby="building-with-us-preview-title" data-testid="building-with-us-preview">
        <h2 id="building-with-us-preview-title" class="border-b border-border-default px-5 py-4 text-lg font-medium text-text-brand">{{ t('buildingWithUsAdmin.previewTitle') }}</h2>
        <div v-if="store.isLoadingPreview" class="space-y-4 p-5" role="status" :aria-label="t('buildingWithUsAdmin.loading')">
          <div class="h-8 w-2/3 animate-pulse rounded bg-surface-raised" />
          <div class="h-48 animate-pulse rounded-xl bg-surface-raised" />
        </div>
        <BaseAlert v-else-if="store.previewError" class="m-5" variant="danger" data-testid="building-with-us-program-error">
          <p>{{ t('buildingWithUsAdmin.previewError') }}</p>
          <BaseButton class="mt-3" variant="secondary" data-testid="building-with-us-program-retry" @click="store.fetchPreview(store.previewLanguage)">{{ t('buildingWithUsAdmin.retry') }}</BaseButton>
        </BaseAlert>
        <BuildingWithUsProgramView
          v-else-if="store.preview"
          :program="store.preview"
          :language="store.previewLanguage"
          :download-url="buildingWithUsPdfUrl(store.previewLanguage)"
          :floating-actions="false"
          @change-language="changePreviewLanguage"
        />
      </section>
    </div>

    <div v-else class="mt-6 min-w-0 space-y-5">
      <BuildingWithUsAdminContractPanel :contract="store.contract" :mirror="store.mirror" :is-loading="store.isLoadingContract" :error="store.contractError" @retry="store.fetchContract()" />
      <BuildingWithUsAdminVersionHistory
        kind="contract"
        :versions="store.history.contract.versions"
        :total="store.history.contract.total"
        :is-loading="store.history.contract.isLoading"
        :error="store.history.contract.error"
        @load-more="store.fetchVersions('contract', { append: true })"
        @retry="retryHistory('contract')"
      />
    </div>
  </BasePageShell>
</template>
