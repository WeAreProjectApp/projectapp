<script setup>
import { useI18n } from 'vue-i18n'
import { formatMoney } from '~/utils/formatMoney'
defineProps({ period: { type: Object, required: true }, showBlocker: { type: Boolean, default: true } })
const { t } = useI18n()
const money = value => formatMoney(value, 'COP', { decimals: 'auto' })
</script>

<template>
  <div class="space-y-1 text-sm" data-testid="hosting-period-summary" aria-live="polite">
    <template v-if="period.period_start">
      <p class="font-semibold">{{ t('hostingBilling.period') }} · {{ period.period_start }} — {{ period.period_end }}</p>
      <p>{{ t('hostingBilling.' + period.source) }} #{{ period.hosting_payment_id || period.income_id }}
        · {{ t('hostingBilling.states.' + period.state) }}</p>
      <p>{{ t('hostingBilling.price') }} {{ money(period.amount) }} · {{ t('hostingBilling.received') }} {{ money(period.received) }}
        · {{ t('hostingBilling.balance') }} {{ money(period.balance) }}</p>
      <p v-if="Number(period.deductions) > 0">{{ t('hostingBilling.deductions') }} {{ money(period.deductions) }}</p>
      <p v-if="Number(period.rescheduled) > 0">{{ t('hostingBilling.rescheduled') }} {{ money(period.rescheduled) }}</p>
      <p v-for="document in period.documents" :key="document.id">
        {{ t('hostingBilling.account', { id: document.number || document.id }) }} · {{ t('hostingBilling.documentStates.' + document.state) }}
      </p>
    </template>
    <p v-if="showBlocker && period.blocker" role="alert" class="text-warning-strong">{{ period.blocker }}</p>
  </div>
</template>
