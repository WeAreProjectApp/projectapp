<template>
  <BaseModal :model-value="visible" kind="form" @update:model-value="(open) => { if (!open) $emit('cancel') }">
    <div class="flex flex-col">
          <div class="sticky top-0 bg-surface border-b border-border-muted px-6 py-4 rounded-t-2xl z-10">
            <h2 class="text-lg font-semibold text-text-default">Acuerdo de Confidencialidad</h2>
            <p class="text-xs text-text-muted mt-0.5">
              Datos para rellenar la plantilla. Los campos vacíos quedarán como
              <span class="font-mono">_______________</span> en el PDF.
            </p>
          </div>

          <form class="px-6 py-5 space-y-6" @submit.prevent="handleSave">
            <section>
              <h3 class="text-xs font-semibold uppercase tracking-wide text-text-brand mb-3">
                Cliente
              </h3>
              <BaseFormRow :cols="2" :gap="3" at="sm">
                <BaseFormField
                  label="Razón social / Nombre"
                  for="confidentiality-client-name"
                  size="sm"
                >
                  <BaseInput
                    id="confidentiality-client-name"
                    v-model="form.client_full_name"
                    type="text"
                    size="sm"
                  />
                </BaseFormField>
                <BaseFormField label="NIT / C.C." for="confidentiality-client-id" size="sm">
                  <BaseInput id="confidentiality-client-id" v-model="form.client_cedula" type="text" size="sm" />
                </BaseFormField>
                <BaseFormField
                  label="Representante legal"
                  for="confidentiality-client-representative"
                  size="sm"
                >
                  <BaseInput
                    id="confidentiality-client-representative"
                    v-model="form.client_legal_representative"
                    type="text"
                    size="sm"
                  />
                </BaseFormField>
                <BaseFormField label="Correo electrónico" for="confidentiality-client-email" size="sm">
                  <BaseInput id="confidentiality-client-email" v-model="form.client_email" type="email" size="sm" />
                </BaseFormField>
              </BaseFormRow>
            </section>

            <section>
              <h3 class="text-xs font-semibold uppercase tracking-wide text-text-brand mb-3">
                Consultor (Project App)
              </h3>
              <BaseFormRow :cols="2" :gap="3" at="sm">
                <BaseFormField
                  label="Razón social / Nombre"
                  for="confidentiality-contractor-name"
                  size="sm"
                >
                  <BaseInput
                    id="confidentiality-contractor-name"
                    v-model="form.contractor_full_name"
                    type="text"
                    size="sm"
                  />
                </BaseFormField>
                <BaseFormField label="NIT" for="confidentiality-contractor-nit" size="sm">
                  <BaseInput id="confidentiality-contractor-nit" v-model="form.contractor_nit" type="text" size="sm" />
                </BaseFormField>
                <BaseFormField label="Cédula" for="confidentiality-contractor-id" size="sm">
                  <BaseInput id="confidentiality-contractor-id" v-model="form.contractor_cedula" type="text" size="sm" />
                </BaseFormField>
                <BaseFormField label="Correo electrónico" for="confidentiality-contractor-email" size="sm">
                  <BaseInput id="confidentiality-contractor-email" v-model="form.contractor_email" type="email" size="sm" />
                </BaseFormField>
                <template #help>
                  <span>Indica NIT o cédula. El NIT tiene prioridad en el acuerdo.</span>
                  <span v-if="idError" class="mt-1 block text-danger-strong" role="alert">{{ idError }}</span>
                </template>
              </BaseFormRow>
            </section>

            <section>
              <h3 class="text-xs font-semibold uppercase tracking-wide text-text-brand mb-3">
                Datos del acuerdo
              </h3>
              <div class="space-y-3">
                <BaseFormRow :cols="2" :gap="3" at="sm">
                  <BaseFormField label="Ciudad" for="confidentiality-city" size="sm">
                    <BaseInput id="confidentiality-city" v-model="form.contract_city" type="text" size="sm" />
                  </BaseFormField>
                  <BaseFormField
                    label="Cláusula penal (valor)"
                    for="confidentiality-penal-clause"
                    size="sm"
                  >
                    <BaseInput
                      id="confidentiality-penal-clause"
                      v-model="form.penal_clause_value"
                      type="text"
                      size="sm"
                    />
                  </BaseFormField>
                </BaseFormRow>
                <BaseFormRow :cols="3" :gap="3" at="sm">
                  <BaseFormField label="Día" for="confidentiality-day" size="sm">
                    <BaseInput id="confidentiality-day" v-model="form.contract_day" type="text" placeholder="Ej: 16" size="sm" />
                  </BaseFormField>
                  <BaseFormField label="Mes" for="confidentiality-month" size="sm">
                    <BaseInput id="confidentiality-month" v-model="form.contract_month" type="text" placeholder="Ej: abril" size="sm" />
                  </BaseFormField>
                  <BaseFormField label="Año" for="confidentiality-year" size="sm">
                    <BaseInput id="confidentiality-year" v-model="form.contract_year" type="text" placeholder="Ej: 2026" size="sm" />
                  </BaseFormField>
                </BaseFormRow>
              </div>
            </section>

            <p v-if="error" class="text-xs text-danger-strong">{{ error }}</p>
          </form>

    </div>
    <template #footer>
      <BaseModalActions>
        <div class="flex flex-col-reverse gap-2 panel-portrait:flex-row panel-portrait:items-center">
          <BaseButton variant="ghost" size="md" @click="$emit('cancel')">Cancelar</BaseButton>
          <BaseButton variant="primary" size="md" :loading="saving" @click="handleSave">
            <BaseActionIcon v-if="!saving" action="generate" />
            {{ saving ? 'Generando…' : 'Guardar y generar PDF' }}
          </BaseButton>
        </div>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch } from 'vue';
import BaseModal from '~/components/base/BaseModal.vue';
import { useDiagnosticsStore } from '~/stores/diagnostics';

const props = defineProps({
  visible: { type: Boolean, default: false },
  diagnostic: { type: Object, default: () => ({}) },
});

const emit = defineEmits(['cancel', 'saved']);

const store = useDiagnosticsStore();

const DEFAULTS = {
  contractor_full_name: 'Project App SAS',
  contract_city: 'Medellín',
  penal_clause_value: 'CINCUENTA SALARIOS MÍNIMOS MENSUALES LEGALES VIGENTES (50 SMMLV)',
  contractor_email: 'team@projectapp.co',
};

const EMPTY_FORM = {
  client_full_name: '',
  client_cedula: '',
  client_legal_representative: '',
  client_email: '',
  contractor_full_name: '',
  contractor_nit: '',
  contractor_cedula: '',
  contractor_email: '',
  contract_city: '',
  contract_day: '',
  contract_month: '',
  contract_year: '',
  penal_clause_value: '',
};

const form = ref({ ...EMPTY_FORM });
const saving = ref(false);
const error = ref('');
const idError = ref('');

watch(
  () => props.visible,
  (val) => {
    if (!val) return;
    error.value = '';
    idError.value = '';
    const stored = props.diagnostic?.confidentiality_params || {};
    const clientName = props.diagnostic?.client?.name || '';
    const clientEmail = props.diagnostic?.client?.email || '';
    form.value = {
      ...EMPTY_FORM,
      ...DEFAULTS,
      client_full_name: stored.client_full_name || clientName,
      client_email: stored.client_email || clientEmail,
      ...stored,
    };
  },
  { immediate: true },
);

function validateIdentity() {
  // The NDA names EL CONSULTOR by whichever document is on file; every other
  // field may stay blank so the acuerdo can be printed and filled by hand.
  const hasId = (form.value.contractor_nit || '').trim()
    || (form.value.contractor_cedula || '').trim();
  idError.value = hasId ? '' : 'Indica el NIT o la cédula del consultor';
  return !idError.value;
}

async function handleSave() {
  if (!validateIdentity()) return;
  saving.value = true;
  error.value = '';
  const payload = {};
  Object.keys(EMPTY_FORM).forEach((key) => {
    const value = (form.value[key] || '').trim();
    if (value) payload[key] = value;
  });
  const result = await store.updateConfidentialityParams(props.diagnostic.id, payload);
  saving.value = false;
  if (result.success) {
    emit('saved', result.data);
  } else {
    error.value = result.error || 'No se pudo guardar.';
  }
}
</script>
