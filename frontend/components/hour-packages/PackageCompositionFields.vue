<template>
  <fieldset class="border border-border-default rounded-xl p-5 space-y-4">
    <legend class="text-sm font-medium text-text-default px-2">Cupos y precio del paquete</legend>
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <label v-for="size in sizes" :key="size" class="block text-sm text-text-default">
        Cupos {{ size.toUpperCase() }}
        <input :value="modelValue[`${size}_count`]" type="number" min="0" step="1" required
          :data-testid="`package-${size}-count`" :aria-label="`Cupos ${size.toUpperCase()}`"
          class="bg-input-bg mt-1 w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text"
          @input="set(`${size}_count`, Number($event.target.value))" />
      </label>
      <label class="block text-sm text-text-default">Descuento (%)
        <input :value="modelValue.discount_percent" type="number" min="0" max="99" step="1" required
          data-testid="package-discount" class="bg-input-bg mt-1 w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text"
          @input="set('discount_percent', Number($event.target.value))" />
      </label>
      <label class="block text-sm text-text-default">Vigencia (meses desde el pago)
        <input :value="modelValue.validity_months" type="number" min="1" step="1" required
          data-testid="package-validity" class="bg-input-bg mt-1 w-full px-4 py-2.5 rounded-xl border border-border-default text-input-text"
          @input="set('validity_months', Number($event.target.value))" />
      </label>
    </div>
    <p v-if="!hasAllowance" role="alert" class="text-sm text-danger-strong">Incluye al menos un cupo XS, S o M.</p>
    <p v-if="fieldError" role="alert" class="text-sm text-danger-strong">{{ fieldError }}</p>
    <div v-if="preview" data-testid="package-price-preview" class="rounded-lg bg-primary-soft px-4 py-3 text-sm text-text-brand">
      Referencia: {{ money(preview.reference, currency) }} · Ahorro: {{ money(preview.savings, currency) }}<br />
      <strong>Total: {{ money(preview.total, currency) }} {{ currency === 'COP' ? '+ IVA' : '+ Tax' }}</strong>
    </div>
    <p v-else class="text-sm text-danger-strong" role="alert">No se pudo calcular el precio. Revisa la configuración y la tasa de Contabilidad.</p>
    <p class="text-xs text-text-subtle">Compra única, sin intercambio entre tallas. L/XL se cotizan aparte. Los valores internos se administran en Configuración.</p>
  </fieldset>
</template>

<script setup>
import { computed, onMounted } from 'vue';
import { useHourPackagesStore } from '~/stores/hour_packages';
import { formatPackageMoney as money } from '~/utils/hourPackagePricing';
const props = defineProps({ modelValue: { type: Object, required: true }, fieldErrors: { type: Object, default: () => ({}) } });
const emit = defineEmits(['update:modelValue']);
const store = useHourPackagesStore();
const sizes = ['xs', 's', 'm'];
const set = (key, value) => emit('update:modelValue', { ...props.modelValue, [key]: value });
const currency = computed(() => props.modelValue.nationality === 'COL' ? 'COP' : 'USD');
const hasAllowance = computed(() => sizes.some((s) => Number(props.modelValue[`${s}_count`]) > 0));
const fieldError = computed(() => ['xs_count', 's_count', 'm_count', 'validity_months', 'discount_percent']
  .map((key) => props.fieldErrors[key]).filter(Boolean).join(' '));
const preview = computed(() => {
  const settings = store.settings;
  if (!settings) return null;
  let reference = sizes.reduce((sum, s) => sum + Number(props.modelValue[`${s}_count`] || 0) * Number(settings[`${s}_price_cop`]), 0);
  if (currency.value === 'USD') {
    if (!(Number(settings.exchange_rate) > 0)) return null;
    reference = reference / Number(settings.exchange_rate) * Number(settings[props.modelValue.nationality === 'EXT' ? 'foreign_multiplier' : 'usa_multiplier']);
  }
  const total = reference * (1 - Number(props.modelValue.discount_percent || 0) / 100);
  const precision = currency.value === 'COP' ? 1 : 100;
  const referenceUnits = Math.round((reference + Number.EPSILON) * precision);
  const totalUnits = Math.round((total + Number.EPSILON) * precision);
  return { reference: referenceUnits / precision, total: totalUnits / precision,
    savings: (referenceUnits - totalUnits) / precision };
});
onMounted(() => store.fetchSettings());
</script>
