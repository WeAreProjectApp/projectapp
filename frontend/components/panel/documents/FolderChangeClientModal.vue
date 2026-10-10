<template>
  <BaseModal
    :model-value="open"
    kind="form"
    initial-focus="[data-testid='folder-change-client-picker']"
    @update:model-value="$emit('close')"
  >
    <div class="p-6 space-y-5" data-testid="folder-change-client-modal">
      <div>
        <h3 class="text-base font-semibold text-text-default">
          Cambiar el cliente de "{{ folder?.name }}"
        </h3>
        <p class="text-xs text-text-muted mt-0.5">
          La carpeta tiene contenido: elige a quién pasa y qué hacer con lo que guarda.
        </p>
      </div>

      <div class="space-y-1.5">
        <label class="block text-xs font-medium text-text-muted">Nuevo cliente</label>
        <ClientAutocomplete
          v-model="clientId"
          :initial-label="clientName"
          test-id="folder-change-client-picker"
          @select="onClientSelect"
        />
      </div>

      <p v-if="isLoadingPreview" class="text-xs text-text-muted">
        Calculando a qué afecta…
      </p>

      <div v-if="preview" class="space-y-3" data-testid="folder-change-client-preview">
        <div class="rounded-xl border border-border-muted p-3">
          <p class="text-xs font-semibold text-text-default mb-1.5">
            Pasan al nuevo cliente ({{ preview.totals.folders + preview.totals.documents }})
          </p>
          <ul class="text-xs text-text-muted space-y-0.5">
            <li v-for="row in preview.folders_move" :key="`f-${row.id}`">
              📁 {{ row.name }}
            </li>
            <li v-for="row in preview.documents_move" :key="`d-${row.id}`">
              📄 {{ row.title }}
            </li>
            <li v-if="!preview.totals.folders && !preview.totals.documents">
              Nada: la carpeta cambia sola.
            </li>
          </ul>
        </div>

        <div
          v-if="preview.totals.blocked"
          class="rounded-xl border border-warning-soft bg-warning-soft p-3"
          data-testid="folder-change-client-blocked"
        >
          <p class="text-xs font-semibold text-warning-strong mb-1.5">
            No se tocan — cuentas de cobro emitidas ({{ preview.totals.blocked }})
          </p>
          <ul class="text-xs text-text-muted space-y-0.5">
            <li v-for="row in preview.documents_blocked" :key="row.id">
              {{ row.title }}<span v-if="row.reason"> · {{ row.reason }}</span>
            </li>
          </ul>
        </div>

        <div
          v-if="preview.totals.foreign || preview.totals.foreign_folders"
          class="rounded-xl border border-border-muted p-3"
          data-testid="folder-change-client-foreign"
        >
          <p class="text-xs font-semibold text-text-default mb-1.5">
            Conservan su cliente ({{ preview.totals.foreign + preview.totals.foreign_folders }})
          </p>
          <ul class="text-xs text-text-muted space-y-0.5">
            <li v-for="row in preview.folders_foreign" :key="`ff-${row.id}`">
              📁 {{ row.name }}<span v-if="row.reason"> · {{ row.reason }}</span>
            </li>
            <li v-for="row in preview.documents_foreign" :key="`df-${row.id}`">
              📄 {{ row.title }}<span v-if="row.reason"> · {{ row.reason }}</span>
            </li>
          </ul>
        </div>

        <div class="space-y-1.5">
          <label class="block text-xs font-medium text-text-muted">
            ¿Qué pasa con el contenido?
          </label>
          <BaseSegmented
            :model-value="mode"
            :options="modeOptions"
            size="sm"
            data-testid="folder-change-client-mode"
            @update:model-value="mode = $event"
          />
        </div>
      </div>

      <BaseAlert v-if="errorMessage" variant="danger" data-testid="folder-change-client-error">
        {{ errorMessage }}
      </BaseAlert>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton
          variant="ghost"
          data-testid="folder-change-client-cancel"
          @click="$emit('close')"
        >
          Cancelar
        </BaseButton>
        <BaseButton
          variant="primary"
          :disabled="!canConfirm"
          :loading="folderStore.isUpdating"
          data-testid="folder-change-client-confirm"
          @click="confirmChange"
        >
          Cambiar cliente
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';

/**
 * El camino guiado para reasignar una carpeta con contenido — el único, porque
 * el PATCH plano responde 409 `folder_has_content`. Mismo criterio que el
 * cambio de cliente de un proyecto: se elige el destino, se lee el impacto
 * completo (incluido lo que NO se va a tocar), se elige el modo CADA vez —sin
 * preselección— y se confirma. Un 409 significa que el contenido se movió con
 * el diálogo abierto: se recarga el plan en vez de adivinar.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  folder: { type: Object, default: null },
  /** Cliente que el formulario de la carpeta ya venía proponiendo. */
  initialClientProfileId: { type: Number, default: null },
});

const emit = defineEmits(['close', 'changed']);

const folderStore = useDocumentFolderStore();
const notify = usePanelNotify();

const clientId = ref(null);
const clientName = ref('');
const preview = ref(null);
const mode = ref('');
const isLoadingPreview = ref(false);
const errorMessage = ref('');

const modeOptions = [
  { value: 'propagate', label: 'Pasa también el contenido' },
  { value: 'folder_only', label: 'Sólo la carpeta' },
];

const canConfirm = computed(() => Boolean(
  preview.value && mode.value && !folderStore.isUpdating && !isLoadingPreview.value,
));

watch(() => props.open, (open) => {
  if (!open) return;
  preview.value = null;
  mode.value = '';
  errorMessage.value = '';
  clientName.value = '';
  clientId.value = props.initialClientProfileId ?? null;
  if (clientId.value != null) loadPreview();
}, { immediate: true });

function onClientSelect(client) {
  clientName.value = client?.name || '';
}

watch(clientId, (id, previous) => {
  if (id === previous) return;
  preview.value = null;
  mode.value = '';
  errorMessage.value = '';
  if (id != null) loadPreview();
});

async function loadPreview() {
  isLoadingPreview.value = true;
  const result = await folderStore.previewChangeClient(props.folder.id, clientId.value);
  isLoadingPreview.value = false;
  if (!result.success) {
    errorMessage.value = result.message;
    return;
  }
  preview.value = result.data;
}

async function confirmChange() {
  errorMessage.value = '';
  const result = await folderStore.changeClient(props.folder.id, {
    client_profile_id: clientId.value,
    mode: mode.value,
    document_ids: preview.value.document_ids,
    folder_ids: preview.value.folder_ids,
  });
  if (result.success) {
    const { moved, skipped } = result.data;
    const parts = [];
    const movedTotal = (moved?.folders || 0) + (moved?.documents || 0);
    const untouched = (skipped?.blocked || 0) + (skipped?.foreign || 0);
    if (movedTotal) parts.push(`${movedTotal} pasaron al nuevo cliente`);
    if (untouched) parts.push(`${untouched} conservaron el suyo`);
    notify.success({
      title: `"${props.folder.name}" ahora es de ${clientName.value || 'su nuevo cliente'}`,
      detail: parts.join(' · '),
    });
    emit('changed', result.data);
    return;
  }
  if (result.code === 'records_not_found' || result.code === 'records_changed') {
    errorMessage.value = 'El contenido de la carpeta cambió mientras confirmabas. Revisa el nuevo impacto.';
    mode.value = '';
    await loadPreview();
    return;
  }
  errorMessage.value = result.message;
}
</script>
