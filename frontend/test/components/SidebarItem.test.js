import { mount } from '@vue/test-utils';
import SidebarItem from '../../components/platform/SidebarItem.vue';

const externalItem = { href: 'https://example.com', external: true, openInNewTab: true, icon: 'dashboard', label: 'External', badge: null };
const internalItem = { href: '/dashboard', external: false, icon: 'dashboard', label: 'Dashboard', badge: null };
const badgeItem = { href: '/notifications', external: false, icon: 'bell', label: 'Notifications', badge: '3' };

function mountItem(props = {}) {
  return mount(SidebarItem, {
    props: { item: internalItem, isCollapsed: false, isActive: false, disabled: false, ...props },
    global: {
      stubs: {
        // Forward attrs so aria-current and class bindings reach the root <a>; render slot so text content shows
        NuxtLink: { template: '<a v-bind="$attrs"><slot /></a>' },
        SidebarIcon: true,
      },
    },
  });
}

describe('SidebarItem', () => {
  it('renders a link with the external href for an external item', () => {
    const wrapper = mountItem({ item: externalItem });

    expect(wrapper.find('a[href="https://example.com"]').exists()).toBe(true);
  });

  it('renders the item label for a non-external non-disabled item', () => {
    const wrapper = mountItem({ item: internalItem });

    expect(wrapper.text()).toContain('Dashboard');
  });

  it('shows "pronto" label when the item is disabled', () => {
    const wrapper = mountItem({ item: internalItem, disabled: true });

    expect(wrapper.text()).toContain('pronto');
  });

  it('shows the badge text when the item has a badge', () => {
    const wrapper = mountItem({ item: badgeItem });

    expect(wrapper.text()).toContain('3');
  });

  it('hides the label when isCollapsed is true', () => {
    const wrapper = mountItem({ item: internalItem, isCollapsed: true });

    expect(wrapper.text()).not.toContain('Dashboard');
  });

  it.each([internalItem, externalItem])('keeps an explicit link name for the compact $label icon', (item) => {
    const wrapper = mountItem({ item, isCollapsed: true });

    expect(wrapper.get('a').attributes('aria-label')).toBe(item.label);
    expect(wrapper.get('a').attributes('title')).toBe(item.label);
  });

  it('sets aria-current to page when isActive is true', () => {
    const wrapper = mountItem({ item: internalItem, isActive: true });

    expect(wrapper.find('a').attributes('aria-current')).toBe('page');
  });
});
