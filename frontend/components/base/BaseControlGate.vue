<script setup>
import { computed, useId } from 'vue'
import BaseTooltip from './BaseTooltip.vue'
import { oneOf } from './propValidators'

const props = defineProps({
  /** Every reason the control is unavailable. Empty strings are ignored. */
  reasons: { type: Array, default: () => [] },
  /** Human name used by the focusable wrapper around a native disabled control. */
  label: { type: String, default: 'Control no disponible' },
  /** Resolvable blockers must stay visible because touch has no hover. Missing
   *  form fields are not gate reasons: BaseFormField names them beside the
   *  field after the attempt. */
  visible: { type: Boolean, default: true },
  /** Keep footer height stable while reasons appear and disappear. */
  reserveSpace: { type: Boolean, default: false },
  align: {
    type: String,
    default: 'end',
    validator: oneOf(['start', 'end', 'stretch']),
  },
  position: {
    type: String,
    default: 'top',
    validator: oneOf(['top', 'bottom', 'left', 'right']),
  },
  testid: { type: String, default: '' },
})

const descriptionId = useId()

const normalizedReasons = computed(() => {
  const seen = new Set()
  return props.reasons
    .map(reason => String(reason || '').trim())
    .filter((reason) => {
      if (!reason || seen.has(reason)) return false
      seen.add(reason)
      return true
    })
})

const blocked = computed(() => normalizedReasons.value.length > 0)
const alignmentClass = computed(() => ({
  start: 'items-start text-left',
  end: 'items-end text-right',
  stretch: 'items-stretch text-left',
}[props.align]))
</script>

<template>
  <div
    :class="['flex flex-col gap-1', alignmentClass]"
    :data-testid="testid || undefined"
  >
    <BaseTooltip
      :disabled="!blocked"
      :position="position"
      floating
      width="max-w-sm"
      min-width="min-w-[240px]"
      trigger-class=""
    >
      <template #trigger>
        <div
          :class="align === 'stretch' ? 'flex w-full' : 'inline-flex max-w-full'"
          :tabindex="blocked ? 0 : undefined"
          :aria-label="blocked ? label : undefined"
          :aria-describedby="blocked ? descriptionId : undefined"
          :data-testid="testid ? `${testid}-trigger` : undefined"
        >
          <slot :blocked="blocked" :described-by="descriptionId" />
        </div>
      </template>
      <template v-if="blocked">
        <p class="font-medium mb-1">{{ label }}</p>
        <ul class="list-disc pl-4 space-y-0.5">
          <li v-for="reason in normalizedReasons" :key="reason">{{ reason }}</li>
        </ul>
      </template>
    </BaseTooltip>

    <!-- Always mounted: adding a live region only when the form becomes
         invalid is too late for assistive technology to subscribe to it. -->
    <div
      :id="descriptionId"
      aria-live="polite"
      :class="[
        'text-xs text-danger-strong',
        reserveSpace ? 'min-h-4' : '',
        !visible && 'sr-only',
      ]"
      :data-testid="testid ? `${testid}-reasons` : undefined"
    >
      <template v-if="blocked">
        <p v-if="normalizedReasons.length === 1">{{ normalizedReasons[0] }}</p>
        <ul v-else class="list-disc pl-4 space-y-0.5">
          <li v-for="reason in normalizedReasons" :key="reason">{{ reason }}</li>
        </ul>
      </template>
    </div>
  </div>
</template>
