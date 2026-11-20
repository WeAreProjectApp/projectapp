import { mount } from '@vue/test-utils';
import { createI18n, useI18n } from 'vue-i18n';
import successEn from '../../locales/contactSuccess/en';
import successEs from '../../locales/contactSuccess/es';

jest.mock('gsap', () => ({
  __esModule: true,
  default: {
    from: jest.fn(),
    to: jest.fn(),
    set: jest.fn(),
    fromTo: jest.fn(),
    timeline: jest.fn(() => ({
      to: jest.fn().mockReturnThis(),
      from: jest.fn().mockReturnThis(),
      fromTo: jest.fn().mockReturnThis(),
    })),
    registerPlugin: jest.fn(),
    killTweensOf: jest.fn(),
  },
}));

global.useI18n = useI18n;
global.useLocalePath = () => {
  const { locale } = useI18n();
  return (path) => `/${locale.value}${path}`;
};

import ContactSuccess from '../../components/pages/ContactSuccess.vue';

function mountContactSuccess(locale = 'es-co') {
  const i18n = createI18n({
    legacy: false,
    locale,
    messages: { 'en-us': { contactSuccess: successEn }, 'es-co': { contactSuccess: successEs } },
  });
  return mount(ContactSuccess, { global: { plugins: [i18n] } });
}

describe('ContactSuccess', () => {
  it('renders the main element', () => {
    const wrapper = mountContactSuccess();

    expect(wrapper.find('main').exists()).toBe(true);
  });

  it('renders the success title', () => {
    const wrapper = mountContactSuccess();

    expect(wrapper.get('h1').text()).toContain('¡Gracias por contactarnos!');
  });

  it('renders the English confirmation heading', () => {
    const wrapper = mountContactSuccess('en-us');

    expect(wrapper.get('h1').text()).toContain('Thank you for contacting us!');
  });

  it('renders the success message', () => {
    const wrapper = mountContactSuccess();

    expect(wrapper.text()).toContain('Nos pondremos en contacto contigo muy pronto');
  });

  it('renders the portfolio link button', () => {
    const wrapper = mountContactSuccess();

    const link = wrapper.get('a');
    expect(link.text()).toBe('Ver nuestro portafolio');
    expect(link.attributes('href')).toBe('/es-co/portfolio-works');
  });
});
