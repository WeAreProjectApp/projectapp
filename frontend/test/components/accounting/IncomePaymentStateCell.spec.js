/**
 * Tests for IncomePaymentStateCell.
 *
 * The "Cobro" cell carries two independent facts: how much of the income has
 * been collected, and whether its notices were silenced. A muted income must
 * not read as one nobody is following up on, which is the whole point of the
 * badge — so these assert the chip's exact wording.
 */
import { mount } from '@vue/test-utils';
import IncomePaymentStateCell from '../../../components/accounting/IncomePaymentStateCell.vue';

function mountCell(row = {}) {
  return mount(IncomePaymentStateCell, {
    props: {
      row: {
        id: 7,
        payment_status: 'pending',
        payment_status_label: 'Pendiente',
        pending_amount: '600000.00',
        reminders_muted: false,
        reminders_muted_until: null,
        ...row,
      },
    },
  });
}

describe('IncomePaymentStateCell', () => {
  it('shows the outstanding balance on a partially collected income', () => {
    const wrapper = mountCell({
      payment_status: 'partial',
      payment_status_label: 'Parcial',
    });

    expect(wrapper.text()).toContain('Parcial');
    expect(wrapper.text()).toContain('faltan');
    expect(wrapper.text()).toContain('600.000');
  });

  it('marks an indefinitely muted income', () => {
    const wrapper = mountCell({ reminders_muted: true });
    const chip = wrapper.find('[data-testid="income-muted-7"]');

    expect(chip.text()).toBe('Silenciado');
    expect(chip.attributes('title')).toBe('Avisos silenciados indefinidamente');
  });

  it('spells out the resume date when the mute has one', () => {
    const wrapper = mountCell({
      reminders_muted: true,
      reminders_muted_until: '2026-09-30',
    });
    const chip = wrapper.find('[data-testid="income-muted-7"]');

    expect(chip.text()).toBe('Silenciado hasta 30 sep');
    expect(chip.attributes('title')).toContain('30 sep 2026');
  });

  it('leaves an un-muted income showing only its collection state', () => {
    // 'paid' rather than 'pending': only paid and partial carry a chip, so it
    // is the positive anchor that proves the cell rendered at all.
    const wrapper = mountCell({
      payment_status: 'paid',
      payment_status_label: 'Pagado',
    });

    expect(wrapper.text()).toContain('Pagado');
    expect(wrapper.find('[data-testid="income-muted-7"]').exists()).toBe(false);
  });

  // Falla si un ingreso pagado deja de decir que todavía necesita su cuenta.
  it('shows the pending collection-account cue after payment completes', () => {
    const wrapper = mountCell({
      payment_status: 'paid',
      payment_status_label: 'Pagado',
      requires_collection_account: true,
    });

    expect(wrapper.get('[data-testid="income-account-pending-7"]').text())
      .toBe('Cuenta pendiente de emitir');
  });

  // Falla si la advertencia documental se muestra para ingresos que ya tienen cuenta.
  it('keeps a paid income with an issued account free of the pending-account cue', () => {
    const wrapper = mountCell({
      payment_status: 'paid',
      payment_status_label: 'Pagado',
      requires_collection_account: false,
    });

    expect(wrapper.get('[data-testid="income-payment-7"]').text()).toContain('Pagado');
    expect(wrapper.find('[data-testid="income-account-pending-7"]').exists()).toBe(false);
  });
});
