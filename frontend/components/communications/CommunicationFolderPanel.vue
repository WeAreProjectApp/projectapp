<script setup>
import { useId, computed, reactive, ref, watch } from 'vue';
import { useCommunicationsStore } from '~/stores/communications';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { folderOptions, folderPath } from '~/utils/communicationFolders';

const props = defineProps({
  clientId: { type: [Number, String], default: null },
  projectId: { type: [Number, String], default: null },
  selected: { type: [Number, String], default: '' },
  searching: { type: Boolean, default: false },
});
const emit = defineEmits(['select', 'loaded', 'changed']);
const { t } = useI18n();
const store = useCommunicationsStore();
const notify = usePanelNotify();
const folders = ref([]);
const collapsed = ref(new Set());
const error = ref('');
const saving = ref(false);
const modalOpen = ref(false);
const deleting = ref(false);
const form = reactive({ id: null, name: '', parent: '', client: null, project: null });
let requestVersion = 0;
const selectedFolder = computed(() => folders.value.find((item) => String(item.id) === String(props.selected)));
const breadcrumbs = computed(() => folderPath(selectedFolder.value, folders.value));
const rows = computed(() => {
  const result = [];
  function visit(parent, depth) {
    for (const folder of folders.value.filter((item) => (item.parent || null) === parent)) {
      result.push({ ...folder, depth, hasChildren: folders.value.some((item) => item.parent === folder.id) });
      if (!collapsed.value.has(folder.id)) visit(folder.id, depth + 1);
    }
  }
  visit(null, 0);
  return result;
});
const parentOptions = computed(() => [
  { value: '', label: t('communicationFiling.root') },
  ...folderOptions(folders.value.filter((item) => (item.project || null) === (form.project || null)), {
    client: form.client, project: form.project, exclude: form.id,
  }),
]);

async function load() {
  const version = ++requestVersion;
  error.value = '';
  folders.value = [];
  if (!props.clientId) { emit('loaded', []); return; }
  const result = await store.fetchFolders({ client: props.clientId });
  if (version !== requestVersion) return;
  if (!result.success) { error.value = result.message; return; }
  folders.value = result.data.filter((folder) => !props.projectId || !folder.project || Number(folder.project) === Number(props.projectId));
  emit('loaded', folders.value);
}
watch(() => [props.clientId, props.projectId], load, { immediate: true });

function select(id) {
  for (const node of folderPath(folders.value.find((item) => item.id === Number(id)), folders.value)) {
    collapsed.value.delete(node.id);
  }
  emit('select', id);
}
function toggle(id) {
  if (collapsed.value.has(id)) collapsed.value.delete(id);
  else collapsed.value.add(id);
}
function openForm(folder = null) {
  deleting.value = false;
  error.value = '';
  Object.assign(form, folder ? {
    ...folder, parent: folder.parent ? String(folder.parent) : '',
  } : {
    id: null, name: '', parent: selectedFolder.value ? String(selectedFolder.value.id) : '',
    client: Number(props.clientId), project: selectedFolder.value ? selectedFolder.value.project : Number(props.projectId) || null,
  });
  modalOpen.value = true;
}
async function save() {
  saving.value = true;
  const result = deleting.value ? await store.deleteFolder(form.id) : await store.saveFolder(form.id, {
    name: form.name.trim(), parent: form.parent ? Number(form.parent) : null,
    client: form.client, project: form.project,
  });
  saving.value = false;
  if (!result.success) { error.value = result.message; return; }
  modalOpen.value = false;
  if (deleting.value && String(props.selected) === String(form.id)) emit('select', '');
  await load();
  emit('changed');
  notify.success({ title: t(deleting.value ? 'communicationFiling.folderDeleted' : 'communicationFiling.folderSaved') });
}

const modalFormId = useId();
</script>

<template>
  <section class="mt-3 border-t border-border-muted pt-3" data-testid="communication-folder-panel">
    <div class="flex items-center justify-between gap-2 px-2">
      <h3 class="text-sm font-semibold text-text-default">{{ t('communicationFiling.folders') }}</h3>
      <BaseActionButton v-if="clientId" action="create" :label="t('communicationFiling.create')" @click="openForm()" />
    </div>
    <p v-if="!clientId" class="p-2 text-xs text-text-muted">{{ t('communicationFiling.chooseContext') }}</p>
    <template v-else>
      <p v-if="searching" class="p-2 text-xs text-text-muted">{{ t('communicationFiling.globalSearch') }}</p>
      <BaseAlert v-if="error && !modalOpen" variant="danger">
        {{ error }} <BaseButton variant="link" @click="load">{{ t('communicationFiling.retry') }}</BaseButton>
      </BaseAlert>
      <div class="flex flex-wrap gap-1 p-2">
        <BaseButton :variant="!selected ? 'primary' : 'ghost'" size="sm" @click="select('')">{{ t('communicationFiling.all') }}</BaseButton>
        <BaseButton :variant="selected === 'none' ? 'primary' : 'ghost'" size="sm" data-testid="communication-folder-unfiled" @click="select('none')">{{ t('communicationFiling.unfiled') }}</BaseButton>
      </div>
      <nav v-if="breadcrumbs.length" :aria-label="t('communicationFiling.location')" class="flex flex-wrap gap-1 px-2 text-xs">
        <BaseButton v-for="folder in breadcrumbs" :key="folder.id" variant="link" size="sm" @click="select(String(folder.id))">/ {{ folder.name }}</BaseButton>
      </nav>
      <p v-if="!folders.length && !error" class="p-2 text-xs text-text-muted">{{ t('communicationFiling.empty') }}</p>
      <ul class="space-y-1 overflow-x-auto py-2">
        <li v-for="folder in rows" :key="folder.id" class="flex min-w-0 items-center gap-1" :style="{ paddingInlineStart: `${Math.min(folder.depth, 6) * 12}px` }">
          <BaseActionButton v-if="folder.hasChildren" :action="collapsed.has(folder.id) ? 'expand' : 'collapse'" :label="t(collapsed.has(folder.id) ? 'communicationFiling.expand' : 'communicationFiling.collapse', { name: folder.name })" @click="toggle(folder.id)" />
          <BaseButton :variant="String(selected) === String(folder.id) ? 'primary' : 'ghost'" size="sm" class="min-w-0 flex-1 justify-start" :data-testid="`communication-folder-${folder.id}`" @click="select(String(folder.id))">
            <BaseActionIcon action="folders" /><span class="truncate">{{ folder.name }}</span>
          </BaseButton>
          <BaseActionButton action="edit" :label="`${t('communicationFiling.edit')}: ${folder.name}`" @click="openForm(folder)" />
        </li>
      </ul>
    </template>
    <BaseModal v-model="modalOpen" kind="form">
      <form :id="modalFormId" class="px-6 py-4" @submit.prevent="save">
        <h2 class="text-lg font-semibold text-text-default">{{ t(deleting ? 'communicationFiling.delete' : (form.id ? 'communicationFiling.edit' : 'communicationFiling.create')) }}</h2>
        <BaseAlert v-if="error" variant="danger" class="mt-3">{{ error }}</BaseAlert>
        <p v-if="deleting" class="my-4 text-sm text-text-muted">{{ t('communicationFiling.confirmDelete') }}</p>
        <BaseFormRow v-else :cols="2" :gap="4" class="my-4">
          <BaseFormField :label="t('communicationFiling.name')"><BaseInput v-model="form.name" required maxlength="120" data-testid="communication-folder-name" /></BaseFormField>
          <BaseFormField :label="t('communicationFiling.parent')"><BaseSelect v-model="form.parent" :options="parentOptions" data-testid="communication-folder-parent" /></BaseFormField>
        </BaseFormRow>
      </form>
      <template #footer>
        <BaseModalActions>
          <BaseButton v-if="form.id && !deleting" variant="danger" @click="deleting = true">{{ t('communicationFiling.delete') }}</BaseButton>
          <BaseButton variant="secondary" @click="modalOpen = false">{{ t('communicationFiling.cancel') }}</BaseButton>
          <BaseButton type="submit" :form="modalFormId" :variant="deleting ? 'danger' : 'primary'" :loading="saving" data-testid="communication-folder-save">{{ t(deleting ? 'communicationFiling.delete' : 'communicationFiling.save') }}</BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </section>
</template>
