import { computed, ref } from 'vue';
import { vatBreakdown } from '~/utils/accountingVat';

/** Per-source drafts. Only an explicit edit adds fiscal fields to the request. */
export function useSettlementVat(records, { form, proposal, manual, credit }) {
  const drafts = ref({});
  const locks = ref({});
  function reset() {
    drafts.value = Object.fromEntries(records.value.map((row) => [row.id, {
      rate: row.vat_rate ?? null, enabled: Number(row.vat_rate) > 0,
      lastRate: Number(row.vat_rate) > 0 ? row.vat_rate : null,
      touched: false, capture: null, invalid: false,
    }]));
    // The opening preview supplies authoritative lock reasons. Until it
    // arrives, do not offer a fiscal write that might already be forbidden.
    locks.value = Object.fromEntries(records.value.map((row) => [row.id, 'Verificando si el IVA admite cambios…']));
  }
  function setLocks(rows) {
    locks.value = Object.fromEntries(rows.map((row) => [row.income_id, row.vat_blocked_reason || '']));
  }
  function updateAmount(id, value) {
    const excess = credit.value;
    const amounts = Object.fromEntries(proposal.value.rows.map((row) => [row.income_id, row.amount]));
    manual.value = { ...amounts, [id]: Number(value) };
    form.value.total_amount = Math.round((Object.values(manual.value).reduce((sum, amount) => sum + amount, 0) + excess) * 100) / 100;
  }
  function capture(id, value) {
    const draft = drafts.value[id];
    draft.capture = value;
    const values = value && vatBreakdown(value.amount, draft.rate, value.amount_mode);
    draft.invalid = !values;
    if (values) updateAmount(id, values.total);
  }
  function setRate(id, value) {
    if (locks.value[id]) return;
    const draft = drafts.value[id];
    draft.rate = value === '' || value == null ? null : value;
    draft.touched = true;
    if (Number(draft.rate) > 0) draft.lastRate = draft.rate;
    if (draft.rate !== null) draft.enabled = Number(draft.rate) > 0;
    if (draft.capture) capture(id, draft.capture);
  }
  function toggle(id, enabled) {
    if (locks.value[id]) return;
    drafts.value[id].enabled = enabled;
    setRate(id, enabled ? drafts.value[id].lastRate : 0);
  }
  function clearCaptures() {
    for (const draft of Object.values(drafts.value)) {
      draft.capture = null;
      draft.invalid = false;
    }
  }
  const updates = computed(() => records.value.flatMap((row) => {
    const draft = drafts.value[row.id];
    return draft && (draft.touched || draft.capture) ? [{
      income_id: row.id, vat_rate: draft.rate, ...(draft.capture || {}),
    }] : [];
  }));
  const blockReason = computed(() => {
    for (const draft of Object.values(drafts.value)) {
      if (draft.enabled && (draft.rate === null || !(Number(draft.rate) > 0))) return 'Define el porcentaje de IVA del ingreso que activaste.';
      if (draft.invalid || !vatBreakdown(0, draft.rate)) return 'Revisa el importe y el porcentaje de IVA: debe estar entre 0 y 100, con hasta dos decimales.';
    }
    return '';
  });
  return { drafts, locks, reset, setLocks, setRate, toggle, capture, clearCaptures, updates, blockReason };
}
