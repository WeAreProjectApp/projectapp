import { settlementProposal } from '../../utils/incomeSettlementAllocation';

function expectedIncome(id, pendingAmount, periodDate) {
  return {
    id,
    concept: `Ingreso ${id}`,
    pending_amount: pendingAmount,
    period_date: periodDate,
  };
}

describe('settlementProposal', () => {
  // Falla si el orden de selección desplaza el pago del ingreso más antiguo.
  it('covers the oldest balance before a later balance selected first', () => {
    const proposal = settlementProposal([
      expectedIncome(12, '100.00', '2026-02-01'),
      expectedIncome(11, '100.00', '2026-01-01'),
    ], 150, []);

    expect(proposal.rows.map(({ income_id, amount }) => ({ income_id, amount }))).toEqual([
      { income_id: 11, amount: 100 },
      { income_id: 12, amount: 50 },
    ]);
  });

  // Falla si una deducción conjunta vuelve a cargarse al último ingreso en vez
  // de repartirla junto con el abono que cubrió ambos ingresos.
  it('splits a 180 receipt and a 20 deduction evenly across two 100 balances', () => {
    const proposal = settlementProposal([
      expectedIncome(11, '100.00', '2026-01-01'),
      expectedIncome(12, '100.00', '2026-02-01'),
    ], 180, [{ type: 'bank_fee', amount: 20 }]);

    expect(proposal.rows.map(({ income_id, amount, deducted }) => ({ income_id, amount, deducted }))).toEqual([
      { income_id: 11, amount: 90, deducted: 10 },
      { income_id: 12, amount: 90, deducted: 10 },
    ]);
  });

  // Falla si redondear ambas filas pierde el centavo de la deducción o del abono.
  it('assigns the tied deduction cent to the oldest income', () => {
    const proposal = settlementProposal([
      expectedIncome(11, '100.00', '2026-01-01'),
      expectedIncome(12, '100.00', '2026-02-01'),
    ], 179.99, [{ type: 'bank_fee', amount: 20.01 }]);

    expect(proposal.rows.map(({ income_id, amount, deducted }) => ({ income_id, amount, deducted }))).toEqual([
      { income_id: 11, amount: 89.99, deducted: 10.01 },
      { income_id: 12, amount: 90, deducted: 10 },
    ]);
  });

  // Falla si editar una imputación vuelve a descontar la deducción de su
  // monto, o le asigna una deducción a una fila sin dinero recibido.
  it('keeps manual receipt amounts and assigns no deduction to a zero-weight row', () => {
    const proposal = settlementProposal([
      expectedIncome(11, '100.00', '2026-01-01'),
      expectedIncome(12, '100.00', '2026-02-01'),
    ], 180, [{ type: 'bank_fee', amount: 20 }], { 11: 100, 12: 0 });

    expect(proposal.rows.map(({ income_id, amount, deducted }) => ({ income_id, amount, deducted }))).toEqual([
      { income_id: 11, amount: 100, deducted: 20 },
      { income_id: 12, amount: 0, deducted: 0 },
    ]);
  });
});
