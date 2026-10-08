import { mount } from '@vue/test-utils';

global.useLocalePath = jest.fn(() => (path) => `/es-co${path}`);

import LegalRichText from '../../components/legal/LegalRichText.vue';

const NuxtLinkStub = { props: ['to'], template: '<a :href="to" data-nuxt-link><slot /></a>' };

// Mounted inside a <p> like in the legal pages: the component renders a
// fragment, and the paragraph's text is what the reader actually sees.
function render(text) {
  return mount({
    components: { LegalRichText },
    props: ['text'],
    template: '<p><LegalRichText :text="text" /></p>',
  }, {
    props: { text },
    global: { stubs: { NuxtLink: NuxtLinkStub } },
  });
}

describe('LegalRichText', () => {
  it('renders plain text unchanged', () => {
    expect(render('Sin marcas.').text()).toBe('Sin marcas.');
  });

  it('renders **bold** as strong text', () => {
    const wrapper = render('Antes **importante** después');

    expect(wrapper.get('strong').text()).toBe('importante');
    expect(wrapper.text()).toBe('Antes importante después');
  });

  it('renders `code` as a code element', () => {
    expect(render('cookie `waiter_diner` de sesión').get('code').text()).toBe('waiter_diner');
  });

  it('renders internal links as locale-aware NuxtLinks', () => {
    const link = render('Lee la [política](/waiter/privacy).').get('[data-nuxt-link]');

    expect(link.attributes('href')).toBe('/es-co/waiter/privacy');
    expect(link.text()).toBe('política');
  });

  it('renders mailto links as plain anchors in the same tab', () => {
    const link = render('[team@projectapp.co](mailto:team@projectapp.co)').get('a');

    expect(link.attributes('href')).toBe('mailto:team@projectapp.co');
    expect(link.attributes('target')).toBeUndefined();
  });

  it('opens external https links in a new tab without opener', () => {
    const link = render('[whatsapp.com/legal](https://www.whatsapp.com/legal)').get('a');

    expect(link.attributes('target')).toBe('_blank');
    expect(link.attributes('rel')).toBe('noopener noreferrer');
  });

  it('never turns an unsafe scheme into a link', () => {
    const wrapper = render('[clic](javascript:alert(1))');

    expect(wrapper.find('a').exists()).toBe(false);
  });
});
