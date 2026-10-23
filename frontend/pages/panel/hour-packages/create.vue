<template>
  <div>
    <div class="flex items-center gap-4 mb-8">
      <BaseActionButton as="NuxtLink" :to="localePath('/panel/hour-packages')" action="back" label="Volver a paquetes de horas" />
      <h1 class="text-2xl font-light text-text-default">Nuevo paquete de horas</h1>
    </div>

    <form class="space-y-6 max-w-3xl" @submit.prevent="handleSubmit">
      <UnsavedChangesNotice
        v-if="hasChanges"
        :title="unsavedTitle"
        :detail="unsavedDetail"
        message="Este paquete todavía no existe. Si sales de esta página, se pierde."
        :can-save="false"
        :can-discard="false"
        testid="hour-package-create-unsaved-notice"
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
            <input id="hp-name-es" v-model="form.name_es" type="text" required class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text placeholder:text-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="Paquete Ágil" />
            <p v-if="fieldErrors.name_es" class="text-xs text-danger-strong mt-1">{{ fieldErrors.name_es }}</p>
          </div>
          <div>
            <label for="hp-name-en" class="block text-sm font-medium text-text-default mb-1">Name (EN)</label>
            <input id="hp-name-en" v-model="form.name_en" type="text" required class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text placeholder:text-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" placeholder="Agile Pack" />
            <p v-if="fieldErrors.name_en" class="text-xs text-danger-strong mt-1">{{ fieldErrors.name_en }}</p>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Nota (ES)</label>
            <BaseRichTextEditor v-model="form.note_es" rows="2" class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text placeholder:text-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" placeholder="Ideal para ajustes puntuales."  :format="form.text_formats?.['/note_es'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/note_es': $event }" />
          </div>
          <div>
            <label class="block text-sm font-medium text-text-default mb-1">Note (EN)</label>
            <BaseRichTextEditor v-model="form.note_en" rows="2" class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text placeholder:text-input-placeholder text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all resize-y" placeholder="Ideal for one-off adjustments."  :format="form.text_formats?.['/note_en'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/note_en': $event }" />
          </div>
        </div>
      </fieldset>

      <!-- Pricing -->
      <fieldset class="border border-border-default rounded-xl p-5 space-y-4">
        <legend class="text-sm font-medium text-text-default px-2">Precio</legend>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label for="hp-hours" class="block text-sm font-medium text-text-default mb-1">Horas</label>
            <input id="hp-hours" v-model.number="form.hours" type="number" min="1" required class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
            <p v-if="fieldErrors.hours" class="text-xs text-danger-strong mt-1">{{ fieldErrors.hours }}</p>
          </div>
          <div>
            <label for="hp-hourly-rate" class="block text-sm font-medium text-text-default mb-1">Tarifa por hora ({{ derivedCurrency }})</label>
            <BaseCurrencyInput id="hp-hourly-rate" v-model="form.hourly_rate" :decimals="2" required />
            <p v-if="fieldErrors.hourly_rate" class="text-xs text-danger-strong mt-1">{{ fieldErrors.hourly_rate }}</p>
          </div>
          <div>
            <label for="hp-discount" class="block text-sm font-medium text-text-default mb-1">Descuento (%)</label>
            <input id="hp-discount" v-model.number="form.discount_percent" type="number" min="0" max="100" class="bg-input-bg w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring transition-all" />
            <p v-if="fieldErrors.discount_percent" class="text-xs text-danger-strong mt-1">{{ fieldErrors.discount_percent }}</p>
          </div>
        </div>
        <div class="bg-primary-soft rounded-lg px-4 py-3 text-sm text-text-brand">
          Tarifa efectiva: <strong>{{ formatMoney(effectiveRate) }}/h</strong> · Total del paquete: <strong>{{ formatMoney(totalPrice) }}</strong>
        </div>
      </fieldset>

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
          {{ hourPackagesStore.isUpdating ? 'Creando...' : 'Crear paquete' }}
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
import { computed, reactive, ref } from 'vue';
import { useHourPackagesStore } from '~/stores/hour_packages';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useUnsavedGuard } from '~/composables/useUnsavedGuard';
import UnsavedChangesNotice from '~/components/panel/UnsavedChangesNotice.vue';

const localePath = useLocalePath();
const route = useRoute();
const router = useRouter();

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const CURRENCY_BY_NATIONALITY = { COL: 'COP', EXT: 'USD', USA: 'USD' };
const VALID_NATIONALITIES = ['COL', 'EXT', 'USA'];

const hourPackagesStore = useHourPackagesStore();
const notify = usePanelNotify();

const initialNationality = VALID_NATIONALITIES.includes(route.query.nationality)
  ? route.query.nationality
  : 'COL';

const form = reactive({
  nationality: initialNationality,
  name_es: '',
  name_en: '',
  note_es: '',
  note_en: '',
  hours: 20,
  hourly_rate: null,
  discount_percent: 0,
  order: 0,
  is_active: true,
});

const errorMsg = ref('');
const fieldErrors = reactive({});

// La baseline es el formulario recién inicializado (incluido el ?nationality=
// de la URL), así que se fija de entrada: lo que difiera de eso ya es del
// operador. `save` en null porque handleSubmit navega al listado.
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
    hours: 'horas',
    hourly_rate: 'tarifa por hora',
    discount_percent: 'descuento',
    order: 'orden',
    is_active: 'estado',
  },
});
commitBaseline();

const derivedCurrency = computed(() => CURRENCY_BY_NATIONALITY[form.nationality]);
const effectiveRate = computed(() =>
  Number(form.hourly_rate || 0) * (1 - Number(form.discount_percent || 0) / 100));
const totalPrice = computed(() => Number(form.hours || 0) * effectiveRate.value);

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
  const result = await hourPackagesStore.createPackage({ ...form });
  if (result.success) {
    notify.success('Paquete creado.');
    // Ya está persistido: desarma el guard antes de navegar.
    commitBaseline();
    router.push(localePath('/panel/hour-packages'));
  } else {
    applyFieldErrors(result.errors);
    errorMsg.value = 'No se pudo crear el paquete. Revisa los campos.';
  }
}
</script>
