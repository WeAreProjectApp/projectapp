<script setup>
import { ref, watch } from 'vue';
import StateHistoryModal from '~/components/panel/states/StateHistoryModal.vue';
import { useDocumentStateStore } from '~/stores/document_states';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  documentId: { type: [Number, String], required: true },
  readonly: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue', 'changed']);
const stateStore = useDocumentStateStore();
const editingEpisodeId = ref(null);
const correctedAt = ref('');
const correctionError = ref('');
const correctionBusy = ref(false);

watch(() => props.modelValue, async (open) => {
  if (!open) return;
  editingEpisodeId.value = null;
  correctionError.value = '';
  await stateStore.fetchHistory(props.documentId);
});

function updateOpen(value) {
  if (!value && correctionBusy.value) return;
  emit('update:modelValue', value);
}

function openCorrection(episode) {
  editingEpisodeId.value = episode.id;
  correctedAt.value = episode.opened_at ? episode.opened_at.slice(0, 16) : '';
  correctionError.value = '';
}

function cancelCorrection() {
  if (correctionBusy.value) return;
  editingEpisodeId.value = null;
  correctionError.value = '';
}

async function correctOpening(episode) {
  if (!correctedAt.value || correctionBusy.value) return;
  const parsed = new Date(correctedAt.value);
  if (Number.isNaN(parsed.getTime())) {
    correctionError.value = 'Ingresa una fecha y hora válidas.';
    return;
  }
  correctionBusy.value = true;
  correctionError.value = '';
  const result = await stateStore.correctEpisode(
    props.documentId,
    episode.id,
    parsed.toISOString(),
  );
  correctionBusy.value = false;
  if (!result.success) {
    correctionError.value = result.message;
    return;
  }
  await stateStore.fetchHistory(props.documentId);
  editingEpisodeId.value = null;
  emit('changed');
}
</script>

<template>
  <StateHistoryModal
    :model-value="modelValue"
    :history="stateStore.history"
    :loading="stateStore.isLoading"
    :busy="correctionBusy"
    title="Historial de estados"
    test-id="document-state-history"
    @update:model-value="updateOpen"
  >
    <template #episode-actions="{ episode }">
      <form
        v-if="editingEpisodeId === episode.id"
        class="mt-3 space-y-3 rounded-xl border border-border-default bg-surface-raised p-3"
        data-testid="document-state-correction-form"
        @submit.prevent="correctOpening(episode)"
      >
        <BaseFormField
          label="Fecha y hora real de apertura"
          hint="La corrección quedará registrada en el historial."
        >
          <BaseInput
            v-model="correctedAt"
            type="datetime-local"
            class="panel-portrait:max-w-[17rem]"
            :max="new Date().toISOString().slice(0, 16)"
            :disabled="correctionBusy"
          />
        </BaseFormField>
        <BaseAlert v-if="correctionError" variant="danger">{{ correctionError }}</BaseAlert>
        <div class="flex flex-wrap justify-end gap-2">
          <BaseButton type="button" variant="ghost" size="sm" :disabled="correctionBusy" @click="cancelCorrection">Cancelar</BaseButton>
          <BaseButton type="submit" variant="primary" size="sm" :loading="correctionBusy" :disabled="!correctedAt">Guardar corrección</BaseButton>
        </div>
      </form>
      <div v-else-if="!readonly" class="mt-3 flex justify-end">
        <BaseButton variant="ghost" size="sm" @click="openCorrection(episode)">Corregir apertura</BaseButton>
      </div>
    </template>
  </StateHistoryModal>
</template>
