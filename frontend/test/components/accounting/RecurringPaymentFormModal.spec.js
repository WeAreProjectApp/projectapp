/**
 * Tests for RecurringPaymentFormModal.
 *
 * Covers: the frequency catalog offered by the select, the month-count field
 * that only a custom cycle brings along, and what each variant submits.
 */
import { mount } from '@vue/test-utils';
import RecurringPaymentFormModal from '../../../components/accounting/RecurringPaymentFormModal.vue';

function mountModal(props = {}) {
  return mount(RecurringPaymentFormModal, {
    props: {
      open: true,
      record: null,
      saving: false,
      categories: [],
      ...props,
    },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size', 'titleId'],
          emits: ['update:modelValue', 'close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseFormField: {
          props: ['label', 'hint', 'error', 'required', 'for', 'size'],
          template:
            '<div><label v-if="label">{{ label }}</label><slot /><p v-if="hint">{{ hint }}</p></div>',
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
        BaseSelect: {
          props: ['modelValue', 'options', 'size', 'error', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
        },
        BaseSegmented: {
          props: ['modelValue', 'options', 'size', 'fullWidth', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<div><button v-for="o in options" :key="o.value" type="button" :aria-selected="modelValue === o.value" @click="$emit(\'update:modelValue\', o.value)">{{ o.label }}</button></div>',
        },
        BaseToggle: {
          props: ['modelValue', 'disabled'],
          emits: ['update:modelValue'],
          template:
            '<button type="button" @click="$emit(\'update:modelValue\', !modelValue)" />',
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
      },
    },
  });
}

function frequencySelect(wrapper) {
  // Second select in the form: payment method comes first, frequency after it.
  return wrapper.findAll('select')[1];
}

const CUSTOM_MONTHS = '[data-testid="recurring-payment-form-custom-months"]';
const CUSTOM_MONTHS_HELP = '[data-testid="recurring-payment-form-custom-months-help"]';
const CYCLE_ANCHOR = '[data-testid="recurring-payment-form-cycle-anchor-date"]';
const ANCHOR_HELP = '[data-testid="recurring-payment-form-anchor-help"]';

describe('RecurringPaymentFormModal', () => {
  it('offers every frequency from the shortest cycle to the longest', () => {
    const wrapper = mountModal();

    // The order is what makes picking the right one immediate; the intermediate
    // cycles exist so a quarterly charge never has to be approximated.
    expect(frequencySelect(wrapper).findAll('option').map((o) => o.text()))
      .toEqual([
        'Mensual',
        'Bimestral',
        'Trimestral',
        'Cuatrimestral',
        'Semestral',
        'Anual',
        'Cada 2 años',
        'Cada 3 años',
        'Personalizada',
      ]);
  });

  it('asks for the month count only once the frequency is custom', async () => {
    const wrapper = mountModal();

    expect(wrapper.find(CUSTOM_MONTHS).exists()).toBe(false);
    expect(wrapper.find(CUSTOM_MONTHS_HELP).exists()).toBe(false);

    await frequencySelect(wrapper).setValue('custom');

    expect(wrapper.find(CUSTOM_MONTHS).exists()).toBe(true);
    expect(wrapper.get(CUSTOM_MONTHS_HELP).text()).toBe(
      'El equivalente mensual es el precio dividido entre este número',
    );
  });

  it('submits the month count with a custom cycle', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="text"]').setValue('Mantenimiento servidor');
    await wrapper.find('input[inputmode="numeric"]').setValue('500000');
    await frequencySelect(wrapper).setValue('custom');
    await wrapper.find(CUSTOM_MONTHS).setValue('5');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      name: 'Mantenimiento servidor',
      frequency: 'custom',
      custom_months: '5',
    });
  });

  it('submits the reference date that anchors the charge cycle', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="text"]').setValue('Dominio anual');
    await wrapper.find('input[inputmode="numeric"]').setValue('80000');
    await frequencySelect(wrapper).setValue('annual');
    await wrapper.find(CYCLE_ANCHOR).setValue('2026-03-15');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      frequency: 'annual',
      cycle_anchor_date: '2026-03-15',
    });
  });

  it('sends a null reference date when it is left empty', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="text"]').setValue('Figma');
    await wrapper.find('input[inputmode="numeric"]').setValue('60000');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      cycle_anchor_date: null,
    });
  });

  it('warns that a non-monthly cycle needs the reference date to notify', async () => {
    const wrapper = mountModal();

    expect(wrapper.get(ANCHOR_HELP).text()).toBe(
      'Con periodicidad mensual basta el día de cobro.',
    );

    await frequencySelect(wrapper).setValue('annual');

    const help = wrapper.get(ANCHOR_HELP).text();
    expect(help).toContain('Sin ella este pago no genera avisos.');
    expect(help).toContain('El próximo cobro se calcula desde la fecha de referencia.');
  });

  it('clears the month count when a catalog frequency is picked back', async () => {
    const wrapper = mountModal({
      record: {
        name: 'Servidor',
        price: '700000.00',
        currency: 'COP',
        frequency: 'custom',
        custom_months: 7,
        payment_method: 'cash',
        cost_type: 'fixed',
        is_active: true,
        notes: '',
      },
    });

    expect(wrapper.find(CUSTOM_MONTHS).element.value).toBe('7');

    await frequencySelect(wrapper).setValue('quarterly');
    await wrapper.find('form').trigger('submit');

    // Leaving the stale 7 in the payload would let the API prorate by the wrong
    // divisor if the field ever stopped being cleared server-side.
    expect(wrapper.find(CUSTOM_MONTHS).exists()).toBe(false);
    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      frequency: 'quarterly',
      custom_months: null,
    });
  });

  it('sends no month count for an ordinary frequency', async () => {
    const wrapper = mountModal();

    await wrapper.find('input[type="text"]').setValue('Figma equipo');
    await wrapper.find('input[inputmode="numeric"]').setValue('300000');
    await frequencySelect(wrapper).setValue('quarterly');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      frequency: 'quarterly',
      custom_months: null,
    });
  });

  it('updates the COP preview when only the USD price changes', async () => {
    const wrapper = mountModal({
      usdExchangeRate: '4000.00',
      record: {
        name: 'Chat-GPT', price: '20.00', currency: 'USD',
        frequency: 'monthly', payment_method: 'credit_card',
        cost_type: 'fixed', is_active: true, notes: '',
      },
    });

    await wrapper.get('[data-testid="recurring-payment-form-price"]')
      .setValue('200');

    expect(wrapper.get('[data-testid="recurring-payment-cop-preview"]').text())
      .toContain('$800.000 COP');
  });

  it('updates the COP preview when only the currency changes', async () => {
    const wrapper = mountModal({
      usdExchangeRate: '4000.00',
      record: {
        name: 'Chat-GPT', price: '200.00', currency: 'COP',
        frequency: 'monthly', payment_method: 'credit_card',
        cost_type: 'fixed', is_active: true, notes: '',
      },
    });

    await wrapper.findAll('button').find((button) => button.text() === 'USD').trigger('click');

    expect(wrapper.get('[data-testid="recurring-payment-cop-preview"]').text())
      .toContain('$800.000 COP');
  });

  it('updates the monthly COP preview when only the frequency changes', async () => {
    const wrapper = mountModal({
      usdExchangeRate: '4000.00',
      record: {
        name: 'Chat-GPT', price: '200.00', currency: 'USD',
        frequency: 'monthly', payment_method: 'credit_card',
        cost_type: 'fixed', is_active: true, notes: '',
      },
    });

    await frequencySelect(wrapper).setValue('annual');

    const preview = wrapper.get('[data-testid="recurring-payment-cop-preview"]').text();
    expect(preview).toContain('$66.667 COP');
  });

  it('never submits the stale COP equivalent received on an edit', async () => {
    const wrapper = mountModal({
      usdExchangeRate: '4000.00',
      record: {
        name: 'Chat-GPT', price: '200.00', currency: 'USD',
        cop_equivalent: '80000.00', frequency: 'monthly',
        payment_method: 'credit_card', cost_type: 'fixed',
        is_active: true, notes: '',
      },
    });

    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')).toHaveLength(1);
    expect(wrapper.emitted('submit')[0][0]).not.toHaveProperty('cop_equivalent');
  });

  it('opens a duplicate seed as an unsaved create form', () => {
    const wrapper = mountModal({
      seed: {
        name: 'Figma equipo',
        price: '270000.00',
        currency: 'COP',
        payment_method: 'credit_card',
        frequency: 'quarterly',
        billing_day: 17,
        cycle_anchor_date: '2026-10-17',
        cost_type: 'variable',
        category: 8,
        is_active: true,
        notes: '',
        schedule_notice: 'La fecha se recalculó.',
      },
      categories: [{ id: 8, name: 'Diseño' }],
    });

    expect(wrapper.text()).toContain('Duplicar pago recurrente');
    expect(wrapper.find('input[type="text"]').element.value).toBe('Figma equipo');
    expect(wrapper.get(CYCLE_ANCHOR).element.value).toBe('2026-10-17');
    expect(wrapper.text()).toContain('La fecha se recalculó.');
    expect(wrapper.emitted('submit')).toBeUndefined();
  });

  it('requires a missing duplicate schedule before save', () => {
    const wrapper = mountModal({
      seed: {
        name: 'Dominio',
        price: '180000.00',
        currency: 'COP',
        payment_method: 'credit_card',
        frequency: 'annual',
        cycle_anchor_date: null,
        cost_type: 'fixed',
        is_active: true,
        schedule_requires_anchor: true,
        schedule_notice: 'Define una fecha de referencia antes de guardar.',
      },
    });

    expect(wrapper.get(CYCLE_ANCHOR).attributes('required')).toBeDefined();
    expect(wrapper.get('[data-testid="recurring-duplicate-schedule-notice"]').text())
      .toContain('Define una fecha de referencia');
  });
});
