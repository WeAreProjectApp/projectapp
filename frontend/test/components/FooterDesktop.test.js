import { enableAutoUnmount, mount } from '@vue/test-utils';

enableAutoUnmount(afterEach);

global.useLocalePath = jest.fn(() => (path) => path);
global.useI18n = jest.fn(() => ({
  t: jest.fn((key) => ({
    'additionalModules.title': 'Additional modules',
    'financing.title': 'Partnership Program',
    'buildingWithUs.title': 'Building with Us',
  }[key] || key)),
}));
global.requestAnimationFrame = jest.fn(() => 0);
global.cancelAnimationFrame = jest.fn();
global.IntersectionObserver = jest.fn(() => {
  const observed = new Set();
  return {
    observed,
    observe: jest.fn((element) => observed.add(element)),
    disconnect: jest.fn(() => observed.clear()),
    unobserve: jest.fn((element) => observed.delete(element)),
  };
});

Object.defineProperty(HTMLVideoElement.prototype, 'play', {
  configurable: true,
  value: jest.fn().mockResolvedValue(undefined),
});
Object.defineProperty(HTMLVideoElement.prototype, 'pause', {
  configurable: true,
  value: jest.fn(),
});
Object.defineProperty(HTMLVideoElement.prototype, 'load', {
  configurable: true,
  value: jest.fn(),
});

jest.mock('assets/videos/presentationPrevPc.mp4', () => '', { virtual: true });

jest.mock('gsap', () => {
  const tl = {
    from: jest.fn(), to: jest.fn(), fromTo: jest.fn(),
    add: jest.fn(), play: jest.fn(), kill: jest.fn(),
  };
  const mock = {
    from: jest.fn(), to: jest.fn(), set: jest.fn(), fromTo: jest.fn(),
    timeline: jest.fn(() => tl),
    registerPlugin: jest.fn(), killTweensOf: jest.fn(),
    context: jest.fn(() => ({ revert: jest.fn() })),
  };
  return { gsap: mock, default: mock, ...mock };
});

jest.mock('@heroicons/vue/24/outline', () => ({
  XMarkIcon: { name: 'XMarkIcon', template: '<svg />' },
}));

jest.mock('@heroicons/vue/20/solid/ArrowUpRightIcon', () => ({
  __esModule: true,
  default: { name: 'ArrowUpRightIcon', template: '<svg />' },
}), { virtual: true });

jest.mock('../../composables/useMessages', () => ({
  useGlobalMessages: jest.fn(() => ({
    globalMessages: require('vue').ref({
      play_reel: 'Play Reel',
      sign_in: 'Sign In',
      instagram: 'Instagram',
      facebook: 'Facebook',
      whatsapp: 'WhatsApp',
      email_address: 'team@projectapp.co',
      based_in: 'Based in Colombia',
      copyright: '©2026 Project App.',
      terms_and_conditions: 'Terms and Conditions',
      privacy_policy: 'Privacy Policy',
      solutions: { software: 'Custom Software', apps: 'App Development', web_developments: 'Our Work', blog: 'Blog' },
    }),
  })),
}));

jest.mock('../../composables/useFreeResources', () => ({
  useFreeResources: jest.fn(() => ({ freeMediaResources: jest.fn() })),
}));

jest.mock('vue3-lottie', () => ({
  Vue3Lottie: { name: 'Vue3Lottie', template: '<div />' },
}));

import { nextTick } from 'vue';
import { gsap } from 'gsap';
import FooterDesktop from '../../components/layouts/FooterDesktop.vue';

function mountFooterDesktop() {
  return mount(FooterDesktop, {
    attachTo: document.body,
    global: {
      stubs: {
        Email: { props: ['visible'], template: '<div v-if="visible" role="dialog" data-testid="footer-email-dialog" />' },
        Teleport: true,
        LegalFooter: { props: ['variant'], template: '<div data-testid="legal-footer-stub" :data-variant="variant" />' },
        NuxtLink: { props: ['to'], template: '<a :href="to" v-bind="$attrs"><slot /></a>' },
      },
    },
  });
}

afterEach(() => {
  document.body.innerHTML = '';
  document.body.style.overflow = '';
  jest.clearAllMocks();
});

describe('FooterDesktop', () => {
  it('renders the footer element', () => {
    const wrapper = mountFooterDesktop();

    expect(wrapper.find('footer').exists()).toBe(true);
  });

  it('renders the Play Reel button text', () => {
    const wrapper = mountFooterDesktop();

    expect(wrapper.text()).toContain('Play Reel');
  });

  it('renders Instagram social link', () => {
    const wrapper = mountFooterDesktop();

    expect(wrapper.text()).toContain('Instagram');
  });

  it('renders Facebook social link', () => {
    const wrapper = mountFooterDesktop();

    expect(wrapper.text()).toContain('Facebook');
  });

  it('renders the Sign In link', () => {
    const wrapper = mountFooterDesktop();

    expect(wrapper.text()).toContain('Sign In');
  });

  it('renders navigation solution links', () => {
    const wrapper = mountFooterDesktop();

    expect(wrapper.text()).toContain('Custom Software');
  });

  it('renders the additional modules catalog link', () => {
    const wrapper = mountFooterDesktop();

    expect(wrapper.get('a[href="/additional-modules"]').attributes('aria-label'))
      .toBe('Additional modules');
  });

  it('renders the partnership program link', () => {
    const wrapper = mountFooterDesktop();

    expect(wrapper.get('a[href="/partnership-program"]').attributes('aria-label'))
      .toBe('Partnership Program');
  });

  it('renders the Building with Us public link', () => {
    const wrapper = mountFooterDesktop();

    expect(wrapper.get('a[href="/building-with-us"]').attributes('aria-label'))
      .toBe('Building with Us');
  });

  // ── modal open / close ────────────────────────────────────────────────────

  it('clicking the Play Reel ball shows the modal dialog', async () => {
    const wrapper = mountFooterDesktop();

    await wrapper.find('button[aria-label="Play our web design portfolio showcase video"]').trigger('click');
    await nextTick();

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true);
  });

  it('clicking the Close video button in the modal hides the dialog', async () => {
    const wrapper = mountFooterDesktop();

    await wrapper.find('button[aria-label="Play our web design portfolio showcase video"]').trigger('click');
    await nextTick();
    await wrapper.find('button[aria-label="Close video"]').trigger('click');
    await nextTick();

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
  });

  // ── video loading ─────────────────────────────────────────────────────────

  it('loadeddata event on modal video sets isLoading to false', async () => {
    const wrapper = mountFooterDesktop();

    await wrapper.find('button[aria-label="Play our web design portfolio showcase video"]').trigger('click');
    await nextTick();

    const modalVideo = wrapper.find('video[preload="metadata"]');
    await modalVideo.trigger('loadeddata');
    await nextTick();

    const loadingOverlay = wrapper.find('[aria-label="Loading video"]');
    expect(loadingOverlay.isVisible()).toBe(false);
  });

  // ── mouse tracking ────────────────────────────────────────────────────────

  it('moves the portfolio control toward the pointer', async () => {
    const wrapper = mountFooterDesktop();
    const ball = wrapper.get('button[aria-label="Play our web design portfolio showcase video"]');
    const frame = requestAnimationFrame.mock.calls.at(-1)[0];

    await wrapper.get('footer').trigger('mousemove', { clientX: 150, clientY: 200 });
    frame();

    const motion = gsap.to.mock.calls.find(([element]) => element === ball.element)[1];
    expect(motion.x).toBeGreaterThan(0);
    expect(motion.y).toBeGreaterThan(0);
  });

  it('moves the close control toward the modal pointer', async () => {
    const wrapper = mountFooterDesktop();
    await wrapper.get('button[aria-label="Play our web design portfolio showcase video"]').trigger('click');
    const ball = wrapper.get('button[aria-label="Close video"]');
    const frame = requestAnimationFrame.mock.calls.at(-1)[0];

    await wrapper.get('[role="dialog"]').trigger('mousemove', { clientX: window.innerWidth, clientY: window.innerHeight });
    frame();

    const motion = gsap.to.mock.calls.find(([element]) => element === ball.element)[1];
    expect(motion.x).toBeGreaterThan(0);
    expect(motion.y).toBeGreaterThan(0);
  });

  // ── showModal watch effects ───────────────────────────────────────────────

  it('showModal watch sets body overflow to hidden when modal opens', async () => {
    const wrapper = mountFooterDesktop();

    await wrapper.find('button[aria-label="Play our web design portfolio showcase video"]').trigger('click');
    await nextTick();

    expect(document.body.style.overflow).toBe('hidden');
  });

  it('showModal watch restores body overflow when modal closes', async () => {
    const wrapper = mountFooterDesktop();

    await wrapper.find('button[aria-label="Play our web design portfolio showcase video"]').trigger('click');
    await nextTick();
    await wrapper.find('button[aria-label="Close video"]').trigger('click');
    await nextTick();

    expect(document.body.style.overflow).toBe('');
  });

  // ── lifecycle cleanup ─────────────────────────────────────────────────────

  it('onUnmounted calls cancelAnimationFrame when animationFrameId is set', () => {
    // Make RAF return a truthy id so the component stores it and cancels it on unmount
    requestAnimationFrame.mockReturnValueOnce(42);
    cancelAnimationFrame.mockClear();
    const wrapper = mountFooterDesktop();

    wrapper.unmount();

    expect(cancelAnimationFrame).toHaveBeenCalledWith(42);
  });

  it('onUnmounted disconnects the video IntersectionObserver', () => {
    const wrapper = mountFooterDesktop();
    const observerInstance =
      IntersectionObserver.mock.results[IntersectionObserver.mock.results.length - 1].value;
    expect(observerInstance.observed.has(wrapper.get('video[preload="auto"]').element)).toBe(true);

    wrapper.unmount();

    expect(observerInstance.observed.size).toBe(0);
  });

  // ── email CTA ─────────────────────────────────────────────────────────────

  it('opens the email contact dialog from its link', async () => {
    const wrapper = mountFooterDesktop();

    const emailLink = wrapper.find('a[aria-label="Email our web design team"]');
    await emailLink.trigger('click');

    expect(wrapper.get('[data-testid="footer-email-dialog"]').attributes('role')).toBe('dialog');
  });

  it('renders the Waiter legal strip in its overlay variant', () => {
    const wrapper = mountFooterDesktop();

    const strip = wrapper.get('[data-testid="legal-footer-stub"]');
    expect(strip.attributes('data-variant')).toBe('overlay');
  });
});
