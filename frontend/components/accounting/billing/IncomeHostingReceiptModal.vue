<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { get_request } from '~/stores/services/request_http'
import { normalizeApiError } from '~/stores/services/normalize_api_error'
import HostingCycleReceiptForm from './HostingCycleReceiptForm.vue'

const props = defineProps({ income: { type: Object, default: null } })
const emit = defineEmits(['close', 'changed'])
const { t } = useI18n()
const record = ref(null)
const error = ref('')
let sequence = 0

watch(() => props.income, async income => {
  const current = ++sequence
  record.value = null
  error.value = ''
  if (!income) return
  try {
    const projectId = income.project_id || income.project
    const { data } = await get_request(`admin/billing-context/projects/${projectId}/hosting/`)
    if (current !== sequence) return
    const source = data.overview.accounting_sources.find(row => row.operational)
    if (!source) {
      error.value = t('hostingBilling.reconcileRequired')
      return
    }
    const detail = await get_request(`accounting/hostings/${source.id}/`)
    if (current === sequence) record.value = detail.data
  } catch (err) {
    if (current === sequence) error.value = normalizeApiError(err).message
  }
}, { immediate: true })
</script>

<template>
  <BaseModal :model-value="Boolean(income)" kind="form" @close="emit('close')">
    <div class="space-y-3 p-5">
      <h2 class="text-lg font-semibold">{{ t('hostingBilling.reviewReceipt') }}</h2>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-else-if="!record" role="status">{{ t('hostingBilling.loading') }}</p>
      <HostingCycleReceiptForm v-else :record="record" :fixed-income-id="income.id" @changed="emit('changed')" />
    </div>
  </BaseModal>
</template>
