<template>
  <div class="min-w-0 space-y-2">
    <label :for="id" class="block text-xs font-medium text-text-muted">{{ t(required ? 'platformIssues.requiredSource' : 'platformIssues.source') }}</label>
    <BaseChoiceSelect :id="id" data-testid="issue-source" :model-value="modelValue"
      :required="required" :aria-describedby="selectedSource ? `${id}-selection` : undefined"
      :options="sourceOptions" @update:model-value="$emit('update:modelValue', $event)" />
    <div v-if="selectedSource" :id="`${id}-selection`" data-testid="issue-source-selection" class="min-w-0 space-y-1 text-sm [overflow-wrap:anywhere]">
      <p class="whitespace-normal font-medium text-text-default" data-testid="issue-source-title">{{ selectedSource.title }}</p>
      <p class="text-xs text-text-muted">{{ selectedSource.contract_title || selectedSource.scope_title }} · {{ selectedSource.stage_title }}</p>
    </div>
    <p v-if="!required" class="text-xs text-text-muted">{{ t('platformIssues.generalHint') }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import BaseChoiceSelect from '~/components/base/BaseChoiceSelect.vue'

const props = defineProps({ modelValue: { type: Number, default: null }, options: { type: Array, default: () => [] }, required: Boolean, id: { type: String, default: 'issue-source' } })
defineEmits(['update:modelValue'])
const { t } = useI18n()
const selectedSource = computed(() => props.options.find((row) => row.id === props.modelValue))
const sourceOptions = computed(() => [
  { value: null, label: t(props.required ? 'platformIssues.selectSource' : 'platformIssues.general') },
  ...props.options.map(row => ({ value: row.id, label: `${row.title} · ${row.contract_title || row.scope_title} · ${row.stage_title}` })),
])
</script>
