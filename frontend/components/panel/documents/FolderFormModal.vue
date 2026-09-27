<template>
  <BaseModal
    :model-value="modelValue"
    kind="form"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <form :id="modalFormId" class="space-y-5" novalidate data-testid="folder-form-modal" @submit.prevent="submit">
      <div class="space-y-5 p-6">
      <div>
        <h3 class="text-base font-semibold text-text-default">
          {{ isEdit ? `Editar "${folder.name}"` : 'Nueva carpeta' }}
        </h3>
        <p class="text-xs text-text-muted mt-0.5">
          {{ isEdit
            ? 'Cambia su nombre, dónde vive y de quién es.'
            : 'De quién es la carpeta se hereda a lo que se cree dentro.' }}
        </p>
      </div>

      <BaseFormField
        label="Nombre"
        for="folder-form-name"
        required
        :error="nameError"
      >
        <BaseInput
          id="folder-form-name"
          v-model="form.name"
          type="text"
          placeholder="Nombre de la carpeta"
          :error="!!nameError"
          data-testid="folder-form-name"
          @update:model-value="nameError = ''"
        />
      </BaseFormField>

      <BaseFormField label="Dentro de" for="folder-form-parent">
        <BaseSelect
          id="folder-form-parent"
          v-model="form.parent"
          data-testid="folder-form-parent"
        >
          <option :value="null">Ninguna (carpeta raíz)</option>
          <option v-for="opt in parentOptions" :key="opt.id" :value="opt.id">
            {{ opt.label }}
          </option>
        </BaseSelect>
      </BaseFormField>

      <BaseFormField label="Cliente" :hint="inheritedNotice">
        <ClientAutocomplete
          :model-value="form.client"
          :initial-label="clientDisplayName"
          test-id="folder-form-client"
          @select="onClientSelect"
        />
      </BaseFormField>

      <BaseFormField label="Proyecto">
        <ProjectSelect
          v-model="form.project"
          :client-profile-id="form.client"
          :client-label="clientDisplayName"
          :allow-no-client="true"
          testid="folder-form-project"
          @select="onProjectSelect"
        />
      </BaseFormField>

      <BaseAlert v-if="errorMsg" variant="danger" data-testid="folder-form-error">
        {{ errorMsg }}
      </BaseAlert>
      </div>

    </form>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="ghost" data-testid="folder-form-cancel" @click="close">
          Cancelar
        </BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          :loading="folderStore.isUpdating"
          data-testid="folder-form-save"
        >
          {{ isEdit ? 'Guardar cambios' : 'Crear carpeta' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
/**
 * El único formulario de carpeta: crea y edita.
 *
 * Antes, editar una carpeta existente sólo se podía desde el modal de NUEVA
 * carpeta — el último lugar donde alguien buscaría cambiar algo que ya existe.
 * Ahora este modal se abre desde donde se usa la carpeta (su cabecera, su fila
 * del panel lateral y el árbol del gestor) y el panel de edición inline del
 * gestor desapareció.
 *
 * Al crear dentro de una carpeta con dueño, cliente y proyecto llegan
 * precargados: es un valor por defecto, no una atadura — se pueden vaciar
 * antes de guardar y nada los repone.
 *
 * Cambiar el cliente de una carpeta CON contenido no se resuelve acá: el
 * backend responde 409 `folder_has_content` y este modal lo eleva como
 * `change-client` para que decida la cascada, que sí sabe decir a qué afecta.
 */
import { useId, computed, reactive, ref, watch } from 'vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import ProjectSelect from '~/components/accounting/ProjectSelect.vue';
import { useClientProjectCascade } from '~/composables/useClientProjectCascade';
import { buildFolderOptions } from '~/utils/folderOptions';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Carpeta a editar. `null` abre el formulario en modo creación. */
  folder: { type: Object, default: null },
  /** Carpeta padre preseleccionada al crear. */
  initialParent: { type: Number, default: null },
  /** Carpeta de la que se hereda la asociación al crear dentro de ella. */
  inheritFrom: { type: Object, default: null },
});

const emit = defineEmits(['update:modelValue', 'saved', 'change-client']);

const folderStore = useDocumentFolderStore();

const form = reactive({ name: '', parent: null, client: null, project: null });
const clientDisplayName = ref('');
const errorMsg = ref('');
const nameError = ref('');
const inheritedClient = ref(null);

const isEdit = computed(() => Boolean(props.folder));

const { onClientSelect, onProjectSelect } = useClientProjectCascade(
  form,
  clientDisplayName,
  { onOperatorChoice: () => { inheritedClient.value = null; } },
);

const parentOptions = computed(() => buildFolderOptions(
  folderStore, isEdit.value ? props.folder.id : null,
));

const inheritedNotice = computed(() => (
  inheritedClient.value
    ? `Heredado de "${inheritedClient.value}". Puedes cambiarlo.`
    : ''
));

function reset() {
  errorMsg.value = '';
  nameError.value = '';
  inheritedClient.value = null;
  if (isEdit.value) {
    form.name = props.folder.name || '';
    form.parent = props.folder.parent ?? null;
    form.client = props.folder.client ?? null;
    form.project = props.folder.project ?? null;
    clientDisplayName.value = props.folder.client_display_name || '';
    return;
  }
  form.name = '';
  form.parent = props.initialParent ?? null;
  form.client = props.inheritFrom?.client ?? null;
  form.project = props.inheritFrom?.project ?? null;
  clientDisplayName.value = props.inheritFrom?.client_display_name || '';
  if (form.client) inheritedClient.value = props.inheritFrom?.name || '';
}

watch(() => props.modelValue, (open) => {
  if (open) reset();
}, { immediate: true });

function close() {
  emit('update:modelValue', false);
}

function formatErr(errors) {
  if (!errors) return '';
  if (typeof errors === 'string') return errors;
  const parts = Object.entries(errors)
    .filter(([key]) => key !== 'code')
    .map(([, value]) => (Array.isArray(value) ? value.join(' ') : value));
  return parts.join(' · ');
}

async function submit() {
  const name = form.name.trim();
  if (!name) {
    nameError.value = 'Escribe el nombre de la carpeta.';
    return;
  }
  errorMsg.value = '';
  const payload = {
    name,
    parent: form.parent,
    client: form.client,
    project: form.project,
  };

  const result = isEdit.value
    ? await folderStore.updateFolder(props.folder.id, payload)
    : await folderStore.createFolder(payload);

  if (result.success) {
    emit('saved', result.data);
    close();
    return;
  }
  if ((result.code || result.errors?.code) === 'folder_has_content') {
    emit('change-client', {
      folder: props.folder,
      clientProfileId: form.client,
    });
    return;
  }
  nameError.value = Array.isArray(result.errors?.name)
    ? result.errors.name.join(' ')
    : (result.errors?.name || '');
  errorMsg.value = nameError.value ? '' : formatErr(result.errors)
    || (isEdit.value ? 'No se pudo guardar.' : 'No se pudo crear la carpeta.');
}

const modalFormId = useId();
</script>
