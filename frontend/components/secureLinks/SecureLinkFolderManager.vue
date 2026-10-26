<script setup>
import { computed, reactive, ref, useId, watch } from 'vue';
import { useSecureLinkFoldersStore } from '~/stores/secure_link_folders';
import { buildFolderOptions } from '~/utils/folderOptions';
const props = defineProps({ open: Boolean, folder: { type: Object, default: null }, parentId: { type: Number, default: null }, moveLink: { type: Object, default: null }, moveFolder: Boolean, busy: Boolean });
const emit = defineEmits(['close', 'saved', 'move-link']);
const store = useSecureLinkFoldersStore();
const form = reactive({ name: '', parent: '' });
const error = ref('');
const formId = useId();
const saving = computed(() => props.busy || store.isUpdating);
const options = computed(() => buildFolderOptions(store, props.folder?.id).filter(o => !store.folderById(o.id)?.is_archived && !store.folderById(o.id)?.is_read_only));
watch(() => props.open, open => { if (open) { form.name = props.folder?.name || ''; form.parent = String(props.moveLink?.folder ?? props.folder?.parent ?? props.parentId ?? ''); error.value = ''; } });
async function save() {
  if (saving.value) return;
  if (props.moveLink) { emit('move-link', { link: props.moveLink, folder: form.parent ? Number(form.parent) : null }); return; }
  const data = { parent: form.parent ? Number(form.parent) : null, ...(props.moveFolder ? {} : { name: form.name }), ...(props.folder ? { expected_updated_at: props.folder.updated_at } : {}) };
  const result = await store.saveFolder(props.folder?.id, data);
  if (!result.success) { error.value = result.error?.message || 'No se pudo guardar la carpeta.'; return; }
  emit('saved');
}
</script>
<template>
  <BaseModal :model-value="open" kind="form" :close-on-backdrop="!saving" :close-on-esc="!saving" @update:model-value="!saving && $emit('close')">
    <form :id="formId" class="space-y-4 px-6 py-5" data-testid="secure-folder-form" @submit.prevent="save">
      <h2 class="text-lg font-semibold text-text-default">{{ moveLink ? 'Mover enlace' : moveFolder ? 'Mover carpeta' : folder ? 'Editar carpeta' : 'Nueva carpeta' }}</h2>
      <BaseAlert v-if="error" variant="danger">{{ error }}</BaseAlert>
      <BaseFormField v-if="!moveLink && !moveFolder" label="Nombre" required>
        <BaseInput v-model="form.name" required maxlength="120" data-testid="secure-folder-name" />
      </BaseFormField>
      <BaseFormField label="Carpeta de destino">
        <BaseSelect v-model="form.parent" :options="[{ value: '', label: 'Sin carpeta (raíz)' }, ...options.map(o => ({ value: String(o.id), label: o.label }))]" data-testid="secure-folder-parent" />
      </BaseFormField>
      <p v-if="moveLink || moveFolder" class="text-sm text-text-muted">El movimiento conserva el cliente, el proyecto y los permisos de los enlaces.</p>
    </form>
    <template #footer><BaseModalActions>
      <BaseButton variant="secondary" :disabled="saving" disabled-reason="Guardando carpeta" @click="$emit('close')">Cancelar</BaseButton>
      <BaseButton type="submit" :form="formId" variant="primary" :loading="saving" data-testid="secure-folder-save">Guardar</BaseButton>
    </BaseModalActions></template>
  </BaseModal>
</template>
