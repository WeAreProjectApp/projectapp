import BaseRichTextEditor from '~/components/base/BaseRichTextEditor.vue';
import BaseRichTextListEditor from '~/components/base/BaseRichTextListEditor.vue';
import { h } from 'vue';
import BaseCurrencyInput from '~/components/base/BaseCurrencyInput.vue';
import BaseCheckbox from '~/components/base/BaseCheckbox.vue';

// Shared control geometry, so a checkbox placed next to an input in the same
// grid row lines up with it instead of floating against the label band.
const CONTROL_HEIGHT = 'min-h-[38px]';

// --- Inline sub-components (render functions for prod compatibility) ---
// Moved verbatim from SectionEditor.vue.
export const FieldInput = {
  // `type` is a declared prop, not a fallthrough attr: the root VNode here is
  // the <label>, so an undeclared type="number" would land on the label and
  // leave the <input> a plain text box.
  props: {
    modelValue: [String, Number],
    label: String,
    placeholder: String,
    disabled: Boolean,
    type: { type: String, default: 'text' },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    // A number field emits a Number, or null when cleared. Emitting the raw ''
    // would slip past the `?? default` guards in sectionEditorUtils and reach
    // the backend, which rejects it as non-numeric.
    const readValue = (raw) => {
      if (props.type !== 'number') return raw;
      if (raw === '') return null;
      const parsed = Number(raw);
      return Number.isNaN(parsed) ? null : parsed;
    };
    return () => h('label', { class: 'block' }, [
      props.label ? h('span', { class: 'block text-xs text-text-muted mb-0.5' }, props.label) : null,
      h('input', {
        value: props.modelValue,
        type: props.type,
        placeholder: props.placeholder,
        disabled: props.disabled,
        class: 'w-full px-3 py-2 border border-input-border bg-input-bg text-input-text placeholder-input-placeholder rounded-lg text-sm focus:ring-1 focus:ring-focus-ring/30 focus:border-focus-ring outline-none disabled:opacity-60 disabled:cursor-not-allowed',
        onInput: (e) => emit('update:modelValue', readValue(e.target.value)),
      }),
    ]);
  },
};

export const FieldCheckbox = {
  // Same label-band structure as the other fields, so it aligns with a
  // sibling input in the same grid row. `label` names the field; `text` is
  // the sentence beside the box.
  props: {
    modelValue: Boolean,
    label: String,
    text: String,
    help: String,
    disabled: Boolean,
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('div', { class: 'block' }, [
      props.label ? h('span', { class: 'block text-xs text-text-muted mb-0.5' }, props.label) : null,
      // py-2 keeps the tap target at 44 px on compact screens (FORM-2).
      h('div', { class: `flex items-center py-2 ${CONTROL_HEIGHT}` }, [
        h(
          BaseCheckbox,
          {
            modelValue: props.modelValue,
            disabled: props.disabled,
            'onUpdate:modelValue': (value) => emit('update:modelValue', Boolean(value)),
          },
          () => props.text || '',
        ),
      ]),
      props.help ? h('p', { class: 'text-[10px] text-text-subtle mt-0.5' }, props.help) : null,
    ]);
  },
};

export const FieldCurrency = {
  props: {
    modelValue: [String, Number],
    label: String,
    placeholder: String,
    decimals: { type: Number, default: 0 },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('label', { class: 'block' }, [
      props.label ? h('span', { class: 'block text-xs text-text-muted mb-0.5' }, props.label) : null,
      h(BaseCurrencyInput, {
        modelValue: props.modelValue,
        decimals: props.decimals,
        placeholder: props.placeholder,
        disabled: props.disabled,
        'onUpdate:modelValue': (value) => emit('update:modelValue', value),
      }),
    ]);
  },
};

export const FieldTextarea = {
  props: { modelValue: String, label: String, help: String, rows: { type: Number, default: 4 }, isSingle: Boolean, lines: Boolean, format: { type: String, default: 'plain' }, formats: { type: Object, default: () => ({}) }, formatPath: String },
  emits: ['update:modelValue', 'update:format', 'update:formats'],
  setup(props, { emit }) {
    return () => h('div', { class: 'block min-w-0' }, [
      props.label ? h('span', { class: 'mb-1 block text-xs text-text-muted' }, props.label) : null,
      h(props.lines ? BaseRichTextListEditor : BaseRichTextEditor, {
        modelValue: props.modelValue, label: props.label, format: props.format,
        formats: props.formats, formatPath: props.formatPath, rows: props.rows,
        'onUpdate:modelValue': (value) => emit('update:modelValue', value),
        'onUpdate:format': (value) => emit('update:format', value),
        'onUpdate:formats': (value) => emit('update:formats', value),
      }),
    ]);
  },
};
