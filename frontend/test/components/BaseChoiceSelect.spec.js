import { defineComponent, ref } from 'vue';
import { mount } from '@vue/test-utils';
import BaseChoiceSelect from '../../components/base/BaseChoiceSelect.vue';

const FloatingListboxStub = defineComponent({
  name: 'BaseFloatingListbox',
  props: ['open'],
  emits: ['close'],
  template: '<div v-if="open" role="listbox"><slot /></div>',
});

const BaseInputStub = defineComponent({
  name: 'BaseInput',
  props: ['modelValue', 'type'],
  emits: ['update:modelValue'],
  template: '<input :type="type" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)">',
});

function renderChoice(props = {}) {
  return mount(BaseChoiceSelect, {
    props: {
      id: 'project-stage',
      modelValue: 7,
      options: [
        { value: 7, label: 'Diagnóstico' },
        { value: 9, label: 'Implementación' },
      ],
      ...props,
    },
    global: {
      stubs: {
        BaseFloatingListbox: FloatingListboxStub,
        BaseInput: BaseInputStub,
        BaseActionIcon: true,
      },
    },
  });
}

function renderRequiredForm() {
  const submit = jest.fn();
  const FormHarness = defineComponent({
    components: { BaseChoiceSelect },
    setup() {
      return { selected: ref(null), submit };
    },
    template: `
      <form data-testid="choice-form" @submit.prevent="submit">
        <BaseChoiceSelect v-model="selected" required :options="[{ value: 12, label: 'Plan profesional' }]" />
      </form>
    `,
  });
  const wrapper = mount(FormHarness, {
    global: {
      stubs: {
        BaseFloatingListbox: FloatingListboxStub,
        BaseInput: BaseInputStub,
        BaseActionIcon: true,
      },
    },
  });
  return { submit, wrapper };
}

describe('BaseChoiceSelect', () => {
  // Falla si elegir una opción numérica convierte su id a texto antes de llegar al formulario padre.
  it('emits a numeric option value after a pointer selection', async () => {
    const wrapper = renderChoice();

    await wrapper.get('[role="combobox"]').trigger('click');
    await wrapper.findAll('[role="option"]').find((option) => option.text() === 'Implementación').trigger('click');

    expect(wrapper.emitted('update:modelValue')).toEqual([[9]]);
    expect(wrapper.get('[role="combobox"]').attributes('aria-expanded')).toBe('false');
  });

  // Falla si una opción bloqueada puede reemplazar el valor confirmado del formulario.
  it('does not emit when a disabled option is selected', async () => {
    const wrapper = renderChoice({ options: [{ value: 7, label: 'Diagnóstico', disabled: true }] });

    await wrapper.get('[role="combobox"]').trigger('click');
    await wrapper.get('[role="option"]').trigger('click');

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(wrapper.get('[role="combobox"]').text()).toBe('Diagnóstico');
  });

  // Falla si diez opciones ya no habilitan búsqueda o si la búsqueda pierde coincidencias con tildes.
  it('searches accent-insensitively once the option threshold is reached', async () => {
    const wrapper = renderChoice({
      options: [
        { value: 1, label: 'Árbol de decisiones' },
        ...Array.from({ length: 9 }, (_, index) => ({ value: index + 2, label: `Alternativa ${index + 2}` })),
      ],
    });

    await wrapper.get('[role="combobox"]').trigger('click');
    await wrapper.get('input[type="search"]').setValue('arbol');

    expect(wrapper.findAll('[role="option"]').map((option) => option.text())).toEqual(['Árbol de decisiones']);
  });

  // Falla si un selector inhabilitado abre resultados que el usuario no puede confirmar.
  it('keeps its listbox closed while disabled', async () => {
    const wrapper = renderChoice({ disabled: true });

    await wrapper.get('[role="combobox"]').trigger('click');

    expect(wrapper.get('[role="combobox"]').attributes('aria-expanded')).toBe('false');
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false);
  });

  // Falla si un campo obligatorio vacío deja pasar el envío nativo sin una elección.
  it('fails native validity while its required value is empty', () => {
    const wrapper = renderChoice({ modelValue: null, required: true });

    expect(wrapper.get('input[required]').element.checkValidity()).toBe(false);
  });

  // Falla si escoger una opción dentro de un formulario activa un submit implícito.
  it('selects a required choice without submitting its parent form', async () => {
    const { submit, wrapper } = renderRequiredForm();

    await wrapper.get('[role="combobox"]').trigger('click');
    await wrapper.get('[role="option"]').trigger('click');

    expect(wrapper.get('[role="combobox"]').text()).toBe('Plan profesional');
    expect(wrapper.get('[data-testid="choice-form"]').element.checkValidity()).toBe(true);
    expect(submit).toHaveBeenCalledTimes(0);
  });
});
