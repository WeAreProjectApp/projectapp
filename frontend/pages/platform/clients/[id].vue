<template>
  <div id="platform-client-detail" class="space-y-6">
    <div data-enter>
      <NuxtLink :to="localePath('/platform/clients')" class="inline-flex items-center text-sm font-medium text-text-muted transition hover:text-text-default dark:hover:text-white">
        ← Volver a clientes
      </NuxtLink>
      <h1 class="mt-3 font-light text-3xl text-text-default">Detalle del cliente</h1>
    </div>

    <div v-if="pageMessage" class="rounded-2xl border px-4 py-3 text-sm" :class="pageMessageVariant === 'success' ? 'border-emerald-500/20 bg-primary-soft text-text-brand dark:bg-emerald-500/10' : 'border-red-500/20 bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-200'">
      {{ pageMessage }}
    </div>

    <div v-if="platformClientsStore.isLoading" class="rounded-3xl border border-border-default bg-surface px-6 py-14 text-center text-sm text-text-muted shadow-sm" data-enter>
      Cargando cliente...
    </div>

    <div v-else-if="!platformClientsStore.currentClient" class="rounded-3xl border border-border-default bg-surface px-6 py-14 text-center text-sm text-text-muted shadow-sm" data-enter>
      No encontramos el cliente solicitado.
    </div>

    <div v-else class="grid grid-cols-1 gap-6 xl:grid-cols-[0.85fr_1.15fr]">
      <section class="space-y-6" data-enter>
        <article class="rounded-3xl border border-border-default bg-surface p-6 shadow-sm">
          <div class="flex items-center gap-4">
            <div class="h-14 w-14 shrink-0 overflow-hidden rounded-full">
              <img
                v-if="platformClientsStore.currentClient?.avatar_display_url"
                :src="platformClientsStore.currentClient.avatar_display_url"
                alt="Avatar"
                class="h-full w-full object-cover"
              />
              <div v-else class="flex h-full w-full items-center justify-center bg-primary text-base font-bold text-on-primary dark:bg-accent dark:text-on-accent">
                {{ clientInitials }}
              </div>
            </div>
            <div class="min-w-0">
              <h2 class="truncate text-lg font-medium text-text-default">{{ form.first_name }} {{ form.last_name }}</h2>
              <p class="mt-0.5 truncate text-sm text-text-muted">{{ platformClientsStore.currentClient.email }}</p>
            </div>
          </div>

          <dl class="mt-6 grid gap-3">
            <div class="rounded-xl border border-border-default p-4">
              <dt class="text-xs uppercase tracking-[0.16em] text-text-muted">Empresa</dt>
              <dd class="mt-2 text-sm font-medium text-text-default">{{ form.company_name || '—' }}</dd>
            </div>
            <div class="rounded-xl border border-border-default p-4">
              <dt class="text-xs uppercase tracking-[0.16em] text-text-muted">Teléfono</dt>
              <dd class="mt-2 text-sm font-medium text-text-default">{{ form.phone || '—' }}</dd>
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="rounded-xl border border-border-default p-4">
                <dt class="text-xs uppercase tracking-[0.16em] text-text-muted">Estado</dt>
                <dd class="mt-2">
                  <span class="inline-flex rounded-full px-3 py-1 text-xs font-medium" :class="statusClass(platformClientsStore.currentClient)">
                    {{ statusLabel(platformClientsStore.currentClient) }}
                  </span>
                </dd>
              </div>
              <div class="rounded-xl border border-border-default p-4">
                <dt class="text-xs uppercase tracking-[0.16em] text-text-muted">Creado</dt>
                <dd class="mt-2 text-sm font-medium text-text-default">{{ formatDate(platformClientsStore.currentClient.created_at) }}</dd>
              </div>
            </div>
          </dl>
        </article>

        <article class="rounded-3xl border border-border-default bg-surface p-6 shadow-sm">
          <h2 class="text-base font-medium text-text-default">Acciones rápidas</h2>
          <div class="mt-5 flex flex-col gap-3">
            <BaseButton variant="secondary" size="md" :disabled="platformClientsStore.isUpdating" @click="handleResendInvite">
              Reenviar invitación
            </BaseButton>

            <BaseButton variant="danger-ghost" size="sm" v-if="platformClientsStore.currentClient.is_active" :disabled="platformClientsStore.isUpdating" @click="requestDeactivate">
              Desactivar acceso
            </BaseButton>

            <BaseButton variant="primary" size="md" v-else :disabled="platformClientsStore.isUpdating" @click="handleReactivate">
              Reactivar acceso
            </BaseButton>
          </div>
        </article>
      </section>

      <section data-enter>
        <article class="rounded-3xl border border-border-default bg-surface p-6 shadow-sm">
          <h2 class="text-base font-medium text-text-default">Editar cliente</h2>
          <p class="mt-2 text-sm leading-6 text-text-muted">
            Ajusta la información visible para el equipo y el cliente dentro del portal.
          </p>

          <form class="mt-6 grid gap-5 sm:grid-cols-2" @submit.prevent="handleSave">
            <div>
              <label for="client-first-name" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Nombre</label>
              <input id="client-first-name" v-model="form.first_name" type="text" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:bg-surface-muted dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20">
            </div>

            <div>
              <label for="client-last-name" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Apellido</label>
              <input id="client-last-name" v-model="form.last_name" type="text" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:bg-surface-muted dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20">
            </div>

            <div class="sm:col-span-2">
              <label for="client-email" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Email</label>
              <input id="client-email" :value="platformClientsStore.currentClient.email" type="email" disabled class="w-full rounded-xl border border-border-default bg-surface-muted/20 px-4 py-3 text-sm text-text-muted outline-none dark:bg-white/5">
            </div>

            <div>
              <label for="client-company" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Empresa</label>
              <input id="client-company" v-model="form.company_name" type="text" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:bg-surface-muted dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20">
            </div>

            <div>
              <label for="client-phone" class="mb-2 block text-sm font-medium text-esmerald/70 dark:text-white/70">Teléfono</label>
              <input id="client-phone" v-model="form.phone" type="text" class="w-full rounded-xl border border-border-default bg-surface-muted/40 px-4 py-3 text-sm text-text-default outline-none transition placeholder:text-text-muted focus:border-border-default focus:ring-1 focus:ring-esmerald/10 dark:bg-surface-muted dark:text-white dark:placeholder:text-text-muted dark:focus:border-lemon/40 dark:focus:ring-lemon/20">
            </div>

            <label class="sm:col-span-2 flex items-center justify-between rounded-xl border border-border-default px-4 py-4">
              <div>
                <p class="text-sm font-medium text-text-default">Cuenta activa</p>
                <p class="mt-1 text-xs text-text-muted">Desactiva esta opción si necesitas pausar el acceso del cliente.</p>
              </div>
              <input v-model="form.is_active" type="checkbox" class="h-5 w-5 rounded border-border-default bg-surface-muted/40 text-text-default focus:ring-esmerald/30 dark:bg-surface-muted dark:text-text-brand dark:focus:ring-lemon/30">
            </label>

            <div class="flex flex-col gap-3 sm:col-span-2 sm:flex-row sm:justify-end">
              <BaseButton variant="secondary" size="md" @click="syncFormFromClient">
                Restablecer
              </BaseButton>
              <BaseButton variant="accent" size="md" type="submit" :disabled="platformClientsStore.isUpdating">
                {{ platformClientsStore.isUpdating ? 'Guardando...' : 'Guardar cambios' }}
              </BaseButton>
            </div>
          </form>
        </article>
      </section>
    </div>

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
import { usePageEntrance } from '~/composables/usePageEntrance'
import { usePlatformClientsStore } from '~/stores/platform-clients'
import { formatDate } from '~/utils/formatDate'

definePageMeta({
  layout: 'platform',
  middleware: ['platform-auth'],
  platformRole: 'admin',
})

usePageEntrance('#platform-client-detail')

const route = useRoute()
const localePath = useLocalePath()
const platformClientsStore = usePlatformClientsStore()
const pageMessage = ref('')
const pageMessageVariant = ref('success')
const form = reactive({
  first_name: '',
  last_name: '',
  company_name: '',
  phone: '',
  is_active: true,
})

const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal()

const clientId = computed(() => Number(route.params.id))
const clientInitials = computed(() => `${form.first_name || ''} ${form.last_name || ''}`
  .trim()
  .split(/\s+/)
  .slice(0, 2)
  .map((part) => part[0]?.toUpperCase() || '')
  .join('') || 'PA')

function statusLabel(client) {
  if (!client?.is_active) return 'Inactivo'
  if (!client?.is_onboarded) return 'Pendiente'
  return 'Activo'
}

function statusClass(client) {
  if (!client?.is_active) return 'bg-white/10 text-text-muted'
  if (!client?.is_onboarded) return 'bg-amber-100 text-amber-700 dark:bg-primary-soft dark:text-text-brand'
  return 'bg-emerald-500/15 text-emerald-400'
}

function syncFormFromClient() {
  const client = platformClientsStore.currentClient
  if (!client) return

  form.first_name = client.first_name || ''
  form.last_name = client.last_name || ''
  form.company_name = client.company_name || ''
  form.phone = client.phone || ''
  form.is_active = Boolean(client.is_active)
}

async function loadClient() {
  pageMessage.value = ''
  const result = await platformClientsStore.fetchClient(clientId.value)
  if (result.success) {
    syncFormFromClient()
  }
}

async function handleSave() {
  pageMessage.value = ''

  if (!form.first_name.trim() || !form.last_name.trim()) {
    pageMessageVariant.value = 'error'
    pageMessage.value = 'Completa nombre y apellido del cliente.'
    return
  }

  const result = await platformClientsStore.updateClient(clientId.value, {
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    company_name: form.company_name.trim(),
    phone: form.phone.trim(),
    is_active: form.is_active,
  })

  pageMessageVariant.value = result.success ? 'success' : 'error'
  pageMessage.value = result.success
    ? 'Cliente actualizado correctamente.'
    : result.message

  if (result.success) {
    syncFormFromClient()
  }
}

async function handleResendInvite() {
  pageMessage.value = ''
  const result = await platformClientsStore.resendInvite(clientId.value)
  pageMessageVariant.value = result.success ? 'success' : 'error'
  pageMessage.value = result.success ? result.message : result.message
  await loadClient()
}

async function handleReactivate() {
  pageMessage.value = ''
  const result = await platformClientsStore.updateClient(clientId.value, { is_active: true })
  pageMessageVariant.value = result.success ? 'success' : 'error'
  pageMessage.value = result.success
    ? 'Cliente reactivado correctamente.'
    : result.message

  await loadClient()
}

function requestDeactivate() {
  requestConfirm({
    title: 'Desactivar acceso',
    message: 'El cliente dejará de poder entrar al portal hasta que se reactive su cuenta.',
    confirmText: 'Desactivar',
    variant: 'danger',
    onConfirm: async () => {
      const result = await platformClientsStore.deactivateClient(clientId.value)
      pageMessageVariant.value = result.success ? 'success' : 'error'
      pageMessage.value = result.success
        ? 'Cliente desactivado correctamente.'
        : result.message

      await loadClient()
    },
  })
}

watch(() => route.params.id, async () => {
  await loadClient()
})

onMounted(async () => {
  await loadClient()
})
</script>
