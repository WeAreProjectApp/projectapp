import { defineComponent, h, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import GatewayGuide from '../../components/BusinessProposal/GatewayGuide.vue';

let receivedSteps;

const PublicGuidedTourStub = defineComponent({
  props: ['steps'],
  setup(props, { expose }) {
    receivedSteps = props.steps;
    expose({ start: jest.fn(), forceStart: jest.fn() });
    return () => h('div', { 'data-testid': 'guided-tour-step-count' }, String(props.steps.length));
  },
});

const BaseButtonStub = defineComponent({
  inheritAttrs: false,
  props: ['as', 'to'],
  emits: ['click'],
  setup(props, { attrs, emit, slots }) {
    const tag = props.as === 'a' ? 'a' : 'button';
    return () => h(tag, {
      ...attrs,
      ...(props.as === 'a' ? { href: props.to } : {}),
      onClick: () => emit('click'),
    }, slots.default?.());
  },
});

function mountGuide(props = {}) {
  return mount(GatewayGuide, {
    props: { language: 'es', ...props },
    global: {
      stubs: {
        PublicGuidedTour: PublicGuidedTourStub,
        BaseButton: BaseButtonStub,
      },
    },
  });
}

describe('GatewayGuide', () => {
  it.each([
    ['es', '/es-co/additional-modules', '/es-co/partnership-program'],
    ['en', '/en-us/additional-modules', '/en-us/partnership-program'],
  ])('uses %s public links in a new browser tab', async (language, modulesHref, allianceHref) => {
    // Fails if the public gateway loses its locale or leaves the proposal in the current tab.
    const wrapper = mountGuide({ language });
    await nextTick();

    expect(wrapper.get('[data-testid="gateway-modules-link"]').attributes()).toMatchObject({
      href: modulesHref, target: '_blank', rel: 'noopener noreferrer',
    });
    expect(wrapper.get('[data-testid="gateway-alliance-link"]').attributes()).toMatchObject({
      href: allianceHref, target: '_blank', rel: 'noopener noreferrer',
    });
  });

  it('adds the two public actions to the guided tour', async () => {
    // Fails if the walkthrough omits either additional public destination.
    mountGuide();
    await nextTick();

    expect(receivedSteps.map((step) => step.target)).toEqual([
      '[data-testid="proposal-explainer-card"]',
      '[data-testid="gateway-executive-card"]',
      '[data-testid="gateway-detailed-card"]',
      '[data-testid="gateway-technical-card"]',
      '[data-testid="gateway-legal-card"]',
      '[data-testid="gateway-modules-link"]',
      '[data-testid="gateway-alliance-link"]',
      '[data-testid="gateway-restart-guide"]',
    ]);
  });


});
