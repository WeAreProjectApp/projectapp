<script setup>
import { ref } from 'vue'

const props = defineProps({
  value: { type: Number, required: true },
  min: { type: Number, required: true },
  max: { type: Number, required: true },
  step: { type: Number, default: 16 },
  label: { type: String, required: true },
  testId: { type: String, default: '' },
  indicatorClass: { type: [String, Array, Object], default: 'h-10 w-1' },
})

const emit = defineEmits([
  'pointer-start', 'pointer-move', 'pointer-end', 'resize', 'reset',
])

const pointerActive = ref(false)

function clamp(value) {
  return Math.min(props.max, Math.max(props.min, Number(value)))
}

function onPointerDown(event) {
  // Native mouse dragging can cancel pointer capture after the first movement.
  event.preventDefault()
  pointerActive.value = true
  event.currentTarget.setPointerCapture?.(event.pointerId)
  emit('pointer-start', event)
}

function onPointerMove(event) {
  if (!pointerActive.value) return
  emit('pointer-move', event)
}

function finishPointer(event) {
  if (!pointerActive.value) return
  pointerActive.value = false
  event.currentTarget.releasePointerCapture?.(event.pointerId)
  emit('pointer-end', event)
}

function onKeydown(event) {
  let next = null
  if (event.key === 'ArrowLeft') next = props.value - props.step
  else if (event.key === 'ArrowRight') next = props.value + props.step
  else if (event.key === 'Home') next = props.min
  else if (event.key === 'End') next = props.max
  if (next === null) return

  event.preventDefault()
  emit('resize', clamp(next))
}
</script>

<template>
  <div
    role="separator"
    aria-orientation="vertical"
    :aria-label="label"
    :aria-valuenow="Math.round(value)"
    :aria-valuemin="min"
    :aria-valuemax="max"
    :data-testid="testId || undefined"
    :title="label"
    tabindex="0"
    class="group flex cursor-col-resize touch-none items-center justify-center focus:outline-none"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="finishPointer"
    @pointercancel="finishPointer"
    @dblclick="emit('reset')"
    @keydown="onKeydown"
  >
    <span
      aria-hidden="true"
      class="rounded-full bg-border-default transition-colors group-hover:bg-text-brand group-focus-visible:bg-text-brand"
      :class="indicatorClass"
    />
  </div>
</template>
