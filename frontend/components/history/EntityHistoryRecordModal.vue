<script setup>
import { computed } from 'vue';
import EntityHistoryTabs from './EntityHistoryTabs.vue';
import HistoryValue from './HistoryValue.vue';
// Controlled so a row-actions menu can open it: a three-dot track has room for
// the kebab only, so «Detalle e historial» is always a menu entry.
const props = defineProps({
  open: { type: Boolean, default: false },
  entityType: { type: String, required: true },
  record: { type: Object, default: null },
});
const emit = defineEmits(['close']);
const fields = {
  expense: ['concept', 'period_date', 'category', 'total_amount', 'gustavo_amount', 'carlos_amount', 'notes'],
  hosting: ['client_name', 'client_email', 'domain_url', 'payment_modality', 'valid_from', 'valid_to', 'total_paid', 'notes'],
  pocket: ['concept', 'movement_date', 'direction', 'amount', 'notes'],
  recurring: ['name', 'price', 'currency', 'cop_equivalent', 'frequency', 'billing_day', 'payment_method', 'notes'],
  ads: ['spend_date', 'platform', 'origin_card', 'amount', 'notes'],
  card_snapshot: ['card_name', 'snapshot_date', 'available_amount', 'debt_amount', 'notes'],
  credit_card: ['name', 'credit_limit', 'is_active', 'statements_since', 'notes'],
  statement_tx: ['transaction_date', 'raw_description', 'merchant_name', 'category', 'amount', 'installment_number', 'installments_total', 'notes'],
  merchant_alias: ['match_text', 'merchant_name', 'default_category', 'is_gateway', 'notes'],
  notification_recipient: ['email', 'is_active', 'notes'],
};
const labels = {
  concept: 'Concepto', period_date: 'Período', category: 'Categoría', total_amount: 'Monto total',
  gustavo_amount: 'Monto Gustavo', carlos_amount: 'Monto Carlos', client_name: 'Cliente',
  client_email: 'Correo del cliente', domain_url: 'Dominio', payment_modality: 'Modalidad de pago',
  valid_from: 'Vigente desde', valid_to: 'Vigente hasta', total_paid: 'Total pagado',
  movement_date: 'Fecha', direction: 'Tipo de movimiento', amount: 'Valor', price: 'Precio',
  cop_equivalent: 'Equivalente COP', frequency: 'Frecuencia', billing_day: 'Día de cobro',
  payment_method: 'Medio de pago', spend_date: 'Fecha', platform: 'Plataforma', origin_card: 'Tarjeta origen',
  card_name: 'Tarjeta', snapshot_date: 'Fecha del saldo', available_amount: 'Disponible', debt_amount: 'Deuda',
  credit_limit: 'Cupo', is_active: 'Activo', statements_since: 'Extractos desde',
  transaction_date: 'Fecha', raw_description: 'Descripción', merchant_name: 'Comercio',
  installment_number: 'Cuota', installments_total: 'Total de cuotas', match_text: 'Texto de coincidencia',
  default_category: 'Categoría por defecto', is_gateway: 'Intermediario de pago',
};
const recordDetails = computed(() => (props.record ? Object.fromEntries(
  (fields[props.entityType] || ['name', 'notes'])
    .filter((field) => field in props.record).map((field) => [field, props.record[field]]),
) : {}));
</script>
<template>
  <BaseModal :model-value="open && Boolean(record)" kind="detail" @close="emit('close')">
    <div v-if="open && record" class="space-y-4 p-5" data-testid="history-record-modal">
      <div class="flex items-center justify-between gap-3"><h2 class="text-lg font-semibold text-text-default">Detalle del registro</h2><BaseButton variant="ghost" @click="emit('close')">Cerrar</BaseButton></div>
      <EntityHistoryTabs :entity-type="entityType" :object-id="record.id">
        <HistoryValue :value="recordDetails" :labels="labels" />
      </EntityHistoryTabs>
    </div>
  </BaseModal>
</template>
