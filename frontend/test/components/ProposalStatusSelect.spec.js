import { computed, defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import ProposalStatusSelect from '../../components/panel/proposal/ProposalStatusSelect.vue';

const ChoiceSelectStub = defineComponent({
  name: 'BaseChoiceSelect',
  props: ['modelValue', 'options', 'disabled'],
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const selectedLabel = computed(() => props.options.find((option) => option.value === props.modelValue)?.label);
    return { emit, selectedLabel };
  },
  template: `
    <div data-testid="proposal-status-choice">
      <button type="button" role="combobox" :disabled="disabled">{{ selectedLabel }}</button>
      <button v-for="option in options" :key="option.value" type="button" role="option"
        :disabled="option.disabled" @click="emit('update:modelValue', option.value)">{{ option.label }}</button>
    </div>
  `,
});

function factory(proposal = {}, props = {}) {
  return mount(ProposalStatusSelect, {
    props: {
      proposal: {
        id: 1,
        status: 'sent',
        available_transitions: ['negotiating', 'rejected'],
        ...proposal,
      },
      ...props,
    },
    global: { stubs: { BaseChoiceSelect: ChoiceSelectStub } },
  });
}

describe('ProposalStatusSelect', () => {
  // Falla si el selector deja de conservar el estado confirmado como opción bloqueada.
  it('passes the confirmed status as the disabled choice', () => {
    const wrapper = factory();
    const choice = wrapper.getComponent(ChoiceSelectStub);

    expect(choice.props('modelValue')).toBe('sent');
    expect(choice.props('options')[0]).toEqual({ value: 'sent', label: 'Enviada', disabled: true });
  });

  // Falla si las transiciones permitidas pierden su grupo y pasan a confundirse con cambios forzados.
  it('separates natural transitions from forced statuses', () => {
    const wrapper = factory();
    const options = wrapper.getComponent(ChoiceSelectStub).props('options');

    expect(options.filter((option) => option.group === 'Flujo normal').map((option) => option.value))
      .toEqual(['negotiating', 'rejected']);
    expect(options.filter((option) => option.group === 'Forzar estado').map((option) => option.value))
      .toEqual(['draft', 'viewed', 'accepted', 'finished', 'expired']);
  });

  // Falla si un estado terminal vuelve a publicar un grupo vacío de transiciones naturales.
  it('omits natural transitions for a terminal status', () => {
    const wrapper = factory({ status: 'finished', available_transitions: [] });
    const options = wrapper.getComponent(ChoiceSelectStub).props('options');

    expect(options.some((option) => option.group === 'Flujo normal')).toBe(false);
    expect(options.filter((option) => option.group === 'Forzar estado').map((option) => option.value))
      .toEqual(['draft', 'sent', 'viewed', 'negotiating', 'accepted', 'rejected', 'expired']);
    expect(options.filter((option) => option.group === 'Forzar estado').map((option) => option.value))
      .not.toContain('finished');
  });

  // Falla si escoger un destino modifica el estado visual antes de que el PATCH del padre lo confirme.
  it('emits a change intent while keeping the confirmed status visible', async () => {
    const wrapper = factory();
    const accepted = wrapper.findAll('[role="option"]').find((option) => option.text() === 'Aceptada');

    await accepted.trigger('click');

    expect(wrapper.emitted('change')).toEqual([['accepted']]);
    expect(wrapper.get('[role="combobox"]').text()).toBe('Enviada');
  });

  // Falla si una actualización pendiente permite enviar un segundo cambio de estado.
  it('disables the choice control while an update is pending', () => {
    const wrapper = factory({}, { updating: true });

    expect(wrapper.get('[role="combobox"]').attributes('disabled')).toBe('');
    expect(wrapper.find('svg').attributes('class')).toBe('animate-spin h-3 w-3 text-text-muted');
  });
});
