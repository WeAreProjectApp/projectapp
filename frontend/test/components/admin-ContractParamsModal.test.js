import { mount } from '@vue/test-utils';

global.useProposalStore = jest.fn(() => ({
  fetchCompanySettings: jest.fn().mockResolvedValue({ success: true, data: {} }),
}));

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
          template: '<button :type="type || \'button\'" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        BaseInput: {
          props: ['modelValue', 'type', 'size', 'placeholder'],
          template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseSelect: {
          props: ['modelValue', 'options', 'size'],
          template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option></select>',
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

    expect(wrapper.emitted('cancel')).toBeTruthy();
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
  const SERVICE_TERMS = {
    service_initial_term: 'doce (12) meses',
    service_renewal_notice_days: 'treinta (30)',
    service_termination_notice_days: 'treinta (30)',
  };

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

  it('asks for the service terms before generating the service contract', async () => {
    // Falla si el contrato de servicio se genera sin duración ni preavisos.
    const wrapper = await openFor('service', PARTIES, undefined, { BaseFormField });

    await wrapper.find('form').trigger('submit');

    expect(wrapper.text()).toContain('Generar contrato de servicio');
    const terms = wrapper.get('[data-testid="contract-service-terms"]');
    expect(terms.text()).toContain('Duración inicial es obligatorio');
    expect(wrapper.emitted('confirm')).toBeFalsy();
  });

  it('sends the service terms with the service contract', async () => {
    // Falla si los tres datos del servicio no viajan al generar su contrato.
    const wrapper = await openFor('service', { ...PARTIES, ...SERVICE_TERMS });

    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('confirm')[0][0];
    expect(payload).toMatchObject({ service_contract_source: 'default', ...SERVICE_TERMS });
    expect(payload.contract_source).toBeUndefined();
  });

  it('keeps the service terms out of the single contract payload', async () => {
    // Falla si editar el contrato único borra los datos guardados del servicio.
    const wrapper = await openFor('combined', { ...PARTIES, ...SERVICE_TERMS });

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
