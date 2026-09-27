<template>
  <BaseModal :model-value="modelValue" kind="form" padding="md" @update:model-value="emit('update:modelValue', $event)">
    <form :id="modalFormId" ref="formElement" autocomplete="off" novalidate data-testid="secure-link-form" @submit.prevent="submit">
      <div class="space-y-4 px-6 py-5">
        <h3 class="text-lg font-bold text-text-default">{{ t(link ? 'secureLinks.panel.editTitle' : 'secureLinks.panel.newTitle') }}</h3>

        <BaseAlert v-if="typesError" variant="danger" data-testid="secure-link-types-error">
          {{ t('secureLinks.typesError') }}
          <BaseButton type="button" variant="ghost" size="sm" :loading="loadingTypes" data-testid="secure-link-types-retry" @click="loadTypes">{{ t('secureLinks.retry') }}</BaseButton>
        </BaseAlert>

        <BaseFormField v-if="editingContent" v-slot="{ invalid, errorId }" :label="t('secureLinks.type')" for="secure-link-type" required :error="errors.secret_type">
          <BaseSelect
            id="secure-link-type"
            v-model="form.secretType"
            :disabled="!catalogReady || store.isUpdating"
            :disabled-reason="t('secureLinks.typesPending')"
            :options="typeOptions"
            :error="invalid"
            :aria-describedby="errorId"
            data-testid="secure-link-type"
          />
        </BaseFormField>

        <BaseFormField
          v-slot="{ invalid, errorId }"
          :label="t('secureLinks.panel.title')"
          for="secure-link-title"
          :hint="t('secureLinks.panel.titleHint')"
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
          v-if="editingContent && catalogReady"
          :key="fieldsVersion"
          :language="uiLanguage"
          :disabled="store.isUpdating"
          v-model="form.fields"
          :type="selectedType"
          :errors="errors"
          id-prefix="secure-link-panel"
        />

        <BaseFormField :label="t('secureLinks.panel.client')" :hint="t('secureLinks.panel.associationHint')" :error="errors.client">
          <ClientAutocomplete
            v-model="form.client"
            :initial-label="form.clientLabel"
            :placeholder="t('secureLinks.panel.clientPlaceholder')"
            test-id="secure-link-client"
            @select="onClientSelect"
          />
        </BaseFormField>
        <ProjectSelect
          v-model="form.project"
          :client-profile-id="form.client"
          :client-label="form.clientLabel"
          :allow-create="false"
          :label="t('secureLinks.panel.project')"
          testid="secure-link-project"
        />
        <BaseAlert v-if="errors.project" variant="danger" tabindex="-1">{{ errors.project }}</BaseAlert>

        <template v-if="!link">
          <BaseFormField label-policy="wrap" :label="t('secureLinks.panel.language')" for="secure-link-language" :error="errors.language">
            <BaseSegmented
              id="secure-link-language"
              v-model="form.language"
              :options="[{ value: 'es', label: 'Español' }, { value: 'en', label: 'English' }]"
              data-testid="secure-link-language"
            />
          </BaseFormField>
          <BaseFormField :label="t('secureLinks.validity')" for="secure-link-validity" :error="errors.validity_days">
            <BaseSegmented
              id="secure-link-validity"
              v-model="form.validityDays"
              :options="validityOptions"
              data-testid="secure-link-validity"
            />
          </BaseFormField>
        </template>

        <BaseAlert v-if="generalError" variant="danger" tabindex="-1" data-testid="secure-link-general-error">{{ generalError }}</BaseAlert>
      </div>

    </form>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="ghost" size="sm" @click="emit('update:modelValue', false)">{{ t('secureLinks.panel.cancel') }}</BaseButton>
        <BaseButton type="submit" :form="modalFormId" variant="primary" size="sm" :loading="store.isUpdating" :disabled="editingContent && !catalogReady" :disabled-reason="t('secureLinks.typesPending')" data-testid="secure-link-save">
          {{ t(link ? 'secureLinks.panel.save' : 'secureLinks.panel.create') }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { useId, computed, reactive, ref, watch } from 'vue';
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
import { useSecureLinkForm } from '~/composables/useSecureLinkForm';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Existing link row when editing; null to create. */
  link: { type: Object, default: null },
  /** Current decrypted values when editing (ephemeral, from the content view). */
  initialFields: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue', 'saved']);
const store = useSecureLinksStore();
const { t, locale } = useI18n();
const uiLanguage = computed(() => locale.value.startsWith('en') ? 'en' : 'es');
const formElement = ref(null);
const fieldsVersion = ref(0);
const editingContent = computed(() => !props.link || Boolean(props.initialFields));

const form = reactive({
  secretType: 'credentials', title: '', fields: {}, client: null, clientLabel: '',
  project: null, language: 'es', validityDays: 7,
});

const typeOptions = computed(() => store.types.map((type) => ({ value: type.key, label: uiLanguage.value === 'en' ? type.label_en : type.label_es })));
const selectedType = computed(() => store.typeByKey(form.secretType));
const validityOptions = computed(() => [1, 3, 7, 30].map((days) => ({ value: days, label: t('secureLinks.days', days) })));
const { errors, generalError, loadingTypes, typesError, catalogReady, loadTypes, resetErrors, validateFields, mapErrors, focusError } = useSecureLinkForm(formElement, selectedType, t);

watch(() => props.modelValue, (open) => {
  if (!open) {
    form.fields = {};
    return;
  }
  fieldsVersion.value += 1;
  resetErrors();
  typesError.value = false;
  if (editingContent.value) loadTypes();
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
  if (previous && next !== previous) {
    // Preserve only the values explicitly loaded for the edited link.
    form.fields = props.modelValue && props.initialFields && next === props.link?.secret_type
      ? { ...props.initialFields } : {};
    resetErrors();
  }
});

function onClientSelect(client) {
  form.clientLabel = client?.name || client?.email || '';
  form.project = null;
}

async function submit() {
  if (store.isUpdating || (editingContent.value && !catalogReady.value)) return;
  resetErrors();
  if (!form.title.trim()) errors.value.title = t('secureLinks.panel.titleRequired');
  else if ([...form.title.trim()].length > 160) errors.value.title = t('secureLinks.validation.maxLength', { max: 160 });
  if (editingContent.value) validateFields(form.fields);
  if (Object.keys(errors.value).length || generalError.value) {
    await focusError();
    return;
  }
  const payload = {
    secret_type: form.secretType,
    title: form.title,
    fields: form.fields,
    client: form.client || null,
    project: form.project || null,
  };
  if (!editingContent.value) {
    delete payload.secret_type;
    delete payload.fields;
  }
  const result = props.link
    ? await store.updateLink(props.link.id, payload)
    : await store.createLink({ ...payload, language: form.language, validity_days: form.validityDays });
  if (!result.success) {
    mapErrors(result.error, [
      'title', 'client', 'project', ...(!props.link ? ['language', 'validity_days'] : []),
      ...(editingContent.value ? ['secret_type', ...(selectedType.value?.fields || []).map((field) => field.key)] : []),
    ]);
    return;
  }
  form.fields = {};
  emit('saved', result.data);
  emit('update:modelValue', false);
}

const modalFormId = useId();
</script>
