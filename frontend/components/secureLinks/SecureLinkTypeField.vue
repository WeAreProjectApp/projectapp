<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue';
import BaseActionIcon from '~/components/base/BaseActionIcon.vue';
import BaseFloatingListbox from '~/components/base/BaseFloatingListbox.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import { INPUT_FIELD_BASE, INPUT_FIELD_SIZE } from '~/components/base/inputClasses';

const props = defineProps({
  modelValue: { type: String, default: '' },
  customName: { type: String, default: '' },
  types: { type: Array, default: () => [] },
  language: { type: String, default: 'es' },
  disabled: { type: Boolean, default: false },
  disabledReason: { type: String, default: '' },
  error: { type: String, default: '' },
  customError: { type: String, default: '' },
  testid: { type: String, default: 'secure-link-type' },
});
const emit = defineEmits(['update:modelValue', 'update:customName']);
const { t } = useI18n();
const id = useId();
const owner = ref(null);
const trigger = ref(null);
const open = ref(false);
const activeIndex = ref(0);
const choices = computed(() => props.types.map(type => ({
  value: type.key, label: props.language === 'en' ? type.label_en : type.label_es,
})));
const selectedLabel = computed(() => choices.value.find(choice => choice.value === props.modelValue)?.label || '');

function close(restoreFocus = true) {
  open.value = false;
  if (restoreFocus && !props.disabled) trigger.value?.focus({ preventScroll: true });
}
watch(() => props.disabled, disabled => { if (disabled) close(false); });
watch(() => props.modelValue, () => close(false));

async function revealOption() {
  await nextTick();
  document.getElementById(`${id}-option-${activeIndex.value}`)?.scrollIntoView?.({ block: 'nearest' });
}
function openList() {
  if (props.disabled || !choices.value.length) return;
  activeIndex.value = Math.max(0, choices.value.findIndex(choice => choice.value === props.modelValue));
  open.value = true;
  revealOption();
}
async function select(value) {
  if (props.disabled) return;
  emit('update:modelValue', value);
  close();
  if (value === 'custom') {
    await nextTick();
    document.getElementById(`${id}-custom`)?.focus();
  }
}
function onKeydown(event) {
  if (props.disabled || !choices.value.length) return;
  if (event.key === 'Tab') { close(false); return; }
  if (event.key === 'Escape' && open.value) { event.preventDefault(); event.stopPropagation(); close(); return; }
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
  else if (wasOpen) activeIndex.value = (activeIndex.value + (event.key === 'ArrowDown' ? 1 : -1) + choices.value.length) % choices.value.length;
  revealOption();
}
</script>

<template>
  <div ref="owner" class="min-w-0 space-y-3">
    <BaseFormField v-slot="{ invalid, errorId }" :label="t('secureLinks.type')" :for="id" required :error="error">
      <button
        :id="id" ref="trigger" type="button" role="combobox" aria-haspopup="listbox" aria-required="true"
        :aria-expanded="open" :aria-controls="open ? `${id}-options` : undefined"
        :aria-activedescendant="open ? `${id}-option-${activeIndex}` : undefined"
        :aria-invalid="invalid || undefined" :aria-describedby="errorId"
        :disabled="disabled" :aria-disabled="disabled" :title="disabled ? disabledReason : undefined"
        :class="[INPUT_FIELD_BASE, INPUT_FIELD_SIZE.sm]"
        class="flex min-h-11 items-center justify-between gap-2 text-left"
        :data-testid="testid" @click="open ? close() : openList()" @keydown="onKeydown"
      >
        <span class="min-w-0 break-words">{{ selectedLabel }}</span>
        <BaseActionIcon :action="open ? 'collapse' : 'expand'" class="shrink-0" />
      </button>
    </BaseFormField>
    <BaseFloatingListbox :id="`${id}-options`" :open="open && !disabled" :anchor="trigger" :owner="owner" :aria-label="t('secureLinks.type')" @close="close()">
      <!-- design-tokens: allow-raw-button — listbox options have active and selected states. -->
      <button
        v-for="(choice, index) in choices" :id="`${id}-option-${index}`" :key="choice.value"
        type="button" role="option" tabindex="-1" :aria-selected="modelValue === choice.value"
        :disabled="disabled" :title="disabled ? disabledReason : undefined"
        class="flex min-h-11 w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-text-default"
        :class="activeIndex === index ? 'bg-surface-raised' : ''"
        @pointermove="activeIndex = index" @mousedown.prevent @click="select(choice.value)"
      >
        <span class="min-w-0 break-words">{{ choice.label }}</span>
        <BaseActionIcon v-if="modelValue === choice.value" action="complete" class="shrink-0" />
      </button>
    </BaseFloatingListbox>
    <BaseFormField v-if="modelValue === 'custom'" v-slot="{ invalid, errorId }" :label="t('secureLinks.customName')" :for="`${id}-custom`" required :error="customError">
      <BaseInput :id="`${id}-custom`" :model-value="customName" :disabled="disabled" :disabled-reason="disabledReason" :error="invalid" :aria-describedby="errorId" maxlength="200" autocomplete="off" data-testid="secure-link-field-custom_name" @update:model-value="emit('update:customName', $event)" />
    </BaseFormField>
  </div>
</template>
