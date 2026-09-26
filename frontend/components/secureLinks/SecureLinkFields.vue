<template>
  <div class="space-y-4" data-testid="secure-link-fields">
    <BaseFormField
      v-for="field in fields"
      :key="field.key"
      v-slot="{ invalid, errorId }"
      :label="labelFor(field)"
      :for="`${idPrefix}-${field.key}`"
      :required="field.required"
      :error="errors?.[field.key] || ''"
    >
      <BaseTextarea
        v-if="isMultiline(field)"
        :id="`${idPrefix}-${field.key}`"
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
          class="min-w-0 flex-1"
          :type="inputType(field)"
          :model-value="modelValue[field.key] || ''"
          :error="invalid"
          :aria-describedby="errorId"
          :disabled="disabled"
          :data-testid="`secure-link-field-${field.key}`"
          autocomplete="off"
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
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseTextarea from '~/components/base/BaseTextarea.vue';

const props = defineProps({
  /** Catalog entry `{ key, label_es, label_en, fields: [...] }`. */
  type: { type: Object, default: null },
  modelValue: { type: Object, default: () => ({}) },
  language: { type: String, default: 'es' },
  errors: { type: Object, default: () => ({}) },
  idPrefix: { type: String, default: 'secure-link' },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);
const { t } = useI18n();
const visible = reactive({});

const fields = computed(() => props.type?.fields || []);

function labelFor(field) {
  return props.language === 'en' ? field.label_en : field.label_es;
}

function isMultiline(field) {
  return field.kind === 'textarea' || (field.kind === 'secret' && field.max_length > 2000);
}

function inputType(field) {
  if (field.kind === 'secret') return visible[field.key] ? 'text' : 'password';
  return field.kind === 'url' ? 'url' : 'text';
}

function update(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value });
}
</script>
