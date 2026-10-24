import { mount } from '@vue/test-utils';
import BaseRichTextContent from '../../components/base/BaseRichTextContent.vue';

jest.mock('../../composables/useSectionAnimations', () => ({
  useSectionAnimations: jest.fn(),
}));

jest.mock('../../utils/technicalProposalPanels', () => ({
  technicalFragmentHasContent: jest.fn(() => true),
  technicalFragmentSummary: jest.fn((fragment, doc, lang) => (lang === 'en'
    ? { stack: '7 layers', architecture: '5 patterns', epics: '6 modules · 38 requirements' }
    : { stack: '7 capas', architecture: '5 patrones', epics: '6 módulos · 38 requerimientos' }
  )[fragment] || ''),
  FRAGMENT_ORDER: ['intro', 'stack', 'architecture'],
  TECH_PANEL_TITLES: {
    es: { intro: 'Introducción', stack: 'Stack Técnico', architecture: 'Arquitectura' },
    en: { intro: 'Introduction', stack: 'Tech Stack', architecture: 'Architecture' },
  },
  TECH_READING_TIME: { es: '~30 min de lectura', en: '~30 min read' },
}));

import TechnicalDocumentPublicPanel from '../../components/BusinessProposal/TechnicalDocumentPublicPanel.vue';

function mountPanel(props = {}) {
  return mount(TechnicalDocumentPublicPanel, {
    props: { fragment: 'intro', contentJson: {}, language: 'es', ...props },
    global: { components: { BaseRichTextContent }, stubs: { Teleport: true } },
  });
}

describe('TechnicalDocumentPublicPanel', () => {
  it('renders the section element', () => {
    const wrapper = mountPanel();

    expect(wrapper.find('section').exists()).toBe(true);
  });

  it('renders the intro heading when fragment is intro', () => {
    const wrapper = mountPanel({ fragment: 'intro' });

    expect(wrapper.text()).toContain('Introducción');
  });

  it('renders the stack heading when fragment is stack', () => {
    const wrapper = mountPanel({ fragment: 'stack' });

    expect(wrapper.text()).toContain('Stack Técnico');
  });

  it('renders English intro heading when language is en', () => {
    const wrapper = mountPanel({ fragment: 'intro', language: 'en' });

    expect(wrapper.text()).toContain('Introduction');
  });

  it('renders the stack table when fragment is stack', () => {
    const wrapper = mountPanel({ fragment: 'stack' });

    expect(wrapper.find('table').exists()).toBe(true);
  });

  describe('intro cover index', () => {
    it('renders one card per listed fragment, excluding intro itself', () => {
      const wrapper = mountPanel({ fragment: 'intro' });
      const cards = wrapper.findAll('[data-testid="tech-index-card"]');

      expect(cards).toHaveLength(2);
      expect(cards[0].text()).toContain('Stack Técnico');
      expect(cards[1].text()).toContain('Arquitectura');
    });

    it('shows how much each section weighs', () => {
      const wrapper = mountPanel({ fragment: 'intro' });
      const cards = wrapper.findAll('[data-testid="tech-index-card"]');

      expect(cards[0].text()).toContain('7 capas');
      expect(cards[1].text()).toContain('5 patrones');
    });

    it('emits navigate with the fragment key when a card is clicked', async () => {
      const wrapper = mountPanel({ fragment: 'intro' });

      await wrapper.findAll('[data-testid="tech-index-card"]')[1].trigger('click');

      expect(wrapper.emitted('navigate')).toEqual([['architecture']]);
    });

    it('summarises section count, product scope and reading time', () => {
      const wrapper = mountPanel({ fragment: 'intro' });

      expect(wrapper.get('[data-testid="tech-cover-stats"]').text())
        .toBe('2 secciones · 6 módulos · 38 requerimientos · ~30 min de lectura');
    });

    it('summarises in English when language is en', () => {
      const wrapper = mountPanel({ fragment: 'intro', language: 'en' });

      expect(wrapper.get('[data-testid="tech-cover-stats"]').text())
        .toBe('2 sections · 6 modules · 38 requirements · ~30 min read');
    });

    it('renders the deck position when index is provided', () => {
      const wrapper = mountPanel({ fragment: 'intro', index: '01' });

      expect(wrapper.get('[data-testid="tech-cover-index"]').text()).toBe('01');
    });

    it('omits the deck position when no index is provided', () => {
      const wrapper = mountPanel({ fragment: 'intro' });

      expect(wrapper.find('[data-testid="tech-cover-index"]').exists()).toBe(false);
    });

    it('does not render the index outside the intro fragment', () => {
      const wrapper = mountPanel({ fragment: 'stack' });

      expect(wrapper.find('[data-testid="tech-index-card"]').exists()).toBe(false);
    });
  });
});
