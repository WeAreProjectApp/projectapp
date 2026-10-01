<script setup>
import BillingAccountDetail from '~/components/platform/billing/BillingAccountDetail.vue'
const route = useRoute()
definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
</script>
<template><div class="mx-auto max-w-4xl p-4 sm:p-6"><BillingAccountDetail :account-id="route.params.id" /></div></template>
