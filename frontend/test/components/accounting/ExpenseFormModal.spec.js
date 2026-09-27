import { mount } from '@vue/test-utils';
import ExpenseFormModal from '../../../components/accounting/ExpenseFormModal.vue';

const PartnerSplitInputStub = {
  name: 'PartnerSplitInput',
  props: ['total', 'gustavoAmount', 'carlosAmount'],
  emits: ['update:total', 'update:gustavoAmount', 'update:carlosAmount'],
  template: `
    <div data-testid="partner-split-stub">
      <input data-testid="split-total" :value="total" @input="$emit('update:total', $event.target.value)" />
      <input data-testid="split-gustavo" :value="gustavoAmount" @input="$emit('update:gustavoAmount', $event.target.value)" />
      <input data-testid="split-carlos" :value="carlosAmount" @input="$emit('update:carlosAmount', $event.target.value)" />
    </div>
  `,
};

function mountModal(props = {}) {
  return mount(ExpenseFormModal, {
    props: {
      open: true,
      record: null,
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
          props: ['modelValue', 'decimals', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<input type="text" inputmode="numeric" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value === \'\' ? null : Number($event.target.value))" />',
        },
        BaseTextarea: {
          props: ['modelValue', 'rows', 'size', 'error', 'placeholder', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseSelect: {
          props: ['modelValue', 'options', 'size', 'error', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
        },
        BaseSegmented: {
          props: ['modelValue', 'options', 'size', 'fullWidth'],
          emits: ['update:modelValue'],
          template:
            '<div><button v-for="o in options" :key="o.value" type="button" :aria-selected="modelValue === o.value" @click="$emit(\'update:modelValue\', o.value)">{{ o.label }}</button></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'type', 'loading', 'disabled'],
          emits: ['click'],
          template:
            '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        BaseToggle: {
          props: ['modelValue', 'size', 'disabled', 'ariaLabel'],
          emits: ['update:modelValue'],
          // The testid falls through from the caller — the modal now renders
          // two toggles (pocket + exact date), so hardcoding one here would
          // collide.
          template:
            '<button type="button" role="switch" :aria-checked="modelValue" @click="$emit(\'update:modelValue\', !modelValue)" />',
        },
        PartnerSplitInput: PartnerSplitInputStub,
      },
    },
  });
}

function segmentedButton(wrapper, label) {
  return wrapper.findAll('button').find((b) => b.text() === label);
}

describe('ExpenseFormModal', () => {
  it('emits submit with the company ledger and split amounts by default', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="text"]').setValue('Windsurf, Marzo');
    // Month-only entry is still possible through the toggle.
    await wrapper.find('[data-testid="expense-form-exact-date"]').trigger('click');
    await wrapper.find('[data-testid="expense-form-period"]').setValue('2026-03');
    await wrapper.find('[data-testid="split-total"]').setValue('3000000');
    await wrapper.find('[data-testid="split-gustavo"]').setValue('1500000');
    await wrapper.find('[data-testid="split-carlos"]').setValue('1500000');

    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')).toHaveLength(1);
    expect(wrapper.emitted('submit')[0][0]).toEqual({
      concept: 'Windsurf, Marzo',
      period_date: '2026-03',
      category: 'business',
      ledger: 'company',
      total_amount: '3000000',
      gustavo_amount: '1500000',
      carlos_amount: '1500000',
      register_in_pocket: true,
      notes: '',
    });
  });

  it('submits register_in_pocket false when the toggle is turned off', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="text"]').setValue('Ajuste contable');
    await wrapper.find('[data-testid="expense-form-period"]').setValue('2026-07-10');
    await wrapper.find('[data-testid="split-total"]').setValue('100000');
    await wrapper.find('[data-testid="expense-register-in-pocket"]').trigger('click');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0].register_in_pocket).toBe(false);
  });

  it('personal ledger hides split and omits split amounts', async () => {
    const wrapper = mountModal();

    expect(wrapper.find('[data-testid="partner-split-stub"]').exists()).toBe(true);

    await segmentedButton(wrapper, 'Personal Gustavo').trigger('click');

    expect(wrapper.find('[data-testid="partner-split-stub"]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Valor');

    await wrapper.find('input[type="text"]').setValue('Aporte Carro Onix');
    await wrapper.find('[data-testid="expense-form-period"]').setValue('2026-06-15');
    await wrapper.find('input[inputmode="numeric"]').setValue('3000000');
    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.ledger).toBe('gustavo');
    expect(payload.total_amount).toBe(3000000);
    expect(payload).not.toHaveProperty('gustavo_amount');
    expect(payload).not.toHaveProperty('carlos_amount');
  });

  it('warns that a personal expense from the pocket becomes a company draw', async () => {
    const wrapper = mountModal();

    expect(
      wrapper.find('[data-testid="expense-pocket-draw-hint"]').exists(),
    ).toBe(false);

    await segmentedButton(wrapper, 'Personal Gustavo').trigger('click');

    // Pocket toggle is on by default: the server will store this as a
    // company expense fully assigned to the partner.
    expect(
      wrapper.find('[data-testid="expense-pocket-draw-hint"]').exists(),
    ).toBe(true);

    await wrapper.find('[data-testid="expense-register-in-pocket"]').trigger('click');

    expect(
      wrapper.find('[data-testid="expense-pocket-draw-hint"]').exists(),
    ).toBe(false);
  });

  it('defaults to the exact date prefilled with today', () => {
    // 20:00 local: toISOString() would already be tomorrow in Bogotá
    // (UTC-5) — this pins the local-date formatting.
    jest.useFakeTimers().setSystemTime(new Date('2026-07-27T20:00:00'));
    try {
      const wrapper = mountModal();

      const input = wrapper.find('[data-testid="expense-form-period"]');
      expect(input.attributes('type')).toBe('date');
      expect(input.element.value).toBe('2026-07-27');
    } finally {
      jest.useRealTimers();
    }
  });

  it('downgrades to month-only via the toggle keeping the typed value', async () => {
    const wrapper = mountModal();

    await wrapper.find('[data-testid="expense-form-period"]').setValue('2026-11-17');
    await wrapper.find('[data-testid="expense-form-exact-date"]').trigger('click');

    const input = wrapper.find('[data-testid="expense-form-period"]');
    expect(input.attributes('type')).toBe('month');
    expect(input.element.value).toBe('2026-11');
  });

  it('opens a day-1 period in full-date mode showing the stored day', () => {
    // Day 1 stays the storage sentinel for month-only records, but the
    // edit always opens as a date so the day is visible and correctable.
    const wrapper = mountModal({
      record: {
        concept: 'Dominio',
        period: '2026-07',
        period_date: '2026-07-01',
        ledger: 'company',
        total_amount: '150000',
      },
    });

    const input = wrapper.find('[data-testid="expense-form-period"]');
    expect(input.attributes('type')).toBe('date');
    expect(input.element.value).toBe('2026-07-01');
  });

  it('prefills the exact day from period_date in edit mode', () => {
    // `period` would truncate to the month and silently reset the day.
    const wrapper = mountModal({
      record: {
        concept: 'Dominio',
        period: '2026-07',
        period_date: '2026-07-17',
        ledger: 'company',
        total_amount: '150000',
      },
    });

    const input = wrapper.find('[data-testid="expense-form-period"]');
    expect(input.attributes('type')).toBe('date');
    expect(input.element.value).toBe('2026-07-17');
  });

  it('prefills the ledger from the record in edit mode', () => {
    const wrapper = mountModal({
      record: {
        concept: 'Aporte Interes Credito',
        period: '2026-06',
        period_date: '2026-06-01',
        category: 'personal',
        ledger: 'gustavo',
        total_amount: '2616581',
        gustavo_amount: '2616581',
        carlos_amount: '0',
        notes: '',
      },
    });

    expect(wrapper.text()).toContain('Editar Gasto');
    expect(segmentedButton(wrapper, 'Personal Gustavo').attributes('aria-selected')).toBe('true');
    expect(wrapper.find('[data-testid="partner-split-stub"]').exists()).toBe(false);
  });

  it('prefills the pocket toggle from the linked movement in edit mode', () => {
    const linked = mountModal({
      record: {
        concept: 'Dominio',
        period: '2026-07',
        period_date: '2026-07-01',
        ledger: 'company',
        total_amount: '150000',
        pocket_movement: 42,
      },
    });
    const historical = mountModal({
      record: {
        concept: 'Gasto histórico',
        period: '2026-02',
        period_date: '2026-02-01',
        ledger: 'company',
        total_amount: '80000',
        pocket_movement: null,
      },
    });

    expect(
      linked.find('[data-testid="expense-register-in-pocket"]')
        .attributes('aria-checked'),
    ).toBe('true');
    expect(
      historical.find('[data-testid="expense-register-in-pocket"]')
        .attributes('aria-checked'),
    ).toBe('false');
  });
});

describe('ExpenseFormModal deduction edit mode', () => {
  const deductionRecord = {
    id: 193,
    concept: 'Comisión plataforma de pago — Hosting Jimmy Junio',
    period_date: '2026-06-01',
    category: 'business',
    ledger: 'company',
    total_amount: '4854.00',
    gustavo_amount: '2427.00',
    carlos_amount: '2427.00',
    deduction_type: 'gateway_fee',
    deduction_type_label: 'Comisión plataforma de pago',
    pocket_movement: null,
    notes: '',
  };

  it('shows the deduction hint and hides the pocket toggle', () => {
    const wrapper = mountModal({ record: deductionRecord });

    const hint = wrapper.get('[data-testid="expense-deduction-edit-hint"]');
    expect(hint.text()).toContain('Comisión plataforma de pago');
    expect(hint.text()).toContain('nunca registra egreso en bolsillo');
    expect(
      wrapper.find('[data-testid="expense-register-in-pocket"]').exists(),
    ).toBe(false);
  });

  it('omits register_in_pocket from the payload when editing a deduction', async () => {
    const wrapper = mountModal({ record: deductionRecord });

    await wrapper.get('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload).not.toHaveProperty('register_in_pocket');
    expect(payload.concept).toBe(deductionRecord.concept);
  });

  it('keeps the pocket toggle for an ordinary expense', () => {
    const wrapper = mountModal({
      record: { ...deductionRecord, deduction_type: '', deduction_type_label: '' },
    });

    expect(
      wrapper.find('[data-testid="expense-register-in-pocket"]').exists(),
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="expense-deduction-edit-hint"]').exists(),
    ).toBe(false);
  });
});
