<template>
  <div>
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-8">
      <div>
        <h1 class="text-2xl font-light text-text-default">Administradores</h1>
        <p class="text-sm text-text-subtle mt-1">Gestionar administradores de la plataforma</p>
      </div>
      <BaseButton
        variant="primary"
        size="md"
        class="w-fit"
        @click="openCreateModal"
      >
        <BaseActionIcon action="create" />
        Agregar Administrador
      </BaseButton>
    </div>

    <!-- Filters -->
    <!--
      `flex-wrap` por la misma razón que la tira de predefinidos: sin él la fila
      se desborda y el `body { overflow-x: hidden }` de app.vue la recorta SIN
      barra de scroll, así que el último filtro queda inalcanzable y el corte se
      lee como el final de la lista. Son cuatro etiquetas cortas: envolver
      alcanza, no hace falta colapsar en un selector.
    -->
    <div class="flex flex-wrap gap-2 mb-5">
      <!-- design-tokens: allow-raw-button — selectable filter chip -->
      <button
        v-for="f in filters"
        :key="f.value"
        class="text-xs px-3 py-1.5 rounded-full font-medium transition-colors"
        :class="activeFilter === f.value
          ? 'bg-primary text-white'
          : 'bg-surface-raised text-text-muted hover:bg-border-muted'"
        @click="activeFilter = f.value"
      >
        {{ f.label }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="adminStore.loading" class="text-center py-16 text-text-subtle text-sm">
      Cargando administradores...
    </div>

    <!-- Empty -->
    <div v-else-if="filteredAdmins.length === 0" class="text-center py-16 text-text-subtle text-sm">
      {{ activeFilter !== 'all' ? 'No hay administradores con este filtro.' : 'No hay administradores aún.' }}
    </div>

    <!-- Admin list -->
    <div v-else class="space-y-3">
      <div
        v-for="admin in filteredAdmins"
        :key="admin.user_id"
        class="bg-surface rounded-xl shadow-sm border border-border-muted px-5 py-4 flex flex-wrap items-center justify-between gap-3"
      >
        <div class="flex min-w-0 flex-1 items-center gap-4">
          <!-- Avatar -->
          <div class="w-10 h-10 rounded-full bg-primary-soft flex items-center justify-center flex-shrink-0">
            <span class="text-text-brand font-bold text-sm">{{ initials(admin.first_name, admin.last_name) }}</span>
          </div>
          <div class="min-w-0 max-w-full">
            <p
              class="min-w-0 max-w-full text-sm font-semibold text-text-default [overflow-wrap:anywhere]"
              :title="`${admin.first_name} ${admin.last_name}`.trim()"
            >
              {{ admin.first_name }} {{ admin.last_name }}
            </p>
            <p class="mt-0.5 min-w-0 max-w-full text-xs text-text-subtle [overflow-wrap:anywhere]" :title="admin.email">{{ admin.email }}</p>
          </div>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
          <!-- Status pill -->
          <span
            class="inline-flex min-w-0 max-w-full flex-wrap rounded-full px-2.5 py-1 text-xs font-medium [overflow-wrap:anywhere]"
            :class="statusClass(admin)"
          >
            {{ statusLabel(admin) }}
          </span>

          <!-- Actions -->
          <BaseButton variant="ghost" size="sm" v-if="!admin.is_onboarded && admin.is_active" :disabled="resendingId === admin.user_id" @click="handleResendInvite(admin.user_id)">
            {{ resendingId === admin.user_id ? 'Enviando...' : 'Reenviar invitación' }}
          </BaseButton>

          <BaseButton variant="secondary" size="sm" v-if="admin.is_active" :disabled="loggingInId === admin.user_id" @click="handleLoginAs(admin.user_id)">
            {{ loggingInId === admin.user_id ? 'Abriendo...' : 'Login with this user' }}
          </BaseButton>

          <BaseButton variant="danger-ghost" size="sm" v-if="admin.is_active" @click="handleDeactivate(admin.user_id)">
            Desactivar
          </BaseButton>

          <BaseButton variant="secondary" size="sm" v-if="!admin.is_active" @click="handleReactivate(admin.user_id)">
            Reactivar
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- Create modal -->
    <BaseModal
      :model-value="showCreateModal"
      kind="form"
      title-id="admins-create-title"
      @close="closeModal"
    >
      <div class="px-6 pb-2 pt-6">
        <h2 id="admins-create-title" class="text-lg font-semibold text-text-default">
          Agregar administrador
        </h2>
        <p class="mt-1 text-sm text-text-muted">
          Enviaremos credenciales temporales al correo indicado.
        </p>
      </div>

      <form :id="modalFormId" novalidate @submit.prevent="handleCreate">
        <div class="space-y-4 px-6 py-4">
          <BaseFormField
            v-slot="{ invalid, errorId }"
            label="Email"
            required
            :error="createFieldErrors.email"
          >
            <BaseInput
              v-model="form.email"
              type="email"
              placeholder="admin@ejemplo.com"
              :error="invalid"
              :aria-describedby="errorId"
              @update:model-value="clearCreateFieldError('email')"
            />
          </BaseFormField>
          <BaseFormRow>
            <BaseFormField
              v-slot="{ invalid, errorId }"
              label="Nombre"
              required
              :error="createFieldErrors.first_name"
            >
              <BaseInput
                v-model="form.first_name"
                placeholder="Nombre"
                :error="invalid"
                :aria-describedby="errorId"
                @update:model-value="clearCreateFieldError('first_name')"
              />
            </BaseFormField>
            <BaseFormField
              v-slot="{ invalid, errorId }"
              label="Apellido"
              required
              :error="createFieldErrors.last_name"
            >
              <BaseInput
                v-model="form.last_name"
                placeholder="Apellido"
                :error="invalid"
                :aria-describedby="errorId"
                @update:model-value="clearCreateFieldError('last_name')"
              />
            </BaseFormField>
          </BaseFormRow>
          <BaseAlert v-if="createError" variant="danger">{{ createError }}</BaseAlert>
        </div>

      </form>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="ghost" size="md" type="button" @click="closeModal">
            Cancelar
          </BaseButton>
          <BaseButton type="submit" :form="modalFormId" variant="primary" size="md" :loading="creating">
            {{ creating ? 'Creando...' : 'Crear administrador' }}
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </div>
</template>

<script setup>
import { useId, ref, computed, onMounted } from 'vue';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { usePanelNotify } from '~/composables/usePanelNotify';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const { usePanelAdminsStore } = await import('~/stores/panel_admins');
const adminStore = usePanelAdminsStore();

const activeFilter = ref('all');
const showCreateModal = ref(false);
const creating = ref(false);
const createError = ref('');
const createFieldErrors = ref({});
const resendingId = ref(null);
const loggingInId = ref(null);
const notify = usePanelNotify();

const form = ref({ email: '', first_name: '', last_name: '' });

const filters = [
  { label: 'Todos', value: 'all' },
  { label: 'Activos', value: 'active' },
  { label: 'Pendientes', value: 'pending' },
  { label: 'Inactivos', value: 'inactive' },
];

const filteredAdmins = computed(() => {
  if (activeFilter.value === 'all') return adminStore.admins;
  if (activeFilter.value === 'active') return adminStore.activeAdmins;
  if (activeFilter.value === 'pending') return adminStore.pendingAdmins;
  if (activeFilter.value === 'inactive') return adminStore.inactiveAdmins;
  return adminStore.admins;
});

onMounted(() => {
  adminStore.fetchAdmins();
});

usePanelRefresh(() => adminStore.fetchAdmins());

function initials(firstName, lastName) {
  return ((firstName?.[0] || '') + (lastName?.[0] || '')).toUpperCase() || '?';
}

function statusLabel(admin) {
  if (!admin.is_active) return 'Inactivo';
  if (!admin.is_onboarded) return 'Pendiente';
  return 'Activo';
}

function statusClass(admin) {
  if (!admin.is_active) return 'bg-surface-raised text-text-muted';
  if (!admin.is_onboarded) return 'bg-warning-soft text-warning-strong';
  return 'bg-primary-soft text-text-brand';
}

function closeModal() {
  showCreateModal.value = false;
  form.value = { email: '', first_name: '', last_name: '' };
  createError.value = '';
  createFieldErrors.value = {};
}

function openCreateModal() {
  form.value = { email: '', first_name: '', last_name: '' };
  createError.value = '';
  createFieldErrors.value = {};
  showCreateModal.value = true;
}

function clearCreateFieldError(field) {
  const nextErrors = { ...createFieldErrors.value };
  delete nextErrors[field];
  createFieldErrors.value = nextErrors;
}

async function handleCreate() {
  createError.value = '';
  createFieldErrors.value = {
    ...(!form.value.email.trim() ? { email: 'Escribe el correo del administrador.' } : {}),
    ...(!form.value.first_name.trim() ? { first_name: 'Escribe el nombre.' } : {}),
    ...(!form.value.last_name.trim() ? { last_name: 'Escribe el apellido.' } : {}),
  };
  if (Object.keys(createFieldErrors.value).length) return;

  creating.value = true;

  const result = await adminStore.createAdmin(form.value);
  creating.value = false;

  if (result.success) {
    closeModal();
    notify.success('Administrador creado. Se envió la invitación por email.');
  } else {
    createFieldErrors.value = result.fieldErrors || {};
    if (!Object.keys(createFieldErrors.value).length) createError.value = result.error;
  }
}

async function handleResendInvite(userId) {
  resendingId.value = userId;
  const result = await adminStore.resendInvite(userId);
  resendingId.value = null;

  if (result.success) {
    notify.success('Invitación reenviada.');
  } else {
    notify.error(result.error);
  }
}

async function handleLoginAs(userId) {
  loggingInId.value = userId;
  const result = await adminStore.loginAsUser(userId);
  loggingInId.value = null;

  if (result.success && result.redirectUrl) {
    window.open(result.redirectUrl, '_blank', 'noopener');
  } else {
    notify.error(result.error || 'No pudimos iniciar sesión como este usuario.');
  }
}

async function handleDeactivate(userId) {
  const result = await adminStore.deactivateAdmin(userId);
  if (result.success) {
    notify.success('Administrador desactivado.');
  } else {
    notify.error(result.error);
  }
}

async function handleReactivate(userId) {
  const result = await adminStore.reactivateAdmin(userId);
  if (result.success) {
    notify.success('Administrador reactivado.');
  } else {
    notify.error(result.error);
  }
}

const modalFormId = useId();
</script>
