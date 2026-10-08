import { mount } from '@vue/test-utils';

global.useLocalePath = jest.fn(() => (path) => path);
global.useI18n = jest.fn(() => ({
  t: jest.fn((key) => ({
    'additionalModules.title': 'Additional modules',
    'financing.title': 'Partnership Program',
  }[key] || key)),
}));
global.IntersectionObserver = jest.fn(() => ({
  observe: jest.fn(),
  disconnect: jest.fn(),
  unobserve: jest.fn(),
}));

Object.defineProperty(HTMLVideoElement.prototype, 'play', {
  configurable: true,
  value: jest.fn().mockResolvedValue(undefined),
});
Object.defineProperty(HTMLVideoElement.prototype, 'pause', {
  configurable: true,
  value: jest.fn(),
});

jest.mock('assets/videos/presentationMobile.mp4', () => '', { virtual: true });

jest.mock('@heroicons/vue/20/solid/ArrowUpRightIcon', () => ({
  __esModule: true,
  default: { name: 'ArrowUpRightIcon', template: '<svg />' },
}), { virtual: true });

jest.mock('../../composables/useMessages', () => ({
  useGlobalMessages: jest.fn(() => ({
    globalMessages: require('vue').ref({
      sign_in: 'Sign In',
      instagram: 'Instagram',
      facebook: 'Facebook',
      whatsapp: 'WhatsApp',
      email_address: 'team@projectapp.co',
      based_in: 'Based in Colombia',
      terms_and_conditions: 'Terms and Conditions',
      privacy_policy: 'Privacy Policy',
      solutions: { software: 'Custom Software', apps: 'App Development', web_developments: 'Our Work', blog: 'Blog' },
    }),
  })),
}));

jest.mock('../../composables/useFreeResources', () => ({
  useFreeResources: jest.fn(() => ({ freeMediaResources: jest.fn() })),
}));

import FooterMobile from '../../components/layouts/FooterMobile.vue';

function mountFooterMobile() {
  return mount(FooterMobile, {
    attachTo: document.body,
    global: {
      stubs: {
        Email: true,
        LegalFooter: { props: ['variant'], template: '<div data-testid="legal-footer-stub" :data-variant="variant" />' },
        NuxtLink: { props: ['to'], template: '<a :href="to" v-bind="$attrs"><slot /></a>' },
      },
    },
  });
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('FooterMobile', () => {
  it('renders the footer element', () => {
    const wrapper = mountFooterMobile();

    expect(wrapper.find('footer').exists()).toBe(true);
  });

  it('renders Instagram social link', () => {
    const wrapper = mountFooterMobile();

    expect(wrapper.text()).toContain('Instagram');
  });

  it('renders Facebook social link', () => {
    const wrapper = mountFooterMobile();

    expect(wrapper.text()).toContain('Facebook');
  });

  it('renders WhatsApp social link', () => {
    const wrapper = mountFooterMobile();

    expect(wrapper.text()).toContain('WhatsApp');
  });

  it('renders Sign In link', () => {
    const wrapper = mountFooterMobile();

    expect(wrapper.text()).toContain('Sign In');
  });

  it('renders navigation links', () => {
    const wrapper = mountFooterMobile();

    expect(wrapper.text()).toContain('Custom Software');
  });

  it('renders the additional modules catalog link', () => {
    const wrapper = mountFooterMobile();

    expect(wrapper.get('a[href="/additional-modules"]').attributes('aria-label'))
      .toBe('Additional modules');
  });

  it('renders the partnership program link', () => {
    const wrapper = mountFooterMobile();

    expect(wrapper.get('a[href="/partnership-program"]').attributes('aria-label'))
      .toBe('Partnership Program');
  });

  it('renders the Waiter legal strip in its overlay variant', () => {
    const wrapper = mountFooterMobile();

    const strip = wrapper.get('[data-testid="legal-footer-stub"]');
    expect(strip.attributes('data-variant')).toBe('overlay');
  });
});
