<template>
  <div class="space-y-4" data-testid="secure-link-fields">
    <p v-if="type?.key === 'credentials'" class="text-sm text-text-muted">{{ t('secureLinks.credentialsHint') }}</p>
    <template v-for="group in groups" :key="group.key">
      <BaseButton v-if="group.optional && group.fields.length" type="button" variant="ghost" size="sm" :aria-expanded="showDetails" :aria-controls="detailsId" data-testid="secure-link-more-details" @click="showDetails = !showDetails">
        {{ t('secureLinks.moreDetails') }}
      </BaseButton>
      <BaseCollapse v-if="group.fields.length" :id="group.optional ? detailsId : undefined" :open="!group.optional || showDetails">
      <BaseFormRow :cols="2" :gap="4">
    <BaseFormField
      v-for="field in group.fields"
      :key="field.key"
      v-slot="{ invalid, errorId }"
      :label="labelFor(field)"
      :for="`${idPrefix}-${field.key}`"
      :required="field.required"
      :error="errors?.[field.key] || ''"
      :class="{ 'panel-portrait:col-span-2': isWide(field) }"
    >
      <BaseTextarea
        v-if="isMultiline(field)"
        :id="`${idPrefix}-${field.key}`"
        :name="`${idPrefix}-${field.key}`"
        :maxlength="field.max_length"
        :required="field.required"
        :model-value="modelValue[field.key] || ''"
        :rows="field.kind === 'secret' ? 5 : 4"
        :class="{ 'font-mono': field.kind === 'secret' }"
        :error="invalid"
        :aria-describedby="errorId"
        :disabled="disabled"
        :data-testid="`secure-link-field-${field.key}`"
        autocomplete="off"
        spellcheck="false"
        @update:model-value="update(field.key, $event)"
      />
      <div v-else class="flex min-w-0 items-center gap-2">
        <BaseInput
          :id="`${idPrefix}-${field.key}`"
          :name="`${idPrefix}-${field.key}`"
          :maxlength="field.max_length"
          :required="field.required"
          class="min-w-0 flex-1"
          :type="inputType(field)"
          :model-value="modelValue[field.key] || ''"
          :error="invalid"
          :aria-describedby="errorId"
          :disabled="disabled"
          :data-testid="`secure-link-field-${field.key}`"
          :autocomplete="field.kind === 'secret' ? 'new-password' : 'off'"
          @update:model-value="update(field.key, $event)"
        />
        <BaseActionButton
          v-if="field.kind === 'secret'"
          :action="visible[field.key] ? 'hide' : 'view'"
          :label="visible[field.key] ? t('secureLinks.fields.hide') : t('secureLinks.fields.show')"
          size="sm"
          :data-testid="`secure-link-field-toggle-${field.key}`"
          @click="visible[field.key] = !visible[field.key]"
        />
      </div>
    </BaseFormField>
      </BaseFormRow>
      </BaseCollapse>
    </template>
  </div>
</template>

<script setup>
import { computed, reactive, ref, useId, watch } from 'vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseFormRow from '~/components/base/BaseFormRow.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseTextarea from '~/components/base/BaseTextarea.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseCollapse from '~/components/base/BaseCollapse.vue';

const props = defineProps({
  /** Catalog entry `{ key, label_es, label_en, fields: [...] }`. */
  type: { type: Object, default: null },
  modelValue: { type: Object, default: () => ({}) },
  language: { type: String, default: 'es' },
  errors: { type: Object, default: () => ({}) },
  idPrefix: { type: String, default: 'secure-link' },
  disabled: { type: Boolean, default: false },
  excludeKeys: { type: Array, default: () => [] },
});
const emit = defineEmits(['update:modelValue']);
const { t } = useI18n();
const visible = reactive({});
const showDetails = ref(false);
const detailsId = useId();

const fields = computed(() => (props.type?.fields || []).filter(field => !props.excludeKeys.includes(field.key)));
const isPrimary = field => field.required || (props.type?.key === 'credentials' && field.key === 'username');
const groups = computed(() => [
  { key: 'primary', optional: false, fields: fields.value.filter(isPrimary) },
  { key: 'optional', optional: true, fields: fields.value.filter(field => !isPrimary(field)) },
]);
watch(() => props.errors, errors => {
  if (groups.value[1].fields.some(field => errors?.[field.key])) showDetails.value = true;
}, { deep: true, immediate: true });

watch(() => props.type?.key, () => {
  Object.keys(visible).forEach((key) => delete visible[key]);
  showDetails.value = false;
});

function labelFor(field) {
  return props.language === 'en' ? field.label_en : field.label_es;
}

function isMultiline(field) {
  return field.kind === 'textarea' || (field.kind === 'secret' && field.max_length > 2000);
}

// One-line values that are long by nature (a token, a subject) keep the full
// row; every other one-line field takes half of it.
const LONG_SINGLE_LINE_KEYS = new Set(['secret_key', 'subject']);

function isWide(field) {
  return isMultiline(field) || LONG_SINGLE_LINE_KEYS.has(field.key);
}

function inputType(field) {
  if (field.kind === 'secret') return visible[field.key] ? 'text' : 'password';
  return field.kind === 'url' ? 'url' : 'text';
}

function update(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value });
}
</script>
