<script setup>
import { computed, nextTick, ref, useAttrs, useId, watch } from 'vue';
import { useI18n } from '#imports';
import BaseActionIcon from './BaseActionIcon.vue';
import BaseFloatingListbox from './BaseFloatingListbox.vue';
import BaseInput from './BaseInput.vue';
import { INPUT_FIELD_BASE, INPUT_FIELD_SIZE, INPUT_FIELD_ERROR } from './inputClasses';

defineOptions({ inheritAttrs: false });
const props = defineProps({
  modelValue: { type: [String, Number, Boolean, null], default: '' },
  options: { type: Array, default: () => [] },
  id: { type: String, default: '' },
  size: { type: String, default: 'md' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  disabledReason: { type: String, default: '' },
  required: { type: Boolean, default: false },
  error: { type: Boolean, default: false },
  searchable: { type: Boolean, default: null },
  triggerClass: { type: [String, Array, Object], default: '' },
});
const emit = defineEmits(['update:modelValue']);
const attrs = useAttrs();
const { t } = useI18n();
const generatedId = useId();
const controlId = computed(() => props.id || `choice-${generatedId}`);
const owner = ref(null), trigger = ref(null), searchInput = ref(null);
const open = ref(false), query = ref(''), activeIndex = ref(-1);
const choices = computed(() => props.options.map(option => (
  typeof option === 'object' && option !== null
    ? { ...option, label: option.label ?? String(option.value ?? '') }
    : { value: option, label: String(option) }
)));
const selected = computed(() => choices.value.find(option => option.value === props.modelValue));
const searchable = computed(() => props.searchable ?? choices.value.length >= 10);
const normalize = text => String(text).normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase();
const filtered = computed(() => {
  const needle = normalize(query.value.trim());
  return choices.value.filter(option => !needle || normalize(option.label).includes(needle));
});
const controlAttrs = computed(() => {
  const { class: _class, style: _style, ...rest } = attrs;
  return rest;
});
const emptyValue = computed(() => props.modelValue === null || props.modelValue === '');

function close(restoreFocus = true) {
  open.value = false;
  query.value = '';
  if (restoreFocus && !props.disabled) trigger.value?.focus({ preventScroll: true });
}
async function reveal() {
  if (props.disabled) return;
  query.value = '';
  activeIndex.value = choices.value.findIndex(option => option.value === props.modelValue && !option.disabled);
  if (activeIndex.value < 0) activeIndex.value = choices.value.findIndex(option => !option.disabled);
  open.value = true;
  await nextTick();
  if (searchable.value) searchInput.value?.$el?.focus();
}
function select(option) {
  if (props.disabled || option.disabled) return;
  // Keep numeric ids, null and booleans intact; selecting never submits a form.
  if (option.value !== props.modelValue) emit('update:modelValue', option.value);
  close();
}
function onKeydown(event) {
  if (props.disabled) return;
  if (event.key === 'Tab') { close(false); return; }
  if (event.key === 'Escape' && open.value) { event.preventDefault(); event.stopPropagation(); close(); return; }
  const inSearch = event.target.tagName === 'INPUT';
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(event.key) || (inSearch && event.key === ' ')) return;
  event.preventDefault();
  if (!open.value) { reveal(); return; }
  if (event.key === 'Enter' || event.key === ' ') {
    if (filtered.value[activeIndex.value]) select(filtered.value[activeIndex.value]);
    return;
  }
  const enabled = filtered.value.map((option, index) => option.disabled ? -1 : index).filter(index => index >= 0);
  if (!enabled.length) return;
  const current = enabled.indexOf(activeIndex.value);
  if (event.key === 'Home') activeIndex.value = enabled[0];
  else if (event.key === 'End') activeIndex.value = enabled.at(-1);
  else activeIndex.value = enabled[(current + (event.key === 'ArrowDown' ? 1 : -1) + enabled.length) % enabled.length];
  nextTick(() => document.getElementById(`${controlId.value}-option-${activeIndex.value}`)?.scrollIntoView?.({ block: 'nearest' }));
}
watch(query, () => { activeIndex.value = filtered.value.findIndex(option => !option.disabled); });
watch(() => props.disabled, disabled => { if (disabled) close(false); });
watch(() => props.modelValue, () => close(false));
</script>

<template>
  <div ref="owner" class="relative min-w-0" :class="attrs.class" :style="attrs.style">
    <!-- design-tokens: allow-raw-button — the trigger is a single-choice form control. -->
    <button
      v-bind="controlAttrs" :id="controlId" ref="trigger" type="button" role="combobox"
      aria-haspopup="listbox" :aria-expanded="open" :aria-controls="open ? `${controlId}-options` : undefined"
      :aria-activedescendant="open && activeIndex >= 0 ? `${controlId}-option-${activeIndex}` : undefined"
      :aria-required="required || undefined" :aria-invalid="error || undefined" :disabled="disabled"
      :title="disabled ? disabledReason : undefined"
      :class="[INPUT_FIELD_BASE, INPUT_FIELD_SIZE[size], error ? INPUT_FIELD_ERROR : '', triggerClass]"
      class="flex min-h-11 w-full items-center justify-between gap-2 text-left disabled:cursor-not-allowed disabled:opacity-60"
      @click="open ? close() : reveal()" @keydown="onKeydown"
    >
      <span class="min-w-0 truncate">{{ selected?.label || placeholder || t('global.choiceSelect.placeholder') }}</span>
      <BaseActionIcon :action="open ? 'collapse' : 'expand'" class="shrink-0" />
    </button>
    <input
      v-if="required" class="sr-only" tabindex="-1" aria-hidden="true" :value="emptyValue ? '' : 'selected'"
      :disabled="disabled" required @invalid.prevent="trigger?.focus()"
    >
    <BaseFloatingListbox
      :id="`${controlId}-options`" :open="open && !disabled" :anchor="trigger" :owner="owner"
      :aria-label="attrs['aria-label'] || selected?.label || placeholder || t('global.choiceSelect.placeholder')"
      @close="close()"
    >
      <div @keydown="onKeydown">
        <div v-if="searchable" class="border-b border-border-muted p-2">
          <BaseInput ref="searchInput" v-model="query" type="search" :aria-label="t('global.choiceSelect.search')" :placeholder="t('global.choiceSelect.search')" />
        </div>
        <template v-for="(option, index) in filtered" :key="`${typeof option.value}:${String(option.value)}`">
          <p v-if="option.group && option.group !== filtered[index - 1]?.group" role="presentation" class="px-3 pt-3 text-xs font-semibold text-text-muted">{{ option.group }}</p>
          <!-- design-tokens: allow-raw-button — listbox options expose their selection state. -->
          <button
            :id="`${controlId}-option-${index}`" type="button" role="option" tabindex="-1"
            :aria-selected="option.value === modelValue" :disabled="option.disabled" :title="option.disabledReason"
            class="flex min-h-11 w-full items-center gap-2 px-3 py-2 text-left text-sm text-text-default hover:bg-surface-raised disabled:cursor-not-allowed disabled:opacity-60"
            :class="option.value === modelValue || index === activeIndex ? 'bg-primary-soft' : ''"
            @click="select(option)"
          >
            <span class="min-w-0 flex-1 break-words">{{ option.label }}</span>
            <BaseActionIcon v-if="option.value === modelValue" action="complete" class="shrink-0" />
          </button>
        </template>
        <p v-if="!filtered.length" class="px-3 py-4 text-sm text-text-muted" role="status">{{ t('global.choiceSelect.empty') }}</p>
      </div>
    </BaseFloatingListbox>
  </div>
</template>
