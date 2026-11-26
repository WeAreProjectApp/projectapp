<script setup>
/**
 * A row of form fields whose controls line up.
 *
 * Wrap the fields in it instead of writing `<div class="grid grid-cols-2 gap-3">`
 * by hand. The row owns three shared bands (label / control / hint) and each
 * `BaseFormField` inside inherits them, so the controls start at the same height
 * even when one label wraps to two lines and the other does not — and the line
 * below stays square when only one field carries an error. Explanatory help is
 * rendered once below the whole group instead of reserving a blank hint cell in
 * every column.
 *
 * Below the breakpoint the fields stack in a single column: no bands, so no
 * reserved space is left over, and the DOM order is the reading order.
 *
 * More fields than columns is fine — they wrap, each line aligns on its own, and
 * the row's `gap` still separates one line from the next.
 *
 * The fields must be *direct* children for the subgrid to have a row to inherit.
 * One nested inside another component still renders fine (it falls back to the
 * plain stacked field); pass `standalone` on it to say so explicitly. A child
 * that is not a field and should span the row needs the bands too, e.g.
 * `class="panel-portrait:col-span-2 panel-portrait:row-span-3"`.
 */
import { computed, provide } from 'vue'
import {
  FORM_ROW_ALIGN,
  ROW_BANDS,
  ROW_COLS,
  ROW_COLS_LG,
  ROW_FIELD_ACTION,
  ROW_GAP,
} from './formRowClasses'
import { oneOf } from './propValidators'

const props = defineProps({
  /** Columns from the breakpoint up. `1` just stacks — useful to keep one
   *  markup for a block that is a grid only in its dense variant. */
  cols: { type: Number, default: 2, validator: oneOf([1, 2, 3, 4]) },
  /** Optional wider step on large screens, for filter bars. `0` means none. */
  lg: { type: Number, default: 0, validator: oneOf([0, 2, 3, 4, 5, 6]) },
  gap: { type: Number, default: 3, validator: oneOf([2, 3, 4, 6]) },
  /** Where the columns appear. `md` is here to preserve the breakpoint rows
   *  already had; new rows should stay on the default. */
  at: {
    type: String,
    default: 'portrait',
    validator: oneOf(['sm', 'md', 'portrait', 'landscape']),
  },
  /** The row is sometimes the `<form>` itself rather than a wrapper around it. */
  as: { type: String, default: 'div', validator: oneOf(['div', 'form']) },
  /** Equal columns by default; `field-action` keeps a compact companion button
   * aligned with the control instead of centring it against label + help. */
  layout: {
    type: String,
    default: 'equal',
    validator: oneOf(['equal', 'field-action']),
  },
  /** Short explanation for the complete group, rendered below every column. */
  help: { type: String, default: '' },
  helpId: { type: String, default: '' },
  helpTestid: { type: String, default: '' },
})

// A single column has nothing to align: the fields already stack, and asking
// them for a subgrid would make both claim the same three bands.
const alignAt = computed(() => (
  props.layout === 'field-action' || props.cols > 1 || props.lg > 1 ? props.at : null
))
provide(FORM_ROW_ALIGN, alignAt)

const rowClass = computed(() => [
  ROW_GAP[props.gap] || ROW_GAP[3],
  props.layout === 'field-action'
    ? ROW_FIELD_ACTION[props.at]
    : (ROW_COLS[props.at][props.cols] || ''),
  props.layout === 'equal' ? (ROW_COLS_LG[props.lg] || '') : '',
  alignAt.value ? ROW_BANDS[props.at] : '',
])
</script>

<template>
  <component :is="as" class="grid grid-cols-1" :class="rowClass">
    <slot />
    <p
      v-if="help || $slots.help"
      class="col-span-full -mt-2 text-xs text-text-muted"
      :id="helpId || undefined"
      :data-testid="helpTestid || undefined"
    >
      <slot name="help">{{ help }}</slot>
    </p>
  </component>
</template>
