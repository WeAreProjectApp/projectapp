import { mount, flushPromises } from '@vue/test-utils';
import BulkAssignModal from '../../../components/accounting/BulkAssignModal.vue';

const mockCreateClient = jest.fn();

jest.mock('../../../stores/proposal_clients', () => ({
  useProposalClientsStore: () => ({
    createClient: (...args) => mockCreateClient(...args),
  }),
}));

/**
 * The picker, the live plan and the gated confirm — everything that used to
 * sit inline in the bulk bar before the actions menu moved it here. A mass
 * edit has to show its scope before it runs, and no confirm may be disabled
 * without the reason on screen.
 */

const ClientAutocompleteStub = {
  name: 'ClientAutocomplete',
  props: [
    'active',
    'initialLabel',
    'modelValue',
    'placeholder',
    'presentation',
    'showLinkedHint',
    'sortStorageKey',
    'testId',
  ],
  emits: ['update:modelValue', 'select', 'create-new'],
  template: `
    <div data-testid="client-autocomplete-stub">
      <button
        type="button"
        data-testid="client-autocomplete-create-trigger"
        @click="$emit('create-new', 'Nueva Cliente')"
      >Crear</button>
    </div>
  `,
};

const ProjectCatalogSelectStub = {
  name: 'ProjectCatalogSelect',
  props: ['modelValue', 'testId', 'placeholder'],
  emits: ['update:modelValue', 'select'],
  template: '<div data-testid="project-catalog-select-stub" />',
};

const ENTITY = { singular: 'hosting', plural: 'hostings' };

const ROWS = [
  { id: 1, client: null, project: null, client_name: 'Kore - Marca', domain_url: 'kore.com.co' },
  { id: 2, client: null, project: null, client_name: 'Huella - Marca', domain_url: 'tuhuella.co' },
  { id: 3, client: 7, project: null, client_display_name: 'Kore SAS', domain_url: 'a.com' },
  {
    id: 4,
    client: 7,
    project: 41,
    project_name: 'Vieja Web',
    client_display_name: 'Kore SAS',
    domain_url: 'b.com',
  },
];

function mountModal(props = {}) {
  return mount(BulkAssignModal, {
    props: {
      open: true,
      target: 'client',
      rows: ROWS,
      selectedIds: [1, 2],
      entity: ENTITY,
      testidPrefix: 'hostings',
      recordLabel: (row) => row.domain_url,
      ...props,
    },
    global: {
      stubs: {
        ClientAutocomplete: ClientAutocompleteStub,
        ProjectCatalogSelect: ProjectCatalogSelectStub,
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        BaseModal: {
          name: 'BaseModal',
          props: ['modelValue', 'kind', 'size', 'titleId', 'initialFocus'],
          emits: ['update:modelValue', 'close'],
          template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
        },
      },
    },
  });
}

/** Pick a client the way ClientAutocomplete does: id via v-model, then `select`. */
async function pickClient(wrapper, client = { id: 5, name: 'Ana Pérez' }) {
  const picker = wrapper.findComponent(ClientAutocompleteStub);
  await picker.vm.$emit('update:modelValue', client.id);
  await picker.vm.$emit('select', client);
  await flushPromises();
}

const PROJECT = {
  id: 40,
  name: 'Kore Web',
  status: 'active',
  status_label: 'Activo',
  client: { profile_id: 7, name: 'Kore SAS' },
};

/** Pick a project the way ProjectCatalogSelect does: id, then the full row. */
async function pickProject(wrapper, project = PROJECT) {
  const picker = wrapper.findComponent(ProjectCatalogSelectStub);
  await picker.vm.$emit('update:modelValue', project.id);
  await picker.vm.$emit('select', project);
  await flushPromises();
}

const hint = (w) => w.find('[data-testid="hostings-bulk-hint"]').text();
const confirmButton = (w) => w.find('[data-testid="hostings-bulk-assign"]');
const confirmProject = (w) => w.find('[data-testid="hostings-bulk-assign-project"]');

beforeEach(() => {
  mockCreateClient.mockReset();
});

describe('BulkAssignModal — nothing is confirmable without a reason on screen', () => {
  it('renders client assignment as a permanent ordered catalog', () => {
    const wrapper = mountModal();
    const picker = wrapper.findComponent(ClientAutocompleteStub);

    expect(picker.props('presentation')).toBe('catalog');
    expect(picker.props('active')).toBe(true);
    expect(picker.props('sortStorageKey')).toBe('panel.accounting.bulk-client-name-order');
    expect(wrapper.findComponent({ name: 'BaseModal' }).props('kind')).toBe('form-wide');
  });

  it('keeps Asignar disabled with the reason visible until a client is picked', () => {
    const wrapper = mountModal();

    expect(confirmButton(wrapper).element.disabled).toBe(true);
    expect(hint(wrapper)).toBe('Elige un cliente para poder asignar.');
  });

  it('blocks Asignar and says why when everything already has that client', async () => {
    const wrapper = mountModal({ selectedIds: [3, 4] });
    await pickClient(wrapper, { id: 7, name: 'Kore SAS' });

    expect(confirmButton(wrapper).element.disabled).toBe(true);
    expect(hint(wrapper)).toBe('Todo lo seleccionado ya tiene a Kore SAS.');
  });

  it('confirms the linked client in its own line once one is picked', async () => {
    const wrapper = mountModal();
    await pickClient(wrapper);

    expect(hint(wrapper)).toBe('Cliente enlazado: Ana Pérez (#5)');
    expect(confirmButton(wrapper).element.disabled).toBe(false);
  });

  it('goes back to asking for a client when the picker is cleared', async () => {
    const wrapper = mountModal();
    await pickClient(wrapper);
    expect(hint(wrapper)).toContain('Cliente enlazado');

    await wrapper.findComponent(ClientAutocompleteStub).vm.$emit('update:modelValue', null);
    await flushPromises();

    expect(hint(wrapper)).toBe('Elige un cliente para poder asignar.');
  });
});

describe('BulkAssignModal — the scope is visible before it runs', () => {
  it('names every selected record before a destination is chosen', () => {
    const wrapper = mountModal();

    const review = wrapper.get('[data-testid="hostings-bulk-selection-review"]');
    expect(review.text()).toContain('Registros seleccionados (2)');
    expect(review.text()).toContain('kore.com.co');
    expect(review.text()).toContain('tuhuella.co');
  });

  it('breaks a mixed selection into its two halves instead of one flat count', async () => {
    const wrapper = mountModal({ selectedIds: [1, 2, 3] });
    await pickClient(wrapper);

    expect(wrapper.find('[data-testid="client-bulk-summary-assign"]').text())
      .toBe('2 sin cliente pasan a Ana Pérez');
    expect(wrapper.find('[data-testid="client-bulk-summary-reassign"]').text())
      .toBe('1 cambia de cliente a Ana Pérez');
  });

  it('names every affected record and writes nothing until confirmed', async () => {
    const wrapper = mountModal({ selectedIds: [1, 2, 3] });
    await pickClient(wrapper);

    // A mass edit has to show its scope, not just its size.
    const list = wrapper.find('[data-testid="client-bulk-summary-list"]').text();
    expect(list).toContain('kore.com.co');
    expect(list).toContain('tuhuella.co');
    expect(wrapper.emitted('submit') ?? []).toHaveLength(0);

    await confirmButton(wrapper).trigger('click');

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      ids: [1, 2, 3],
      client: 5,
      mode: 'assign',
    });
  });

  it('leaves the rows already on the target out of the payload', async () => {
    const wrapper = mountModal({ selectedIds: [1, 3] });
    await pickClient(wrapper, { id: 7, name: 'Kore SAS' });

    await confirmButton(wrapper).trigger('click');

    expect(wrapper.emitted('submit')[0][0].ids).toEqual([1]);
  });

  it('closes itself after submitting, so the page can clear the selection', async () => {
    const wrapper = mountModal();
    await pickClient(wrapper);

    await confirmButton(wrapper).trigger('click');

    expect(wrapper.emitted('submit')).toHaveLength(1);
    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('emits close and never submit when cancelled', async () => {
    const wrapper = mountModal();
    await pickClient(wrapper);

    await wrapper.find('[data-testid="hostings-bulk-assign-cancel"]').trigger('click');

    expect(wrapper.emitted('close')).toHaveLength(1);
    expect(wrapper.emitted('submit') ?? []).toHaveLength(0);
  });
});

describe('BulkAssignModal — client creation from an empty search', () => {
  function expectDescribedError(wrapper, testId, message) {
    const control = wrapper.get(`[data-testid="${testId}"]`);
    const errorId = control.attributes('aria-describedby');
    const error = wrapper.findAll('[role="alert"]')
      .find((node) => node.attributes('id') === errorId);
    expect(control.attributes('aria-invalid')).toBe('true');
    expect(error.exists()).toBe(true);
    expect(error.text()).toBe(message);
  }

  // Falla si el botón de alta rápida vuelve a bloquearse antes de validar.
  it('keeps the inline client create action enabled', async () => {
    const wrapper = mountModal();
    await wrapper.findComponent(ClientAutocompleteStub).vm.$emit('create-new', '');
    await flushPromises();

    const save = wrapper.get('[data-testid="hostings-bulk-inline-client-save"]');
    expect(save.element.disabled).toBe(false);
  });

  // Falla si el alta rápida intenta crear un perfil vacío o no describe el nombre incompleto.
  it('rejects an empty bulk inline client name', async () => {
    const wrapper = mountModal();
    await wrapper.findComponent(ClientAutocompleteStub).vm.$emit('create-new', '');
    await flushPromises();

    const save = wrapper.get('[data-testid="hostings-bulk-inline-client-save"]');
    await save.trigger('click');

    expect(mockCreateClient).toHaveBeenCalledTimes(0);
    expectDescribedError(wrapper, 'hostings-bulk-inline-client-name', 'Escribe el nombre del cliente.');
  });

  it('selects the client created inside the modal', async () => {
    mockCreateClient.mockResolvedValueOnce({
      success: true,
      data: { id: 88, name: 'Nueva Cliente' },
    });
    const wrapper = mountModal();

    await wrapper.get('[data-testid="client-autocomplete-create-trigger"]').trigger('click');
    await wrapper.get('[data-testid="hostings-bulk-inline-client-save"]').trigger('click');
    await flushPromises();

    expect(mockCreateClient).toHaveBeenCalledWith({
      name: 'Nueva Cliente',
      email: '',
      phone: '',
      company: '',
      nit: '',
      cedula: '',
      address: '',
      billing_code: '',
    });
    expect(hint(wrapper)).toBe('Cliente enlazado: Nueva Cliente (#88)');
  });

  it('shows the creation error inside the modal', async () => {
    mockCreateClient.mockResolvedValueOnce({
      success: false,
      errors: { email: ['Ese correo ya existe.'] },
    });
    const wrapper = mountModal();

    await wrapper.get('[data-testid="client-autocomplete-create-trigger"]').trigger('click');
    await wrapper.get('[data-testid="hostings-bulk-inline-client-save"]').trigger('click');
    await flushPromises();

    const emailControl = wrapper.get('[data-testid="hostings-bulk-inline-client-email"]');
    const emailError = wrapper.get(`#${emailControl.attributes('aria-describedby')}`);
    expect(emailControl.attributes('aria-invalid')).toBe('true');
    expect(emailError.attributes('role')).toBe('alert');
    expect(emailError.text()).toBe('Ese correo ya existe.');
  });
});

describe('BulkAssignModal — the Proyecto target', () => {
  it('swaps the picker for the project one without touching the rest', () => {
    const wrapper = mountModal({ target: 'project' });

    expect(wrapper.findComponent(ProjectCatalogSelectStub).exists()).toBe(true);
    expect(wrapper.findComponent(ClientAutocompleteStub).exists()).toBe(false);
    expect(hint(wrapper)).toBe('Elige un proyecto para poder asignar.');
  });

  it('confirms against the plan and leaves the foreign-client rows out', async () => {
    const wrapper = mountModal({ target: 'project', selectedIds: [1, 3, 4] });
    await pickProject(wrapper);

    expect(wrapper.find('[data-testid="project-bulk-summary-blocked"]').text())
      .toContain('kore.com.co');
    await confirmProject(wrapper).trigger('click');

    expect(wrapper.emitted('submit')[0][0]).toMatchObject({
      ids: [3, 4],
      project: 40,
      mode: 'assign',
    });
  });

  it('blocks with the ownership reason when nothing can change', async () => {
    const wrapper = mountModal({ target: 'project', selectedIds: [1, 2] });
    await pickProject(wrapper);

    expect(confirmProject(wrapper).element.disabled).toBe(true);
    expect(hint(wrapper)).toContain('La selección pertenece a otro cliente');
  });
});

describe('BulkAssignModal — each opening starts clean', () => {
  it('forgets the client picked the previous time it was opened', async () => {
    const wrapper = mountModal();
    await pickClient(wrapper);
    expect(hint(wrapper)).toContain('Ana Pérez');

    await wrapper.setProps({ open: false });
    await wrapper.setProps({ open: true });

    expect(hint(wrapper)).toBe('Elige un cliente para poder asignar.');
  });

  it('acts on the selection frozen at open, not on a later one', async () => {
    const wrapper = mountModal({ selectedIds: [1, 2] });
    await pickClient(wrapper);

    // The page clears the selection right after a successful submit; reading
    // it live would blank the plan while the dialog is still fading out.
    await wrapper.setProps({ selectedIds: [] });

    expect(wrapper.find('[data-testid="client-bulk-summary-list"]').text())
      .toContain('kore.com.co');
    await confirmButton(wrapper).trigger('click');
    expect(wrapper.emitted('submit')[0][0].ids).toEqual([1, 2]);
  });
});
