<template>
  <div class="space-y-4">
    <header class="rounded-3xl border border-border-default bg-surface px-6 py-4 shadow-sm">
      <ProjectBreadcrumb :project-name="project?.name" />
      <div class="mt-2 flex items-center justify-between gap-3">
        <div class="flex items-center gap-3 min-w-0">
          <h1 class="text-xl font-semibold text-text-default truncate">{{ project?.name || 'Proyecto' }}</h1>
          <span v-if="project" :class="statusChipClass(project.current_state)">{{ project.status_label }}</span>
        </div>
        <!-- PA-50 return path: the same record's commercial face. Admin-only —
             a client never sees the panel. Plain link on the Django session
             (PhaseList precedent), NOT the JWT bridge: wrong direction. -->
        <button
          v-if="isAdminUser"
          type="button"
          class="inline-flex items-center gap-1.5 text-sm text-text-brand hover:underline whitespace-nowrap"
          :title="t('projectAccess.commercialRecord.title')"
          data-testid="project-back-to-panel"
          @click="openPanelRecord"
        >
          <ArrowTopRightOnSquareIcon class="w-4 h-4" />
          {{ t('projectAccess.commercialRecord.label') }}
        </button>
      </div>
      <p v-if="project" class="mt-1 text-sm text-green-light">
        <template v-if="project.client_name">Cliente: {{ project.client_name }}</template>
        <template v-if="project.start_date"> · Inició: {{ formatDate(project.start_date) }}</template>
        <template v-if="project.next_deliverable"> · Próx. entrega: {{ formatDate(project.next_deliverable.due_date) }}</template>
      </p>
    </header>
    <div class="flex flex-col gap-4 lg:flex-row">
      <ProjectSecondarySidebar :project-id="projectId" />
      <main class="min-w-0 flex-1 rounded-3xl border border-border-default bg-surface px-4 py-6 shadow-sm sm:px-6">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { ArrowTopRightOnSquareIcon } from '@heroicons/vue/24/outline'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformProjectsStore } from '~/stores/platform-projects'
import { formatDate as formatDateUtil } from '~/utils/formatDate'
import ProjectBreadcrumb from '~/components/platform/projects/ProjectBreadcrumb.vue'
import ProjectSecondarySidebar from '~/components/platform/projects/ProjectSecondarySidebar.vue'

const route = useRoute()
const localePath = useLocalePath()
const { t } = useI18n()
const store = usePlatformProjectsStore()
const authStore = usePlatformAuthStore()

const isAdminUser = computed(() => authStore.isAdmin)

function openPanelRecord() {
  window.open(localePath({ path: '/panel/projects', query: { highlight: projectId.value } }), '_blank')
}

const projectId = computed(() => Number(route.params.id))
const project = computed(() => store.currentProject)

onMounted(() => { if (projectId.value) store.fetchProject(projectId.value) })
watch(projectId, (id) => { if (id) store.fetchProject(id) })

function statusChipClass(state) {
  const base = 'rounded-full px-2 py-0.5 text-xs font-medium'
  const map = {
    emerald: 'bg-green-100 text-green-700',
    yellow: 'bg-amber-100 text-amber-700',
    orange: 'bg-orange-100 text-orange-700',
    blue: 'bg-sky-100 text-sky-700',
    red: 'bg-red-100 text-red-700',
    purple: 'bg-purple-100 text-purple-700',
    gray: 'bg-slate-100 text-slate-600',
  }
  return `${base} ${map[state?.color] || map.gray}`
}
function formatDate(iso) {
  return formatDateUtil(iso, { fallback: '' })
}
</script>
