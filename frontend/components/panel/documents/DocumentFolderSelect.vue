<template>
  <BaseFormField :label="label" :for="inputId" :hint="showHint ? 'Opcional.' : ''">
    <div ref="wrapperRef" class="relative">
      <div class="relative">
        <span
          class="absolute inset-y-0 left-0 flex items-center pl-3 text-text-subtle pointer-events-none"
        >
          <MagnifyingGlassIcon class="w-4 h-4" />
        </span>
        <input
          :id="inputId"
          ref="inputRef"
          v-model="inputText"
          type="text"
          :placeholder="placeholder"
          :disabled="disabled"
          :title="disabled ? disabledReason || undefined : committedLabel || undefined"
          :data-testid="testid"
          autocomplete="off"
          class="w-full pl-9 pr-9 py-2.5 border border-input-border bg-input-bg text-input-text placeholder:text-text-subtle rounded-xl text-sm text-ellipsis focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none disabled:opacity-60 disabled:cursor-not-allowed"
          role="combobox"
          :aria-expanded="isOpen"
          :aria-controls="isOpen ? listboxId : undefined"
          :aria-activedescendant="activeOptionId"
          aria-autocomplete="list"
          aria-haspopup="listbox"
          @input="onInput"
          @focus="openCatalog"
          @click="openCatalog"
          @keydown.down.prevent="onArrowDown"
          @keydown.up.prevent="onArrowUp"
          @keydown.enter.prevent="onEnter"
          @keydown.esc.prevent="closeDropdown"
          @keydown.tab="closeDropdown"
        >
        <BaseButton
          unstyled
          icon-only
          v-if="!disabled && (committedId != null || inputText)"
          type="button"
          class="absolute inset-y-0 right-0 flex items-center pr-3 text-text-subtle hover:text-text-default transition-colors"
          aria-label="Quitar carpeta"
          title="Quitar carpeta"
          :data-testid="`${testid}-clear`"
          @click="clearSelection"
        >
          <BaseActionIcon action="clear" />
        </BaseButton>
      </div>

      <BaseFloatingListbox
        :id="listboxId"
        :open="isOpen"
        :anchor="inputRef"
        :owner="wrapperRef"
        @close="closeDropdown"
      >
        <div v-if="isLoading" class="px-4 py-3 text-sm text-text-subtle text-center">
          Cargando carpetas...
        </div>

        <div
          v-else-if="loadFailed"
          class="px-4 py-3 text-sm text-text-muted"
          :data-testid="`${testid}-error`"
        >
          <p class="mb-2">No se pudieron cargar las carpetas.</p>
          <BaseButton
            type="button"
            variant="secondary"
            size="sm"
            :data-testid="`${testid}-retry`"
            @click="retryLoad"
          >
            Reintentar
          </BaseButton>
        </div>

        <!-- Filtrado local: el árbol entero ya está en el store. -->
        <ul v-else-if="visibleOptions.length > 0" role="presentation" class="divide-y divide-border-muted">
          <li
            v-for="(option, idx) in visibleOptions"
            :id="optionDomId(option.id)"
            :key="option.id"
            :data-testid="`${testid}-option-${option.id}`"
            :title="option.pathLabel"
            :class="[
              'px-4 py-2.5 cursor-pointer transition-colors',
              highlightIndex === idx ? 'bg-primary-soft' : 'hover:bg-surface-raised',
            ]"
            role="option"
            :aria-selected="highlightIndex === idx"
            @click="selectOption(option)"
            @mouseenter="highlightIndex = idx"
          >
            <p class="truncate text-sm text-text-default">{{ option.name }}</p>
            <!-- Los nombres se repiten a propósito (cada proyecto tiene su
                 «Entregables»): la ubicación y el dueño son los que distinguen. -->
            <p
              class="truncate text-xs text-text-subtle"
              :data-testid="`${testid}-detail-${option.id}`"
            >
              {{ option.detail }}
            </p>
          </li>
        </ul>

        <p v-else class="px-4 py-3 text-sm text-text-muted" :data-testid="`${testid}-empty`">
          {{ term ? `Sin carpetas que coincidan con "${term}".` : 'No hay carpetas todavía.' }}
        </p>
      </BaseFloatingListbox>
    </div>
  </BaseFormField>
</template>

<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue';
import { MagnifyingGlassIcon } from '@heroicons/vue/24/outline';
import BaseFloatingListbox from '~/components/base/BaseFloatingListbox.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import { useDocumentFolderStore } from '~/stores/document_folders';
import {
  buildFolderPickerOptions,
  filterFolderPickerOptions,
  folderPathLabel,
} from '~/utils/folderOptions';

/**
 * Selector de la carpeta de un documento, con el mismo patrón que
 * ClientAutocomplete y ProjectSelect: campo de búsqueda y lista de resultados.
 *
 * Cada resultado muestra su ubicación, su dueño y el estado del proyecto cuando
 * no es el operativo, porque los nombres se repiten por diseño. Las carpetas
 * del archivado automático no se ofrecen: el backend las rechaza como destino.
 *
 * Lee el store; cargarlo es de la página, salvo el reintento explícito cuando
 * la lectura falló. Emite únicamente cuando el operador elige o quita una
 * carpeta: resolver el rótulo nunca escribe el modelo, así un formulario
 * abierto dentro de una carpeta no nace modificado.
 */
const props = defineProps({
  modelValue: { type: [Number, String], default: null },
  label: { type: String, default: 'Carpeta' },
  testid: { type: String, default: 'document-folder-select' },
  disabled: { type: Boolean, default: false },
  disabledReason: { type: String, default: '' },
  showHint: { type: Boolean, default: true },
});

const emit = defineEmits(['update:modelValue', 'select']);

const store = useDocumentFolderStore();

const wrapperRef = ref(null);
const inputRef = ref(null);
const baseId = useId();
const inputId = `${baseId}-input`;
const listboxId = `${baseId}-listbox`;
const isOpen = ref(false);
// Al abrir se ve el catálogo completo; sólo lo que se teclea después filtra.
const filtering = ref(false);
const inputText = ref('');
// La ruta de la carpeta REALMENTE elegida, separada de lo que se teclea encima:
// es lo que se restaura al cerrar sin elegir.
const committedLabel = ref('');
const highlightIndex = ref(-1);

const list = computed(() => (Array.isArray(store.folders) ? store.folders : []));
const options = computed(() => buildFolderPickerOptions(list.value));
const term = computed(() => (filtering.value ? inputText.value.trim() : ''));
const visibleOptions = computed(() => filterFolderPickerOptions(options.value, term.value));
const isLoading = computed(() => Boolean(store.isLoading) && list.value.length === 0);
// Una lectura fallida se dice y se puede reintentar, como en ClientAutocomplete:
// «no hay carpetas» sería falso.
const loadFailed = computed(() => (
  store.error === 'fetch_folders_failed' && !store.isLoading && list.value.length === 0
));

const committedId = computed(() => {
  if (props.modelValue == null || props.modelValue === '') return null;
  const id = Number(props.modelValue);
  return Number.isInteger(id) ? id : null;
});

const placeholder = computed(() => (
  isOpen.value && committedLabel.value
    ? committedLabel.value
    : 'Sin carpeta — busca por nombre o ruta…'
));

const activeOptionId = computed(() => {
  if (!isOpen.value) return undefined;
  const option = visibleOptions.value[highlightIndex.value];
  return option ? optionDomId(option.id) : undefined;
});

function optionDomId(id) {
  return `${baseId}-option-${id}`;
}

function resolveCommittedLabel() {
  if (committedId.value == null) return '';
  const label = folderPathLabel(list.value, committedId.value);
  if (label) return label;
  // Mientras llega la lista no se inventa nada: queda el rótulo que había.
  if (store.isLoading) return committedLabel.value;
  return `Carpeta #${committedId.value}`;
}

function syncLabel() {
  committedLabel.value = resolveCommittedLabel();
  if (!isOpen.value) inputText.value = committedLabel.value;
}

watch([committedId, options, () => store.isLoading], syncLabel, { immediate: true });

watch(() => props.disabled, (disabled) => {
  if (disabled && isOpen.value) closeDropdown();
});

function retryLoad() {
  store.fetchFolders();
}

function scrollHighlightedIntoView() {
  const option = visibleOptions.value[highlightIndex.value];
  if (!option || typeof document === 'undefined') return;
  document.getElementById(optionDomId(option.id))?.scrollIntoView?.({ block: 'nearest' });
}

// Reabrir un campo ya elegido muestra todo el catálogo con la carpeta actual
// marcada: filtrar por su ruta dejaría una sola fila. Lo elegido pasa al
// placeholder, así se sigue viendo mientras se busca otra.
function openCatalog() {
  if (props.disabled || isOpen.value) return;
  filtering.value = false;
  inputText.value = '';
  isOpen.value = true;
  highlightIndex.value = visibleOptions.value.findIndex((option) => option.id === committedId.value);
  nextTick(scrollHighlightedIntoView);
}

function closeDropdown() {
  isOpen.value = false;
  filtering.value = false;
  highlightIndex.value = -1;
  inputText.value = committedLabel.value;
}

function onInput() {
  // Escribir filtra, no desvincula: para quitar la carpeta está la X.
  isOpen.value = true;
  filtering.value = true;
  highlightIndex.value = visibleOptions.value.length > 0 ? 0 : -1;
}

function selectOption(option) {
  committedLabel.value = option.pathLabel;
  inputText.value = option.pathLabel;
  isOpen.value = false;
  filtering.value = false;
  highlightIndex.value = -1;
  emit('update:modelValue', option.id);
  emit('select', list.value.find((folder) => Number(folder.id) === option.id) || null);
}

function clearSelection() {
  const hadFolder = committedId.value != null;
  committedLabel.value = '';
  inputText.value = '';
  filtering.value = false;
  if (hadFolder) {
    emit('update:modelValue', null);
    emit('select', null);
  }
  // Después del render del padre: así el catálogo ya no marca la que se quitó.
  nextTick(() => inputRef.value?.focus());
}

function onArrowDown() {
  if (!isOpen.value) {
    openCatalog();
    return;
  }
  const count = visibleOptions.value.length;
  if (!count) return;
  highlightIndex.value = (highlightIndex.value + 1) % count;
  nextTick(scrollHighlightedIntoView);
}

function onArrowUp() {
  const count = visibleOptions.value.length;
  if (!isOpen.value || !count) return;
  highlightIndex.value = highlightIndex.value <= 0 ? count - 1 : highlightIndex.value - 1;
  nextTick(scrollHighlightedIntoView);
}

function onEnter() {
  if (!isOpen.value) return;
  const option = visibleOptions.value[highlightIndex.value];
  if (option) selectOption(option);
}
</script>
