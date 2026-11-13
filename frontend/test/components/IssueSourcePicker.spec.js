import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import IssueSourcePicker from '../../components/platform/issues/IssueSourcePicker.vue';

const requirements = [
  { id: 41, title: 'RequerimientoExtremoSinEspacios'.padEnd(300, 'X'), contract_title: 'Alcance vigente', stage_title: 'Etapa 1: revisión del cliente' },
  { id: 42, title: 'Segundo requerimiento de la misma etapa', contract_title: 'Alcance vigente', stage_title: 'Etapa 1: revisión del cliente' },
];

const ChoiceSelectStub = defineComponent({
  name: 'BaseChoiceSelect',
  props: ['modelValue', 'options', 'required'],
  emits: ['update:modelValue'],
  template: `
    <div role="combobox">
      <button v-for="option in options" :key="String(option.value)" type="button" role="option"
        @click="$emit('update:modelValue', option.value)">{{ option.label }}</button>
    </div>
  `,
});

function renderPicker(props = {}) {
  return mount(IssueSourcePicker, {
    props: { id: 'bug-source', options: requirements, ...props },
    global: { stubs: { BaseChoiceSelect: ChoiceSelectStub } },
  });
}

describe('IssueSourcePicker', () => {
  let originalUseI18n;

  beforeEach(() => {
    originalUseI18n = global.useI18n;
    global.useI18n = () => ({ t: (key) => key });
  });
  afterEach(() => { global.useI18n = originalUseI18n; });

  // Falla si el requerimiento ya elegido deja de identificarse debajo del selector cerrado.
  it('shows the complete preselected requirement below the closed control', () => {
    const wrapper = renderPicker({ modelValue: 41 });

    expect(wrapper.get('[data-testid="issue-source-title"]').text()).toBe(requirements[0].title);
    expect(wrapper.get('[data-testid="issue-source-selection"]').text())
      .toBe(`${requirements[0].title}${requirements[0].contract_title} · ${requirements[0].stage_title}`);
    expect(wrapper.getComponent(ChoiceSelectStub).attributes('aria-describedby')).toBe('bug-source-selection');
  });

  // Falla si el selector deja de conservar los ids numéricos al elegir otra fuente.
  it('emits the numeric identifier selected with the listbox', async () => {
    const wrapper = renderPicker({ modelValue: 41 });
    const nextRequirement = wrapper.findAll('[role="option"]').find((option) => option.text().startsWith(requirements[1].title));

    await nextRequirement.trigger('click');

    expect(wrapper.emitted('update:modelValue')).toEqual([[42]]);
  });

  // Falla si las opciones dejan de mostrar el requisito antes de su contrato y etapa.
  it('passes each requirement label to the choice control', () => {
    const wrapper = renderPicker();

    expect(wrapper.getComponent(ChoiceSelectStub).props('options')[1].label)
      .toBe(`${requirements[0].title} · ${requirements[0].contract_title} · ${requirements[0].stage_title}`);
  });

  // Falla si la opción general deja de emitir null y queda un id de requerimiento obsoleto.
  it('emits null when the optional source is cleared', async () => {
    const wrapper = renderPicker({ modelValue: 41 });
    const general = wrapper.findAll('[role="option"]').find((option) => option.text() === 'platformIssues.general');

    await general.trigger('click');
    await wrapper.setProps({ modelValue: null });

    expect(wrapper.emitted('update:modelValue')).toEqual([[null]]);
    expect(wrapper.find('[data-testid="issue-source-selection"]').exists()).toBe(false);
  });

  // Falla si el resumen no reacciona cuando llegan opciones nuevas o desaparece la fuente elegida.
  it('updates the source summary when the available requirements change', async () => {
    const wrapper = renderPicker({ modelValue: 41, options: [] });

    await wrapper.setProps({ options: requirements });
    expect(wrapper.get('[data-testid="issue-source-title"]').text()).toBe(requirements[0].title);

    await wrapper.setProps({ modelValue: 42 });
    expect(wrapper.get('[data-testid="issue-source-title"]').text()).toBe(requirements[1].title);

    await wrapper.setProps({ options: [requirements[0]] });
    expect(wrapper.find('[data-testid="issue-source-selection"]').exists()).toBe(false);
  });

  // Falla si una fuente obligatoria pierde el requisito nativo que evita guardar el issue sin origen.
  it('passes the required contract to the choice control', () => {
    const wrapper = renderPicker({ required: true });

    expect(wrapper.getComponent(ChoiceSelectStub).props('required')).toBe(true);
  });
});
