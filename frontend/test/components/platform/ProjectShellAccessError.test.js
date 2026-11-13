import { mount } from '@vue/test-utils';
import es from '../../../locales/projectAccess/es';
import en from '../../../locales/projectAccess/en';
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

function mountShell(locale = 'es-co') {
  global.useRoute = () => ({ params: { id: '6' }, query: {}, path: '/platform/projects/6' });
  global.useLocalePath = () => (path) => `/${locale}${path}`;
  global.useI18n = () => ({ t: (key) => (locale === 'es-co' ? es : en).accessError[key.split('.').at(-1)] });
  return mount(ProjectShell, {
    slots: { default: '<p>Contenido privado del espacio</p>' },
    global: {
      stubs: {
        ProjectBreadcrumb: { template: '<div />' },
        ProjectSecondarySidebar: { template: '<aside>Menú privado</aside>' },
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
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
    delete global.useI18n;
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


describe('ProjectShell terminal states (PA-252)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore.currentProject = null;
    mockStore.isLoading = false;
    mockStore.error = 'No disponible';
    mockStore.errorStatus = 403;
  });
  afterEach(() => {
    delete global.useRoute;
    delete global.useLocalePath;
    delete global.useI18n;
  });

  it.each([
    [403, 'No tienes acceso a este proyecto'],
    [404, 'Proyecto no disponible'],
    [500, 'No pudimos abrir el proyecto'],
  ])('explains the completed %s request', (status, title) => {
    mockStore.errorStatus = status;
    const wrapper = mountShell();

    expect(wrapper.get('[role="alert"]').text()).toContain(title);
    expect(wrapper.text()).not.toContain('Cargando proyecto');
    wrapper.unmount();
  });

  it.each(['es-co', 'en-us'])('preserves %s in the recovery link', (locale) => {
    const wrapper = mountShell(locale);

    expect(wrapper.get('a').attributes('href')).toBe(`/${locale}/platform/projects`);
    wrapper.unmount();
  });

  it('translates the denial in English', () => {
    const wrapper = mountShell('en-us');

    expect(wrapper.get('[role="alert"]').text()).toContain(en.accessError.deniedTitle);
    wrapper.unmount();
  });

  it.each([403, 404])('does not retry a terminal %s response', (status) => {
    mockStore.errorStatus = status;
    const wrapper = mountShell();

    expect(wrapper.findAll('button')).toHaveLength(0);
    wrapper.unmount();
  });

  it('retries a recoverable failure for the requested project', async () => {
    mockStore.errorStatus = 500;
    const wrapper = mountShell();
    mockFetchProject.mockClear();

    await wrapper.get('button').trigger('click');

    expect(mockFetchProject).toHaveBeenCalledWith(6);
    wrapper.unmount();
  });

  it('announces the pending request without an error', () => {
    mockStore.isLoading = true;
    mockStore.error = '';
    const wrapper = mountShell();

    expect(wrapper.get('[role="status"]').text()).toBe('Cargando proyecto…');
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
