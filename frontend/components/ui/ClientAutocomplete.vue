<template>
  <div ref="wrapperRef" class="relative">
    <!-- Input -->
    <div class="relative">
      <span
        class="absolute inset-y-0 left-0 flex items-center pl-3 text-text-subtle pointer-events-none"
      >
        <MagnifyingGlassIcon class="w-4 h-4" />
      </span>
      <input
        ref="inputRef"
        v-model="inputText"
        :type="isCatalog ? 'search' : 'text'"
        :placeholder="placeholder"
        :disabled="disabled"
        :required="required"
        :title="disabled && disabledReason ? disabledReason : undefined"
        :data-testid="testId"
        autocomplete="off"
        :class="[
          'w-full pl-9 pr-9 py-2.5 border bg-input-bg text-input-text placeholder:text-text-subtle rounded-xl text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none',
          error ? 'border-danger-strong' : 'border-input-border',
        ]"
        @input="onInput"
        @focus="onFocus"
        @keydown.down.prevent="onArrowDown"
        @keydown.up.prevent="onArrowUp"
        @keydown.enter.prevent="onEnter"
        @keydown.esc="onEscape"
        :role="isCatalog ? 'searchbox' : 'combobox'"
        :aria-expanded="isCatalog ? undefined : isOpen"
        :aria-controls="isCatalog || isOpen ? listboxId : undefined"
        :aria-busy="isSearching || isLoadingMore"
        :aria-autocomplete="isCatalog ? undefined : 'list'"
        :aria-haspopup="isCatalog ? undefined : 'listbox'"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="errorDescribedBy || undefined"
      />
      <!-- In catalog mode this clears only the filter; selecting a client and
           filtering the visible catalog are deliberately independent acts. -->
      <BaseButton
        unstyled
        icon-only
        v-if="!disabled && (isCatalog ? inputText : (modelValue || inputText))"
        type="button"
        class="absolute inset-y-0 right-0 flex items-center pr-3 text-text-subtle hover:text-text-default transition-colors"
        :aria-label="isCatalog
          ? 'Limpiar búsqueda'
          : (clearLabel || ($t ? $t('global.clearClientSelection') : 'Limpiar'))"
        :title="isCatalog
          ? 'Limpiar búsqueda'
          : (clearLabel || ($t ? $t('global.clearClientSelection') : 'Limpiar'))"
        @click="isCatalog ? clearCatalogFilter() : clearSelection()"
      >
        <BaseActionIcon action="clear" />
      </BaseButton>
    </div>

    <!-- Linked client hint (id beside the name) -->
    <p
      v-if="modelValue && showLinkedHint"
      class="text-xs text-text-subtle mt-1"
      data-testid="client-autocomplete-linked"
    >
      Cliente enlazado: {{ committedLabel }} <span class="tabular-nums">(#{{ modelValue }})</span>
    </p>

    <!-- Default form presentation: a modal-owned floating listbox. -->
    <BaseFloatingListbox
      v-if="!isCatalog"
      :id="listboxId"
      :open="isOpen"
      :anchor="inputRef"
      :owner="wrapperRef"
      @close="closeDropdown"
      @reach-end="loadMore"
    >
      <ClientAutocompleteResults
        v-bind="resultsProps"
        @create-new="emitCreateNew"
        @highlight="highlightIndex = $event"
        @load-more="loadMore"
        @retry="retrySearch"
        @select="selectClient"
      />
    </BaseFloatingListbox>

    <!-- Bulk-decision presentation: permanent in-flow catalog. The header is
         outside the five-row scroller, so the modal never reserves an empty
         dropdown-sized block and never becomes the catalog's scrollbar. -->
    <div
      v-else
      :id="listboxId"
      role="grid"
      aria-label="Clientes disponibles"
      class="mt-2 overflow-hidden rounded-xl border border-border-default bg-surface"
      data-testid="client-catalog"
    >
      <ClientAutocompleteResults
        v-bind="resultsProps"
        @create-new="emitCreateNew"
        @highlight="highlightIndex = $event"
        @load-more="loadMore"
        @retry="retrySearch"
        @select="selectClient"
        @toggle-sort="toggleCatalogSort"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import {
  MagnifyingGlassIcon,
} from '@heroicons/vue/24/outline';
import BaseFloatingListbox from '~/components/base/BaseFloatingListbox.vue';
import ClientAutocompleteResults from '~/components/ui/ClientAutocompleteResults.vue';
import { useProposalClientsStore } from '~/stores/proposal_clients';

/**
 * Searchable client picker for the proposal create/edit forms.
 *
 * Two-way binds the selected client id via v-model. When the user picks a
 * row from the dropdown, the parent receives the **full** client object via
 * the `select` event so it can auto-fill snapshot fields (email, phone,
 * company) on the proposal form.
 *
 * Consumers that support inline creation opt in with `allowCreate`. The
 * dropdown then keeps a visible "Crear nuevo" action even when matching
 * clients exist, so the escape hatch is discoverable before an error.
 */

const props = defineProps({
  modelValue: { type: [Number, null], default: null },
  /** Pre-fill input when editing an existing proposal that already has a client. */
  initialLabel: { type: String, default: '' },
  placeholder: { type: String, default: 'Buscar cliente por nombre, email o empresa...' },
  clearLabel: { type: String, default: '' },
  testId: { type: String, default: 'client-autocomplete-input' },
  /**
   * Los layouts de barra pintan su propia línea de estado y necesitan que el
   * alto del picker sea constante: el hint en flujo hace crecer la celda del
   * flex y arrastra el input fuera de línea con los botones de al lado.
   */
  showLinkedHint: { type: Boolean, default: true },
  /** Floating combobox for forms; permanent catalog for bulk decisions. */
  presentation: {
    type: String,
    default: 'floating',
    validator: (value) => ['floating', 'catalog'].includes(value),
  },
  /** Catalog lifecycle. Opening reloads a clean first page without waiting for focus. */
  active: { type: Boolean, default: true },
  /** Browser-local preference key. Empty means A-Z without persistence. */
  sortStorageKey: { type: String, default: '' },
  allowCreate: { type: Boolean, default: false },
  required: { type: Boolean, default: false },
  requiredMessage: { type: String, default: 'Elige un cliente de la lista.' },
  error: { type: Boolean, default: false },
  errorDescribedBy: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  disabledReason: { type: String, default: '' },
});

const emit = defineEmits(['update:modelValue', 'select', 'create-new']);

const clientsStore = useProposalClientsStore();
const PAGE_SIZE = 20;
const isCatalog = computed(() => props.presentation === 'catalog');

function readCatalogSort() {
  if (!props.sortStorageKey || typeof window === 'undefined') return 'asc';
  try {
    return window.localStorage.getItem(props.sortStorageKey) === 'desc' ? 'desc' : 'asc';
  } catch (_error) {
    return 'asc';
  }
}

function persistCatalogSort(direction) {
  if (!props.sortStorageKey || typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(props.sortStorageKey, direction);
  } catch (_error) { /* Browser storage is an enhancement, never a blocker. */ }
}

const wrapperRef = ref(null);
const inputRef = ref(null);
watch(
  () => [props.required, props.modelValue],
  async () => {
    await nextTick();
    inputRef.value?.setCustomValidity(
      props.required && !props.modelValue ? props.requiredMessage : '',
    );
  },
  { immediate: true },
);
const listboxId = `${useId()}-listbox`;
const inputText = ref(props.initialLabel || '');
// El nombre del cliente que está REALMENTE enlazado, separado de lo que se
// teclea encima: es lo que se restaura al cerrar sin elegir y lo que nombra el
// hint mientras se busca.
const committedLabel = ref(props.initialLabel || '');
const isOpen = ref(false);
const hasSearched = ref(false);
const results = ref([]);
const highlightIndex = ref(-1);
const isSearching = ref(false);
const isLoadingMore = ref(false);
const hasMore = ref(false);
const nextOffset = ref(0);
const searchError = ref('');
const loadMoreError = ref('');
const sortDirection = ref(readCatalogSort());
let searchGeneration = 0;

const resultsProps = computed(() => ({
  results: results.value,
  inputText: inputText.value,
  modelValue: props.modelValue,
  highlightIndex: highlightIndex.value,
  hasSearched: hasSearched.value,
  isSearching: isSearching.value,
  isLoadingMore: isLoadingMore.value,
  searchError: searchError.value,
  loadMoreError: loadMoreError.value,
  presentation: props.presentation,
  sortDirection: sortDirection.value,
  allowCreate: props.allowCreate,
}));

// -------------------------------------------------------------------
// Search (debounced 200ms)
// -------------------------------------------------------------------

const runSearch = async (query, { append = false } = {}) => {
  if (append && (!hasMore.value || isSearching.value || isLoadingMore.value)) return;

  const generation = append ? searchGeneration : ++searchGeneration;
  const offset = append ? nextOffset.value : 0;
  if (append) {
    isLoadingMore.value = true;
    loadMoreError.value = '';
  } else {
    isSearching.value = true;
    searchError.value = '';
    loadMoreError.value = '';
    hasSearched.value = false;
    hasMore.value = false;
    nextOffset.value = 0;
  }

  try {
    const paging = {
      offset,
      limit: PAGE_SIZE,
    };
    if (isCatalog.value) {
      paging.order = sortDirection.value === 'desc' ? '-name' : 'name';
    }
    const result = await clientsStore.searchClients(query, paging);
    if (generation !== searchGeneration) return;
    if (result?.cancelled) {
      // Superseded searches are normally rejected after the next generation
      // starts. If an adapter cancels the current request on its own, close the
      // empty layer instead of leaving a permanent "Cargando" state behind.
      if (!append && !isCatalog.value) isOpen.value = false;
      return;
    }
    if (!result?.success) {
      if (append) loadMoreError.value = 'load_failed';
      else searchError.value = 'load_failed';
      return;
    }

    const page = Array.isArray(result.data) ? result.data : [];
    if (append) {
      const knownIds = new Set(results.value.map((client) => client.id));
      results.value = [
        ...results.value,
        ...page.filter((client) => !knownIds.has(client.id)),
      ];
    } else {
      results.value = page;
    }
    nextOffset.value = result.nextOffset ?? offset + page.length;
    hasMore.value = Boolean(result.hasMore);
    hasSearched.value = true;
    if (!append) highlightIndex.value = results.value.length > 0 ? 0 : -1;
  } finally {
    if (generation === searchGeneration) {
      if (append) isLoadingMore.value = false;
      else isSearching.value = false;
    }
  }
};

const debouncedSearch = useDebounceFn(runSearch, 200);

const onInput = () => {
  // Invalidate the request that belongs to the previous text immediately;
  // otherwise it could resolve during the 200 ms debounce window and flash a
  // result set for a query the input no longer contains.
  searchGeneration += 1;
  isOpen.value = true;
  hasSearched.value = false;
  searchError.value = '';
  isSearching.value = true;
  // Escribir es buscar, no desvincular. Soltar el id acá dejaba el formulario
  // sucio por un caracter y, al guardar, desvinculaba al cliente de verdad.
  // Para desvincular está la X (`clearSelection`).
  debouncedSearch(inputText.value.trim());
};

const onFocus = () => {
  isOpen.value = true;
  if (isCatalog.value) return;
  // Skip the auto-search when the parent already committed a selection
  // (editing an existing proposal) — otherwise we'd waste a request.
  if (!hasSearched.value && props.modelValue === null) {
    runSearch(inputText.value.trim());
  }
};

const retrySearch = () => runSearch(inputText.value.trim());

const loadMore = () => runSearch(inputText.value.trim(), { append: true });

// -------------------------------------------------------------------
// Selection
// -------------------------------------------------------------------

const selectClient = (client) => {
  emit('update:modelValue', client.id);
  emit('select', client);
  committedLabel.value = client.name;
  if (isCatalog.value) {
    highlightIndex.value = results.value.findIndex((result) => result.id === client.id);
    return;
  }
  inputText.value = client.name;
  closeDropdown();
};

const clearCatalogFilter = () => {
  searchGeneration += 1;
  inputText.value = '';
  highlightIndex.value = -1;
  runSearch('');
  inputRef.value?.focus();
};

const clearSelection = () => {
  searchGeneration += 1;
  emit('update:modelValue', null);
  emit('select', null);
  inputText.value = '';
  committedLabel.value = '';
  results.value = [];
  hasSearched.value = false;
  hasMore.value = false;
  nextOffset.value = 0;
  searchError.value = '';
  loadMoreError.value = '';
  isSearching.value = false;
  isLoadingMore.value = false;
  highlightIndex.value = -1;
  inputRef.value?.focus();
};

/**
 * `opts` llega como Event desde esc y click-outside; sólo un objeto con
 * `restore: false` explícito apaga la restauración (lo usa "Crear nuevo",
 * donde el texto tecleado es el nombre del cliente por crear).
 */
const closeDropdown = (opts) => {
  if (isCatalog.value) return;
  isOpen.value = false;
  highlightIndex.value = -1;
  const restore = !(opts && opts.restore === false);
  if (restore && props.modelValue !== null && inputText.value !== committedLabel.value) {
    inputText.value = committedLabel.value;
  }
};

// -------------------------------------------------------------------
// Keyboard navigation
// -------------------------------------------------------------------

const onArrowDown = () => {
  if (!isOpen.value) {
    isOpen.value = true;
    if (!hasSearched.value && props.modelValue === null) {
      runSearch(inputText.value.trim());
    }
    return;
  }
  if (results.value.length === 0) return;
  highlightIndex.value =
    (highlightIndex.value + 1) % results.value.length;
};

const onArrowUp = () => {
  if (!isOpen.value || results.value.length === 0) return;
  highlightIndex.value =
    (highlightIndex.value - 1 + results.value.length) % results.value.length;
};

const onEnter = () => {
  if (!isOpen.value) return;
  if (highlightIndex.value >= 0 && results.value[highlightIndex.value]) {
    selectClient(results.value[highlightIndex.value]);
  } else if (
    props.allowCreate
    && hasSearched.value
    && results.value.length === 0
    && inputText.value.trim()
  ) {
    emitCreateNew();
  }
};

const onEscape = (event) => {
  if (isCatalog.value) return;
  event.preventDefault();
  closeDropdown();
};

const toggleCatalogSort = () => {
  sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc';
  persistCatalogSort(sortDirection.value);
  runSearch(inputText.value.trim());
};

// -------------------------------------------------------------------
// Create new
// -------------------------------------------------------------------

const emitCreateNew = () => {
  const typed = inputText.value.trim();
  emit('create-new', typed);
  if (isCatalog.value) return;
  // Lo tecleado ES el nombre del cliente nuevo: se vuelve la etiqueta enlazada
  // en vez de perderse contra el cliente anterior.
  committedLabel.value = typed;
  closeDropdown({ restore: false });
};

// -------------------------------------------------------------------
// External value sync
// -------------------------------------------------------------------

watch(
  () => props.initialLabel,
  (newLabel) => {
    if (isCatalog.value) {
      committedLabel.value = newLabel || '';
      return;
    }
    // Los dos casos del input son excluyentes (uno exige rótulo, el otro que no
    // lo haya), pero NINGUNO puede cortar el watcher: la sincronización de
    // `committedLabel` de más abajo tiene que correr siempre.
    if (!inputText.value && newLabel) {
      inputText.value = newLabel;
    } else if (!newLabel && props.modelValue == null) {
      // Retirar el rótulo con el valor ya vacío es el padre diciendo «esto se
      // fue» — una sugerencia que se retracta, un formulario que se resetea. El
      // input no puede seguir mostrando al cliente anterior: decía tener uno
      // cuando ya no lo tenía. Con un cliente elegido no se toca nada.
      inputText.value = '';
    }
    // El padre reetiqueta tras guardar; sincronizar sin pisar algo que el
    // usuario esté tecleando encima en ese momento.
    //
    // Va SIEMPRE, y ahí estuvo el bug: la hidratación de la página real entra
    // por la primera rama (el documento llega por red, así que el picker nace
    // sin rótulo), y cortar el watcher ahí dejaba `committedLabel` vacío para
    // siempre. Después, al salir del campo, el restore escribía ese vacío y
    // borraba el cliente de la pantalla.
    if (inputText.value === committedLabel.value || !committedLabel.value) {
      committedLabel.value = newLabel || '';
    }
  },
);

watch(
  () => props.active,
  (active) => {
    if (!isCatalog.value) return;
    searchGeneration += 1;
    isOpen.value = active;
    if (!active) return;
    inputText.value = '';
    highlightIndex.value = -1;
    runSearch('');
  },
  { immediate: true },
);

watch(
  () => props.modelValue,
  (clientId, previousClientId) => {
    if (
      !isCatalog.value
      || !props.active
      || clientId == null
      || clientId === previousClientId
      || results.value.some((client) => client.id === clientId)
    ) return;
    // Inline creation happens in the parent modal. Refetching the current
    // query places the new row back into the canonical server order.
    runSearch(inputText.value.trim());
  },
);

</script>
