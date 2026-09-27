import { defineComponent, h } from 'vue';
import { mount } from '@vue/test-utils';
import ProposalViewGateway from '../../components/BusinessProposal/ProposalViewGateway.vue';

let interactionOrder;

const ExplainerVideoCardStub = defineComponent({
  name: 'ExplainerVideoCard',
  setup(_props, { expose }) {
    expose({ pause: () => interactionOrder.push('pause') });
    return () => h('section', { 'data-testid': 'proposal-explainer-card' }, 'Video de bienvenida');
  },
});

function mountGateway(props = {}) {
  return mount(ProposalViewGateway, {
    props: {
      language: 'es',
      clientName: '',
      showTechnical: false,
      showLegal: false,
      onSelect: (mode) => interactionOrder.push(`select:${mode}`),
      ...props,
    },
    global: { stubs: { ExplainerVideoCard: ExplainerVideoCardStub } },
  });
}

describe('ProposalViewGateway', () => {
  beforeEach(() => {
    interactionOrder = [];
  });

  it('renders the Spanish heading text by default', () => {
    // Fails if the public gateway loses its default Spanish introduction.
    const wrapper = mountGateway();

    expect(wrapper.get('h2').text()).toBe('¿Cómo prefieres explorar esta propuesta?');
  });

  it('emits select with "executive" when the executive card is clicked', async () => {
    // Fails if the executive option stops selecting its public proposal mode.
    const wrapper = mountGateway();

    await wrapper.get('[data-testid="gateway-executive-card"]').trigger('click');

    expect(wrapper.emitted('select')).toEqual([['executive']]);
  });

  it('emits select with "detailed" when the detailed card is clicked', async () => {
    // Fails if the complete proposal option stops selecting its public mode.
    const wrapper = mountGateway();

    await wrapper.get('[data-testid="gateway-detailed-card"]').trigger('click');

    expect(wrapper.emitted('select')).toEqual([['detailed']]);
  });

  it.each([
    [0, false],
    [1, true],
  ])('renders %i technical destinations when visibility is %s', (expectedCount, showTechnical) => {
    // Fails if a customer is shown a technical route without technical content, or loses an available route.
    const wrapper = mountGateway({ showTechnical });

    const cards = wrapper.findAll('[data-testid="gateway-technical-card"]');
    expect(cards).toHaveLength(expectedCount);
  });

  it('emits select with "technical" when the technical card is clicked', async () => {
    // Fails if the technical option no longer opens technical proposal content.
    const wrapper = mountGateway({ showTechnical: true });

    await wrapper.find('[data-testid="gateway-technical-card"]').trigger('click');

    expect(wrapper.emitted('select')).toEqual([['technical']]);
  });

  it.each([
    [0, false],
    [1, true],
  ])('renders %i legal destinations when visibility is %s', (expectedCount, showLegal) => {
    // Fails if a customer is shown a contract route without legal content, or loses an available route.
    const wrapper = mountGateway({ showLegal });

    const cards = wrapper.findAll('[data-testid="gateway-legal-card"]');
    expect(cards).toHaveLength(expectedCount);
  });

  it('emits select with "legal" when the legal card is clicked', async () => {
    // Fails if the legal option no longer opens the contract content.
    const wrapper = mountGateway({ showLegal: true });

    await wrapper.find('[data-testid="gateway-legal-card"]').trigger('click');

    expect(wrapper.emitted('select')).toEqual([['legal']]);
  });

  it.each([
    ['technical', { showTechnical: false, showLegal: true }],
    ['legal', { showTechnical: true, showLegal: false }],
  ])('hides the welcome video when %s is unavailable', (_unavailable, availability) => {
    // Fails if the guide appears while one of its four customer destinations is unavailable.
    const wrapper = mountGateway({ showExplainerVideo: true, ...availability });

    expect(wrapper.findAll('[data-testid="proposal-explainer-card"]')).toHaveLength(0);
  });

  it('renders the welcome video with every public destination available', () => {
    // Fails if the enabled welcome guide disappears from a complete Spanish proposal.
    const wrapper = mountGateway({ showExplainerVideo: true, showTechnical: true, showLegal: true });

    expect(wrapper.get('[data-testid="proposal-explainer-card"]').text()).toBe('Video de bienvenida');
  });

  it('pauses the welcome video before changing the selected mode', async () => {
    // Fails if video audio continues after the customer enters the proposal.
    const wrapper = mountGateway({ showExplainerVideo: true, showTechnical: true, showLegal: true });

    await wrapper.get('[data-testid="gateway-executive-card"]').trigger('click');

    expect(interactionOrder).toEqual(['pause', 'select:executive']);
  });

  it('renders the English heading text when language is "en"', () => {
    // Fails if the selected proposal locale falls back to Spanish gateway copy.
    const wrapper = mountGateway({ language: 'en' });

    expect(wrapper.get('h2').text()).toBe('How would you like to explore this proposal?');
  });
});
