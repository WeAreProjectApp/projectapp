import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import SettlementHostingPeriod from '../../../components/accounting/SettlementHostingPeriod.vue';

const record = {
  id: 71,
  concept: 'Hosting Acme',
  period_date: '2026-05-01',
};

const stubs = {
  BaseFormField: { template: '<div><slot /></div>' },
  BaseInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  BaseSelect: {
    props: ['modelValue', 'options'],
    emits: ['update:modelValue'],
    template: '<select v-bind="$attrs" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option value=""></option><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
  },
  BaseButton: {
    emits: ['click'],
    template: '<button v-bind="$attrs" type="button" @click="$emit(\'click\', $event)"><slot /></button>',
  },
};

function mountPeriod(overrides = {}) {
  setActivePinia(createPinia());
  return mount(SettlementHostingPeriod, {
    props: { record: { ...record, ...overrides } },
    global: { stubs },
  });
}

function lastChange(wrapper) {
  const changes = wrapper.emitted('change');
  return changes[changes.length - 1][0];
}

describe('SettlementHostingPeriod', () => {
  // Falla si sólo mostrar el bloque de hosting convierte una liquidación
  // ordinaria en inválida antes de que el operador toque el período opcional.
  it('keeps an untouched hosting period optional', () => {
    const wrapper = mountPeriod();

    expect(lastChange(wrapper)).toEqual({ period: null, invalid: false });
  });

  // Falla si el atajo deja fechas parciales o calcula un fin no inclusivo,
  // dejando al formulario padre sin un período listo para enviar.
  it('emits a complete inclusive period after choosing the quarterly shortcut', async () => {
    const wrapper = mountPeriod();

    await wrapper.get('[data-testid="income-liquidate-cycle-3"]').trigger('click');

    expect(lastChange(wrapper)).toEqual({
      period: {
        period_start: '2026-05-01',
        period_end: '2026-07-31',
        period_cadence: 'quarterly',
      },
      invalid: false,
    });
  });

  // Falla si una edición parcial parece opcional y permite una liquidación
  // con una ventana de hosting incoherente.
  it('marks a partially edited period invalid and clears the block when it is emptied', async () => {
    const wrapper = mountPeriod();
    const start = wrapper.get('[data-testid="income-liquidate-period-start"]');

    await start.setValue('2026-05-02');
    expect(lastChange(wrapper)).toEqual({ period: null, invalid: true });

    await start.setValue('');
    expect(lastChange(wrapper)).toEqual({ period: null, invalid: false });
  });
});
