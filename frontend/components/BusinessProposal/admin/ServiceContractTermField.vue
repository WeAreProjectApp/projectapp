<script setup>
import { computed, ref, useId, watch } from 'vue';
import { formatServiceTerm, savedServiceTermNumber } from '~/utils/serviceContractTerms';

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
// null means Personalizar has not been opened yet; an empty draft is intentional.
const customValue = ref(null);
let emittedValue;

watch(() => props.modelValue, value => {
  // Echoes from v-model must preserve the custom draft and the user's mode.
  if (value === emittedValue) return;
  const number = savedServiceTermNumber(value, props.duration);
  selection.value = props.options.includes(number) ? String(number) : 'custom';
  customValue.value = selection.value === 'custom'
    ? (typeof value === 'number' ? formatServiceTerm(value, props.duration) : value)
    : null;
}, { immediate: true });

const choices = computed(() => [
  ...props.options.map(value => ({ value: String(value), label: formatServiceTerm(value, props.duration) })),
  { value: 'custom', label: t('serviceContract.custom') },
]);

function publish(value) {
  emittedValue = value;
  emit('update:modelValue', value);
}

function select(value) {
  if (value === 'custom' && customValue.value === null) {
    customValue.value = formatServiceTerm(Number(selection.value), props.duration);
  }
  selection.value = value;
  publish(value === 'custom' ? customValue.value : Number(value));
}

function edit(value) {
  customValue.value = value;
  publish(value);
}
</script>

<template>
  <div class="space-y-2">
    <BaseFormField :label="label" :for="id" required size="sm" label-policy="wrap" :error="selection !== 'custom' ? error : ''">
      <BaseSelect :id="id" :model-value="selection" size="sm" :options="choices" @update:model-value="select" />
    </BaseFormField>
    <BaseFormField
      v-if="selection === 'custom'"
      :label="t('serviceContract.customLabel', { field: label })"
      :for="`${id}-custom`"
      :error="error"
      :hint="t(duration ? 'serviceContract.customDurationHint' : 'serviceContract.customNoticeHint')"
      required
      size="sm"
      label-policy="wrap"
    >
      <BaseInput
        :id="`${id}-custom`"
        :model-value="customValue"
        type="text"
        :maxlength="duration ? 100 : 60"
        size="sm"
        @update:model-value="edit"
      />
    </BaseFormField>
  </div>
</template>
