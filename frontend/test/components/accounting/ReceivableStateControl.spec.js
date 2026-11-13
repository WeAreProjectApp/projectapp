import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import ReceivableStateControl from '~/components/accounting/ReceivableStateControl.vue';

const ChoiceSelectStub = defineComponent({
  name: 'BaseChoiceSelect',
  props: ['modelValue', 'options', 'disabled'],
  emits: ['update:modelValue'],
  template: `<div role="combobox" :aria-disabled="disabled"><button v-for="option in options" :key="option.value" type="button" role="option" @click="$emit('update:modelValue', option.value)">{{ option.label }}</button></div>`,
});

const expectedRow = (overrides = {}) => ({
  id: 7,
  concept: 'Kore - Entrega',
  kind: 'expected',
  ledger: 'company',
  payment_status: 'pending',
  is_receivable_candidate: false,
  collection_confidence: '',
  ...overrides,
});

function renderControl(props = {}) {
  return mount(ReceivableStateControl, {
    props: { row: expectedRow(), ...props },
    global: { stubs: { BaseChoiceSelect: ChoiceSelectStub } },
  });
}

describe('ReceivableStateControl', () => {
  // Falla si marcar una previsión deja de comunicar al padre que entra a pendientes por cobrar.
  it('emits candidate selection from the switch', async () => {
    const wrapper = renderControl();

    await wrapper.get('[role="switch"]').trigger('click');

    expect(wrapper.emitted('change')).toEqual([[{ is_receivable_candidate: true }]]);
  });

  // Falla si el semáforo deja de entregar la probabilidad elegida para persistirla.
  it('emits the confidence selected with the choice control', async () => {
    const wrapper = renderControl();
    const high = wrapper.findAll('[role="option"]').find((option) => option.text() === 'Cobro muy probable');

    await high.trigger('click');

    expect(wrapper.emitted('change')).toEqual([[{ collection_confidence: 'high' }]]);
  });

  // Falla si una previsión sin clasificación deja de pasar el valor vacío al selector compartido.
  it('passes an empty confidence to the shared choice control', () => {
    const wrapper = renderControl();

    expect(wrapper.getComponent(ChoiceSelectStub).props('modelValue')).toBe('');
    expect(wrapper.getComponent(ChoiceSelectStub).props('options').map((option) => option.label))
      .toEqual(['Sin clasificar', 'Cobro muy probable', 'Cobro incierto (50/50)', 'Alto riesgo de pérdida']);
  });

  // Falla si el estado medio deja de mostrar su etiqueta completa como opción seleccionable.
  it('passes the medium confidence value and label to the choice control', () => {
    const wrapper = renderControl({ row: expectedRow({ collection_confidence: 'medium' }) });

    expect(wrapper.getComponent(ChoiceSelectStub).props('modelValue')).toBe('medium');
    expect(wrapper.findAll('[role="option"]').find((option) => option.text() === 'Cobro incierto (50/50)').text())
      .toBe('Cobro incierto (50/50)');
  });

  // Falla si una persistencia en curso permite cambiar la probabilidad de cobro.
  it('disables both controls during persistence', () => {
    const wrapper = renderControl({ busy: true });

    expect(wrapper.get('[role="switch"]').attributes('disabled')).toBe('');
    expect(wrapper.get('[role="combobox"]').attributes('aria-disabled')).toBe('true');
  });

  // Falla si un ingreso liquidado vuelve a exponer controles de cuentas por cobrar.
  it('shows the unavailable marker for liquid income', () => {
    const wrapper = renderControl({ row: expectedRow({ kind: 'liquid' }) });

    expect(wrapper.find('[role="switch"]').exists()).toBe(false);
    expect(wrapper.text()).toBe('—');
  });
});
