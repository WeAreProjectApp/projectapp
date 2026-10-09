import {
  clientPendingAfter,
  formatPaymentDate,
  paymentConfirmationDetail,
  paymentConfirmationWarning,
} from '../../utils/paymentConfirmation';

describe('formatPaymentDate', () => {
  it('names the month when only the month is known', () => {
    expect(formatPaymentDate('2026-07', false)).toBe('julio de 2026');
  });

  it('keeps the exact day of an exact date, without shifting it', () => {
    expect(formatPaymentDate('2026-07-01', true)).toBe('Mié, 1 jul 2026');
  });

  it('is empty without a date', () => {
    expect(formatPaymentDate('', true)).toBe('');
  });
});

describe('clientPendingAfter', () => {
  it('subtracts the payment and the deductions from the pending balance', () => {
    expect(clientPendingAfter({
      pending: '600000.00', received: 400000, deductions: 8000, rescheduled: '0.00',
    })).toBe(192000);
  });

  it('still counts what was rescheduled into follow-ups', () => {
    expect(clientPendingAfter({
      pending: 600000, received: 600000, deductions: 0, rescheduled: '300000.00',
    })).toBe(300000);
  });

  it('never goes below zero on the income itself', () => {
    expect(clientPendingAfter({ pending: 100, received: 150 })).toBe(0);
  });
});

describe('payment confirmation notices', () => {
  const sent = { requested: true, status: 'sent', recipient: 'pagos@acme.co', error: '' };

  it('names the recipient of a sent confirmation', () => {
    expect(paymentConfirmationDetail(sent))
      .toBe('Confirmación de pago enviada a pagos@acme.co.');
    expect(paymentConfirmationWarning(sent, 7)).toBeNull();
  });

  it('points a failed send at the history of that income', () => {
    const warning = paymentConfirmationWarning(
      { requested: true, status: 'failed', recipient: 'pagos@acme.co', error: 'El correo no salió.' },
      7,
    );

    expect(warning.title).toBe('La confirmación de pago no salió');
    expect(warning.action.label).toBe('Ver correos de este ingreso');
    expect(warning.action.to.query).toEqual({
      tab: 'sends', entity_type: 'income', object_id: '7',
    });
  });

  it('says why a requested confirmation was skipped', () => {
    const warning = paymentConfirmationWarning(
      { requested: true, status: 'skipped', recipient: '', error: 'Sin valor recibido.' },
      7,
    );

    expect(warning.detail).toBe('Sin valor recibido.');
    expect(warning.action).toBeUndefined();
  });

  it('stays quiet when no confirmation was asked for', () => {
    const block = { requested: false, status: 'not_requested', recipient: '', error: '' };

    expect(paymentConfirmationDetail(block)).toBe('');
    expect(paymentConfirmationWarning(block, 7)).toBeNull();
    expect(paymentConfirmationWarning(undefined, 7)).toBeNull();
  });
});
