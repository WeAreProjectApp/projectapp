import { mount } from '@vue/test-utils';

global.useLocalePath = jest.fn(() => (path) => `/es-co${path}`);

jest.mock('../../composables/useMessages', () => ({
  useMessages: jest.fn(() => ({ messages: require('vue').ref(require('../../locales/waiter/es.js').default) })),
}));
jest.mock('../../components/legal/LegalFooter.vue', () => ({
  __esModule: true,
  default: { name: 'LegalFooter', template: '<footer data-testid="legal-footer-stub" />' },
}));

import WaiterProduct from '../../components/pages/WaiterProduct.vue';

const NuxtLinkStub = { props: ['to'], template: '<a :href="to" v-bind="$attrs"><slot /></a>' };

function mountPage() {
  return mount(WaiterProduct, { global: { stubs: { NuxtLink: NuxtLinkStub } } });
}

describe('WaiterProduct', () => {
  it('presents Waiter as a ProjectApp product', () => {
    const wrapper = mountPage();

    expect(wrapper.get('h1').text()).toBe('Waiter');
    expect(wrapper.text()).toContain('Un producto de ProjectApp');
  });

  it('explains the WhatsApp connection in four ordered steps', () => {
    const steps = mountPage().findAll('ol > li');

    expect(steps).toHaveLength(4);
    expect(steps[0].text()).toContain('Conectar WhatsApp');
  });

  it('links to the contact page and to the Waiter legal pages', () => {
    const hrefs = mountPage().findAll('a').map((a) => a.attributes('href'));

    expect(hrefs).toEqual(expect.arrayContaining([
      '/es-co/contact',
      '/es-co/waiter/privacy',
      '/es-co/waiter/terms',
      '/es-co/waiter/data-deletion',
    ]));
  });

  it('renders the legal footer', () => {
    expect(mountPage().find('[data-testid="legal-footer-stub"]').exists()).toBe(true);
  });
});
