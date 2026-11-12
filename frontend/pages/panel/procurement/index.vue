<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ProcurementFilters from '~/components/Procurement/Filters.vue'
import { useProcurementStore } from '~/stores/procurement'
import { useRowNavigation } from '~/composables/useRowNavigation'
import { PAGE_MAX_WIDTH } from '~/utils/tableLayout'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })
const { t, locale } = useI18n()
const tr = key => t(`procurement.${key}`)
const lp = useLocalePath()
const route = useRoute()
const router = useRouter()
const store = useProcurementStore()
const { openRow } = useRowNavigation()
const tabs = ['processes', 'classified', 'alerts', 'searches', 'deliveries', 'settings']
const tab = ref(tabs.includes(String(route.query.tab)) ? String(route.query.tab) : 'processes')
function routeFilters() { try { const value = JSON.parse(String(route.query.filters || '{}')); return value && typeof value === 'object' && !Array.isArray(value) ? value : {} } catch { return {} } }
const copyFilters = value => JSON.parse(JSON.stringify(value || {}))
const filters = ref(routeFilters())
const page = ref(1)
const deliveryPage = ref(1)
const state = ref('')
const ordering = ref('-published_at')
const error = ref('')
const message = ref('')
const modal = ref('')
const form = ref({})
const formId = ref(null)
const deleteTarget = ref(null)
const retryTarget = ref(null)
const sentContent = ref(null)
const settingsForm = ref({})
const frequencies = computed(() => ['immediate', 'daily', 'weekly'].map(value => ({ value, label: tr(value) })))
const weekdays = computed(() => ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map((key, value) => ({ value, label: tr(key) })))
const options = computed(() => ({ filters: filters.value, page: page.value, ordering: ordering.value,
  ...(tab.value === 'classified' ? { classified: true, ...(state.value ? { state: state.value } : {}) } : {}) }))
const isProcessTab = computed(() => ['processes', 'classified'].includes(tab.value))
const money = value => value === null ? tr('unknown') : new Intl.NumberFormat(locale.value, { maximumFractionDigits: 0 }).format(Number(value))
const date = value => value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota' }).format(new Date(value)) : tr('unknown')
let timer

async function explainError(exception) {
  let data = exception?.response?.data
  if (data instanceof Blob) {
    try { data = JSON.parse(await data.text()) }
    catch { return tr('exportError') }
  }
  if (!data || typeof data !== 'object') return tr('saveError')
  return Object.values(data).flat().map(value => typeof value === 'string' ? value : tr('saveError')).join(' ') || tr('saveError')
}
async function attempt(action, success = '') {
  error.value = ''; message.value = ''
  try { await action(); message.value = success; return true }
  catch (exception) { error.value = await explainError(exception); return false }
}
async function refresh() {
  await attempt(async () => {
    if (isProcessTab.value) await store.list(options.value)
    else if (tab.value === 'alerts') await store.loadAlerts()
    else if (tab.value === 'searches') await store.loadSearches()
    else if (tab.value === 'deliveries') await store.loadDeliveries(deliveryPage.value)
    else if (tab.value === 'settings') { await store.loadSettings(); resetSettingsForm() }
  })
}
function resetSettingsForm() {
  const { id, updated_at, ...values } = store.settings || {}
  settingsForm.value = { ...values }
}
async function selectTab(value) {
  tab.value = value; page.value = 1
  await router.replace({ query: { tab: value, filters: JSON.stringify(filters.value) } })
  await refresh()
}
async function applyFilters() {
  page.value = 1
  await router.replace({ query: { tab: tab.value, filters: JSON.stringify(filters.value) } })
  await refresh()
}
function editSearch(item = null) {
  error.value = ''; formId.value = item?.id || null
  form.value = { name: item?.name || '', filters: copyFilters(item?.filters || filters.value), is_favorite: item?.is_favorite || false }
  modal.value = 'search'
}
function editAlert(item = null, search = null) {
  error.value = ''; formId.value = item?.id || null
  form.value = { name: item?.name || search?.name || '', filters: copyFilters(item?.filters || search?.filters || filters.value),
    recipients: (item?.recipients || []).join(', '), frequency: item?.frequency || 'daily', is_active: item?.is_active || false }
  modal.value = 'alert'
}
async function saveForm() {
  const isAlert = modal.value === 'alert'
  const payload = { ...form.value }
  if (isAlert) payload.recipients = payload.recipients.split(',').map(value => value.trim()).filter(Boolean)
  const saved = await attempt(() => isAlert ? store.saveAlert(payload, formId.value) : store.saveSearch(payload, formId.value), tr('saved'))
  if (saved) modal.value = ''
}
async function applySearch(search) {
  filters.value = copyFilters(search.filters)
  if (search.frequency) filters.value.is_open = true
  await selectTab('processes')
}
async function requestSync() {
  await attempt(() => store.requestSync(), tr('syncRequested'))
}
async function exportExcel() {
  await attempt(async () => {
    const blob = await store.export(options.value)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a'); link.href = url; link.download = 'oportunidades-secop.xlsx'; link.click()
    URL.revokeObjectURL(url)
  })
}
async function removeSearch() {
  if (await attempt(() => store.removeSearch(deleteTarget.value.id), tr('saved'))) deleteTarget.value = null
}
async function openSent(delivery) {
  await attempt(async () => { sentContent.value = delivery.snapshot ? delivery : await store.getDelivery(delivery.id) })
}
async function retry() {
  if (await attempt(() => store.retry(retryTarget.value.id), tr('retrying'))) retryTarget.value = null
}
onMounted(async () => {
  if (await attempt(async () => { await Promise.all([store.loadSearches(), store.loadSettings(), store.loadSync()]) })) {
    if (!route.query.filters) filters.value = copyFilters(store.searches.find(search => search.is_favorite)?.filters || {})
    await refresh()
  }
  timer = setInterval(async () => {
    if (document.hidden || store.loading || store.saving) return
    if (store.sync?.recent?.some(run => ['queued', 'running'].includes(run.status))) {
      try { await store.loadSync(); if (isProcessTab.value) await store.list(options.value) } catch { /* Retain visible data; manual refresh exposes errors. */ }
    }
  }, 5000)
})
onBeforeUnmount(() => { clearInterval(timer); store.requestId += 1 })
watch(() => route.query.tab, value => { if (tabs.includes(String(value))) tab.value = String(value) })
</script>

<template>
  <div :class="PAGE_MAX_WIDTH" data-testid="procurement-page">
    <header class="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div><h1 class="text-2xl font-light text-text-default">{{ tr('title') }}</h1><p class="text-sm text-text-subtle">{{ tr('subtitle') }}</p></div>
      <div class="flex flex-wrap gap-2">
        <BaseButton variant="secondary" :loading="store.loading" @click="refresh"><BaseActionIcon action="refresh" />{{ tr('refresh') }}</BaseButton>
        <BaseButton variant="secondary" data-testid="procurement-sync" @click="requestSync"><BaseActionIcon action="refresh" />{{ tr('sync') }}</BaseButton>
      </div>
    </header>
    <p class="mb-3 text-sm text-text-subtle">{{ tr('analysisHelp') }}</p>
    <p v-if="store.settings && !store.settings.email_enabled" class="mb-3 text-sm text-text-subtle">{{ tr('outboundOff') }}</p>
    <div v-if="store.sync" class="mb-4 text-sm text-text-subtle" data-testid="procurement-sync-status">
      {{ tr('openCount') }}: {{ store.sync.open_count }} · {{ tr('lastSync') }}: {{ store.sync.recent?.[0] ? tr(store.sync.recent[0].status) : tr('noSync') }}
      <span v-if="store.sync.recent?.[0]?.message"> · {{ store.sync.recent[0].message }}</span>
    </div>
    <nav class="mb-5 flex flex-wrap gap-2" :aria-label="tr('title')">
      <BaseButton v-for="value in tabs" :key="value" :variant="tab === value ? 'primary' : 'secondary'" :aria-pressed="tab === value" :data-testid="`procurement-tab-${value}`" @click="selectTab(value)">{{ tr(value) }}</BaseButton>
    </nav>
    <p v-if="message" role="status" class="mb-4 text-sm text-text-default">{{ message }}</p>
    <p v-if="error && !modal && !deleteTarget && !retryTarget" role="alert" class="mb-4 text-sm text-text-default">{{ error }}</p>
    <template v-if="isProcessTab">
      <form class="mb-5 space-y-4 rounded-xl border border-input-border bg-surface p-4" @submit.prevent="applyFilters">
        <ProcurementFilters v-model="filters" />
        <div class="flex flex-wrap items-end gap-3">
          <BaseFormField v-if="tab === 'classified'" :label="tr('status')" for="classified-state"><BaseSelect id="classified-state" v-model="state" :options="[{ value: '', label: tr('allStates') }, ...['interesting', 'reviewing', 'applied', 'discarded'].map(value => ({ value, label: tr(value) }))]" /></BaseFormField>
          <BaseFormField :label="tr('sort')" for="process-order"><BaseSelect id="process-order" v-model="ordering" :options="[{ value: '-published_at', label: tr('newest') }, { value: 'closing_at', label: tr('soonest') }, { value: '-budget', label: tr('highest') }, { value: 'entity_name', label: tr('byEntity') }]" /></BaseFormField>
          <BaseButton type="submit"><BaseActionIcon action="filter" />{{ tr('filter') }}</BaseButton>
          <BaseButton variant="secondary" @click="filters = {}; applyFilters()"><BaseActionIcon action="clear" />{{ tr('clear') }}</BaseButton>
          <BaseButton variant="secondary" data-testid="procurement-new-search" @click="editSearch()"><BaseActionIcon action="create" />{{ tr('saveSearch') }}</BaseButton>
          <BaseButton variant="secondary" data-testid="procurement-new-alert" @click="editAlert()"><BaseActionIcon action="create" />{{ tr('newAlert') }}</BaseButton>
          <BaseButton variant="secondary" @click="exportExcel"><BaseActionIcon action="export" />{{ tr('export') }}</BaseButton>
        </div>
      </form>
      <p v-if="store.loading" role="status">{{ tr('loading') }}</p>
      <p v-else-if="!error && !store.records.length" class="p-6 text-text-subtle">{{ tr('empty') }}</p>
      <ul class="space-y-3" :aria-busy="store.loading">
        <li v-for="item in store.records" :key="item.id" class="relative cursor-pointer rounded-xl border border-input-border bg-surface p-4" :data-testid="`procurement-opportunity-${item.id}`" @click="openRow(lp(`/panel/procurement/${item.id}`), $event)">
          <BaseRowLink :to="lp(`/panel/procurement/${item.id}`)">{{ item.title || item.reference }}</BaseRowLink>
          <p class="mt-2 break-words text-sm text-text-subtle">{{ item.entity_name }} · {{ item.department }} · {{ item.reference }}</p>
          <div class="mt-2 flex flex-wrap gap-3 text-sm text-text-default"><span>{{ tr('budget') }}: {{ money(item.budget) }}</span><span>{{ tr('closing') }}: {{ date(item.closing_at) }}</span><strong v-if="item.days_remaining !== null" :class="item.days_remaining <= 3 ? 'text-danger-strong' : 'text-text-default'">{{ item.days_remaining }} {{ tr('days') }}</strong><span v-if="item.my_classification">{{ tr(item.my_classification.state) }}</span></div>
        </li>
      </ul>
      <footer class="mt-5 flex items-center justify-between gap-3"><span class="text-sm text-text-subtle">{{ store.count }} · {{ page }}</span><div class="flex gap-2"><BaseButton v-if="page > 1" variant="secondary" @click="page--; refresh()">{{ tr('previous') }}</BaseButton><BaseButton v-if="page * 25 < store.count" variant="secondary" @click="page++; refresh()">{{ tr('next') }}</BaseButton></div></footer>
    </template>
    <template v-else-if="tab === 'alerts'">
      <BaseButton class="mb-4" data-testid="procurement-new-alert" @click="editAlert()"><BaseActionIcon action="create" />{{ tr('newAlert') }}</BaseButton>
      <p v-if="!store.alerts.length">{{ tr('empty') }}</p>
      <ul class="space-y-3"><li v-for="alert in store.alerts" :key="alert.id" class="rounded-xl border border-input-border p-4">
        <h2 class="font-medium text-text-default">{{ alert.name }}</h2><p class="break-words text-sm text-text-subtle">{{ alert.recipients.join(', ') }} · {{ tr(alert.frequency) }} · {{ alert.is_active ? tr('active') : tr('disable') }}</p>
        <div class="mt-3 flex flex-wrap gap-2"><BaseButton variant="secondary" @click="editAlert(alert)"><BaseActionIcon action="edit" />{{ tr('edit') }}</BaseButton><BaseButton variant="secondary" @click="applySearch(alert)"><BaseActionIcon action="search" />{{ tr('preview') }}</BaseButton><BaseButton variant="secondary" :loading="store.saving" @click="attempt(() => store.saveAlert({ is_active: !alert.is_active }, alert.id), tr('alertUpdated'))">{{ alert.is_active ? tr('disable') : tr('enable') }}</BaseButton></div>
      </li></ul>
    </template>
    <template v-else-if="tab === 'searches'">
      <BaseButton class="mb-4" data-testid="procurement-new-search" @click="editSearch()"><BaseActionIcon action="create" />{{ tr('saveSearch') }}</BaseButton>
      <p v-if="!store.searches.length">{{ tr('empty') }}</p>
      <ul class="space-y-3"><li v-for="search in store.searches" :key="search.id" class="rounded-xl border border-input-border p-4"><h2 class="font-medium">{{ search.name }}<span v-if="search.is_favorite"> ★</span></h2><div class="mt-3 flex flex-wrap gap-2"><BaseButton variant="secondary" @click="applySearch(search)"><BaseActionIcon action="filter" />{{ tr('apply') }}</BaseButton><BaseButton variant="secondary" @click="editSearch(search)"><BaseActionIcon action="edit" />{{ tr('edit') }}</BaseButton><BaseButton variant="secondary" @click="editAlert(null, search)"><BaseActionIcon action="create" />{{ tr('alertFromSearch') }}</BaseButton><BaseButton variant="danger-ghost" @click="deleteTarget = search"><BaseActionIcon action="delete" />{{ tr('delete') }}</BaseButton></div></li></ul>
    </template>
    <form v-else-if="tab === 'settings'" class="max-w-3xl space-y-5" @submit.prevent="attempt(() => store.saveSettings(settingsForm), tr('saved'))">
      <p class="text-sm text-text-subtle">{{ tr('timezone') }}</p>
      <BaseCheckbox v-model="settingsForm.sync_enabled">{{ tr('sync_enabled') }}</BaseCheckbox><br>
      <BaseCheckbox v-model="settingsForm.email_enabled">{{ tr('email_enabled') }}</BaseCheckbox>
      <div class="grid gap-4 sm:grid-cols-2"><BaseFormField v-for="key in ['sync_time', 'daily_time', 'weekly_time']" :key="key" :label="tr(key)" :for="`setting-${key}`"><BaseInput :id="`setting-${key}`" v-model="settingsForm[key]" type="time" /></BaseFormField><BaseFormField :label="tr('weekly_day')" for="weekly-day"><BaseSelect id="weekly-day" v-model="settingsForm.weekly_day" :options="weekdays" /></BaseFormField><BaseFormField :label="tr('lookback_days')" for="lookback-days"><BaseInput id="lookback-days" v-model="settingsForm.lookback_days" type="number" min="1" max="365" /></BaseFormField></div>
      <BaseButton data-testid="procurement-save" type="submit" :loading="store.saving">{{ tr('save') }}</BaseButton>
    </form>
    <template v-else-if="tab === 'deliveries'">
      <p v-if="!store.deliveries.length">{{ tr('empty') }}</p>
      <ul class="space-y-3"><li v-for="delivery in store.deliveries" :key="delivery.id" class="rounded-xl border border-input-border p-4"><h2 class="break-words font-medium">{{ delivery.recipient }}</h2><p class="text-sm text-text-subtle">{{ tr(delivery.status) }} · {{ tr(delivery.frequency) }} · {{ date(delivery.created_at) }} · {{ tr('attempts') }}: {{ delivery.attempts }}</p><p v-if="delivery.error" class="mt-2 text-sm text-text-default">{{ delivery.error }}</p><div class="mt-3 flex flex-wrap gap-2"><BaseButton v-if="['failed', 'uncertain'].includes(delivery.status)" variant="secondary" @click="retryTarget = delivery"><BaseActionIcon action="retry" />{{ tr('retry') }}</BaseButton><BaseButton v-if="delivery.opportunity_count || delivery.snapshot?.opportunities?.length" variant="secondary" @click="openSent(delivery)"><BaseActionIcon action="search" />{{ tr('viewSent') }}</BaseButton></div></li></ul>
      <div class="mt-4 flex gap-2"><BaseButton v-if="deliveryPage > 1" variant="secondary" @click="deliveryPage--; refresh()">{{ tr('previous') }}</BaseButton><BaseButton v-if="deliveryPage * 25 < store.deliveryCount" variant="secondary" @click="deliveryPage++; refresh()">{{ tr('next') }}</BaseButton></div>
    </template>
    <BaseModal :model-value="Boolean(modal)" kind="form-wide" padding="md" :close-on-backdrop="!store.saving" :close-on-esc="!store.saving" @update:model-value="value => { if (!value) modal = '' }">
      <form class="space-y-4" data-testid="procurement-record-form" @submit.prevent="saveForm">
        <h2 class="text-xl text-text-default">{{ tr(modal === 'alert' ? 'newAlert' : 'saveSearch') }}</h2>
        <p v-if="error" role="alert" class="text-sm text-text-default">{{ error }}</p>
        <BaseFormField :label="tr('name')" for="record-name"><BaseInput id="record-name" v-model="form.name" required maxlength="150" /></BaseFormField>
        <ProcurementFilters v-model="form.filters" />
        <template v-if="modal === 'alert'"><BaseFormField :label="tr('recipients')" for="alert-recipients"><BaseInput id="alert-recipients" v-model="form.recipients" required /><p class="text-xs text-text-subtle">{{ tr('maxRecipients') }}</p></BaseFormField><BaseFormField :label="tr('frequency')" for="alert-frequency"><BaseSelect id="alert-frequency" v-model="form.frequency" :options="frequencies" /></BaseFormField><BaseCheckbox v-model="form.is_active">{{ tr('active') }}</BaseCheckbox><p class="text-sm text-text-subtle">{{ tr('alertNotice') }}</p></template>
        <BaseCheckbox v-else v-model="form.is_favorite">{{ tr('favorite') }}</BaseCheckbox>
        <div class="flex justify-end gap-2"><BaseButton variant="secondary" :disabled="store.saving" :disabled-reason="tr('loading')" @click="modal = ''">{{ tr('cancel') }}</BaseButton><BaseButton data-testid="procurement-save" type="submit" :loading="store.saving">{{ tr('save') }}</BaseButton></div>
      </form>
    </BaseModal>
    <BaseModal :model-value="Boolean(deleteTarget || retryTarget)" kind="confirm" padding="md" @update:model-value="value => { if (!value) { deleteTarget = null; retryTarget = null } }"><h2 class="text-lg">{{ tr(deleteTarget ? 'confirmDelete' : 'confirmRetry') }}</h2><p v-if="retryTarget?.status === 'uncertain'" class="mt-3 text-sm">{{ tr('uncertainWarning') }}</p><p v-if="error" role="alert" class="mt-3">{{ error }}</p><div class="mt-5 flex justify-end gap-2"><BaseButton variant="secondary" @click="deleteTarget = null; retryTarget = null">{{ tr('cancel') }}</BaseButton><BaseButton :variant="deleteTarget ? 'danger' : 'primary'" :loading="store.saving" data-testid="procurement-confirm" @click="deleteTarget ? removeSearch() : retry()">{{ tr(deleteTarget ? 'delete' : 'retry') }}</BaseButton></div></BaseModal>
    <BaseModal :model-value="Boolean(sentContent)" kind="detail" padding="md" @update:model-value="value => { if (!value) sentContent = null }"><h2 class="text-lg">{{ tr('sentContent') }}</h2><article v-for="item in sentContent?.snapshot?.opportunities || []" :key="item.id" class="mt-4 border-b border-input-border pb-4"><h3 class="font-medium">{{ item.title }}</h3><p class="text-sm">{{ item.entity_name }} · {{ date(item.closing_at) }}</p><div v-for="alert in item.matched_alerts" :key="alert.name" class="mt-2 text-sm"><strong>{{ alert.name }}</strong><dl><template v-for="(value, key) in alert.filters" :key="key"><dt>{{ tr(key) }}</dt><dd class="break-words">{{ Array.isArray(value) ? value.join(', ') : value }}</dd></template></dl></div></article><BaseButton class="mt-4" variant="secondary" @click="sentContent = null">{{ tr('cancel') }}</BaseButton></BaseModal>
  </div>
</template>
