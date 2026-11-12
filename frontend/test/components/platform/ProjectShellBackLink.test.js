/**
 * ProjectShell "Ficha comercial" back-link (PA-50 return path).
 *
 * Covers the role gate (a platform admin sees the jump to the panel, a
 * client never does) and the deep-link URL that lands the panel listing on
 * exactly this project.
 */
import { mount } from '@vue/test-utils';
import ProjectShell from '../../../components/platform/projects/ProjectShell.vue';

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

function mountShell() {
  global.useRoute = () => ({ params: { id: '5' }, query: {}, path: '/' });
  global.useLocalePath = () => (path) => path;
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
    delete global.useRoute;
    delete global.useLocalePath;
  });

  it('an admin jumps to the commercial record in a new tab', async () => {
    mockRole = 'admin';
    const wrapper = mountShell();

    const link = wrapper.find('[data-testid="project-back-to-panel"]');
    expect(link.exists()).toBe(true);
    await link.trigger('click');

    expect(openSpy).toHaveBeenCalledWith('/panel/projects?highlight=5', '_blank');
    wrapper.unmount();
  });

  it('a client never sees the panel link', () => {
    mockRole = 'client';
    const wrapper = mountShell();

    expect(wrapper.find('[data-testid="project-back-to-panel"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
