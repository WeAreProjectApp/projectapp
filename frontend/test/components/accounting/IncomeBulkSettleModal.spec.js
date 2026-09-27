import { mount } from '@vue/test-utils';
import IncomeBulkSettleModal from '../../../components/accounting/IncomeBulkSettleModal.vue';

function expectedRow(overrides = {}) {
  return {
    id: 21,
    concept: 'Kore - Fase 2 Entrega',
    kind: 'expected',
    ledger: 'company',
    period_date: '2026-05-01',
    period_label: 'Mayo 2026',
    pending_amount: '500000.00',
    client: 5,
    client_name: 'Kore SAS',
    ...overrides,
  };
}

const THREE_RECORDS = [
  expectedRow(),
  expectedRow({
    id: 22, concept: 'Kore - Fase 3 Inicio',
    period_date: '2026-06-01', pending_amount: '300000.00',
  }),
  expectedRow({
    id: 23, concept: 'Kore - Fase 3 Diseño',
    period_date: '2026-07-01', pending_amount: '200000.00',
  }),
];

function mountModal(props = {}) {
  return mount(IncomeBulkSettleModal, {
    props: {
      open: true,
      records: THREE_RECORDS,
      excludedCount: 0,
      saving: false,
      ...props,
    },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size'],
          emits: ['update:modelValue', 'close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseFormField: {
          props: ['label', 'hint', 'error', 'required', 'for', 'size'],
          template: '<div><label v-if="label">{{ label }}</label><slot /></div>',
        },
        BaseInput: {
          props: ['modelValue', 'type', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<input :type="type || \'text\'" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseCurrencyInput: {
          props: ['modelValue', 'decimals', 'size', 'error', 'placeholder', 'disabled', 'suggestion'],
          emits: ['update:modelValue'],
          // The real component emits a NUMBER (or null when empty), not the
          // typed string — the payload assertions depend on that contract.
          template:
            '<input type="text" inputmode="numeric" :value="modelValue" :data-error="error ? \'true\' : undefined" @input="$emit(\'update:modelValue\', $event.target.value === \'\' ? null : Number($event.target.value))" />',
        },
        BaseTextarea: {
          props: ['modelValue', 'rows', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseButton: {
          props: ['variant', 'size', 'type', 'loading', 'disabled'],
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        BaseToggle: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
        },
        BaseBadge: {
          props: ['variant', 'size'],
          template: '<span :data-variant="variant"><slot /></span>',
        },
      },
    },
  });
}

function amountInput(wrapper, id) {
  return wrapper.find(`[data-testid="income-bulk-settle-amount-${id}"]`);
}

async function setTotal(wrapper, value) {
  await wrapper.find('[data-testid="income-bulk-settle-total"]').setValue(value);
}

describe('IncomeBulkSettleModal', () => {
  it('lists the incomes oldest first with the proposed reparto and totals', () => {
    const wrapper = mountModal();

    const concepts = wrapper.findAll('tbody tr td:first-child')
      .map((cell) => cell.text());
    expect(concepts).toEqual([
      'Kore - Fase 2 Entrega', 'Kore - Fase 3 Inicio', 'Kore - Fase 3 Diseño',
    ]);
    expect(amountInput(wrapper, 21).element.value).toBe('500000');
    expect(wrapper.find('[data-testid="income-bulk-settle-pending-sum"]').text())
      .toContain('1.000.000');
  });

  it('prefills the valor with the pending sum and opens fully covered', () => {
    const wrapper = mountModal();

    expect(wrapper.find('[data-testid="income-bulk-settle-total"]').element.value)
      .toBe('1000000');
    expect(wrapper.find('[data-testid="income-bulk-settle-summary"]').text())
      .toContain('Cobro cubierto por completo');
  });

  it('redistributes oldest first while the valor changes', async () => {
    const wrapper = mountModal();

    await setTotal(wrapper, '600000');

    expect(amountInput(wrapper, 21).element.value).toBe('500000');
    expect(amountInput(wrapper, 22).element.value).toBe('100000');
    expect(amountInput(wrapper, 23).element.value).toBe('0');
    expect(wrapper.find('[data-testid="income-bulk-settle-coverage"]').text())
      .toBe('Quedan pagados: 1 · parciales: 1 · sin abono: 1');
  });

  it('turns an excess valor into saldo a favor without blocking', async () => {
    const wrapper = mountModal();

    await setTotal(wrapper, '1200000');

    const summary = wrapper.find('[data-testid="income-bulk-settle-summary"]');
    expect(summary.text()).toContain('Excedente: $200.000');
    expect(summary.text()).toContain('quedará como saldo a favor de Kore SAS.');
    expect(
      wrapper.find('[data-testid="income-bulk-settle-submit"]').element.disabled,
    ).toBe(false);
  });

  it('blocks an excess when the selection mixes clients', async () => {
    const mixed = [
      THREE_RECORDS[0],
      expectedRow({
        id: 22, concept: 'Globex - Fase 1', period_date: '2026-06-01',
        pending_amount: '300000.00', client: 9, client_name: 'Globex',
      }),
    ];
    const wrapper = mountModal({ records: mixed });

    await setTotal(wrapper, '900000');

    expect(wrapper.find('[data-testid="income-bulk-settle-mixed-clients"]').text())
      .toContain('La selección mezcla ingresos de Kore SAS y Globex.');
    expect(wrapper.find('[data-testid="income-bulk-settle-submit-reason"]').text())
      .toContain('Con clientes mezclados el excedente no se puede asignar');
    expect(
      wrapper.find('[data-testid="income-bulk-settle-submit"]').element.disabled,
    ).toBe(true);
  });

  it('freezes the reparto on a manual edit until Recalcular restores it', async () => {
    const wrapper = mountModal();

    await amountInput(wrapper, 22).setValue('50000');
    await setTotal(wrapper, '600000');
    expect(amountInput(wrapper, 21).element.value).toBe('500000');
    expect(amountInput(wrapper, 22).element.value).toBe('50000');
    expect(wrapper.find('[data-testid="income-bulk-settle-manual-hint"]').exists())
      .toBe(true);

    await wrapper.find('[data-testid="income-bulk-settle-recalculate"]')
      .trigger('click');
    expect(amountInput(wrapper, 22).element.value).toBe('100000');
    expect(wrapper.find('[data-testid="income-bulk-settle-manual-hint"]').exists())
      .toBe(false);
  });

  it('blocks a reparto that sums above the valor', async () => {
    const wrapper = mountModal();

    await amountInput(wrapper, 21).setValue('500000');
    await setTotal(wrapper, '400000');
    await amountInput(wrapper, 22).setValue('0');
    await amountInput(wrapper, 23).setValue('0');

    expect(wrapper.find('[data-testid="income-bulk-settle-submit-reason"]').text())
      .toContain('Ajusta las filas o usa Recalcular reparto.');
    expect(
      wrapper.find('[data-testid="income-bulk-settle-submit"]').element.disabled,
    ).toBe(true);
  });

  it('flags the exact row that goes above its own pending', async () => {
    const wrapper = mountModal();

    await amountInput(wrapper, 23).setValue('999999');

    expect(
      wrapper.find('[data-testid="income-bulk-settle-row-error-23"]').text(),
    ).toContain('Supera el pendiente de esta fila');
    expect(wrapper.find('[data-testid="income-bulk-settle-row-error-21"]').exists())
      .toBe(false);
    expect(wrapper.find('[data-testid="income-bulk-settle-submit-reason"]').text())
      .toContain('Hay filas que superan su pendiente');
  });

  it('drops zero rows from the payload', async () => {
    const wrapper = mountModal();

    await setTotal(wrapper, '600000');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.allocations).toEqual([
      { income_id: 21, amount: 500000 },
      { income_id: 22, amount: 100000 },
    ]);
  });

  it('submits the total, the exact date and the notes', async () => {
    const wrapper = mountModal();

    await wrapper.find('[data-testid="income-bulk-settle-period"]')
      .setValue('2026-08-15');
    await wrapper.find('[data-testid="income-bulk-settle-notes"]')
      .setValue('Transferencia Bancolombia');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.total_amount).toBe(1000000);
    expect(payload.period_date).toBe('2026-08-15');
    expect(payload.notes).toBe('Transferencia Bancolombia');
    expect(payload.allocations).toHaveLength(3);
  });

  it('downgrades the date to month granularity when the toggle drops', async () => {
    const wrapper = mountModal();

    await wrapper.find('[data-testid="income-bulk-settle-period"]')
      .setValue('2026-08-15');
    await wrapper.find('[data-testid="income-bulk-settle-exact-date"]')
      .setValue(false);
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0].period_date).toBe('2026-08');
  });

  it('announces how many selected rows were excluded', () => {
    const wrapper = mountModal({ excludedCount: 2 });

    expect(wrapper.find('[data-testid="income-bulk-settle-excluded"]').text())
      .toContain('Se excluyeron 2 seleccionados que no aplican');
  });
});
