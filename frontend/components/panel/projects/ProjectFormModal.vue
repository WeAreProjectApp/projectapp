<script setup>
import { useId, computed, ref, watch } from 'vue'
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue'
import ClientFormFields from '~/components/clients/ClientFormFields.vue'
import { clientFormPayload, emptyClientForm } from '~/utils/billingCode'
import { useProposalClientsStore } from '~/stores/proposal_clients'
import { useProjectStateStore } from '~/stores/project_states'
import { normalizeName } from '~/utils/clientMatch'

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  saving: { type: Boolean, default: false },
  /** { profile_id|id, name } — pre-selects the client (orphans panel CTA). */
  seedClient: { type: Object, default: null },
  /** Loaded module rows; the duplicate warning scans the same client's. */
  existingProjects: { type: Array, default: () => [] },
  /** Serializer errors returned by the create/update request. */
  fieldErrors: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['close', 'submit', 'change-client', 'clear-error'])

const clientsStore = useProposalClientsStore()
const stateStore = useProjectStateStore()
const creatingClient = ref(false)
const inlineClientOpen = ref(false)
const inlineClient = ref(emptyClientForm())
const inlineClientErrors = ref({})
const validationAttempted = ref(false)

const isEdit = computed(() => !!props.record)
const title = computed(() => (isEdit.value ? 'Editar proyecto' : 'Nuevo proyecto'))

const stateOptions = computed(() => stateStore.activeStates.map((state) => ({
  value: state.id,
  label: state.name,
})))

function defaultForm() {
  return {
    name: '',
    client_profile_id: null,
    client_display_name: '',
    description: '',
    state_id: '',
  }
}

const form = ref(defaultForm())

watch(
  () => [props.open, props.record],
  async () => {
    if (!props.open) return
    if (!stateStore.states.length) await stateStore.fetchCatalog()
    if (props.record) {
      form.value = {
        name: props.record.name ?? '',
        client_profile_id: props.record.client?.profile_id ?? null,
        client_display_name: props.record.client?.name ?? '',
        description: props.record.description ?? '',
        state_id: props.record.current_state?.id ?? '',
      }
    } else {
      form.value = defaultForm()
      form.value.state_id = stateStore.stateByKey('development')?.id ?? ''
      if (props.seedClient) {
        form.value.client_profile_id = props.seedClient.profile_id
          ?? props.seedClient.id ?? null
        form.value.client_display_name = props.seedClient.name ?? ''
      }
    }
    inlineClientOpen.value = false
    inlineClientErrors.value = {}
    validationAttempted.value = false
  },
  { immediate: true },
)

/**
 * Same-name project for the same client: a signal, not an error — the
 * backend accepts it and the strip never blocks saving. Accent/case-blind
 * comparison so "Vástago" and "vastago" read as the same name.
 */
const duplicate = computed(() => {
  const term = normalizeName(form.value.name)
  if (!term || !form.value.client_profile_id) return null
  return props.existingProjects.find((project) => (
    project.client?.profile_id === form.value.client_profile_id
    && project.id !== props.record?.id
    && normalizeName(project.name) === term
  )) || null
})

const nameError = computed(() => (
  props.fieldErrors.name
  || (validationAttempted.value && !form.value.name.trim()
    ? 'Escribe el nombre del proyecto.'
    : '')
))

const clientError = computed(() => (
  props.fieldErrors.client_profile_id
  || props.fieldErrors.client
  || (validationAttempted.value && !isEdit.value && !form.value.client_profile_id
    ? 'Elige o crea un cliente.'
    : '')
))

const stateError = computed(() => props.fieldErrors.state_id || props.fieldErrors.state || '')
const descriptionError = computed(() => props.fieldErrors.description || '')

function clearFieldError(field) {
  emit('clear-error', field)
}

function onClientSelect(client) {
  clearFieldError('client_profile_id')
  clearFieldError('client')
  if (!client) {
    form.value.client_profile_id = null
    form.value.client_display_name = ''
    return
  }
  form.value.client_profile_id = client.id
  form.value.client_display_name = client.name || ''
}

function onCreateNewClient(typedName) {
  inlineClientOpen.value = true
  inlineClient.value = { ...emptyClientForm(), name: typedName || '' }
  inlineClientErrors.value = {}
}

function clearInlineClientError(field) {
  if (!inlineClientErrors.value[field]) return
  const nextErrors = { ...inlineClientErrors.value }
  delete nextErrors[field]
  inlineClientErrors.value = nextErrors
}

async function createInlineClient() {
  if (!inlineClient.value.name.trim()) {
    inlineClientErrors.value = { name: 'Escribe el nombre del cliente.' }
    return
  }
  creatingClient.value = true
  const result = await clientsStore.createClient(clientFormPayload(inlineClient.value))
  creatingClient.value = false
  if (result.success && result.data?.id) {
    inlineClientOpen.value = false
    onClientSelect(result.data)
    return
  }
  const errors = result.errors && typeof result.errors === 'object' ? result.errors : {}
  inlineClientErrors.value = {
    ...errors,
    name: errors.name?.[0] || errors.name || '',
  }
}

function onSubmit() {
  validationAttempted.value = true
  if (nameError.value || clientError.value) return
  const payload = {
    name: form.value.name.trim(),
    description: form.value.description,
  }
  // The client travels only on create: the panel keeps it immutable and the
  // backend answers 400 if the key even appears on an update.
  if (!isEdit.value) {
    payload.client_profile_id = form.value.client_profile_id
    if (form.value.state_id) payload.state_id = form.value.state_id
  }
  emit('submit', payload)
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="form" title-id="project-form-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="project-form-title" class="text-lg font-bold text-text-default">{{ title }}</h3>
    </div>
    <form :id="modalFormId" novalidate @submit.prevent="onSubmit">
      <div class="space-y-4 px-6 py-4">
      <BaseFormField
        v-slot="{ invalid, errorId }"
        label="Nombre del proyecto"
        required
        :error="nameError"
      >
        <BaseInput
          v-model="form.name"
          data-testid="project-form-name"
          placeholder="Kore, Vástago, Crushme..."
          :error="invalid"
          :aria-describedby="errorId"
          @update:model-value="clearFieldError('name')"
        />
        <!-- Duplicate signal: warn, never block -->
        <div
          v-if="duplicate"
          class="mt-2 flex flex-wrap items-center gap-2 text-xs rounded-lg border border-border-default bg-surface-raised px-3 py-2"
          data-testid="project-form-duplicate-warning"
        >
          <span class="text-text-muted">
            Este cliente ya tiene un proyecto llamado
            <span class="font-medium text-text-default">{{ duplicate.name }}</span>.
            Puedes guardarlo igual si es otro proyecto.
          </span>
        </div>
      </BaseFormField>

      <BaseFormField
        v-if="!isEdit"
        label="Cliente"
        required
        hint="Cliente al que pertenece y se factura el proyecto."
        :error="clientError"
        v-slot="{ invalid, errorId }"
      >
        <ClientAutocomplete
          v-model="form.client_profile_id"
          :initial-label="form.client_display_name"
          test-id="project-form-client"
          allow-create
          :error="invalid"
          :error-described-by="errorId"
          @select="onClientSelect"
          @create-new="onCreateNewClient"
        />
      </BaseFormField>
      <BaseFormField
        v-else
        label="Cliente"
        hint="Cambiarlo es una operación guiada: muestra el impacto sobre hostings, ingresos y cuentas antes de aplicar."
      >
        <div class="flex items-center justify-between gap-2 py-1.5">
          <p class="text-sm text-text-default" data-testid="project-form-client-readonly">
            {{ form.client_display_name || '—' }}
          </p>
          <BaseButton
            type="button"
            variant="ghost"
            size="sm"
            data-testid="project-form-change-client"
            @click="emit('change-client')"
          >
            Cambiar cliente…
          </BaseButton>
        </div>
      </BaseFormField>

      <!-- Inline client creation: same escape hatch as hostings and incomes -->
      <div
        v-if="inlineClientOpen"
        class="rounded-xl border border-border-default bg-surface-raised p-4 space-y-3"
        data-testid="project-form-inline-client"
      >
        <p class="text-sm font-medium text-text-default">Crear cliente nuevo</p>
        <ClientFormFields
          v-model="inlineClient"
          testid-prefix="project-form-inline-client"
          dense
          :errors="inlineClientErrors"
          @clear-error="clearInlineClientError"
        />
        <div class="flex justify-end gap-2">
          <BaseButton type="button" variant="secondary" size="sm" @click="inlineClientOpen = false">
            Cancelar
          </BaseButton>
          <BaseButton
            type="button"
            variant="primary"
            size="sm"
            :loading="creatingClient"
            data-testid="project-form-inline-client-save"
            @click="createInlineClient"
          >
            {{ creatingClient ? 'Creando...' : 'Crear cliente' }}
          </BaseButton>
        </div>
      </div>

      <!-- Later state changes go through the impact preview. -->
      <BaseFormField
        v-if="!isEdit"
        v-slot="{ invalid, errorId }"
        label="Estado inicial"
        :error="stateError"
      >
        <BaseSelect
          v-model="form.state_id"
          :options="stateOptions"
          data-testid="project-form-status"
          :error="invalid"
          :aria-describedby="errorId"
          @update:model-value="clearFieldError('state_id')"
        />
      </BaseFormField>

      <BaseFormField
        v-slot="{ invalid, errorId }"
        label="Descripción"
        :error="descriptionError"
      >
        <BaseTextarea
          v-model="form.description"
          :rows="3"
          data-testid="project-form-description"
          placeholder="Qué se entrega, alcance, contexto..."
          :error="invalid"
          :aria-describedby="errorId"
          @update:model-value="clearFieldError('description')"
        />
      </BaseFormField>

      </div>

    </form>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="secondary" @click="emit('close')">
          Cancelar
        </BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          :loading="saving"
          data-testid="project-form-submit"
        >
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
