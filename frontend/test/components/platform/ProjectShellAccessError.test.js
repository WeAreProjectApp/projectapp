import { mount } from '@vue/test-utils';
import ProjectShell from '../../../components/platform/projects/ProjectShell.vue';

const mockFetchProject = jest.fn();
const mockStore = {
  fetchProject: mockFetchProject,
  currentProject: null,
  isLoading: false,
  error: '',
  errorStatus: null,
};

jest.mock('../../../stores/platform-auth', () => ({
  usePlatformAuthStore: () => ({ isAdmin: true }),
}));

jest.mock('../../../stores/platform-projects', () => ({
  usePlatformProjectsStore: () => mockStore,
}));

function mountShell() {
  global.useRoute = () => ({ params: { id: '6' }, query: {}, path: '/platform/projects/6' });
  global.useLocalePath = () => (path) => path;
  return mount(ProjectShell, {
    slots: { default: '<p>Contenido privado del espacio</p>' },
    global: {
      stubs: {
        ProjectBreadcrumb: { template: '<div />' },
        ProjectSecondarySidebar: { template: '<aside>Menú privado</aside>' },
      },
    },
  });
}

describe('ProjectShell access errors', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore.currentProject = { id: 5, name: 'Proyecto anterior', current_state: { color: 'emerald' } };
    mockStore.isLoading = false;
    mockStore.error = 'No autorizado.';
    mockStore.errorStatus = 403;
  });

  afterEach(() => {
    delete global.useRoute;
    delete global.useLocalePath;
  });

  // Falla si un 403 para la ruta nueva deja visibles datos, navegación o retorno al Panel del proyecto anterior.
  it('hides a previous project while showing the 403 state for the requested route', () => {
    const wrapper = mountShell();

    expect(mockFetchProject).toHaveBeenCalledWith(6);
    expect(wrapper.get('[role="alert"]').text()).toContain('No tienes acceso a este proyecto');
    expect(wrapper.get('[role="alert"]').text()).toContain('Tu cuenta no tiene permiso para abrir este espacio.');
    expect(wrapper.text()).not.toContain('Proyecto anterior');
    expect(wrapper.text()).not.toContain('Contenido privado del espacio');
    expect(wrapper.text()).not.toContain('Menú privado');
    expect(wrapper.text()).not.toContain('Ficha comercial');
    expect(wrapper.get('[role="alert"]').text()).toContain('Volver a proyectos');
    wrapper.unmount();
  });
});
