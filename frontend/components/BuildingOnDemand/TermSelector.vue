<script setup>
import { computed } from 'vue'
import BaseSegmented from '~/components/base/BaseSegmented.vue'
import { listOf } from '~/utils/buildingWithUs'

const props = defineProps({
  terms: { type: Object, required: true },
  modelValue: { type: String, default: 'monthly' },
})
const emit = defineEmits(['update:modelValue'])
const options = computed(() => listOf(props.terms.items).map((term) => ({
  value: term.id,
  label: term.label,
  testId: `building-on-demand-term-${term.id}`,
})))
const selectedTerm = computed(() => listOf(props.terms.items).find((term) => term.id === props.modelValue))
</script>

<template>
  <div class="building-on-demand-terms min-w-0 space-y-3 [overflow-wrap:anywhere]" data-testid="building-on-demand-terms">
    <h3 class="text-lg font-semibold text-text-default">{{ terms.title }}</h3>
    <p class="max-w-prose text-base text-text-muted">{{ terms.summary }}</p>
    <BaseSegmented
      :model-value="modelValue"
      :options="options"
      :aria-label="terms.title"
      @update:model-value="emit('update:modelValue', $event)"
    />
    <p v-if="selectedTerm?.months > 1" class="max-w-prose text-sm text-text-muted">{{ terms.note }}</p>
  </div>
</template>

<style scoped>
.building-on-demand-terms :deep([role='tab']) {
  min-height: 2.75rem;
  white-space: normal;
  overflow-wrap: anywhere;
}
</style>
