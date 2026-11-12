<script setup>
import { computed, useId } from 'vue'
const props = defineProps({ modelValue: { type: Object, default: () => ({}) } })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const tr = key => t(`procurement.${key}`)
const uid = useId()
const lists = ['keywords', 'unspsc_codes', 'entity_names', 'departments', 'methods', 'contract_types', 'statuses']
const ranges = ['min_budget', 'max_budget', 'published_from', 'published_to', 'closing_from', 'closing_to']
const display = key => lists.includes(key) ? (props.modelValue[key] || []).join(key === 'keywords' ? ' | ' : ', ') : (props.modelValue[key] ?? '')
function update(key, value) {
  const filters = { ...props.modelValue }
  if (lists.includes(key)) value = value.split(key === 'keywords' ? '|' : ',').map(item => item.trim()).filter(Boolean)
  if (value === '' || (Array.isArray(value) && !value.length)) delete filters[key]
  else filters[key] = value
  emit('update:modelValue', filters)
}
const open = computed({ get: () => props.modelValue.is_open !== false, set: value => update('is_open', value) })
</script>

<template>
  <div class="space-y-4" data-testid="procurement-filters">
    <p class="text-sm text-text-subtle">{{ tr('keywordHelp') }}</p>
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <BaseFormField v-for="key in ['search', 'keywords', 'unspsc_codes']" :key="key" :label="tr(key)" :for="`${uid}-${key}`">
        <BaseInput :id="`${uid}-${key}`" :model-value="display(key)" :data-testid="`filter-${key}`" @update:model-value="update(key, $event)" />
      </BaseFormField>
    </div>
    <details>
      <summary class="cursor-pointer text-sm text-text-default">{{ tr('advanced') }}</summary>
      <div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <BaseFormField v-for="key in [...lists.slice(2), ...ranges]" :key="key" :label="tr(key)" :for="`${uid}-${key}`">
          <BaseInput :id="`${uid}-${key}`" :type="key.includes('budget') ? 'number' : ranges.includes(key) ? 'date' : 'text'" :min="key.includes('budget') ? 0 : undefined" :step="key.includes('budget') ? '0.01' : undefined" :model-value="display(key)" :data-testid="`filter-${key}`" @update:model-value="update(key, $event)" />
        </BaseFormField>
      </div>
    </details>
    <BaseCheckbox v-model="open">{{ tr('is_open') }}</BaseCheckbox>
  </div>
</template>
