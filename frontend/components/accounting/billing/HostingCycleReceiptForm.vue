<script setup>
import { useI18n } from 'vue-i18n'
import { computed, ref, watch } from 'vue'
import { get_request, create_request } from '~/stores/services/request_http'
import { useAccountingStore } from '~/stores/accounting'
import { normalizeApiError } from '~/stores/services/normalize_api_error'
import { emptyReceipt, receiptPayload, requestUuid } from '~/utils/hostingReceipt'
import { addMonths, todayISO } from '~/utils/periodDates'
import { formatMoney } from '~/utils/formatMoney'
import HostingReceiptFields from './HostingReceiptFields.vue'
import HostingPeriodSummary from './HostingPeriodSummary.vue'

const { t } = useI18n()
const props = defineProps({ record: { type: Object, required: true }, fixedIncomeId: { type: Number, default: null } })
const emit = defineEmits(['changed', 'next-income'])
const store = useAccountingStore()
const incomes = ref([]), incomeId = ref(''), amount = ref(null), paidAt = ref(todayISO()), notes = ref('')
const modality = ref(''), destination = ref('pocket'), advance = ref(true), receipt = ref(emptyReceipt())
const busy = ref(false), loading = ref(false), error = ref(''), review = ref(null), saved = ref(null)
const sending = ref(false), sendMessage = ref('')
const requestId = ref(''); let sequence = 0
const url = computed(() => `accounting/hostings/${props.record.id}/cycle-receipt/`)
const selected = computed(() => incomes.value.find(row => row.income_id === Number(incomeId.value)))
const options = computed(() => incomes.value.map(row => ({ value: row.income_id,
  label: `#${row.income_id} · ${row.concept} · ${row.period_start || t('hostingBilling.blocked')}` })))
const modalities = computed(() => [
  { value: 'quarterly', label: t('hostingBilling.modality.quarterly') }, { value: 'semiannual', label: t('hostingBilling.modality.semiannual') }, { value: 'nine_month', label: t('hostingBilling.modality.nine_month') },
  ...(['monthly', 'annual'].includes(props.record.payment_modality) ? [{ value: props.record.payment_modality, label: props.record.payment_modality_label }] : []),
])
const validityTarget = computed(() => addMonths(props.record.valid_to || paidAt.value,
  { monthly: 1, quarterly: 3, semiannual: 6, nine_month: 9, annual: 12 }[modality.value] || 1))
const identity = computed(() => selected.value && receiptPayload(receipt.value, [selected.value]))
const block = computed(() => {
  if (!selected.value) return t('hostingBilling.selectIncome')
  if (!selected.value.period_start) return selected.value.blocker
  if (!identity.value) return t('hostingBilling.identify')
  if (!(Number(amount.value) > 0) || !paidAt.value) return t('hostingBilling.amountDate')
  return ''
})
function reset() {
  receipt.value = emptyReceipt(); amount.value = null; notes.value = ''; review.value = null
  paidAt.value = todayISO(); modality.value = props.record.payment_modality; destination.value = 'pocket'
  advance.value = !props.fixedIncomeId; requestId.value = requestUuid()
}
async function load() {
  const current = ++sequence
  loading.value = true; busy.value = false; error.value = ''; incomes.value = []; incomeId.value = ''; reset()
  try {
    const { data } = await get_request(url.value)
    if (current !== sequence) return
    incomes.value = props.fixedIncomeId ? data.incomes.filter(row => row.income_id === props.fixedIncomeId) : data.incomes
    if (incomes.value.length === 1) incomeId.value = String(incomes.value[0].income_id)
    error.value = data.blocker || (!incomes.value.length ? t('hostingBilling.missingIncome') : '')
  } catch (e) { if (current === sequence) error.value = normalizeApiError(e).message }
  finally { if (current === sequence) loading.value = false }
}
watch([() => props.record.id, () => props.fixedIncomeId], () => { saved.value = null; sending.value = false; sendMessage.value = ''; load() }, { immediate: true })
watch(incomeId, () => { reset(); amount.value = selected.value ? Number(selected.value.balance) || null : null })
watch(() => receipt.value.entries, entries => {
  const evidence = entries.find(row => row.income_id === selected.value?.income_id)
  const source = selected.value?.liquids?.find(row => row.id === evidence?.liquid_id)
    || selected.value?.cycles?.find(row => row.id === evidence?.cycle_id)
  if (source) { amount.value = Number(source.amount); paidAt.value = source.date; if (source.destination) destination.value = source.destination }
})
function payload() {
  const data = { income_id: Number(incomeId.value), amount: String(amount.value), paid_at: paidAt.value,
    destination: destination.value, notes: notes.value, hosting_receipt: identity.value,
    advance_validity: advance.value, request_id: requestId.value }
  if (['quarterly', 'semiannual', 'nine_month'].includes(modality.value)) data.modality = modality.value
  return data
}
async function submit() {
  if (busy.value || block.value) return
  const current = sequence
  const body = review.value?.body || payload()
  busy.value = true; error.value = ''
  try {
    if (!review.value) {
      const { data } = await create_request(url.value + '?preview=1', body)
      if (current === sequence) review.value = { data, body: { ...body, preview_hash: data.preview_hash } }
    } else {
      const { data } = await create_request(url.value, body)
      if (current !== sequence) return
      saved.value = data; review.value = null; sending.value = false; sendMessage.value = ''
      emit('changed')
    }
  } catch (e) { if (current === sequence) { error.value = normalizeApiError(e).message; review.value = null } }
  finally { if (current === sequence) busy.value = false }
}
async function documentPayment() {
  if (busy.value || !saved.value) return
  busy.value = true
  const current = sequence
  const result = await store.sendHostingCollectionAccount(props.record.id, {
    receipt_allocation_id: saved.value.allocation_id, period_version: saved.value.period.version,
    hosting_payment_id: saved.value.period.hosting_payment_id,
  })
  if (current !== sequence) return
  busy.value = false; sending.value = false
  if (!result.success) {
    error.value = result.message
    try {
      const { data } = await get_request(url.value)
      const period = data.incomes.find(row => row.income_id === saved.value?.period.income_id)
      if (current === sequence && period?.documents?.length) saved.value.period = period
    } catch { /* The durable issue error remains visible when refresh is unavailable. */ }
    return
  }
  const doc = result.data.document
  saved.value.period.documents = [{ id: doc.id, number: doc.public_number, state: doc.commercial_status }]
  sendMessage.value = result.data.email_sent ? t('hostingBilling.sent') : t('hostingBilling.sendFailed')
}
</script>

<template>
  <section class="space-y-4">
    <p v-if="loading" role="status">{{ t('hostingBilling.loadingIncomes') }}</p>
    <p v-if="error" role="alert" class="text-sm text-danger-strong">{{ error }}</p>
    <div v-if="saved" class="space-y-3" data-testid="cycle-payment-recorded">
      <p role="status">{{ saved.already_registered ? t('hostingBilling.alreadyRecorded') : t('hostingBilling.recorded') }}</p>
      <HostingPeriodSummary :period="saved.period" :show-blocker="false" />
      <p v-if="sendMessage" role="status">{{ sendMessage }}</p>
      <div class="flex flex-wrap gap-2">
        <BaseButton v-if="!fixedIncomeId" data-testid="cycle-next-income" @click="emit('next-income', saved.period.income_id)">{{ t('hostingBilling.createNext') }}</BaseButton>
        <BaseButton v-if="!saved.period.documents.length && !sending" variant="secondary" @click="sending = true">{{ t('hostingBilling.documentReceipt') }}</BaseButton>
        <BaseButton variant="ghost" @click="saved = null; load()">{{ t('hostingBilling.backPayments') }}</BaseButton>
      </div>
      <div v-if="sending" class="space-y-2">
        <p>{{ t('hostingBilling.documentPrompt', { email: record.billing_email }) }}</p>
        <BaseButton :loading="busy" @click="documentPayment">{{ t('hostingBilling.confirmSend') }}</BaseButton>
        <BaseButton variant="secondary" @click="sending = false">{{ t('hostingBilling.cancel') }}</BaseButton>
      </div>
    </div>
    <form v-else-if="!loading && incomes.length" class="space-y-3" @submit.prevent="submit">
      <template v-if="!review">
        <BaseFormField :label="t('hostingBilling.incomeField')">
          <BaseSelect v-model="incomeId" :options="options" :placeholder="t('hostingBilling.chooseIncome')" :disabled="Boolean(fixedIncomeId)" :disabled-reason="fixedIncomeId ? t('hostingBilling.incomeFixed') : ''" data-testid="cycle-income" />
        </BaseFormField>
        <HostingReceiptFields v-if="selected" v-model="receipt" :periods="[selected]" />
        <BaseFormRow :cols="2">
          <BaseFormField :label="t('hostingBilling.amountPaid')"><BaseCurrencyInput v-model="amount" :decimals="2" required data-testid="cycle-amount" /></BaseFormField>
          <BaseFormField :label="t('hostingBilling.datePaid')"><BaseInput v-model="paidAt" type="date" required /></BaseFormField>
          <BaseFormField :label="t('hostingBilling.cycleModality')"><BaseSelect v-model="modality" :options="modalities" /></BaseFormField>
          <BaseFormField :label="t('hostingBilling.destination')"><BaseSelect v-model="destination" :options="[{ value: 'pocket', label: t('hostingBilling.pocket') }, { value: 'partners', label: t('hostingBilling.partners') }]" /></BaseFormField>
          <BaseFormField :label="t('hostingBilling.notes')"><BaseInput v-model="notes" /></BaseFormField>
        </BaseFormRow>
        <label v-if="!fixedIncomeId" class="flex items-center gap-2"><BaseToggle v-model="advance" data-testid="cycle-advance-validity" :aria-label="t('hostingBilling.extend')" />
          {{ t('hostingBilling.extend') }} <span v-if="validityTarget">{{ t('hostingBilling.until', { date: validityTarget }) }}</span>
        </label>
      </template>
      <div v-else class="space-y-2" data-testid="cycle-receipt-review">
        <p>{{ review.data.already_registered ? t('hostingBilling.linkRecorded') : t('hostingBilling.confirmNew') }} ·
          {{ formatMoney(amount, 'COP') }} · {{ paidAt }}</p>
        <HostingPeriodSummary :period="selected" :show-blocker="false" />
        <p v-if="review.data.rows[0]?.validity_target">{{ t('hostingBilling.validity', { date: review.data.rows[0].validity_target }) }}</p>
        <BaseButton type="button" variant="secondary" :disabled="busy" @click="review = null">{{ t('hostingBilling.cancelReview') }}</BaseButton>
      </div>
      <BaseButton type="submit" :loading="busy" :disabled="Boolean(block) || busy" :disabled-reason="block" data-testid="cycle-submit">
        {{ review ? t('hostingBilling.confirmPayment') : t('hostingBilling.reviewPayment') }}
      </BaseButton>
    </form>
  </section>
</template>
