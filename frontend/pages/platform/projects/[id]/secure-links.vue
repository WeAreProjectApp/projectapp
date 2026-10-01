<script setup>
import { computed } from 'vue'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'
import PlatformSecureLinksWorkspace from '~/components/platform/secureLinks/PlatformSecureLinksWorkspace.vue'

definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
const route = useRoute()
const { t } = useI18n()
const projectId = computed(() => Number(route.params.id))
useHead({ title: () => `${t('platformSecureLinks.title')} | Project App` })
</script>

<template>
  <ProjectShell><PlatformSecureLinksWorkspace :key="projectId" :project-id="projectId" /></ProjectShell>
</template>
