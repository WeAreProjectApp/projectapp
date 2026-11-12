<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
const props = defineProps({ decision: { type: Object, required: true }, type: { type: String, required: true }, inventory: { type: Object, required: true } })
const { t } = useI18n()
const proposal = computed(() => props.decision.result?.proposal || props.decision.payload)
const sourceLabel = id => {
  const source = props.inventory.accounting_sources.find(row => row.id === id)
  return source ? `#${id} · ${source.domain_url || t('hostingBilling.domainMissing')}` : `#${id}`
}
const sourceIds = computed(() => proposal.value.add_record_ids || proposal.value.hosting_record_ids || [])
const subscription = computed(() => props.inventory.subscriptions.find(row => row.id === proposal.value.subscription_id))
</script>
<template>
  <dl class="space-y-3 break-words text-sm" data-testid="hosting-decision-summary">
    <template v-if="type === 'identity'">
      <div><dt class="font-semibold text-text-default">{{ t('hostingBilling.subscription') }}</dt><dd class="text-text-muted">{{ subscription ? `#${subscription.id} · ${subscription.plan}` : t('hostingBilling.noSubscription') }}</dd></div>
      <div><dt class="font-semibold text-text-default">{{ t('hostingBilling.records') }}</dt><dd class="text-text-muted">{{ sourceIds.length ? sourceIds.map(sourceLabel).join('; ') : t('hostingBilling.noRecords') }}</dd></div>
      <div><dt class="font-semibold text-text-default">{{ t('hostingBilling.operational') }}</dt><dd class="text-text-muted">{{ proposal.operational_record_id ? sourceLabel(proposal.operational_record_id) : t('hostingBilling.noOperational') }}</dd></div>
    </template>
    <div v-else>
      <dt class="font-semibold text-text-default">{{ t('hostingBilling.evidence') }} · {{ proposal.label }}</dt>
      <dd class="text-text-muted">
        <ul class="space-y-1">
          <li v-for="id in proposal.payment_ids || []" :key="`payment-${id}`">{{ t('hostingBilling.payment', { id }) }}</li>
          <li v-for="id in proposal.cycle_ids || []" :key="`cycle-${id}`">{{ t('hostingBilling.cycle', { id }) }}</li>
          <li v-for="id in proposal.document_ids || []" :key="`account-${id}`">{{ t('hostingBilling.account', { id }) }}</li>
        </ul>
      </dd>
    </div>
    <div><dt class="font-semibold text-text-default">{{ t('hostingBilling.reason') }}</dt><dd class="text-text-muted">{{ decision.payload.reason }}</dd></div>
  </dl>
</template>
