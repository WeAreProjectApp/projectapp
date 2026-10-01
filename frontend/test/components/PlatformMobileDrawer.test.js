import { mount } from '@vue/test-utils';

global.useLocalePath = jest.fn(() => (path) => path);
global.useI18n = jest.fn(() => ({ t: (key) => key }));
global.useRoute = jest.fn(() => ({ fullPath: '/', name: 'index', path: '/' }));

jest.mock('../../stores/platform-auth', () => ({
  usePlatformAuthStore: jest.fn(() => ({
    user: { display_name: 'Test User', email: 'test@example.com' },
    displayName: 'Test User',
    userInitials: 'TU',
    isAdmin: false,
  })),
}));

jest.mock('../../stores/platform-notifications', () => ({
  usePlatformNotificationsStore: jest.fn(() => ({
    unreadCount: 3,
    startPolling: jest.fn(),
    stopPolling: jest.fn(),
  })),
}));

import PlatformMobileDrawer from '../../components/platform/PlatformMobileDrawer.vue';

function mountPlatformMobileDrawer(props = {}) {
  return mount(PlatformMobileDrawer, {
    props: { isOpen: true, ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        SidebarItem: { template: '<div class="sidebar-item-stub" />' },
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  });
}

describe('PlatformMobileDrawer', () => {
  it('renders the aside when isOpen is true', () => {
    const wrapper = mountPlatformMobileDrawer();

    expect(wrapper.find('aside').exists()).toBe(true);
  });

  it('renders nav items via SidebarItem stubs', () => {
    const wrapper = mountPlatformMobileDrawer();

    expect(wrapper.findAll('.sidebar-item-stub').length).toBeGreaterThan(0);
  });

  it('emits close when the close button is clicked', async () => {
    const wrapper = mountPlatformMobileDrawer();

    // First button in header is the close button
    const closeBtn = wrapper.find('aside button');
    await closeBtn.trigger('click');

    expect(wrapper.emitted('close')).toBeTruthy();
  });

  it('emits logout when the logout button is clicked', async () => {
    const wrapper = mountPlatformMobileDrawer();

    const logoutBtn = wrapper.findAll('button').find(b => b.text().includes('Salir'));
    await logoutBtn.trigger('click');

    expect(wrapper.emitted('logout')).toBeTruthy();
  });

  it('does not render aside when isOpen is false', () => {
    const wrapper = mountPlatformMobileDrawer({ isOpen: false });

    expect(wrapper.find('aside').exists()).toBe(false);
  });
});
