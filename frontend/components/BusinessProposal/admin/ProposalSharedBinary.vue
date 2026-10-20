<script setup>
import { ref, computed } from 'vue';
import { create_request } from '~/stores/services/request_http';
const props = defineProps({ source: { type: Object, required: true } });
const emit = defineEmits(['updated']);
const { locale } = useI18n();
const en = computed(() => locale.value.startsWith('en'));
const file = ref(null);
const busy = ref(false);
const error = ref('');
const version = ref(props.source.source_hash);
const saved = ref(false);
async function save() {
  if (!file.value || busy.value) return;
  const body = new FormData();
  body.append('source_hash', version.value);
  body.append('file', file.value);
  busy.value = true;
  error.value = '';
  saved.value = false;
  try {
    const result = await create_request(`documents/${props.source.document_id}/proposal-source/`, body);
    version.value = result.data.document.source_hash;
    saved.value = true;
    file.value = null;
    emit('updated');
  } catch (failure) {
    error.value = failure.response?.status === 409
      ? (en.value ? 'The source changed. Your file has been kept; review the current revision before retrying.' : 'La fuente cambió. Conservamos tu archivo; revisa la versión actual antes de reintentar.')
      : (en.value ? 'Could not save the draft. Your file has been kept.' : 'No se pudo guardar el borrador. Conservamos tu archivo.');
  } finally { busy.value = false; }
}
</script>

<template>
  <section v-if="source.can_replace_binary" class="space-y-3 rounded-xl border border-border-default bg-surface p-4" data-testid="shared-binary-editor">
    <h3 class="font-medium text-text-default">{{ en ? 'Replace draft attachment' : 'Sustituir adjunto en borrador' }}</h3>
    <p class="text-sm text-text-muted">{{ en ? 'The approved file stays unchanged until you review and confirm a new package.' : 'El archivo aprobado se conserva hasta revisar y confirmar un nuevo paquete.' }}</p>
    <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg" :aria-label="en ? 'New attachment' : 'Nuevo adjunto'" data-testid="shared-binary-file" class="block w-full min-w-0 text-sm text-text-default" @change="file = $event.target.files?.[0] || null; saved = false" />
    <p v-if="error" role="alert" class="text-sm text-danger-strong">{{ error }}</p>
    <p v-if="saved" role="status" class="text-sm text-text-default">{{ en ? 'Draft saved. Review the new package to make it current.' : 'Borrador guardado. Revisa el nuevo paquete para hacerlo vigente.' }}</p>
    <BaseButton type="button" variant="secondary" size="sm" :loading="busy" :disabled="!file || busy" :disabled-reason="en ? 'Choose an attachment first.' : 'Selecciona primero un adjunto.'" data-testid="shared-binary-save" @click="save">{{ en ? 'Save draft' : 'Guardar borrador' }}</BaseButton>
  </section>
</template>
