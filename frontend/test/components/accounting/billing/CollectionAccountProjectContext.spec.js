import { mount, flushPromises } from '@vue/test-utils';
import CollectionAccountProjectContext from '../../../../components/accounting/billing/CollectionAccountProjectContext.vue';

jest.mock('../../../../stores/services/request_http', () => ({ get_request: jest.fn() }));

const { get_request } = require('../../../../stores/services/request_http');

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
});
