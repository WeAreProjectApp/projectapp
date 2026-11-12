<template>
  <div class="min-w-0 space-y-2">
    <label :for="id" class="block text-xs font-medium text-text-muted">{{ t(required ? 'platformIssues.requiredSource' : 'platformIssues.source') }}</label>
    <select :id="id" data-testid="issue-source" :value="modelValue ?? ''" :required="required" :aria-describedby="selectedSource ? `${id}-selection` : undefined" class="min-h-11 w-full min-w-0 max-w-full rounded-xl border border-border-default bg-surface px-3 py-2 text-base text-text-default sm:text-sm" @change="selectSource">
      <option value="">{{ t(required ? 'platformIssues.selectSource' : 'platformIssues.general') }}</option>
      <option v-for="row in options" :key="row.id" :value="row.id">{{ row.title }} · {{ row.contract_title || row.scope_title }} · {{ row.stage_title }}</option>
    </select>
    <div v-if="selectedSource" :id="`${id}-selection`" data-testid="issue-source-selection" class="min-w-0 space-y-1 text-sm [overflow-wrap:anywhere]">
      <p class="whitespace-normal font-medium text-text-default" data-testid="issue-source-title">{{ selectedSource.title }}</p>
      <p class="text-xs text-text-muted">{{ selectedSource.contract_title || selectedSource.scope_title }} · {{ selectedSource.stage_title }}</p>
    </div>
    <p v-if="!required" class="text-xs text-text-muted">{{ t('platformIssues.generalHint') }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ modelValue: { type: Number, default: null }, options: { type: Array, default: () => [] }, required: Boolean, id: { type: String, default: 'issue-source' } })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const selectedSource = computed(() => props.options.find((row) => row.id === props.modelValue))
function selectSource(event) {
  emit('update:modelValue', event.target.value ? Number(event.target.value) : null)
}
</script>
