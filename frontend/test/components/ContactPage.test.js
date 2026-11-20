import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import { createI18n, useI18n } from 'vue-i18n';
import contactEn from '../../locales/contact/en';
import contactEs from '../../locales/contact/es';

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

jest.mock('../../animations', () => ({
  waveEmoji: jest.fn(),
}));

jest.mock('pinia', () => ({
  storeToRefs: jest.fn((store) => store),
  defineStore: jest.fn(),
}));

jest.mock('../../stores/language', () => ({
  useLanguageStore: jest.fn(() => ({
    currentLocale: require('vue').ref('en-us'),
  })),
}));

// Shared store instance so tests can drive submitError / sendContact.
const mockContactsStore = {
  isSubmitting: require('vue').ref(false),
  submitError: require('vue').ref(null),
  sendContact: jest.fn(),
};

jest.mock('../../stores/contacts', () => ({
  useContactsStore: jest.fn(() => mockContactsStore),
}));

jest.mock('../../composables/useGtagConversions', () => ({
  useGtagConversions: jest.fn(() => ({ trackFormSubmission: jest.fn() })),
}));

const mockRouterPush = jest.fn();
global.useRouter = jest.fn(() => ({ push: mockRouterPush }));
global.useI18n = useI18n;

import ContactPage from '../../components/pages/ContactPage.vue';

function mountContactPage(locale = 'en-us') {
  const i18n = createI18n({
    legacy: false,
    locale,
    messages: { 'en-us': { contact: contactEn }, 'es-co': { contact: contactEs } },
  });
  return mount(ContactPage, {
    global: {
      plugins: [i18n],
      stubs: { CompanyDetails: { template: '<section data-testid="company-details-stub" />' } },
    },
  });
}

describe('ContactPage', () => {
  it('renders the main element', () => {
    const wrapper = mountContactPage();

    expect(wrapper.find('main').exists()).toBe(true);
  });

  it('renders the company details block required by the Meta review', () => {
    const wrapper = mountContactPage();

    expect(wrapper.find('[data-testid="company-details-stub"]').exists()).toBe(true);
  });

  it('renders the page title', () => {
    const wrapper = mountContactPage();

    expect(wrapper.text()).toContain('Need a professional website?');
  });

  it('renders the contact form', () => {
    const wrapper = mountContactPage();

    expect(wrapper.find('form').exists()).toBe(true);
  });

  it('renders the submit button', () => {
    const wrapper = mountContactPage();

    expect(wrapper.find('button[type="submit"]').exists()).toBe(true);
  });

  it('renders budget option buttons', () => {
    const wrapper = mountContactPage();

    expect(wrapper.text()).toContain('500-5K');
  });
});

describe('ContactPage submit error display', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockContactsStore.submitError.value = null;
    mockContactsStore.sendContact.mockReset();
    mockRouterPush.mockReset();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('shows the Spanish error after a rejected submission', async () => {
    // The store may hold a raw DRF payload object — the page must render the
    // localized generic message, never "[object Object]".
    mockContactsStore.sendContact.mockImplementation(async () => {
      mockContactsStore.submitError.value = { email: ['Enter a valid email.'] };
      return { success: false, error: mockContactsStore.submitError.value };
    });
    const wrapper = mountContactPage('es-co');
    expect(wrapper.find('[data-testid="contact-submit-error"]').exists()).toBe(false);

    await wrapper.find('form').trigger('submit');
    await nextTick();

    const alert = wrapper.find('[data-testid="contact-submit-error"]');
    expect(alert.exists()).toBe(true);
    expect(alert.text()).toBe('No pudimos enviar tu mensaje. Por favor inténtalo de nuevo.');
    expect(alert.text()).not.toContain('object');
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  it('keeps the error hidden after a successful submission', async () => {
    mockContactsStore.sendContact.mockResolvedValue({ success: true, data: {} });
    const wrapper = mountContactPage();

    await wrapper.find('form').trigger('submit');
    await nextTick();

    expect(wrapper.find('[data-testid="contact-submit-error"]').exists()).toBe(false);
    expect(mockContactsStore.sendContact).toHaveBeenCalledTimes(1);
  });

  it('ignores a second submission after acceptance', async () => {
    mockContactsStore.sendContact.mockResolvedValue({ success: true, data: { id: 1 } });
    const wrapper = mountContactPage();
    const form = wrapper.get('[data-testid="contact-form"]');

    await form.trigger('submit');
    await nextTick();
    await form.trigger('submit');

    expect(mockContactsStore.sendContact).toHaveBeenCalledTimes(1);
    expect(wrapper.get('button[type="submit"]').element.disabled).toBe(true);
  });
});
