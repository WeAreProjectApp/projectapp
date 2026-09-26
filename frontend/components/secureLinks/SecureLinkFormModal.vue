<template>
  <BaseModal :model-value="modelValue" kind="form" padding="md" @update:model-value="emit('update:modelValue', $event)">
    <form novalidate data-testid="secure-link-form" @submit.prevent="submit">
      <div class="space-y-4 px-6 py-5">
        <h3 class="text-lg font-bold text-text-default">{{ link ? 'Editar enlace seguro' : 'Nuevo enlace seguro' }}</h3>

        <BaseFormField v-slot="{ invalid, errorId }" label="Tipo de información" for="secure-link-type" required :error="errors.secret_type">
          <BaseSelect
            id="secure-link-type"
            v-model="form.secretType"
            :options="typeOptions"
            :error="invalid"
            :aria-describedby="errorId"
            data-testid="secure-link-type"
          />
        </BaseFormField>

        <BaseFormField
          v-slot="{ invalid, errorId }"
          label="Título interno"
          for="secure-link-title"
          hint="Para reconocerlo en el panel. El destinatario lo ve sólo después de abrirlo; no escribas el secreto aquí."
          required
          :error="errors.title"
        >
          <BaseInput
            id="secure-link-title"
            v-model="form.title"
            :error="invalid"
            :aria-describedby="errorId"
            maxlength="160"
            data-testid="secure-link-title"
          />
        </BaseFormField>

        <SecureLinkFields
          v-model="form.fields"
          :type="selectedType"
          :errors="errors"
          id-prefix="secure-link-panel"
        />

        <BaseFormField label="Cliente" hint="Opcional: asocia el enlace a un cliente y proyecto.">
          <ClientAutocomplete
            v-model="form.client"
            :initial-label="form.clientLabel"
            placeholder="Buscar cliente..."
            test-id="secure-link-client"
            @select="onClientSelect"
          />
        </BaseFormField>
        <ProjectSelect
          v-model="form.project"
          :client-profile-id="form.client"
          :client-label="form.clientLabel"
          :allow-create="false"
          label="Proyecto"
          testid="secure-link-project"
        />
        <BaseAlert v-if="errors.project" variant="danger">{{ errors.project }}</BaseAlert>

        <template v-if="!link">
          <BaseFormField label="Idioma de la página que verá el destinatario" for="secure-link-language">
            <BaseSegmented
              id="secure-link-language"
              v-model="form.language"
              :options="[{ value: 'es', label: 'Español' }, { value: 'en', label: 'English' }]"
              data-testid="secure-link-language"
            />
          </BaseFormField>
          <BaseFormField label="Vigencia" for="secure-link-validity" :error="errors.validity_days">
            <BaseSegmented
              id="secure-link-validity"
              v-model="form.validityDays"
              :options="validityOptions"
              data-testid="secure-link-validity"
            />
          </BaseFormField>
        </template>

        <BaseAlert v-if="generalError" variant="danger">{{ generalError }}</BaseAlert>
      </div>

      <BaseModalActions>
        <BaseButton type="button" variant="ghost" size="sm" @click="emit('update:modelValue', false)">Cancelar</BaseButton>
        <BaseButton type="submit" variant="primary" size="sm" :loading="store.isUpdating" data-testid="secure-link-save">
          {{ link ? 'Guardar cambios' : 'Crear enlace' }}
        </BaseButton>
      </BaseModalActions>
    </form>
  </BaseModal>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseModalActions from '~/components/base/BaseModalActions.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import ProjectSelect from '~/components/accounting/ProjectSelect.vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import SecureLinkFields from '~/components/secureLinks/SecureLinkFields.vue';
import { useSecureLinksStore } from '~/stores/secure_links';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Existing link row when editing; null to create. */
  link: { type: Object, default: null },
  /** Current decrypted values when editing (ephemeral, from the content view). */
  initialFields: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue', 'saved']);
const store = useSecureLinksStore();

const form = reactive({
  secretType: 'credentials', title: '', fields: {}, client: null, clientLabel: '',
  project: null, language: 'es', validityDays: 7,
});
const errors = ref({});
const generalError = ref('');

const typeOptions = computed(() => store.types.map((type) => ({ value: type.key, label: type.label_es })));
const selectedType = computed(() => store.typeByKey(form.secretType));
const validityOptions = [1, 3, 7, 30].map((days) => ({ value: days, label: days === 1 ? '1 día' : `${days} días` }));

watch(() => props.modelValue, (open) => {
  if (!open) {
    form.fields = {};
    return;
  }
  store.fetchTypes();
  errors.value = {};
  generalError.value = '';
  Object.assign(form, {
    secretType: props.link?.secret_type || 'credentials',
    title: props.link?.title || '',
    fields: props.initialFields ? { ...props.initialFields } : {},
    client: props.link?.client ?? null,
    clientLabel: props.link?.client_name || '',
    project: props.link?.project ?? null,
    language: props.link?.language || 'es',
    validityDays: 7,
  });
});

watch(() => form.secretType, (next, previous) => {
  if (previous && next !== previous && !props.initialFields) form.fields = {};
});

function onClientSelect(client) {
  form.clientLabel = client?.name || client?.email || '';
  if (!client) form.project = null;
}

function mapErrors(error) {
  const fieldErrors = error?.fieldErrors || {};
  errors.value = Object.fromEntries(
    Object.entries(fieldErrors).map(([key, value]) => [key, Array.isArray(value) ? value[0] : value]),
  );
  const handled = Object.keys(errors.value).some((key) => key !== 'fields');
  generalError.value = errors.value.fields || (handled ? '' : error?.message || '');
}

async function submit() {
  errors.value = {};
  generalError.value = '';
  if (!form.title.trim()) {
    errors.value = { title: 'Escribe un título para reconocer el enlace.' };
    return;
  }
  const payload = {
    secret_type: form.secretType,
    title: form.title,
    fields: form.fields,
    client: form.client || null,
    project: form.project || null,
  };
  const editingContent = !props.link || props.initialFields;
  if (!editingContent) {
    delete payload.secret_type;
    delete payload.fields;
  }
  const result = props.link
    ? await store.updateLink(props.link.id, payload)
    : await store.createLink({ ...payload, language: form.language, validity_days: form.validityDays });
  if (!result.success) {
    mapErrors(result.error);
    return;
  }
  form.fields = {};
  emit('saved', result.data);
  emit('update:modelValue', false);
}
</script>
