global.useLocalePath = () => (path) => path;
global.definePageMeta = jest.fn();

jest.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, path: '/panel/clients' }),
  useRouter: () => ({ replace: jest.fn() }),
}));

import { mount, flushPromises } from '@vue/test-utils';
import PanelClientsIndex from '../../pages/panel/clients/index.vue';

const mockStore = {
  clients: [],
  statusCounts: {},
  isLoading: false,
  isUpdating: false,
  fetchClients: jest.fn(),
  fetchStatusCounts: jest.fn(),
  fetchClient: jest.fn(),
  createClient: jest.fn(),
  deleteClient: jest.fn(),
};

jest.mock('../../stores/proposal_clients', () => ({
  useProposalClientsStore: () => mockStore,
}));

jest.mock('../../stores/proposals', () => ({
  useProposalStore: () => ({
    deleteProposal: jest.fn().mockResolvedValue({ success: true }),
  }),
}));

jest.mock('../../stores/diagnostics', () => ({
  useDiagnosticsStore: () => ({
    remove: jest.fn().mockResolvedValue({ success: true }),
  }),
}));

jest.mock('../../composables/usePanelRefresh', () => ({
  usePanelRefresh: jest.fn(),
}));

jest.mock('../../composables/useConfirmModal', () => ({
  useConfirmModal: () => ({
    confirmState: {
      open: false,
      title: '',
      message: '',
    confirmText: 'Confirmar',
    cancelText: 'Cancelar',
    variant: 'warning',
  },
    requestConfirm: jest.fn(),
    handleConfirmed: jest.fn(),
    handleCancelled: jest.fn(),
  }),
}));

function mountPage() {
  return mount(PanelClientsIndex, {
    global: {
      stubs: {
        Teleport: true,
        ConfirmModal: {
          template: '<div />',
        },
        NuxtLink: {
          template: '<a><slot /></a>',
        },
        BaseInput: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          inheritAttrs: false,
          template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        BaseButton: {
          inheritAttrs: false,
          template: '<button v-bind="$attrs"><slot /></button>',
        },
      },
    },
  });
}

const LONG_CLIENT = {
  id: 99,
  name: 'Levantamiento_Fase_4_Multi-Tenant_24082026',
  email: 'guia_apuntar_dominio_ux_26082026@example.com',
  company: 'Respuesta_Etapa_3_Inventario',
  is_email_placeholder: false,
  is_orphan: false,
  is_archived: false,
  total_proposals: 0,
  projects_count: 0,
  diagnostics_count: 0,
  incomes_count: 0,
  hostings_count: 0,
  active_projects_count: 0,
  accepted_count: 0,
};

describe('panel/clients index page', () => {
  beforeEach(() => {
    mockStore.clients = [];
    mockStore.statusCounts = {};
    mockStore.isLoading = false;
    mockStore.isUpdating = false;
    mockStore.fetchClients.mockReset().mockResolvedValue({ success: true, data: [] });
    mockStore.fetchStatusCounts.mockReset().mockResolvedValue({ success: true, data: {} });
    mockStore.fetchClient.mockReset().mockResolvedValue({ success: true, data: { proposals: [] } });
    mockStore.createClient.mockReset().mockResolvedValue({ success: true });
    mockStore.deleteClient.mockReset().mockResolvedValue({ success: true });
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const selectStatus = (wrapper, value) =>
    wrapper.findComponent({ name: 'BaseSegmented' }).vm.$emit('update:modelValue', value);

  it('contains an unbroken client name in the row header', async () => {
    mockStore.clients = [LONG_CLIENT];
    const wrapper = mountPage();
    await flushPromises();
    const name = wrapper.get('[data-testid="client-header-99"] p');

    expect(name.attributes('title')).toBe(LONG_CLIENT.name);
    expect(name.classes()).toEqual(expect.arrayContaining(['min-w-0', 'max-w-full']));
  });

  it('contains an unbroken document title in the expanded client list', async () => {
    mockStore.clients = [LONG_CLIENT];
    mockStore.fetchClient.mockResolvedValueOnce({
      success: true,
      data: {
        proposals: [],
        projects: [],
        diagnostics: [],
        hostings: [],
        incomes: [],
        documents_total: 1,
        documents: [{
          id: 501,
          title: 'guia_apuntar_dominio_ux_26082026',
          project_name: 'Respuesta_Etapa_3_Inventario',
          status: 'draft',
          created_at: '2026-08-26T00:00:00Z',
        }],
      },
    });
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.get('[data-testid="client-header-99"]').trigger('click');
    await flushPromises();
    const title = wrapper.get('[data-testid="client-document-row-501"] a');

    expect(title.attributes('title')).toBe('guia_apuntar_dominio_ux_26082026');
    expect(title.classes()).toContain('[overflow-wrap:anywhere]');
  });

  it('loads orphan clients when the Huérfanos status is selected', async () => {
    const wrapper = mountPage();
    await flushPromises();

    selectStatus(wrapper, 'orphans');
    await flushPromises();

    // `limit` asks for the endpoint's hard cap: the page does not paginate
    // server-side and the subfilters (and their counts) run over whatever was
    // loaded, so a 100-row window would make them lie.
    expect(mockStore.fetchClients).toHaveBeenNthCalledWith(1, { search: '', orphans: null, archived: false, limit: 500, silent: false });
    expect(mockStore.fetchClients).toHaveBeenNthCalledWith(2, { search: '', orphans: true, archived: false, limit: 500, silent: false });
  });

  it('keeps the status out of the module row it used to compete with', async () => {
    const wrapper = mountPage();
    await flushPromises();

    expect(wrapper.find('[data-testid="clients-module-hosting"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="clients-tab-orphans"]').exists()).toBe(false);
  });

  it('labels each status with its own match count', async () => {
    mockStore.statusCounts = { all: 12000, active: 9999, orphans: 9999, archived: 0 };
    const wrapper = mountPage();
    await flushPromises();

    const options = wrapper.findComponent({ name: 'BaseSegmented' }).props('options');
    expect(options.map((o) => o.label)).toEqual([
      'Todos (12000)', 'Activos (9999)', 'Huérfanos (9999)', 'Archivados (0)',
    ]);
  });

  // Fails if an active client's row control reverts to the former "Desactivar" label.
  it('announces Archivar for an active client row control', async () => {
    mockStore.clients = [LONG_CLIENT];
    const wrapper = mountPage();
    await flushPromises();

    const control = wrapper.get('button[data-testid="client-toggle-archived-99"]');

    expect(control.attributes('aria-label')).toBe('Archivar cliente');
  });

  // Fails if an archived client's row control reverts to the former "Activar" label.
  it('announces Desarchivar for an archived client row control', async () => {
    mockStore.clients = [{ ...LONG_CLIENT, is_archived: true }];
    const wrapper = mountPage();
    await flushPromises();

    const control = wrapper.get('button[data-testid="client-toggle-archived-99"]');

    expect(control.attributes('aria-label')).toBe('Desarchivar cliente');
  });

  it('asks for the status counts with the same search as the list', async () => {
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.get('[data-testid="clients-search-input"]').setValue('acme');
    jest.advanceTimersByTime(250);
    await flushPromises();

    expect(mockStore.fetchStatusCounts).toHaveBeenLastCalledWith({ search: 'acme' });
  });

  it('submits the create modal payload trimmed and refreshes the list', async () => {
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.get('[data-testid="clients-new-button"]').trigger('click');
    await wrapper.get('[data-testid="clients-new-name"]').setValue('  Laura Gómez  ');
    await wrapper.get('[data-testid="clients-new-email"]').setValue('  laura@example.com  ');
    await wrapper.get('[data-testid="clients-new-company"]').setValue('  LauraCo  ');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(mockStore.createClient).toHaveBeenCalledWith({
      name: 'Laura Gómez',
      email: 'laura@example.com',
      phone: '',
      company: 'LauraCo',
      nit: '',
      billing_code: '',
    });
    expect(mockStore.fetchClients).toHaveBeenCalledTimes(2);
  });

  it('creates a client with its billing identity in one step', async () => {
    // The whole point of the parity fix: NIT and código are on the create form,
    // so a client no longer has to be created and then edited to be complete.
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.get('[data-testid="clients-new-button"]').trigger('click');
    await wrapper.get('[data-testid="clients-new-name"]').setValue('G&M');
    await wrapper.get('[data-testid="clients-new-nit"]').setValue('901234567-1');
    await wrapper.get('[data-testid="clients-new-billing-code"]').setValue('  g&m  ');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(mockStore.createClient).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'G&M',
        nit: '901234567-1',
        // Normalized the same way the edit modal always did.
        billing_code: 'G&M',
      }),
    );
  });

  it('creates a client from the name alone', async () => {
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.get('[data-testid="clients-new-button"]').trigger('click');
    await wrapper.get('[data-testid="clients-new-name"]').setValue('Solo Nombre');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(mockStore.createClient).toHaveBeenCalledWith({
      name: 'Solo Nombre',
      email: '',
      phone: '',
      company: '',
      nit: '',
      billing_code: '',
    });
  });

  it('surfaces the backend billing-code error on the create modal', async () => {
    // It used to read only `message`, so an `invalid_billing_code` answer left
    // the operator with the generic fallback and no idea what was wrong.
    mockStore.createClient.mockResolvedValueOnce({
      success: false,
      errors: { error: 'invalid_billing_code', message: 'El código debe tener entre 2 y 12 caracteres.' },
    });
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.get('[data-testid="clients-new-button"]').trigger('click');
    await wrapper.get('[data-testid="clients-new-name"]').setValue('G&M');
    await wrapper.get('[data-testid="clients-new-billing-code"]').setValue('G/M');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(wrapper.text()).toContain('El código debe tener entre 2 y 12 caracteres.');
  });

  it('debounces search before refetching clients', async () => {
    const wrapper = mountPage();
    await flushPromises();

    await wrapper.get('[data-testid="clients-search-input"]').setValue('ana');
    expect(mockStore.fetchClients).toHaveBeenCalledTimes(1);

    jest.advanceTimersByTime(250);
    await flushPromises();

    expect(mockStore.fetchClients).toHaveBeenNthCalledWith(2, { search: 'ana', orphans: null, archived: false, limit: 500, silent: false });
  });
});
