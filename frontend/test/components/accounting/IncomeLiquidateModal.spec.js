import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import BaseCollapse from '../../../components/base/BaseCollapse.vue';
import IncomeLiquidateModal from '../../../components/accounting/IncomeLiquidateModal.vue';
import { useAccountingStore } from '../../../stores/accounting';

const income = (id, overrides = {}) => ({
  id,
  concept: `Ingreso ${id}`,
  kind: 'expected',
  ledger: 'company',
  client: 8,
  period_date: `2026-0${id}-01`,
  period_label: `Mes ${id}`,
  total_amount: '100.00',
  pending_amount: '100.00',
  ...overrides,
});

const preview = (rows, previewHash = 'preview-verified') => ({
  success: true,
  data: {
    preview_hash: previewHash,
    total_amount: 150,
    pending_after: 50,
    rows,
  },
});

const stubs = {
  Teleport: { template: '<div><slot /></div>' },
  Transition: { template: '<div><slot /></div>' },
  BaseModal: {
    props: ['modelValue'],
    template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
  },
  BaseFormField: { template: '<div><slot /></div>' },
  BaseButton: {
    props: ['type', 'disabled'],
    emits: ['click'],
    template: '<button v-bind="$attrs" :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
  },
  BaseCurrencyInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value === \'\' ? null : Number($event.target.value))" />',
  },
  BaseInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  BaseSelect: {
    props: ['modelValue', 'options', 'placeholder'],
    emits: ['update:modelValue'],
    template: '<select v-bind="$attrs" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option value=""></option><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
  },
  BaseTextarea: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<textarea v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  BaseSegmented: {
    props: ['modelValue', 'options'],
    emits: ['update:modelValue'],
    template: '<div v-bind="$attrs"><button v-for="option in options" :key="option.value" type="button" @click="$emit(\'update:modelValue\', option.value)">{{ option.label }}</button></div>',
  },
  BaseToggle: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<button v-bind="$attrs" type="button" @click="$emit(\'update:modelValue\', !modelValue)">{{ modelValue ? \'on\' : \'off\' }}</button>',
  },
  BaseCheckbox: {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template: '<label><input v-bind="$attrs" type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.checked)" /><slot /></label>',
  },
  BaseCollapse,
  PeriodDateField: {
    props: ['modelValue', 'exact'],
    emits: ['update:modelValue', 'update:exact'],
    template: '<input v-bind="$attrs" type="date" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  SettlementHostingPeriod: { template: '<div />' },
  VatBreakdown: {
    props: ['total', 'rate'],
    template: '<p data-testid="vat-breakdown-stub">{{ rate === null ? \'sin tasa\' : `tasa ${rate}` }} · {{ total }}</p>',
  },
};

function mountModal(props = {}, componentStubs = {}) {
  return mount(IncomeLiquidateModal, {
    props: { open: true, record: income(1), records: [], saving: false, ...props },
    global: { stubs: { ...stubs, ...componentStubs } },
  });
}

function mockPreview(result) {
  const store = useAccountingStore();
  jest.spyOn(store, 'previewIncomeSettlement').mockResolvedValue(result);
  return store;
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => {
  setActivePinia(createPinia());
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe('IncomeLiquidateModal', () => {
  // Falla si el período se completa visualmente pero el abono no identifica
  // a qué ingreso debe aplicarse su ventana de hosting.
  it('includes the completed hosting window under its source income', async () => {
    mockPreview(preview([{ income_id: 1, confirmation: { can_send: false } }]));
    const wrapper = mountModal({
      record: income(1, { origin: 'hosting', period_start: null }),
    }, { SettlementHostingPeriod: false });
    await flushPromises();

    await wrapper.get('[data-testid="income-liquidate-cycle-3"]').trigger('click');
    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await flushPromises();

    expect(wrapper.emitted('submit')[0][0].periods).toEqual([{
      income_id: 1, period_start: '2026-01-01', period_end: '2026-03-31', period_cadence: 'quarterly',
    }]);
  });

  // Falla si varias filas vuelven a ir a un segundo modal, si el faltante no
  // descubre sus ajustes o si esos ajustes se pierden al construir el abono.
  it('keeps multi-income adjustments in the form and emits their exact payload', async () => {
    const records = [income(1), income(2)];
    const rows = records.map((record) => ({
      income_id: record.id,
      concept: record.concept,
      amount: 75,
      deducted: 0,
      reexpected: 0,
      pending_after: 25,
      confirmation: { can_send: false, blocked_reason: 'Sin cuenta' },
    }));
    mockPreview(preview(rows));
    const wrapper = mountModal({ record: null, records });
    await flushPromises();

    await wrapper.get('[data-testid="income-liquidate-paid"]').setValue('150');
    expect(wrapper.get('[data-testid="income-liquidate-difference-toggle"]').attributes('aria-expanded')).toBe('true');

    await wrapper.get('[data-testid="income-liquidate-add-deduction"]').trigger('click');
    await wrapper.get('[data-testid="deduction-type-0"]').setValue('bank_fee');
    await wrapper.get('[data-testid="deduction-amount-0"]').setValue('20');
    await wrapper.get('[data-testid="income-liquidate-add-followup"]').trigger('click');
    await wrapper.get('[data-testid="followup-concept-0"]').setValue('Saldo fase 2');
    await wrapper.get('[data-testid="followup-period-0"]').setValue('2026-10');
    await wrapper.get('[data-testid="followup-amount-0"]').setValue('30');
    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await flushPromises();

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      income_ids: [1, 2],
      total_amount: 150,
      deductions: [{ type: 'bank_fee', amount: 20, detail: '' }],
      expected_incomes: [{ income_id: 2, concept: 'Saldo fase 2', period_date: '2026-10', amount: 30 }],
      gustavo_amount: 75,
      carlos_amount: 75,
      preview_hash: 'preview-verified',
    });
  });

  // Falla si el reparto automático vuelve a ocultar o dejar vacíos los
  // importes de Carlos y Gustavo cuando el modal se abre sobre un pendiente.
  it('shows the automatic partner split before its section is expanded', async () => {
    const record = income(1, { pending_amount: '151.00' });
    mockPreview(preview([{ income_id: 1, confirmation: { can_send: false } }]));
    const wrapper = mountModal({ record });
    await flushPromises();

    expect(wrapper.get('[data-testid="income-liquidate-participations-toggle"]').text()).toContain('Carlos $75');
    expect(wrapper.get('[data-testid="income-liquidate-participations-toggle"]').text()).toContain('Gustavo $75');
  });

  // Falla si cada cambio corto vuelve a abrir Diferencia después de que el
  // usuario la cerró para seguir diligenciando las demás secciones.
  it('automatically opens the difference section only on the first shortfall', async () => {
    mockPreview(preview([{ income_id: 1, confirmation: { can_send: false } }]));
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="income-liquidate-paid"]').setValue('80');
    expect(wrapper.get('[data-testid="income-liquidate-difference-toggle"]').attributes('aria-expanded')).toBe('true');
    await wrapper.get('[data-testid="income-liquidate-difference-toggle"]').trigger('click');
    await wrapper.get('[data-testid="income-liquidate-paid"]').setValue('70');

    expect(wrapper.get('[data-testid="income-liquidate-difference-toggle"]').attributes('aria-expanded')).toBe('false');
  });

  // Falla si una liquidación personal conserva el destino invisible de
  // bolsillo, que el servidor rechaza para su contabilidad individual.
  it('emits the partners destination for a personal ledger', async () => {
    const record = income(1, { ledger: 'gustavo' });
    mockPreview(preview([{ income_id: 1, confirmation: { can_send: false } }]));
    const wrapper = mountModal({ record });
    await flushPromises();

    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await flushPromises();

    expect(wrapper.emitted('submit')[0][0].destination).toBe('partners');
  });

  // Falla si un pago sin dinero recibido no puede cerrar un saldo cuando una
  // deducción válida explica íntegramente por qué no entró al bolsillo.
  it('submits a deduction-only settlement with a null received amount', async () => {
    mockPreview(preview([{ income_id: 1, confirmation: { can_send: false } }]));
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="income-liquidate-paid"]').setValue('');
    await wrapper.get('[data-testid="income-liquidate-add-deduction"]').trigger('click');
    await wrapper.get('[data-testid="deduction-type-0"]').setValue('withholding');
    await wrapper.get('[data-testid="deduction-amount-0"]').setValue('100');
    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await flushPromises();

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      total_amount: 0,
      deductions: [{ type: 'withholding', amount: 100, detail: '' }],
    });
  });

  // Falla si el IVA se convierte en una modificación fiscal silenciosa al
  // abrir su acordeón: sólo debe mostrar las tasas ya registradas.
  it('shows stored VAT rates without adding a VAT override to the payload', async () => {
    const records = [
      income(1, { vat_rate: null }), income(2, { vat_rate: 0 }), income(3, { vat_rate: 19 }),
    ];
    mockPreview(preview(records.map((record) => ({ income_id: record.id, confirmation: { can_send: false } }))));
    const wrapper = mountModal({ record: null, records });
    await flushPromises();

    await wrapper.get('[data-testid="income-liquidate-vat-toggle"]').trigger('click');
    expect(wrapper.findAll('[data-testid="vat-breakdown-stub"]').map((node) => node.text())).toEqual([
      'sin tasa · 100', 'tasa 0 · 100', 'tasa 19 · 100',
    ]);

    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await flushPromises();
    expect(wrapper.emitted('submit')[0][0].vat_rate).toBeUndefined();
  });

  // Falla si una confirmación vuelve a registrar el pago antes de que el
  // usuario acepte la revisión, o si se pierde la huella anti-stale.
  it('reviews eligible confirmations before emitting the preview hash once', async () => {
    const result = preview([{
      income_id: 1,
      concept: 'Ingreso 1',
      amount: 100,
      deducted: 0,
      reexpected: 0,
      pending_after: 0,
      confirmation: { can_send: true, recipient: 'cliente@example.com', collection_account_number: 'CC-7' },
    }], 'preview-with-email');
    mockPreview(result);
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await flushPromises();
    expect(wrapper.get('[data-testid="income-liquidate-review"]').text()).toContain('cliente@example.com');
    expect(wrapper.emitted('submit')).toBeUndefined();

    await wrapper.get('[data-testid="income-liquidate-confirm"]').trigger('click');
    expect(wrapper.emitted('submit')).toHaveLength(1);
    expect(wrapper.emitted('submit')[0][0].preview_hash).toBe('preview-with-email');
  });

  // Falla si un abono global habilita confirmaciones para un ingreso que no
  // recibió dinero dentro de la imputación automática por antigüedad.
  it('only includes confirmations for rows that received part of a multi-income payment', async () => {
    const records = [income(1), income(2)];
    const result = preview([
      { income_id: 1, concept: 'Ingreso 1', amount: 100, deducted: 0, reexpected: 0, pending_after: 0, confirmation: { can_send: true, recipient: 'ana@example.com' } },
      { income_id: 2, concept: 'Ingreso 2', amount: 0, deducted: 0, reexpected: 0, pending_after: 100, confirmation: { can_send: true, recipient: 'bea@example.com' } },
    ], 'preview-first-row-only');
    mockPreview(result);
    const wrapper = mountModal({ record: null, records });
    await flushPromises();

    await wrapper.get('[data-testid="income-liquidate-paid"]').setValue('100');
    expect(wrapper.get('[data-testid="income-liquidate-confirmation-2"]').find('input').element.disabled).toBe(true);
    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await flushPromises();
    await wrapper.get('[data-testid="income-liquidate-confirm"]').trigger('click');

    expect(wrapper.emitted('submit')[0][0].confirmation_income_ids).toEqual([1]);
  });

  // Falla si dos clics rápidos envían dos previsualizaciones y permiten dos
  // liquidaciones mientras la primera comprobación sigue en curso.
  it('ignores a second submit while the settlement preview is pending', async () => {
    const delayed = deferred();
    const store = mockPreview(preview([{ income_id: 1, confirmation: { can_send: false } }]));
    const wrapper = mountModal();
    await flushPromises();
    store.previewIncomeSettlement.mockImplementationOnce(() => delayed.promise);

    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    delayed.resolve(preview([{ income_id: 1, confirmation: { can_send: false } }], 'single-submit'));
    await flushPromises();

    expect(store.previewIncomeSettlement).toHaveBeenCalledTimes(2);
    expect(wrapper.emitted('submit')[0][0].preview_hash).toBe('single-submit');
  });

  // Falla si una respuesta lenta de una apertura anterior reemplaza el
  // destinatario que se obtuvo al reabrir el mismo formulario.
  it('discards an obsolete context preview after the modal reopens', async () => {
    const older = deferred();
    const store = useAccountingStore();
    jest.spyOn(store, 'previewIncomeSettlement')
      .mockImplementationOnce(() => older.promise)
      .mockResolvedValueOnce(preview([{ income_id: 1, confirmation: { can_send: true, recipient: 'nuevo@example.com' } }]));
    const wrapper = mountModal();

    await wrapper.setProps({ open: false });
    await wrapper.setProps({ open: true });
    await flushPromises();
    older.resolve(preview([{ income_id: 1, confirmation: { can_send: true, recipient: 'viejo@example.com' } }]));
    await flushPromises();

    expect(wrapper.get('[data-testid="income-liquidate-confirmation-1"]').element.parentElement.textContent).toContain('nuevo@example.com');
  });

  // Falla si un error al revisar borra el formulario o permite emitir una
  // liquidación sin la comprobación que protege contra cambios concurrentes.
  it('keeps the entered amount and does not emit when settlement preview fails', async () => {
    const store = mockPreview(preview([{ income_id: 1, confirmation: { can_send: false } }]));
    const wrapper = mountModal();
    await flushPromises();
    store.previewIncomeSettlement.mockResolvedValueOnce({ success: false, message: 'El ingreso cambió mientras revisabas.' });

    await wrapper.get('[data-testid="income-liquidate-paid"]').setValue('80');
    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toBe('El ingreso cambió mientras revisabas.');
    expect(wrapper.get('[data-testid="income-liquidate-paid"]').element.value).toBe('80');
    expect(wrapper.emitted('submit')).toBeUndefined();
  });

  // Falla si una previsualización responde para un monto anterior y registra
  // ese abono aunque el operador ya lo corrigió mientras esperaba.
  it('rejects a late final preview after the received amount changes', async () => {
    const delayed = deferred();
    const store = mockPreview(preview([{ income_id: 1, confirmation: { can_send: false } }]));
    const wrapper = mountModal();
    await flushPromises();
    store.previewIncomeSettlement.mockImplementationOnce(() => delayed.promise);

    await wrapper.get('[data-testid="income-liquidate-paid"]').setValue('80');
    await wrapper.get('[data-testid="income-liquidate-form"]').trigger('submit');
    await wrapper.get('[data-testid="income-liquidate-paid"]').setValue('70');
    delayed.resolve(preview([{ income_id: 1, confirmation: { can_send: false } }]));
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toBe('La liquidación cambió durante la revisión. Vuelve a pulsar Liquidar.');
    expect(wrapper.get('[data-testid="income-liquidate-paid"]').element.value).toBe('70');
    expect(wrapper.emitted('submit')).toBeUndefined();
  });
});
