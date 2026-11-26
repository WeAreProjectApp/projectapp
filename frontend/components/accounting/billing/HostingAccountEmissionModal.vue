<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseModal from '~/components/base/BaseModal.vue'
import { get_request } from '~/stores/services/request_http'
import { formatMoney } from '~/utils/formatMoney'
import HostingPeriodSummary from './HostingPeriodSummary.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  record: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'confirm', 'cancel', 'reconcile'])
const { t } = useI18n()
const projectId = computed(() => props.record?.project ?? props.record?.project_id)
const data = ref(null)
const loading = ref(false)
const readFailed = ref(false)
const submitted = ref(false)

const rowIssue = computed(() => {
  if (!props.record?.id || !projectId.value) return t('hostingBilling.rowEmission.linkProject')
  if (!props.record.client) return t('hostingBilling.rowEmission.linkClient')
  if (!props.record.billing_email?.trim()) return t('hostingBilling.rowEmission.addRecipient')
  return ''
})

function sameId(left, right) {
  return left != null && right != null && String(left) === String(right)
}

const contextIssue = computed(() => {
  if (!data.value) return ''
  const { overview, selection, billing_period: period } = data.value
  if (!sameId(overview?.project_id, projectId.value)) return t('hostingBilling.rowEmission.identityConflict')
  const source = overview.accounting_sources?.find(item => sameId(item.id, props.record.id))
  const selectionReason = selection?.blockers?.find(item => item.message)?.message
  if (selectionReason) return selectionReason
  if (!source?.operational || source.associated === false) return t('hostingBilling.rowEmission.historical')
  if (selection?.requires_reconciliation !== false || overview.reconciliation_required !== false) return t('hostingBilling.reconcileRequired')
  // PA-296 can return just the reason when there is no eligible period.
  if (period?.blocker && !period.period_start) return ''
  if (!period?.version || !period.period_start || !period.period_end || period.balance == null || !period.currency) {
    return t('hostingBilling.rowEmission.noPeriod')
  }
  if (!sameId(period.hosting_record_id, props.record.id) || !sameId(period.client_id, props.record.client)
    || !sameId(period.project_id, projectId.value) || !sameId(period.project_hosting_id, overview.hosting_id)) {
    return t('hostingBilling.rowEmission.identityConflict')
  }
  return ''
})

const period = computed(() => !rowIssue.value && !contextIssue.value ? data.value?.billing_period : null)
const blocker = computed(() => rowIssue.value || (readFailed.value && t('hostingBilling.rowEmission.readFailed'))
  || contextIssue.value || period.value?.blocker || '')
const ready = computed(() => props.modelValue && !loading.value && !submitted.value && !blocker.value && Boolean(period.value?.version))
const projectName = computed(() => props.record?.project_name
  || (sameId(data.value?.overview?.project_id, projectId.value) && data.value.overview.project_name)
  || (projectId.value && '#' + projectId.value) || '—')

watch([() => props.modelValue, () => props.record?.id, projectId, () => props.record?.client, () => props.record?.billing_email],
  async ([open], _previous, onCleanup) => {
    let current = true
    onCleanup(() => { current = false })
    data.value = null
    readFailed.value = false
    submitted.value = false
    loading.value = false
    if (!open || rowIssue.value) return
    loading.value = true
    try {
      const response = await get_request(`admin/billing-context/projects/${projectId.value}/hosting/`)
      if (current) {
        data.value = response.data
        readFailed.value = !response.data
      }
    } catch {
      if (current) readFailed.value = true
    } finally {
      if (current) loading.value = false
    }
  }, { immediate: true })

function confirm() {
  if (!ready.value) return
  submitted.value = true
  emit('confirm', { hosting_payment_id: period.value.hosting_payment_id, period_version: period.value.version })
  emit('update:modelValue', false)
}

function cancel() {
  data.value = null
  emit('cancel')
  emit('update:modelValue', false)
}
</script>

<template>
  <BaseModal :model-value="modelValue" kind="confirm" @update:model-value="cancel">
    <div class="space-y-4 p-5">
      <h2 class="text-xl font-semibold">{{ t('hostingBilling.sendAccount') }}</h2>
      <dl v-if="record" class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
        <dt class="text-text-subtle">{{ t('hostingBilling.rowEmission.project') }}</dt>
        <dd>{{ projectName }}</dd>
        <dt class="text-text-subtle">{{ t('hostingBilling.rowEmission.client') }}</dt>
        <dd>{{ record.client_display_name || record.client_name || (record.client && '#' + record.client) || '—' }}</dd>
        <dt class="text-text-subtle">{{ t('hostingBilling.service') }}</dt>
        <dd class="break-words">{{ record.domain_url || record.display_label || 'Hosting #' + record.id }}</dd>
        <dt class="text-text-subtle">{{ t('hostingBilling.rowEmission.recipient') }}</dt>
        <dd class="break-words">{{ record.billing_email || '—' }}</dd>
      </dl>
      <p v-if="loading" role="status">{{ t('hostingBilling.loading') }}</p>
      <HostingPeriodSummary v-if="period" :period="period" />
      <p v-if="blocker && !period?.blocker" role="alert" class="text-warning-strong">{{ blocker }}</p>
      <BaseButton
        v-if="!rowIssue && (contextIssue || period?.blocker)" variant="link" size="sm"
        @click="emit('reconcile', { record, hosting_payment_id: period?.hosting_payment_id ?? null })"
      >{{ t('hostingBilling.reconcile') }}</BaseButton>
      <p v-if="ready" class="text-sm">
        {{ t('hostingBilling.rowEmission.delivery', { amount: formatMoney(period.balance, period.currency, { decimals: 'auto' }) }) }}
      </p>
      <div class="flex flex-wrap justify-end gap-3">
        <BaseButton variant="secondary" @click="cancel">{{ t('hostingBilling.cancel') }}</BaseButton>
        <BaseButton :disabled="!ready" :loading="loading" :disabled-reason="blocker" @click="confirm">
          {{ t('hostingBilling.sendClient') }}
        </BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
