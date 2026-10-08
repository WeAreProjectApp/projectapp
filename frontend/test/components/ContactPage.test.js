import { mount } from '@vue/test-utils';

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
    messages: require('vue').ref({
      contact: {
        title: 'Need a professional website?',
        subtitle: 'We develop custom websites.',
        form: {
          fullName: 'Full name',
          phone: 'Phone number',
          email: 'Your email',
          project: 'Tell us about your project',
          budget: 'Estimated budget',
          submit: 'Send message',
          error: 'We could not send your message. Please try again.',
        },
        budgetOptions: ['500-5K', '5-10K', '10-20K'],
      },
    }),
    currentLocale: require('vue').ref('es-co'),
  })),
}));

// Shared store instance so tests can drive submitError / sendContact.
const mockContactsStore = {
  isSubmitting: require('vue').ref(false),
  submitSuccess: require('vue').ref(false),
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

import ContactPage from '../../components/pages/ContactPage.vue';

function mountContactPage() {
  return mount(ContactPage, {
    global: {
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
    mockContactsStore.submitError.value = null;
    mockContactsStore.sendContact.mockReset();
    mockRouterPush.mockReset();
  });

  it('shows the localized error and does not redirect when submission fails', async () => {
    // The store may hold a raw DRF payload object — the page must render the
    // localized generic message, never "[object Object]".
    mockContactsStore.sendContact.mockImplementation(async () => {
      mockContactsStore.submitError.value = { email: ['Enter a valid email.'] };
      return { success: false, error: mockContactsStore.submitError.value };
    });
    const wrapper = mountContactPage();
    expect(wrapper.find('[data-testid="contact-submit-error"]').exists()).toBe(false);

    await wrapper.find('form').trigger('submit');
    await wrapper.vm.$nextTick();

    const alert = wrapper.find('[data-testid="contact-submit-error"]');
    expect(alert.exists()).toBe(true);
    expect(alert.text()).toBe('We could not send your message. Please try again.');
    expect(alert.text()).not.toContain('object');
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  it('keeps the error hidden after a successful submission', async () => {
    mockContactsStore.sendContact.mockResolvedValue({ success: true, data: {} });
    const wrapper = mountContactPage();

    await wrapper.find('form').trigger('submit');
    await wrapper.vm.$nextTick();

    expect(wrapper.find('[data-testid="contact-submit-error"]').exists()).toBe(false);
    expect(mockContactsStore.sendContact).toHaveBeenCalledTimes(1);
  });
});
