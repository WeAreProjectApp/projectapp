<script setup>
import { computed } from 'vue'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'
import DeliveryWorkspace from '~/components/platform/delivery/DeliveryWorkspace.vue'

definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
const route = useRoute()
const { t } = useI18n()
const projectId = computed(() => Number(route.params.id))
useHead({ title: () => `${t('platformDelivery.title')} | Project App` })
</script>

<template>
  <ProjectShell><DeliveryWorkspace :project-id="projectId" /></ProjectShell>
</template>
