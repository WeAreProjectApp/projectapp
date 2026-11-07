<script setup>
import { computed } from 'vue';
import BaseDropdown from '~/components/base/BaseDropdown.vue';
import BaseButton from '~/components/base/BaseButton.vue';

const props = defineProps({
  modelValue: { type: [Number, String], default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '' },
  label: { type: String, required: true },
  testid: { type: String, required: true },
  invalid: { type: Boolean, default: false },
  describedby: { type: String, default: undefined },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);
const selectedLabel = computed(() => props.options.find(option => String(option.value) === String(props.modelValue))?.label || props.placeholder);
const items = computed(() => props.options.map(option => ({
  label: option.label, testid: `${props.testid}-${option.value}`,
  onClick: () => emit('update:modelValue', option.value),
})));
</script>

<template>
  <BaseDropdown :items="items" align="left" width="w-full" class="w-full">
    <template #trigger>
      <BaseButton type="button" variant="secondary" class="w-full justify-between"
        :aria-label="label" :aria-invalid="invalid || undefined" :aria-describedby="describedby"
        :disabled="disabled" disabled-reason="El cambio está en curso." :data-testid="testid">
        {{ selectedLabel }}
        <span aria-hidden="true">▾</span>
      </BaseButton>
    </template>
  </BaseDropdown>
</template>
