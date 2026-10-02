import { defineComponent, nextTick, ref } from 'vue';
import { mount } from '@vue/test-utils';

jest.mock('../../composables/useSmoothScroll', () => ({
  smoothScrollTo: jest.fn(),
  smoothScrollToElement: jest.fn().mockResolvedValue(undefined),
}));

import InvestmentOnboarding from '../../components/BusinessProposal/InvestmentOnboarding.vue';

function mountInvestmentOnboarding(props = {}) {
  const Host = defineComponent({
    components: { InvestmentOnboarding },
    props: ['hasModules', 'language', 'proposalUuid'],
    setup() {
      const onboarding = ref(null);
      const start = () => onboarding.value?.start();
      return { onboarding, start };
    },
    template: '<button data-testid="start-onboarding" aria-label="Iniciar guía" @click="start" /><InvestmentOnboarding ref="onboarding" :has-modules="hasModules" :language="language" :proposal-uuid="proposalUuid" />',
  });
  return mount(Host, {
    props: { hasModules: true, ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
      },
    },
  });
}

describe('InvestmentOnboarding', () => {
  let targetBtn;
  let originalGetComputedStyle;

  beforeEach(() => {
    localStorage.clear();
    jest.useFakeTimers();

    // jsdom's CSSStyleDeclaration is not iterable; cloneTarget uses for...of on it
    originalGetComputedStyle = window.getComputedStyle;
    window.getComputedStyle = () => ({
      [Symbol.iterator]: function* () {},
      getPropertyValue: () => '',
    });

    targetBtn = document.createElement('button');
    targetBtn.className = 'customize-investment-btn';
    document.body.appendChild(targetBtn);
  });

  afterEach(() => {
    jest.useRealTimers();
    window.getComputedStyle = originalGetComputedStyle;
    if (targetBtn && targetBtn.parentNode) {
      document.body.removeChild(targetBtn);
    }
  });

  it('mounts without errors', () => {
    const wrapper = mountInvestmentOnboarding();

    expect(wrapper.exists()).toBe(true);
  });

  it('is hidden initially', () => {
    const wrapper = mountInvestmentOnboarding();

    expect(wrapper.text()).toBe('');
  });

  it('shows the step title after start() when target element is in DOM', async () => {
    const wrapper = mountInvestmentOnboarding();

    await wrapper.get('[data-testid="start-onboarding"]').trigger('click');
    jest.runAllTimers();
    await nextTick();

    expect(wrapper.text()).toContain('Explora módulos adicionales');
  });

  it('shows English step title when language is en', async () => {
    const wrapper = mountInvestmentOnboarding({ language: 'en' });

    await wrapper.get('[data-testid="start-onboarding"]').trigger('click');
    jest.runAllTimers();
    await nextTick();

    expect(wrapper.text()).toContain('Explore additional modules');
  });

  it('emits complete when skip button is clicked', async () => {
    const wrapper = mountInvestmentOnboarding();

    await wrapper.get('[data-testid="start-onboarding"]').trigger('click');
    jest.runAllTimers();
    await nextTick();

    const skipBtn = wrapper.findAll('button').find(b => b.text() === 'Omitir');
    await skipBtn.trigger('click');

    expect(wrapper.getComponent(InvestmentOnboarding).emitted('complete')).toEqual([[]]);
  });
});
