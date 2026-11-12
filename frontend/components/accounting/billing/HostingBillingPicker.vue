<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '~/components/base/BaseButton.vue'
import HostingFormModal from '~/components/accounting/HostingFormModal.vue'
import { INPUT_FIELD_BASE, INPUT_FIELD_SIZE } from '~/components/base/inputClasses'
import { get_request, create_request } from '~/stores/services/request_http'
import { useAccountingStore } from '~/stores/accounting'

const props = defineProps({
  projectId: { type: [String, Number], required: true },
  client: { type: Object, default: null },
  modelValue: { type: Object, required: true },
  data: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'refreshed', 'reconcile', 'validation-message', 'nested-open'])
const { t } = useI18n()
const store = useAccountingStore()
const choice = ref(''), preview = ref(null), busy = ref(false), error = ref(''), creating = ref(false)
const fieldClass = `${INPUT_FIELD_BASE} ${INPUT_FIELD_SIZE.md}`
const selection = computed(() => props.data?.selection)
const candidates = computed(() => selection.value?.candidates || [])
const keyFor = row => row.hosting_record_id ? `record:${row.hosting_record_id}` : `hosting:${row.project_hosting_id}`
const selected = computed(() => candidates.value.find(row => keyFor(row) === choice.value))
const subscription = computed(() => props.data?.overview?.subscription)
const payments = computed(() => subscription.value?.associated ? subscription.value.payments || [] : [])
const blockers = computed(() => selection.value?.blockers || [])
const confirmed = computed(() => candidates.value.some(row => row.selectable && !row.requires_association
  && Number(row.project_hosting_id) === Number(props.modelValue.project_hosting_id)))
const validation = computed(() => {
  if (blockers.value.length) return blockers.value[0].message
  if (!confirmed.value) return t('hostingBilling.chooseRequired')
  if (subscription.value && !payments.value.length) return t('hostingBilling.paymentEmpty')
  if (subscription.value && !payments.value.some(row => Number(row.id) === Number(props.modelValue.hosting_payment_id))) return t('hostingBilling.paymentRequired')
  return ''
})
let sequence = 0, revision = 0
onBeforeUnmount(() => { sequence += 1 })
watch(() => props.modelValue, () => { revision += 1; preview.value = null }, { deep: true, flush: 'sync' })
watch(() => props.data, () => { preview.value = null; choice.value = ''; sequence += 1; busy.value = false })
watch(() => props.projectId, () => { sequence += 1; creating.value = false; choice.value = ''; preview.value = null; error.value = ''; busy.value = false }, { flush: 'sync' })
watch(validation, message => emit('validation-message', message), { immediate: true })
watch(creating, value => emit('nested-open', value), { flush: 'sync' })
function label(row) {
  const modality = row.payment_modality ? t(`hostingBilling.modality.${row.payment_modality}`) : ''
  return [row.domain_url || t('hostingBilling.domainMissing'), modality,
    t(row.is_active ? 'hostingBilling.active' : 'hostingBilling.inactive'),
    row.historical ? t('hostingBilling.historical') : ''].filter(Boolean).join(' · ')
}
function choose(value) {
  choice.value = value; preview.value = null; error.value = ''
  emit('update:modelValue', { ...props.modelValue, project_hosting_id: null, hosting_payment_id: null })
}
function selectHosting(id) {
  emit('update:modelValue', { billing_nature: 'hosting', contract_id: null, amendment_id: null,
    project_hosting_id: id, hosting_payment_id: null })
}
async function refresh() {
  const request = ++sequence
  busy.value = true; preview.value = null; error.value = ''
  try {
    const result = await get_request(`admin/billing-context/projects/${props.projectId}/hosting/`)
    if (request === sequence) emit('refreshed', result.data)
  } catch (err) { if (request === sequence) error.value = err.response?.data?.detail || t('hostingBilling.failed') }
  finally { if (request === sequence) busy.value = false }
}
async function review() {
  const row = selected.value
  if (!row?.selectable || busy.value) return
  if (!row.requires_association) { selectHosting(row.project_hosting_id); return }
  const request = ++sequence, contextRevision = revision
  const payload = {
    expected_version: selection.value.version,
    subscription_id: props.data.inventory.hosting?.subscription_id || null,
    hosting_record_ids: [...new Set([...(props.data.inventory.hosting?.hosting_record_ids || []), row.hosting_record_id])],
    operational_record_id: row.hosting_record_id, reason: t('hostingBilling.auditReason'),
  }
  busy.value = true; error.value = ''
  try {
    await create_request(`admin/billing-context/projects/${props.projectId}/hosting/?preview=1`, payload)
    if (request === sequence && contextRevision === revision) preview.value = { payload, label: label(row) }
  } catch (err) { if (request === sequence && contextRevision === revision) error.value = err.response?.data?.detail || t('hostingBilling.failed') }
  finally { if (request === sequence) busy.value = false }
}
async function confirmLink() {
  if (!preview.value || busy.value) return
  const payload = preview.value.payload, projectId = props.projectId
  const request = ++sequence, contextRevision = revision
  busy.value = true; error.value = ''
  try {
    const result = await create_request(`admin/billing-context/projects/${projectId}/hosting/`, payload)
    if (request !== sequence || contextRevision !== revision) return
    const refreshed = await get_request(`admin/billing-context/projects/${projectId}/hosting/`)
    if (request !== sequence || contextRevision !== revision) return
    emit('refreshed', refreshed.data)
    selectHosting(result.data.id)
    preview.value = null
  } catch (err) { if (request === sequence && contextRevision === revision) { preview.value = null; error.value = err.response?.data?.detail || t('hostingBilling.failed') } }
  finally { if (request === sequence) busy.value = false }
}
async function createHosting(payload) {
  if (busy.value || !selection.value?.can_create || !props.client?.id) return
  const request = ++sequence, contextRevision = revision, projectId = props.projectId
  busy.value = true; error.value = ''
  const result = await store.createRecord('hostings', { ...payload, client: props.client.id, project: Number(projectId) })
  if (request !== sequence) return
  if (!result.success) { busy.value = false; error.value = result.message || t('hostingBilling.createFailed'); return }
  creating.value = false
  // Creation registers the new origin through the existing writer. The operator
  // still chooses and confirms its use for this account after refreshing.
  if (contextRevision !== revision) { busy.value = false; return }
  await refresh()
}
</script>
<template>
  <section class="space-y-3" data-testid="billing-hosting-picker">
    <p v-if="!data" role="status" class="text-sm text-text-muted">{{ t('hostingBilling.loading') }}</p>
    <template v-else>
      <label v-if="candidates.length" class="block text-sm text-text-default">{{ t('hostingBilling.title') }}
        <select :value="choice" :class="fieldClass" :disabled="busy" data-testid="billing-hosting-choice" @change="choose($event.target.value)">
          <option value="">{{ t('hostingBilling.choose') }}</option>
          <option v-for="row in candidates" :key="keyFor(row)" :value="keyFor(row)" :disabled="!row.selectable">{{ label(row) }}</option>
        </select>
      </label>
      <p v-if="selection?.can_create" class="text-sm text-text-muted" data-testid="billing-hosting-empty">{{ t('hostingBilling.empty') }}</p>
      <p v-else-if="!candidates.some(row => row.selectable)" class="text-sm text-text-muted">{{ t('hostingBilling.noEligible') }}</p>
      <ul v-if="blockers.length" class="space-y-1 text-sm text-warning-strong" data-testid="billing-hosting-blockers">
        <li v-for="(blocker, index) in blockers" :key="index">{{ blocker.message }}</li>
      </ul>
      <BaseButton v-if="selected?.selectable && !preview" size="sm" :loading="busy" data-testid="billing-hosting-review" @click="review">{{ t(selected.requires_association ? 'hostingBilling.review' : 'hostingBilling.use') }}</BaseButton>
      <section v-if="preview" class="space-y-2 rounded-xl border border-border-default p-3" data-testid="billing-hosting-link-preview">
        <h5 class="font-semibold text-text-default">{{ t('hostingBilling.reviewTitle') }}</h5>
        <p class="break-words text-sm text-text-default">{{ preview.label }}</p>
        <p class="text-sm text-text-muted">{{ t('hostingBilling.reviewHelp') }}</p>
        <p class="text-xs text-text-muted">{{ t('hostingBilling.reason') }}: {{ preview.payload.reason }}</p>
        <div class="flex flex-wrap gap-2">
          <BaseButton size="sm" :loading="busy" data-testid="billing-hosting-confirm" @click="confirmLink">{{ t('hostingBilling.confirm') }}</BaseButton>
          <BaseButton size="sm" variant="secondary" @click="preview = null">{{ t('hostingBilling.cancel') }}</BaseButton>
        </div>
      </section>
      <p v-if="confirmed" role="status" class="text-sm text-success-strong" data-testid="billing-hosting-confirmed">{{ t('hostingBilling.selected') }}</p>
      <label v-if="confirmed && payments.length" class="block text-sm text-text-default">{{ t('hostingBilling.period') }}
        <select :value="modelValue.hosting_payment_id || ''" :class="fieldClass" data-testid="billing-payment" @change="emit('update:modelValue', { ...modelValue, hosting_payment_id: Number($event.target.value) || null })">
          <option value="">{{ t('hostingBilling.choosePeriod') }}</option>
          <option v-for="payment in payments" :key="payment.id" :value="payment.id">#{{ payment.id }} · {{ payment.billing_period_start }} — {{ payment.billing_period_end }} · {{ payment.amount }} · {{ payment.status }}</option>
        </select>
      </label>
      <p v-if="confirmed && subscription && !payments.length" role="alert" class="text-sm text-warning-strong">{{ t('hostingBilling.paymentEmpty') }}</p>
      <div class="flex flex-wrap gap-3">
        <BaseButton v-if="selection?.can_create && client?.id" size="sm" variant="secondary" data-testid="billing-hosting-create" @click="creating = true">{{ t('hostingBilling.create') }}</BaseButton>
        <BaseButton v-if="selection?.requires_reconciliation" size="sm" variant="link" data-testid="billing-hosting-reconcile" @click="emit('reconcile')">{{ t('hostingBilling.reconcile') }}</BaseButton>
        <BaseButton size="sm" variant="link" :loading="busy" data-testid="billing-hosting-refresh" @click="refresh">{{ t('hostingBilling.refresh') }}</BaseButton>
      </div>
    </template>
    <p v-if="error" role="alert" class="text-sm text-danger-strong" data-testid="billing-hosting-error">{{ error }}</p>
    <HostingFormModal v-if="creating" :open="creating" :saving="busy" :initial-context="{ client, projectId }"
      :context-label="t('hostingBilling.owner', { client: client?.name, project: data?.inventory?.project_name })" :submit-error="error"
      @close="!busy && (creating = false)" @submit="createHosting" />
  </section>
</template>
