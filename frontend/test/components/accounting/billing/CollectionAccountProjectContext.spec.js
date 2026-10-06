import { mount, flushPromises } from '@vue/test-utils';
import CollectionAccountProjectContext from '../../../../components/accounting/billing/CollectionAccountProjectContext.vue';

jest.mock('../../../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
}));

const { get_request, create_request } = require('../../../../stores/services/request_http');

beforeAll(() => {
  global.useLocalePath = () => (path) => path;
});

afterAll(() => {
  delete global.useLocalePath;
});

function mockProjectContextRequests() {
  get_request.mockImplementation((url) => {
    if (url.includes('/options/')) return Promise.resolve({ data: { contracts: [{ id: 17, label: 'Contrato base' }] } });
    if (url.includes('/hosting/')) return Promise.resolve({ data: { overview: { subscription: { associated: false, payments: [] } } } });
    throw new Error(`Unexpected request: ${url}`);
  });
}

function mountContext(props = {}) {
  return mount(CollectionAccountProjectContext, {
    props: { projectId: 7, modelValue: {}, ...props },
    global: {
      stubs: {
        BillingContextFields: { props: ['modelValue', 'options', 'payments'], template: '<div />' },
        NuxtLink: { template: '<a><slot /></a>' },
        BaseFormField: { template: '<div><slot /></div>' },
        BaseSelect: {
          props: ['modelValue', 'options', 'placeholder'],
          emits: ['update:modelValue'],
          template: `<select v-bind="$attrs" :value="modelValue" @change="$emit('update:modelValue', $event.target.value)">
            <option v-if="placeholder" value="">{{ placeholder }}</option>
            <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>`,
        },
        BaseControlGate: {
          props: ['reasons'],
          template: '<div><slot :blocked="reasons.length > 0" described-by="billing-link-gate-reason" /></div>',
        },
        BaseButton: {
          props: ['disabled', 'loading'],
          emits: ['click'],
          template: '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  });
}

describe('CollectionAccountProjectContext', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockProjectContextRequests();
  });

  it('explains that the operator must choose contract or hosting', async () => {
    // Fails if a project charge reverts to the generic nature/link blocker.
    const wrapper = mountContext();
    await flushPromises();

    expect(wrapper.emitted('valid').at(-1)[0]).toBe(false);
    expect(wrapper.emitted('validation-message').at(-1)[0])
      .toBe('En «Cobro del proyecto», elige si cobras un contrato o el hosting.');
  });

  it('keeps reviewed links on an initial mount for the same project', async () => {
    // Fails if returning from preview clears the contract or hosting choice without changing project.
    const wrapper = mountContext({ modelValue: { billing_nature: 'contract', contract_id: 17 } });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(wrapper.emitted('valid').at(-1)[0]).toBe(true);
    expect(wrapper.emitted('validation-message').at(-1)[0]).toBe('');
  });

  it('recovers the project context after retrying a failed load', async () => {
    // Fails if a temporary context lookup failure cannot recover into the actionable contract/hosting prompt.
    get_request
      .mockRejectedValueOnce({ response: { data: { detail: 'No se pudo cargar el proyecto.' } } })
      .mockResolvedValueOnce({ data: { overview: { subscription: { associated: false, payments: [] } } } })
      .mockResolvedValueOnce({ data: { contracts: [{ id: 17, label: 'Contrato base' }] } })
      .mockResolvedValueOnce({ data: { overview: { subscription: { associated: false, payments: [] } } } });
    const wrapper = mountContext();
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toContain('No se pudo cargar el proyecto.');
    await wrapper.get('[role="alert"] button').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenCalledTimes(4);
    expect(wrapper.emitted('validation-message').at(-1)[0])
      .toBe('En «Cobro del proyecto», elige si cobras un contrato o el hosting.');
  });

  it('clears reviewed links after selecting another project', async () => {
    // Fails if a contract from project 7 survives after changing to project 8.
    const wrapper = mountContext({ modelValue: { billing_nature: 'contract', contract_id: 17 } });
    await flushPromises();
    await wrapper.setProps({ projectId: 8 });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual({});
  });

  // Falla si un contrato fuente sigue sin poder vincularse desde la cuenta en curso.
  it('selects the contract returned by a linked source', async () => {
    get_request.mockImplementation((url) => {
      if (url.includes('/hosting/')) {
        return Promise.resolve({ data: { overview: { subscription: { associated: false, payments: [] } } } });
      }
      return Promise.resolve({ data: {
        contracts: [],
        delivery_version: 4,
        contract_sources: [{
          source_type: 'document', id: 31, title: 'Contrato Litigio', origin_label: 'Documento del proyecto',
        }],
      } });
    });
    create_request.mockResolvedValue({ data: { id: 88 } });
    const wrapper = mountContext({
      modelValue: { billing_nature: 'contract', contract_id: null },
    });
    await flushPromises();

    await wrapper.get('[data-testid="billing-link-contract-open"]').trigger('click');
    await wrapper.get('[data-testid="billing-link-contract-source"]').setValue('document:31');
    await wrapper.get('[data-testid="billing-link-contract-submit"]').trigger('click');
    await flushPromises();

    expect(create_request).toHaveBeenCalledWith(
      'admin/billing-context/projects/7/contracts/link/',
      {
        source_type: 'document',
        source_id: 31,
        expected_version: 4,
        request_id: expect.stringMatching(/^billing-link-\d+-document:31$/),
      },
    );
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual({
      billing_nature: 'contract', contract_id: 88, amendment_id: null,
      project_hosting_id: null, hosting_payment_id: null,
    });
    expect(get_request).toHaveBeenCalledTimes(3);
  });

  // Falla si un rechazo de vínculo borra la selección que el operador estaba revisando.
  it('keeps the source form after a link rejection', async () => {
    get_request.mockImplementation((url) => {
      if (url.includes('/hosting/')) {
        return Promise.resolve({ data: { overview: { subscription: { associated: false, payments: [] } } } });
      }
      return Promise.resolve({ data: {
        contracts: [],
        delivery_version: 4,
        contract_sources: [{
          source_type: 'document', id: 31, title: 'Contrato Litigio', origin_label: 'Documento del proyecto',
        }],
      } });
    });
    create_request.mockRejectedValue({ response: { data: { detail: 'El documento ya cambió.' } } });
    const wrapper = mountContext({
      modelValue: { billing_nature: 'contract', contract_id: null },
    });
    await flushPromises();

    await wrapper.get('[data-testid="billing-link-contract-open"]').trigger('click');
    await wrapper.get('[data-testid="billing-link-contract-source"]').setValue('document:31');
    await wrapper.get('[data-testid="billing-link-contract-submit"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="billing-link-contract-error"]').text())
      .toBe('El documento ya cambió.');
    expect(wrapper.get('[data-testid="billing-link-contract-source"]').element.value)
      .toBe('document:31');
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });
});
