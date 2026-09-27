import { mount } from '@vue/test-utils';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseSelect from '../../components/base/BaseSelect.vue';
import ServiceContractTermField from '../../components/BusinessProposal/admin/ServiceContractTermField.vue';

global.useI18n = () => ({
  t: (key, values = {}) => ({
    'serviceContract.custom': 'Personalizado',
    'serviceContract.savedValue': 'Valor guardado',
    'serviceContract.customLabel': `${values.field}: valor personalizado`,
    'serviceContract.monthsHint': 'Meses enteros, de 1 a 999.',
    'serviceContract.daysHint': 'Días calendario enteros, de 1 a 999.',
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
    global: {
      components: {
        BaseFormField,
        BaseInput,
        BaseSelect,
      },
    },
  });
}

describe('ServiceContractTermField', () => {
  it('emits the selected preset as a number', async () => {
    // Falla si elegir una opción frecuente envía la etiqueta contractual en vez del número API.
    const wrapper = mountField();

    await wrapper.get('select').setValue('9');

    expect(wrapper.emitted('update:modelValue')[0][0]).toBe(9);
  });

  it('previews a custom duration before emitting its number', async () => {
    // Falla si el valor personalizado se guarda como texto distinto al que el contrato mostrará.
    const wrapper = mountField();

    await wrapper.get('select').setValue('custom');
    await wrapper.get('input').setValue('21');

    expect(wrapper.text()).toContain('veintiún (21) meses');
    expect(wrapper.emitted('update:modelValue')[1][0]).toBe(21);
  });

  it('restores the entered custom number after selecting a preset', async () => {
    // Falla si alternar una opción frecuente descarta el número personalizado que el usuario quiere recuperar.
    const wrapper = mountField();

    await wrapper.get('input').setValue('21');
    await wrapper.get('select').setValue('9');
    await wrapper.get('select').setValue('custom');

    expect(wrapper.get('input').element.value).toBe('21');
    expect(wrapper.emitted('update:modelValue')[2][0]).toBe(21);
  });

  it('keeps a custom selection when its number matches a preset', async () => {
    // Falla si ingresar nueve como personalizado cambia silenciosamente la decisión del usuario a una opción frecuente.
    const wrapper = mountField();

    await wrapper.get('input').setValue('9');
    await wrapper.setProps({ modelValue: 9 });

    expect(wrapper.get('select').element.value).toBe('custom');
    expect(wrapper.get('input').element.value).toBe('9');
  });

  it('preserves a noncanonical saved service term after selecting its saved value', async () => {
    // Falla si abrir un contrato anterior convierte o borra una cláusula existente.
    const wrapper = mountField({
      modelValue: 'veintidós (22) días calendario',
      duration: false,
      label: 'Preaviso para no renovar',
    });

    await wrapper.get('select').setValue('saved');

    expect(wrapper.text()).toContain('Valor guardado');
    expect(wrapper.text()).toContain('veintidós (22) días calendario');
    expect(wrapper.emitted('update:modelValue')[0][0]).toBe('veintidós (22) días calendario');
  });
});
