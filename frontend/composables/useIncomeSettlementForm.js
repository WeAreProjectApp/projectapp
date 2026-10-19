import { computed, ref, watch } from 'vue';
import { useAccountingStore } from '~/stores/accounting';
import { settlementBlockedReason } from '~/utils/incomeSettlement';
import { settlementProposal } from '~/utils/incomeSettlementAllocation';
import { todayISO } from '~/utils/periodDates';

const requestUuid = () => globalThis.crypto?.randomUUID?.()
  ?? 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const value = Math.floor(Math.random() * 16);
    return (c === 'x' ? value : (value & 3) | 8).toString(16);
  });

export function useIncomeSettlementForm(props, emit) {
  const store = useAccountingStore();
  const records = computed(() => props.records.length ? props.records : (props.record ? [props.record] : []));
  const personal = computed(() => records.value[0]?.ledger !== 'company');
  const form = ref({ total_amount: null, period_date: '', destination: 'pocket', notes: '', gustavo_amount: '', carlos_amount: '' });
  const exactDate = ref(true);
  const requestId = ref('');
  const deductions = ref([]);
  const followUps = ref([]);
  const periods = ref({});
  const participantsOpen = ref(false);
  const differenceOpen = ref(false);
  const vatOpen = ref(false);
  const showVat = ref(true);
  const manual = ref(null);
  const contexts = ref({});
  const sendConfirmations = ref({});
  const contextLoading = ref(false);
  const preparing = ref(false);
  const dispatched = ref(false);
  watch(() => props.saving, (value, old) => { if (old && !value) dispatched.value = false; });
  const error = ref('');
  const review = ref(null);
  const pendingPayload = ref(null);
  let contextRequest = 0;
  let autoExpanded = false;

  const activeDeductions = computed(() => deductions.value.filter((row) => row.type || row.detail.trim() || Number(row.amount)));
  const activeFollowUps = computed(() => followUps.value.filter((row) => row.period_date || Number(row.amount) || row.concept.trim()));
  const proposal = computed(() => settlementProposal(records.value, form.value.total_amount, activeDeductions.value, manual.value));
  const receivedById = computed(() => Object.fromEntries(proposal.value.rows.map((row) => [row.income_id, row.amount])));
  const shortfall = computed(() => Math.max(proposal.value.pending - (Number(form.value.total_amount) || 0), 0));
  const followUpTotal = computed(() => activeFollowUps.value.reduce((sum, row) => sum + (Number(row.amount) || 0), 0));
  const remaining = computed(() => Math.round((proposal.value.pending - proposal.value.allocated - proposal.value.deducted - followUpTotal.value) * 100) / 100);
  const credit = computed(() => Math.max(Math.round(((Number(form.value.total_amount) || 0) - proposal.value.allocated) * 100) / 100, 0));
  const hostingRecords = computed(() => records.value.filter((row) => row.origin === 'hosting' && !row.period_start));

  watch(shortfall, (value) => {
    if (value > 0 && !autoExpanded) {
      autoExpanded = true;
      differenceOpen.value = true;
    }
  });

  function buildPayload() {
    const confirmationIds = proposal.value.rows.filter((row) => row.amount > 0 && contexts.value[row.income_id]?.can_send && sendConfirmations.value[row.income_id]).map((row) => row.income_id);
    const payload = {
      income_ids: records.value.map((row) => row.id),
      total_amount: Number(form.value.total_amount) || 0,
      period_date: form.value.period_date, destination: form.value.destination,
      notes: form.value.notes, request_id: requestId.value,
      deductions: activeDeductions.value.map((row) => ({ type: row.type, amount: row.amount, detail: row.type === 'other' ? row.detail.trim() : '' })),
      expected_incomes: activeFollowUps.value.map((row) => ({ ...row, income_id: Number(row.income_id), concept: row.concept.trim() })),
      periods: Object.entries(periods.value).filter(([, value]) => value?.period).map(([id, value]) => ({ income_id: Number(id), ...value.period })),
      send_payment_confirmation: confirmationIds.length > 0 && Number(form.value.total_amount) > 0,
      confirmation_income_ids: confirmationIds,
    };
    if (manual.value) payload.allocations = proposal.value.rows.map((row) => ({ income_id: row.income_id, amount: row.amount }));
    if (!personal.value && form.value.gustavo_amount !== '' && form.value.carlos_amount !== '') {
      payload.gustavo_amount = form.value.gustavo_amount;
      payload.carlos_amount = form.value.carlos_amount;
    }
    return payload;
  }

  const blockReason = computed(() => {
    if (!records.value.length) return 'Selecciona al menos un ingreso.';
    if (contextLoading.value && records.value.some((row) => row.client)) return 'Verificando los destinatarios de la confirmación…';
    const blocked = records.value.find((row) => settlementBlockedReason(row));
    if (blocked) return settlementBlockedReason(blocked);
    if (Number(form.value.total_amount) < 0) return 'El valor recibido no puede ser negativo.';
    if (!(Number(form.value.total_amount) > 0) && !activeDeductions.value.length && !activeFollowUps.value.length) return 'Ingresa un valor recibido o resuelve la diferencia.';
    if (!form.value.period_date) return 'Indica cuándo se recibió el pago.';
    if (activeDeductions.value.some((row) => !row.type || !(Number(row.amount) > 0) || (row.type === 'other' && !row.detail.trim()))) return 'Completa el tipo, monto y descripción de las deducciones.';
    if (activeFollowUps.value.some((row) => !row.income_id || !row.concept.trim() || !row.period_date || !(Number(row.amount) > 0))) return 'Completa el origen, concepto, mes y monto del nuevo ingreso esperado.';
    if (remaining.value < 0 || proposal.value.rows.some((row) => {
      const scheduled = activeFollowUps.value.filter((entry) => Number(entry.income_id) === row.income_id).reduce((sum, entry) => sum + Number(entry.amount || 0), 0);
      return row.amount < 0 || row.amount + row.deducted + scheduled > row.pending + 0.001;
    })) return 'La distribución supera un saldo pendiente. Recalcula el reparto o revisa los ajustes.';
    if (manual.value && Object.values(manual.value).some((value) => Number(value) < 0)) return 'El reparto contiene montos negativos.';
    if (manual.value && proposal.value.allocated <= 0 && Number(form.value.total_amount) > 0 && !activeDeductions.value.length && !activeFollowUps.value.length) return 'Imputa al menos una fila o reduce el valor recibido.';
    if (proposal.value.allocated > (Number(form.value.total_amount) || 0) + 0.001) return 'El reparto supera el valor recibido.';
    if (!personal.value && Number(form.value.gustavo_amount) + Number(form.value.carlos_amount) > Number(form.value.total_amount)) return 'La suma de socios supera el valor recibido.';
    if (credit.value > 0 && new Set(records.value.map((row) => row.client ?? null)).size > 1) return 'Con clientes mezclados el excedente no se puede asignar como saldo a favor.';
    if (Object.values(periods.value).some((value) => value?.invalid)) return 'Completa el período de hosting que comenzaste, o déjalo vacío.';
    return '';
  });

  async function loadContexts() {
    const current = ++contextRequest;
    contextLoading.value = true;
    const result = await store.previewIncomeSettlement(buildPayload());
    if (current !== contextRequest || !props.open) return;
    contextLoading.value = false;
    if (!result.success) {
      contexts.value = Object.fromEntries(records.value.map((row) => [row.id, { can_send: false, blocked_reason: 'No se pudo verificar el correo. Puedes volver a intentar al liquidar.' }]));
      return;
    }
    contexts.value = Object.fromEntries(result.data.rows.map((row) => [row.income_id, row.confirmation]));
  }

  watch(() => [props.open, props.records, props.record], () => {
    if (!props.open) { contextRequest += 1; return; }
    if (!records.value.length) return;
    requestId.value = requestUuid(); exactDate.value = true;
    deductions.value = []; followUps.value = []; periods.value = {}; manual.value = null;
    participantsOpen.value = false; differenceOpen.value = false; vatOpen.value = false;
    showVat.value = true; autoExpanded = false; error.value = ''; review.value = null; pendingPayload.value = null; dispatched.value = false;
    contexts.value = {};
    sendConfirmations.value = Object.fromEntries(records.value.map((row) => [row.id, true]));
    const initialTotal = records.value.reduce((sum, row) => sum + Number(row.pending_amount ?? row.total_amount ?? 0), 0);
    const half = Math.floor(initialTotal / 2);
    form.value = { total_amount: initialTotal, period_date: todayISO(), destination: personal.value ? 'partners' : 'pocket', notes: '', gustavo_amount: half, carlos_amount: half };
    loadContexts();
  }, { immediate: true });

  function addDeduction() { deductions.value.push({ type: '', detail: '', amount: Math.max(0, remaining.value) || null }); }
  function addFollowUp() {
    const origin = proposal.value.rows.find((row) => row.pending > row.amount + row.deducted) ?? proposal.value.rows[0];
    followUps.value.push({ income_id: origin?.income_id, concept: `${origin?.record.concept ?? ''} - saldo`, period_date: '', amount: Math.max(0, remaining.value) || null });
  }
  function editAllocation(id, value) {
    if (!manual.value) manual.value = Object.fromEntries(proposal.value.rows.map((row) => [row.income_id, row.amount]));
    manual.value = { ...manual.value, [id]: value };
  }
  function recalculate() { manual.value = null; }
  async function submit() {
    if (props.saving || preparing.value || dispatched.value || blockReason.value) return;
    preparing.value = true; error.value = '';
    const payload = buildPayload();
    const currentRequestId = requestId.value;
    const result = await store.previewIncomeSettlement(payload);
    preparing.value = false;
    if (!props.open || currentRequestId !== requestId.value) return;
    if (JSON.stringify(payload) !== JSON.stringify(buildPayload())) {
      error.value = 'La liquidación cambió durante la revisión. Vuelve a pulsar Liquidar.';
      return;
    }
    if (!result.success) { error.value = result.message || result.error || 'No se pudo revisar la liquidación. Inténtalo de nuevo.'; return; }
    pendingPayload.value = { ...payload, preview_hash: result.data.preview_hash };
    if (payload.send_payment_confirmation) review.value = result.data;
    else { dispatched.value = true; emit('submit', pendingPayload.value); }
  }
  function confirm() {
    if (!props.saving && !dispatched.value && pendingPayload.value) {
      dispatched.value = true; emit('submit', pendingPayload.value);
    }
  }
  function back() { review.value = null; pendingPayload.value = null; dispatched.value = false; }

  return {
    records, personal, form, exactDate, requestId, deductions, followUps, periods,
    participantsOpen, differenceOpen, vatOpen, showVat, manual, contexts,
    sendConfirmations, contextLoading, preparing, error, review, proposal,
    shortfall, remaining, credit, hostingRecords, blockReason, receivedById,
    addDeduction, addFollowUp, editAllocation, recalculate, submit, confirm, back,
  };
}
