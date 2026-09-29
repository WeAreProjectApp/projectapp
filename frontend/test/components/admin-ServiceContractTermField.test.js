import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import ServiceContractTermField from '../../components/BusinessProposal/admin/ServiceContractTermField.vue';

enableAutoUnmount(afterEach);

global.useI18n = () => ({
  t: (key, values = {}) => ({
    'serviceContract.custom': 'Personalizar',
    'serviceContract.customLabel': `${values.field}: valor personalizado`,
    'serviceContract.customDurationHint': 'Incluye la unidad.',
    'serviceContract.customNoticeHint': 'La plantilla agrega días calendario.',
  }[key] || key),
});

function mountField(props = {}) {
  return mount(ServiceContractTermField, {
    props: {
      modelValue: '',
      options: [3, 6, 9],
      label: 'Duración inicial',
      duration: true,
      ...props,
    },
    attachTo: document.body,
    global: {
      stubs: { Teleport: true },
      components: {
        BaseFormField,
        BaseInput,
      },
    },
  });
}

async function choose(wrapper, label) {
  await wrapper.get('[role="combobox"]').trigger('click');
  await wrapper.findAll('[role="option"]').find(option => option.text() === label).trigger('click');
}

describe('ServiceContractTermField', () => {
  it('emits the selected preset as a number', async () => {
    // Falla si elegir una opción frecuente envía la etiqueta contractual en vez del número API.
    const wrapper = mountField();

    await choose(wrapper, 'nueve (9) meses');

    expect(wrapper.emitted('update:modelValue')[0][0]).toBe(9);
  });

  it('emits the custom contractual wording literally', async () => {
    // Falla si el campo descarta la redacción libre o la transforma en un número.
    const wrapper = mountField();

    await choose(wrapper, 'Personalizar');
    await wrapper.get('input').setValue('dieciocho meses iniciales');

    expect(wrapper.emitted('update:modelValue')[1][0]).toBe('dieciocho meses iniciales');
  });

  it('restores the entered custom text after selecting a preset', async () => {
    // Falla si alternar una opción frecuente descarta el texto personalizado que el usuario quiere recuperar.
    const wrapper = mountField();

    await wrapper.get('input').setValue('dieciocho meses iniciales');
    await choose(wrapper, 'nueve (9) meses');
    await choose(wrapper, 'Personalizar');

    expect(wrapper.get('input').element.value).toBe('dieciocho meses iniciales');
    expect(wrapper.emitted('update:modelValue')[2][0]).toBe('dieciocho meses iniciales');
  });

  it('keeps the custom editor when its wording matches a preset', async () => {
    // Falla si ingresar nueve como personalizado cambia silenciosamente la decisión del usuario a una opción frecuente.
    const wrapper = mountField();

    await wrapper.get('input').setValue('nueve (9) meses');
    await wrapper.setProps({ modelValue: 'nueve (9) meses' });

    expect(wrapper.get('[role="combobox"]').text()).toBe('Personalizar');
    expect(wrapper.get('input').element.value).toBe('nueve (9) meses');
  });

  it('opens historical wording in the editable custom field', async () => {
    // Falla si una condición ya negociada queda atrapada en Valor guardado.
    const wrapper = mountField({ modelValue: 'plazo pactado de un año' });

    await wrapper.get('input').setValue('plazo pactado de dos años');

    expect(wrapper.get('[role="combobox"]').text()).toBe('Personalizar');
    expect(wrapper.emitted('update:modelValue')[0][0]).toBe('plazo pactado de dos años');
  });

  it('prefills custom wording from the currently selected preset', async () => {
    // Falla si Personalizar toma el valor inicial en lugar de la opción vigente.
    const wrapper = mountField({ modelValue: 3 });
    await choose(wrapper, 'nueve (9) meses');
    await wrapper.setProps({ modelValue: 9 });

    await choose(wrapper, 'Personalizar');

    expect(wrapper.get('input').element.value).toBe('nueve (9) meses');
    expect(wrapper.emitted('update:modelValue')[1][0]).toBe('nueve (9) meses');
  });

  it('preserves an intentionally empty custom draft after a preset', async () => {
    // Falla si alternar rellena de nuevo un borrador que el operador borró.
    const wrapper = mountField({ modelValue: 3 });
    await choose(wrapper, 'Personalizar');
    await wrapper.get('input').setValue('');
    await wrapper.setProps({ modelValue: '' });
    await choose(wrapper, 'nueve (9) meses');
    await wrapper.setProps({ modelValue: 9 });

    await choose(wrapper, 'Personalizar');

    expect(wrapper.get('input').element.value).toBe('');
    expect(wrapper.emitted('update:modelValue')[3][0]).toBe('');
  });

  it('chooses a preset using the keyboard', async () => {
    const wrapper = mountField({ modelValue: 3 });
    const trigger = wrapper.get('[role="combobox"]');

    await trigger.trigger('keydown', { key: 'ArrowDown' });
    await trigger.trigger('keydown', { key: 'ArrowDown' });
    await trigger.trigger('keydown', { key: 'Enter' });

    expect(wrapper.emitted('update:modelValue')[0][0]).toBe(6);
  });

  it('focuses the custom editor after choosing Personalizar', async () => {
    const wrapper = mountField({ modelValue: 3 });

    await choose(wrapper, 'Personalizar');

    expect(document.activeElement).toBe(wrapper.get('input').element);
  });

  it('closes an open list when saving starts', async () => {
    const wrapper = mountField({ modelValue: 3 });
    await wrapper.get('[role="combobox"]').trigger('click');

    await wrapper.setProps({ disabled: true });

    expect(wrapper.find('[role="listbox"]').exists()).toBe(false);
    expect(wrapper.get('[role="combobox"]').element.disabled).toBe(true);
  });

  it('keeps the chosen value when Tab dismisses the options', async () => {
    const wrapper = mountField({ modelValue: 3 });
    const trigger = wrapper.get('[role="combobox"]');
    await trigger.trigger('keydown', { key: 'End' });

    await trigger.trigger('keydown', { key: 'Tab' });

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(trigger.text()).toBe('tres (3) meses');
  });

  it('connects a server error to the dropdown', async () => {
    const wrapper = mountField({ modelValue: 3 });

    await wrapper.setProps({ error: 'Revisa la duración acordada.' });
    await flushPromises();

    expect(wrapper.get('[role="combobox"]').attributes('aria-describedby')).toBe(wrapper.get('[role="alert"]').attributes('id'));
  });

});
