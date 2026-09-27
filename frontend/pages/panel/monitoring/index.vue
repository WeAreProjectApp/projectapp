<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useMonitoringStore } from '~/stores/monitoring'
import { PAGE_MAX_WIDTH } from '~/utils/tableLayout'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useMonitoringStore()
const tr = (key, values) => t(`monitoring.${key}`, values || {})
const tab = ref(['project', 'server', 'reports'].includes(route.query.tab) ? route.query.tab : 'project')
const reports = computed(() => tab.value === 'reports')
const filters = reactive(Object.fromEntries(['resource', 'source', 'state', 'severity', 'search', 'since', 'until'].map(key => [key, String(route.query[key] || '')])))
const page = ref(Math.max(1, Number(route.query.page) || 1))
const note = ref('')
const selectedState = ref('pending')
const actionError = ref('')
const detailLoading = ref(false)
const detailReports = ref(false)
const catalogError = ref(false)
const detailPage = ref(1)
let timer
const options = values => values.map(value => ({ value, label: value ? tr(value) : tr('any') }))
const resourceOptions = computed(() => [{ value: '', label: tr('any') }, ...store.resources.filter(r => reports.value || r.kind === tab.value).map(r => ({ value: r.id, label: r.name }))])
const tabResourceIds = computed(() => new Set(store.resources.filter(r => r.kind === tab.value).map(r => r.id)))
const visibleSources = computed(() => store.sources.filter(s => (!filters.resource || String(s.resource) === String(filters.resource)) && (reports.value || tabResourceIds.value.has(s.resource))))
const sourceOptions = computed(() => [{ value: '', label: tr('any') }, ...visibleSources.value.map(s => ({ value: s.id, label: `${s.resource_name} · ${s.name}` }))])
const dateFormatter = computed(() => new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }))
const formatDate = value => value ? dateFormatter.value.format(new Date(value)) : '—'
const detailOpen = computed({ get: () => Boolean(store.detail) || detailLoading.value, set: value => { if (!value) closeDetail() } })

function closeDetail() {
  if (store.saving) return
  store.close()
  detailLoading.value = false
}

async function refresh() {
  const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value))
  if (reports.value) { delete params.state; delete params.severity }
  else params.kind = tab.value
  params.page = page.value
  await Promise.all([store.list(params, reports.value), store.catalog().then(() => { catalogError.value = false }).catch(() => { catalogError.value = true })])
}
async function applyFilters(reset = true) {
  if (reset) page.value = 1
  await router.replace({ query: { ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value)), tab: tab.value, page: String(page.value) } })
  await refresh()
}
async function selectTab(value) {
  closeDetail()
  store.records = []
  store.count = 0
  tab.value = value
  filters.resource = ''
  filters.source = ''
  await applyFilters()
}
async function openRecord(id, detailNumber = 1, isReport = reports.value) {
  actionError.value = ''
  detailLoading.value = true
  detailReports.value = isReport
  detailPage.value = detailNumber
  try {
    await store.open(id, isReport, detailNumber)
    selectedState.value = store.detail?.state || 'pending'
    note.value = ''
  } catch { actionError.value = tr('load') }
  finally { detailLoading.value = false }
}
async function save(action) {
  actionError.value = ''
  try {
    if (action === 'note') { await store.note(note.value.trim()); note.value = '' }
    else await store.transition(selectedState.value)
    detailPage.value = 1
    await refresh()
  } catch (error) { actionError.value = error.response?.status === 409 ? tr('conflict') : tr('saveError') }
}
watch(() => filters.resource, () => { filters.source = '' })
onMounted(() => {
  refresh()
  timer = setInterval(() => { if (!document.hidden && !store.loading) refresh() }, 60000)
})
onBeforeUnmount(() => { clearInterval(timer); store.requestId += 1; store.close() })
</script>

<template>
  <div :class="PAGE_MAX_WIDTH" data-testid="monitoring-page">
    <header class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div><h1 class="text-2xl font-light text-text-default">{{ tr('title') }}</h1><p class="text-sm text-text-subtle">{{ tr('subtitle') }}</p></div>
      <BaseButton variant="secondary" :disabled="store.loading" :disabled-reason="tr('busy')" @click="refresh">{{ tr('refresh') }}</BaseButton>
    </header>
    <nav class="mb-5 flex flex-wrap gap-2" :aria-label="tr('title')">
      <BaseButton v-for="value in ['project', 'server', 'reports']" :key="value" :variant="tab === value ? 'primary' : 'secondary'" :aria-pressed="tab === value" @click="selectTab(value)">{{ tr(value) }}</BaseButton>
    </nav>
    <form class="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4" @submit.prevent="applyFilters()">
      <BaseFormField :label="tr('resource')" for="monitor-resource"><BaseSelect id="monitor-resource" v-model="filters.resource" :options="resourceOptions" /></BaseFormField>
      <BaseFormField :label="tr('source')" for="monitor-source"><BaseSelect id="monitor-source" v-model="filters.source" :options="sourceOptions" /></BaseFormField>
      <BaseFormField v-if="!reports" :label="tr('state')" for="monitor-state"><BaseSelect id="monitor-state" v-model="filters.state" :options="options(['', 'pending', 'reviewing', 'resolved'])" /></BaseFormField>
      <BaseFormField v-if="!reports" :label="tr('severity')" for="monitor-severity"><BaseSelect id="monitor-severity" v-model="filters.severity" :options="options(['', 'info', 'warning', 'critical'])" /></BaseFormField>
      <BaseFormField :label="tr('search')" for="monitor-search"><BaseInput id="monitor-search" v-model="filters.search" maxlength="200" /></BaseFormField>
      <BaseFormField :label="tr('since')" for="monitor-since"><BaseInput id="monitor-since" v-model="filters.since" type="date" /></BaseFormField>
      <BaseFormField :label="tr('until')" for="monitor-until"><BaseInput id="monitor-until" v-model="filters.until" type="date" /></BaseFormField>
      <div class="flex items-end"><BaseButton type="submit">{{ tr('filter') }}</BaseButton></div>
    </form>
    <p v-if="store.error || catalogError" role="alert" class="mb-4 text-text-default">{{ tr('load') }}</p>
    <p v-if="actionError && !detailOpen" role="alert" class="mb-4 text-text-default">{{ actionError }}</p>
    <details class="mb-5 rounded-xl border border-input-border bg-surface p-4">
      <summary class="cursor-pointer font-medium text-text-default">{{ tr('sources') }}</summary>
      <ul class="mt-3 grid gap-3 sm:grid-cols-2">
        <li v-for="source in visibleSources" :key="source.id" class="min-w-0 text-sm text-text-subtle">
          <span class="font-medium text-text-default">{{ source.resource_name }} · {{ source.name }}</span>
          <p>{{ tr(source.health) }} · {{ formatDate(source.last_seen_at) }}</p>
          <p v-if="source.last_error" class="break-words">{{ source.last_error }}</p>
        </li>
      </ul>
    </details>
    <p v-if="reports" class="mb-4 text-sm text-text-subtle">{{ tr('retained') }}</p>
    <p v-if="store.loading" role="status" class="mb-3 text-text-subtle">{{ tr('loading') }}</p>
    <p v-else-if="!store.error && !store.records.length" class="rounded-xl border border-input-border p-8 text-center text-text-subtle">{{ tr('empty') }}</p>
    <ul class="space-y-3" :aria-busy="store.loading">
      <li v-for="record in store.records" :key="record.id" class="rounded-xl border border-input-border bg-surface p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <BaseButton variant="ghost" class="max-w-full text-left" @click="openRecord(record.id)"><span class="whitespace-normal break-words">{{ record.title }}</span></BaseButton>
            <p class="mt-1 text-sm text-text-subtle">{{ record.resource.name }} · {{ record.source_name }}</p>
          </div>
          <div v-if="!reports" class="flex flex-wrap gap-2 text-sm text-text-default"><span>{{ tr(record.severity) }}</span><span>· {{ tr(record.state) }}</span></div>
        </div>
        <p class="mt-2 text-sm text-text-subtle">{{ formatDate(record.last_seen_at || record.observed_at) }}<span v-if="!reports"> · {{ tr('detections', { count: record.detections }) }} · {{ tr(record.condition) }}</span></p>
      </li>
    </ul>
    <footer class="mt-5 flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-text-subtle">{{ tr('page', { page, count: store.count }) }}</p>
      <div class="flex gap-2"><BaseButton v-if="page > 1" variant="secondary" @click="page--; applyFilters(false)">{{ tr('previous') }}</BaseButton><BaseButton v-if="page * store.pageSize < store.count" variant="secondary" @click="page++; applyFilters(false)">{{ tr('next') }}</BaseButton></div>
    </footer>
    <BaseModal v-model="detailOpen" kind="detail" padding="md" full-height :close-on-backdrop="!store.saving" :close-on-esc="!store.saving">
      <div class="flex min-h-0 flex-1 flex-col gap-5" data-testid="monitoring-detail">
        <h2 class="shrink-0 break-words text-xl font-medium text-text-default">{{ store.detail?.title || tr('loading') }}</h2>
        <div class="min-h-0 flex-1 space-y-5 overflow-y-auto">
        <p v-if="actionError" role="alert" class="text-text-default">{{ actionError }}</p>
        <p v-if="detailLoading" role="status">{{ tr('loading') }}</p>
        <template v-if="store.detail && !detailLoading">
          <p class="text-sm text-text-subtle">{{ store.detail.resource.name }} · {{ store.detail.source_name }}</p>
          <template v-if="detailReports"><p class="text-sm text-text-subtle">{{ tr('readOnlyReport') }}</p><pre class="whitespace-pre-wrap break-words text-sm text-text-default">{{ store.detail.text }}</pre></template>
          <template v-else>
            <p class="text-text-default">{{ tr(store.detail.condition) }} · {{ tr(store.detail.state) }}</p>
            <p class="text-sm text-text-subtle">{{ tr('first') }}: {{ formatDate(store.detail.first_seen_at) }}<br>{{ tr('last') }}: {{ formatDate(store.detail.last_seen_at) }}</p>
            <form class="flex flex-wrap items-end gap-3" @submit.prevent="save('state')">
              <BaseFormField :label="tr('state')" for="monitor-detail-state"><BaseSelect id="monitor-detail-state" v-model="selectedState" :options="options(['pending', 'reviewing', 'resolved'])" /></BaseFormField>
              <BaseButton type="submit" :disabled="store.saving" :disabled-reason="tr('busy')">{{ tr('save') }}</BaseButton>
            </form>
            <section><h3 class="font-medium text-text-default">{{ tr('evidence') }}</h3><pre class="mt-2 whitespace-pre-wrap break-words text-sm text-text-subtle">{{ JSON.stringify(store.detail.evidence, null, 2) }}</pre></section>
            <form class="space-y-3" @submit.prevent="save('note')">
              <BaseFormField :label="tr('note')" for="monitor-note"><BaseTextarea id="monitor-note" v-model="note" maxlength="4000" /></BaseFormField>
              <BaseButton type="submit" :disabled="store.saving || !note.trim()" :disabled-reason="store.saving ? tr('busy') : tr('emptyNote')">{{ tr('addNote') }}</BaseButton>
            </form>
            <section><h3 class="mb-3 font-medium text-text-default">{{ tr('notes') }}</h3>
              <p v-if="!store.detail.activities.results.length" class="text-sm text-text-subtle">{{ tr('noNotes') }}</p>
              <ol class="space-y-3"><li v-for="item in store.detail.activities.results" :key="item.id" class="rounded-lg border border-input-border p-3 text-sm text-text-default"><p>{{ item.actor_name || tr('system') }} · {{ formatDate(item.created_at) }}</p><p v-if="item.to_state">{{ tr(item.from_state) }} → {{ tr(item.to_state) }}</p><p class="whitespace-pre-wrap break-words">{{ item.text }}</p></li></ol>
            </section>
            <section><h3 class="mb-3 font-medium text-text-default">{{ tr('history') }}</h3><ol class="space-y-2"><li v-for="item in store.detail.deliveries.results" :key="item.id" class="text-sm text-text-subtle">{{ tr(item.kind) }} · {{ formatDate(item.observed_at) }}<pre class="whitespace-pre-wrap break-words">{{ JSON.stringify(item.evidence, null, 2) }}</pre><BaseButton v-if="item.report" variant="ghost" @click="openRecord(item.report, 1, true)">{{ tr('readOnlyReport') }}</BaseButton></li></ol></section>
            <div class="flex gap-2"><BaseButton v-if="detailPage > 1" variant="secondary" @click="openRecord(store.detail.id, detailPage - 1)">{{ tr('previous') }}</BaseButton><BaseButton v-if="detailPage * 25 < Math.max(store.detail.activities.count, store.detail.deliveries.count)" variant="secondary" @click="openRecord(store.detail.id, detailPage + 1)">{{ tr('next') }}</BaseButton></div>
          </template>
        </template>
        </div>
      </div>
      <template #footer>
        <BaseModalActions>
          <BaseButton v-if="store.detail" variant="secondary" :disabled="store.saving" :disabled-reason="tr('busy')" @click="openRecord(store.detail.id, detailPage, detailReports)">{{ tr('refreshDetail') }}</BaseButton>
          <BaseButton variant="secondary" :disabled="store.saving" :disabled-reason="tr('busy')" @click="closeDetail">{{ tr('close') }}</BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </div>
</template>
