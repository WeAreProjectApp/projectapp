<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseModal from '~/components/base/BaseModal.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import HostingBillingPicker from './HostingBillingPicker.vue'
import { get_request } from '~/stores/services/request_http'
const props = defineProps({ modelValue: { type: Boolean, default: false }, record: { type: Object, default: null }, message: { type: String, default: '' }, resumeDraft: { type: Object, default: null } })
const emit = defineEmits(['update:modelValue', 'confirm', 'cancel', 'reconcile'])
const { t } = useI18n()
const hostingData = ref(null), error = ref(''), loading = ref(false), context = ref({})
const overview = computed(() => hostingData.value?.overview)
let sequence = 0
onBeforeUnmount(() => { sequence += 1 })
const source = computed(() => overview.value?.accounting_sources?.find(row => Number(row.id) === Number(props.record?.id)))
const projectId = computed(() => props.record?.project_id || props.record?.project)
const ready = computed(() => !projectId.value || (!loading.value && !error.value && source.value?.operational
  && !overview.value?.reconciliation_required && !hostingData.value?.selection?.requires_reconciliation
  && (!overview.value?.subscription || (overview.value.subscription.associated
    && overview.value.subscription.payments.some(row => Number(row.id) === Number(context.value.hosting_payment_id))))))
watch(() => [props.modelValue, props.record?.id], async () => {
  const request = ++sequence
  hostingData.value = null; context.value = {}; error.value = ''; loading.value = false
  if (!props.modelValue || !projectId.value) return
  loading.value = true
  try {
    const result = await get_request(`admin/billing-context/projects/${projectId.value}/hosting/`)
    if (request !== sequence) return
    hostingData.value = result.data
    context.value = { billing_nature: 'hosting', project_hosting_id: result.data.overview.hosting_id,
      hosting_payment_id: props.resumeDraft?.hosting_payment_id || null }
  } catch (err) { if (request === sequence) error.value = err.response?.data?.detail || t('hostingBilling.failed') }
  finally { if (request === sequence) loading.value = false }
})
function confirm() {
  if (!ready.value) return
  emit('confirm', { hosting_payment_id: context.value.hosting_payment_id || null }); emit('update:modelValue', false)
}
function cancel() { emit('cancel'); emit('update:modelValue', false) }
function reconcile() { emit('reconcile', { record: props.record, hosting_payment_id: context.value.hosting_payment_id || null }) }
</script>
<template>
  <BaseModal :model-value="modelValue" kind="confirm" @update:model-value="cancel">
    <div class="space-y-4 p-5">
      <h2 class="text-xl font-semibold">Enviar cuenta de cobro</h2><p class="text-sm">{{ message }}</p>
      <p v-if="loading" role="status">{{ t('hostingBilling.loading') }}</p>
      <p v-if="error" role="alert" class="text-danger-strong">{{ error }}</p>
      <template v-if="projectId && hostingData">
        <HostingBillingPicker v-model="context" :project-id="projectId" :data="hostingData" @refreshed="hostingData = $event" @reconcile="reconcile" />
        <template v-if="!source?.operational && !hostingData.selection?.requires_reconciliation">
          <p class="text-sm text-warning-strong">{{ t('hostingBilling.reconcileRequired') }}</p>
          <BaseButton variant="link" size="sm" @click="reconcile">{{ t('hostingBilling.reconcile') }}</BaseButton>
        </template>
      </template>
      <div class="flex flex-wrap justify-end gap-3">
        <BaseButton variant="secondary" @click="cancel">{{ t('hostingBilling.cancel') }}</BaseButton>
        <BaseButton :disabled="!ready" :loading="loading" :disabled-reason="t('hostingBilling.paymentRequired')" @click="confirm">Enviar al cliente</BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
