import { flushPromises, mount } from '@vue/test-utils';
import ServiceContractTermField from '../../components/BusinessProposal/admin/ServiceContractTermField.vue';

const proposalStore = { fetchCompanySettings: jest.fn() };

global.useProposalStore = jest.fn(() => proposalStore);

global.useI18n = () => ({
  t: (key, values = {}) => ({
    'serviceContract.custom': 'Personalizado',
    'serviceContract.savedValue': 'Valor guardado',
    'serviceContract.customLabel': `${values.field}: valor personalizado`,
    'serviceContract.monthsHint': 'Meses enteros, de 1 a 999.',
    'serviceContract.daysHint': 'Días calendario enteros, de 1 a 999.',
    'serviceContract.formHint': 'Elige una opción o un número personalizado.',
    'serviceContract.loading': 'Cargando configuración…',
    'serviceContract.loadError': 'No se pudo cargar la configuración del servicio. Reintenta para continuar.',
    'serviceContract.retry': 'Reintentar',
    'serviceContract.invalidNumber': 'Escribe un entero entre 1 y 999.',
    'serviceContract.fields.service_initial_term': 'Duración inicial',
    'serviceContract.fields.service_renewal_notice_days': 'Preaviso para no renovar (días calendario)',
    'serviceContract.fields.service_termination_notice_days': 'Preaviso de terminación del cliente (días calendario)',
  }[key] || key),
});

global.useMarkdownPreview = jest.fn(() => ({
  parseMarkdown: jest.fn((val) => val),
}));

jest.mock('dompurify', () => ({ sanitize: jest.fn((val) => val) }));

import ContractParamsModal from '../../components/BusinessProposal/admin/ContractParamsModal.vue';
import BaseFormField from '../../components/base/BaseFormField.vue';

// BaseFormField is not global in jest.setup; tests that read field errors pass it in.
function mountContractParamsModal(props = {}, components = {}) {
  return mount(ContractParamsModal, {
    props: {
      visible: true,
      proposal: { client_name: 'Acme Corp', client_email: 'client@acme.com' },
      initialParams: {},
      isEditing: false,
      saving: false,
      ...props,
    },
    global: {
      components,
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size'],
          template: '<div v-if="modelValue"><slot /></div>',
        },
        BaseSegmented: {
          props: ['modelValue', 'options', 'fullWidth'],
          emits: ['update:modelValue'],
          template: '<div><button v-for="o in options" :key="o.value" type="button" @click="$emit(\'update:modelValue\', o.value)">{{ o.label }}</button></div>',
        },
        BaseButton: {
          props: ['variant', 'size', 'loading', 'disabled', 'type'],
          emits: ['click'],
          template: '<button v-bind="$attrs" :type="type || \'button\'" :disabled="disabled || loading" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        BaseInput: {
          props: ['modelValue', 'type', 'size', 'placeholder'],
          template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseSelect: {
          props: ['modelValue', 'options', 'size'],
          template: '<select v-bind="$attrs" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
        },
        BaseFormField: {
          props: ['error'],
          template: '<label><slot /><span v-if="error">{{ error }}</span></label>',
        },
      },
    },
  });
}

describe('ContractParamsModal', () => {
  it('renders the modal form when visible', () => {
    const wrapper = mountContractParamsModal();

    expect(wrapper.find('form').exists()).toBe(true);
  });

  it('shows "Generar contrato" heading when not editing', () => {
    const wrapper = mountContractParamsModal({ isEditing: false });

    expect(wrapper.text()).toContain('Generar contrato de desarrollo');
  });

  it('shows "Editar contrato" heading when isEditing is true', () => {
    const wrapper = mountContractParamsModal({ isEditing: true });

    expect(wrapper.text()).toContain('Editar contrato de desarrollo');
  });

  it('emits cancel when cancel button is clicked', async () => {
    const wrapper = mountContractParamsModal();

    const cancelBtn = wrapper.findAll('button').find(b => b.text() === 'Cancelar');
    await cancelBtn.trigger('click');

    expect(wrapper.emitted('cancel')).toEqual([[]]);
  });

  it('switches to custom contract mode when custom button is clicked', async () => {
    const wrapper = mountContractParamsModal();

    const customBtn = wrapper.findAll('button').find(b => b.text() === 'Contrato personalizado');
    await customBtn.trigger('click');

    expect(wrapper.text()).toContain('Contenido del contrato (Markdown)');
  });

  it('does not render form when visible is false', () => {
    const wrapper = mountContractParamsModal({ visible: false });

    expect(wrapper.find('form').exists()).toBe(false);
  });
});

describe('ContractParamsModal — identificación del contratista', () => {
  // The contract prints whichever document is on file, preferring the NIT, so
  // either one on its own is a complete answer — but neither is not.
  const FILLED = {
    contractor_full_name: 'GUSTAVO ADOLFO PEREZ PEREZ',
    contractor_email: 'team@projectapp.co',
    contract_city: 'Medellín',
    bank_name: 'Bancolombia',
    bank_account_number: '123456789',
    client_full_name: 'Acme Corp',
    client_cedula: '123456',
    client_email: 'client@acme.com',
    contract_date: '2026-08-11',
  };

  // The `visible` watcher is not immediate, so mounting straight to true never
  // runs resetForm() and the form would stay empty. Toggle it instead.
  async function openWith(params) {
    const wrapper = mountContractParamsModal({ visible: false, initialParams: params });
    await wrapper.setProps({ visible: true });
    await new Promise((resolve) => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();
    return wrapper;
  }

  function submit(wrapper) {
    return wrapper.find('form').trigger('submit');
  }

  it('blocks the submit and explains why when neither document is filled', async () => {
    const wrapper = await openWith({ ...FILLED, contractor_nit: '', contractor_cedula: '' });

    await submit(wrapper);

    expect(wrapper.emitted('confirm')).toBeFalsy();
    expect(wrapper.text()).toContain('Indica el NIT o la cédula del contratista');
  });

  it('accepts a contractor identified only by NIT', async () => {
    const wrapper = await openWith({ ...FILLED, contractor_nit: '900.123.456-7', contractor_cedula: '' });

    await submit(wrapper);

    expect(wrapper.emitted('confirm')).toBeTruthy();
    expect(wrapper.emitted('confirm')[0][0].contractor_nit).toBe('900.123.456-7');
  });

  it('accepts a contractor identified only by cédula and sends it', async () => {
    const wrapper = await openWith({ ...FILLED, contractor_nit: '', contractor_cedula: '1037635428' });

    await submit(wrapper);

    expect(wrapper.emitted('confirm')).toBeTruthy();
    const payload = wrapper.emitted('confirm')[0][0];
    expect(payload.contractor_cedula).toBe('1037635428');
    expect(payload.contractor_nit).toBe('');
  });
});

describe('ContractParamsModal — contratos separados', () => {
  const PARTIES = {
    contractor_full_name: 'GUSTAVO ADOLFO PEREZ PEREZ',
    contractor_nit: '900.123.456-7',
    contractor_email: 'team@projectapp.co',
    contract_city: 'Medellín',
    bank_name: 'Bancolombia',
    bank_account_number: '123456789',
    client_full_name: 'Acme Corp',
    client_cedula: '123456',
    client_email: 'client@acme.com',
    contract_date: '2026-09-26',
  };
  const SERVICE_SETTINGS = {
    duration_options: [3, 6, 9, 12],
    notice_options: [30, 60, 90],
    default_duration: 9,
    default_renewal_notice: 60,
    default_termination_notice: 60,
  };

  beforeEach(() => {
    proposalStore.fetchCompanySettings.mockReset().mockResolvedValue({ success: true, data: {} });
  });

  async function openFor(variant, params, proposal, components) {
    const wrapper = mountContractParamsModal(
      { visible: false, initialParams: params, variant, ...(proposal ? { proposal } : {}) },
      components,
    );
    await wrapper.setProps({ visible: true });
    await new Promise((resolve) => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();
    return wrapper;
  }

  it('preselects the configured service terms', async () => {
    // Falla si el contrato abre con campos de texto o ignora las preselecciones administrativas.
    proposalStore.fetchCompanySettings.mockResolvedValue({
      success: true,
      data: { service_contract_settings: SERVICE_SETTINGS },
    });
    const wrapper = await openFor('service', PARTIES);
    const fields = wrapper.findAllComponents(ServiceContractTermField);

    expect(fields.map((field) => field.get('select').element.value)).toEqual(['9', '60', '60']);

    await wrapper.get('form').trigger('submit');

    expect(wrapper.emitted('confirm')[0][0]).toMatchObject({
      service_contract_source: 'default',
      service_initial_term: 9,
      service_renewal_notice_days: 60,
      service_termination_notice_days: 60,
    });
  });

  it('serializes a custom service duration as an integer', async () => {
    // Falla si un valor personalizado viaja como etiqueta de presentación en vez del número del API.
    proposalStore.fetchCompanySettings.mockResolvedValue({
      success: true,
      data: { service_contract_settings: SERVICE_SETTINGS },
    });
    const wrapper = await openFor('service', PARTIES);
    const duration = wrapper.findAllComponents(ServiceContractTermField)[0];

    await duration.get('select').setValue('custom');
    await duration.get('input').setValue('21');
    await wrapper.get('form').trigger('submit');

    expect(wrapper.emitted('confirm')[0][0].service_initial_term).toBe(21);
  });

  test.each(['', '1000'])('blocks custom service duration %p', async (customValue) => {
    // Falla si un número vacío o fuera del límite habilita una cláusula que el contrato no puede representar.
    proposalStore.fetchCompanySettings.mockResolvedValue({
      success: true,
      data: { service_contract_settings: SERVICE_SETTINGS },
    });
    const wrapper = await openFor('service', PARTIES);
    const duration = wrapper.findAllComponents(ServiceContractTermField)[0];

    await duration.get('select').setValue('custom');
    await duration.get('input').setValue(customValue);
    await wrapper.get('form').trigger('submit');

    expect(wrapper.emitted('confirm')).toBeFalsy();
    expect(wrapper.text()).toContain('Escribe un entero entre 1 y 999.');
  });

  it('preserves a legacy service duration during submission', async () => {
    // Falla si editar un contrato previo normaliza o elimina una cláusula histórica no canónica.
    proposalStore.fetchCompanySettings.mockResolvedValue({
      success: true,
      data: { service_contract_settings: SERVICE_SETTINGS },
    });
    const wrapper = await openFor('service', {
      ...PARTIES,
      service_initial_term: 'doce (12) meses iniciales',
    });

    await wrapper.get('form').trigger('submit');

    expect(wrapper.emitted('confirm')[0][0].service_initial_term).toBe('doce (12) meses iniciales');
  });

  it('requires a successful service-settings retry', async () => {
    // Falla si se permite generar con valores vacíos después de que la configuración no cargó.
    proposalStore.fetchCompanySettings
      .mockResolvedValueOnce({ success: false })
      .mockResolvedValueOnce({ success: true, data: { service_contract_settings: SERVICE_SETTINGS } });
    const wrapper = await openFor('service', PARTIES);

    expect(wrapper.text()).toContain('No se pudo cargar la configuración del servicio. Reintenta para continuar.');
    await wrapper.get('form').trigger('submit');
    expect(wrapper.emitted('confirm')).toBeFalsy();

    const retry = wrapper.findAll('button').find((button) => button.text() === 'Reintentar');
    await retry.trigger('click');
    await flushPromises();
    expect(wrapper.findAllComponents(ServiceContractTermField)).toHaveLength(3);
    await wrapper.get('form').trigger('submit');

    expect(wrapper.emitted('confirm')[0][0]).toMatchObject({
      service_initial_term: 9,
      service_renewal_notice_days: 60,
      service_termination_notice_days: 60,
    });
  });

  it('uses refreshed defaults when the service modal reopens', async () => {
    // Falla si una nueva apertura reutiliza valores predeterminados que el administrador ya cambió.
    proposalStore.fetchCompanySettings
      .mockResolvedValueOnce({ success: true, data: { service_contract_settings: SERVICE_SETTINGS } })
      .mockResolvedValueOnce({
        success: true,
        data: {
          service_contract_settings: {
            ...SERVICE_SETTINGS,
            default_duration: 12,
            default_renewal_notice: 90,
            default_termination_notice: 30,
          },
        },
      });
    const wrapper = mountContractParamsModal({ visible: false, initialParams: PARTIES, variant: 'service' });

    await wrapper.setProps({ visible: true });
    await flushPromises();
    await wrapper.setProps({ visible: false });
    await wrapper.setProps({ visible: true });
    await flushPromises();

    const fields = wrapper.findAllComponents(ServiceContractTermField);
    expect(fields.map((field) => field.get('select').element.value)).toEqual(['12', '90', '30']);
  });

  it('keeps a saved service term when the service modal reopens', async () => {
    // Falla si recargar los valores globales sobrescribe una condición ya negociada con el cliente.
    proposalStore.fetchCompanySettings
      .mockResolvedValueOnce({ success: true, data: { service_contract_settings: SERVICE_SETTINGS } })
      .mockResolvedValueOnce({
        success: true,
        data: { service_contract_settings: { ...SERVICE_SETTINGS, default_duration: 12 } },
      });
    const wrapper = mountContractParamsModal({
      visible: false,
      initialParams: { ...PARTIES, service_initial_term: 6 },
      variant: 'service',
    });

    await wrapper.setProps({ visible: true });
    await flushPromises();
    await wrapper.setProps({ visible: false });
    await wrapper.setProps({ visible: true });
    await flushPromises();

    expect(wrapper.findAllComponents(ServiceContractTermField)[0].get('select').element.value).toBe('6');
  });

  it('keeps the service terms out of the single contract payload', async () => {
    // Falla si editar el contrato único borra los datos guardados del servicio.
    const wrapper = await openFor('combined', PARTIES);

    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('confirm')[0][0];
    expect(payload.contract_source).toBe('default');
    expect(payload).not.toHaveProperty('service_initial_term');
    expect(wrapper.find('[data-testid="contract-service-terms"]').exists()).toBe(false);
  });

  it('edits the custom text of the product contract only', async () => {
    // Falla si el texto personalizado del producto se guarda como el del contrato único.
    const wrapper = await openFor('product', {
      ...PARTIES, product_contract_source: 'custom', product_custom_contract_markdown: '# Producto negociado',
      custom_contract_markdown: '# Contrato único',
    });

    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('confirm')[0][0]).toEqual({
      product_contract_source: 'custom',
      product_custom_contract_markdown: '# Producto negociado',
      contract_date: '2026-09-26',
    });
  });

  test.each([
    ['sent', 'Generar contrato y negociar'],
    ['negotiating', 'Generar contrato'],
  ])('labels the submit of a %s proposal "%s"', async (status, label) => {
    // Falla si generar un contrato en negociación promete mover la propuesta de estado.
    const wrapper = await openFor('combined', PARTIES, { client_name: 'Acme Corp', status });
    const submitButton = wrapper.findAll('button').find((button) => button.attributes('type') === 'submit');

    expect(submitButton.text()).toBe(label);
  });
});
