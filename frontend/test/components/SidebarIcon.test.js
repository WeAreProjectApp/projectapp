import { mount } from '@vue/test-utils';
import SidebarIcon from '../../components/platform/SidebarIcon.vue';

function mountIcon(name) {
  return mount(SidebarIcon, { props: { name } });
}

describe('SidebarIcon', () => {
  it('renders rect elements for the dashboard icon', () => {
    const wrapper = mountIcon('dashboard');

    expect(wrapper.findAll('rect').length).toBe(4);
  });

  it('renders path elements for the bell icon', () => {
    const wrapper = mountIcon('bell');

    expect(wrapper.findAll('path').length).toBe(2);
  });

  it('renders a dedicated puzzle path for additional modules', () => {
    const wrapper = mountIcon('puzzle');

    expect(wrapper.findAll('path')).toHaveLength(1);
    expect(wrapper.find('circle[r="10"]').exists()).toBe(false);
  });

  it('renders dedicated handshake paths for Building with Us', () => {
    const wrapper = mountIcon('handshake');

    expect(wrapper.findAll('path')).toHaveLength(3);
    expect(wrapper.find('circle[r="10"]').exists()).toBe(false);
  });

  it('renders the fallback circle for an unrecognized icon name', () => {
    const wrapper = mountIcon('not-a-real-icon');

    expect(wrapper.find('circle[r="10"]').exists()).toBe(true);
  });
});
