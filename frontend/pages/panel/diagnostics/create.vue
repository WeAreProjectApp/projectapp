<template>
  <div class="max-w-2xl mx-auto">
    <header class="mb-6">
      <BaseButton
        as="NuxtLink"
        :to="localePath('/panel/diagnostics')"
        variant="link"
        size="sm"
      >
        <BaseActionIcon action="back" />
        Diagnósticos
      </BaseButton>
      <h1 class="text-2xl font-light text-text-default mt-1">Nuevo diagnóstico de aplicación</h1>
      <p class="text-sm text-text-muted mt-1">
        Crea un diagnóstico para un cliente existente. Podrás completar pricing, radiografía y documentos después.
      </p>
    </header>

    <form
      class="bg-surface rounded-2xl shadow-sm border border-border-muted p-6 space-y-6"
      @submit.prevent="submit"
    >
      <UnsavedChangesNotice
        v-if="hasChanges"
        :title="unsavedTitle"
        :detail="unsavedDetail"
        message="Este diagnóstico todavía no existe. Si sales de esta página, se pierde."
        :can-save="false"
        :can-discard="false"
        testid="diagnostic-create-unsaved-notice"
      />

      <BaseFormField
        label="Cliente"
        hint="Busca por nombre, email o empresa. Solo clientes existentes pueden recibir un diagnóstico."
      >
        <ClientAutocomplete
          v-model="selectedClientId"
          placeholder="Buscar cliente por nombre, email o empresa..."
          test-id="diagnostic-client-autocomplete"
          @select="onClientSelected"
        />
      </BaseFormField>

      <BaseFormField label="Idioma" for="diagnostic-create-language">
        <BaseChoiceSelect
          id="diagnostic-create-language"
          v-model="language"
          :options="[
            { value: 'es', label: 'Español' },
            { value: 'en', label: 'English' },
          ]"
        />
      </BaseFormField>

      <BaseFormField label="Título">
        <BaseInput
          v-model="title"
          placeholder="Se generará automáticamente si lo dejas vacío"
        />
      </BaseFormField>

      <BaseAlert v-if="errorMsg" variant="danger">{{ errorMsg }}</BaseAlert>

      <div class="text-right">
        <BaseButton
          type="submit"
          variant="primary"
          :loading="store.isUpdating"
          :disabled="!selectedClientId || store.isUpdating"
          data-testid="diagnostic-submit-btn"
        >
          Crear diagnóstico
        </BaseButton>
      </div>
    </form>

    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      :require-type-text="confirmState.requireTypeText"
      :hide-cancel="confirmState.hideCancel"
      :secondary-text="confirmState.secondaryText"
      :secondary-variant="confirmState.secondaryVariant"
      :secondary-hint="confirmState.secondaryHint"
      :loading="confirmState.busy"
      @confirm="handleConfirmed"
      @secondary="handleSecondaryAction"
      @cancel="handleCancelled"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useDiagnosticsStore } from '~/stores/diagnostics';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import UnsavedChangesNotice from '~/components/panel/UnsavedChangesNotice.vue';
import { useUnsavedGuard } from '~/composables/useUnsavedGuard';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const localePath = useLocalePath();
const router = useRouter();
const store = useDiagnosticsStore();

const selectedClientId = ref(null);
const selectedClientName = ref('');
const language = ref('es');
const titleOverride = ref(null);
const title = computed({
  get() {
    if (titleOverride.value !== null) return titleOverride.value;
    if (!selectedClientId.value || !selectedClientName.value) return '';
    const prefix = language.value === 'en' ? 'Diagnostic' : 'Diagnóstico';
    return `${prefix} — ${selectedClientName.value}`;
  },
  set(value) { titleOverride.value = value; },
});
const errorMsg = ref('');

const FALLBACK_ERROR = 'No se pudo crear el diagnóstico. Verifica tu sesión e inténtalo de nuevo.';

// Refs sueltos, sin objeto `form`: por eso el snapshot los junta a mano.
// `save` en null porque submit navega al editor del diagnóstico creado.
const {
  hasChanges,
  unsavedTitle,
  unsavedDetail,
  commit: commitBaseline,
  confirmState,
  handleConfirmed,
  handleSecondaryAction,
  handleCancelled,
} = useUnsavedGuard({
  snapshot: () => ({
    client: selectedClientId.value,
    language: language.value,
    title: title.value,
  }),
  labels: { client: 'cliente', language: 'idioma', title: 'título' },
});
commitBaseline();

function onClientSelected(client) {
  errorMsg.value = '';
  selectedClientName.value = client?.name || client?.company || client?.email || '';
}

async function submit() {
  errorMsg.value = '';
  if (!selectedClientId.value) {
    errorMsg.value = 'Selecciona un cliente antes de continuar.';
    return;
  }
  const result = await store.create({
    client_id: selectedClientId.value,
    language: language.value,
    title: title.value.trim(),
  });
  if (!result.success) {
    errorMsg.value = result.message || FALLBACK_ERROR;
    return;
  }
  // Ya está creado: desarma el guard antes de ir al editor.
  commitBaseline();
  router.push(localePath(`/panel/diagnostics/${result.data.id}/edit`));
}
</script>
