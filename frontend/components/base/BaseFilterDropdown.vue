<template>
  <div ref="containerRef" class="relative">
    <button
      type="button"
      class="inline-flex min-h-10 w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring/40"
      :class="isActive
        ? 'border-primary bg-primary-soft text-text-brand'
        : 'border-border-default bg-surface text-text-default hover:border-text-muted'"
      :aria-expanded="isOpen"
      aria-haspopup="dialog"
      :data-testid="testId || undefined"
      @click="toggleOpen"
      @keydown.down.prevent="openAndFocusOptions"
    >
      <span class="min-w-0 truncate">{{ triggerLabel }}</span>
      <span class="flex shrink-0 items-center gap-1.5">
        <span
          v-if="modelValue.length && !single"
          class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-2xs font-semibold text-white"
        >{{ modelValue.length }}</span>
        <BaseActionIcon :action="isOpen ? 'collapse' : 'expand'" class="h-3.5 w-3.5" />
      </span>
    </button>

    <Transition name="base-filter-dropdown">
      <div
        v-if="isOpen"
        ref="panelRef"
        class="absolute left-0 top-full z-50 mt-1 w-[min(20rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-border-default bg-surface shadow-raised"
        role="dialog"
        :aria-label="label"
        @keydown="onPanelKeydown"
      >
        <div v-if="searchable" class="border-b border-border-muted p-2">
          <BaseInput
            ref="searchInputRef"
            v-model="query"
            size="sm"
            :placeholder="`Buscar en ${label.toLowerCase()}...`"
            :aria-label="`Buscar en ${label}`"
          />
        </div>

        <div class="max-h-64 overflow-y-auto py-1" role="group" :aria-label="label">
          <label
            v-for="option in filteredOptions"
            :key="String(option.value)"
            class="flex min-h-10 cursor-pointer items-center gap-2.5 px-3 py-2 text-sm text-text-default hover:bg-surface-raised"
            :class="option.disabled ? 'cursor-not-allowed opacity-50' : ''"
          >
            <input
              type="checkbox"
              :value="option.value"
              :checked="modelValue.includes(option.value)"
              :disabled="option.disabled"
              :title="option.disabled ? 'No hay hilos disponibles con esta combinación de filtros.' : undefined"
              class="h-4 w-4 rounded border-input-border accent-primary focus:ring-focus-ring/30"
              @change="toggle(option.value)"
            >
            <span class="min-w-0 flex-1 truncate" :title="option.label">{{ option.label }}</span>
            <span
              v-if="typeof option.count === 'number'"
              class="shrink-0 text-xs tabular-nums text-text-subtle"
              :title="`${option.count} hilos con esta opción`"
            >{{ option.count }}</span>
          </label>
          <p v-if="filteredOptions.length === 0" class="px-3 py-5 text-center text-sm text-text-subtle">
            No hay opciones que coincidan.
          </p>
        </div>

        <div class="flex items-center justify-between border-t border-border-muted px-3 py-2">
          <span class="text-xs text-text-subtle">
            {{ modelValue.length ? `${modelValue.length} seleccionada${modelValue.length === 1 ? '' : 's'}` : 'Todas' }}
          </span>
          <BaseButton
            variant="link"
            size="sm"
            :disabled="modelValue.length === 0"
            disabled-reason="No hay valores seleccionados."
            @click="clear"
          >
            Limpiar
          </BaseButton>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { onClickOutside } from '@vueuse/core';

const props = defineProps({
  label: { type: String, required: true },
  options: { type: Array, required: true },
  modelValue: { type: Array, default: () => [] },
  searchable: { type: Boolean, default: true },
  single: { type: Boolean, default: false },
  testId: { type: String, default: '' },
});

const emit = defineEmits(['update:modelValue']);
const containerRef = ref(null);
const panelRef = ref(null);
const searchInputRef = ref(null);
const isOpen = ref(false);
const query = ref('');

const isActive = computed(() => props.modelValue.length > 0);
const selectedLabels = computed(() => props.options
  .filter((option) => props.modelValue.includes(option.value))
  .map((option) => option.label));
const triggerLabel = computed(() => {
  if (selectedLabels.value.length === 1) return `${props.label}: ${selectedLabels.value[0]}`;
  return props.label;
});
const filteredOptions = computed(() => {
  const normalized = query.value.trim().toLocaleLowerCase('es');
  if (!normalized) return props.options;
  return props.options.filter((option) => (
    option.label.toLocaleLowerCase('es').includes(normalized)
  ));
});

onClickOutside(containerRef, () => { isOpen.value = false; });
watch(isOpen, (open) => {
  if (!open) query.value = '';
});

function toggleOpen() {
  isOpen.value = !isOpen.value;
  if (isOpen.value && props.searchable) {
    nextTick(() => searchInputRef.value?.$el?.focus());
  }
}

async function openAndFocusOptions() {
  isOpen.value = true;
  await nextTick();
  panelRef.value?.querySelector('input[type="checkbox"]')?.focus();
}

function toggle(value) {
  if (props.single) {
    emit('update:modelValue', [value]);
    isOpen.value = false;
    return;
  }
  if (props.modelValue.includes(value)) {
    emit('update:modelValue', props.modelValue.filter((item) => item !== value));
  } else {
    emit('update:modelValue', [...props.modelValue, value]);
  }
}

function clear() {
  emit('update:modelValue', []);
}

function onPanelKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault();
    isOpen.value = false;
    containerRef.value?.querySelector('button')?.focus();
    return;
  }
  if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
  const options = [...panelRef.value.querySelectorAll('input[type="checkbox"]:not(:disabled)')];
  const current = options.indexOf(document.activeElement);
  if (current === -1) return;
  event.preventDefault();
  const delta = event.key === 'ArrowDown' ? 1 : -1;
  options[(current + delta + options.length) % options.length]?.focus();
}
</script>

<style scoped>
.base-filter-dropdown-enter-active,
.base-filter-dropdown-leave-active {
  transition: opacity 120ms ease, transform 120ms ease;
}
.base-filter-dropdown-enter-from,
.base-filter-dropdown-leave-to {
  opacity: 0;
  transform: translateY(-0.25rem);
}
@media (prefers-reduced-motion: reduce) {
  .base-filter-dropdown-enter-active,
  .base-filter-dropdown-leave-active {
    transition: none;
  }
}
</style>
