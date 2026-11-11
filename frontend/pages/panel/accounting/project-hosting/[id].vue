<script setup>
import { computed } from 'vue'
import BasePageShell from '~/components/base/BasePageShell.vue'
import HostingReconciliation from '~/components/accounting/billing/HostingReconciliation.vue'
import { useProposalStore } from '~/stores/proposals'
import { readBillingReturnDraft } from '~/utils/billingReturnDraft'
const route = useRoute(), auth = useProposalStore()
const draft = computed(() => {
  const current = readBillingReturnDraft(route.query.returnDraft, auth.adminUser?.id)
  return current && Number(current.projectId) === Number(route.params.id) ? current : null
})
const returnTo = computed(() => draft.value ? { path: draft.value.origin.path,
  query: { ...draft.value.origin.query, returnDraft: route.query.returnDraft } } : null)
definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] })
</script>
<template><BasePageShell><HostingReconciliation :project-id="route.params.id" :return-to="returnTo" :return-missing="Boolean(route.query.returnDraft) && !draft" /></BasePageShell></template>
