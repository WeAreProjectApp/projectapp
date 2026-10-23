<template>
  <div class="space-y-4">
    <div v-if="!section" class="rounded-xl border border-border-default bg-surface-raised p-6" data-testid="hour-rate-no-section">
      <p class="text-sm text-text-muted">Crea las condiciones comerciales para incluir los paquetes de requerimientos en el PDF.</p>
      <BaseButton variant="primary" size="sm" data-testid="hour-rate-create-section" :disabled="busy" @click="createSection">Crear la sección</BaseButton>
    </div>
    <template v-else>
      <p v-if="section.is_enabled === false" class="rounded-lg bg-warning-soft p-3 text-sm text-warning-strong" data-testid="hour-rate-disabled-warning">La sección está deshabilitada y no se imprime en el PDF.</p>
      <template v-if="legacy && !adopting">
        <p class="rounded-lg bg-surface-raised p-3 text-sm text-text-muted" data-testid="packages-legacy-notice">Esta propuesta conserva sus condiciones históricas de horas. No se convierten automáticamente en requerimientos.</p>
        <ProposalHourPackagesTable :packages="content.packages || []" :currency="content.currency || 'COP'" :base-rate="Number(content.hourlyRate) || 0" :editable="false" :language="proposal.language" />
        <BaseButton v-if="proposal.status === 'draft'" variant="secondary" size="sm" data-testid="packages-adopt" @click="adoptCatalog">Revisar nuevos paquetes</BaseButton>
      </template>
      <template v-else>
        <p v-if="adopting" class="rounded-lg bg-warning-soft p-3 text-sm text-warning-strong">Revisa composición y precios. Guardar reemplaza las condiciones de horas de este borrador.</p>
        <p v-if="content.packagesFrozen && !adopting" class="text-sm text-text-muted">Oferta emitida: conserva sus precios. Actualizar desde el catálogo prepara condiciones nuevas; los archivos enviados permanecen en el historial.</p>
        <label class="flex items-center gap-3 text-sm text-text-default">
          <input v-model="enabled" type="checkbox" aria-label="Incluir paquetes de requerimientos en el PDF" />
          Incluir paquetes de requerimientos en el PDF
        </label>
        <p class="text-xs text-text-subtle">La cláusula de alcance se conserva aunque ocultes los paquetes.</p>
        <div class="flex flex-wrap items-center gap-3">
          <label class="text-sm text-text-default">Fuente de los paquetes
            <select :value="mode" data-testid="packages-mode" @change="changeMode($event.target.value)" class="ml-2 rounded-lg border border-border-default bg-input-bg p-2 text-input-text">
              <option value="auto">Catálogo automático</option>
              <option value="manual">Manual para esta propuesta</option>
            </select>
          </label>
          <BaseButton variant="secondary" size="sm" data-testid="packages-reset" :disabled="!catalog.length" disabled-reason="No hay paquetes activos en el catálogo de este mercado." @click="resetCatalog">Actualizar desde el catálogo</BaseButton>
        </div>
        <p v-if="loadError" role="alert" class="text-sm text-danger-strong">No se pudo cargar el catálogo. Revisa la configuración y la tasa de cambio.</p>
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <article v-for="(row, idx) in displayed" :key="row.id || idx" class="min-w-0 space-y-3 rounded-xl border border-border-default bg-surface p-4" :data-testid="`requirement-package-${idx}`">
            <template v-if="mode === 'manual'">
              <label class="block text-xs text-text-muted">Nombre
                <input v-model="row.name" required class="mt-1 w-full rounded-lg border border-border-default bg-input-bg p-2 text-input-text" :aria-label="`Nombre del paquete ${idx + 1}`" />
              </label>
              <div class="grid grid-cols-3 gap-2">
                <label v-for="size in ['xs', 's', 'm']" :key="size" class="text-xs text-text-muted">{{ size.toUpperCase() }}
                  <input v-model.number="row[`${size}Count`]" type="number" min="0" step="1" :aria-label="`Cupos ${size.toUpperCase()} del paquete ${idx + 1}`" class="mt-1 w-full rounded-lg border border-border-default bg-input-bg p-2 text-input-text" />
                </label>
              </div>
              <label class="block text-xs text-text-muted">Referencia ({{ currency }})
                <BaseCurrencyInput v-model="row.referencePrice" :decimals="currency === 'COP' ? 0 : 2" :aria-label="`Referencia del paquete ${idx + 1}`" />
              </label>
              <label class="block text-xs text-text-muted">Descuento (%)
                <input v-model.number="row.discountPercent" type="number" min="0" max="99" step="1" class="mt-1 w-full rounded-lg border border-border-default bg-input-bg p-2 text-input-text" />
              </label>
              <label class="block text-xs text-text-muted">Vigencia (meses desde el pago)
                <input v-model.number="row.validityMonths" type="number" min="1" step="1" class="mt-1 w-full rounded-lg border border-border-default bg-input-bg p-2 text-input-text" />
              </label>
              <label class="block text-xs text-text-muted">Nota
                <textarea v-model="row.note" rows="2" class="mt-1 w-full rounded-lg border border-border-default bg-input-bg p-2 text-input-text" />
              </label>
              <BaseButton variant="danger-ghost" size="sm" :disabled="rows.length <= 1" :disabled-reason="rows.length <= 1 ? 'Conserva al menos un paquete.' : ''" @click="rows.splice(idx, 1)">Quitar paquete</BaseButton>
            </template>
            <template v-else>
              <h3 class="font-medium text-text-default">{{ row.name }}</h3>
              <p class="text-sm text-text-default">{{ row.xsCount }} XS · {{ row.sCount }} S · {{ row.mCount }} M</p>
              <p class="text-xs text-text-muted">{{ row.validityMonths }} meses desde el pago</p>
              <p class="text-xs text-text-muted">{{ row.note }}</p>
            </template>
            <p class="text-sm text-text-muted"><span class="line-through">{{ money(row.referencePrice, currency) }}</span> · −{{ row.discountPercent }} %</p>
            <p class="font-medium text-text-brand">{{ money(net(row), currency) }} {{ currency === 'COP' ? '+ IVA' : '+ Tax' }}</p>
            <p class="text-xs text-text-brand">Ahorro: {{ money(Number(row.referencePrice) - net(row), currency) }}</p>
          </article>
        </div>
        <p v-if="!displayed.length" class="text-sm text-text-muted">No hay paquetes activos en este mercado.</p>
        <BaseButton v-if="mode === 'manual'" variant="secondary" size="sm" data-testid="packages-add" @click="addPackage">Agregar paquete</BaseButton>
        <p class="text-xs text-text-subtle">Cupos por talla sin intercambio. Acuerda resultado y talla antes de programar. L/XL se cotizan por separado; la garantía no consume cupos.</p>
        <BaseButton variant="primary" size="sm" data-testid="hour-rate-save" :disabled="busy || !dirty || (mode === 'auto' && loadError)" :disabled-reason="!dirty ? 'No hay cambios pendientes.' : ''" @click="save">{{ busy ? 'Guardando…' : 'Guardar paquetes' }}</BaseButton>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useProposalStore } from '~/stores/proposals';
import { useHourPackagesStore } from '~/stores/hour_packages';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { formatPackageMoney as money } from '~/utils/hourPackagePricing';
import BaseCurrencyInput from '~/components/base/BaseCurrencyInput.vue';
import ProposalHourPackagesTable from './ProposalHourPackagesTable.vue';
const props = defineProps({ proposal: { type: Object, required: true } });
const emit = defineEmits(['dirty-state-change']);
const proposals = useProposalStore();
const packages = useHourPackagesStore();
const notify = usePanelNotify();
const section = computed(() => proposals.currentProposal?.sections?.find((s) => s.section_type === 'commercial_conditions'));
const content = computed(() => section.value?.content_json || {});
const legacy = computed(() => content.value.pricingModel !== 'requirements');
const currency = computed(() => props.proposal.nationality === 'COL' ? 'COP' : 'USD');
const mode = ref('auto');
const enabled = ref(true);
const rows = ref([]);
const adopting = ref(false);
const refreshing = ref(false);
const manualDraftAvailable = ref(false);
const busy = ref(false);
const loadError = ref(false);
const baseline = ref('');
const snapshot = () => JSON.stringify([mode.value, enabled.value, rows.value, adopting.value, refreshing.value]);
const dirty = computed(() => baseline.value !== snapshot());
watch(dirty, (value) => emit('dirty-state-change', value));
const catalog = computed(() => (packages.packages || []).filter((p) => p.is_active).map((p) => ({
  id: p.id, name: props.proposal.language === 'en' ? p.name_en : p.name_es,
  note: props.proposal.language === 'en' ? p.note_en : p.note_es,
  xsCount: p.xs_count, sCount: p.s_count, mCount: p.m_count,
  validityMonths: p.validity_months, referencePrice: p.reference_price,
  discountPercent: p.discount_percent, totalPrice: p.total_price,
})));
const displayed = computed(() => mode.value === 'manual' || (content.value.packagesFrozen && !refreshing.value && !adopting.value) ? rows.value : catalog.value);
const net = (row) => {
  const source = [...catalog.value, ...(content.value.packages || [])].find((p) => p.id === row.id
    && Number(p.referencePrice) === Number(row.referencePrice)
    && Number(p.discountPercent) === Number(row.discountPercent));
  return source?.totalPrice != null ? Number(source.totalPrice)
    : Number(row.referencePrice) * (1 - Number(row.discountPercent) / 100);
};
function resetCatalog() { rows.value = structuredClone(catalog.value); refreshing.value = true; }
function adoptCatalog() { adopting.value = true; mode.value = 'auto'; resetCatalog(); }
function addPackage() { rows.value.push({ name: 'Paquete nuevo', note: '', xsCount: 1, sCount: 0, mCount: 0, validityMonths: 12, referencePrice: 0, discountPercent: 0 }); }
function changeMode(value) {
  if (value === 'manual' && !manualDraftAvailable.value) {
    rows.value = JSON.parse(JSON.stringify(displayed.value));
    manualDraftAvailable.value = true;
  }
  mode.value = value;
}
function load() {
  rows.value = JSON.parse(JSON.stringify(content.value.packages || []));
  enabled.value = content.value.hourPackagesEnabled !== false;
  mode.value = content.value.hourPackagesMode || 'auto';
  manualDraftAvailable.value = mode.value === 'manual';
  adopting.value = false; refreshing.value = false; baseline.value = snapshot();
}
watch(() => section.value?.id, load, { immediate: true });
watch(() => props.proposal.nationality, async (nationality, previous) => {
  const result = await packages.fetchAdminPackages(nationality);
  loadError.value = result?.success === false;
  if (previous && previous !== nationality && !legacy.value) {
    resetCatalog(); mode.value = 'auto';
    notify.warning?.('Revisa la composición y los precios del nuevo mercado antes de guardar.');
  }
}, { immediate: true });
async function createSection() {
  busy.value = true;
  try { await proposals.createSection(props.proposal.id, 'commercial_conditions'); load(); }
  finally { busy.value = false; }
}
async function save() {
  busy.value = true;
  try {
    const next = { ...content.value, pricingModel: 'requirements', hourPackagesMode: mode.value,
      hourPackagesEnabled: enabled.value, currency: currency.value, manualCurrency: currency.value,
      packagesFrozen: Boolean(content.value.packagesFrozen && !refreshing.value && !adopting.value),
      packages: JSON.parse(JSON.stringify(displayed.value)) };
    const result = await proposals.updateSection(section.value.id, { content_json: next });
    if (result?.success === false) { notify.error('No se pudieron guardar los paquetes. Revisa cupos, vigencia, referencia y descuento.'); return; }
    load(); notify.success('Paquetes guardados.');
  } finally { busy.value = false; }
}
</script>
