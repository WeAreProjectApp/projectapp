import { mount, flushPromises } from '@vue/test-utils';
import { reactive } from 'vue';
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

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

function linkOptions(id = 31) {
  return { contracts: [], delivery_version: 4, contract_sources: [
    { source_type: 'document', id, title: 'Contrato Litigio', origin_label: 'Documento del proyecto' },
  ] };
}

function sourceRequests() {
  get_request.mockImplementation(url => Promise.resolve({ data: url.includes('/options/')
    ? linkOptions() : { overview: { subscription: { associated: false } } } }));
}

async function startLink(wrapper) {
  await flushPromises();
  await wrapper.get('[data-testid="billing-link-contract-open"]').trigger('click');
  await wrapper.get('[data-testid="billing-link-contract-source"]').setValue('Litigio');
  await wrapper.get('[data-testid="billing-link-contract-source"]').trigger('keydown', { key: 'Enter' });
  await wrapper.get('[data-testid="billing-link-contract-submit"]').trigger('click');
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
    await wrapper.get('[data-testid="billing-link-contract-source"]').setValue('Litigio');
    await wrapper.get('[data-testid="billing-link-contract-source"]').trigger('keydown', { key: 'Enter' });
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
    await wrapper.get('[data-testid="billing-link-contract-source"]').setValue('Litigio');
    await wrapper.get('[data-testid="billing-link-contract-source"]').trigger('keydown', { key: 'Enter' });
    await wrapper.get('[data-testid="billing-link-contract-submit"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="billing-link-contract-error"]').text())
      .toBe('El documento ya cambió.');
    expect(wrapper.get('[data-testid="billing-link-contract-source"]').element.value)
      .toBe('Contrato Litigio');
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });

  it('ignores project A options arriving after project B has loaded', async () => {
    const late = deferred();
    sourceRequests();
    get_request.mockImplementationOnce(() => late.promise);
    const wrapper = mountContext({ modelValue: { billing_nature: 'contract' } });
    await wrapper.setProps({ projectId: 8 });
    await flushPromises();
    late.resolve({ data: linkOptions(99) });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toEqual([[{}]]);
    create_request.mockResolvedValue({ data: { id: 88 } });
    await startLink(wrapper);
    expect(create_request).toHaveBeenCalledWith(
      'admin/billing-context/projects/8/contracts/link/', expect.objectContaining({ source_id: 31 }),
    );
  });

  it('ignores a project A link completing after switching to project B', async () => {
    const late = deferred();
    sourceRequests();
    create_request.mockReturnValue(late.promise);
    const wrapper = mountContext({ modelValue: { billing_nature: 'contract' } });
    await startLink(wrapper);
    await wrapper.setProps({ projectId: 8 });
    await flushPromises();
    late.resolve({ data: { id: 88 } });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toEqual([[{}]]);
    expect(get_request).toHaveBeenCalledTimes(4);
  });

  it('does not overwrite the later pending choice when the link POST completes', async () => {
    const late = deferred();
    sourceRequests();
    create_request.mockReturnValue(late.promise);
    const wrapper = mountContext({ modelValue: { billing_nature: 'contract' } });
    await startLink(wrapper);
    await wrapper.setProps({ modelValue: { billing_nature: 'contract', document_pending: true } });
    late.resolve({ data: { id: 88 } });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(get_request).toHaveBeenCalledTimes(2);
  });

  it('does not overwrite the pending choice made during the post-link refresh', async () => {
    const late = deferred();
    sourceRequests();
    create_request.mockResolvedValue({ data: { id: 88 } });
    const wrapper = mountContext({ modelValue: { billing_nature: 'contract' } });
    await flushPromises();
    get_request.mockReturnValueOnce(late.promise);
    await startLink(wrapper);
    await flushPromises();
    await wrapper.setProps({ modelValue: { billing_nature: 'contract', document_pending: true } });
    late.resolve({ data: linkOptions() });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(get_request).toHaveBeenCalledTimes(3);
  });

  it('invalidates an earlier link even when the operator toggles pending back off', async () => {
    const late = deferred();
    sourceRequests();
    create_request.mockReturnValue(late.promise);
    const wrapper = mountContext({ modelValue: { billing_nature: 'contract' } });
    await startLink(wrapper);
    await wrapper.setProps({ modelValue: { billing_nature: 'contract', document_pending: true } });
    await wrapper.setProps({ modelValue: { billing_nature: 'contract', document_pending: false } });
    late.resolve({ data: { id: 88 } });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });

  it('detects an in-place change of the billing context during a link', async () => {
    const late = deferred();
    sourceRequests();
    create_request.mockReturnValue(late.promise);
    const modelValue = reactive({ billing_nature: 'contract', document_pending: false });
    const wrapper = mountContext({ modelValue });
    await startLink(wrapper);
    modelValue.document_pending = true;
    late.resolve({ data: { id: 88 } });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
  });

  it('discards a link response after the context form is unmounted', async () => {
    const late = deferred();
    sourceRequests();
    create_request.mockReturnValue(late.promise);
    const wrapper = mountContext({ modelValue: { billing_nature: 'contract' } });
    await startLink(wrapper);
    wrapper.unmount();
    late.resolve({ data: { id: 88 } });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(get_request).toHaveBeenCalledTimes(2);
  });

  it('keeps the reviewed context while refreshing sources for the same project', async () => {
    sourceRequests();
    const modelValue = { billing_nature: 'contract', contract_id: 17 };
    get_request.mockResolvedValue({ data: { ...linkOptions(), contracts: [{ id: 17, title: 'Contrato revisado' }] } });
    const wrapper = mountContext({ modelValue });
    await flushPromises();
    await wrapper.get('[data-testid="billing-link-contract-open"]').trigger('click');
    await wrapper.get('[data-testid="billing-link-contract-source"]').setValue('Litigio');
    await wrapper.findAll('button').find(button => button.text() === 'Actualizar opciones').trigger('click');
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    expect(wrapper.emitted('valid').at(-1)).toEqual([true]);
  });

  it('discards a post-link refresh after switching to another project', async () => {
    const late = deferred();
    sourceRequests();
    create_request.mockResolvedValue({ data: { id: 88 } });
    const wrapper = mountContext({ modelValue: { billing_nature: 'contract' } });
    await flushPromises();
    get_request.mockReturnValueOnce(late.promise);
    await startLink(wrapper);
    await wrapper.setProps({ projectId: 8 });
    await flushPromises();

    late.resolve({ data: { ...linkOptions(99), contracts: [{ id: 88, title: 'Contrato A' }] } });
    await flushPromises();

    expect(wrapper.emitted('update:modelValue')).toEqual([[{}]]);
    expect(wrapper.emitted('valid').at(-1)).toEqual([false]);
    await startLink(wrapper);
    expect(create_request).toHaveBeenLastCalledWith(
      'admin/billing-context/projects/8/contracts/link/', expect.objectContaining({ source_id: 31 }),
    );
  });
});
