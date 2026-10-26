<template>
  <div>
    <!-- Header -->
    <div class="mb-8 flex flex-col justify-between gap-3 panel-portrait:flex-row panel-portrait:items-center">
      <div>
        <h1 class="text-2xl font-light text-text-default">Dashboard</h1>
        <p class="text-xs text-text-subtle mt-1 first-letter:uppercase">{{ todayLabel }}</p>
      </div>
      <BaseDropdown :items="createItems" align="right">
        <template #trigger>
          <BaseButton variant="primary" size="md">
        <BaseActionIcon action="create" />
            Crear
          </BaseButton>
        </template>
      </BaseDropdown>
    </div>

    <!-- Loading skeleton mirrors the real geometry -->
    <div v-if="loading && !summary" class="space-y-8" aria-hidden="true" data-testid="dashboard-skeleton">
      <div class="grid grid-cols-1 gap-4 panel-portrait:grid-cols-3">
        <div
          v-for="n in 3"
          :key="`pulse-${n}`"
          class="h-28 rounded-xl bg-surface-raised motion-safe:animate-pulse"
        />
      </div>
      <div class="space-y-2">
        <div class="h-3 w-40 rounded bg-surface-raised motion-safe:animate-pulse" />
        <div
          v-for="n in 2"
          :key="`radar-${n}`"
          class="h-14 rounded-xl bg-surface-raised motion-safe:animate-pulse"
        />
      </div>
      <div class="grid grid-cols-1 gap-4 panel-desktop:grid-cols-2">
        <div class="h-64 rounded-xl bg-surface-raised motion-safe:animate-pulse" />
        <div class="h-64 rounded-xl bg-surface-raised motion-safe:animate-pulse" />
      </div>
    </div>

    <!-- Error state with retry -->
    <BaseEmptyState
      v-else-if="error && !summary"
      title="No pudimos cargar el dashboard"
      description="Revisa tu conexión e intenta de nuevo."
      data-testid="dashboard-error"
    >
      <template #actions>
        <BaseButton variant="primary" size="md" @click="loadDashboard">
          Reintentar
        </BaseButton>
      </template>
    </BaseEmptyState>

    <template v-else-if="summary">
      <!-- Pulse: the three vital signs -->
      <div
        class="mb-8 grid grid-cols-1 gap-4 dash-reveal panel-portrait:grid-cols-2"
        :class="hasFinance ? 'panel-desktop:grid-cols-3' : ''"
        data-testid="dashboard-pulse"
      >
        <DashboardStatTile
          v-if="hasFinance"
          size="lg"
          :label="`Utilidad líquida ${finance.year}`"
          :value="Number(finance.liquid_utility)"
          format="currency"
          :tone="Number(finance.liquid_utility) >= 0 ? 'success' : 'danger'"
          sub="ingresos líquidos − gastos"
          clickable
          data-testid="dashboard-finance-tile"
          @click="showFinanceStats = true"
        />
        <DashboardStatTile
          size="lg"
          label="Pipeline activo"
          :value="proposals?.pipeline_value ?? null"
          format="currency"
          tone="brand"
          :sub="pipelineSub"
          clickable
          data-testid="dashboard-pipeline-tile"
          @click="showProposalsStats = true"
        />
        <DashboardStatTile
          size="lg"
          label="Pendientes de atención"
          :value="attentionCount"
          format="number"
          :tone="attentionTone"
          :sub="attention.length ? 'revisa el radar' : 'todo al día'"
        />
      </div>

      <!-- Attention radar (signature) -->
      <DashboardAttentionRadar :key="summary?.generated_at" :items="attention" class="mb-8 dash-reveal" style="animation-delay: 60ms" />

      <!-- Module sections -->
      <DashboardFinanceSection
        v-if="hasFinance"
        :finance="finance"
        class="mb-8 dash-reveal"
        style="animation-delay: 120ms"
      />
      <DashboardProposalsSection
        :proposals="proposals"
        class="mb-8 dash-reveal"
        style="animation-delay: 180ms"
      />
      <DashboardAdditionalModulesSection
        :summary="additionalModules"
        class="mb-8 dash-reveal"
        style="animation-delay: 240ms"
      />
      <DashboardOperationsSection
        :operations="operations"
        class="mb-4 dash-reveal"
        style="animation-delay: 300ms"
      />

      <!-- Stats modals -->
      <FinanceStatsModal
        v-if="hasFinance"
        :open="showFinanceStats"
        :finance="finance"
        @close="showFinanceStats = false"
      />
      <ProposalsStatsModal
        :open="showProposalsStats"
        @close="showProposalsStats = false"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { storeToRefs } from 'pinia';
import DashboardAttentionRadar from '~/components/panel/dashboard/DashboardAttentionRadar.vue';
import DashboardAdditionalModulesSection from '~/components/panel/dashboard/DashboardAdditionalModulesSection.vue';
import DashboardFinanceSection from '~/components/panel/dashboard/DashboardFinanceSection.vue';
import DashboardOperationsSection from '~/components/panel/dashboard/DashboardOperationsSection.vue';
import DashboardProposalsSection from '~/components/panel/dashboard/DashboardProposalsSection.vue';
import DashboardStatTile from '~/components/panel/dashboard/DashboardStatTile.vue';
import FinanceStatsModal from '~/components/panel/dashboard/FinanceStatsModal.vue';
import ProposalsStatsModal from '~/components/panel/dashboard/ProposalsStatsModal.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { usePanelDashboardStore } from '~/stores/panel_dashboard';

const localePath = useLocalePath();
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const store = usePanelDashboardStore();
const { summary, loading, error } = storeToRefs(store);
const {
  finance,
  proposals,
  additionalModules,
  operations,
  attention,
  attentionCount,
  hasFinance,
} = storeToRefs(store);
const notify = usePanelNotify();

const todayLabel = computed(() =>
  new Date().toLocaleDateString('es-CO', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  }),
);

const createItems = computed(() => [
  { label: 'Propuesta', to: localePath('/panel/proposals/create') },
  { label: 'Documento', to: localePath('/panel/documents') },
  { label: 'Tarea', to: localePath('/panel/tasks') },
  { label: 'Gasto', to: localePath('/panel/accounting/expenses') },
]);

const pipelineSub = computed(() => {
  const count = proposals.value?.pipeline_count ?? 0;
  return `${count} propuesta${count === 1 ? '' : 's'} en curso (enviadas + vistas)`;
});

const showFinanceStats = ref(false);
const showProposalsStats = ref(false);

const attentionTone = computed(() => {
  if (!attention.value.length) return 'success';
  return attention.value.some((item) => item.severity === 'danger')
    ? 'danger'
    : 'warning';
});

async function loadDashboard() {
  const result = await store.fetchSummary();
  if (!result.success && !summary.value) {
    notify.error({
      title: 'No pudimos cargar el dashboard',
      detail: 'Revisa tu conexión e intenta de nuevo.',
    });
  }
}

onMounted(loadDashboard);
usePanelRefresh(loadDashboard);
</script>

<style scoped>
@media (prefers-reduced-motion: no-preference) {
  .dash-reveal {
    animation: dash-rise 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
  }

  @keyframes dash-rise {
    from {
      opacity: 0;
      transform: translateY(10px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
}
</style>
