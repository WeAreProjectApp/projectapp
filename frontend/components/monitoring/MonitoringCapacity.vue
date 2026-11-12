<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { get_request, put_request } from '~/stores/services/request_http'
const props = defineProps({ resourceId: { type: [String, Number], required: true }, refreshKey: { type: Number, default: 0 } })
const { t, locale } = useI18n()
const tr = (key, values) => t(`monitoring.${key}`, values || {})
const data = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const saved = ref(false)
const history = ref(null)
const historyPage = ref(1)
const historyOpen = ref(false)
const form = reactive({ version: 0, cpu_mode: 'unknown', ram_mode: 'unknown', storage_mode: 'unknown', cpu: '', ram: '', storage: '' })
const dimensions = ['cpu', 'ram', 'storage']
const units = { cpu: 'vCPU', ram: 'GiB', storage: 'GiB' }
const modes = computed(() => ['unknown', 'shared', 'assigned'].map(value => ({ value, label: tr(`capacityModes.${value}`) })))
let requestId = 0, historyRequest = 0
const formatDate = value => new Date(value).toLocaleString(locale.value)
function fill(allocation) {
  form.version = allocation?.version || 0
  for (const dimension of dimensions) form[`${dimension}_mode`] = allocation?.[`${dimension}_mode`] || 'unknown'
  form.cpu = allocation?.cpu_vcpu ?? ''
  form.ram = allocation?.ram_bytes == null ? '' : allocation.ram_bytes / 1024 ** 3
  form.storage = allocation?.storage_bytes == null ? '' : allocation.storage_bytes / 1024 ** 3
}
async function load() {
  const id = ++requestId
  loading.value = true
  error.value = ''
  saved.value = false
  historyRequest++
  history.value = null
  try {
    const response = await get_request(`monitoring/resources/${props.resourceId}/capacity/`)
    if (id === requestId) { data.value = response.data; fill(response.data.allocation) }
  } catch { if (id === requestId) { data.value = null; error.value = tr('load') } }
  finally { if (id === requestId) loading.value = false }
}
async function save() {
  saving.value = true
  error.value = ''
  saved.value = false
  const id = requestId
  const payload = { version: form.version }
  for (const dimension of dimensions) {
    const mode = form[`${dimension}_mode`]
    payload[`${dimension}_mode`] = mode
    const field = dimension === 'cpu' ? 'cpu_vcpu' : `${dimension}_bytes`
    payload[field] = mode === 'assigned' ? Number(form[dimension]) * (dimension === 'cpu' ? 1 : 1024 ** 3) : null
    if (mode === 'assigned' && (!Number.isFinite(payload[field]) || payload[field] <= 0 || (dimension !== 'cpu' && !Number.isSafeInteger(payload[field])))) {
      error.value = tr('invalidCapacity'); saving.value = false; return
    }
  }
  try {
    const response = await put_request(`monitoring/resources/${props.resourceId}/capacity/`, payload)
    if (id === requestId) { data.value = response.data; fill(response.data.allocation); saved.value = true; history.value = null }
  } catch (failure) {
    if (id === requestId) error.value = failure.response?.status === 409 ? tr('capacityConflict') : tr('saveError')
  } finally { if (id === requestId) saving.value = false }
}
async function loadHistory(page = 1) {
  const id = requestId
  const historyId = ++historyRequest
  try {
    const response = await get_request(`monitoring/resources/${props.resourceId}/capacity/history/`, { params: { page } })
    if (id === requestId && historyId === historyRequest) { history.value = response.data; historyPage.value = page }
  } catch { if (id === requestId && historyId === historyRequest) error.value = tr('load') }
}
function describe(allocation, dimension) {
  const mode = allocation?.[`${dimension}_mode`] || 'unknown'
  if (mode !== 'assigned') return tr(`capacityModes.${mode}`)
  const value = dimension === 'cpu' ? Number(allocation.cpu_vcpu) : allocation[`${dimension}_bytes`] / 1024 ** 3
  return `${value} ${units[dimension]}`
}
watch(() => [props.resourceId, props.refreshKey], () => { saving.value = false; historyOpen.value = false; load() }, { immediate: true })
watch(historyOpen, open => { if (open && data.value?.allocation) loadHistory() })
onBeforeUnmount(() => { requestId++ })
</script>

<template>
  <section class="space-y-4 rounded-xl border border-border-default bg-surface p-4" data-testid="monitoring-capacity">
    <h3 class="font-medium text-text-default">{{ tr('projectCapacity') }}</h3>
    <p class="text-sm text-text-subtle">{{ tr('capacityExplanation') }}</p>
    <p v-if="loading" role="status">{{ tr('loading') }}</p>
    <p v-if="error" role="alert" class="text-sm text-text-default">{{ error }}</p>
    <template v-if="data && !loading">
      <p class="text-sm text-text-subtle">{{ data.resource.name }} · {{ tr('serverLabel') }}: {{ data.server_name || tr('notConfigured') }}</p>
      <form class="space-y-4" @submit.prevent="save">
        <fieldset :disabled="saving" class="grid gap-4 md:grid-cols-3">
          <div v-for="dimension in dimensions" :key="dimension" class="min-w-0 space-y-2">
            <MonitoringSelect v-model="form[`${dimension}_mode`]" :label="tr(dimension)" :options="modes" />
            <BaseFormField v-if="form[`${dimension}_mode`] === 'assigned'" :label="`${tr(dimension)} (${units[dimension]})`" :for="`capacity-${dimension}`">
              <BaseInput :id="`capacity-${dimension}`" v-model="form[dimension]" type="number" min="0.001" step="any" required :disabled="saving" />
            </BaseFormField>
          </div>
        </fieldset>
        <div class="flex flex-wrap gap-2">
          <BaseButton type="submit" :disabled="saving" :disabled-reason="tr('busy')">{{ tr('saveCapacity') }}</BaseButton>
          <BaseButton variant="secondary" :disabled="saving" :disabled-reason="tr('busy')" @click="load">{{ tr('reloadCapacity') }}</BaseButton>
        </div>
        <p v-if="saved" role="status" class="text-sm text-text-default">{{ tr('capacitySaved') }}</p>
      </form>
      <p class="text-xs text-text-subtle">{{ tr('projectConsumptionUnavailable') }}</p>
      <details v-if="data.allocation" :open="historyOpen" @toggle="historyOpen = $event.target.open">
        <summary class="cursor-pointer text-sm text-text-default">{{ tr('capacityHistory') }}</summary>
        <ol class="mt-3 space-y-3">
          <li v-for="change in history?.results || []" :key="change.id" class="rounded-lg border border-border-default p-3 text-sm">
            <p class="text-text-subtle">{{ change.actor_name }} · {{ formatDate(change.created_at) }}</p>
            <p v-for="dimension in dimensions" :key="dimension" class="break-words text-text-default">{{ tr(dimension) }}: {{ describe(change.before, dimension) }} → {{ describe(change.after, dimension) }}</p>
          </li>
        </ol>
        <BasePagination v-if="history" :current-page="historyPage" :total-pages="Math.max(1, Math.ceil(history.count / history.page_size))" :total-items="history.count" :range-from="history.count ? (historyPage - 1) * history.page_size + 1 : 0" :range-to="Math.min(historyPage * history.page_size, history.count)" @prev="loadHistory(historyPage - 1)" @next="loadHistory(historyPage + 1)" @go="loadHistory" />
      </details>
    </template>
    <BaseButton v-else-if="!loading" variant="secondary" @click="load">{{ tr('refresh') }}</BaseButton>
  </section>
</template>
