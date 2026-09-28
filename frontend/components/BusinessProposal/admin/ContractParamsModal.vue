<template>
  <BaseModal
    :model-value="visible"
    :kind="contractSource === 'custom' && showPreview ? 'wizard' : 'form-wide'"
    :close-on-backdrop="!saving"
    :close-on-esc="!saving"
    @update:model-value="(v) => !v && !saving && $emit('cancel')"
  >
    <div>
      <div class="sticky top-0 bg-surface border-b border-border-muted px-6 py-4 rounded-t-2xl z-10">
            <h2 class="text-lg font-semibold text-text-default">
              {{ isEditing ? 'Editar' : 'Generar' }} {{ variantSpec.label.toLowerCase() }}
            </h2>
            <p class="text-xs text-text-muted mt-1">
              <template v-if="variantSpec.subtitle">{{ variantSpec.subtitle }}. </template>
              Usa el contrato por defecto con datos del cliente, o sube un contrato personalizado en Markdown.
              <template v-if="variant !== 'combined'"> Los datos de las partes son comunes a los dos contratos.</template>
            </p>
          </div>

          <form :id="modalFormId" class="px-6 py-5 space-y-6" @submit.prevent="handleSubmit">
            <fieldset :disabled="saving" class="min-w-0 space-y-6">
            <!-- Source toggle -->
            <BaseSegmented
              v-model="contractSource"
              class="max-w-md"
              full-width
              :options="[
                { value: 'default', label: 'Contrato por defecto' },
                { value: 'custom', label: 'Contrato personalizado' },
              ]"
            />

            <!-- DEFAULT MODE: contract params form -->
            <template v-if="contractSource === 'default'">
              <!-- Contractor (seller) section -->
              <fieldset>
                <legend class="text-sm font-semibold text-text-brand mb-3">EL CONTRATISTA (tu empresa)</legend>
                <div class="space-y-4">
                  <BaseFormRow :cols="2" :gap="4" at="sm">
                    <BaseFormField
                      label="Nombre completo"
                      required
                      size="sm"
                      :error="formErrors.contractor_full_name"
                    >
                    <BaseInput v-model="form.contractor_full_name" type="text" size="sm" />
                    </BaseFormField>
                    <BaseFormField label="NIT" size="sm">
                    <BaseInput v-model="form.contractor_nit" type="text" size="sm" />
                    </BaseFormField>
                  </BaseFormRow>
                  <BaseFormRow :cols="2" :gap="4" at="sm">
                    <BaseFormField label="Cédula" size="sm">
                    <BaseInput v-model="form.contractor_cedula" type="text" size="sm" />
                    </BaseFormField>
                    <BaseFormField
                      label="Email de notificación"
                      required
                      size="sm"
                      :error="formErrors.contractor_email"
                    >
                    <BaseInput v-model="form.contractor_email" type="email" size="sm" />
                    </BaseFormField>
                    <template #help>
                      <span>Indica NIT o cédula. El NIT tiene prioridad en el contrato.</span>
                      <span
                        v-if="formErrors.contractor_identity"
                        class="mt-1 block text-danger-strong"
                        role="alert"
                      >
                        {{ formErrors.contractor_identity }}
                      </span>
                    </template>
                  </BaseFormRow>
                  <BaseFormField
                    label="Ciudad del contrato"
                    required
                    size="sm"
                    :error="formErrors.contract_city"
                  >
                    <BaseInput v-model="form.contract_city" type="text" size="sm" />
                  </BaseFormField>
                </div>
                <BaseFormRow :cols="3" :gap="4" at="sm" class="mt-4">
                  <BaseFormField label="Banco" required size="sm" :error="formErrors.bank_name">
                    <BaseInput v-model="form.bank_name" type="text" size="sm" />
                  </BaseFormField>
                  <BaseFormField label="Tipo de cuenta" size="sm">
                    <BaseSelect
                      v-model="form.bank_account_type"
                      size="sm"
                      :options="[{ value: 'Ahorros', label: 'Ahorros' }, { value: 'Corriente', label: 'Corriente' }]"
                    />
                  </BaseFormField>
                  <BaseFormField
                    label="Número de cuenta"
                    required
                    size="sm"
                    :error="formErrors.bank_account_number"
                  >
                    <BaseInput v-model="form.bank_account_number" type="text" size="sm" />
                  </BaseFormField>
                </BaseFormRow>
              </fieldset>

              <!-- Client (contratante) section -->
              <fieldset>
                <legend class="text-sm font-semibold text-text-brand mb-3">EL CONTRATANTE (cliente)</legend>
                <div class="space-y-4">
                  <BaseFormRow :cols="2" :gap="4" at="sm">
                    <BaseFormField
                      label="Nombre completo"
                      required
                      size="sm"
                      :error="formErrors.client_full_name"
                    >
                    <BaseInput v-model="form.client_full_name" type="text" size="sm" />
                    </BaseFormField>
                    <BaseFormField
                      label="Cédula / NIT"
                      required
                      size="sm"
                      :error="formErrors.client_cedula"
                    >
                    <BaseInput v-model="form.client_cedula" type="text" size="sm" placeholder="Ej: 1.234.567.890" />
                    </BaseFormField>
                  </BaseFormRow>
                  <BaseFormField
                    label="Email de notificación"
                    required
                    size="sm"
                    :error="formErrors.client_email"
                  >
                    <BaseInput v-model="form.client_email" type="email" size="sm" />
                  </BaseFormField>
                </div>
              </fieldset>

              <!-- Contract date -->
              <fieldset>
                <legend class="text-sm font-semibold text-text-brand mb-3">Datos del contrato</legend>
                <BaseFormField
                  label="Fecha del contrato"
                  required
                  size="sm"
                  :error="formErrors.contract_date"
                >
                    <BaseInput v-model="form.contract_date" type="date" size="sm" />
                </BaseFormField>
              </fieldset>

              <!-- Service terms: only the standalone service contract uses them -->
              <fieldset v-if="variant === 'service'" data-testid="contract-service-terms">
                <legend class="text-sm font-semibold text-text-brand mb-1">Datos del servicio</legend>
                <p class="text-xs text-text-muted mb-3">{{ t('serviceContract.formHint') }}</p>
                <p v-if="loadingDefaults" role="status" class="text-sm text-text-muted">{{ t('serviceContract.loading') }}</p>
                <div v-else-if="!serviceSettingsReady" class="space-y-2">
                  <p role="alert" class="text-sm text-danger-strong">{{ t('serviceContract.loadError') }}</p>
                  <BaseButton size="sm" variant="secondary" @click="retryDefaults">{{ t('serviceContract.retry') }}</BaseButton>
                </div>
                <div v-else class="space-y-4">
                  <ServiceContractTermField
                    v-for="field in SERVICE_CONTRACT_FIELDS"
                    :key="`${formRevision}-${field.key}`"
                    v-model="form[field.key]"
                    :label="t(`serviceContract.fields.${field.key}`)"
                    :options="companyDefaults.service_contract_settings[field.optionsKey]"
                    :duration="Boolean(field.duration)"
                    :error="formErrors[field.key]"
                  />
                </div>
              </fieldset>
            </template>

            <!-- CUSTOM MODE: markdown editor -->
            <template v-else>
              <div>
                <div class="flex items-center justify-between mb-2">
                  <label class="block text-sm font-medium text-text-default">Contenido del contrato (Markdown)</label>
                  <div class="flex items-center gap-2">
                    <label
                      class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg cursor-pointer
                             bg-surface-raised text-text-muted hover:bg-border-muted transition-colors"
                    >
          <BaseActionIcon action="upload" />
                      Cargar .md
                      <input type="file" accept=".md,.markdown,.txt" class="hidden" @change="handleFileUpload" />
                    </label>
                    <BaseButton
                      type="button"
                      size="sm"
                      :variant="showPreview ? 'accent' : 'secondary'"
                      :aria-pressed="showPreview"
                      @click="showPreview = !showPreview"
                    >
                      {{ showPreview ? 'Ocultar preview' : 'Vista previa' }}
                    </BaseButton>
                  </div>
                </div>
                <div :class="showPreview ? 'grid grid-cols-1 lg:grid-cols-2 gap-4' : ''">
                  <textarea
                    v-model="customMarkdown"
                    rows="14"
                    placeholder="# Contrato de prestacion de servicios&#10;&#10;Pega o escribe tu contrato en formato Markdown..."
                    class="w-full px-4 py-3 border border-input-border rounded-xl text-sm font-mono leading-relaxed
                           bg-input-bg text-input-text placeholder:text-text-subtle
                           focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none resize-y"
                  ></textarea>
                  <div
                    v-if="showPreview"
                    class="border border-border-default rounded-xl bg-surface overflow-y-auto"
                    style="min-height: 20rem; max-height: 36rem;"
                  >
                    <div class="px-3 py-2 border-b border-border-muted bg-surface-raised rounded-t-xl">
                      <span class="text-xs font-medium text-text-muted uppercase tracking-wide">Vista previa</span>
                    </div>
                    <div
                      v-if="customMarkdown.trim()"
                      class="markdown-preview px-5 py-4 text-text-default"
                      v-html="previewHtml"
                    ></div>
                    <div v-else class="flex items-center justify-center h-48 text-sm text-text-subtle">
                      Escribe markdown para ver la vista previa...
                    </div>
                  </div>
                </div>
              </div>

              <!-- Contract date (also for custom) -->
              <fieldset>
                <legend class="text-sm font-semibold text-text-brand mb-3">Datos del contrato</legend>
                <BaseFormField
                  label="Fecha del contrato"
                  required
                  size="sm"
                  :error="formErrors.contract_date"
                >
                    <BaseInput v-model="form.contract_date" type="date" size="sm" />
                </BaseFormField>
              </fieldset>
            </template>

            </fieldset>
          </form>
    </div>
    <template #footer>
      <p v-if="saveError?.message" role="alert" class="mb-3 text-sm text-danger-strong">{{ saveError.message }}</p>
      <BaseModalActions>
        <BaseButton variant="ghost" size="md" :disabled="saving" :disabled-reason="t('serviceContract.contractSaving')" @click="!saving && $emit('cancel')">
          Cancelar
        </BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          size="md"
          :loading="saving"
          :disabled="saving || serviceSettingsBlocked || (contractSource === 'custom' && !customMarkdown.trim())"
          :disabled-reason="saving ? t('serviceContract.contractSaving') : serviceSettingsBlocked ? t('serviceContract.loadError') : ''"
        >
          {{ saving ? 'Generando...' : submitLabel }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { useId, ref, watch, computed, onBeforeUnmount } from 'vue';
import DOMPurify from 'dompurify';
import { CONTRACT_LOCKED_STATUSES, CONTRACT_VARIANTS, SERVICE_CONTRACT_FIELDS } from '~/stores/proposals_constants';
import ServiceContractTermField from './ServiceContractTermField.vue';
import { serviceTermNumber, validServiceContractSettings } from '~/utils/serviceContractTerms';

const { parseMarkdown } = useMarkdownPreview();
const { t } = useI18n();

const props = defineProps({
  visible: { type: Boolean, default: false },
  proposal: { type: Object, default: () => ({}) },
  initialParams: { type: Object, default: () => ({}) },
  isEditing: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  saveError: { type: Object, default: null },
  // Document being generated or edited: 'combined', 'product' or 'service'.
  variant: { type: String, default: 'combined' },
});

const emit = defineEmits(['confirm', 'cancel']);

const variantSpec = computed(() => CONTRACT_VARIANTS[props.variant] || CONTRACT_VARIANTS.combined);
// Only a sent or viewed proposal enters negotiation from this modal.
const submitLabel = computed(() => {
  if (props.isEditing) return 'Actualizar contrato';
  return CONTRACT_LOCKED_STATUSES.includes(props.proposal?.status)
    ? 'Generar contrato y negociar'
    : 'Generar contrato';
});

const proposalStore = useProposalStore();
const companyDefaults = ref({});
const contractSource = ref('default');
const customMarkdown = ref('');
const showPreview = ref(false);
const formErrors = ref({});
watch(() => props.saveError, error => {
  const fields = error?.fieldErrors || {};
  formErrors.value = {
    ...fields,
    customMarkdown: fields[variantSpec.value.customKey] || '',
  };
});
const loadingDefaults = ref(false);
const formRevision = ref(0);
const serviceSettingsReady = computed(() => validServiceContractSettings(companyDefaults.value.service_contract_settings));
const serviceSettingsBlocked = computed(() => props.variant === 'service' && contractSource.value === 'default'
  && (loadingDefaults.value || !serviceSettingsReady.value));

const debouncedMarkdown = ref('');
let debounceTimer = null;
onBeforeUnmount(() => { clearTimeout(debounceTimer); });
watch(customMarkdown, (val) => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => { debouncedMarkdown.value = val; }, 200);
}, { immediate: true });

const previewHtml = computed(() => DOMPurify.sanitize(parseMarkdown(debouncedMarkdown.value)));

const form = ref({
  contractor_full_name: '',
  contractor_nit: '',
  contractor_cedula: '',
  contractor_email: '',
  bank_name: '',
  bank_account_type: 'Ahorros',
  bank_account_number: '',
  contract_city: 'Medellín',
  client_full_name: '',
  client_cedula: '',
  client_email: '',
  contract_date: new Date().toISOString().slice(0, 10),
  service_initial_term: '',
  service_renewal_notice_days: '',
  service_termination_notice_days: '',
});

async function loadDefaults() {
  loadingDefaults.value = true;
  try {
    const result = await proposalStore.fetchCompanySettings();
    companyDefaults.value = result.success ? result.data : {};
  } catch {
    companyDefaults.value = {};
  } finally {
    loadingDefaults.value = false;
  }
}

function fillServiceDefaults() {
  if (!serviceSettingsReady.value) return;
  for (const { key, defaultKey } of SERVICE_CONTRACT_FIELDS) {
    if (form.value[key] === '' || form.value[key] == null) {
      form.value[key] = companyDefaults.value.service_contract_settings[defaultKey];
    }
  }
}

async function retryDefaults() {
  await loadDefaults();
  for (const key of Object.keys(form.value)) {
    if (!form.value[key] && companyDefaults.value[key]) form.value[key] = companyDefaults.value[key];
  }
  fillServiceDefaults();
}

function resetForm() {
  formRevision.value += 1;
  formErrors.value = {};
  const defaults = companyDefaults.value;
  const existing = props.initialParams || {};
  const p = props.proposal || {};

  contractSource.value = existing[variantSpec.value.sourceKey] || 'default';
  customMarkdown.value = existing[variantSpec.value.customKey] || '';

  form.value = {
    contractor_full_name: existing.contractor_full_name || defaults.contractor_full_name || '',
    contractor_nit: existing.contractor_nit || defaults.contractor_nit || '',
    contractor_cedula: existing.contractor_cedula || defaults.contractor_cedula || '',
    contractor_email: existing.contractor_email || defaults.contractor_email || '',
    bank_name: existing.bank_name || defaults.bank_name || '',
    bank_account_type: existing.bank_account_type || defaults.bank_account_type || 'Ahorros',
    bank_account_number: existing.bank_account_number || defaults.bank_account_number || '',
    contract_city: existing.contract_city || defaults.contract_city || 'Medellín',
    client_full_name: existing.client_full_name || p.client_name || '',
    client_cedula: existing.client_cedula || '',
    client_email: existing.client_email || p.client_email || '',
    contract_date: existing.contract_date || new Date().toISOString().slice(0, 10),
    ...Object.fromEntries(SERVICE_CONTRACT_FIELDS.map(({ key }) => [key, existing[key] || ''])),
  };
  fillServiceDefaults();
}

watch(() => props.visible, async (val) => {
  if (val) {
    if (props.variant === 'service' || !companyDefaults.value.contractor_full_name) {
      await loadDefaults();
    }
    resetForm();
  }
});

function handleFileUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    customMarkdown.value = e.target?.result || '';
  };
  reader.readAsText(file);
}

function validate() {
  if (serviceSettingsBlocked.value) return false;
  const errors = {};
  if (contractSource.value === 'default') {
    const required = [
      ['contractor_full_name', 'Nombre completo del contratista'],
      ['contractor_email', 'Email del contratista'],
      ['contract_city', 'Ciudad del contrato'],
      ['bank_name', 'Banco'],
      ['bank_account_number', 'Número de cuenta'],
      ['client_full_name', 'Nombre completo del cliente'],
      ['client_cedula', 'Cédula/NIT del cliente'],
      ['client_email', 'Email del cliente'],
      ['contract_date', 'Fecha del contrato'],
    ];
    for (const [field, label] of required) {
      if (!form.value[field]?.toString().trim()) {
        errors[field] = `${label} es obligatorio`;
      }
    }
    // The contract identifies EL CONTRATISTA by whichever document is on
    // file, so either one satisfies the requirement — but not neither.
    const nit = form.value.contractor_nit?.toString().trim();
    const cedula = form.value.contractor_cedula?.toString().trim();
    if (!nit && !cedula) {
      errors.contractor_identity = 'Indica el NIT o la cédula del contratista';
    }
    if (props.variant === 'service') {
      for (const { key, duration } of SERVICE_CONTRACT_FIELDS) {
        const value = form.value[key];
        const max = duration ? 100 : 60;
        if (!value?.toString().trim()) {
          errors[key] = t('serviceContract.requiredTerm');
        } else if (typeof value === 'number' && serviceTermNumber(value) === null) {
          errors[key] = t('serviceContract.invalidNumber');
        } else if (typeof value === 'string' && [...value].length > max) {
          errors[key] = t('serviceContract.termTooLong', { max });
        }
      }
    }
  } else {
    if (!customMarkdown.value.trim()) {
      errors.customMarkdown = 'El contenido del contrato es obligatorio';
    }
    if (!form.value.contract_date?.trim()) {
      errors.contract_date = 'Fecha del contrato es obligatoria';
    }
  }
  formErrors.value = errors;
  return Object.keys(errors).length === 0;
}

// The backend merges these keys over the saved parameters, so each document
// only sends its own source and text; the service terms travel with the
// service contract only.
function handleSubmit() {
  if (props.saving || !validate()) return;
  const { sourceKey, customKey } = variantSpec.value;
  if (contractSource.value === 'custom') {
    emit('confirm', {
      [sourceKey]: 'custom',
      [customKey]: customMarkdown.value,
      contract_date: form.value.contract_date,
    });
    return;
  }
  const serviceKeys = SERVICE_CONTRACT_FIELDS.map(({ key }) => key);
  const params = Object.fromEntries(
    Object.entries(form.value).filter(([key]) => props.variant === 'service' || !serviceKeys.includes(key)),
  );
  emit('confirm', { [sourceKey]: 'default', ...params });
}

const modalFormId = useId();
</script>
