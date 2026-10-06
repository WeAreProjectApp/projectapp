// Pure engine of the bulk abono flow: eligibility, the oldest-first
// distribution the modal pre-fills, and the success-toast copy. No Vue on
// purpose — the modal, the bar and the page must agree on these rules, and
// a composable would drag reactivity into what is plain arithmetic.
import { settlementBlockedReason } from './incomeSettlement';

// An abono lands in the company pocket, so only company expected incomes
// with something left to collect qualify (the liquidate modal enforces the
// same ledger rule for its Bolsillo destination).
export function isSettleEligible(row) {
  return (
    row?.kind === 'expected'
    && Number(row.pending_amount) > 0
    && row.ledger === 'company'
    && !settlementBlockedReason(row)
  );
}

// Stable copy ordered the way the money fills: oldest expected date first,
// id as the deterministic tie-break. Exported so the modal's table renders
// in exactly this order — a distribution shown in another order would read
// as arbitrary.
export function sortForSettle(records) {
  return [...(records ?? [])].sort((a, b) => {
    const byDate = String(a.period_date).localeCompare(String(b.period_date));
    return byDate !== 0 ? byDate : a.id - b.id;
  });
}

// The proposed reparto: each income takes its full pending until the money
// runs out, the one it runs out on stays partial, the rest get 0. Returns
// one entry per record (zeros included) so the modal maps entries 1:1 to
// its inputs. Never assigns above a row's pending — an excess total is the
// summary's business, not the distribution's.
export function distributeOldestFirst(records, total) {
  let remaining = Number(total) > 0 ? Number(total) : 0;
  return sortForSettle(records).map((row) => {
    const pending = Math.max(Number(row.pending_amount) || 0, 0);
    const amount = Math.min(remaining, pending);
    remaining -= amount;
    return { income_id: row.id, amount };
  });
}

// Success-toast detail from the refreshed rows the endpoint returns: only
// the expected rows carry a payment_status worth narrating.
export function describeBulkSettleResult(results) {
  const expected = (results ?? []).filter((row) => row.kind === 'expected');
  const paid = expected.filter((row) => row.payment_status === 'paid').length;
  const partial = expected.filter(
    (row) => row.payment_status === 'partial',
  ).length;
  const paidPhrase = paid === 1
    ? '1 ingreso quedó pagado'
    : `${paid} ingresos quedaron pagados`;
  const partialPhrase = partial === 1
    ? '1 quedó parcial'
    : `${partial} quedaron parciales`;
  if (paid && partial) return `${paidPhrase} y ${partialPhrase}.`;
  if (paid) return `${paidPhrase}.`;
  if (partial) {
    return partial === 1
      ? '1 ingreso quedó parcial.'
      : `${partial} ingresos quedaron parciales.`;
  }
  return '';
}
