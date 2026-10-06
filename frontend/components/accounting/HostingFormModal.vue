<script setup>
import VatAmountInput from './VatAmountInput.vue'
import EntityHistorySection from '~/components/history/EntityHistorySection.vue';
import { useId, computed, ref, watch } from 'vue'
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue'
import ProjectSelect from '~/components/accounting/ProjectSelect.vue'
import ClientFormFields from '~/components/clients/ClientFormFields.vue'
import { clientFormPayload, emptyClientForm } from '~/utils/billingCode'
import { useProposalClientsStore } from '~/stores/proposal_clients'
import { suggestClient } from '~/utils/clientMatch'
import { formatMoney } from '~/utils/formatMoney'

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'submit', 'project-created'])

const clientsStore = useProposalClientsStore()
const creatingClient = ref(false)
const inlineClientOpen = ref(false)
const inlineClient = ref(emptyClientForm())
const inlineClientErrors = ref({})
/** Proposed pairing for a record saved before the relation existed. */
const suggestion = ref(null)

const isEdit = computed(() => !!props.record)
const title = computed(() => (isEdit.value ? 'Editar Hosting' : 'Nuevo Hosting'))

const modalityOptions = [
  { value: 'quarterly', label: 'Trimestral' },
  { value: 'semiannual', label: 'Semestral' },
  { value: 'nine_month', label: 'Cada 9 meses' },
]
const legacyModalityLabels = {
  monthly: 'Mensual (histórico)',
  annual: 'Anual (histórico)',
}
const availableModalityOptions = computed(() => {
  const current = props.record?.payment_modality
  if (!legacyModalityLabels[current]) return modalityOptions
  return [
    ...modalityOptions,
    { value: current, label: legacyModalityLabels[current] },
  ]
})

function defaultForm() {
  return {
    client: null,
    project: null,
    client_display_name: '',
    client_name: '',
    client_email: '',
    client_contact_name: '',
    client_identification: '',
    domain_url: '',
    monthly_value: '',
    payment_modality: 'quarterly',
    benefit: '',
    valid_from: '',
    valid_to: '',
    payment_per_cycle: '',
    vat_rate: 19,
    vat_capture: null,
    is_active: true,
    notes: '',
  }
}

const form = ref(defaultForm())

watch(
  () => [props.open, props.record],
  () => {
    if (!props.open) return
    if (props.record) {
      form.value = {
        client: props.record.client ?? null,
        project: props.record.project ?? null,
        client_display_name: props.record.client_display_name ?? '',
        client_name: props.record.client_name ?? '',
        client_email: props.record.client_email ?? '',
        client_contact_name: props.record.client_contact_name ?? '',
        client_identification: props.record.client_identification ?? '',
        domain_url: props.record.domain_url ?? '',
        monthly_value: props.record.monthly_value ?? '',
        payment_modality: props.record.payment_modality ?? 'quarterly',
        benefit: props.record.benefit ?? '',
        valid_from: props.record.valid_from ?? '',
        valid_to: props.record.valid_to ?? '',
        payment_per_cycle: props.record.payment_per_cycle ?? '',
        vat_rate: props.record.vat_rate ?? null,
        vat_capture: null,
        is_active: props.record.is_active ?? true,
        notes: props.record.notes ?? '',
      }
    } else {
      form.value = defaultForm()
    }
    inlineClientOpen.value = false
    inlineClientErrors.value = {}
    suggestion.value = null
    if (props.record && !props.record.client) proposeClient()
  },
  { immediate: true },
)

/**
 * Records saved before the relation existed carry the client as free text.
 * Search it and, if a registered client resembles it, offer the pairing —
 * confirming is one click, and a wrong guess is discarded just as fast.
 */
async function proposeClient() {
  const typed = form.value.client_name?.trim()
  if (!typed) return
  const result = await clientsStore.searchClients(typed.split(' - ')[0] || typed)
  if (!result.success) return
  const match = suggestClient(typed, result.data)
  if (match) suggestion.value = match
}

function acceptSuggestion() {
  const match = suggestion.value
  suggestion.value = null
  if (match) onClientSelect(match)
}

function onClientSelect(client) {
  if (!client) {
    form.value.client = null
    form.value.client_display_name = ''
    return
  }
  form.value.client = client.id
  form.value.client_display_name = client.name || ''
  suggestion.value = null
  // Seed the billing snapshot, never overwrite what the operator typed.
  if (!form.value.client_name) {
    form.value.client_name = client.company || client.name || ''
  }
  if (!form.value.client_email && !client.is_email_placeholder) {
    form.value.client_email = client.email || ''
  }
  if (!form.value.client_contact_name) {
    form.value.client_contact_name = client.name || ''
  }
  if (!form.value.client_identification) {
    form.value.client_identification = client.nit || client.cedula || ''
  }
}

function onCreateNewClient(typedName) {
  inlineClientOpen.value = true
  inlineClientErrors.value = {}
  inlineClient.value = {
    ...emptyClientForm(),
    name: typedName || form.value.client_name || '',
  }
}

function clearInlineClientError(field) {
  if (!inlineClientErrors.value[field]) return
  const next = { ...inlineClientErrors.value }
  delete next[field]
  inlineClientErrors.value = next
}

async function createInlineClient() {
  inlineClientErrors.value = {}
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
  inlineClientErrors.value = Object.fromEntries(
    Object.entries(result.errors || {})
      .filter(([field]) => !['message', 'error'].includes(field))
      .map(([field, messages]) => [
        field,
        Array.isArray(messages) ? messages.join(' ') : String(messages || ''),
      ]),
  )
}

function addIfFilled(payload, key, value) {
  if (value !== '' && value !== null && value !== undefined) payload[key] = value
}

function onSubmit() {
  const payload = {
    client: form.value.client,
    // Always sent, null included: that is what lets an edit unlink it.
    project: form.value.project,
    client_name: form.value.client_name,
    monthly_value: form.value.monthly_value,
    payment_modality: form.value.payment_modality,
    is_active: form.value.is_active,
  }
  payload.client_email = form.value.client_email
  payload.client_contact_name = form.value.client_contact_name
  payload.client_identification = form.value.client_identification
  payload.domain_url = form.value.domain_url
  payload.benefit = form.value.benefit
  payload.notes = form.value.notes
  payload.valid_from = form.value.valid_from || null
  payload.valid_to = form.value.valid_to || null
  payload.vat_rate = form.value.vat_rate
  if (form.value.vat_capture) Object.assign(payload, form.value.vat_capture)
  else addIfFilled(payload, 'payment_per_cycle', form.value.payment_per_cycle)
  emit('submit', payload)
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="form" title-id="hosting-form-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="hosting-form-title" class="text-lg font-bold text-text-default">{{ title }}</h3>
    </div>
    <EntityHistorySection v-if="open && record?.id" entity-type="hosting" :object-id="record.id" class="mx-5" />
    <form :id="modalFormId" class="px-6 py-4 space-y-4" @submit.prevent="onSubmit">
      <BaseFormField
        label="Cliente"
        :required="!isEdit"
        required-message="Elige o crea un cliente."
        hint="Cliente al que pertenece el hosting."
      >
        <ClientAutocomplete
          v-model="form.client"
          :initial-label="form.client_display_name"
          test-id="hosting-form-client"
          allow-create
          :required="!isEdit"
          required-message="Elige o crea un cliente."
          @select="onClientSelect"
          @create-new="onCreateNewClient"
        />
        <p
          v-if="isEdit && !form.client"
          class="text-xs text-warning-strong mt-1"
          data-testid="hosting-form-client-pending"
        >
          Pendiente de asignación — podés guardar igual mientras lo completás.
        </p>
        <!-- Suggested pairing for the free-text name saved before the relation -->
        <div
          v-if="suggestion"
          class="mt-2 flex flex-wrap items-center gap-2 text-xs rounded-lg border border-border-default bg-surface-raised px-3 py-2"
          data-testid="hosting-form-client-suggestion"
        >
          <span class="text-text-muted">
            ¿Es <span class="font-medium text-text-default">{{ suggestion.name }}</span>
            <span v-if="suggestion.company">({{ suggestion.company }})</span>?
          </span>
          <BaseButton
            type="button"
            variant="primary"
            size="sm"
            data-testid="hosting-form-accept-suggestion"
            @click="acceptSuggestion"
          >
            Sí, es este
          </BaseButton>
          <BaseButton type="button" variant="ghost" size="sm" @click="suggestion = null">
            No
          </BaseButton>
        </div>
      </BaseFormField>

      <!-- The `Marca` half of the old `Persona - Marca` label, as a relation -->
      <ProjectSelect
        v-model="form.project"
        :client-profile-id="form.client"
        :client-label="form.client_display_name"
        :auto-select-single="!isEdit"
        testid="hosting-form-project"
        @created="emit('project-created', $event)"
      />

      <!-- Inline client creation: the clients module without leaving the form -->
      <div
        v-if="inlineClientOpen"
        class="rounded-xl border border-border-default bg-surface-raised p-4 space-y-3"
        data-testid="hosting-form-inline-client"
      >
        <p class="text-sm font-medium text-text-default">Crear cliente nuevo</p>
        <ClientFormFields
          v-model="inlineClient"
          :errors="inlineClientErrors"
          testid-prefix="hosting-form-inline-client"
          dense
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
            :disabled="creatingClient"
            data-testid="hosting-form-inline-client-save"
            @click="createInlineClient"
          >
            {{ creatingClient ? 'Creando...' : 'Crear cliente' }}
          </BaseButton>
        </div>
      </div>

      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Nombre en la cuenta de cobro" required>
          <BaseInput v-model="form.client_name" data-testid="hosting-form-client-name" required />
        </BaseFormField>
        <BaseFormField label="Dominio">
          <BaseInput
            v-model="form.domain_url"
            data-testid="hosting-form-domain"
            placeholder="https://ejemplo.com"
          />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormRow
        :cols="2"
        :gap="4"
        help="Si el email queda vacío, se usa el correo del cliente."
      >
        <BaseFormField label="Email del cliente">
          <BaseInput
            v-model="form.client_email"
            type="email"
            data-testid="hosting-form-client-email"
            placeholder="cliente@dominio.com"
          />
        </BaseFormField>
        <BaseFormField label="Contacto del cliente">
          <BaseInput
            v-model="form.client_contact_name"
            data-testid="hosting-form-contact"
            placeholder="Nombre de quien recibe"
          />
        </BaseFormField>
      </BaseFormRow>



      <BaseFormRow :cols="3" :gap="3">
      <BaseFormField label="Identificación del cliente (NIT/CC)">
        <BaseInput v-model="form.client_identification" data-testid="hosting-form-identification" />
      </BaseFormField>
        <BaseFormField label="Valor por mes" required>
          <BaseCurrencyInput v-model="form.monthly_value" data-testid="hosting-form-monthly" required />
        </BaseFormField>
        <BaseFormField label="Modalidad de pago">
          <BaseSelect
            v-model="form.payment_modality"
            :options="availableModalityOptions"
            data-testid="hosting-form-modality"
          />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormField label="Beneficio">
        <BaseInput v-model="form.benefit" data-testid="hosting-form-benefit" />
      </BaseFormField>

      <BaseFormRow :cols="2" :gap="4">
        <BaseFormField label="Vigente desde" for="hosting-form-valid-from">
          <BaseInput id="hosting-form-valid-from" v-model="form.valid_from" type="date" />
        </BaseFormField>
        <BaseFormField label="Vigente hasta" for="hosting-form-valid-to">
          <BaseInput id="hosting-form-valid-to" v-model="form.valid_to" type="date" />
        </BaseFormField>
      </BaseFormRow>

      <BaseFormField
        label="Pago por ciclo"
        hint="Si lo dejas vacío al crear, se calcula desde la modalidad"
      >
        <VatAmountInput v-model="form.payment_per_cycle" v-model:rate="form.vat_rate" :reset-key="open" :required="false" input-test-id="hosting-form-per-cycle" @capture="form.vat_capture = $event" />
      </BaseFormField>

      <p v-if="isEdit" class="text-xs text-text-muted">
        Ciclos: <span class="font-medium text-text-default">{{ record?.cycles_count ?? 0 }}</span>
        · Total pagado:
        <span class="font-medium text-text-default">{{ formatMoney(record?.total_paid ?? 0, 'COP') }}</span>
        — se calculan desde el histórico de ciclos (acción "Ciclos de pago" en la tabla).
      </p>

      <BaseFormField label="Activo">
        <BaseToggle v-model="form.is_active" aria-label="Activo" />
      </BaseFormField>

      <BaseFormField label="Notas">
        <BaseTextarea v-model="form.notes" :rows="3" />
      </BaseFormField>

    </form>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="secondary" @click="emit('close')">
          Cancelar
        </BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          :disabled="saving"
          data-testid="hosting-form-submit"
        >
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
