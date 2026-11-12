<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { get_request } from '~/stores/services/request_http'
import { useChartTheme } from '~/composables/useChartTheme'
const props = defineProps({ serverId: { type: [Number, String], required: true }, refreshKey: { type: Number, default: 0 } })
const { t, locale } = useI18n()
const tr = (key, values) => t(`monitoring.${key}`, values || {})
const { palette, baseOptions } = useChartTheme()
const period = ref('24h')
const data = ref(null)
const loading = ref(false)
const error = ref(false)
let requestId = 0
async function load() {
  const id = ++requestId
  loading.value = true
  error.value = false
  try {
    const response = await get_request(`monitoring/servers/${props.serverId}/series/`, { params: { period: period.value } })
    if (id === requestId) data.value = response.data
  } catch { if (id === requestId) { error.value = true; data.value = null } }
  finally { if (id === requestId) loading.value = false }
}
watch(() => [props.serverId, props.refreshKey, period.value], load, { immediate: true })
onBeforeUnmount(() => { requestId++ })
const hasData = computed(() => data.value?.points?.some(point => point.count > 0))
const lastUpdate = computed(() => data.value?.last_observed_at ? new Date(data.value.last_observed_at).toLocaleString(locale.value) : '—')
const definitions = [
  { key: 'ram', field: 'ram_used_bytes', capacity: 'ram_total_bytes', divisor: 1024 ** 3, unit: 'GiB' },
  { key: 'disk', field: 'disk_used_bytes', capacity: 'disk_total_bytes', divisor: 1024 ** 3, unit: 'GiB' },
  { key: 'cpu', field: 'cpu_percent', divisor: 1, unit: '%' },
  { key: 'loadMetric', field: 'load_1m', capacity: 'cpu_count', multiplier: 3, divisor: 1, unit: tr('loadUnit') },
]
const charts = computed(() => definitions.map(definition => {
  const points = data.value?.points || []
  const measure = (point, mode) => {
    const value = point[mode]?.[definition.field]
    return [point.timestamp, value === null || value === undefined ? null : value / definition.divisor]
  }
  return {
    ...definition,
    series: [
      { name: tr('averageMeasured'), data: points.map(point => measure(point, 'average')) },
      { name: tr('maximumMeasured'), data: points.map(point => measure(point, 'max')) },
      { name: tr(definition.key === 'loadMetric' ? 'pressureThreshold' : 'totalCapacity'), data: points.map(point => {
        const capacity = definition.key === 'cpu' ? 100 : point.average?.[definition.capacity]
        return [point.timestamp, !point.count || capacity === null || capacity === undefined ? null : capacity * (definition.multiplier || 1) / definition.divisor]
      }) },
    ],
    options: {
      ...baseOptions.value,
      chart: { ...baseOptions.value.chart, id: `monitor-${definition.key}-${props.serverId}` },
      colors: [palette.value.measures[0], palette.value.measures[2], palette.value.measures[1]],
      stroke: { curve: 'straight', width: [2, 1, 1], dashArray: [0, 0, 5] },
      xaxis: { type: 'datetime' },
      yaxis: { min: 0, title: { text: definition.unit }, labels: { formatter: value => Number(value).toFixed(1) } },
      tooltip: { ...baseOptions.value.tooltip, x: { format: 'dd MMM HH:mm' } },
    },
  }
}))
</script>

<template>
  <section class="space-y-4" data-testid="monitoring-charts">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h3 class="font-medium text-text-default">{{ tr('serverTrends') }}</h3>
      <MonitoringSelect v-model="period" :label="tr('period')" :options="['24h', '7d', '30d', '90d'].map(value => ({ value, label: tr(`periods.${value}`) }))" />
    </div>
    <p class="text-xs text-text-subtle">{{ tr('measuredOnly') }} · {{ tr('lastUpdate') }}: {{ lastUpdate }}</p>
    <p v-if="loading" role="status" class="text-sm text-text-subtle">{{ tr('loading') }}</p>
    <div v-else-if="error" role="alert" class="space-y-2"><p>{{ tr('load') }}</p><BaseButton variant="secondary" @click="load">{{ tr('refresh') }}</BaseButton></div>
    <p v-else-if="!hasData" class="rounded-xl border border-border-default p-5 text-sm text-text-subtle">{{ tr('noHistory') }}</p>
    <div v-else class="grid min-w-0 gap-4 xl:grid-cols-2">
      <article v-for="chart in charts" :key="chart.key" class="min-w-0 overflow-hidden rounded-xl border border-border-default bg-surface p-3">
        <h4 class="mb-2 text-sm font-medium text-text-default">{{ tr(chart.key) }}</h4>
        <ClientOnly><LazyApexChart type="line" height="240" :options="chart.options" :series="chart.series" /><template #fallback><p class="h-60 text-text-subtle">{{ tr('loading') }}</p></template></ClientOnly>
      </article>
    </div>
  </section>
</template>
