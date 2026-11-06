<script setup>
import { computed } from 'vue'
import { QuestionMarkCircleIcon } from '@heroicons/vue/24/outline'
import BaseActionIcon from '~/components/base/BaseActionIcon.vue'
import BaseTooltip from '~/components/base/BaseTooltip.vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: '' },
  /** Opt in when the complete amount must remain readable in a narrow card. */
  valueWrap: { type: Boolean, default: false },
  support: { type: String, default: '' },
  layout: {
    type: String,
    default: 'stacked',
    validator: (value) => ['stacked', 'compact-horizontal'].includes(value),
  },
  tone: {
    type: String,
    default: 'default',
    validator: (value) => ['default', 'success', 'warning', 'danger', 'brand'].includes(value),
  },
  /** Empty means informational. Any panel action turns the main surface into a button. */
  action: { type: String, default: '' },
  actionLabel: { type: String, default: '' },
  helpLabel: { type: String, default: '' },
  helpTestId: { type: String, default: '' },
  helpPosition: {
    type: String,
    default: 'left',
    validator: (value) => ['top', 'bottom', 'left', 'right'].includes(value),
  },
})

const emit = defineEmits(['activate'])

const TONE_CLASSES = {
  default: 'text-text-default',
  success: 'text-success-strong',
  warning: 'text-warning-strong',
  danger: 'text-danger-strong',
  brand: 'text-text-brand',
}

const toneClass = computed(() => TONE_CLASSES[props.tone] || TONE_CLASSES.default)
const isActionable = computed(() => Boolean(props.action))
const isCompactHorizontal = computed(() => props.layout === 'compact-horizontal')
const resolvedActionLabel = computed(() => (
  props.actionLabel || `${props.label}: ver detalle`
))
const resolvedHelpLabel = computed(() => props.helpLabel || `Ayuda sobre ${props.label}`)
</script>

<template>
  <article
    class="relative min-w-0 rounded-xl border border-border-muted bg-surface shadow-sm"
    :class="isCompactHorizontal
      ? ($slots.help
        ? 'grid h-20 grid-cols-[minmax(0,1fr)_3rem] items-stretch'
        : 'grid h-20 grid-cols-1 items-stretch')
      : 'h-full min-h-[8.25rem] sm:min-h-[9.5rem]'"
    :data-layout="layout"
  >
    <component
      :is="isActionable ? 'button' : 'div'"
      :type="isActionable ? 'button' : undefined"
      class="min-w-0 text-left"
      :class="[
        isCompactHorizontal
          ? 'grid h-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-3'
          : 'grid h-full min-h-[8.25rem] w-full gap-1 rounded-xl p-4 pr-12 sm:min-h-[9.5rem] sm:p-5 sm:pr-14',
        !isCompactHorizontal && (valueWrap
          ? 'grid-rows-[2.25rem_minmax(2.25rem,auto)_1.25rem]'
          : 'grid-rows-[2.25rem_2.25rem_1.25rem]'),
        isCompactHorizontal && $slots.help ? 'rounded-l-xl' : 'rounded-xl',
        isActionable && isCompactHorizontal
          ? 'cursor-pointer transition duration-base motion-reduce:transition-none hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring'
          : '',
        isActionable && !isCompactHorizontal
          ? 'cursor-pointer transition duration-base motion-reduce:transition-none hover:border-border-default hover:shadow-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring'
          : '',
      ]"
      :aria-label="isActionable ? resolvedActionLabel : undefined"
      @click="isActionable && emit('activate')"
    >
      <template v-if="isCompactHorizontal">
        <div class="min-w-0">
          <p
            class="line-clamp-2 min-w-0 text-xs uppercase leading-4 tracking-wider text-text-muted [overflow-wrap:anywhere]"
            data-testid="indicator-label"
          >
            {{ label }}
          </p>
          <p
            v-if="support"
            class="mt-0.5 line-clamp-1 min-w-0 text-xs leading-4 text-text-muted [overflow-wrap:anywhere]"
            data-testid="indicator-support"
          >
            {{ support }}
          </p>
        </div>
        <div
          class="flex shrink-0 items-center gap-2.5"
          data-testid="indicator-result-action"
        >
          <p
            class="whitespace-nowrap text-2xl font-semibold tabular-nums"
            :class="toneClass"
            data-testid="accounting-stat-value"
          >
            {{ value }}
          </p>
          <BaseActionIcon
            v-if="isActionable"
            :action="action"
            class="text-text-subtle"
          />
        </div>
      </template>

      <template v-else>
        <p
          class="line-clamp-2 min-w-0 self-start text-xs uppercase leading-4 tracking-wider text-text-muted [overflow-wrap:anywhere]"
          data-testid="indicator-label"
        >
          {{ label }}
        </p>
        <p
          class="min-w-0 self-center text-2xl font-semibold tabular-nums"
          :class="[toneClass, valueWrap ? 'whitespace-normal [overflow-wrap:anywhere]' : 'truncate']"
          data-testid="accounting-stat-value"
        >
          {{ value }}
        </p>
        <p
          class="line-clamp-1 min-w-0 self-end text-xs leading-5 text-text-muted [overflow-wrap:anywhere]"
          :aria-hidden="support ? undefined : 'true'"
          data-testid="indicator-support"
        >
          {{ support || '\u00a0' }}
        </p>
      </template>
    </component>

    <BaseTooltip
      v-if="$slots.help"
      :position="helpPosition"
      width="max-w-xs"
      min-width="min-w-[min(15rem,calc(100vw-2rem))]"
      :floating="!isCompactHorizontal"
      :root-class="isCompactHorizontal
        ? 'flex h-full items-center justify-center border-l border-border-muted'
        : 'absolute right-2 top-2 z-20'"
      trigger-class="inline-flex"
    >
      <template #trigger="{ tooltipId }">
        <button
          type="button"
          class="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full text-info-strong transition-colors hover:bg-info-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          :aria-label="resolvedHelpLabel"
          :aria-describedby="tooltipId"
          :data-testid="helpTestId || 'indicator-help'"
        >
          <QuestionMarkCircleIcon class="h-4 w-4" aria-hidden="true" />
        </button>
      </template>
      <div
        class="space-y-2"
        :data-testid="helpTestId ? `${helpTestId}-content` : 'indicator-help-content'"
      >
        <slot name="help" />
      </div>
    </BaseTooltip>

    <BaseActionIcon
      v-if="isActionable && !isCompactHorizontal"
      :action="action"
      class="pointer-events-none absolute bottom-4 right-4 text-text-subtle"
    />
  </article>
</template>
