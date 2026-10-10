/** Payment eligibility, also checked on stale rows before the next API refresh. */
export function settlementBlockedReason(row) {
  if (row?.settlement_blocked_reason) return row.settlement_blocked_reason;
  if (row?.kind !== 'expected') return 'Solo se puede liquidar un ingreso esperado.';
  if (row.payment_status === 'paid' || Number(row.pending_amount) <= 0) {
    return 'Este ingreso esperado ya está completamente pagado.';
  }
  return row.can_settle === false ? 'Actualiza el ingreso antes de liquidarlo.' : '';
}
