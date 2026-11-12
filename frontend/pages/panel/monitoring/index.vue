<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useMonitoringStore } from '~/stores/monitoring'
import { get_request } from '~/stores/services/request_http'
import { PAGE_MAX_WIDTH } from '~/utils/tableLayout'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useMonitoringStore()
const tr = (key, values) => t(`monitoring.${key}`, values || {})
const filterKeys = ['resource', 'source', 'state', 'severity', 'search', 'since', 'until', 'condition', 'followup']
const tab = ref(['project', 'server', 'reports'].includes(route.query.tab) ? route.query.tab : 'project')
const reports = computed(() => tab.value === 'reports')
const filters = reactive(Object.fromEntries(filterKeys.map(key => [key, String(route.query[key] || '')])))
const page = ref(Math.max(1, Number(route.query.page) || 1))
const catalogError = ref(false)
const statusError = ref(false)
const hosts = ref([])
const hasUpdates = ref(false)
const chartServer = ref('')
const chartRefresh = ref(0)
const detailLoading = ref(false)
const detailReports = ref(false)
const activeRecord = ref(null)
const returnCase = ref(null)
const selectedState = ref('pending')
const actionError = ref('')
const activityPage = ref(1)
const deliveryPage = ref(1)
const detailBounds = ref({})
const sourceDetailOpen = ref(false)
const inspectedSources = ref([])
const drafts = reactive({})
const note = computed({ get: () => drafts[activeRecord.value] || '', set: value => { drafts[activeRecord.value] = value } })
let filterTimer, pollTimer, synchronizing = false, disposed = false, detailRequest = 0, statusRequest = 0, consultation = ''
let writtenQuery = JSON.stringify(route.query)
const options = values => values.map(value => ({ value, label: tr(value) }))
const resourceOptions = computed(() => store.resources.filter(resource => reports.value || resource.kind === tab.value).map(resource => ({ value: String(resource.id), label: reports.value ? `${resource.name} · ${tr(resource.kind === 'project' ? 'projectLabel' : 'serverLabel')}` : resource.name })))
const resourceIds = computed(() => new Set(store.resources.filter(resource => resource.kind === tab.value).map(resource => resource.id)))
const visibleSources = computed(() => store.sources.filter(source => (!filters.resource || String(source.resource) === filters.resource) && (reports.value || resourceIds.value.has(source.resource))))
const sourceOptions = computed(() => visibleSources.value.map(source => ({ value: String(source.id), label: `${source.resource_name} · ${sourceLabel(source)}` })))
const sourceLabel = source => ['server-alerts', 'healthcheck', 'integrity', 'silk', 'telemetry', 'monitoring', 'weekly', 'diagnostic', 'traffic', 'qa', 'restore', 'verify', 'email', 'ssh'].includes(source.key) ? tr(`sourceNames.${source.key}`) : source.name
const dateFormatter = computed(() => new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }))
const formatDate = value => value ? dateFormatter.value.format(new Date(value)) : '—'
const humanTitle = record => {
  const key = record.title.replace(/^Alerta: /, '')
  return ['failed-units', 'integrity'].includes(key) ? tr(`eventTitles.${key}`) : record.title
}
const invalidDates = computed(() => Boolean(filters.since && filters.until && filters.since > filters.until))
const totalPages = computed(() => Math.max(1, Math.ceil(store.count / store.pageSize)))
const scopedSources = computed(() => visibleSources.value.filter(source => !filters.source || String(source.id) === filters.source))
const sourceProblems = computed(() => scopedSources.value.filter(source => ['no_data', 'stale'].includes(source.health)))
const pressureHosts = computed(() => hosts.value.filter(host => host.pressure.length))
const resourceLabel = computed(() => tr(reports.value ? 'resource' : tab.value === 'server' ? 'serverLabel' : 'projectLabel'))
const activeFilters = computed(() => filterKeys.filter(key => filters[key] && (!reports.value || !['state', 'severity', 'condition', 'followup'].includes(key))).map(key => ({ key, label: key === 'resource' ? resourceLabel.value : tr(key), value: key === 'resource' ? resourceOptions.value.find(item => item.value === filters[key])?.label || filters[key] : key === 'source' ? sourceOptions.value.find(item => item.value === filters[key])?.label || filters[key] : key === 'followup' ? tr('followupOnly') : ['state', 'severity', 'condition'].includes(key) ? tr(filters[key]) : filters[key] })))
const detailOpen = computed({ get: () => activeRecord.value !== null, set: value => { if (!value) closeDetail() } })
function parameters() {
  const result = Object.fromEntries(Object.entries(filters).filter(([, value]) => value))
  if (reports.value) { for (const key of ['state', 'severity', 'condition', 'followup']) delete result[key] } else result.kind = tab.value
  return result
}
async function writeUrl() {
  const query = { ...parameters(), tab: tab.value, page: String(page.value) }
  delete query.kind
  writtenQuery = JSON.stringify(query)
  await router.replace({ query })
}
async function loadList(fresh = false) {
  if (invalidDates.value || disposed) return
  const params = parameters()
  const key = JSON.stringify(params) + reports.value
  const snapshot = fresh || key !== consultation || !store.snapshot ? 'new' : store.snapshot
  consultation = key
  const success = await store.list({ ...params, page: page.value, snapshot }, reports.value)
  if (success && !disposed) { page.value = store.currentPage; hasUpdates.value = false; await writeUrl() }
}
async function checkStatus() {
  const id = ++statusRequest
  try {
    const { data } = await get_request('monitoring/status/', { params: parameters() })
    if (disposed || id !== statusRequest) return
    statusError.value = false
    hosts.value = data.hosts || []
    hasUpdates.value = Boolean(store.revision && data.revision !== store.revision)
    if (!hosts.value.some(host => String(host.id) === chartServer.value)) chartServer.value = hosts.value.length === 1 ? String(hosts.value[0].id) : ''
  } catch { if (id === statusRequest) statusError.value = true }
}
async function refresh() {
  clearTimeout(filterTimer)
  page.value = 1
  chartRefresh.value++
  await Promise.all([loadList(true), store.catalog().then(() => { catalogError.value = false }).catch(() => { catalogError.value = true })])
  await checkStatus()
}
function queueFilters(delay = 0) {
  if (synchronizing) return
  clearTimeout(filterTimer)
  page.value = 1
  filterTimer = setTimeout(() => { loadList(true); checkStatus() }, delay)
}
function changeResource(value) {
  synchronizing = true
  filters.resource = value
  filters.source = ''
  synchronizing = false
  queueFilters()
}
function clearFilters() {
  synchronizing = true
  for (const key of filterKeys) filters[key] = ''
  synchronizing = false
  queueFilters()
}
function selectTab(value) {
  if (store.saving) return
  closeDetail()
  synchronizing = true
  tab.value = value
  filters.resource = ''; filters.source = ''
  if (value === 'reports') { filters.state = ''; filters.severity = ''; filters.condition = ''; filters.followup = '' }
  synchronizing = false
  consultation = ''
  refresh()
}
async function goPage(value) { page.value = value; await loadList() }
function inspectSeverity(severity) {
  synchronizing = true
  filters.severity = severity
  filters.condition = 'active'
  synchronizing = false
  queueFilters()
}
function inspectSources(health) {
  inspectedSources.value = scopedSources.value.filter(source => source.health === health)
  sourceDetailOpen.value = true
}
function inspectSource(source) { inspectedSources.value = [source]; sourceDetailOpen.value = true }
function closeDetail() {
  if (store.saving) return
  detailRequest++
  store.close(); activeRecord.value = null; detailLoading.value = false; actionError.value = ''; returnCase.value = null
}
async function openRecord(id, isReport = reports.value, pages = null) {
  const request = ++detailRequest
  const changed = id !== activeRecord.value || isReport !== detailReports.value
  if (changed) { store.close(); activityPage.value = 1; deliveryPage.value = 1; detailBounds.value = {} }
  activeRecord.value = id
  detailReports.value = isReport
  detailLoading.value = true
  actionError.value = ''
  try {
    const history = pages ? { activities_page: activityPage.value, deliveries_page: deliveryPage.value, ...pages } : { activities_page: activityPage.value, deliveries_page: deliveryPage.value }
    await store.open(id, isReport, 1, { ...history, history_snapshot: true })
    if (request === detailRequest) detailBounds.value = store.detail?.history_bounds || {}
    if (request === detailRequest && (changed || !pages)) selectedState.value = store.detail?.state || 'pending'
  } catch { if (request === detailRequest) actionError.value = tr('load') }
  finally { if (request === detailRequest) detailLoading.value = false }
}
function detailPagination(kind, number) {
  if (kind === 'activities') activityPage.value = number; else deliveryPage.value = number
  openRecord(activeRecord.value, false, { activities_before: detailBounds.value.activities, deliveries_before: detailBounds.value.deliveries })
}
async function save(action) {
  actionError.value = ''
  const id = activeRecord.value
  try {
    if (action === 'note') { await store.note(note.value.trim(), { history_snapshot: true }); drafts[id] = '' }
    else await store.transition(selectedState.value, { history_snapshot: true })
    activityPage.value = 1; deliveryPage.value = 1; detailBounds.value = store.detail?.history_bounds || {}
    hasUpdates.value = true
  } catch (failure) { actionError.value = failure.response?.status === 409 ? tr('conflict') : tr('saveError') }
}
function followReport(id) { returnCase.value = activeRecord.value; openRecord(id, true) }
watch(() => filterKeys.map(key => filters[key]), (values, previous) => queueFilters(values[4] !== previous[4] ? 300 : 0), { flush: 'sync' })
watch(() => route.query, query => {
  if (JSON.stringify(query) === writtenQuery) return
  synchronizing = true
  tab.value = ['project', 'server', 'reports'].includes(query.tab) ? query.tab : 'project'
  for (const key of filterKeys) filters[key] = String(query[key] || '')
  page.value = Math.max(1, Number(query.page) || 1)
  synchronizing = false
  loadList(); checkStatus()
})
onMounted(async () => {
  await Promise.all([loadList(true), store.catalog().catch(() => { catalogError.value = true })])
  await checkStatus()
  pollTimer = setInterval(() => { if (!document.hidden && !store.loading) checkStatus() }, 60000)
})
onBeforeUnmount(() => { disposed = true; statusRequest++; detailRequest++; clearTimeout(filterTimer); clearInterval(pollTimer); store.requestId++; store.close() })
</script>

<template>
  <div :class="PAGE_MAX_WIDTH" class="space-y-5" data-testid="monitoring-page">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div><h1 class="text-2xl font-light text-text-default">{{ tr('title') }}</h1><p class="text-sm text-text-subtle">{{ tr('dashboardSubtitle') }}</p></div>
      <BaseButton variant="secondary" :disabled="store.loading" :disabled-reason="tr('busy')" @click="refresh">{{ tr('refresh') }}</BaseButton>
    </header>
    <nav class="flex flex-wrap gap-2" :aria-label="tr('title')">
      <BaseButton v-for="value in ['project', 'server', 'reports']" :key="value" :variant="tab === value ? 'primary' : 'secondary'" :aria-pressed="tab === value" @click="selectTab(value)">{{ tr(value) }}</BaseButton>
    </nav>
    <section :aria-label="tr('filters')" class="space-y-3">
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MonitoringSelect :model-value="filters.resource" :label="resourceLabel" :options="resourceOptions" searchable test-id="monitor-resource" @update:model-value="changeResource" />
        <MonitoringSelect v-model="filters.source" :label="tr('source')" :options="sourceOptions" searchable test-id="monitor-source" />
        <MonitoringSelect v-if="!reports" v-model="filters.state" :label="tr('state')" :options="options(['pending', 'reviewing', 'resolved'])" test-id="monitor-state" />
        <MonitoringSelect v-if="!reports" v-model="filters.severity" :label="tr('severity')" :options="options(['info', 'warning', 'critical'])" test-id="monitor-severity" />
        <MonitoringSelect v-if="!reports" v-model="filters.condition" :label="tr('condition')" :options="options(['active', 'recovered'])" test-id="monitor-condition" />
        <MonitoringSelect v-if="!reports" v-model="filters.followup" :label="tr('followup')" :options="[{ value: 'true', label: tr('followupOnly') }]" test-id="monitor-followup" />
        <BaseFormField :label="tr('search')" for="monitor-search"><BaseInput id="monitor-search" v-model="filters.search" maxlength="200" /></BaseFormField>
        <BaseFormField :label="tr('since')" for="monitor-since"><BaseInput id="monitor-since" v-model="filters.since" type="date" /></BaseFormField>
        <BaseFormField :label="tr('until')" for="monitor-until"><BaseInput id="monitor-until" v-model="filters.until" type="date" :aria-invalid="invalidDates" /></BaseFormField>
        <div class="flex items-end"><BaseButton variant="secondary" @click="clearFilters">{{ tr('clearFilters') }}</BaseButton></div>
      </div>
      <p v-if="invalidDates" role="alert" class="text-sm text-text-default">{{ tr('invalidDates') }}</p>
      <ul v-if="activeFilters.length" class="flex flex-wrap gap-2" :aria-label="tr('activeFilters')">
        <li v-for="filter in activeFilters" :key="filter.key" class="max-w-full rounded-lg bg-surface-raised px-3 py-1 text-xs text-text-default"><span class="break-words">{{ filter.label }}: {{ filter.value }}</span></li>
      </ul>
    </section>
    <p v-if="store.error || catalogError" role="alert" class="text-sm text-text-default">{{ store.expired ? tr('snapshotExpired') : tr('load') }}</p>
    <div v-if="hasUpdates" role="status" class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-default bg-surface-raised p-4"><p class="text-sm text-text-default">{{ tr('newData') }}</p><BaseButton variant="secondary" @click="refresh">{{ tr('refresh') }}</BaseButton></div>
    <p v-if="store.loading" role="status" class="text-sm text-text-subtle">{{ tr('loading') }}</p>
    <template v-if="!invalidDates">
      <section v-if="store.summary" :aria-label="tr('overview')" class="space-y-3" data-testid="monitoring-summary">
        <p class="text-xs text-text-subtle">{{ tr('filteredSnapshot') }} · {{ formatDate(store.capturedAt) }}</p>
        <div class="grid grid-cols-2 gap-3 xl:grid-cols-5">
          <article class="rounded-xl border border-border-default bg-surface p-4"><p class="text-xs text-text-subtle">{{ tr(reports ? 'reportsTotal' : 'casesTotal') }}</p><p class="mt-2 text-2xl tabular-nums text-text-default">{{ store.summary.total }}</p></article>
          <template v-if="!reports">
            <BaseButton unstyled variant="secondary" v-for="severity in ['critical', 'warning', 'info']" :key="severity" type="button" class="rounded-xl border border-border-default bg-surface p-4 text-left focus:outline focus:outline-2 focus:outline-focus-ring" @click="inspectSeverity(severity)"><span class="block text-xs text-text-subtle">{{ tr('activeSeverity', { severity: tr(severity) }) }}</span><span class="mt-2 block text-2xl tabular-nums text-text-default">{{ store.summary.active[severity] || 0 }}</span></BaseButton>
            <BaseButton unstyled variant="secondary" type="button" class="rounded-xl border border-border-default bg-surface p-4 text-left focus:outline focus:outline-2 focus:outline-focus-ring" @click="filters.followup = 'true'"><span class="block text-xs text-text-subtle">{{ tr('followupTotal') }}</span><span class="mt-2 block text-2xl tabular-nums text-text-default">{{ store.summary.followup }}</span></BaseButton>
          </template>
          <article v-else class="col-span-2 rounded-xl border border-border-default bg-surface p-4"><p class="text-xs text-text-subtle">{{ tr('lastReport') }}</p><p class="mt-2 text-sm text-text-default">{{ formatDate(store.summary.latest_report_at) }}</p></article>
        </div>
        <div class="grid gap-3 sm:grid-cols-3">
          <BaseButton unstyled variant="secondary" v-for="health in ['no_data', 'stale']" :key="health" type="button" class="rounded-xl border border-border-default bg-surface p-4 text-left focus:outline focus:outline-2 focus:outline-focus-ring" @click="inspectSources(health)"><span class="block text-xs text-text-subtle">{{ tr(health === 'no_data' ? 'sourcesWithoutData' : 'staleSources') }}</span><span class="mt-2 block text-2xl tabular-nums text-text-default">{{ scopedSources.filter(source => source.health === health).length }}</span></BaseButton>
          <BaseButton unstyled variant="secondary" type="button" class="rounded-xl border border-border-default bg-surface p-4 text-left focus:outline focus:outline-2 focus:outline-focus-ring" @click="selectTab('server')"><span class="block text-xs text-text-subtle">{{ tr('resourcesUnderPressure') }}</span><span class="mt-2 block text-2xl tabular-nums text-text-default">{{ statusError || !hosts.some(host => host.health === 'current') ? '—' : pressureHosts.length }}</span></BaseButton>
        </div>
        <details class="text-xs text-text-subtle"><summary class="cursor-pointer">{{ tr('indicatorDefinitions') }}</summary><p class="mt-2">{{ tr('indicatorHelp') }}</p></details>
      </section>
      <section class="space-y-3 rounded-xl border border-border-default bg-surface p-4" data-testid="monitoring-attention">
        <h2 class="font-medium text-text-default">{{ tr('attention') }}</h2>
        <p class="text-xs text-text-subtle">{{ tr('sourceScopeHelp') }}</p>
        <ul class="grid gap-2 lg:grid-cols-2">
          <li v-for="record in store.attention" :key="`case-${record.id}`" class="min-w-0 rounded-lg border border-border-default p-3"><BaseButton variant="ghost" class="max-w-full text-left" @click="openRecord(record.id, false)"><span class="whitespace-normal break-words">{{ humanTitle(record) }}</span></BaseButton><p class="text-xs text-text-subtle">{{ record.resource.name }} · {{ tr(record.severity) }} · {{ formatDate(record.last_seen_at) }}</p></li>
          <li v-for="source in sourceProblems" :key="`source-${source.id}`" class="min-w-0 rounded-lg border border-border-default p-3"><BaseButton variant="ghost" class="max-w-full text-left" @click="inspectSource(source)"><span class="whitespace-normal break-words">{{ source.resource_name }} · {{ sourceLabel(source) }}</span></BaseButton><p class="text-xs text-text-subtle">{{ tr(source.health) }} · {{ formatDate(source.last_seen_at) }}</p><p v-if="source.last_error" class="break-words text-xs text-text-subtle">{{ source.last_error }}</p></li>
          <li v-for="host in pressureHosts" :key="`pressure-${host.id}`" class="min-w-0 rounded-lg border border-border-default p-3"><BaseButton variant="ghost" @click="selectTab('server'); changeResource(String(host.id))">{{ host.name }}</BaseButton><p class="text-xs text-text-subtle">{{ tr('underPressure') }}: {{ host.pressure.map(metric => tr(metric === 'load' ? 'loadMetric' : metric)).join(', ') }} · {{ formatDate(host.metrics.observed_at) }}</p></li>
        </ul>
        <p v-if="!store.attention.length && !sourceProblems.length && !pressureHosts.length" class="text-sm text-text-subtle">{{ scopedSources.some(source => source.health === 'current') ? tr('noAttention') : tr('coverageUnknown') }}</p>
        <p v-if="statusError" role="alert" class="text-xs text-text-subtle">{{ tr('statusUnavailable') }}</p>
      </section>
      <section v-if="tab === 'server'" class="space-y-4">
        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <article v-for="host in hosts" :key="host.id" class="min-w-0 rounded-xl border border-border-default bg-surface p-4"><BaseButton variant="ghost" @click="chartServer = String(host.id)">{{ host.name }}</BaseButton><p class="text-xs text-text-subtle">{{ tr(host.health) }} · {{ formatDate(host.metrics?.observed_at) }}</p><p v-if="host.metrics" class="mt-2 text-sm text-text-default">RAM {{ (host.metrics.ram_used_bytes / 1024 ** 3).toFixed(2) }} / {{ (host.metrics.ram_total_bytes / 1024 ** 3).toFixed(2) }} GiB · {{ host.metrics.cpu_count }} vCPU</p></article>
        </div>
        <MonitoringSelect v-if="hosts.length > 1" v-model="chartServer" :label="tr('chartServer')" :options="hosts.map(host => ({ value: String(host.id), label: host.name }))" searchable />
        <MonitoringCharts v-if="chartServer" :key="chartServer" :server-id="chartServer" :refresh-key="chartRefresh" />
        <p v-else class="text-sm text-text-subtle">{{ tr('chooseServer') }}</p>
      </section>
      <template v-if="tab === 'project'"><MonitoringCapacity v-if="filters.resource" :key="filters.resource" :resource-id="filters.resource" :refresh-key="chartRefresh" /><p v-else class="text-sm text-text-subtle">{{ tr('chooseProjectCapacity') }}</p></template>
      <details class="rounded-xl border border-border-default bg-surface p-4"><summary class="cursor-pointer font-medium text-text-default">{{ tr('sources') }} · {{ visibleSources.length }}</summary><ul class="mt-3 grid gap-3 sm:grid-cols-2"><li v-for="source in visibleSources" :key="source.id" class="min-w-0 text-sm text-text-subtle"><span class="font-medium text-text-default">{{ source.resource_name }} · {{ sourceLabel(source) }}</span><p>{{ tr(source.health) }} · {{ formatDate(source.last_seen_at) }}</p><p v-if="source.last_error" class="break-words">{{ source.last_error }}</p></li></ul></details>
      <section class="space-y-3"><h2 class="font-medium text-text-default">{{ tr(reports ? 'reports' : 'events') }}</h2><p v-if="reports" class="text-xs text-text-subtle">{{ tr('retained') }}</p>
        <p v-if="!store.loading && !store.error && !store.records.length" class="rounded-xl border border-border-default p-6 text-center text-sm text-text-subtle">{{ tr('empty') }}</p>
        <ul class="space-y-2" :aria-busy="store.loading"><li v-for="record in store.records" :key="record.id" class="rounded-xl border border-border-default bg-surface p-3"><div class="flex flex-wrap items-start justify-between gap-2"><div class="min-w-0 flex-1"><BaseButton variant="ghost" class="max-w-full text-left" @click="openRecord(record.id)"><span class="whitespace-normal break-words">{{ humanTitle(record) }}</span></BaseButton><p class="text-xs text-text-subtle">{{ record.resource.name }} · {{ sourceLabel({ key: record.source_key, name: record.source_name }) }}</p></div><p v-if="!reports" class="text-xs text-text-default">{{ tr(record.severity) }} · {{ tr(record.state) }}</p></div><p v-if="record.summary" class="mt-1 break-words text-sm text-text-subtle">{{ record.summary }}</p><p class="mt-1 text-xs text-text-subtle">{{ formatDate(record.last_seen_at || record.observed_at) }}<span v-if="!reports"> · {{ tr('detections', { count: record.detections }) }} · {{ tr(record.condition) }}</span></p></li></ul>
        <BasePagination :current-page="page" :total-pages="totalPages" :total-items="store.count" :range-from="store.count ? (page - 1) * store.pageSize + 1 : 0" :range-to="Math.min(page * store.pageSize, store.count)" always-show @prev="goPage(page - 1)" @next="goPage(page + 1)" @go="goPage" />
      </section>
    </template>
    <BaseModal v-model="sourceDetailOpen" kind="detail" padding="md">
      <h2 class="text-xl font-medium text-text-default">{{ tr('sources') }}</h2>
      <p v-if="!inspectedSources.length" class="mt-4 text-sm text-text-subtle">{{ tr('noSourcesInState') }}</p>
      <ul class="mt-4 space-y-4"><li v-for="source in inspectedSources" :key="source.id" class="min-w-0 rounded-lg border border-border-default p-3"><h3 class="break-words font-medium text-text-default">{{ source.resource_name }} · {{ sourceLabel(source) }}</h3><p class="text-sm text-text-subtle">{{ tr(source.health) }} · {{ tr('lastUpdate') }}: {{ formatDate(source.last_seen_at) }}</p><p class="text-sm text-text-subtle">{{ tr('expectedInterval', { seconds: source.expected_interval }) }}</p><p v-if="source.last_error" class="mt-2 break-words text-sm text-text-default">{{ source.last_error }}</p></li></ul>
      <template #footer><BaseModalActions><BaseButton variant="secondary" @click="sourceDetailOpen = false">{{ tr('close') }}</BaseButton></BaseModalActions></template>
    </BaseModal>
    <BaseModal v-model="detailOpen" kind="detail" padding="md" full-height :close-on-backdrop="!store.saving" :close-on-esc="!store.saving">
      <div class="flex min-h-0 flex-1 flex-col gap-4" data-testid="monitoring-detail"><h2 class="shrink-0 break-words text-xl font-medium text-text-default">{{ store.detail ? humanTitle(store.detail) : tr('loading') }}</h2><div class="min-h-0 flex-1 space-y-5 overflow-y-auto">
        <p v-if="actionError" role="alert" class="text-sm text-text-default">{{ actionError }}</p><p v-if="detailLoading" role="status">{{ tr('loading') }}</p>
        <template v-if="store.detail && !detailLoading"><p class="text-sm text-text-subtle">{{ store.detail.resource.name }} · {{ sourceLabel({ key: store.detail.source_key, name: store.detail.source_name }) }}</p>
          <template v-if="detailReports"><p class="text-sm text-text-subtle">{{ tr('readOnlyReport') }}</p><pre class="whitespace-pre-wrap break-words text-sm text-text-default">{{ store.detail.text }}</pre></template>
          <template v-else><p class="text-sm text-text-default">{{ tr(store.detail.condition) }} · {{ tr(store.detail.state) }} · {{ tr('detections', { count: store.detail.detections }) }}</p><p class="text-xs text-text-subtle">{{ tr('first') }}: {{ formatDate(store.detail.first_seen_at) }} · {{ tr('last') }}: {{ formatDate(store.detail.last_seen_at) }}</p>
            <form class="flex flex-wrap items-end gap-3" @submit.prevent="save('state')"><MonitoringSelect v-model="selectedState" :label="tr('state')" :options="options(['pending', 'reviewing', 'resolved'])" test-id="monitor-detail-state" /><BaseButton type="submit" :disabled="store.saving" :disabled-reason="tr('busy')">{{ tr('save') }}</BaseButton></form>
            <section><h3 class="mb-3 font-medium text-text-default">{{ tr('evidence') }}</h3><MonitoringEvidence :evidence="store.detail.evidence" /><p v-if="humanTitle(store.detail) !== store.detail.title" class="mt-2 break-words text-xs text-text-subtle">{{ tr('originalTitle') }}: {{ store.detail.title }}</p></section>
            <form class="space-y-3" @submit.prevent="save('note')"><BaseFormField :label="tr('note')" for="monitor-note"><BaseTextarea id="monitor-note" v-model="note" maxlength="4000" /></BaseFormField><BaseButton type="submit" :disabled="store.saving || !note.trim()" :disabled-reason="store.saving ? tr('busy') : tr('emptyNote')">{{ tr('addNote') }}</BaseButton></form>
            <section><h3 class="mb-3 font-medium text-text-default">{{ tr('notes') }}</h3><p v-if="!store.detail.activities.results.length" class="text-sm text-text-subtle">{{ tr('noNotes') }}</p><ol class="space-y-2"><li v-for="item in store.detail.activities.results" :key="item.id" class="rounded-lg border border-border-default p-3 text-sm text-text-default"><p class="text-xs text-text-subtle">{{ item.actor_name || tr('system') }} · {{ formatDate(item.created_at) }}</p><p v-if="item.to_state">{{ tr(item.from_state) }} → {{ tr(item.to_state) }}</p><p class="whitespace-pre-wrap break-words">{{ item.text }}</p></li></ol><BasePagination :current-page="activityPage" :total-pages="Math.max(1, Math.ceil(store.detail.activities.count / store.detail.activities.page_size))" :total-items="store.detail.activities.count" :range-from="store.detail.activities.count ? (activityPage - 1) * 25 + 1 : 0" :range-to="Math.min(activityPage * 25, store.detail.activities.count)" always-show @prev="detailPagination('activities', activityPage - 1)" @next="detailPagination('activities', activityPage + 1)" @go="detailPagination('activities', $event)" /></section>
            <section><h3 class="mb-3 font-medium text-text-default">{{ tr('history') }}</h3><ol class="space-y-3"><li v-for="item in store.detail.deliveries.results" :key="item.id" class="space-y-2 rounded-lg border border-border-default p-3"><p class="text-xs text-text-subtle">{{ tr(item.kind) }} · {{ formatDate(item.observed_at) }}</p><MonitoringEvidence :evidence="item.evidence" /><BaseButton v-if="item.report" variant="ghost" @click="followReport(item.report)">{{ tr('readOnlyReport') }}</BaseButton></li></ol><BasePagination :current-page="deliveryPage" :total-pages="Math.max(1, Math.ceil(store.detail.deliveries.count / store.detail.deliveries.page_size))" :total-items="store.detail.deliveries.count" :range-from="store.detail.deliveries.count ? (deliveryPage - 1) * 25 + 1 : 0" :range-to="Math.min(deliveryPage * 25, store.detail.deliveries.count)" always-show @prev="detailPagination('deliveries', deliveryPage - 1)" @next="detailPagination('deliveries', deliveryPage + 1)" @go="detailPagination('deliveries', $event)" /></section>
          </template>
        </template>
      </div></div>
      <template #footer><BaseModalActions><BaseButton v-if="detailReports && returnCase" variant="secondary" @click="openRecord(returnCase, false)">{{ tr('backToCase') }}</BaseButton><BaseButton variant="secondary" :disabled="store.saving" :disabled-reason="tr('busy')" @click="openRecord(activeRecord, detailReports)">{{ tr('refreshDetail') }}</BaseButton><BaseButton variant="secondary" :disabled="store.saving" :disabled-reason="tr('busy')" @click="closeDetail">{{ tr('close') }}</BaseButton></BaseModalActions></template>
    </BaseModal>
  </div>
</template>
