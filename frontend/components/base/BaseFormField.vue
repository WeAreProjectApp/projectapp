<script setup>
import { computed, inject, nextTick, provide, ref, unref, useId, watch } from 'vue'
import { FIELD_ALIGNED, FIELD_CELL, FORM_ROW_ALIGN } from './formRowClasses'
import { oneOf } from './propValidators'

const props = defineProps({
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
  /** Only when the hint is itself the assertion — it lives in the row's
   *  shared band, so it cannot be reached through the control. */
  hintTestid: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false },
  requiredMessage: { type: String, default: '' },
  for: { type: String, default: '' },
  size: { type: String, default: 'md' }, // sm | md
  /** Short interface labels are atomic. Long sentence-like labels can opt in
   * to wrapping while the shared bands keep their controls aligned. */
  labelPolicy: {
    type: String,
    default: 'atomic',
    validator: oneOf(['atomic', 'wrap']),
  },
  /** Ignore the surrounding `BaseFormRow` and stack on its own. For a field
   *  that is inside a row without being one of its direct children: it would
   *  pick up the marker but is not a grid item, so there is no row to inherit. */
  standalone: { type: Boolean, default: false },
})

const rowAlign = inject(FORM_ROW_ALIGN, null)

/** The breakpoint at which this field joins the row's shared bands, if any. */
const alignAt = computed(() => (props.standalone ? null : unref(rowAlign)))

const rootClass = computed(() => (alignAt.value ? FIELD_ALIGNED[alignAt.value] : ''))

const nativeError = ref('')
const nativeControl = ref(null)
const rootRef = ref(null)
const errorId = `${useId()}-error`
const displayedError = computed(() => props.error || nativeError.value)
provide('editorialField', { error: displayedError, errorId, label: computed(() => props.label) })

function fieldName() {
  return props.label.trim().replace(/\s*\*$/, '').toLocaleLowerCase('es') || 'este campo'
}

function nativeValidationMessage(control) {
  if (control.validity?.valueMissing) {
    return props.requiredMessage || `Completa ${fieldName()}.`
  }
  if (control.validity?.typeMismatch && control.type === 'email') {
    return 'Escribe un correo válido.'
  }
  return control.validationMessage || `Revisa ${fieldName()}.`
}

function connectNativeError(control) {
  if (nativeControl.value && nativeControl.value !== control) disconnectNativeError()
  nativeControl.value = control
  control.setAttribute('aria-invalid', 'true')
  const ids = new Set((control.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean))
  ids.add(errorId)
  control.setAttribute('aria-describedby', [...ids].join(' '))
}

watch(
  displayedError,
  async (error) => {
    if (!error) {
      disconnectNativeError()
      return
    }
    await nextTick()
    const control = rootRef.value?.querySelector('[data-editorial-active="true"]') || rootRef.value?.querySelector(
      'input:not([type="hidden"]), select, textarea, [role="combobox"]',
    )
    if (control) connectNativeError(control)
  },
  { immediate: true },
)

function disconnectNativeError(control = nativeControl.value) {
  if (!control) return
  const ids = (control.getAttribute('aria-describedby') || '')
    .split(/\s+/)
    .filter((id) => id && id !== errorId)
  if (ids.length) control.setAttribute('aria-describedby', ids.join(' '))
  else control.removeAttribute('aria-describedby')
  if (!props.error) control.removeAttribute('aria-invalid')
  if (control === nativeControl.value) nativeControl.value = null
}

function onInvalid(event) {
  event.preventDefault()
  nativeError.value = nativeValidationMessage(event.target)
  connectNativeError(event.target)
}

function onControlChange(event) {
  if (!nativeError.value || event.target !== nativeControl.value) return
  if (typeof event.target.checkValidity === 'function' && !event.target.checkValidity()) return
  nativeError.value = ''
  disconnectNativeError(event.target)
}

/**
 * Outside a row the wrappers are `contents`, which keeps them out of the box
 * tree — the field renders exactly as it did before the bands existed.
 */
const cellClass = computed(() => (alignAt.value ? FIELD_CELL[alignAt.value] : 'contents'))
</script>

<template>
  <div
    ref="rootRef"
    class="base-form-field"
    :class="rootClass"
    :data-invalid="displayedError ? 'true' : undefined"
    @invalid.capture="onInvalid"
    @input.capture="onControlChange"
    @change.capture="onControlChange"
  >
    <div :class="cellClass">
      <label
        v-if="label"
        :for="$props.for"
        class="block font-medium text-text-default mb-1"
        :class="[
          size === 'sm' ? 'text-xs' : 'text-sm',
          labelPolicy === 'atomic' ? 'whitespace-nowrap' : 'whitespace-normal',
        ]"
      >
        {{ label }}
        <span v-if="required" class="text-danger-strong">*</span>
      </label>
    </div>
    <div :class="cellClass">
      <slot
        :error-id="displayedError ? errorId : undefined"
        :invalid="Boolean(displayedError)"
      />
    </div>
    <div :class="cellClass">
      <p
        v-if="displayedError"
        :id="errorId"
        role="alert"
        class="text-xs text-danger-strong mt-1"
      >
        {{ displayedError }}
      </p>
      <p
        v-else-if="hint && !alignAt"
        class="text-xs text-text-muted mt-1"
        :data-testid="hintTestid || undefined"
      >
        {{ hint }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.base-form-field[data-invalid='true'] :deep(input:not(:disabled)),
.base-form-field[data-invalid='true'] :deep(select:not(:disabled)),
.base-form-field[data-invalid='true'] :deep(textarea:not(:disabled)),
.base-form-field[data-invalid='true'] :deep([role='combobox']:not([aria-disabled='true'])) {
  border-color: rgb(var(--color-danger-strong-rgb));
}
</style>
