<template>
  <div>
    <div class="mb-6 flex flex-col items-start gap-3 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
      <div class="min-w-0">
        <h1 class="text-2xl font-light text-text-default">Tarjetas QR</h1>
        <p class="text-sm text-text-subtle mt-1">
          Generá códigos QR con un link corto y cambiá su destino cuando quieras, sin reimprimir nada.
        </p>
      </div>
      <BaseButton variant="primary" size="sm" data-testid="qr-card-new" @click="openCreateModal">
        Nueva tarjeta
      </BaseButton>
    </div>

    <div v-if="store.isLoading && store.cards.length === 0" class="text-center py-16 text-text-subtle text-sm">
      Cargando tarjetas...
    </div>

    <BaseEmptyState
      v-else-if="store.cards.length === 0"
      title="Sin tarjetas todavía"
      description="Creá tu primera tarjeta QR para generar un link corto."
    />

    <BaseExploratoryList
      v-else
      :columns="qrCardColumns"
      :rows="store.cards"
      caption="Tarjetas QR y sus destinos"
      card-test-id-prefix="qr-card-row"
      table-min-width="58rem"
      row-actions-layout="menu-start"
    >
      <template #cell-short_link="{ row: card }">
        <div class="flex min-w-0 items-center gap-2">
          <code class="min-w-0 break-all rounded bg-surface-muted px-2 py-1 text-xs">{{ shortLinkFor(card) }}</code>
          <BaseActionButton
            action="copy"
            :label="copyFeedback(card).label || 'Copiar link'"
            :status-label="copyFeedback(card).label"
            :status-tone="copyFeedback(card).tone"
            size="sm"
            @click="copyLink(card)"
          />
        </div>
      </template>

      <template #cell-destination="{ row: card }">
        <span v-if="card.destination_type === 'linktree' && card.linktree_handle">
          Linktree: @{{ card.linktree_handle }}
        </span>
        <span v-else-if="card.destination_type === 'linktree'" class="italic text-text-subtle">
          Linktree sin asignar
        </span>
        <span v-else-if="card.destination_url" class="break-all">{{ card.destination_url }}</span>
        <span v-else class="italic text-text-subtle">Sin configurar</span>
      </template>

      <template #cell-is_active="{ row: card }">
        <BaseToggle
          :model-value="card.is_active"
          :aria-label="`Activar ${card.name}`"
          :data-testid="`qr-card-toggle-${card.id}`"
          @update:model-value="(value) => onToggleActive(card, value)"
        />
      </template>

      <template #row-actions="{ row: card }">
        <BaseActionButton
          action="more"
          class="h-11 w-11 shrink-0"
          :label="`Acciones de ${card.name}`"
          :data-testid="`qr-card-actions-${card.id}`"
          @click.stop="actionsRow = card"
        />
      </template>
    </BaseExploratoryList>

    <BaseRowActionsModal
      :open="actionsRow !== null"
      :title="actionsRow?.name || ''"
      :items="actionsRow ? qrCardActionItems(actionsRow) : []"
      testid="qr-card-actions-modal"
      @close="actionsRow = null"
    />

    <!-- Create / edit modal -->
    <BaseModal v-model="formModal.open" kind="form" padding="md">
      <form :id="modalFormId" novalidate data-testid="qr-card-form" @submit.prevent="onSubmit">
        <div class="space-y-4 px-6 py-5">
          <h3 class="text-lg font-bold text-text-default">
            {{ formModal.editingId ? 'Editar tarjeta' : 'Nueva tarjeta' }}
          </h3>

          <BaseFormField v-slot="{ invalid, errorId }" label="Nombre" for="qr-card-name" required :error="formErrors.name">
            <BaseInput
              id="qr-card-name"
              v-model="formModal.name"
              data-testid="qr-card-name-input"
              :error="invalid"
              :aria-describedby="errorId"
              @update:model-value="formErrors.name = ''"
            />
          </BaseFormField>

          <BaseFormField label="Tipo de destino" for="qr-card-destination-type">
            <BaseSegmented
              id="qr-card-destination-type"
              v-model="formModal.destinationType"
              data-testid="qr-card-destination-type"
              :options="[
                { value: 'url', label: 'URL directa' },
                { value: 'linktree', label: 'Linktree' },
              ]"
            />
          </BaseFormField>

          <BaseFormField
            v-if="formModal.destinationType === 'url'"
            label="Link de destino"
            for="qr-card-destination"
            :error="formErrors.destination_url"
          >
            <BaseInput
              id="qr-card-destination"
              v-model="formModal.destinationUrl"
              placeholder="https://..."
              data-testid="qr-card-destination-input"
            />
          </BaseFormField>

          <BaseFormField
            v-else
            label="Linktree de destino"
            for="qr-card-linktree"
            hint="Creá y personalizá linktrees en el módulo Linktrees."
            :error="formErrors.linktree"
          >
            <BaseSelect
              id="qr-card-linktree"
              v-model="formModal.linktreeId"
              data-testid="qr-card-linktree-select"
              :options="linktreeOptions"
            />
          </BaseFormField>
        </div>

      </form>
      <template #footer>
        <BaseModalActions>
          <BaseButton type="button" variant="ghost" size="sm" @click="formModal.open = false">Cancelar</BaseButton>
          <BaseButton type="submit" :form="modalFormId" variant="primary" size="sm" :loading="store.isUpdating" data-testid="qr-card-save">
            Guardar
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>

    <DownloadQrModal v-model="downloadModal.open" :card="downloadModal.card" />

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
import { useId, computed, onMounted, reactive, ref } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue';
import BaseRowActionsModal from '~/components/base/BaseRowActionsModal.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import DownloadQrModal from '~/components/panel/qr-cards/DownloadQrModal.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { useQrCardsStore } from '~/stores/qr_cards';
import { useLinktreesStore } from '~/stores/linktrees';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const store = useQrCardsStore();
const linktreesStore = useLinktreesStore();
const notify = usePanelNotify();
const clipboardFeedback = useClipboardFeedback();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();

const formModal = reactive({
  open: false, editingId: null, name: '', destinationUrl: '',
  destinationType: 'url', linktreeId: '',
});
const formErrors = reactive({ name: '', destination_url: '', linktree: '' });
const downloadModal = reactive({ open: false, card: null });
const actionsRow = ref(null);

const qrCardColumns = [
  { key: 'name', label: 'Nombre', mobile: 'primary' },
  { key: 'short_link', label: 'Link corto', mobile: 'secondary' },
  { key: 'destination', label: 'Destino', mobile: 'secondary', cardClass: '[overflow-wrap:anywhere]' },
  { key: 'is_active', label: 'Activa', mobile: 'meta' },
];

const linktreeOptions = computed(() => [
  { value: '', label: 'Sin asignar' },
  ...linktreesStore.linktrees.map((tree) => ({
    value: tree.id,
    label: `${tree.name} (@${tree.handle})`,
  })),
]);

function qrCardActionItems(card) {
  return [
    {
      action: 'download',
      label: 'Descargar QR',
      testid: `qr-card-download-${card.id}`,
      onClick: () => openDownloadModal(card),
    },
    {
      action: 'edit',
      label: 'Editar',
      testid: `qr-card-edit-${card.id}`,
      onClick: () => openEditModal(card),
    },
    { divider: true },
    {
      action: 'delete',
      label: 'Eliminar',
      danger: true,
      testid: `qr-card-delete-${card.id}`,
      onClick: () => onDelete(card),
    },
  ];
}

onMounted(() => {
  store.fetchCards();
  linktreesStore.fetchLinktrees();
});

function shortLinkFor(card) {
  return `${window.location.origin}/t/${card.id}/`;
}

async function copyLink(card) {
  await clipboardFeedback.copyText({
    key: `qr-card-${card.id}`,
    text: shortLinkFor(card),
    successLabel: 'Copiado: link corto',
    errorLabel: 'No se pudo copiar el link',
    onError: () => notify.error({
      title: 'No se pudo copiar',
      detail: 'Copiá el link manualmente.',
    }),
  });
}

function copyFeedback(card) {
  return clipboardFeedback.feedbackFor(`qr-card-${card.id}`);
}

function openCreateModal() {
  formModal.editingId = null;
  formModal.name = '';
  formModal.destinationUrl = '';
  formModal.destinationType = 'url';
  formModal.linktreeId = '';
  formErrors.name = '';
  formErrors.destination_url = '';
  formErrors.linktree = '';
  formModal.open = true;
}

function openEditModal(card) {
  formModal.editingId = card.id;
  formModal.name = card.name;
  formModal.destinationUrl = card.destination_url;
  formModal.destinationType = card.destination_type || 'url';
  formModal.linktreeId = card.linktree || '';
  formErrors.name = '';
  formErrors.destination_url = '';
  formErrors.linktree = '';
  formModal.open = true;
}

function openDownloadModal(card) {
  downloadModal.card = card;
  downloadModal.open = true;
}

async function onToggleActive(card, value) {
  const result = await store.updateCard(card.id, { is_active: value });
  if (!result.success) {
    notify.error({ title: 'No se pudo actualizar la tarjeta' });
  }
}

async function onSubmit() {
  formErrors.name = '';
  formErrors.destination_url = '';
  formErrors.linktree = '';
  if (!formModal.name.trim()) {
    formErrors.name = 'Escribe el nombre de la tarjeta.';
    return;
  }
  const payload = {
    name: formModal.name,
    destination_url: formModal.destinationUrl,
    destination_type: formModal.destinationType,
    linktree: formModal.destinationType === 'linktree' ? formModal.linktreeId || null : null,
  };
  const result = formModal.editingId
    ? await store.updateCard(formModal.editingId, payload)
    : await store.createCard(payload);

  if (!result.success) {
    formErrors.name = result.errors?.name?.[0] || '';
    formErrors.destination_url = result.errors?.destination_url?.[0] || '';
    formErrors.linktree = result.errors?.linktree?.[0] || '';
    if (!result.errors) {
      notify.error({ title: 'No se pudo guardar la tarjeta' });
    }
    return;
  }
  formModal.open = false;
}

async function onDelete(card) {
  const confirmed = await requestConfirm({
    title: 'Eliminar tarjeta',
    message: `"${card.name}" se eliminará de forma permanente. Si el QR fue impreso o compartido, dejará de funcionar — el link corto ya no redirigirá a ningún destino. Esta acción no se puede deshacer.`,
    confirmText: 'Eliminar',
    variant: 'danger',
  });
  if (!confirmed) return;

  const result = await store.deleteCard(card.id);
  if (!result.success) {
    notify.error({ title: 'No se pudo eliminar la tarjeta' });
  }
}

const modalFormId = useId();
</script>
