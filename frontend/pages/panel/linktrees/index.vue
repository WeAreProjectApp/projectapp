<template>
  <div>
    <div class="mb-6 flex flex-col items-start gap-3 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
      <div class="min-w-0">
        <h1 class="text-2xl font-light text-text-default">Linktrees</h1>
        <p class="text-sm text-text-subtle mt-1">
          Páginas de links personalizables con URL propia (/lk/@handle) — usalas como destino de las tarjetas QR.
        </p>
      </div>
      <BaseButton variant="primary" size="sm" data-testid="linktree-new" @click="openCreateModal">
        Nuevo linktree
      </BaseButton>
    </div>

    <div v-if="store.isLoading && store.linktrees.length === 0" class="text-center py-16 text-text-subtle text-sm">
      Cargando linktrees...
    </div>

    <BaseEmptyState
      v-else-if="store.linktrees.length === 0"
      title="Sin linktrees todavía"
      description="Creá tu primer linktree para usarlo como destino de una tarjeta QR."
    />

    <BaseExploratoryList
      v-else
      :columns="linktreeColumns"
      :rows="store.linktrees"
      caption="Linktrees y estado de publicación"
      card-test-id-prefix="linktree-row"
      table-min-width="58rem"
      row-actions-layout="menu-start"
    >
      <template #cell-public_url="{ row: tree }">
        <div class="flex min-w-0 items-center gap-2">
          <code class="min-w-0 break-all rounded bg-surface-muted px-2 py-1 text-xs">{{ publicLinkFor(tree) }}</code>
          <BaseActionButton
            action="copy"
            :label="copyFeedback(tree).label || 'Copiar link'"
            :status-label="copyFeedback(tree).label"
            :status-tone="copyFeedback(tree).tone"
            size="sm"
            @click="copyLink(tree)"
          />
        </div>
      </template>

      <template #cell-kind="{ row: tree }">
        {{ tree.kind === 'company' ? 'Empresa' : 'Personal' }}
      </template>

      <template #cell-is_active="{ row: tree }">
        <BaseToggle
          :model-value="tree.is_active"
          :aria-label="`Activar ${tree.name}`"
          :data-testid="`linktree-toggle-${tree.id}`"
          @update:model-value="(value) => onToggleActive(tree, value)"
        />
      </template>

      <template #row-actions="{ row: tree }">
        <BaseActionButton
          action="more"
          class="h-11 w-11 shrink-0"
          :label="`Acciones de ${tree.name}`"
          :data-testid="`linktree-actions-${tree.id}`"
          @click.stop="actionsRow = tree"
        />
      </template>
    </BaseExploratoryList>

    <BaseRowActionsModal
      :open="actionsRow !== null"
      :title="actionsRow?.name || ''"
      :items="actionsRow ? linktreeActionItems(actionsRow) : []"
      testid="linktree-actions-modal"
      @close="actionsRow = null"
    />

    <!-- Create modal -->
    <BaseModal v-model="formModal.open" kind="form" padding="md">
      <form :id="modalFormId" novalidate data-testid="linktree-form" @submit.prevent="onSubmit">
        <div class="space-y-4 px-6 py-5">
          <h3 class="text-lg font-bold text-text-default">Nuevo linktree</h3>

          <BaseFormField v-slot="{ invalid, errorId }" label="Nombre interno" for="linktree-name" required :error="formErrors.name">
            <BaseInput
              id="linktree-name"
              v-model="formModal.name"
              data-testid="linktree-name-input"
              :error="invalid"
              :aria-describedby="errorId"
              @update:model-value="formErrors.name = ''"
            />
          </BaseFormField>

          <BaseFormField
            label="Handle"
            for="linktree-handle"
            required
            hint="La URL pública queda como /lk/@handle — minúsculas, números, punto, guion y guion bajo."
            :error="formErrors.handle"
            v-slot="{ invalid, errorId }"
          >
            <BaseInput
              id="linktree-handle"
              v-model="formModal.handle"
              placeholder="@mi_handle"
              data-testid="linktree-handle-input"
              :error="invalid"
              :aria-describedby="errorId"
              @update:model-value="formErrors.handle = ''"
            />
          </BaseFormField>

          <BaseFormField label="Tipo" for="linktree-kind">
            <BaseSegmented
              id="linktree-kind"
              v-model="formModal.kind"
              :options="[
                { value: 'personal', label: 'Personal' },
                { value: 'company', label: 'Empresa' },
              ]"
            />
          </BaseFormField>
        </div>

      </form>
      <template #footer>
        <BaseModalActions>
          <BaseButton type="button" variant="ghost" size="sm" @click="formModal.open = false">Cancelar</BaseButton>
          <BaseButton type="submit" :form="modalFormId" variant="primary" size="sm" :loading="store.isUpdating" data-testid="linktree-save">
            Crear y editar
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>

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
import { useId, onMounted, reactive, ref } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseEmptyState from '~/components/base/BaseEmptyState.vue';
import BaseExploratoryList from '~/components/base/BaseExploratoryList.vue';
import BaseRowActionsModal from '~/components/base/BaseRowActionsModal.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { useLinktreesStore } from '~/stores/linktrees';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const store = useLinktreesStore();
const notify = usePanelNotify();
const clipboardFeedback = useClipboardFeedback();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const localePath = useLocalePath();
const lp = (path) => localePath(path);

const formModal = reactive({ open: false, name: '', handle: '', kind: 'personal' });
const formErrors = reactive({ name: '', handle: '' });
const actionsRow = ref(null);

const linktreeColumns = [
  { key: 'name', label: 'Nombre', mobile: 'primary' },
  { key: 'public_url', label: 'URL pública', mobile: 'secondary' },
  { key: 'kind', label: 'Tipo', mobile: 'secondary' },
  { key: 'buttons_count', label: 'Botones', mobile: 'meta' },
  { key: 'is_active', label: 'Activo', mobile: 'meta' },
];

function linktreeActionItems(tree) {
  return [
    {
      action: 'edit',
      label: 'Editar',
      to: lp(`/panel/linktrees/${tree.id}/edit`),
      testid: `linktree-edit-${tree.id}`,
    },
    { divider: true },
    {
      action: 'delete',
      label: 'Eliminar',
      danger: true,
      testid: `linktree-delete-${tree.id}`,
      onClick: () => onDelete(tree),
    },
  ];
}

onMounted(() => {
  store.fetchLinktrees();
});

function publicLinkFor(tree) {
  return `${window.location.origin}${tree.public_path}`;
}

async function copyLink(tree) {
  await clipboardFeedback.copyText({
    key: `linktree-${tree.id}`,
    text: publicLinkFor(tree),
    successLabel: 'Copiado: link público',
    errorLabel: 'No se pudo copiar el link',
    onError: () => notify.error({
      title: 'No se pudo copiar',
      detail: 'Copiá el link manualmente.',
    }),
  });
}

function copyFeedback(tree) {
  return clipboardFeedback.feedbackFor(`linktree-${tree.id}`);
}

function openCreateModal() {
  formModal.name = '';
  formModal.handle = '';
  formModal.kind = 'personal';
  formErrors.name = '';
  formErrors.handle = '';
  formModal.open = true;
}

async function onToggleActive(tree, value) {
  const result = await store.updateLinktree(tree.id, { is_active: value });
  if (!result.success) {
    notify.error({ title: 'No se pudo actualizar el linktree' });
  }
}

async function onSubmit() {
  formErrors.name = '';
  formErrors.handle = '';
  if (!formModal.name.trim()) formErrors.name = 'Escribe el nombre interno.';
  if (!formModal.handle.trim()) formErrors.handle = 'Escribe el handle.';
  if (formErrors.name || formErrors.handle) return;
  const result = await store.createLinktree({
    name: formModal.name,
    handle: formModal.handle,
    kind: formModal.kind,
  });

  if (!result.success) {
    formErrors.name = result.errors?.name?.[0] || '';
    formErrors.handle = result.errors?.handle?.[0] || '';
    if (!result.errors) {
      notify.error({ title: 'No se pudo crear el linktree' });
    }
    return;
  }
  formModal.open = false;
  navigateTo(lp(`/panel/linktrees/${result.data.id}/edit`));
}

async function onDelete(tree) {
  const confirmed = await requestConfirm({
    title: 'Eliminar linktree',
    message: `"${tree.name}" se eliminará de forma permanente. Las tarjetas QR que lo usen como destino quedarán sin configurar hasta que les asignes otro. Esta acción no se puede deshacer.`,
    confirmText: 'Eliminar',
    variant: 'danger',
  });
  if (!confirmed) return;

  const result = await store.deleteLinktree(tree.id);
  if (!result.success) {
    notify.error({ title: 'No se pudo eliminar el linktree' });
  }
}

const modalFormId = useId();
</script>
