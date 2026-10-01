<script setup>
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'
import BillingAccountList from '~/components/platform/billing/BillingAccountList.vue'
const route = useRoute()
definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
</script>
<template><ProjectShell><BillingAccountList :project-id="route.params.id" /></ProjectShell></template>
