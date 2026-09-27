import { flushPromises, mount } from '@vue/test-utils';
import StateCatalogManager from '../../components/panel/states/StateCatalogManager.vue';
import BaseControlGate from '../../components/base/BaseControlGate.vue';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseFormRow from '../../components/base/BaseFormRow.vue';
import BaseFormRowAction from '../../components/base/BaseFormRowAction.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseTextarea from '../../components/base/BaseTextarea.vue';

const notify = {
  error: jest.fn(),
  success: jest.fn(),
};

global.usePanelNotify = () => notify;
global.useLocalePath = () => (path) => path;

const mockConfirmModal = {
  confirmState: {
    open: false,
    title: '',
    message: '',
    confirmText: '',
    cancelText: '',
    variant: 'warning',
  },
  requestConfirm: jest.fn(async () => false),
  handleConfirmed: jest.fn(),
  handleCancelled: jest.fn(),
};

jest.mock('../../composables/useConfirmModal', () => ({
  useConfirmModal: () => mockConfirmModal,
}));

const GROUP = {
  id: 4,
  name: 'Ciclo del proyecto',
  selection_mode: 'exclusive',
  is_active: true,
};

const STATES = [
  {
    id: 2,
    name: 'Activo',
    description: 'Proyecto entregado y operando.',
    color: 'emerald',
    group: 4,
    order: 1,
    operational_effect: 'operating',
    system_key: 'active',
    is_active: true,
    merged_into: null,
    incompatibility_ids: [],
    active_project_count: 1,
    historical_episode_count: 3,
  },
  {
    id: 8,
    name: 'En garantía',
    description: 'Acompañamiento posterior a la entrega.',
    color: 'blue',
    group: 4,
    order: 2,
    operational_effect: 'operating',
    system_key: '',
    is_active: true,
    merged_into: null,
    incompatibility_ids: [],
    active_project_count: 0,
    historical_episode_count: 0,
  },
];

const OPERATIONAL_EFFECTS = [
  { value: 'development', label: 'En construcción' },
  { value: 'operating', label: 'Operando y cobrable' },
];

function makeStore(overrides = {}) {
  return {
    states: STATES.map((state) => ({ ...state })),
    groups: [{ ...GROUP }],
    get activeStates() {
      return this.states.filter((state) => state.is_active && !state.merged_into);
    },
    fetchCatalog: jest.fn(async () => ({ success: true })),
    createState: jest.fn(async () => ({ success: true })),
    updateState: jest.fn(async () => ({ success: true })),
    mergeState: jest.fn(async () => ({ success: true })),
    retireState: jest.fn(async () => ({ success: true })),
    createGroup: jest.fn(async () => ({ success: true })),
    ...overrides,
  };
}

// Document states carry neither description nor operational effect.
function documentStates() {
  return [
    {
      id: 21,
      name: 'Borrador',
      color: 'gray',
      group: 4,
      order: 1,
      system_key: 'draft',
      is_active: true,
      merged_into: null,
      incompatibility_ids: [],
      active_project_count: 2,
      historical_episode_count: 4,
    },
    {
      id: 22,
      name: 'Urgente',
      color: 'red',
      group: 4,
      order: 2,
      system_key: '',
      is_active: true,
      merged_into: null,
      incompatibility_ids: [],
      active_project_count: 0,
      historical_episode_count: 1,
    },
  ];
}

function mountManager({
  store = makeStore(),
  projectCatalog = true,
  manageGroups = false,
} = {}) {
  return mount(StateCatalogManager, {
    props: {
      stateStore: store,
      title: projectCatalog ? 'Estados de proyectos' : 'Estados de documentos',
      description: 'Administra el catálogo.',
      backTo: '/panel/projects',
      backLabel: 'Volver',
      activeCountField: 'active_project_count',
      activeCountLabel: 'proyectos',
      manageGroups,
      operationalEffects: projectCatalog ? OPERATIONAL_EFFECTS : [],
    },
    global: {
      components: {
        BaseFormField,
        BaseFormRow,
        BaseFormRowAction,
        BaseInput,
        BaseTextarea,
      },
      stubs: {
        BaseActionIcon: true,
        BaseBadge: { template: '<span><slot /></span>' },
        ConfirmModal: true,
        NuxtLink: { template: '<a><slot /></a>' },
        ProjectStateHelpBadge: true,
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
      },
    },
  });
}

describe('StateCatalogManager project field validation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('places missing creation requirements below their fields after submit', async () => {
    const store = makeStore();
    const wrapper = mountManager({ store });
    await flushPromises();

    expect(wrapper.findAll('[role="alert"]')).toHaveLength(0);
    expect(wrapper.get('[data-testid="catalog-create-state"]').attributes('disabled'))
      .toBeUndefined();

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.findAll('[role="alert"]').map((alert) => alert.text())).toEqual([
      'Escribe el nombre del estado.',
      'Explica qué significa el estado.',
    ]);
    expect(wrapper.get('[data-testid="catalog-new-state-name"]').attributes('aria-invalid'))
      .toBe('true');
    expect(wrapper.get('[data-testid="catalog-new-state-description"]').attributes('aria-invalid'))
      .toBe('true');
    expect(wrapper.find('form').findAll('li')).toHaveLength(0);
    expect(store.createState).not.toHaveBeenCalled();
  });

  it('renders a serializer rejection below its editable field', async () => {
    const store = makeStore({
      createState: jest.fn(async () => ({
        success: false,
        message: 'Ya existe un estado con ese nombre.',
        fieldErrors: { name: 'Ya existe un estado con ese nombre.' },
      })),
    });
    const wrapper = mountManager({ store });
    await flushPromises();

    await wrapper.get('[data-testid="catalog-new-state-name"]').setValue('Activo');
    await wrapper.get('[data-testid="catalog-new-state-description"]')
      .setValue('Otro nombre para el mismo estado.');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text())
      .toBe('Ya existe un estado con ese nombre.');
    expect(wrapper.get('[data-testid="catalog-new-state-name"]').element.value)
      .toBe('Activo');
    expect(notify.error).not.toHaveBeenCalled();

    await wrapper.get('[data-testid="catalog-new-state-name"]').setValue('Activo alterno');
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
  });

  it('places missing edit requirements inside the edited state', async () => {
    const store = makeStore();
    const wrapper = mountManager({ store });
    await flushPromises();
    const row = wrapper.get('[data-testid="catalog-state-8"]');

    await row.get('[aria-label="Nombre del estado"]').setValue('');
    await row.get('[data-testid="catalog-state-description-8"]').setValue('');
    await row.get('[data-testid="catalog-save-state-8"]').trigger('click');
    await flushPromises();

    expect(row.findAll('[role="alert"]').map((alert) => alert.text())).toEqual([
      'Escribe el nombre del estado.',
      'Explica qué significa el estado.',
    ]);
    expect(store.updateState).not.toHaveBeenCalled();
  });

  it('places a missing merge target below its selector after the action', async () => {
    const store = makeStore();
    const wrapper = mountManager({ store });
    await flushPromises();
    const row = wrapper.get('[data-testid="catalog-state-8"]');
    const mergeButton = row.get('[data-testid="catalog-merge-state-8"]');

    expect(mergeButton.attributes('disabled')).toBeUndefined();
    await mergeButton.trigger('click');
    await flushPromises();

    expect(row.get('[role="alert"]').text()).toBe('Elige el estado de destino.');
    expect(store.mergeState).not.toHaveBeenCalled();

    await row.get('[aria-label="Destino para fusionar En garantía"]').setValue('2');
    expect(row.find('[role="alert"]').exists()).toBe(false);
  });

  it('keeps a seed merge restriction in accessible help', async () => {
    const wrapper = mountManager();
    await flushPromises();
    const row = wrapper.get('[data-testid="catalog-state-2"]');
    const gate = row.findComponent(BaseControlGate);

    expect(gate.props('visible')).toBe(false);
    expect(gate.props('reasons')).toEqual([
      'Los estados semilla del sistema no se pueden fusionar.',
    ]);
    expect(row.get('[data-testid="catalog-merge-state-2"]').attributes('disabled'))
      .toBeDefined();
  });

});

describe('StateCatalogManager document field validation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('places a missing state name below its field after submit', async () => {
    const store = makeStore({ states: documentStates() });
    const wrapper = mountManager({ store, projectCatalog: false });
    await flushPromises();
    const form = wrapper.find('form');

    expect(wrapper.get('[data-testid="catalog-create-state"]').attributes('disabled'))
      .toBeUndefined();
    expect(form.text()).not.toContain('Escribe el nombre del estado.');

    await form.trigger('submit');
    await flushPromises();

    expect(form.findAll('[role="alert"]').map((alert) => alert.text()))
      .toEqual(['Escribe el nombre del estado.']);
    expect(wrapper.get('[data-testid="catalog-new-state-name"]').attributes('aria-invalid'))
      .toBe('true');
    expect(store.createState).not.toHaveBeenCalled();
  });

  it('creates a document state without asking for project-only fields', async () => {
    const store = makeStore({ states: documentStates() });
    const wrapper = mountManager({ store, projectCatalog: false });
    await flushPromises();

    await wrapper.get('[data-testid="catalog-new-state-name"]').setValue('Esperando cliente');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(store.createState).toHaveBeenCalledTimes(1);
    const payload = store.createState.mock.calls[0][0];
    expect(payload).toEqual(expect.objectContaining({ name: 'Esperando cliente', group: 4 }));
    expect(payload).not.toHaveProperty('operational_effect');
    expect(wrapper.findAll('[role="alert"]')).toHaveLength(0);
  });

  it('saves a document state that has no description', async () => {
    const store = makeStore({ states: documentStates() });
    const wrapper = mountManager({ store, projectCatalog: false });
    await flushPromises();
    const row = wrapper.get('[data-testid="catalog-state-22"]');

    await row.get('[aria-label="Nombre del estado"]').setValue('Urgencia crítica');
    await row.get('[data-testid="catalog-save-state-22"]').trigger('click');
    await flushPromises();

    expect(store.updateState).toHaveBeenCalledWith(
      22,
      expect.objectContaining({ name: 'Urgencia crítica', description: '' }),
    );
    expect(store.updateState.mock.calls[0][1]).not.toHaveProperty('operational_effect');
  });

  it('places missing edit and merge requirements inside the document state', async () => {
    const store = makeStore({ states: documentStates() });
    const wrapper = mountManager({ store, projectCatalog: false });
    await flushPromises();
    const row = wrapper.get('[data-testid="catalog-state-22"]');

    await row.get('[aria-label="Nombre del estado"]').setValue('');
    await row.get('[data-testid="catalog-save-state-22"]').trigger('click');
    await row.get('[data-testid="catalog-merge-state-22"]').trigger('click');
    await flushPromises();

    expect(row.findAll('[role="alert"]').map((alert) => alert.text())).toEqual([
      'Escribe el nombre del estado.',
      'Elige el estado de destino.',
    ]);
    expect(store.updateState).not.toHaveBeenCalled();
    expect(store.mergeState).not.toHaveBeenCalled();
  });

  it('keeps the document seed merge restriction in accessible help', async () => {
    const wrapper = mountManager({
      store: makeStore({ states: documentStates() }),
      projectCatalog: false,
    });
    await flushPromises();
    const row = wrapper.get('[data-testid="catalog-state-21"]');
    const gate = row.findComponent(BaseControlGate);

    expect(gate.props('visible')).toBe(false);
    expect(gate.props('reasons')).toEqual([
      'Los estados semilla del sistema no se pueden fusionar.',
    ]);
    expect(row.get('[data-testid="catalog-merge-state-21"]').attributes('disabled'))
      .toBeDefined();
  });

  it('places a missing group name below its field and clears it once created', async () => {
    const store = makeStore({ states: documentStates() });
    const wrapper = mountManager({ store, projectCatalog: false, manageGroups: true });
    await flushPromises();
    const groupForm = wrapper.findAll('form')[1];
    const groupName = groupForm.get('[data-testid="catalog-new-group-name"]');

    await groupForm.trigger('submit');
    await flushPromises();

    expect(groupForm.get('[role="alert"]').text()).toBe('Escribe el nombre del grupo.');
    expect(groupName.attributes('aria-invalid')).toBe('true');
    expect(store.createGroup).not.toHaveBeenCalled();

    await groupName.setValue('Señales de pago');
    await groupForm.trigger('submit');
    await flushPromises();

    expect(store.createGroup)
      .toHaveBeenCalledWith(expect.objectContaining({ name: 'Señales de pago' }));
    expect(groupForm.find('[role="alert"]').exists()).toBe(false);
  });

  it('keeps a serializer rejection below its field and reports what has no field', async () => {
    const store = makeStore({
      states: documentStates(),
      updateState: jest.fn(async () => ({
        success: false,
        message: 'Ya existe un estado con ese nombre.',
        fieldErrors: {
          name: 'Ya existe un estado con ese nombre.',
          incompatibility_ids: 'Un estado no puede excluirse a sí mismo.',
        },
      })),
    });
    const wrapper = mountManager({ store, projectCatalog: false });
    await flushPromises();
    const row = wrapper.get('[data-testid="catalog-state-22"]');

    await row.get('[aria-label="Nombre del estado"]').setValue('Borrador');
    await row.get('[data-testid="catalog-save-state-22"]').trigger('click');
    await flushPromises();

    expect(row.get('[role="alert"]').text()).toBe('Ya existe un estado con ese nombre.');
    expect(notify.error).toHaveBeenCalledWith(expect.objectContaining({
      detail: 'Un estado no puede excluirse a sí mismo.',
    }));
  });
});
