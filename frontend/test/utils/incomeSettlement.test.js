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
  // Falla si una fila local todavía no refrescada permite liquidar una cuenta sin emitir.
  test.each(['', 'draft', 'cancelled'])(
    'blocks a client income whose collection account is %s',
    (collectionAccountStatus) => {
      expect(settlementBlockedReason(expectedIncome({
        collection_account_status: collectionAccountStatus,
      }))).toBe('Primero genera y emite una cuenta de cobro para este ingreso.');
    },
  );

  test.each(['issued', 'paid'])(
    'allows a client income whose collection account is %s',
    (collectionAccountStatus) => {
      expect(settlementBlockedReason(expectedIncome({
        collection_account_status: collectionAccountStatus,
      }))).toBe('');
    },
  );

  it('allows an expected income without a client', () => {
    expect(settlementBlockedReason(expectedIncome({ client: null }))).toBe('');
  });

  it('keeps the server blocker over the stale-row calculation', () => {
    expect(settlementBlockedReason(expectedIncome({
      collection_account_status: 'issued',
      settlement_blocked_reason: 'El ingreso cambió mientras revisabas.',
    }))).toBe('El ingreso cambió mientras revisabas.');
  });
});
