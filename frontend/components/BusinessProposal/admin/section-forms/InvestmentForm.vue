<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <FieldInput v-model="form.index" label="Índice" placeholder="9" />
    <FieldInput v-model="form.title" label="Título" />
  </div>
  <FieldTextarea v-model="form.introText" :format="form.text_formats?.['/introText'] || 'plain'" @update:format="form.text_formats = { ...form.text_formats, '/introText': $event }" label="Texto introductorio" :rows="2" :isSingle="true" />
  <div class="bg-info-soft border border-info-strong/30 rounded-xl px-4 py-3 text-sm text-info-strong">
    💰 <strong>Inversión total:</strong> ${{ Number(proposalData?.total_investment || 0).toLocaleString() }} {{ proposalData?.currency || 'COP' }}
    <span class="text-xs text-info-strong ml-2">(se edita en la pestaña "General")</span>
  </div>
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Qué incluye</label>
    <draggable v-model="form.whatsIncluded" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
      <template #item="{ element: item, index: idx }">
        <div class="mb-3 bg-surface-raised rounded-xl p-3 border border-border-muted">
          <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-2">
              <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
              <span class="text-xs text-text-subtle">Item {{ idx + 1 }}</span>
            </div>
            <BaseButton variant="danger-ghost" size="sm" @click="form.whatsIncluded.splice(idx, 1)">Eliminar</BaseButton>
          </div>
          <div class="grid grid-cols-[100px_1fr] gap-2 mb-1">
            <EmojiIconField v-model="item.icon" label="Icono" placeholder="🎨" />
            <FieldInput v-model="item.title" label="Título" />
          </div>
          <FieldInput v-model="item.description" label="Descripción" />
        </div>
      </template>
    </draggable>
    <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="form.whatsIncluded.push({ icon: '', title: '', description: '' })"><BaseActionIcon action="create" /> Agregar item</button>
  </div>
  <div>
    <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Opciones de pago</label>
    <draggable v-model="form.paymentOptions" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
      <template #item="{ element: opt, index: idx }">
        <div class="mb-3 bg-surface-raised rounded-xl p-3 border border-border-muted">
          <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-2">
              <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
              <span class="text-xs text-text-subtle">Opción {{ idx + 1 }}</span>
            </div>
            <BaseButton variant="danger-ghost" size="sm" @click="form.paymentOptions.splice(idx, 1)">Eliminar</BaseButton>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <FieldInput v-model="opt.label" label="Etiqueta" placeholder="40% al firmar" />
            <FieldInput v-model="opt.description" label="Descripción" placeholder="$596.000 COP" />
          </div>
        </div>
      </template>
    </draggable>
    <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="form.paymentOptions.push({ label: '', description: '' })"><BaseActionIcon action="create" /> Agregar opción</button>
  </div>
  <FieldTextarea v-model="form.paymentMethods" :lines="true" format-path="/paymentMethods" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Métodos de pago" help="Uno por línea" :rows="3" />
  <FieldTextarea v-model="form.valueReasons" :lines="true" format-path="/valueReasons" :formats="form.text_formats || {}" @update:formats="form.text_formats = $event" label="Razones de valor" help="Una por línea" :rows="3" />

  <!-- Hosting Plan -->
  <div class="mt-4 border border-border-default dark:border-white/[0.08] rounded-xl overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 bg-surface-raised cursor-pointer hover:bg-surface-raised transition-colors"
         @click="hostingCollapsed = !hostingCollapsed">
      <h4 class="text-sm font-semibold text-text-default flex items-center gap-2">
        <BaseActionIcon :action="hostingCollapsed ? 'expand' : 'collapse'" class="text-text-subtle" />
        ☁️ Plan de Hosting
      </h4>
    </div>
    <div v-show="!hostingCollapsed" class="p-4 space-y-4">
      <FieldInput v-model="form.hostingPlan.title" label="Título" placeholder="Hosting, Mantenimiento y Soporte" />
      <FieldTextarea v-model="form.hostingPlan.description" :format="form.hostingPlan.text_formats?.['/description'] || 'plain'" @update:format="form.hostingPlan.text_formats = { ...form.hostingPlan.text_formats, '/description': $event }" label="Descripción" :rows="2" :isSingle="true" />
      <div>
        <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Especificaciones</label>
        <draggable v-model="form.hostingPlan.specs" item-key="_idx" handle=".drag-handle" ghost-class="opacity-30">
          <template #item="{ element: spec, index: idx }">
            <div class="mb-2 bg-surface-raised rounded-lg p-3 border border-border-muted">
              <div class="flex items-center justify-between mb-1">
                <div class="flex items-center gap-2">
                  <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted">⠿</span>
                  <span class="text-[10px] text-text-subtle">{{ idx + 1 }}</span>
                </div>
                <BaseButton variant="danger-ghost" size="sm" @click="form.hostingPlan.specs.splice(idx, 1)">Eliminar</BaseButton>
              </div>
              <div class="grid grid-cols-[80px_1fr_1fr] gap-2">
                <EmojiIconField v-model="spec.icon" label="Icono" placeholder="🧠" />
                <FieldInput v-model="spec.label" label="Etiqueta" placeholder="vCPU" />
                <FieldInput v-model="spec.value" label="Valor" placeholder="1 núcleo de vCPU" />
              </div>
            </div>
          </template>
        </draggable>
        <button type="button" class="inline-flex items-center gap-1 text-xs text-text-brand font-medium" @click="form.hostingPlan.specs.push({ icon: '', label: '', value: '' })"><BaseActionIcon action="create" /> Agregar especificación</button>
      </div>
      <FieldInput v-model="form.hostingPlan.hostingPercent" label="% de inversión total" type="number" placeholder="70" />
      <div v-if="form.hostingPlan.hostingPercent > 0 && proposalData?.total_investment" class="bg-info-soft border border-info-strong/30 rounded-xl px-4 py-3 text-sm text-info-strong">
        💡 <strong>Referencia para calcular los pagos de hosting:</strong> ${{ Math.round(Number(proposalData.total_investment) * form.hostingPlan.hostingPercent / 100).toLocaleString() }} {{ proposalData?.currency || 'COP' }}
        <span class="text-xs text-info-strong ml-2">({{ form.hostingPlan.hostingPercent }}% de ${{ Number(proposalData.total_investment).toLocaleString() }})</span>
      </div>
      <!-- Billing Tiers -->
      <div>
        <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Frecuencias de pago del hosting</label>
        <div class="space-y-3">
          <div v-for="(tier, tIdx) in form.hostingPlan.billingTiers" :key="tIdx"
               class="bg-surface-raised rounded-xl p-3 border border-border-muted">
            <div class="grid grid-cols-2 sm:grid-cols-5 gap-2">
              <FieldInput v-model="tier.label" label="Etiqueta" :placeholder="tier.frequency === 'nine_month' ? 'Cada 9 meses' : tier.frequency === 'semiannual' ? 'Semestral' : tier.frequency === 'quarterly' ? 'Trimestral' : ''" />
              <FieldInput v-model.number="tier.months" label="Meses" type="number" :placeholder="String(tier.months)" />
              <FieldInput v-model.number="tier.discountPercent" label="% Descuento" type="number" placeholder="0" />
              <FieldInput v-model="tier.badge" label="Badge" placeholder="Mejor precio" />
              <div class="flex items-end pb-1">
                <span v-if="form.hostingPlan.hostingPercent > 0 && proposalData?.total_investment" class="text-xs text-text-brand font-medium">
                  ${{ Math.round(Math.round(Number(proposalData.total_investment) * form.hostingPlan.hostingPercent / 100 / 12) * (100 - (tier.discountPercent || 0)) / 100).toLocaleString() }} /mes
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <FieldTextarea v-model="form.hostingPlan.renewalNote" :format="form.hostingPlan.text_formats?.['/renewalNote'] || 'plain'" @update:format="form.hostingPlan.text_formats = { ...form.hostingPlan.text_formats, '/renewalNote': $event }" label="Nota de renovación (visible al cliente)" help="Fórmula de incremento anual, SMLMV, etc." :rows="3" />
      <FieldTextarea v-model="form.hostingPlan.coverageNote" :format="form.hostingPlan.text_formats?.['/coverageNote'] || 'plain'" @update:format="form.hostingPlan.text_formats = { ...form.hostingPlan.text_formats, '/coverageNote': $event }" label="Nota de cobertura (solo PDF)" help="Descripción de los 3 componentes del hosting (mantenimiento, soporte, recursos)" :rows="3" />
      <!-- Free months: count, visibility and copy travel together -->
      <div>
        <label class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Meses gratis de hosting</label>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FieldInput v-model="form.hostingPlan.freeMonths" label="Cantidad de meses" type="number" placeholder="1" />
          <FieldCheckbox v-model="form.hostingPlan.freeMonthsVisible" label="Visibilidad" text="Mostrar el bloque en la propuesta y el PDF" />
        </div>
        <p v-if="showFreeMonthsZeroHint" role="status" class="mt-2 text-xs text-warning-strong">
          ⚠️ Con 0 meses el bloque se muestra igual, pero el título va sin número. Revisa que el texto tenga sentido.
        </p>
        <FieldTextarea v-model="form.hostingPlan.freeMonthNote" :format="form.hostingPlan.text_formats?.['/freeMonthNote'] || 'plain'" @update:format="form.hostingPlan.text_formats = { ...form.hostingPlan.text_formats, '/freeMonthNote': $event }" label="Texto del bloque (web y PDF)" help="Viene con el texto por defecto según el idioma. Edítalo para personalizarlo; para esconder el bloque usa la casilla." :rows="3" class="mt-4" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { FieldCheckbox, FieldInput, FieldTextarea } from './fields.js';
import EmojiIconField from '~/components/BusinessProposal/admin/EmojiIconField.vue';
import draggable from 'vuedraggable';

const props = defineProps({
  form: { type: Object, required: true },
  proposalData: { type: Object, default: () => ({}) },
});

const hostingCollapsed = ref(true);

// Visible with a zero count is allowed — the copy can be qualitative — but it
// is unusual enough to point out, without blocking the save.
const showFreeMonthsZeroHint = computed(() =>
  Boolean(props.form.hostingPlan?.freeMonthsVisible)
  && Number(props.form.hostingPlan?.freeMonths ?? 0) === 0);

function fillInvestmentFromProposal() {
  if (!props.proposalData?.total_investment) return;
  const total = Number(props.proposalData.total_investment);
  const currency = props.proposalData.currency || 'COP';
  const fmt = (n) => '$' + Math.round(n).toLocaleString();
  props.form.totalInvestment = fmt(total);
  props.form.currency = currency;
  // Auto-fill 40/30/30 payment split
  props.form.paymentOptions = [
    { label: '40% al firmar el contrato ✍️', description: fmt(total * 0.4) + ' ' + currency },
    { label: '30% al aprobar el diseño final ✅', description: fmt(total * 0.3) + ' ' + currency },
    { label: '30% al desplegar el sitio web 🚀', description: fmt(total * 0.3) + ' ' + currency },
  ];
}

function recalcPaymentFromProposal() {
  if (!props.proposalData?.total_investment) return;
  const total = Number(props.proposalData.total_investment);
  if (!total) return;
  const cur = props.proposalData.currency || 'COP';
  const fmt = (n) => '$' + Math.round(n).toLocaleString();
  for (const opt of props.form.paymentOptions) {
    const pctMatch = opt.label?.match(/(\d+)%/);
    if (pctMatch) {
      const pct = Number(pctMatch[1]) / 100;
      opt.description = fmt(total * pct) + ' ' + cur;
    }
  }
}

// Auto-fill investment from proposal data if section is empty
if (!props.form.totalInvestment && props.proposalData?.total_investment) {
  fillInvestmentFromProposal();
}

// Auto-recalculate payment option descriptions when proposal investment changes
watch(() => props.proposalData?.total_investment, () => {
  recalcPaymentFromProposal();
});

// Sync hosting_percent from General tab → hostingPlan.hostingPercent
watch(() => props.proposalData?.hosting_percent, (newVal) => {
  if (newVal != null && props.form.hostingPlan && props.form.hostingPlan.hostingPercent !== newVal) {
    props.form.hostingPlan.hostingPercent = newVal;
  }
});
</script>
