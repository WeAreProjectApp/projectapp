<script setup>
import { computed } from 'vue'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'
import ProjectIdeasWorkspace from '~/components/projects/ideas/ProjectIdeasWorkspace.vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { createProjectIdeasApi } from '~/services/projectIdeasApi'
import { hasPersonalPlatformSession } from '~/services/projectCollaborationSession'

definePageMeta({ middleware: ['platform-auth'], layout: 'platform' })
const route = useRoute()
const auth = usePlatformAuthStore()
const projectId = computed(() => Number(route.params.id))
const transport = usePlatformApi()
const api = computed(() => createProjectIdeasApi(transport, projectId.value))
const canWrite = computed(() => auth.isAuthenticated && hasPersonalPlatformSession(auth.accessToken))
</script>

<template>
  <ProjectShell>
    <ProjectIdeasWorkspace v-if="projectId && auth.isAuthenticated" :key="`${projectId}-${auth.user?.id}`" :project-id="projectId" :api="api" :is-admin="auth.isAdmin" :can-write="canWrite" />
  </ProjectShell>
</template>
