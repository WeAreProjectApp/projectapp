import { mount } from '@vue/test-utils';

jest.mock('../../composables/useSectionAnimations', () => ({
  useSectionAnimations: jest.fn(),
}));

import ProposalSummary from '../../components/BusinessProposal/ProposalSummary.vue';

function mountSummary(props = {}) {
  return mount(ProposalSummary, { props });
}

describe('ProposalSummary', () => {
  it('renders the section title from content.title', () => {
    const wrapper = mountSummary({ content: { title: 'Resumen del Proyecto' } });

    expect(wrapper.text()).toContain('Resumen del Proyecto');
  });

  it('renders the subtitle when content.subtitle is provided', () => {
    const wrapper = mountSummary({ content: { title: 'Resumen', subtitle: 'Todo lo que necesitas saber.' } });

    expect(wrapper.text()).toContain('Todo lo que necesitas saber.');
  });

  it('hides the subtitle when content.subtitle is absent', () => {
    const wrapper = mountSummary({ content: { title: 'Resumen' } });

    expect(wrapper.find('p.text-esmerald\\/70').exists()).toBe(false);
  });

  it('renders auto-generated cards when no content.cards are provided', () => {
    const wrapper = mountSummary({ content: {} });

    // Auto-generates only genuinely universal proposal benefits.
    expect(wrapper.findAll('.summary-card').length).toBeGreaterThan(0);
  });

  it('does not invent a reports and analytics card', () => {
    const wrapper = mountSummary({ content: {} });

    expect(wrapper.findAll('[data-testid="proposal-summary-card"]')).toHaveLength(2);
    expect(wrapper.text()).not.toContain('Reportes y analítica');
  });

  it('renders an explicit reports card from proposal content', () => {
    const wrapper = mountSummary({
      content: {
        cards: [{
          icon: '📊',
          title: 'Reportes contratados',
          source: 'analytics_dashboard',
          description: 'Incluidos expresamente en este alcance.',
        }],
      },
    });

    expect(wrapper.text()).toContain('Reportes contratados');
  });

  it('renders investment modules card when investmentModules are provided', () => {
    const wrapper = mountSummary({
      content: {},
      investmentModules: [{ id: 1 }, { id: 2 }],
    });

    expect(wrapper.text()).toContain('2');
  });

  describe('total_investment card description sync', () => {
    const investmentCardContent = (description) => ({
      cards: [
        {
          icon: '💰',
          title: 'Inversión',
          source: 'total_investment',
          description,
        },
      ],
    });

    it('rewrites a stale taxed amount with the supplied agreed investment plus IVA', () => {
      const wrapper = mountSummary({
        content: investmentCardContent('Monto total del proyecto: $4.900.000 COP más IVA.'),
        proposal: { total_investment: 3200000, currency: 'COP' },
        investmentTotal: 4320000,
      });

      const card = wrapper.get('[data-testid="proposal-summary-card"]');
      expect(card.text()).toContain('$4.320.000 COP + IVA');
      expect(card.text()).not.toContain('$4.900.000');
      expect(card.text()).not.toContain('más IVA');
    });

    it('falls back to proposal.total_investment when no agreed investment is supplied', () => {
      const wrapper = mountSummary({
        content: investmentCardContent('Monto total del proyecto: $4.900.000 COP.'),
        proposal: { total_investment: 3200000, currency: 'COP' },
        investmentTotal: null,
      });

      const card = wrapper.get('[data-testid="proposal-summary-card"]');
      expect(card.text()).toContain('$3.200.000 COP + IVA');
      expect(card.text()).not.toContain('$4.900.000');
    });

    it('preserves narrative text when there is no monetary amount in the description', () => {
      const wrapper = mountSummary({
        content: investmentCardContent('Inversión total acordada para el proyecto.'),
        proposal: { total_investment: 3200000, currency: 'COP' },
        investmentTotal: 4320000,
      });

      const card = wrapper.get('[data-testid="proposal-summary-card"]');
      expect(card.text()).toContain('Inversión total acordada para el proyecto.');
      expect(card.text()).toContain('$4.320.000 COP');
    });
  });
});
