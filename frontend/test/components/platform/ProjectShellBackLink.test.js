/**
 * ProjectShell "Ficha comercial" back-link (PA-50 return path).
 *
 * Covers the role gate (a platform admin sees the jump to the panel, a
 * client never does) and the deep-link URL that lands the panel listing on
 * exactly this project.
 */
import { mount } from '@vue/test-utils';
import ProjectShell from '../../../components/platform/projects/ProjectShell.vue';
import es from '../../../locales/projectAccess/es';
import en from '../../../locales/projectAccess/en';

let mockRole = 'admin';
const mockFetchProject = jest.fn();

jest.mock('../../../stores/platform-auth', () => ({
  usePlatformAuthStore: () => ({
    get isAdmin() {
      return mockRole === 'admin';
    },
  }),
}));

jest.mock('../../../stores/platform-projects', () => ({
  usePlatformProjectsStore: () => ({
    fetchProject: mockFetchProject,
    currentProject: {
      id: 5,
      name: 'Kore',
      status: 'active',
      status_label: 'Activo',
      current_state: { id: 2, name: 'Activo', color: 'emerald' },
      client_name: 'Deivis',
    },
  }),
}));

function mountShell(locale = 'es-co') {
  global.useRoute = () => ({ params: { id: '5' }, query: {}, path: '/' });
  global.useLocalePath = () => ({ path, query }) => `/${locale}${path}?${new URLSearchParams(query)}`;
  global.useI18n = () => ({
    t: (key) => (locale === 'es-co' ? es : en).commercialRecord[key.split('.').pop()],
  });
  return mount(ProjectShell, {
    global: {
      stubs: {
        ProjectBreadcrumb: { template: '<div />' },
        ProjectSecondarySidebar: { template: '<div />' },
      },
    },
  });
}

describe('ProjectShell back link', () => {
  let openSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    openSpy = jest.spyOn(window, 'open').mockImplementation(() => {});
  });

  afterEach(() => {
    openSpy.mockRestore();
    delete global.useLocalePath;
    delete global.useI18n;
    delete global.useRoute;
  });

  it.each(['es-co', 'en-us'])('preserves %s when opening the commercial record', async (locale) => {
    mockRole = 'admin';
    const wrapper = mountShell(locale);

    const link = wrapper.find('[data-testid="project-back-to-panel"]');
    expect(link.exists()).toBe(true);
    await link.trigger('click');

    expect(openSpy).toHaveBeenCalledWith(`/${locale}/panel/projects?highlight=5`, '_blank');
  });

  it.each([
    ['es-co', es.commercialRecord],
    ['en-us', en.commercialRecord],
  ])('labels the commercial link in %s', (locale, text) => {
    mockRole = 'admin';
    const wrapper = mountShell(locale);

    expect(wrapper.get('[data-testid="project-back-to-panel"]').text()).toBe(text.label);
    expect(wrapper.get('[data-testid="project-back-to-panel"]').attributes('title')).toBe(text.title);
    wrapper.unmount();
  });

  it('a client never sees the panel link', () => {
    mockRole = 'client';
    const wrapper = mountShell();

    expect(wrapper.find('[data-testid="project-back-to-panel"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
