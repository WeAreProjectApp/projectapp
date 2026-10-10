<script setup>
import { watch } from 'vue'

/**
 * Period input honouring the accounting convention: day 1 means
 * "month only", any other day is the exact date. Exact mode is the
 * parent's choice via `v-model:exact`; the toggle downgrades to month
 * granularity when only the month is known.
 */
const model = defineModel({ type: [String, null], default: '' })
const exact = defineModel('exact', { type: Boolean, default: true })

defineProps({
  labelExact: { type: String, required: true },
  labelMonth: { type: String, required: true },
  toggleLabel: { type: String, default: 'Registrar el día exacto' },
  required: { type: Boolean, default: false },
  inputTestid: { type: String, default: '' },
  toggleTestid: { type: String, default: '' },
  /**
   * Forwarded to the inner `BaseFormField`, which shows it only when this
   * component stands alone. Inside an aligned `BaseFormRow` (more than one
   * column) the field drops hints by design: pass that copy to the row's
   * `help` instead of wrapping this component, which would break the row.
   */
  hint: { type: String, default: '' },
  hintTestid: { type: String, default: '' },
})

// Keep whatever was typed when flipping modes: 'YYYY-MM' ⇄ 'YYYY-MM-DD'.
// Upgrading only converts month-shaped values: a full date must survive a
// flip untouched, or a parent re-syncing `exact` on open would silently
// reset a real day back to the 1st.
watch(exact, (isExact) => {
  const value = model.value
  if (!value) return
  if (isExact) {
    if (value.length === 7) model.value = `${value}-01`
  } else {
    model.value = value.slice(0, 7)
  }
})
</script>

<template>
  <BaseFormField
    :label="exact ? labelExact : labelMonth"
    :required="required"
    :hint="hint"
    :hint-testid="hintTestid"
  >
    <BaseInput
      v-model="model"
      :type="exact ? 'date' : 'month'"
      :required="required"
      :data-testid="inputTestid || undefined"
    />
    <label class="flex items-center gap-2 mt-2 text-xs text-text-subtle">
      <BaseToggle
        v-model="exact"
        :aria-label="toggleLabel"
        :data-testid="toggleTestid || undefined"
      />
      {{ toggleLabel }}
    </label>
  </BaseFormField>
</template>
