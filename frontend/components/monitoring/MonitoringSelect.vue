<script setup>
const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, required: true },
  label: { type: String, required: true },
  searchable: { type: Boolean, default: false },
  testId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <BaseFilterDropdown :label="label" :options="options" :model-value="modelValue === '' ? [] : [String(modelValue)]"
    :searchable="searchable" single :test-id="testId"
    @update:model-value="emit('update:modelValue', $event[0] ?? '')" />
</template>
