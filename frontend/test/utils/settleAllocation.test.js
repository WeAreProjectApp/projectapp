import {
  describeBulkSettleResult,
  distributeOldestFirst,
  isSettleEligible,
  sortForSettle,
} from '../../utils/settleAllocation';

function expectedRow(overrides = {}) {
  return {
    id: 1,
    kind: 'expected',
    ledger: 'company',
    period_date: '2026-05-01',
    pending_amount: '500000.00',
    ...overrides,
  };
}

const THREE_ROWS = [
  expectedRow({ id: 21, period_date: '2026-05-01', pending_amount: '500000.00' }),
  expectedRow({ id: 22, period_date: '2026-06-01', pending_amount: '300000.00' }),
  expectedRow({ id: 23, period_date: '2026-07-01', pending_amount: '200000.00' }),
];

describe('isSettleEligible', () => {
  it('admits only company expected rows with a pending balance', () => {
    expect(isSettleEligible(expectedRow())).toBe(true);
    expect(isSettleEligible(expectedRow({ kind: 'liquid' }))).toBe(false);
    expect(isSettleEligible(expectedRow({ kind: 'lost' }))).toBe(false);
    expect(isSettleEligible(expectedRow({ pending_amount: '0.00' }))).toBe(false);
    expect(isSettleEligible(expectedRow({ ledger: 'gustavo' }))).toBe(false);
  });

  // Falla si el abono masivo vuelve a excluir una fila cobrable sólo por no tener cuenta.
  test.each(['', 'draft', 'cancelled'])(
    'includes a client row whose collection account is %s',
    (collectionAccountStatus) => {
      expect(isSettleEligible(expectedRow({
        client: 5,
        collection_account_status: collectionAccountStatus,
      }))).toBe(true);
    },
  );

  test.each(['issued', 'paid'])(
    'keeps a client row eligible when its collection account is %s',
    (collectionAccountStatus) => {
      expect(isSettleEligible(expectedRow({
        client: 5,
        collection_account_status: collectionAccountStatus,
      }))).toBe(true);
    },
  );
});

describe('sortForSettle', () => {
  it('orders by expected date and breaks ties by id', () => {
    const shuffled = [
      expectedRow({ id: 9, period_date: '2026-06-01' }),
      expectedRow({ id: 3, period_date: '2026-05-01' }),
      expectedRow({ id: 1, period_date: '2026-06-01' }),
    ];

    expect(sortForSettle(shuffled).map((row) => row.id)).toEqual([3, 1, 9]);
  });
});

describe('distributeOldestFirst', () => {
  it('fills each pending fully until the money runs out', () => {
    expect(distributeOldestFirst(THREE_ROWS, 600000)).toEqual([
      { income_id: 21, amount: 500000 },
      { income_id: 22, amount: 100000 },
      { income_id: 23, amount: 0 },
    ]);
  });

  it('covers everything when the total matches the pendings', () => {
    expect(distributeOldestFirst(THREE_ROWS, 1000000)).toEqual([
      { income_id: 21, amount: 500000 },
      { income_id: 22, amount: 300000 },
      { income_id: 23, amount: 200000 },
    ]);
  });

  it('leaves a single partial when the total is below the first pending', () => {
    const amounts = distributeOldestFirst(THREE_ROWS, 200000);

    expect(amounts[0]).toEqual({ income_id: 21, amount: 200000 });
    expect(amounts.slice(1).every((entry) => entry.amount === 0)).toBe(true);
  });

  it('never assigns above the pendings on an excess total', () => {
    expect(distributeOldestFirst(THREE_ROWS, 2000000)).toEqual([
      { income_id: 21, amount: 500000 },
      { income_id: 22, amount: 300000 },
      { income_id: 23, amount: 200000 },
    ]);
  });

  it('returns zeros for a zero total and an empty list without rows', () => {
    expect(
      distributeOldestFirst(THREE_ROWS, 0).every((entry) => entry.amount === 0),
    ).toBe(true);
    expect(distributeOldestFirst([], 100000)).toEqual([]);
  });
});

describe('describeBulkSettleResult', () => {
  it('phrases the pagados and parciales mix in Spanish', () => {
    const paid = { kind: 'expected', payment_status: 'paid' };
    const partial = { kind: 'expected', payment_status: 'partial' };
    const child = { kind: 'liquid', payment_status: null };

    expect(describeBulkSettleResult([paid, paid, partial, child]))
      .toBe('2 ingresos quedaron pagados y 1 quedó parcial.');
    expect(describeBulkSettleResult([paid, child])).toBe('1 ingreso quedó pagado.');
    expect(describeBulkSettleResult([partial])).toBe('1 ingreso quedó parcial.');
    expect(describeBulkSettleResult([])).toBe('');
  });
});
