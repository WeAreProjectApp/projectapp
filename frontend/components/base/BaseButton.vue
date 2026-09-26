<script setup>
import {
  computed, onBeforeUnmount, ref, useAttrs, watchEffect,
} from 'vue'
import { oneOf } from './propValidators'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  // One variant per kind of action — see the action→variant table in
  // components/base/README.md. Anything destructive uses danger (confirmed,
  // e.g. a modal footer) or danger-ghost (inline, e.g. a row's trash icon).
  variant: {
    type: String,
    default: 'primary',
    validator: oneOf(['primary', 'secondary', 'ghost', 'danger', 'danger-ghost', 'link', 'accent']),
  },
  size: { type: String, default: 'md', validator: oneOf(['sm', 'md', 'lg']) },
  type: { type: String, default: 'button' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  /** Why a non-loading action is unavailable. A resolvable prerequisite that no
   *  field owns should also render visibly through BaseControlGate; a missing
   *  form field is not a reason to disable submit (BaseFormField names it). */
  disabledReason: { type: String, default: '' },
  /** Keep the browser-native title unless an owning primitive already exposes
   * the same help through an application tooltip. */
  nativeTitle: { type: Boolean, default: true },
  iconOnly: { type: Boolean, default: false },    // square padding for icon buttons
  /** Preserve a bespoke branded control's visual classes while adopting the
   * shared semantics, focus, touch target and activation feedback. */
  unstyled: { type: Boolean, default: false },
  /** Buttons are short UI controls by default. Sentence-like CTAs can opt in
   * to wrapping without allowing an icon to detach from its text. */
  textPolicy: {
    type: String,
    default: 'atomic',
    validator: oneOf(['atomic', 'wrap']),
  },
  as: { type: String, default: 'button' },        // button | a | NuxtLink
  to: { type: [String, Object], default: null },
})

const emit = defineEmits(['click'])

const ICON_ACTIVATION_DURATION = 420

const attrs = useAttrs()
const forwardedAttrs = computed(() => {
  const result = { ...attrs }
  if (!props.nativeTitle) delete result.title
  return result
})
const disabledTitle = computed(() => {
  if (!props.nativeTitle) return ''
  return props.disabled && !props.loading
    ? (props.disabledReason || attrs.title || 'Operación en curso. Espera un momento.')
    : (attrs.title || '')
})

const isActivated = ref(false)
const activationCycle = ref(0)
let activationTimer = null

function handleClick(event) {
  if (props.iconOnly && !props.disabled && !props.loading) {
    clearTimeout(activationTimer)
    // Alternate the animation name so a rapid second click visibly restarts
    // the pulse instead of only extending the active-state timer.
    activationCycle.value += 1
    isActivated.value = true
    activationTimer = setTimeout(() => {
      isActivated.value = false
      activationTimer = null
    }, ICON_ACTIVATION_DURATION)
  }
  emit('click', event)
}

onBeforeUnmount(() => clearTimeout(activationTimer))

const variants = {
  primary: 'bg-primary text-on-primary hover:bg-primary-strong border border-transparent',
  secondary: 'bg-surface text-text-default border border-border-default hover:bg-surface-raised',
  ghost: 'bg-transparent text-text-default hover:bg-surface-raised border border-transparent',
  danger: 'bg-danger-strong text-on-danger hover:opacity-90 border border-transparent',
  'danger-ghost': 'bg-transparent text-danger-strong hover:bg-danger-soft border border-transparent',
  link: 'bg-transparent text-text-brand hover:underline',
  accent: 'bg-accent text-primary-strong hover:brightness-95 border border-transparent',
}

const sizes = {
  sm: 'px-3 py-1.5 text-xs rounded-lg',
  md: 'px-4 py-2 text-sm rounded-xl',
  lg: 'px-5 py-2.5 text-base rounded-xl',
}

// Icon buttons get square padding so the glyph stays centred instead of
// sitting in a wide pill.
const iconSizes = {
  sm: 'p-1.5 text-xs rounded-lg',
  md: 'p-2 text-sm rounded-lg',
  lg: 'p-2.5 text-base rounded-xl',
}

// `link` renders as inline text: no padding, no radius, just the text size.
const linkSizes = {
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
}

const sizeClasses = computed(() => {
  if (props.unstyled) return ''
  if (props.variant === 'link') return linkSizes[props.size] || linkSizes.md
  if (props.iconOnly) return iconSizes[props.size] || iconSizes.md
  return sizes[props.size] || sizes.md
})

const classes = computed(() => [
  'base-button',
  props.iconOnly && 'base-button--icon',
  props.iconOnly && isActivated.value && (
    activationCycle.value % 2
      ? 'base-button--activation-odd'
      : 'base-button--activation-even'
  ),
  !props.unstyled && props.variant === 'link' && 'base-button--link',
  props.unstyled
    ? 'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/40 disabled:cursor-not-allowed disabled:opacity-60'
    : 'inline-flex min-w-0 max-w-full flex-nowrap items-center justify-center gap-2 font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/40 disabled:cursor-not-allowed disabled:opacity-60',
  !props.unstyled && (props.textPolicy === 'atomic' ? 'whitespace-nowrap' : 'whitespace-normal'),
  !props.unstyled && (variants[props.variant] || variants.primary),
  sizeClasses.value,
])

// An icon-only button has no text for a screen reader to announce, so the
// aria-label is the only thing naming it.
if (process.env.NODE_ENV !== 'production') {
  watchEffect(() => {
    if (props.iconOnly && !attrs['aria-label'] && !attrs['aria-labelledby']) {
      console.warn('[BaseButton] iconOnly buttons need an aria-label to be announced by screen readers.')
    }
  })
}
</script>

<template>
  <NuxtLink
    v-if="as === 'NuxtLink'"
    v-bind="forwardedAttrs"
    :to="to"
    :class="classes"
    :data-activation-state="iconOnly ? (isActivated ? 'active' : 'idle') : undefined"
    @click="handleClick"
  >
    <svg
      v-if="loading"
      class="h-4 w-4 shrink-0 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
    <span v-if="iconOnly" class="base-button__icon-content">
      <slot />
    </span>
    <slot v-else />
  </NuxtLink>
  <a
    v-else-if="as === 'a'"
    v-bind="forwardedAttrs"
    :href="typeof to === 'string' ? to : undefined"
    :class="classes"
    :data-activation-state="iconOnly ? (isActivated ? 'active' : 'idle') : undefined"
    @click="handleClick"
  >
    <svg
      v-if="loading"
      class="h-4 w-4 shrink-0 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
    <span v-if="iconOnly" class="base-button__icon-content">
      <slot />
    </span>
    <slot v-else />
  </a>
  <button
    v-else
    v-bind="forwardedAttrs"
    :type="type"
    :disabled="disabled || loading"
    :title="disabledTitle || undefined"
    :class="classes"
    :data-activation-state="iconOnly ? (isActivated ? 'active' : 'idle') : undefined"
    @click="handleClick"
  >
    <svg
      v-if="loading"
      class="h-4 w-4 shrink-0 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
    <span v-if="iconOnly" class="base-button__icon-content">
      <slot />
    </span>
    <slot v-else />
  </button>
</template>

<style scoped>
.base-button--icon {
  transition:
    color 150ms ease,
    background-color 150ms ease,
    border-color 150ms ease,
    opacity 150ms ease;
}

.base-button__icon-content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transform-origin: center;
  transition: transform 80ms ease-out;
}

.base-button--icon:active .base-button__icon-content {
  transform: translateY(1px) scale(0.92);
}

.base-button--activation-odd .base-button__icon-content,
.base-button--activation-even .base-button__icon-content {
  animation-duration: 420ms;
  animation-timing-function: cubic-bezier(0.22, 1, 0.36, 1);
}

.base-button--activation-odd .base-button__icon-content {
  animation-name: base-button-icon-hop-odd;
}

.base-button--activation-even .base-button__icon-content {
  animation-name: base-button-icon-hop-even;
}

@keyframes base-button-icon-hop-odd {
  0% { transform: translateY(1px) scale(0.92); }
  45% { transform: translateY(-3px) scale(1.08); }
  70% { transform: translateY(0.75px) scale(0.98); }
  85% { transform: translateY(-0.75px) scale(1.02); }
  100% { transform: scale(1); }
}

@keyframes base-button-icon-hop-even {
  0% { transform: translateY(1px) scale(0.92); }
  45% { transform: translateY(-3px) scale(1.08); }
  70% { transform: translateY(0.75px) scale(0.98); }
  85% { transform: translateY(-0.75px) scale(1.02); }
  100% { transform: scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .base-button--icon {
    transition: none;
  }

  .base-button--icon:active .base-button__icon-content,
  .base-button--activation-odd .base-button__icon-content,
  .base-button--activation-even .base-button__icon-content {
    animation: none;
    transform: none;
    opacity: 0.6;
    transition: none;
  }
}

/* The visual size may stay compact with a mouse; coarse pointers still get
 * the canonical 44px hit area without every caller remembering it. */
@media (pointer: coarse) {
  .base-button:not(.base-button--link) {
    min-height: 44px;
  }

  .base-button--icon {
    min-width: 44px;
  }
}
</style>
