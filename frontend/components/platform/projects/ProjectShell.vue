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
        <BaseButton unstyled
          v-if="isAdminUser && project"
          type="button"
          class="inline-flex items-center gap-1.5 text-sm text-text-brand hover:underline whitespace-nowrap"
          :title="t('projectAccess.commercialRecord.title')"
          data-testid="project-back-to-panel"
          @click="openPanelRecord"
        >
          <ArrowTopRightOnSquareIcon class="w-4 h-4" />
          {{ t('projectAccess.commercialRecord.label') }}
        </BaseButton>
      </div>
      <p v-if="project" class="mt-1 text-sm text-text-muted">
        <template v-if="project.client_name">Cliente: {{ project.client_name }}</template>
        <template v-if="project.start_date"> · Inició: {{ formatDate(project.start_date) }}</template>
        <template v-if="project.next_deliverable"> · Próx. entrega: {{ formatDate(project.next_deliverable.due_date) }}</template>
      </p>
    </header>
    <div v-if="project" class="flex flex-col gap-4 lg:flex-row">
      <ProjectSecondarySidebar :project-id="projectId" />
      <main class="min-w-0 flex-1 rounded-3xl border border-border-default bg-surface px-4 py-6 shadow-sm sm:px-6">
        <slot />
      </main>
    </div>
    <p v-else-if="store.isLoading" role="status" class="px-6 py-12 text-center text-text-muted">Cargando proyecto…</p>
    <section v-else-if="store.error" role="alert" class="space-y-4 rounded-3xl border border-border-default bg-surface p-6" data-testid="project-access-error">
      <h2 class="text-lg font-semibold text-text-default">{{ errorTitle }}</h2>
      <p class="text-sm text-text-muted">{{ errorMessage }}</p>
      <div class="flex flex-wrap gap-3">
        <BaseButton as="NuxtLink" :to="localePath('/platform/projects')" variant="secondary">Volver a proyectos</BaseButton>
        <BaseButton v-if="store.errorStatus !== 403 && store.errorStatus !== 404" variant="primary" @click="store.fetchProject(projectId)">Volver a intentar</BaseButton>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeMount, watch } from 'vue'
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
const localePath = useLocalePath()

const isAdminUser = computed(() => authStore.isAdmin)

function openPanelRecord() {
  window.open(localePath({ path: '/panel/projects', query: { highlight: projectId.value } }), '_blank')
}

const projectId = computed(() => Number(route.params.id))
const project = computed(() => Number(store.currentProject?.id) === projectId.value ? store.currentProject : null)
const errorTitle = computed(() => store.errorStatus === 403 ? 'No tienes acceso a este proyecto' : store.errorStatus === 404 ? 'Proyecto no disponible' : 'No pudimos abrir el proyecto')
const errorMessage = computed(() => store.errorStatus === 403
  ? 'Tu cuenta no tiene permiso para abrir este espacio. Consulta con el equipo que administra tu acceso.'
  : store.errorStatus === 404 ? 'El proyecto no está disponible. Vuelve al listado para consultar tus proyectos.'
    : 'No pudimos cargar este espacio. Comprueba tu sesión y vuelve a intentarlo.')

onBeforeMount(() => { if (projectId.value) store.fetchProject(projectId.value) })
watch(projectId, (id) => { if (id) store.fetchProject(id) }, { flush: 'sync' })

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
