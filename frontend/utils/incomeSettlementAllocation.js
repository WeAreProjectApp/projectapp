import { sortForSettle } from './settleAllocation';

const cents = (value) => Math.round((Number(value) || 0) * 100);

/** Stable largest-remainder distribution, using integer cents. */
export function distributeCents(amount, weights) {
  const total = weights.reduce((sum, value) => sum + value, 0);
  if (!amount) return weights.map(() => 0);
  if (!total) return null;
  const quotas = weights.map((weight) => amount * weight / total);
  const result = quotas.map(Math.floor);
  let remaining = amount - result.reduce((sum, value) => sum + value, 0);
  const order = weights.map((_, index) => index).sort((a, b) => (
    (quotas[b] - result[b]) - (quotas[a] - result[a]) || a - b
  ));
  for (const index of order) {
    if (remaining > 0 && weights[index] > 0) {
      result[index] += 1;
      remaining -= 1;
    }
  }
  return result;
}

export function settlementProposal(records, received, deductions, manual = null) {
  const ordered = sortForSettle(records);
  const pending = ordered.map((row) => Math.max(0, cents(row.pending_amount)));
  const payment = Math.max(0, cents(received));
  const fees = deductions.reduce((sum, row) => sum + Math.max(0, cents(row.amount)), 0);
  let remaining = Math.min(payment + fees, pending.reduce((sum, value) => sum + value, 0));
  const coverage = pending.map((value) => {
    const covered = Math.min(value, remaining);
    remaining -= covered;
    return covered;
  });
  const cash = manual ? ordered.map((row) => Math.max(0, cents(manual[row.id]))) : coverage;
  const feeWeights = manual && cash.some((value) => value > 0) ? cash : coverage;
  const apportioned = distributeCents(fees, feeWeights) ?? feeWeights.map(() => 0);
  const rows = ordered.map((record, index) => ({
    record, income_id: record.id,
    amount: (cash[index] - (manual ? 0 : apportioned[index])) / 100,
    deducted: apportioned[index] / 100, pending: pending[index] / 100,
  }));
  return {
    rows, allocated: rows.reduce((sum, row) => sum + row.amount, 0),
    deducted: fees / 100,
    pending: pending.reduce((sum, value) => sum + value, 0) / 100,
  };
}
