<script setup>
import { computed } from 'vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import { useChartTheme } from '~/composables/useChartTheme';

/**
 * Proposals monthly trend as a stacked column chart (accepted / rejected /
 * in progress per month). Mirrors AccountingMonthlyChart: client-only
 * mount, centralized theme, animations off under reduced motion.
 */
const props = defineProps({
  /** build_dashboard_core monthly_trend rows: { month, sent, accepted, rejected }. */
  trend: { type: Array, default: () => [] },
});

const { palette, baseOptions } = useChartTheme();

function monthLabel(iso) {
  if (!iso) return '';
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleDateString('es-CO', { month: 'short' });
}

const categories = computed(() => props.trend.map((row) => monthLabel(row.month)));

const series = computed(() => [
  {
    name: 'Aceptadas',
    data: props.trend.map((row) => row.accepted || 0),
  },
  {
    name: 'Rechazadas',
    data: props.trend.map((row) => row.rejected || 0),
  },
  {
    name: 'En curso',
    data: props.trend.map((row) =>
      Math.max(0, (row.sent || 0) - (row.accepted || 0) - (row.rejected || 0)),
    ),
  },
]);

const isEmpty = computed(() =>
  series.value.every((serie) => serie.data.every((value) => value === 0)),
);

const options = computed(() => ({
  ...baseOptions.value,
  chart: {
    ...baseOptions.value.chart,
    stacked: true,
    redrawOnParentResize: true,
    redrawOnWindowResize: true,
  },
  // Accepted=emerald, rejected=red, in-progress=blue from the validated ramp.
  colors: [palette.value.measures[1], palette.value.measures[2], palette.value.measures[0]],
  plotOptions: { bar: { columnWidth: '45%', borderRadius: 3 } },
  stroke: { width: 0 },
  xaxis: {
    type: 'category',
    categories: categories.value,
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  yaxis: {
    labels: { formatter: (value) => Math.round(value) },
  },
}));
</script>

<template>
  <div class="w-full min-w-0 max-w-full" data-testid="dashboard-trend-chart">
    <BaseEmptyState
      v-if="isEmpty"
      title="Sin propuestas en los últimos meses"
      description="Cuando envíes propuestas verás aquí su evolución mensual."
    />
    <ClientOnly v-else>
      <LazyApexChart
        type="bar"
        width="100%"
        height="220"
        :options="options"
        :series="series"
      />
      <template #fallback>
        <div class="h-52 rounded-xl bg-surface-raised motion-safe:animate-pulse" />
      </template>
    </ClientOnly>
  </div>
</template>
