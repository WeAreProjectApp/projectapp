<script setup>
import BillingAccountList from '~/components/platform/billing/BillingAccountList.vue'
definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
</script>
<template><div class="mx-auto max-w-6xl p-4 sm:p-6"><BillingAccountList /></div></template>
