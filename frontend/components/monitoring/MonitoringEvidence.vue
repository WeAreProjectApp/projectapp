<script setup>
import { computed } from 'vue'
const props = defineProps({ evidence: { type: Object, default: () => ({}) } })
const { t } = useI18n()
const tr = key => t(`monitoring.${key}`)
const fields = computed(() => Object.entries(props.evidence || {}).filter(([, value]) => value !== null && value !== undefined && value !== ''))
const label = key => {
  const known = ['metric', 'value', 'unit', 'threshold', 'service', 'route', 'query_count', 'duration_ms', 'rule', 'path', 'result', 'count', 'sample_percent', 'message']
  return known.includes(key) ? tr(`fields.${key}`) : key.replaceAll('_', ' ')
}
</script>

<template>
  <div class="space-y-3">
    <dl v-if="fields.length" class="grid gap-3 sm:grid-cols-2">
      <div v-for="[key, value] in fields" :key="key" class="min-w-0 rounded-lg bg-surface-raised p-3">
        <dt class="text-xs text-text-subtle">{{ label(key) }}</dt>
        <dd class="mt-1 whitespace-pre-wrap break-words text-sm text-text-default">{{ value }}</dd>
      </div>
    </dl>
    <p v-else class="text-sm text-text-subtle">{{ tr('noObservations') }}</p>
    <details class="rounded-lg border border-border-default p-3">
      <summary class="cursor-pointer text-sm font-medium text-text-default">{{ tr('technicalData') }}</summary>
      <pre class="mt-3 whitespace-pre-wrap break-words text-xs text-text-subtle">{{ JSON.stringify(evidence, null, 2) }}</pre>
    </details>
  </div>
</template>
