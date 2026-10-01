<template>
  <div class="space-y-2">
    <label :for="id" class="block text-xs font-medium text-text-muted">{{ t(required ? 'platformIssues.requiredSource' : 'platformIssues.source') }}</label>
    <select :id="id" :value="modelValue ?? ''" :required="required" class="w-full rounded-xl border border-border-default bg-surface px-3 py-2 text-sm text-text-default" @change="selectSource">
      <option value="">{{ t(required ? 'platformIssues.selectSource' : 'platformIssues.general') }}</option>
      <option v-for="row in options" :key="row.id" :value="row.id">{{ row.contract_title || row.scope_title }} · {{ row.stage_title }} · {{ row.title }}</option>
    </select>
    <p v-if="!required" class="text-xs text-text-muted">{{ t('platformIssues.generalHint') }}</p>
  </div>
</template>

<script setup>
const props = defineProps({ modelValue: { type: Number, default: null }, options: { type: Array, default: () => [] }, required: Boolean, id: { type: String, default: 'issue-source' } })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
function selectSource(event) {
  emit('update:modelValue', event.target.value ? Number(event.target.value) : null)
}
</script>
