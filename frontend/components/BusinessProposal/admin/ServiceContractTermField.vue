<script setup>
import { computed, ref, useId, watch } from 'vue';
import { formatServiceTerm, savedServiceTermNumber, serviceTermNumber } from '~/utils/serviceContractTerms';

const props = defineProps({
  modelValue: { type: [Number, String], default: '' },
  options: { type: Array, required: true },
  duration: { type: Boolean, default: false },
  label: { type: String, required: true },
  error: { type: String, default: '' },
});
const emit = defineEmits(['update:modelValue']);
const { t } = useI18n();
const id = useId();
const selection = ref('');
const customValue = ref('');
const savedValue = ref('');
let emittedValue;

watch(() => props.modelValue, value => {
  // An internal edit must not collapse Personalizado when its number is a preset.
  if (value === emittedValue) return;
  const number = savedServiceTermNumber(value, props.duration);
  savedValue.value = number === null && value ? String(value) : '';
  customValue.value = number ?? '';
  selection.value = savedValue.value ? 'saved' : props.options.includes(number) ? String(number) : 'custom';
}, { immediate: true });

const choices = computed(() => [
  ...props.options.map(value => ({ value: String(value), label: formatServiceTerm(value, props.duration) })),
  { value: 'custom', label: t('serviceContract.custom') },
  ...(savedValue.value ? [{ value: 'saved', label: t('serviceContract.savedValue') }] : []),
]);
const preview = computed(() => formatServiceTerm(customValue.value, props.duration));

function update() {
  emittedValue = selection.value === 'saved' ? savedValue.value
    : selection.value === 'custom' ? (serviceTermNumber(customValue.value) ?? '')
      : Number(selection.value);
  emit('update:modelValue', emittedValue);
}
</script>

<template>
  <div class="space-y-2">
    <BaseFormField :label="label" :for="id" required size="sm" label-policy="wrap" :error="selection !== 'custom' ? error : ''">
      <BaseSelect :id="id" v-model="selection" size="sm" :options="choices" @update:model-value="update" />
    </BaseFormField>
    <BaseFormField
      v-if="selection === 'custom'"
      :label="t('serviceContract.customLabel', { field: label })"
      :for="`${id}-custom`"
      :error="error"
      :hint="t(duration ? 'serviceContract.monthsHint' : 'serviceContract.daysHint')"
      size="sm"
      label-policy="wrap"
    >
      <BaseInput
        :id="`${id}-custom`"
        v-model="customValue"
        type="number"
        min="1"
        max="999"
        step="1"
        size="sm"
        @update:model-value="update"
      />
      <p v-if="preview" class="mt-1 text-sm text-text-muted" aria-live="polite">{{ preview }}</p>
    </BaseFormField>
    <p v-if="selection === 'saved'" class="break-words text-sm text-text-muted">{{ savedValue }}</p>
  </div>
</template>
