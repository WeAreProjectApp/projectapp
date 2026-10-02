<script setup>
import { computed } from 'vue'
import ProjectIdeasWorkspace from '~/components/projects/ideas/ProjectIdeasWorkspace.vue'
import { createProjectIdeasApi } from '~/services/projectIdeasApi'
import { create_request, get_request, patch_request } from '~/stores/services/request_http'

definePageMeta({ middleware: ['admin-auth'], layout: 'admin' })
const route = useRoute()
const localePath = useLocalePath()
const projectId = computed(() => Number(route.params.id))
const api = computed(() => createProjectIdeasApi({ get: get_request, post: create_request, patch: patch_request }, projectId.value))
</script>

<template>
  <div class="mx-auto w-full max-w-5xl space-y-4">
    <NuxtLink :to="localePath('/panel/projects')" class="inline-flex min-h-11 items-center text-text-brand underline">{{ $t('projectIdeas.backToProjects') }}</NuxtLink>
    <ProjectIdeasWorkspace v-if="projectId" :key="projectId" :project-id="projectId" :api="api" is-admin />
  </div>
</template>
