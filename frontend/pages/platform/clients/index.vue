<template>
  <div id="platform-clients" class="space-y-6">
    <section class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between" data-enter>
      <div>
        <h1 class="font-light text-3xl text-text-default">Clientes</h1>
        <p class="mt-2 max-w-2xl text-sm leading-7 text-text-muted">
          Invita clientes, revisa su estado de onboarding y administra sus accesos.
        </p>
      </div>

      <BaseButton variant="accent" size="md" @click="openInviteModal">
        Invitar cliente
      </BaseButton>
    </section>

    <section class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between" data-enter>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="filter in filters"
          :key="filter.value"
          type="button"
          class="rounded-full px-4 py-2 text-sm font-medium transition"
          :class="activeFilter === filter.value ? 'bg-primary text-white dark:bg-accent dark:text-on-accent' : 'text-text-muted hover:text-text-default dark:hover:text-white'"
          @click="activeFilter = filter.value"
        >
          {{ filter.label }}
        </button>
      </div>

      <div class="w-full lg:max-w-sm">
        <input
          v-model="search"
          type="text"
          placeholder="Buscar por nombre, email o empresa"
          class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20"
        >
      </div>
    </section>

    <div v-if="pageMessage" class="rounded-2xl border px-4 py-3 text-sm" :class="pageMessageVariant === 'success' ? 'border-emerald-500/20 bg-primary-soft text-text-brand dark:bg-emerald-500/10' : 'border-red-500/20 bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-200'">
      {{ pageMessage }}
    </div>

    <section class="rounded-3xl border border-border-default bg-surface shadow-sm" data-enter>
      <div v-if="platformClientsStore.isLoading" class="px-6 py-14 text-center text-sm text-text-muted">
        Cargando clientes...
      </div>

      <div v-else-if="filteredClients.length === 0" class="px-6 py-14 text-center text-sm text-text-muted">
        {{ search.trim() ? 'No encontramos clientes con ese criterio.' : 'Todavía no hay clientes en esta vista.' }}
      </div>

      <!-- Móvil: lista de filas-tarjeta -->
      <div v-else-if="isMobile" class="divide-y divide-border-muted">
        <button
          v-for="client in filteredClients"
          :key="client.user_id"
          type="button"
          class="flex w-full items-start gap-3 p-4 text-left transition hover:bg-primary-soft"
          @click="goToClient(client.user_id)"
        >
          <div class="h-9 w-9 shrink-0 overflow-hidden rounded-full">
            <img v-if="client.avatar_display_url" :src="client.avatar_display_url" alt="Avatar" class="h-full w-full object-cover" />
            <div v-else class="flex h-full w-full items-center justify-center bg-surface-muted text-xs font-semibold text-text-default dark:bg-white/10 dark:text-white">
              {{ initials(client) }}
            </div>
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <p class="truncate font-medium text-text-default">{{ client.first_name }} {{ client.last_name }}</p>
              <span v-if="!client.is_active" class="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-white/10 dark:text-text-muted">Inactivo</span>
            </div>
            <p class="truncate text-xs text-text-muted">{{ client.email }}</p>
            <dl class="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <div>
                <dt class="text-text-muted">Empresa</dt>
                <dd class="truncate text-text-muted">{{ client.company_name || '—' }}</dd>
              </div>
              <div>
                <dt class="text-text-muted">Proyectos</dt>
                <dd class="text-text-muted">{{ client.active_projects_count ?? 0 }} / {{ client.total_projects_count ?? 0 }}</dd>
              </div>
              <div>
                <dt class="text-text-muted">Plan hosting</dt>
                <dd>
                  <span v-if="client.hosting_plan" class="rounded-full bg-primary-soft px-2 py-0.5 text-[10px] font-medium text-text-brand dark:bg-primary-soft dark:text-text-brand">{{ planLabel(client.hosting_plan) }}</span>
                  <span v-else class="text-text-muted">—</span>
                </dd>
              </div>
              <div>
                <dt class="text-text-muted">Próx. renovación</dt>
                <dd :class="renewalClass(client.hosting_renewal_at)">{{ formatDate(client.hosting_renewal_at) }}</dd>
              </div>
              <div>
                <dt class="text-text-muted">Valor renovación</dt>
                <dd class="text-text-muted">{{ formatMoney(client.hosting_renewal_value) }}</dd>
              </div>
              <div>
                <dt class="text-text-muted">Última actividad</dt>
                <dd class="text-text-muted">{{ relativeTime(client.last_activity_at) }}</dd>
              </div>
            </dl>
          </div>
          <span class="shrink-0 self-center text-text-muted">›</span>
        </button>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full text-left text-sm">
          <thead>
            <tr class="border-b border-border-default text-xs uppercase tracking-[0.16em] text-text-muted">
              <th class="px-6 py-4 font-medium">Cliente</th>
              <th class="px-6 py-4 font-medium">Empresa</th>
              <th class="px-6 py-4 font-medium">Proyectos</th>
              <th class="px-6 py-4 font-medium">Plan hosting</th>
              <th class="px-6 py-4 font-medium">Próx. renovación</th>
              <th class="px-6 py-4 font-medium">Valor renovación</th>
              <th class="px-6 py-4 font-medium">Última actividad</th>
              <th class="w-10 px-2"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="client in filteredClients"
              :key="client.user_id"
              class="cursor-pointer border-b border-border-muted transition hover:bg-primary-soft last:border-b-0"
              @click="goToClient(client.user_id)"
            >
              <td class="px-6 py-4">
                <div class="flex items-center gap-3">
                  <div class="h-9 w-9 shrink-0 overflow-hidden rounded-full">
                    <img v-if="client.avatar_display_url" :src="client.avatar_display_url" alt="Avatar" class="h-full w-full object-cover" />
                    <div v-else class="flex h-full w-full items-center justify-center bg-surface-muted text-xs font-semibold text-text-default dark:bg-white/10 dark:text-white">
                      {{ initials(client) }}
                    </div>
                  </div>
                  <div>
                    <div class="flex items-center gap-2">
                      <p class="font-medium text-text-default">{{ client.first_name }} {{ client.last_name }}</p>
                      <span v-if="!client.is_active" class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-white/10 dark:text-text-muted">Inactivo</span>
                    </div>
                    <div class="mt-0.5 flex items-center gap-1 text-xs text-text-muted">
                      <span>{{ client.email }}</span>
                      <svg v-if="!client.has_logged_in_once" class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" aria-label="Sin acceso aún">
                        <title>Sin acceso aún</title>
                        <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
                      </svg>
                    </div>
                  </div>
                </div>
              </td>
              <td class="px-6 py-4 text-text-muted">{{ client.company_name || '—' }}</td>
              <td class="px-6 py-4 text-text-muted">{{ client.active_projects_count ?? 0 }} / {{ client.total_projects_count ?? 0 }}</td>
              <td class="px-6 py-4">
                <span v-if="client.hosting_plan" class="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-medium text-text-brand dark:bg-primary-soft dark:text-text-brand">
                  {{ planLabel(client.hosting_plan) }}
                </span>
                <span v-else class="text-text-muted">—</span>
              </td>
              <td class="px-6 py-4" :class="renewalClass(client.hosting_renewal_at)">
                {{ formatDate(client.hosting_renewal_at) }}
              </td>
              <td class="px-6 py-4 text-text-muted">{{ formatMoney(client.hosting_renewal_value) }}</td>
              <td class="px-6 py-4 text-sm text-text-muted">{{ relativeTime(client.last_activity_at) }}</td>
              <td class="px-2 py-4 text-right text-text-muted">›</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <Teleport to="body">
      <Transition name="platform-modal">
        <div v-if="isInviteModalOpen" class="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" @click.self="closeInviteModal">
          <div class="w-full max-w-lg rounded-3xl border border-border-default bg-surface p-6 shadow-2xl dark:shadow-black/40 sm:p-8">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h2 class="text-xl font-medium text-text-default">Invitar cliente</h2>
                <p class="mt-2 text-sm text-text-muted">
                  Crea el acceso inicial y envía credenciales temporales por email.
                </p>
              </div>

              <BaseButton
                unstyled
                icon-only
                type="button"
                aria-label="Cerrar invitación"
                class="flex h-9 w-9 items-center justify-center rounded-full text-text-muted transition hover:text-text-default dark:hover:text-white"
                @click="closeInviteModal"
              >
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </BaseButton>
            </div>

            <div v-if="inviteError" class="mt-6 rounded-2xl border border-red-500/20 bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-200">
              {{ inviteError }}
            </div>

            <form class="mt-6 grid gap-5 sm:grid-cols-2" @submit.prevent="handleCreateClient">
              <div class="sm:col-span-2">
                <label for="invite-email" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Email</label>
                <input id="invite-email" v-model="inviteForm.email" type="email" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:bg-surface-muted dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20" placeholder="cliente@empresa.com">
              </div>

              <div>
                <label for="invite-first-name" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Nombre</label>
                <input id="invite-first-name" v-model="inviteForm.first_name" type="text" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:bg-surface-muted dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20" placeholder="Nombre">
              </div>

              <div>
                <label for="invite-last-name" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Apellido</label>
                <input id="invite-last-name" v-model="inviteForm.last_name" type="text" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:bg-surface-muted dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20" placeholder="Apellido">
              </div>

              <div>
                <label for="invite-company" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Empresa</label>
                <input id="invite-company" v-model="inviteForm.company_name" type="text" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:bg-surface-muted dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20" placeholder="Empresa">
              </div>

              <div>
                <label for="invite-phone" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Teléfono</label>
                <input id="invite-phone" v-model="inviteForm.phone" type="text" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:bg-surface-muted dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20" placeholder="+57 300 000 0000">
              </div>

              <div class="flex flex-col gap-3 sm:col-span-2 sm:flex-row sm:justify-end">
                <BaseButton variant="ghost" size="md" @click="closeInviteModal">
                  Cancelar
                </BaseButton>
                <BaseButton variant="accent" size="md" type="submit" :disabled="platformClientsStore.isUpdating">
                  {{ platformClientsStore.isUpdating ? 'Enviando...' : 'Crear e invitar' }}
                </BaseButton>
              </div>
            </form>
          </div>
        </div>
      </Transition>
    </Teleport>

    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import ConfirmModal from '~/components/ConfirmModal.vue'
import { useConfirmModal } from '~/composables/useConfirmModal'
import { useIsMobile } from '~/composables/useIsMobile'

const localePath = useLocalePath()
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformClientsStore } from '~/stores/platform-clients'
import { formatDate } from '~/utils/formatDate'

definePageMeta({
  layout: 'platform',
  middleware: ['platform-auth'],
  platformRole: 'admin',
})

usePageEntrance('#platform-clients')

const platformClientsStore = usePlatformClientsStore()
const { isMobile } = useIsMobile()
const activeFilter = ref('active')
const search = ref('')
const isInviteModalOpen = ref(false)
const inviteError = ref('')
const pageMessage = ref('')
const pageMessageVariant = ref('success')
const inviteForm = reactive({
  email: '',
  first_name: '',
  last_name: '',
  company_name: '',
  phone: '',
})

const filters = [
  { label: 'Activos', value: 'active' },
  { label: 'Inactivos', value: 'inactive' },
  { label: 'Todos', value: 'all' },
]

const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal()

const filteredClients = computed(() => {
  const all = platformClientsStore.clients
  // Status filter: Activos (default) / Inactivos / Todos
  const byStatus = all.filter((client) => {
    if (activeFilter.value === 'all') return true
    if (activeFilter.value === 'inactive') return !client.is_active
    return client.is_active  // 'active' (default)
  })
  if (!search.value.trim()) return byStatus
  const query = search.value.trim().toLowerCase()
  return byStatus.filter((client) => {
    const fullName = `${client.first_name} ${client.last_name}`.toLowerCase()
    const company = `${client.company_name || ''}`.toLowerCase()
    return fullName.includes(query) || client.email.toLowerCase().includes(query) || company.includes(query)
  })
})

function resetInviteForm() {
  inviteForm.email = ''
  inviteForm.first_name = ''
  inviteForm.last_name = ''
  inviteForm.company_name = ''
  inviteForm.phone = ''
}

function openInviteModal() {
  inviteError.value = ''
  isInviteModalOpen.value = true
}

function closeInviteModal() {
  inviteError.value = ''
  isInviteModalOpen.value = false
  resetInviteForm()
}

function initials(client) {
  return `${client.first_name || ''} ${client.last_name || ''}`
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('') || 'PA'
}

function statusLabel(client) {
  if (!client.is_active) return 'Inactivo'
  if (!client.is_onboarded) return 'Pendiente'
  return 'Activo'
}

function statusClass(client) {
  if (!client.is_active) return 'bg-white/10 text-text-muted'
  if (!client.is_onboarded) return 'bg-amber-100 text-amber-700 dark:bg-primary-soft dark:text-text-brand'
  return 'bg-emerald-500/15 text-emerald-400'
}

const PLAN_LABELS = {
  monthly: 'Mensual (histórico)',
  quarterly: 'Trimestral',
  semiannual: 'Semestral',
  nine_month: 'Cada 9 meses',
  annual: 'Anual (histórico)',
}
function planLabel(p) { return PLAN_LABELS[p] || p }

function formatMoney(v) {
  if (v === null || v === undefined) return '—'
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(v)
}

function relativeTime(iso) {
  if (!iso) return '—'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24))
  if (days < 1) return 'Hoy'
  if (days === 1) return 'Ayer'
  if (days < 30) return `Hace ${days} días`
  if (days < 365) return `Hace ${Math.floor(days / 30)} meses`
  return `Hace ${Math.floor(days / 365)} años`
}

function renewalClass(iso) {
  if (!iso) return 'text-text-muted'
  const days = Math.floor((new Date(iso).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  return days <= 30 ? 'text-amber-700 dark:text-amber-300 font-medium' : 'text-text-muted'
}

function goToClient(id) {
  navigateTo(localePath(`/platform/clients/${id}`))
}

async function loadClients() {
  pageMessage.value = ''
  await platformClientsStore.fetchClients(activeFilter.value)
}

async function handleCreateClient() {
  inviteError.value = ''

  const normalizedEmail = inviteForm.email.trim().toLowerCase()
  if (!normalizedEmail.includes('@')) {
    inviteError.value = 'Ingresa un email válido.'
    return
  }

  if (!inviteForm.first_name.trim() || !inviteForm.last_name.trim()) {
    inviteError.value = 'Completa nombre y apellido del cliente.'
    return
  }

  const result = await platformClientsStore.createClient(inviteForm)
  if (!result.success) {
    inviteError.value = result.message
    return
  }

  pageMessageVariant.value = 'success'
  pageMessage.value = 'Cliente creado e invitación enviada correctamente.'
  closeInviteModal()

  if (activeFilter.value === 'inactive') {
    await loadClients()
  }
}

async function handleResendInvite(client) {
  pageMessage.value = ''
  const result = await platformClientsStore.resendInvite(client.user_id)
  if (!result.success) {
    pageMessageVariant.value = 'error'
    pageMessage.value = result.message
    return
  }

  pageMessageVariant.value = 'success'
  pageMessage.value = result.message

  if (activeFilter.value === 'inactive') {
    await loadClients()
  }
}

function requestDeactivate(client) {
  requestConfirm({
    title: 'Desactivar cliente',
    message: `Se desactivará el acceso de ${client.first_name} ${client.last_name}.`,
    confirmText: 'Desactivar',
    variant: 'danger',
    onConfirm: async () => {
      const result = await platformClientsStore.deactivateClient(client.user_id)
      pageMessageVariant.value = result.success ? 'success' : 'error'
      pageMessage.value = result.success
        ? 'Cliente desactivado correctamente.'
        : result.message

      await loadClients()
    },
  })
}

watch(activeFilter, async () => {
  await loadClients()
})

onMounted(async () => {
  await loadClients()
})
</script>

<style scoped>
.platform-modal-enter-active,
.platform-modal-leave-active {
  transition: opacity 0.2s ease;
}

.platform-modal-enter-active > div,
.platform-modal-leave-active > div {
  transition: transform 0.2s ease;
}

.platform-modal-enter-from,
.platform-modal-leave-to {
  opacity: 0;
}

.platform-modal-enter-from > div,
.platform-modal-leave-to > div {
  transform: scale(0.98) translateY(10px);
}
</style>
