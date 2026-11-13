jest.mock('~/stores/platform-features', () => ({ usePlatformFeaturesStore: () => ({ routeAllowed: () => true, enabled: () => true }) }))
import { mount } from '@vue/test-utils';

global.useLocalePath = jest.fn(() => (path) => path);
global.useI18n = jest.fn(() => ({ t: (key) => key }));
global.useRoute = jest.fn(() => ({ fullPath: '/', name: 'index', path: '/' }));

jest.mock('../../stores/platform-auth', () => ({
  usePlatformAuthStore: jest.fn(() => ({
    user: { display_name: 'Admin User', email: 'admin@example.com' },
    displayName: 'Admin User',
    userInitials: 'AU',
    isAdmin: false,
  })),
}));

jest.mock('../../stores/platform-notifications', () => ({
  usePlatformNotificationsStore: jest.fn(() => ({
    unreadCount: 0,
    startPolling: jest.fn(),
    stopPolling: jest.fn(),
  })),
}));

import PlatformSidebar from '../../components/platform/PlatformSidebar.vue';

function mountPlatformSidebar(props = {}, toggleTheme = jest.fn()) {
  return mount(PlatformSidebar, {
    props,
    global: {
      stubs: {
        PlatformHelpMenu: { template: '<div data-testid="platform-help-menu-stub" />' },
        SidebarItem: { template: '<div class="sidebar-item-stub" />' },
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
      provide: {
        toggleSidebar: jest.fn(),
        toggleTheme,
        showThemePicker: false,
      },
    },
  });
}

describe('PlatformSidebar', () => {
  it('renders the aside element', () => {
    const wrapper = mountPlatformSidebar();

    expect(wrapper.find('aside').exists()).toBe(true);
  });

  it('renders nav items', () => {
    const wrapper = mountPlatformSidebar();

    expect(wrapper.findAll('.sidebar-item-stub').length).toBeGreaterThan(0);
  });

  it('shows collapsed abbreviated logo when isCollapsed is true', () => {
    const wrapper = mountPlatformSidebar({ isCollapsed: true });

    expect(wrapper.text()).toContain('PA');
  });

  it('shows full logo text when not collapsed', () => {
    const wrapper = mountPlatformSidebar({ isCollapsed: false });

    expect(wrapper.text()).toContain('Project');
  });

  it('emits logout when logout button is clicked', async () => {
    const wrapper = mountPlatformSidebar();

    await wrapper.get('button[aria-label="Cerrar sesión"]').trigger('click');

    expect(wrapper.emitted('logout')).toEqual([[]]);
  });

  it.each([
    [false, false, 'global.theme.enableDark', 'global.theme.enableLight'],
    [true, false, 'global.theme.enableLight', 'global.theme.enableDark'],
    [false, true, 'global.theme.enableDark', 'global.theme.enableLight'],
    [true, true, 'global.theme.enableLight', 'global.theme.enableDark'],
  ])('switches the theme with dark=%s collapsed=%s', async (isDark, isCollapsed, action, nextAction) => {
    const toggleTheme = jest.fn();
    const wrapper = mountPlatformSidebar({ isDark, isCollapsed }, toggleTheme);

    await wrapper.get(`button[aria-label="${action}"]`).trigger('click');

    expect(toggleTheme).toHaveBeenCalledTimes(1);
    await wrapper.setProps({ isDark: !isDark });
    expect(wrapper.get(`button[aria-label="${nextAction}"]`).attributes('type')).toBe('button');
  });
});
