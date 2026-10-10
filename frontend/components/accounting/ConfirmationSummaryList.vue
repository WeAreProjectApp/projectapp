<script setup>
/**
 * The facts a last notice shows before an email leaves, one row each, so
 * they can be checked without closing the dialog.
 */
defineProps({
  /** [{ key, label, value }] in reading order. */
  rows: { type: Array, required: true },
  /** Prefix for one data-testid per value: `${testid}-${row.key}`. */
  testid: { type: String, default: '' },
})
</script>

<template>
  <dl class="text-sm space-y-1" :data-testid="testid || undefined">
    <div
      v-for="row in rows"
      :key="row.key"
      class="flex justify-between gap-4"
    >
      <dt class="shrink-0 text-text-muted">{{ row.label }}</dt>
      <dd
        class="min-w-0 break-words text-right font-medium text-text-default tabular-nums"
        :data-testid="testid ? `${testid}-${row.key}` : undefined"
      >
        {{ row.value }}
      </dd>
    </div>
  </dl>
</template>
