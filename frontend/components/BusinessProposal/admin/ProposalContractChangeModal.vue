<script setup>
import { computed, ref, useId } from 'vue';
import { useProposalStore } from '~/stores/proposals';
import { usePanelNotify } from '~/composables/usePanelNotify';

const props = defineProps({
  proposal: { type: Object, required: true },
  modality: { type: String, default: '' },
  snapshotId: { type: Number, default: null },
});
const emit = defineEmits(['close', 'changed']);
const store = useProposalStore();
const notify = usePanelNotify();
const id = useId();
const note = ref('');
const busy = ref(false);
const error = ref('');
const fieldErrors = ref({});
const conflict = ref(false);
const resolveConflict = ref(false);
const preview = ref(null);
const terms = ref(Object.fromEntries(['service_initial_term', 'service_renewal_notice_days', 'service_termination_notice_days'].map(key => [key, String(props.proposal.contract_params?.[key] || '')])));
const termFields = [
  { key: 'service_initial_term', label: 'Plazo inicial del servicio' },
  { key: 'service_renewal_notice_days', label: 'Preaviso de renovación (días)' },
  { key: 'service_termination_notice_days', label: 'Preaviso de terminación (días)' },
];
const needsNote = computed(() => Boolean(props.snapshotId) || props.proposal.status !== 'negotiating');
const canPreview = computed(() => !busy.value && (!needsNote.value || note.value.trim()) && (!conflict.value || resolveConflict.value));
const actionLabels = { create: 'Crear desde plantilla', move: 'Trasladar sin cambiar el contenido', reuse: 'Conservar personalizado', restore: 'Restaurar copia guardada' };
const variantLabels = { combined: 'Contrato único', product: 'Contrato de producto', service: 'Contrato de servicio' };

function showError(err) {
  const data = err?.response?.data;
  error.value = data?.error || 'No se pudo completar la operación. Intenta de nuevo.';
  fieldErrors.value = data?.details?.contract_params || data?.details || {};
  if (data?.code === 'CUSTOM_CONTRACT_CONFLICT') conflict.value = true;
}

async function prepare() {
  if (!canPreview.value) return;
  busy.value = true;
  error.value = '';
  fieldErrors.value = {};
  const payload = props.snapshotId ? { snapshot_id: props.snapshotId, change_note: note.value } : {
    contract_modality: props.modality, change_note: note.value,
    ...(props.modality === 'split' ? { contract_params: Object.fromEntries(Object.entries(terms.value).map(([key, value]) => [key, /^\d+$/.test(value) ? Number(value) : value])) } : {}),
    ...(resolveConflict.value ? { conflict_resolution: 'use_origin' } : {}),
  };
  try { preview.value = await store.previewContractChange(props.proposal.id, payload); }
  catch (err) { showError(err); }
  finally { busy.value = false; }
}

async function confirm() {
  if (busy.value || !preview.value) return;
  busy.value = true;
  error.value = '';
  try {
    await store.confirmContractChange(props.proposal.id, preview.value.confirmation_id);
    notify.success(props.snapshotId ? 'Contratos restaurados.' : 'Modalidad de contrato actualizada.');
    emit('changed');
  } catch (err) {
    showError(err);
    // Require a fresh review after a rejected or expired confirmation.
    preview.value = null;
  } finally { busy.value = false; }
}

async function cancel() {
  if (busy.value) return;
  busy.value = true;
  try {
    if (preview.value) await store.cancelContractChange(props.proposal.id, preview.value.confirmation_id);
    emit('close');
  } catch (err) { showError(err); }
  finally { busy.value = false; }
}
</script>

<template>
  <BaseModal :model-value="true" kind="form" :close-on-esc="!busy" :close-on-backdrop="!busy" @close="cancel">
    <div class="space-y-4 p-5" data-testid="proposal-contract-change-modal">
      <h2 class="text-lg font-semibold text-text-default">{{ snapshotId ? 'Restaurar contratos anteriores' : 'Cambiar modalidad de contrato' }}</h2>
      <p class="text-sm text-text-muted">Se conservará una copia de los contratos actuales. El estado comercial, las firmas y los envíos anteriores se mantienen.</p>
      <p v-if="error" class="text-sm text-danger-strong" role="alert">{{ error }}</p>
      <template v-if="!preview">
        <div>
          <label :for="`${id}-note`" class="text-sm text-text-default">Nota de cambio {{ needsNote ? '(obligatoria)' : '(opcional)' }}</label>
          <BaseTextarea :id="`${id}-note`" v-model="note" maxlength="4000" :disabled="busy" disabled-reason="Espera a que termine la operación." data-testid="contract-change-note" />
          <p v-if="fieldErrors.change_note" class="text-sm text-danger-strong">{{ fieldErrors.change_note }}</p>
        </div>
        <BaseFormRow v-if="modality === 'split' && !snapshotId" :cols="3" :gap="4">
          <BaseFormField v-for="field in termFields" :key="field.key" :label="field.label" :for="`${id}-${field.key}`" label-policy="wrap">
            <BaseInput :id="`${id}-${field.key}`" v-model="terms[field.key]" :disabled="busy" disabled-reason="Espera a que termine la operación." :data-testid="`contract-change-${field.key}`" />
            <p v-if="fieldErrors[field.key]" class="text-sm text-danger-strong">{{ fieldErrors[field.key] }}</p>
          </BaseFormField>
        </BaseFormRow>
        <label v-if="conflict" class="flex items-start gap-2 text-sm text-text-default">
          <input v-model="resolveConflict" type="checkbox" :disabled="busy" data-testid="contract-change-resolve-conflict" />
          Conservar el personalizado del destino en la instantánea y trasladar el contrato de origen.
        </label>
      </template>
      <div v-else class="space-y-3" data-testid="contract-change-impact">
        <p class="text-sm text-text-default">{{ preview.impact.previous_modality === 'split' ? 'Producto y servicio' : 'Contrato único' }} → {{ preview.impact.contract_modality === 'split' ? 'Producto y servicio' : 'Contrato único' }}</p>
        <p v-if="preview.impact.arguments?.change_note" class="text-sm text-text-muted">Nota de cambio: {{ preview.impact.arguments.change_note }}</p>
        <ul class="space-y-2 text-sm text-text-default">
          <li v-for="contract in preview.impact.contracts" :key="contract.variant">{{ variantLabels[contract.variant] }}: {{ actionLabels[contract.action] }} · {{ contract.source === 'custom' ? 'Personalizado' : 'Plantilla' }}</li>
          <li v-for="contract in preview.impact.archive" :key="`archive-${contract.variant}`">Archivar {{ variantLabels[contract.variant] }} (documento {{ contract.document_id }})</li>
        </ul>
        <dl v-if="modality === 'split'" class="space-y-1 text-sm text-text-muted">
          <div v-for="field in termFields" :key="field.key"><dt class="inline">{{ field.label }}: </dt><dd class="inline">{{ preview.impact.contract_params[field.key] }}</dd></div>
        </dl>
        <p v-for="warning in preview.impact.warnings" :key="warning" class="text-sm text-text-muted">{{ warning }}</p>
        <p v-for="document in preview.impact.linked_documents" :key="document.document_id" class="text-sm text-text-muted">Documento anterior {{ document.document_id }}: {{ document.title }}{{ document.signed ? ' · firmado' : '' }}</p>
      </div>
    </div>
    <template #footer>
      <div class="flex flex-wrap justify-end gap-3">
        <BaseButton variant="secondary" :disabled="busy" disabled-reason="Espera a que termine la operación." data-testid="contract-change-cancel" @click="cancel">Cancelar</BaseButton>
        <BaseButton v-if="!preview" variant="primary" :disabled="!canPreview" disabled-reason="Completa la nota y resuelve el conflicto antes de revisar." data-testid="contract-change-preview" @click="prepare">Revisar cambio</BaseButton>
        <BaseButton v-else variant="primary" :disabled="busy" disabled-reason="Aplicando el cambio…" data-testid="contract-change-confirm" @click="confirm">Confirmar cambio</BaseButton>
      </div>
    </template>
  </BaseModal>
</template>
