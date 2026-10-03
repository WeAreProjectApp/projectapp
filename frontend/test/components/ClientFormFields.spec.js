import { mount } from '@vue/test-utils';

import ClientFormFields from '~/components/clients/ClientFormFields.vue';
import { emptyClientForm } from '~/utils/billingCode';

function mountFields(overrides = {}, testidPrefix = 'clients-new') {
  return mount(ClientFormFields, {
    props: {
      modelValue: { ...emptyClientForm(), ...overrides },
      testidPrefix,
    },
    global: {
      stubs: {
        BaseSelect: {
          props: ['modelValue', 'options'],
          emits: ['update:modelValue'],
          template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
        },
      },
    },
  });
}

describe('ClientFormFields', () => {
  it('marks the client name as required', () => {
    // Fails if inline client creation allows a blank legal customer name.
    const wrapper = mountFields();

    expect(wrapper.get('[data-testid="clients-new-name"]').attributes('required')).toBe('');
  });

  it('limits the billing code to the server column width', () => {
    // Fails if the shared form accepts a billing code that the API will reject.
    const wrapper = mountFields();

    expect(wrapper.get('[data-testid="clients-new-billing-code"]').attributes('maxlength')).toBe('12');
  });

  it('emits the billing code with the client form payload', async () => {
    // Fails if collection and income inline forms stop sending the billing code.
    const wrapper = mountFields();

    await wrapper.find('[data-testid="clients-new-billing-code"]').setValue('G&M');

    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual({
      ...emptyClientForm(),
      billing_code: 'G&M',
    });
  });

  it('uses the supplied test id prefix for an inline client update', async () => {
    // Fails if a surface loses its isolated hook and updates the wrong client input.
    const wrapper = mountFields({}, 'collection-form-inline-client');

    await wrapper.find('[data-testid="collection-form-inline-client-billing-code"]').setValue('ACME');

    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual({
      ...emptyClientForm(),
      billing_code: 'ACME',
    });
  });

  it('emits C.C. as the selected identification type', async () => {
    // Fails if a natural person's identity is saved as NIT after selecting C.C.
    const wrapper = mountFields();

    await wrapper.find('[data-testid="clients-new-identification-type"]').setValue('CC');

    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual({
      ...emptyClientForm(),
      identification_type: 'CC',
    });
  });

  it('emits the cédula field after the selected type changes', async () => {
    // Fails if the number remains bound to nit after the form receives C.C.
    const wrapper = mountFields();
    await wrapper.setProps({ modelValue: { ...emptyClientForm(), identification_type: 'CC' } });

    await wrapper.find('[data-testid="clients-new-cedula"]').setValue('10203040');

    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual({
      ...emptyClientForm(),
      identification_type: 'CC',
      cedula: '10203040',
    });
  });

  it('shows a legacy cédula value when the stored type is absent', () => {
    // Fails if legacy client rows show the C.C. selector but bind the number to an empty NIT field.
    const wrapper = mountFields({ identification_type: undefined, nit: '', cedula: '10203040' });

    expect(wrapper.get('[data-testid="clients-new-cedula"]').element.value).toBe('10203040');
  });

  it('emits the typed address from the shared client form', async () => {
    // Fails if the address field is absent or no longer updates the client payload.
    const wrapper = mountFields();

    await wrapper.find('[data-testid="clients-new-address"]').setValue('Carrera 7 # 72-41');

    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual({
      ...emptyClientForm(),
      address: 'Carrera 7 # 72-41',
    });
  });
});
