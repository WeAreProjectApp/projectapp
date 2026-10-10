import { settlementBlockedReason } from '../../utils/incomeSettlement';

function expectedIncome(overrides = {}) {
  return {
    id: 41,
    kind: 'expected',
    pending_amount: '250000.00',
    payment_status: 'pending',
    client: 7,
    ...overrides,
  };
}

describe('settlementBlockedReason', () => {
  // Falla si una fila local vuelve a impedir registrar un abono válido sin cuenta emitida.
  test.each(['', 'draft', 'cancelled'])(
    'allows a client income whose collection account is %s',
    (collectionAccountStatus) => {
      expect(settlementBlockedReason(expectedIncome({
        collection_account_status: collectionAccountStatus,
      }))).toBe('');
    },
  );

  // Falla si las restricciones de saldo y tipo dejan de proteger el abono.
  test.each([
    [{ kind: 'liquid' }, 'Solo se puede liquidar un ingreso esperado.'],
    [{ payment_status: 'paid', pending_amount: '0.00' }, 'Este ingreso esperado ya está completamente pagado.'],
    [{ can_settle: false }, 'Actualiza el ingreso antes de liquidarlo.'],
  ])('keeps the concrete local blocker for %o', (overrides, expected) => {
    expect(settlementBlockedReason(expectedIncome(overrides))).toBe(expected);
  });

  it('keeps the server blocker over the stale-row calculation', () => {
    expect(settlementBlockedReason(expectedIncome({
      collection_account_status: 'issued',
      settlement_blocked_reason: 'El ingreso cambió mientras revisabas.',
    }))).toBe('El ingreso cambió mientras revisabas.');
  });
});
