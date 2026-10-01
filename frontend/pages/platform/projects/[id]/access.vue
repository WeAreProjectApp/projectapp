<script setup>
import { computed } from 'vue'
import ProjectAccessEditor from '~/components/projects/ProjectAccessEditor.vue'
import ProjectShell from '~/components/platform/projects/ProjectShell.vue'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { createProjectAccessApi } from '~/services/projectAccessApi'
import { createProjectClientAccessApi } from '~/services/projectClientAccessApi'
import { hasPersonalPlatformSession } from '~/services/projectCollaborationSession'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import ProjectClientAccessPolicyEditor from '~/components/projects/client-access/ProjectClientAccessPolicyEditor.vue'
import ProjectClientAccessView from '~/components/projects/client-access/ProjectClientAccessView.vue'

definePageMeta({
  middleware: ['platform-auth'],
  layout: 'platform',
})

const route = useRoute()
const projectId = computed(() => Number(route.params.id))
const platformApi = usePlatformApi()
const auth = usePlatformAuthStore()
const clientApi = computed(() => createProjectClientAccessApi(platformApi, projectId.value))
const canReveal = computed(() => hasPersonalPlatformSession(auth.accessToken))
const accessApi = computed(() => createProjectAccessApi({
  get: platformApi.get,
  post: platformApi.post,
  patch: platformApi.patch,
  remove: platformApi.delete,
}, `projects/${projectId.value}/access/`))
</script>

<template>
  <ProjectShell>
    <div v-if="projectId && auth.isAdmin" class="space-y-6">
      <ProjectAccessEditor :key="projectId" :api="accessApi" />
      <ProjectClientAccessPolicyEditor :key="projectId" :project-id="projectId" :api="clientApi" />
    </div>
    <ProjectClientAccessView v-else-if="projectId && auth.isAuthenticated" :key="`${projectId}-${auth.accessToken}`" :project-id="projectId" :api="clientApi" :can-reveal="canReveal" />
  </ProjectShell>
</template>
