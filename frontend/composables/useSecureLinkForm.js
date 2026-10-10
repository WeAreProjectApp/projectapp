import { computed, nextTick, ref } from 'vue';
import { useSecureLinksStore } from '~/stores/secure_links';

/**
 * Revealed content (`[{ key, value }]`) as the `{ key: value }` map the form
 * edits. Used by every entry point to "Editar contenido".
 */
export function contentFieldValues(fields = []) {
  return Object.fromEntries(fields.map((field) => [field.key, field.value]));
}

/** Shared catalog loading, validation and visible errors for both creators. */
export function useSecureLinkForm(formElement, selectedType, t) {
  const store = useSecureLinksStore();
  const errors = ref({});
  const generalError = ref('');
  const loadingTypes = ref(false);
  const typesError = ref(false);
  const catalogReady = computed(() => !loadingTypes.value && !typesError.value && Boolean(selectedType.value));

  function resetErrors() {
    errors.value = {};
    generalError.value = '';
  }

  async function loadTypes() {
    if (loadingTypes.value) return;
    loadingTypes.value = true;
    typesError.value = false;
    try {
      const result = await store.fetchTypes();
      typesError.value = !result.success || !selectedType.value;
    } finally {
      loadingTypes.value = false;
    }
  }

  function validateFields(values) {
    let total = 0;
    for (const field of selectedType.value?.fields || []) {
      const value = String(values[field.key] ?? '');
      const cleaned = ['secret', 'textarea'].includes(field.kind) ? value : value.trim();
      if (!value.trim()) {
        if (field.required) errors.value[field.key] = t('secureLinks.validation.required');
        continue;
      }
      if ([...cleaned].length > field.max_length) {
        errors.value[field.key] = t('secureLinks.validation.maxLength', { max: field.max_length });
      }
      total += [...cleaned].length;
    }
    // Matches the encrypted-payload limit in secure_links/catalog.py.
    if (total > 20000) generalError.value = t('secureLinks.validation.totalLength');
    return !Object.keys(errors.value).length && !generalError.value;
  }

  async function focusError() {
    await nextTick();
    formElement.value?.querySelector(
      '[aria-invalid="true"], [data-invalid="true"] input, [data-invalid="true"] select, [role="alert"][tabindex="-1"]',
    )?.focus();
  }

  function mapErrors(error, visibleKeys) {
    const visible = new Set(visibleKeys);
    const unhandled = [];
    errors.value = {};
    for (const [key, value] of Object.entries(error?.fieldErrors || {})) {
      const message = Array.isArray(value) ? value[0] : value;
      if (typeof message !== 'string' || !message) continue;
      if (visible.has(key)) errors.value[key] = message;
      else unhandled.push(message);
    }
    generalError.value = unhandled.join(' ') || (
      Object.keys(errors.value).length ? '' : error?.message || t('secureLinks.genericError')
    );
    focusError();
  }

  return { errors, generalError, loadingTypes, typesError, catalogReady, loadTypes, resetErrors, validateFields, mapErrors, focusError };
}
