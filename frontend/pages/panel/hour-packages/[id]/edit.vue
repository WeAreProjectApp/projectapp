<template>
  <div>
    <div class="flex items-center gap-4 mb-8">
      <BaseActionButton as="NuxtLink" :to="localePath('/panel/hour-packages')" action="back" label="Volver a paquetes de requerimientos" />
      <h1 class="text-2xl font-light text-text-default">Editar paquete de requerimientos</h1>
    </div>

    <!-- Loading -->
    <div v-if="hourPackagesStore.isLoading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-focus-ring/30 border-t-focus-ring rounded-full animate-spin" />
    </div>

    <div v-else-if="loadError" class="bg-danger-soft text-danger-strong rounded-xl px-6 py-4 text-sm max-w-3xl">
      No se pudo cargar el paquete. <NuxtLink :to="localePath('/panel/hour-packages')" class="underline">Volver al listado</NuxtLink>
    </div>

    <form v-else class="space-y-6 max-w-3xl" @submit.prevent="handleSubmit">
      <UnsavedChangesNotice
        v-if="hasChanges"
        :title="unsavedTitle"
        :detail="unsavedDetail"
        :can-save="false"
        :can-discard="false"
        testid="hour-package-unsaved-notice"
      />

      <!-- Nationality + derived currency -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label for="hp-nationality" class="block text-sm font-medium text-text-default mb-1">Nacionalidad</label>
          <select id="hp-nationality" v-model="form.nationality" class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all">
            <option value="COL">Colombia</option>
            <option value="EXT">Extranjeros</option>
            <option value="USA">Estados Unidos</option>
          </select>
          <p v-if="fieldErrors.nationality" class="text-xs text-danger-strong mt-1">{{ fieldErrors.nationality }}</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-text-default mb-1">Moneda</label>
          <p class="px-4 py-2.5 rounded-xl border border-border-muted bg-surface-raised text-sm text-text-muted">
            {{ derivedCurrency }} (derivada de la nacionalidad)
          </p>
        </div>
      </div>

      <!-- Bilingual names -->
      <fieldset class="border border-border-default rounded-xl p-5 space-y-4">
        <legend class="text-sm font-medium text-text-default px-2">Nombre y nota</legend>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label for="hp-name-es" class="block text-sm font-medium text-text-default mb-1">Nombre (ES)</label>
            <input id="hp-name-es" v-model="form.name_es" type="text" required class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text placeholder:text-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
            <p v-if="fieldErrors.name_es" class="text-xs text-danger-strong mt-1">{{ fieldErrors.name_es }}</p>
          </div>
          <div>
            <label for="hp-name-en" class="block text-sm font-medium text-text-default mb-1">Name (EN)</label>
            <input id="hp-name-en" v-model="form.name_en" type="text" required class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text placeholder:text-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
            <p v-if="fieldErrors.name_en" class="text-xs text-danger-strong mt-1">{{ fieldErrors.name_en }}</p>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Nota (ES)</label>
            <textarea v-model="form.note_es" rows="2" class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text placeholder:text-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Note (EN)</label>
            <textarea v-model="form.note_en" rows="2" class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text placeholder:text-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" />
          </div>
        </div>
      </fieldset>

      <PackageCompositionFields :model-value="form" :field-errors="fieldErrors" @update:model-value="Object.assign(form, $event)" />

      <!-- Order + active -->
      <div class="flex items-end gap-6">
        <div class="max-w-[200px]">
          <label for="hp-order" class="block text-sm font-medium text-text-default mb-1">Orden</label>
          <input id="hp-order" v-model.number="form.order" type="number" min="0" class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
        </div>
        <label class="flex items-center gap-3 cursor-pointer pb-2.5">
          <input v-model="form.is_active" type="checkbox" class="w-4 h-4 rounded text-text-brand focus:ring-focus-ring/30" />
          <span class="text-sm text-text-default">Activo (se usa al crear propuestas)</span>
        </label>
      </div>

      <p v-if="errorMsg" class="text-sm text-danger-strong">{{ errorMsg }}</p>

      <div class="flex gap-3 pt-4">
        <BaseButton variant="primary" size="md" type="submit" :disabled="hourPackagesStore.isUpdating">
          {{ hourPackagesStore.isUpdating ? 'Guardando...' : 'Guardar cambios' }}
        </BaseButton>
        <NuxtLink :to="localePath('/panel/hour-packages')" class="px-6 py-2.5 border border-border-default text-text-muted rounded-xl text-sm hover:bg-surface-raised transition-colors">Cancelar</NuxtLink>
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
import { computed, onMounted, reactive, ref } from 'vue';
import PackageCompositionFields from '~/components/hour-packages/PackageCompositionFields.vue';
import { useHourPackagesStore } from '~/stores/hour_packages';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useUnsavedGuard } from '~/composables/useUnsavedGuard';
import UnsavedChangesNotice from '~/components/panel/UnsavedChangesNotice.vue';

const localePath = useLocalePath();
const route = useRoute();
const router = useRouter();

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const CURRENCY_BY_NATIONALITY = { COL: 'COP', EXT: 'USD', USA: 'USD' };

const hourPackagesStore = useHourPackagesStore();
const notify = usePanelNotify();

const packageId = Number(route.params.id);
const loadError = ref(false);
const errorMsg = ref('');
const fieldErrors = reactive({});

const form = reactive({
  nationality: 'COL',
  name_es: '',
  name_en: '',
  note_es: '',
  note_en: '',
  xs_count: 30,
  s_count: 0,
  m_count: 0,
  validity_months: 12,
  discount_percent: 0,
  order: 0,
  is_active: true,
});

// `save` en null: handleSubmit navega al listado, y llamarlo desde dentro del
// guard de navegación sería reentrante. Quedan dos salidas.
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
  snapshot: () => ({ ...form }),
  labels: {
    nationality: 'nacionalidad',
    name_es: 'nombre (ES)',
    name_en: 'nombre (EN)',
    note_es: 'nota (ES)',
    note_en: 'nota (EN)',
    xs_count: 'cupos XS', s_count: 'cupos S', m_count: 'cupos M', validity_months: 'vigencia',
    discount_percent: 'descuento',
    order: 'orden',
    is_active: 'estado',
  },
});

const derivedCurrency = computed(() => CURRENCY_BY_NATIONALITY[form.nationality]);


onMounted(async () => {
  const result = await hourPackagesStore.fetchAdminPackage(packageId);
  if (!result.success) {
    loadError.value = true;
    return;
  }
  const pkg = result.data;
  form.nationality = pkg.nationality;
  form.name_es = pkg.name_es;
  form.name_en = pkg.name_en;
  form.note_es = pkg.note_es;
  form.note_en = pkg.note_en;
  form.xs_count = pkg.xs_count;
  form.s_count = pkg.s_count;
  form.m_count = pkg.m_count;
  form.validity_months = pkg.validity_months;
  form.discount_percent = pkg.discount_percent;
  form.order = pkg.order;
  form.is_active = pkg.is_active;
  // Con todo lo cargado en su sitio: de acá en más, lo que cambie es del
  // operador. Si la carga falla no se fija baseline y el guard queda desarmado.
  commitBaseline();
});

function formatMoney(value) {
  const currency = derivedCurrency.value;
  const formatted = (Number(value) || 0).toLocaleString(
    currency === 'COP' ? 'es-CO' : 'en-US',
    { maximumFractionDigits: currency === 'COP' ? 0 : 2 },
  );
  return `$${formatted} ${currency}`;
}

function applyFieldErrors(errors) {
  Object.keys(fieldErrors).forEach((k) => delete fieldErrors[k]);
  if (!errors || typeof errors !== 'object') return;
  Object.entries(errors).forEach(([field, messages]) => {
    fieldErrors[field] = Array.isArray(messages) ? messages.join(' ') : String(messages);
  });
}

async function handleSubmit() {
  errorMsg.value = '';
  const result = await hourPackagesStore.updatePackage(packageId, { ...form });
  if (result.success) {
    notify.success('Paquete actualizado.');
    // Ya está persistido: re-fijar la baseline desarma el guard para que la
    // vuelta al listado no pregunte nada.
    commitBaseline();
    router.push(localePath('/panel/hour-packages'));
  } else {
    applyFieldErrors(result.errors);
    errorMsg.value = 'No se pudo guardar el paquete. Revisa los campos.';
  }
}
</script>
