<script setup>
import BasePageShell from '~/components/base/BasePageShell.vue'
import HostingReconciliation from '~/components/accounting/billing/HostingReconciliation.vue'
const route = useRoute()
definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] })
</script>
<template><BasePageShell><HostingReconciliation :project-id="route.params.id" /></BasePageShell></template>
