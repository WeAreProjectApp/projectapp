<script setup>
import { computed, ref, watch } from 'vue'
import BaseButton from '~/components/base/BaseButton.vue'
import { usePlatformBillingStore } from '~/stores/platform-billing'
import { usePlatformCollectionAccountsStore } from '~/stores/platform-collection-accounts'
const props = defineProps({ accountId: { type: [String, Number], required: true } })
const store = usePlatformBillingStore()
const pdfStore = usePlatformCollectionAccountsStore()
const { t, locale } = useI18n()
const localePath = useLocalePath()
const pdfError = ref('')
const downloading = ref(false)
const account = computed(() => store.account)
const money = value => new Intl.NumberFormat(locale.value, { style: 'currency', currency: account.value?.currency || 'COP' }).format(Number(value))
const contextHref = computed(() => {
  const row = account.value
  if (!row?.project_id) return null
  return localePath(row.context?.nature === 'hosting'
    ? `/platform/projects/${row.project_id}/payments`
    : { path: `/platform/projects/${row.project_id}/collection-accounts`, query: { contract_id: row.context?.contract?.id, amendment_id: row.context?.amendment?.id } })
})
async function download() {
  const id = props.accountId
  pdfError.value = ''; downloading.value = true
  const result = await pdfStore.downloadPdf(id)
  if (String(props.accountId) === String(id)) {
    if (!result.success) pdfError.value = result.message || t('platformBilling.pdfError')
    downloading.value = false
  }
}
watch(() => props.accountId, () => { pdfError.value = ''; downloading.value = false; store.fetchAccount(props.accountId) }, { immediate: true })
</script>

<template>
  <section class="space-y-5" data-testid="billing-account-detail">
    <NuxtLink :to="localePath('/platform/collection-accounts')" class="text-text-brand">{{ t('platformBilling.backAccounts') }}</NuxtLink>
    <p v-if="store.loading.account" role="status">{{ t('platformBilling.loading') }}</p>
    <div v-else-if="store.errors.account" role="alert">
      <p>{{ store.errors.account }}</p><button class="text-text-brand" @click="store.fetchAccount(accountId)">{{ t('platformBilling.retry') }}</button>
    </div>
    <template v-else-if="account">
      <h1 class="text-2xl font-semibold text-text-default">{{ account.public_number || account.title }}</h1>
      <p class="text-text-muted">{{ account.title }}</p>
      <dl class="grid gap-4 rounded-xl border border-border-default bg-surface p-5 sm:grid-cols-2">
        <div><dt class="text-sm text-text-muted">{{ t('platformBilling.project') }}</dt><dd class="text-text-default">{{ account.project_name || t('platformBilling.noProject') }}</dd></div>
        <div><dt class="text-sm text-text-muted">{{ t('platformBilling.context') }}</dt><dd class="text-text-default">
          <NuxtLink v-if="contextHref && account.context?.nature" :to="contextHref" class="text-text-brand">{{ account.context.nature === 'hosting' ? t('platformBilling.hosting') : account.context.contract.title }}<span v-if="account.context.amendment"> · {{ account.context.amendment.title }}</span></NuxtLink>
          <span v-else>{{ t(account.project_id ? 'platformBilling.pendingAssociation' : 'platformBilling.nonProjectAccount') }}</span>
        </dd></div>
        <div><dt class="text-sm text-text-muted">{{ t('platformBilling.state') }}</dt><dd>{{ t(`platformBilling.states.${account.commercial_status}`) }}<span v-if="account.is_overdue"> · {{ t('platformBilling.states.overdue') }}</span></dd></div>
        <div><dt class="text-sm text-text-muted">{{ t('platformBilling.total') }}</dt><dd class="font-semibold">{{ money(account.total) }}</dd></div>
        <div><dt class="text-sm text-text-muted">{{ t('platformBilling.issued') }}</dt><dd>{{ account.issue_date || '—' }}</dd></div>
        <div><dt class="text-sm text-text-muted">{{ t('platformBilling.due') }}</dt><dd>{{ account.due_date || '—' }}</dd></div>
      </dl>
      <p v-if="account.collection_account?.billing_concept" class="text-text-default">{{ account.collection_account.billing_concept }}</p>
      <ul class="space-y-2">
        <li v-for="item in account.items" :key="item.id" class="flex flex-wrap justify-between gap-3 rounded-xl border border-border-default p-4"><span>{{ item.description }}<span v-if="item.period_start" class="block text-sm text-text-muted">{{ item.period_start }} — {{ item.period_end }}</span></span><span>{{ money(item.line_total) }}</span></li>
      </ul>
      <div v-if="account.payment_methods?.length" class="space-y-2 rounded-xl border border-border-default p-4">
        <h2 class="font-semibold">{{ t('platformBilling.paymentInstructions') }}</h2>
        <p v-for="method in account.payment_methods" :key="method.id" class="text-sm">{{ method.bank_name }} · {{ method.account_type }} · {{ method.account_number }} · {{ method.account_holder_name }}<span class="block">{{ method.payment_instructions }}</span></p>
      </div>
      <p v-if="account.collection_account?.observations" class="whitespace-pre-wrap text-text-default">{{ account.collection_account.observations }}</p>
      <p v-if="account.terms_and_conditions" class="whitespace-pre-wrap text-sm text-text-muted">{{ account.terms_and_conditions }}</p>
      <BaseButton :loading="downloading" @click="download">{{ t('platformBilling.downloadPdf') }}</BaseButton>
      <p v-if="pdfError" role="alert" class="text-text-default">{{ pdfError }}</p>
    </template>
  </section>
</template>
