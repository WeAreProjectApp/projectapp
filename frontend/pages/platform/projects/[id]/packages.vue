<script setup>
import { computed } from "vue";
import ProjectShell from "~/components/platform/projects/ProjectShell.vue";
import Workspace from "~/components/RequirementPackages/Workspace.vue";
import { usePlatformAuthStore } from "~/stores/platform-auth";
import { usePlatformApi } from "~/composables/usePlatformApi";
import { hasPersonalPlatformSession } from "~/services/projectCollaborationSession";
import { createRequirementPackagesApi } from "~/services/requirementPackagesApi";

definePageMeta({ middleware: ["platform-auth"], layout: "platform" });
const route = useRoute();
const auth = usePlatformAuthStore();
const transport = usePlatformApi();
const projectId = computed(() => Number(route.params.id));
const api = computed(() =>
  createRequirementPackagesApi(
    {
      get: (path) => transport.get(`/api/${path}`),
      post: (path, data) => transport.post(`/api/${path}`, data),
    },
    projectId.value,
  ),
);
const canConsent = computed(
  () => !auth.isAdmin && hasPersonalPlatformSession(auth.accessToken),
);
</script>

<template>
  <ProjectShell
    ><Workspace
      v-if="auth.isAuthenticated"
      :key="`${projectId}-${auth.user?.id}`"
      :api="api"
      :can-consent="canConsent"
  /></ProjectShell>
</template>
