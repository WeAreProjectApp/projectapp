<script setup>
import { useI18n } from 'vue-i18n'
import { ref, watch } from 'vue'
import { get_request, create_request } from '~/stores/services/request_http'
import { normalizeApiError } from '~/stores/services/normalize_api_error'
import { formatMoney } from '~/utils/formatMoney'
const { t } = useI18n()
const props = defineProps({ record: { type: Object, default: null }, referenceIncomeId: { type: Number, default: null } })
const emit = defineEmits(['close', 'created'])
const plan = ref(null), error = ref(''), busy = ref(false), loading = ref(false)
let sequence = 0
watch(() => [props.record?.id, props.referenceIncomeId], async ([id, reference]) => {
  const current = ++sequence
  plan.value = null; error.value = ''; busy.value = false; loading.value = false
  if (!id) return
  loading.value = true
  try {
    const suffix = reference ? `?reference_income_id=${reference}` : ''
    const { data } = await get_request(`accounting/hostings/${id}/next-income/${suffix}`)
    if (current === sequence) plan.value = data
  } catch (e) { if (current === sequence) error.value = normalizeApiError(e).message }
  finally { if (current === sequence) loading.value = false }
}, { immediate: true })
async function confirm() {
  if (!plan.value || busy.value || plan.value.existing_income_id) return
  busy.value = true; error.value = ''
  const current = sequence
  try {
    const payload = { version: plan.value.version }
    if (props.referenceIncomeId) payload.reference_income_id = props.referenceIncomeId
    const { data } = await create_request(`accounting/hostings/${props.record.id}/next-income/`, payload)
    if (current === sequence) { plan.value = data; emit('created', data.existing_income_id) }
  } catch (e) { if (current === sequence) error.value = normalizeApiError(e).message }
  finally { if (current === sequence) busy.value = false }
}
</script>

<template>
  <BaseModal :model-value="Boolean(record)" kind="confirm" title-id="next-hosting-income" @close="!busy && emit('close')">
    <div class="space-y-3 p-5" data-testid="hosting-next-income">
      <h2 id="next-hosting-income" class="text-lg font-semibold">{{ t('hostingBilling.nextTitle') }}</h2>
      <p v-if="loading" role="status">{{ t('hostingBilling.loadingCalendar') }}</p>
      <p v-if="error" role="alert" class="text-sm text-danger-strong">{{ error }}</p>
      <dl v-if="plan" class="space-y-2 text-sm">
        <div><dt>{{ t('hostingBilling.customerProject') }}</dt><dd>{{ plan.client_name }} · {{ plan.project_name }}</dd></div>
        <div><dt>{{ t('hostingBilling.service') }}</dt><dd>{{ plan.service }}</dd></div>
        <div><dt>{{ t('hostingBilling.concept') }}</dt><dd>{{ plan.fields.concept }}</dd></div>
        <div><dt>{{ t('hostingBilling.nextPeriod') }}</dt><dd>{{ plan.fields.period_start }} — {{ plan.fields.period_end }}</dd></div>
        <div><dt>{{ t('hostingBilling.value') }}</dt><dd>{{ formatMoney(plan.fields.total_amount, 'COP', { decimals: 'auto' }) }}</dd></div>
      </dl>
      <p v-if="plan?.existing_income_id" role="status">{{ t('hostingBilling.expectedCreated', { id: plan.existing_income_id }) }}</p>
    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton variant="secondary" :disabled="busy" @click="emit('close')">{{ plan?.existing_income_id ? t('hostingBilling.close') : t('hostingBilling.cancel') }}</BaseButton>
        <BaseButton v-if="plan && !plan.existing_income_id" :loading="busy" data-testid="hosting-next-confirm" @click="confirm">{{ t('hostingBilling.confirmCreate') }}</BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
