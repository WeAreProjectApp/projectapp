import { mount } from '@vue/test-utils';

global.useLocalePath = jest.fn(() => (path) => `/es-co${path}`);

jest.mock('../../composables/useMessages', () => ({
  useMessages: jest.fn(() => ({ messages: require('vue').ref({ footer: require('../../locales/waiter/es.js').default.footer }) })),
}));

import LegalFooter from '../../components/legal/LegalFooter.vue';
import { LEGAL_ENTITY } from '../../config/legalEntity.js';

const NuxtLinkStub = { props: ['to'], template: '<a :href="to" v-bind="$attrs"><slot /></a>' };

function mountFooter(variant) {
  return mount(LegalFooter, {
    props: variant ? { variant } : {},
    global: { stubs: { NuxtLink: NuxtLinkStub } },
  });
}

describe('LegalFooter', () => {
  it('links every public Waiter legal page and the contact page', () => {
    const hrefs = mountFooter().findAll('nav a').map((a) => a.attributes('href'));

    expect(hrefs).toEqual([
      '/es-co/waiter',
      '/es-co/waiter/privacy',
      '/es-co/waiter/terms',
      '/es-co/waiter/data-deletion',
      '/es-co/contact',
    ]);
  });

  it('shows the legal identity as registered in Meta', () => {
    const identity = mountFooter().get('[data-testid="legal-footer-identity"]').text();

    expect(identity).toContain(LEGAL_ENTITY.tradeName);
    expect(identity).toContain(LEGAL_ENTITY.owner);
    expect(identity).toContain(`NIT ${LEGAL_ENTITY.nit}`);
    expect(identity).toContain(`${LEGAL_ENTITY.address}, ${LEGAL_ENTITY.city}, ${LEGAL_ENTITY.country}`);
    expect(identity).toContain(LEGAL_ENTITY.phone);
    expect(identity).toContain(LEGAL_ENTITY.email);
  });

  it('states that Waiter is a ProjectApp product on the legal pages', () => {
    expect(mountFooter().text()).toContain('Waiter es un producto de ProjectApp.');
  });

  it('omits the contact link and copyright inside the marketing footer overlay', () => {
    const wrapper = mountFooter('overlay');

    expect(wrapper.find('[data-testid="legal-footer-link-contact"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="legal-footer-link-deletion"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Waiter es un producto de ProjectApp.');
  });
});
