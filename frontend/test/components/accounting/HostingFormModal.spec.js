import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import HostingFormModal from '../../../components/accounting/HostingFormModal.vue';
import { useProposalClientsStore } from '../../../stores/proposal_clients';
import BaseFormField from '../../../components/base/BaseFormField.vue';
import BaseInput from '../../../components/base/BaseInput.vue';
import BaseSegmented from '../../../components/base/BaseSegmented.vue';

jest.mock('../../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const { get_request, create_request } = require('../../../stores/services/request_http');

const ClientAutocompleteStub = {
  name: 'ClientAutocomplete',
  props: ['modelValue', 'initialLabel', 'testId'],
  emits: ['update:modelValue', 'select', 'create-new'],
  template: '<div data-testid="client-autocomplete-stub" />',
};

const CLIENT = {
  id: 5,
  name: 'Daniel Felipe Corredor',
  company: 'MIMITTOS',
  email: 'arq.daniel@example.com',
  nit: '901234567',
  cedula: '',
  is_email_placeholder: false,
};

const LEGACY_RECORD = {
  id: 1,
  client: null,
  client_display_name: '',
  client_name: 'Jimmy & Daniel - Mimittos',
  client_email: '',
  client_contact_name: '',
  client_identification: '',
  domain_url: 'https://mimittos.com/',
  monthly_value: '19440.00',
  payment_modality: 'quarterly',
  benefit: '',
  valid_from: '2026-02-01',
  valid_to: '2026-11-01',
  payment_per_cycle: '58320.00',
  is_active: true,
  notes: '',
};

function mountModal(props = {}) {
  const pinia = createPinia();
  setActivePinia(pinia);
  return mount(HostingFormModal, {
    props: { open: true, saving: false, ...props },
    global: {
      plugins: [pinia],
      components: { BaseFormField, BaseInput, BaseSegmented },
      stubs: {
        ClientAutocomplete: ClientAutocompleteStub,
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          props: ['modelValue', 'size'],
          emits: ['close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
        BaseCurrencyInput: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input type="text" inputmode="numeric" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseTextarea: {
          props: ['modelValue', 'rows'],
          emits: ['update:modelValue'],
          template:
            '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseSelect: {
          name: 'BaseSelect',
          props: ['modelValue', 'options'],
          emits: ['update:modelValue'],
          template: '<select :value="modelValue"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
        },
        BaseToggle: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input type="checkbox" :checked="modelValue" />',
        },
        BaseButton: {
          props: ['variant', 'size', 'disabled', 'type'],
          template:
            '<button :type="type || \'button\'" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  });
}

describe('HostingFormModal', () => {
  function expectDescribedError(wrapper, testId, message) {
    const control = wrapper.get(`[data-testid="${testId}"]`);
    const errorId = control.attributes('aria-describedby');
    const error = wrapper.findAll('[role="alert"]')
      .find((node) => node.attributes('id') === errorId);
    expect(control.attributes('aria-invalid')).toBe('true');
    expect(error.exists()).toBe(true);
    expect(error.text()).toBe(message);
  }
  beforeEach(() => {
    jest.clearAllMocks();
    get_request.mockResolvedValue({ data: [CLIENT] });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('sends the client alongside the billing snapshot', async () => {
    const wrapper = mountModal();
    await flushPromises();

    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('select', CLIENT);
    await flushPromises();
    await wrapper.find('[data-testid="hosting-form-monthly"]').setValue('19440');

    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.client).toBe(5);
    // The snapshot is seeded from the profile so the cuenta de cobro prints
    // something even if the operator types nothing else.
    expect(payload.client_name).toBe('MIMITTOS');
    expect(payload.client_email).toBe('arq.daniel@example.com');
    expect(payload.client_identification).toBe('901234567');
    expect(payload.payment_modality).toBe('quarterly');
  });

  it('offers only quarterly, semiannual and nine-month periodicities', () => {
    const wrapper = mountModal();

    expect(wrapper.findComponent({ name: 'BaseSelect' }).props('options')).toEqual([
      { value: 'quarterly', label: 'Trimestral' },
      { value: 'semiannual', label: 'Semestral' },
      { value: 'nine_month', label: 'Cada 9 meses' },
    ]);
  });

  it('keeps an existing annual modality readable only while editing history', async () => {
    const wrapper = mountModal({
      record: { ...LEGACY_RECORD, payment_modality: 'annual' },
    });
    await flushPromises();

    expect(wrapper.findComponent({ name: 'BaseSelect' }).props('options')).toEqual([
      { value: 'quarterly', label: 'Trimestral' },
      { value: 'semiannual', label: 'Semestral' },
      { value: 'nine_month', label: 'Cada 9 meses' },
      { value: 'annual', label: 'Anual (histórico)' },
    ]);
  });

  it('never overwrites what the operator already typed', async () => {
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.find('[data-testid="hosting-form-client-name"]').setValue('Facturar a Otro');
    await wrapper.find('[data-testid="hosting-form-client-email"]').setValue('pagos@otro.co');
    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('select', CLIENT);
    await flushPromises();

    await wrapper.find('form').trigger('submit');

    const payload = wrapper.emitted('submit')[0][0];
    expect(payload.client_name).toBe('Facturar a Otro');
    expect(payload.client_email).toBe('pagos@otro.co');
  });

  it('suggests the matching client when editing a legacy record', async () => {
    const wrapper = mountModal({ record: { ...LEGACY_RECORD } });
    await flushPromises();

    const suggestion = wrapper.find('[data-testid="hosting-form-client-suggestion"]');
    expect(suggestion.text()).toContain('MIMITTOS');
    expect(get_request).toHaveBeenCalledWith(
      expect.stringContaining('client-profiles/search/'),
      expect.anything(),
    );

    await wrapper.find('[data-testid="hosting-form-accept-suggestion"]').trigger('click');
    await wrapper.find('form').trigger('submit');

    expect(wrapper.emitted('submit')[0][0].client).toBe(5);
  });

  it('flags a legacy record as pending instead of blocking it', async () => {
    const wrapper = mountModal({ record: { ...LEGACY_RECORD } });
    await flushPromises();

    expect(wrapper.find('[data-testid="hosting-form-client-pending"]').exists()).toBe(true);

    // Saving without a client still works: completing it is a separate step.
    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')[0][0].client).toBeNull();
  });

  it('offers no suggestion when nothing resembles a registered client', async () => {
    get_request.mockResolvedValue({ data: [] });
    const wrapper = mountModal({
      record: { ...LEGACY_RECORD, client_name: 'Katerin Ruiz - Senses Candles' },
    });
    await flushPromises();

    expect(wrapper.find('[data-testid="hosting-form-client-suggestion"]').exists()).toBe(false);
  });

  it('creates a client inline and links it', async () => {
    const wrapper = mountModal();
    await flushPromises();

    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('create-new', 'Senses Candles');
    await flushPromises();
    expect(
      wrapper.find('[data-testid="hosting-form-inline-client-name"]').element.value,
    ).toBe('Senses Candles');

    create_request.mockResolvedValueOnce({
      data: { ...CLIENT, id: 12, name: 'Senses Candles', company: '' },
    });
    await wrapper.find('[data-testid="hosting-form-inline-client-save"]').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith(
      'proposals/client-profiles/create/',
      expect.objectContaining({ name: 'Senses Candles' }),
    );
    expect(wrapper.find('[data-testid="hosting-form-inline-client"]').exists()).toBe(false);

    await wrapper.find('[data-testid="hosting-form-monthly"]').setValue('38333');
    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')[0][0].client).toBe(12);
  });

  // Falla si el alta rápida intenta enviar un cliente sin nombre o no explica el campo incompleto.
  it('rejects an empty inline hosting client name', async () => {
    const wrapper = mountModal();
    await flushPromises();
    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('create-new', '');
    await flushPromises();

    await wrapper.get('[data-testid="hosting-form-inline-client-save"]').trigger('click');

    expect(create_request).toHaveBeenCalledTimes(0);
    expectDescribedError(wrapper, 'hosting-form-inline-client-name', 'Escribe el nombre del cliente.');
  });

  // Falla si el rechazo de correo del servidor se vuelve un aviso general en lugar de marcar su control.
  it('places inline hosting email rejection on its control', async () => {
    const wrapper = mountModal();
    jest.spyOn(useProposalClientsStore(), 'createClient').mockResolvedValue({
      success: false,
      errors: { email: ['Ese correo ya existe.'] },
    });
    await flushPromises();
    wrapper.findComponent(ClientAutocompleteStub).vm.$emit('create-new', 'Senses Candles');
    await flushPromises();

    await wrapper.get('[data-testid="hosting-form-inline-client-save"]').trigger('click');
    await flushPromises();

    const emailControl = wrapper.get('[data-testid="hosting-form-inline-client-email"]');
    const emailError = wrapper.get(`#${emailControl.attributes('aria-describedby')}`);
    expect(emailControl.attributes('aria-invalid')).toBe('true');
    expect(emailError.attributes('role')).toBe('alert');
    expect(emailError.text()).toBe('Ese correo ya existe.');
  });

  it('pre-fills the only project on create but never on edit (PA-51)', async () => {
    const creating = mountModal();
    await flushPromises();
    expect(
      creating.findComponent({ name: 'ProjectSelect' }).props('autoSelectSingle'),
    ).toBe(true);

    const editing = mountModal({ record: LEGACY_RECORD });
    await flushPromises();
    expect(
      editing.findComponent({ name: 'ProjectSelect' }).props('autoSelectSingle'),
    ).toBe(false);
  });
});
