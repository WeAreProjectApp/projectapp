<script setup>
import { watch } from 'vue'
import { usePlatformBillingStore } from '~/stores/platform-billing'
const props = defineProps({ projectId: { type: [String, Number], required: true }, showPayments: { type: Boolean, default: true } })
const store = usePlatformBillingStore()
const localePath = useLocalePath()
const { t, locale } = useI18n()
const money = value => new Intl.NumberFormat(locale.value, { style: 'currency', currency: 'COP' }).format(Number(value))
const accountsHref = () => localePath({ path: `/platform/projects/${props.projectId}/collection-accounts`, query: { nature: 'hosting' } })
watch(() => props.projectId, id => store.fetchHosting(id), { immediate: true })
</script>
<template>
  <section class="mb-6 space-y-4 rounded-2xl border border-border-default bg-surface p-4 sm:p-5" data-testid="project-hosting-context">
    <h2 class="text-lg font-semibold text-text-default">{{ t('platformBilling.projectHosting') }}</h2>
    <p v-if="store.loading.hosting" role="status">{{ t('platformBilling.loading') }}</p>
    <div v-else-if="store.errors.hosting" role="alert"><p>{{ store.errors.hosting }}</p><button class="text-text-brand" @click="store.fetchHosting(projectId)">{{ t('platformBilling.retry') }}</button></div>
    <template v-else-if="store.hosting">
      <p v-if="!store.hosting.has_hosting" class="text-text-muted">{{ t('platformBilling.noHosting') }}</p>
      <template v-else>
        <p class="text-sm text-text-muted">{{ t('platformBilling.hostingIndependent') }}</p>
        <p v-if="store.hosting.reconciliation_required" class="rounded-xl bg-warning-soft p-3 text-sm text-warning-strong">{{ t('platformBilling.sourcesPending') }}</p>
        <div class="flex flex-wrap gap-4">
          <NuxtLink :to="accountsHref()" class="font-medium text-text-brand">{{ t('platformBilling.hostingAccounts') }}</NuxtLink>
        </div>
        <section v-if="showPayments && store.hosting.subscription" class="space-y-3">
          <h3 class="font-semibold">{{ t('platformBilling.subscriptionPayments') }}</h3>
          <p class="text-sm">{{ t(`platformBilling.states.${store.hosting.subscription.status}`) }} · {{ t(`platformBilling.modalities.${store.hosting.subscription.plan}`) }} · {{ money(store.hosting.subscription.billing_amount) }}</p>
          <p v-if="!store.hosting.subscription.payments.length" class="text-sm text-text-muted">{{ t('platformBilling.noPayments') }}</p>
          <ul class="space-y-2">
            <li v-for="payment in store.hosting.subscription.payments" :key="payment.id" class="flex flex-wrap justify-between gap-3 rounded-xl border border-border-default p-3 text-sm"><span>{{ payment.billing_period_start }} — {{ payment.billing_period_end }}<span class="block text-text-muted">{{ t('platformBilling.due') }}: {{ payment.due_date }}</span></span><span>{{ money(payment.amount) }} · {{ t(`platformBilling.states.${payment.status}`) }}</span></li>
          </ul>
        </section>
        <section v-for="source in store.hosting.accounting_sources" :key="source.id" class="space-y-2 border-t border-border-default pt-3">
          <h3 class="font-medium">{{ source.domain_url || t('platformBilling.accountingOrigin') }} · #{{ source.id }}</h3>
          <p class="text-sm text-text-muted">{{ source.operational ? t('platformBilling.operationalOrigin') : source.associated ? t('platformBilling.historicalOrigin') : t('platformBilling.pendingAssociation') }}</p>
          <p class="text-sm">{{ source.valid_from || '—' }} — {{ source.valid_to || '—' }} · {{ t(`platformBilling.modalities.${source.payment_modality}`) }} · {{ money(source.payment_per_cycle) }} · {{ t(`platformBilling.states.${source.is_active ? 'active' : 'inactive'}`) }}</p>
          <p v-if="!source.cycles.length" class="text-sm text-text-muted">{{ t('platformBilling.noCycles') }}</p>
          <ul class="space-y-1 text-sm">
            <li v-for="cycle in source.cycles" :key="cycle.id" class="flex flex-wrap justify-between gap-2"><span>{{ cycle.period_from || cycle.paid_at }} — {{ cycle.period_to || '—' }} · #{{ cycle.id }}</span><span>{{ money(cycle.amount) }} · {{ t('platformBilling.states.paid') }}</span></li>
          </ul>
        </section>
        <section v-if="store.hosting.evidence_groups.length" class="space-y-2 border-t border-border-default pt-3">
          <h3 class="font-semibold">{{ t('platformBilling.reconciledEvidence') }}</h3>
          <div v-for="group in store.hosting.evidence_groups" :key="group.id" class="rounded-xl bg-surface-muted p-3 text-sm">
            <p class="font-medium">{{ group.label }}</p>
            <p v-if="group.amounts_differ || group.statuses_differ" class="text-warning-strong">{{ t('platformBilling.evidenceDifference') }}</p>
            <ul>
              <li v-for="reference in group.evidence" :key="`${reference.kind}-${reference.id}`">
                <NuxtLink v-if="reference.kind === 'account'" :to="localePath(`/platform/collection-accounts/${reference.id}`)" class="text-text-brand">{{ t('platformBilling.account') }} #{{ reference.id }}</NuxtLink>
                <span v-else>{{ t(`platformBilling.evidenceKinds.${reference.kind}`) }} #{{ reference.id }}</span>
                · {{ money(reference.amount) }} · {{ t(`platformBilling.states.${reference.status}`) }}
              </li>
            </ul>
          </div>
        </section>
      </template>
    </template>
  </section>
</template>
