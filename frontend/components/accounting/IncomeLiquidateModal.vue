<script setup>
import { useId } from 'vue';
import PartnerSplitInput from './PartnerSplitInput.vue';
import PeriodDateField from './PeriodDateField.vue';
import SettlementHostingPeriod from './SettlementHostingPeriod.vue';
import VatBreakdown from './VatBreakdown.vue';
import { useIncomeSettlementForm } from '~/composables/useIncomeSettlementForm';
import { DEDUCTION_TYPE_OPTIONS } from '~/utils/accountingDeductions';
import { formatMoney } from '~/utils/formatMoney';
import { formatPaymentDate } from '~/utils/paymentConfirmation';

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  records: { type: Array, default: () => [] },
  excludedCount: { type: Number, default: 0 },
  saving: { type: Boolean, default: false },
});
const emit = defineEmits(['close', 'submit']);
const {
  records: selected, personal, form, exactDate, requestId, deductions, followUps, periods,
  participantsOpen, differenceOpen, vatOpen, showVat, manual, contexts, sendConfirmations,
  contextLoading, preparing, error, review, proposal, shortfall, remaining, credit,
  hostingRecords, blockReason, addDeduction, addFollowUp, editAllocation, recalculate,
  submit, confirm, back,
} = useIncomeSettlementForm(props, emit);
const formId = useId();
const sectionId = (name) => `${formId}-${name}`;
const money = (value) => formatMoney(Number(value ?? 0), 'COP');
const destinations = [{ value: 'pocket', label: 'Bolsillo ProjectApp' }, { value: 'partners', label: 'Socios' }];
</script>

<template>
  <BaseModal :model-value="open" kind="form" :title-id="sectionId('title')" :close-on-esc="!saving && !preparing" :close-on-backdrop="!saving && !preparing" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 :id="sectionId('title')" class="text-lg font-bold text-text-default">{{ review ? 'Revisar y liquidar' : 'Liquidar ingresos' }}</h3>
      <p class="mt-1 text-sm text-text-muted">{{ selected.length }} {{ selected.length === 1 ? 'ingreso seleccionado' : 'ingresos seleccionados' }} · Pendiente {{ money(proposal.pending) }}</p>
      <p v-if="excludedCount" class="mt-1 text-xs text-text-subtle" data-testid="income-bulk-settle-excluded">Se excluyeron {{ excludedCount }} seleccionados que no aplican: solo entran esperados con saldo pendiente de empresa.</p>
    </div>

    <div v-if="review" class="px-6 py-4 space-y-4" data-testid="income-liquidate-review">
      <p class="text-sm text-text-muted">Revisa el pago y los destinatarios. Todavía no se ha registrado la liquidación ni enviado ningún correo.</p>
      <dl class="grid grid-cols-1 gap-3 text-sm panel-portrait:grid-cols-2">
        <div><dt class="text-text-muted">Valor recibido</dt><dd class="font-semibold text-text-default">{{ money(review.total_amount) }}</dd></div>
        <div><dt class="text-text-muted">Fecha de pago</dt><dd class="text-text-default">{{ formatPaymentDate(form.period_date, exactDate) }}</dd></div>
        <div><dt class="text-text-muted">Destino del dinero</dt><dd class="text-text-default">{{ personal ? 'Contabilidad personal' : destinations.find(option => option.value === form.destination)?.label }}</dd></div>
        <div><dt class="text-text-muted">Saldo pendiente en los originales</dt><dd class="text-text-default">{{ money(review.pending_after) }}</dd></div>
      </dl>
      <div v-for="row in review.rows" :key="row.income_id" class="rounded-lg bg-surface-raised p-3 space-y-1 text-sm">
        <p class="font-medium text-text-default">{{ row.concept }}</p>
        <p class="text-text-muted">Recibido {{ money(row.amount) }} · Deducciones {{ money(row.deducted) }} · Reprogramado {{ money(row.reexpected) }} · Pendiente {{ money(row.pending_after) }}</p>
        <p v-if="sendConfirmations[row.income_id] && row.confirmation.can_send && Number(row.amount) > 0" class="text-text-default" data-testid="income-liquidate-review-recipient">Confirmación a {{ row.confirmation.recipient }} · {{ row.confirmation.collection_account_number || 'Sin número de cuenta' }}</p>
        <p v-else class="text-xs text-text-subtle">Sin correo: {{ row.confirmation.blocked_reason || 'no solicitado o sin dinero recibido para este ingreso' }}.</p>
      </div>
    </div>

    <form v-else :id="formId" class="px-6 py-4 space-y-4" data-testid="income-liquidate-form" @submit.prevent="submit">
      <div class="space-y-2" data-testid="income-liquidate-selection">
        <div v-for="row in proposal.rows" :key="row.income_id" class="rounded-lg bg-surface-raised p-3 space-y-2">
          <p class="text-sm font-medium text-text-default break-words">{{ row.record.concept }}</p>
          <p class="text-xs text-text-muted">{{ row.record.period_label || row.record.period_date }} · Esperado {{ money(row.record.total_amount) }} · Pendiente {{ money(row.pending) }}</p>
          <div v-if="selected.length > 1 || manual" class="grid grid-cols-1 items-center gap-2 panel-portrait:grid-cols-2">
            <label class="text-xs text-text-muted" :for="`${formId}-allocation-${row.income_id}`">Dinero imputado</label>
            <BaseCurrencyInput :id="`${formId}-allocation-${row.income_id}`" :model-value="row.amount" :aria-label="`Imputado a ${row.record.concept}`" :data-testid="`income-bulk-settle-amount-${row.income_id}`" @update:model-value="editAllocation(row.income_id, $event)" />
          </div>
          <p v-if="row.deducted > 0" class="text-xs text-text-muted">Deducción proporcional: {{ money(row.deducted) }}</p>
        </div>
        <BaseButton v-if="manual" type="button" size="sm" variant="ghost" data-testid="income-bulk-settle-recalculate" @click="recalculate">Recalcular reparto</BaseButton>
        <p v-if="manual" class="text-xs text-text-subtle">Reparto manual: no se recalcula al cambiar el valor recibido.</p>
      </div>

      <BaseFormRow :cols="2" :gap="3">
        <BaseFormField label="Valor recibido" required>
          <BaseCurrencyInput v-model="form.total_amount" required data-testid="income-liquidate-paid" aria-label="Valor recibido" />
        </BaseFormField>
        <PeriodDateField v-model="form.period_date" v-model:exact="exactDate" label-exact="Fecha en que se pagó" label-month="Mes en que se pagó" toggle-label="Registrar el día exacto de pago" required input-testid="income-liquidate-period" toggle-testid="income-liquidate-exact-date" />
      </BaseFormRow>
      <BaseFormField v-if="!personal" label="Destino del dinero">
        <BaseSegmented v-model="form.destination" :options="destinations" full-width data-testid="income-liquidate-destination" />
      </BaseFormField>

      <div class="rounded-lg bg-surface-raised p-3 space-y-1 text-sm" aria-live="polite" data-testid="income-liquidate-summary">
        <p class="text-text-default">Cubierto: {{ money(proposal.allocated + proposal.deducted) }} · Falta: {{ money(Math.max(remaining, 0)) }}</p>
        <p v-if="credit > 0" class="text-warning-strong">Excedente: {{ money(credit) }} quedará como saldo a favor.</p>
        <p v-if="shortfall > 0" class="text-xs text-text-muted">Diferencia entre lo esperado y lo recibido: {{ money(shortfall) }}.</p>
      </div>

      <section v-if="!personal" class="rounded-lg border border-border-muted">
        <button type="button" class="flex w-full items-center justify-between gap-2 p-4 text-left text-sm font-medium text-text-default" :aria-expanded="participantsOpen" :aria-controls="sectionId('participants')" data-testid="income-liquidate-participations-toggle" @click="participantsOpen = !participantsOpen">
          <span>Participaciones</span><span class="text-xs text-text-muted">Carlos {{ money(form.carlos_amount) }} · Gustavo {{ money(form.gustavo_amount) }}</span>
        </button>
        <BaseCollapse :id="sectionId('participants')" :open="participantsOpen">
          <div class="px-4 pb-4"><PartnerSplitInput compact hide-total v-model:total="form.total_amount" v-model:gustavoAmount="form.gustavo_amount" v-model:carlosAmount="form.carlos_amount" /></div>
        </BaseCollapse>
      </section>

      <section class="rounded-lg border border-border-muted" data-testid="income-liquidate-shortfall">
        <button type="button" class="flex w-full items-center justify-between gap-2 p-4 text-left text-sm font-medium text-text-default" :aria-expanded="differenceOpen" :aria-controls="sectionId('difference')" data-testid="income-liquidate-difference-toggle" @click="differenceOpen = !differenceOpen">
          <span>Diferencia</span><span class="text-xs text-text-muted">{{ money(shortfall) }}</span>
        </button>
        <BaseCollapse :id="sectionId('difference')" :open="differenceOpen">
          <div class="px-4 pb-4 space-y-3">
            <p class="text-xs text-text-muted">El saldo sin asignar seguirá pendiente en su ingreso. Registra una deducción si no lo cobrarás, o reprograma su cobro como un nuevo ingreso esperado.</p>
            <p class="text-sm text-text-default" data-testid="income-liquidate-remaining">Sin asignar: {{ money(Math.max(remaining, 0)) }}</p>
            <div v-for="(row, index) in deductions" :key="`deduction-${index}`" class="rounded-lg bg-surface-raised p-3 space-y-2" :data-testid="`income-liquidate-deduction-${index}`">
              <BaseFormRow :cols="2" :gap="3">
                <BaseFormField label="Tipo de deducción"><BaseSelect v-model="row.type" :options="DEDUCTION_TYPE_OPTIONS" placeholder="Seleccionar concepto" :data-testid="`deduction-type-${index}`" /></BaseFormField>
                <BaseFormField label="Monto"><BaseCurrencyInput v-model="row.amount" :suggestion="Math.max(remaining, 0)" :data-testid="`deduction-amount-${index}`" /></BaseFormField>
              </BaseFormRow>
              <BaseFormField v-if="row.type === 'other'" label="Descripción"><BaseInput v-model="row.detail" :data-testid="`deduction-detail-${index}`" /></BaseFormField>
              <BaseButton type="button" size="sm" variant="ghost" :aria-label="`Quitar deducción ${index + 1}`" @click="deductions.splice(index, 1)">Quitar</BaseButton>
            </div>
            <BaseButton type="button" size="sm" variant="secondary" data-testid="income-liquidate-add-deduction" @click="addDeduction">Agregar deducción</BaseButton>
            <div v-for="(row, index) in followUps" :key="`followup-${index}`" class="rounded-lg bg-surface-raised p-3 space-y-2" :data-testid="`income-liquidate-followup-${index}`">
              <BaseFormField label="Ingreso de origen"><BaseSelect v-model="row.income_id" :options="selected.map(record => ({ value: record.id, label: record.concept }))" :data-testid="`followup-origin-${index}`" /></BaseFormField>
              <BaseFormField label="Concepto"><BaseInput v-model="row.concept" :data-testid="`followup-concept-${index}`" /></BaseFormField>
              <BaseFormRow :cols="2" :gap="3">
                <BaseFormField label="Mes esperado de cobro"><BaseInput v-model="row.period_date" type="month" :data-testid="`followup-period-${index}`" /></BaseFormField>
                <BaseFormField label="Monto esperado"><BaseCurrencyInput v-model="row.amount" :data-testid="`followup-amount-${index}`" /></BaseFormField>
              </BaseFormRow>
              <BaseButton type="button" size="sm" variant="ghost" :aria-label="`Quitar ingreso esperado ${index + 1}`" @click="followUps.splice(index, 1)">Quitar</BaseButton>
            </div>
            <BaseButton type="button" size="sm" variant="secondary" data-testid="income-liquidate-add-followup" @click="addFollowUp">Reprogramar saldo como ingreso esperado</BaseButton>
          </div>
        </BaseCollapse>
      </section>

      <section class="rounded-lg border border-border-muted">
        <button type="button" class="flex w-full items-center justify-between gap-2 p-4 text-left text-sm font-medium text-text-default" :aria-expanded="vatOpen" :aria-controls="sectionId('vat')" data-testid="income-liquidate-vat-toggle" @click="vatOpen = !vatOpen">IVA</button>
        <BaseCollapse :id="sectionId('vat')" :open="vatOpen">
          <div class="px-4 pb-4 space-y-3">
            <label class="flex items-center gap-2 text-sm text-text-default"><BaseToggle v-model="showVat" aria-label="Mostrar desglose de IVA" data-testid="income-liquidate-show-vat" />Mostrar desglose de IVA</label>
            <p class="text-xs text-text-muted">Se conserva el IVA registrado en cada ingreso. Este desglose no cambia el valor recibido ni las participaciones.</p>
            <div v-if="showVat" class="space-y-3">
              <div v-for="row in proposal.rows" :key="row.income_id"><p class="mb-1 text-sm font-medium text-text-default">{{ row.record.concept }}</p><VatBreakdown :total="row.amount" :rate="row.record.vat_rate ?? null" /></div>
            </div>
          </div>
        </BaseCollapse>
      </section>

      <SettlementHostingPeriod v-for="record in hostingRecords" :key="`${requestId}-${record.id}`" :record="record" @change="periods[record.id] = $event" />

      <section class="space-y-2" data-testid="income-liquidate-confirmations">
        <h4 class="text-sm font-medium text-text-default">Confirmaciones de pago</h4>
        <p v-if="contextLoading" class="text-xs text-text-subtle">Verificando los destinatarios…</p>
        <div v-for="record in selected" :key="record.id" class="space-y-1">
          <BaseCheckbox v-model="sendConfirmations[record.id]" :disabled="!contexts[record.id]?.can_send || !Number(form.total_amount)" :disabled-reason="contexts[record.id]?.blocked_reason || 'Sin valor recibido no hay pago que confirmar.'" :data-testid="`income-liquidate-confirmation-${record.id}`">{{ record.concept }}<span v-if="contexts[record.id]?.can_send"> · {{ contexts[record.id].recipient }}</span></BaseCheckbox>
          <p v-if="contexts[record.id]?.blocked_reason" class="text-xs text-text-subtle">{{ contexts[record.id].blocked_reason }}</p>
        </div>
      </section>
      <BaseFormField label="Notas"><BaseTextarea v-model="form.notes" :rows="2" data-testid="income-liquidate-notes" /></BaseFormField>
    </form>

    <template #footer>
      <div class="space-y-2">
        <p v-if="error" class="text-sm text-danger-strong" role="alert">{{ error }}</p>
        <p :id="sectionId('submit-reason')" class="min-h-4 text-right text-xs text-danger-strong" aria-live="polite" data-testid="income-liquidate-submit-reason">{{ review || saving ? '' : blockReason }}</p>
        <div class="flex flex-col-reverse items-stretch gap-2 panel-portrait:flex-row panel-portrait:justify-end">
          <BaseButton v-if="review" type="button" variant="secondary" :disabled="saving" disabled-reason="Espera a que termine el registro de la liquidación." data-testid="income-liquidate-review-back" @click="back">Volver a editar</BaseButton>
          <BaseButton v-else type="button" variant="secondary" :disabled="saving || preparing" disabled-reason="Espera a que termine la liquidación." @click="emit('close')">Cancelar</BaseButton>
          <BaseButton v-if="review" type="button" :loading="saving" :disabled="saving" disabled-reason="La liquidación se está registrando." data-testid="income-liquidate-confirm" @click="confirm">Confirmar y liquidar</BaseButton>
          <BaseButton v-else type="submit" :form="formId" :loading="saving || preparing" :disabled="Boolean(blockReason) || saving || preparing" :disabled-reason="blockReason || 'Espera a que termine la liquidación.'" :aria-describedby="sectionId('submit-reason')" data-testid="income-liquidate-submit">Liquidar</BaseButton>
        </div>
      </div>
    </template>
  </BaseModal>
</template>
