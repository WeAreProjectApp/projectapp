<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue';
import BaseFloatingListbox from '~/components/base/BaseFloatingListbox.vue';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import { INPUT_FIELD_BASE, INPUT_FIELD_SIZE } from '~/components/base/inputClasses';
import { formatServiceTerm, savedServiceTermNumber } from '~/utils/serviceContractTerms';

const props = defineProps({
  modelValue: { type: [Number, String], default: '' },
  options: { type: Array, required: true },
  duration: { type: Boolean, default: false },
  label: { type: String, required: true },
  error: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);
const { t } = useI18n();
const id = useId();
const selection = ref('');
const owner = ref(null);
const trigger = ref(null);
const open = ref(false);
const activeIndex = ref(0);
// null means Personalizar has not been opened yet; an empty draft is intentional.
const customValue = ref(null);
let emittedValue;

watch(() => props.modelValue, value => {
  // Echoes from v-model must preserve the custom draft and the user's mode.
  if (value === emittedValue) return;
  const number = savedServiceTermNumber(value, props.duration);
  selection.value = props.options.includes(number) ? String(number) : 'custom';
  customValue.value = selection.value === 'custom'
    ? (typeof value === 'number' ? formatServiceTerm(value, props.duration) : value)
    : null;
}, { immediate: true });

const choices = computed(() => [
  ...props.options.map(value => ({ value: String(value), label: formatServiceTerm(value, props.duration) })),
  { value: 'custom', label: t('serviceContract.custom') },
]);
const selectedLabel = computed(() => choices.value.find(choice => choice.value === selection.value)?.label || '');

function close(restoreFocus = true) {
  open.value = false;
  if (restoreFocus && !props.disabled) trigger.value?.focus({ preventScroll: true });
}

watch(() => props.disabled, disabled => {
  if (disabled) close(false);
});

async function revealOption() {
  await nextTick();
  document.getElementById(`${id}-option-${activeIndex.value}`)?.scrollIntoView?.({ block: 'nearest' });
}

function openList() {
  if (props.disabled) return;
  activeIndex.value = Math.max(0, choices.value.findIndex(choice => choice.value === selection.value));
  open.value = true;
  revealOption();
}

function onKeydown(event) {
  if (props.disabled) return;
  if (event.key === 'Tab') {
    close(false);
    return;
  }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(event.key)) return;
  event.preventDefault();
  if (event.key === 'Enter' || event.key === ' ') {
    if (open.value) select(choices.value[activeIndex.value].value);
    else openList();
    return;
  }
  const wasOpen = open.value;
  if (!wasOpen) openList();
  if (event.key === 'Home') activeIndex.value = 0;
  else if (event.key === 'End') activeIndex.value = choices.value.length - 1;
  else if (wasOpen) {
    activeIndex.value = (activeIndex.value + (event.key === 'ArrowDown' ? 1 : -1) + choices.value.length) % choices.value.length;
  }
  revealOption();
}

function publish(value) {
  emittedValue = value;
  emit('update:modelValue', value);
}

async function select(value) {
  if (props.disabled) return;
  if (value === 'custom' && customValue.value === null) {
    customValue.value = formatServiceTerm(Number(selection.value), props.duration);
  }
  selection.value = value;
  publish(value === 'custom' ? customValue.value : Number(value));
  close();
  if (value === 'custom') {
    await nextTick();
    document.getElementById(`${id}-custom`)?.focus();
  }
}

function edit(value) {
  if (props.disabled) return;
  customValue.value = value;
  publish(value);
}
</script>

<template>
  <!-- Three shared field bands align the triggers; the fourth holds custom input. -->
  <div ref="owner" class="min-w-0 space-y-2 sm:grid sm:grid-rows-subgrid sm:row-span-4 sm:gap-y-0 sm:space-y-0">
    <BaseFormField :label="label" :for="id" required size="sm" label-policy="wrap" :error="selection !== 'custom' ? error : ''">
      <button
        :id="id"
        ref="trigger"
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-required="true"
        :aria-expanded="open"
        :aria-controls="open ? `${id}-options` : undefined"
        :aria-activedescendant="open ? `${id}-option-${activeIndex}` : undefined"
        :aria-disabled="disabled"
        :disabled="disabled"
        :title="disabled ? t('serviceContract.contractSaving') : undefined"
        :class="[INPUT_FIELD_BASE, INPUT_FIELD_SIZE.sm]"
        class="flex min-h-11 items-center justify-between gap-2 text-left"
        @click="open ? close() : openList()"
        @keydown="onKeydown"
      >
        <span class="min-w-0 break-words">{{ selectedLabel }}</span>
        <BaseActionIcon :action="open ? 'collapse' : 'expand'" class="shrink-0" />
      </button>
    </BaseFormField>
    <BaseFloatingListbox
      :id="`${id}-options`"
      :open="open && !disabled"
      :anchor="trigger"
      :owner="owner"
      :aria-label="label"
      @close="close()"
    >
      <!-- design-tokens: allow-raw-button — selectable listbox options use their own active/selected states. -->
      <button
        v-for="(choice, index) in choices"
        :id="`${id}-option-${index}`"
        :key="choice.value"
        type="button"
        role="option"
        tabindex="-1"
        :aria-selected="selection === choice.value"
        :disabled="disabled"
        :title="disabled ? t('serviceContract.contractSaving') : undefined"
        class="flex min-h-11 w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-text-default"
        :class="activeIndex === index ? 'bg-surface-raised' : ''"
        @pointermove="activeIndex = index"
        @mousedown.prevent
        @click="select(choice.value)"
      >
        <span class="min-w-0 break-words">{{ choice.label }}</span>
        <BaseActionIcon v-if="selection === choice.value" action="complete" class="shrink-0" />
      </button>
    </BaseFloatingListbox>
    <BaseFormField
      v-if="selection === 'custom'"
      :label="t('serviceContract.customLabel', { field: label })"
      :for="`${id}-custom`"
      :error="error"
      :hint="t(duration ? 'serviceContract.customDurationHint' : 'serviceContract.customNoticeHint')"
      required
      size="sm"
      label-policy="wrap"
      standalone
      class="min-w-0 sm:mt-2"
    >
      <BaseInput
        :id="`${id}-custom`"
        :model-value="customValue"
        type="text"
        :maxlength="duration ? 100 : 60"
        size="sm"
        :disabled="disabled"
        :disabled-reason="t('serviceContract.contractSaving')"
        @update:model-value="edit"
      />
    </BaseFormField>
  </div>
</template>
