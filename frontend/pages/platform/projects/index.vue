<template>
  <div id="platform-projects">
    <!-- Header -->
    <div class="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between" data-enter>
      <div>
        <h1 class="text-2xl font-bold text-text-default sm:text-3xl">
          {{ authStore.isAdmin ? 'Proyectos' : 'Mis proyectos' }}
        </h1>
        <p class="mt-1 text-sm text-text-muted">
          {{ authStore.isAdmin ? 'Todos los proyectos de tus clientes.' : 'El estado actual de tus proyectos.' }}
        </p>
      </div>
      <BaseButton variant="accent" size="md" v-if="authStore.isAdmin" @click="isCreateModalOpen = true">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        Nuevo proyecto
      </BaseButton>
    </div>

    <!-- Status filters (admin) -->
    <div v-if="authStore.isAdmin" class="mb-6 flex flex-wrap gap-2" data-enter>
      <button
        v-for="filter in statusFilters"
        :key="filter.value"
        type="button"
        class="rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-wider transition"
        :class="activeFilter === filter.value
          ? 'bg-primary text-on-primary dark:bg-accent dark:text-on-accent'
          : 'border border-border-default text-text-muted hover:text-text-default dark:hover:text-white'"
        @click="handleFilterChange(filter.value)"
      >
        {{ filter.label }}
      </button>
    </div>

    <!-- Loading state -->
    <div v-if="projectsStore.isLoading" class="py-20 text-center" data-enter>
      <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border-default border-t-esmerald dark:border-t-lemon" />
      <p class="mt-4 text-sm text-text-muted">Cargando proyectos...</p>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="filteredProjects.length === 0"
      class="rounded-3xl border border-dashed border-border-default py-20 text-center"
      data-enter
    >
      <svg class="mx-auto h-12 w-12 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
      </svg>
      <p class="mt-4 text-sm font-medium text-text-default">
        {{ authStore.isAdmin ? 'No hay proyectos creados.' : 'Todavía no tienes proyectos asignados.' }}
      </p>
      <p class="mt-1 text-xs text-text-muted">
        {{ authStore.isAdmin ? 'Crea el primer proyecto para un cliente.' : 'Tu administrador te asignará proyectos pronto.' }}
      </p>
    </div>

    <!-- Projects table -->
    <ProjectsTable
      v-else
      :projects="filteredProjects"
      :role="authStore.isAdmin ? 'admin' : 'client'"
      @navigate="goToProject"
    />

    <!-- Create project modal -->
    <Teleport to="body">
      <Transition name="modal-overlay">
        <div
          v-if="isCreateModalOpen"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm"
          @click.self="closeCreateModal"
        >
          <Transition name="modal-content" appear>
            <div
              v-if="isCreateModalOpen"
              class="w-full max-w-lg rounded-3xl border border-border-default bg-surface p-6 shadow-2xl sm:p-8"
            >
              <div class="mb-6 flex items-center justify-between">
                <h2 class="text-lg font-bold text-text-default">Nuevo proyecto</h2>
                <BaseButton
                  unstyled
                  icon-only
                  type="button"
                  aria-label="Cerrar creación de proyecto"
                  class="flex h-8 w-8 items-center justify-center rounded-full text-text-muted transition hover:bg-surface-muted hover:text-text-default dark:hover:bg-white/10 dark:hover:text-white"
                  @click="closeCreateModal"
                >
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </BaseButton>
              </div>

              <div
                v-if="createError"
                class="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-400"
              >
                {{ createError }}
              </div>

              <form class="space-y-4" @submit.prevent="handleCreateProject">
                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Nombre del proyecto <span class="text-red-400">*</span></label>
                  <input
                    v-model="createForm.name"
                    type="text"
                    required
                    placeholder="Ej: Plataforma E-commerce"
                    class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default dark:bg-surface-muted dark:text-white dark:placeholder:text-text-subtle dark:focus:border-lemon/40"
                  />
                </div>

                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Descripción</label>
                  <textarea
                    v-model="createForm.description"
                    rows="3"
                    placeholder="Breve descripción del proyecto..."
                    class="w-full resize-none rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default dark:bg-surface-muted dark:text-white dark:placeholder:text-text-subtle dark:focus:border-lemon/40"
                  />
                </div>

                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Cliente <span class="text-red-400">*</span></label>
                  <select
                    v-model="createForm.client_id"
                    required
                    class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
                  >
                    <option value="" disabled>Selecciona un cliente</option>
                    <option
                      v-for="client in clientsForSelect"
                      :key="client.user_id"
                      :value="client.user_id"
                    >
                      {{ client.first_name }} {{ client.last_name }} — {{ client.company_name || client.email }}
                    </option>
                  </select>
                </div>

                <div>
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Propuesta de negocio</label>
                  <div ref="proposalSelectRef" class="relative">
                    <button
                      type="button"
                      class="flex w-full items-center justify-between gap-2 rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-left text-sm outline-none transition focus:border-border-default dark:bg-surface-muted dark:focus:border-lemon/40"
                      @click="toggleProposalDropdown"
                    >
                      <span class="truncate" :class="createForm.proposal_id ? 'text-text-default' : 'text-text-muted'">
                        {{ selectedProposalLabel || 'Sin propuesta vinculada' }}
                      </span>
                      <svg class="h-4 w-4 shrink-0 text-text-muted transition-transform" :class="proposalDropdownOpen ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                    </button>
                    <div
                      v-if="proposalDropdownOpen"
                      class="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-border-default bg-surface shadow-lg"
                    >
                      <div class="border-b border-border-muted p-2">
                        <input
                          ref="proposalSearchInput"
                          v-model="proposalSearch"
                          type="text"
                          placeholder="Buscar propuesta por nombre..."
                          class="w-full rounded-lg border border-border-default bg-surface-muted/40 px-3 py-2 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default dark:bg-surface-muted dark:text-white dark:placeholder:text-text-subtle dark:focus:border-lemon/40"
                          @keydown.esc.stop.prevent="closeProposalDropdown"
                        />
                      </div>
                      <ul class="max-h-56 overflow-y-auto py-1">
                        <li>
                          <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm transition hover:bg-primary-soft dark:hover:bg-white/5"
                            :class="!createForm.proposal_id ? 'text-text-brand dark:text-text-brand' : 'text-text-muted'"
                            @click="selectProposal(null)"
                          >
                            Sin propuesta vinculada
                          </button>
                        </li>
                        <li v-for="p in filteredProposals" :key="p.id">
                          <button
                            type="button"
                            class="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm transition hover:bg-primary-soft dark:hover:bg-white/5"
                            :class="createForm.proposal_id === p.id ? 'bg-primary-soft dark:bg-white/5' : ''"
                            @click="selectProposal(p)"
                          >
                            <span class="truncate text-text-default">{{ p.title }}</span>
                            <span class="shrink-0 text-xs text-text-muted">{{ formatCurrency(p.total_investment, p.currency) }}</span>
                          </button>
                        </li>
                        <li v-if="!filteredProposals.length" class="px-3 py-4 text-center text-xs text-text-muted">
                          No hay propuestas que coincidan.
                        </li>
                      </ul>
                    </div>
                  </div>
                  <p class="mt-1 text-[11px] text-text-muted">
                    Al vincular una propuesta, se crean automáticamente los requerimientos del tablero Kanban.
                  </p>
                </div>

                <div v-if="createForm.proposal_id">
                  <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Inicio cobro hosting</label>
                  <input
                    v-model="createForm.hosting_start_date"
                    type="date"
                    class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
                  />
                  <p class="mt-1 text-[11px] text-text-muted">Fecha a partir de la cual el cliente puede activar su plan de hosting.</p>
                </div>

                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Fecha inicio</label>
                    <input
                      v-model="createForm.start_date"
                      type="date"
                      class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
                    />
                  </div>
                  <div>
                    <label class="mb-1.5 block text-xs font-medium text-esmerald/70 dark:text-white/70">Entrega estimada</label>
                    <input
                      v-model="createForm.estimated_end_date"
                      type="date"
                      class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition focus:border-border-default dark:bg-surface-muted dark:text-white dark:focus:border-lemon/40"
                    />
                  </div>
                </div>

                <div class="flex justify-end gap-3 pt-2">
                  <BaseButton variant="ghost" size="md" @click="closeCreateModal">
                    Cancelar
                  </BaseButton>
                  <BaseButton variant="accent" size="md" type="submit" :disabled="!canCreate || projectsStore.isUpdating">
                    {{ projectsStore.isUpdating ? 'Creando...' : 'Crear proyecto' }}
                  </BaseButton>
                </div>
              </form>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformProjectsStore } from '~/stores/platform-projects'
import { usePlatformClientsStore } from '~/stores/platform-clients'
import { usePlatformPaymentsStore } from '~/stores/platform-payments'
import { formatDate as formatDateUtil } from '~/utils/formatDate'
import ProjectsTable from '~/components/platform/projects/ProjectsTable.vue'

definePageMeta({
  layout: 'platform',
  middleware: ['platform-auth'],
})


usePageEntrance('#platform-projects')

const localePath = useLocalePath()
const authStore = usePlatformAuthStore()
const projectsStore = usePlatformProjectsStore()
const clientsStore = usePlatformClientsStore()
const paymentsStore = usePlatformPaymentsStore()

function goToProject(id) {
  navigateTo(localePath(`/platform/projects/${id}`))
}

const activeFilter = ref('')
const isCreateModalOpen = ref(false)
const createError = ref('')
const createForm = reactive({
  name: '',
  description: '',
  client_id: '',
  proposal_id: null,
  hosting_start_date: '',
  start_date: '',
  estimated_end_date: '',
})

const statusFilters = computed(() => [
  { label: 'Todos', value: '' },
  ...Array.from(new Map(projectsStore.projects
    .filter((project) => project.current_state)
    .map((project) => [project.current_state.id, {
      label: project.current_state.name,
      value: String(project.current_state.id),
    }])).values()),
])

const filteredProjects = computed(() => {
  if (!activeFilter.value) return projectsStore.projects
  return projectsStore.projects.filter(
    (project) => String(project.current_state?.id) === activeFilter.value,
  )
})

const clientsForSelect = computed(() =>
  clientsStore.clients.filter((c) => c.is_active && c.is_onboarded),
)

// --- Selector de propuesta con buscador ---
const proposalSearch = ref('')
const proposalDropdownOpen = ref(false)
const proposalSelectRef = ref(null)
const proposalSearchInput = ref(null)

const filteredProposals = computed(() => {
  const list = paymentsStore.proposals || []
  const q = proposalSearch.value.trim().toLowerCase()
  if (!q) return list
  return list.filter((p) => (p.title || '').toLowerCase().includes(q))
})

const selectedProposalLabel = computed(() => {
  if (!createForm.proposal_id) return ''
  const p = (paymentsStore.proposals || []).find((x) => x.id === createForm.proposal_id)
  return p ? `${p.title} — ${formatCurrency(p.total_investment, p.currency)}` : ''
})

function toggleProposalDropdown() {
  proposalDropdownOpen.value = !proposalDropdownOpen.value
  if (proposalDropdownOpen.value) {
    proposalSearch.value = ''
    nextTick(() => proposalSearchInput.value?.focus())
  }
}

function closeProposalDropdown() {
  proposalDropdownOpen.value = false
}

function selectProposal(proposal) {
  createForm.proposal_id = proposal ? proposal.id : null
  closeProposalDropdown()
}

function onClickOutsideProposal(event) {
  if (proposalSelectRef.value && !proposalSelectRef.value.contains(event.target)) {
    closeProposalDropdown()
  }
}

onMounted(() => document.addEventListener('mousedown', onClickOutsideProposal))
onBeforeUnmount(() => document.removeEventListener('mousedown', onClickOutsideProposal))

const canCreate = computed(() => Boolean(createForm.name.trim()) && Boolean(createForm.client_id))

function clientInitials(project) {
  const name = project.client_name || ''
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('')
}

function formatDate(value) {
  return formatDateUtil(value, { fallback: 'Sin fecha' })
}

function handleFilterChange(value) {
  activeFilter.value = value
}

function formatCurrency(amount, currency) {
  const num = Number(amount)
  if (currency === 'USD') return `$${num.toLocaleString('en-US')} USD`
  return `$${num.toLocaleString('es-CO')} ${currency || 'COP'}`
}

function closeCreateModal() {
  isCreateModalOpen.value = false
  createError.value = ''
  proposalDropdownOpen.value = false
  proposalSearch.value = ''
  createForm.name = ''
  createForm.description = ''
  createForm.client_id = ''
  createForm.proposal_id = null
  createForm.hosting_start_date = ''
  createForm.start_date = ''
  createForm.estimated_end_date = ''
}

async function handleCreateProject() {
  createError.value = ''

  const payload = {
    name: createForm.name.trim(),
    description: createForm.description.trim(),
    client_id: Number(createForm.client_id),
  }
  if (createForm.proposal_id) payload.proposal_id = createForm.proposal_id
  if (createForm.hosting_start_date) payload.hosting_start_date = createForm.hosting_start_date
  if (createForm.start_date) payload.start_date = createForm.start_date
  if (createForm.estimated_end_date) payload.estimated_end_date = createForm.estimated_end_date

  const result = await projectsStore.createProject(payload)
  if (!result.success) {
    createError.value = result.message
    return
  }

  closeCreateModal()
}

onMounted(async () => {
  await projectsStore.fetchProjects()
  if (authStore.isAdmin) {
    await Promise.all([
      clientsStore.fetchClients('all'),
      paymentsStore.fetchProposals(),
    ])
  }
})
</script>

<style scoped>
.modal-overlay-enter-active,
.modal-overlay-leave-active {
  transition: opacity 0.25s ease;
}
.modal-overlay-enter-from,
.modal-overlay-leave-to {
  opacity: 0;
}
.modal-content-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.modal-content-leave-active {
  transition: all 0.2s ease-in;
}
.modal-content-enter-from {
  opacity: 0;
  transform: scale(0.95) translateY(10px);
}
.modal-content-leave-to {
  opacity: 0;
  transform: scale(0.97);
}
</style>
