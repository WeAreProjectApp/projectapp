/**
 * SectionPreviewModal — functional-requirements preview wiring.
 *
 * The preview must surface the same "Ver requerimientos (N)" affordance the
 * public proposal shows, built from the proposal's technical_document.
 */
import { mount } from '@vue/test-utils';

// marked is ESM-only (jest cannot parse it) and only feeds paste-mode raw
// sections, which these tests never render.
jest.mock('marked', () => {
  const render = (src) => src || '';
  render.parse = render;
  return { ...jest.requireActual('marked'), marked: render };
});

import SectionPreviewModal from '../../components/BusinessProposal/admin/SectionPreviewModal.vue';

const FR_SECTION = {
  section_type: 'functional_requirements',
  content_json: {
    title: 'Requerimientos Funcionales',
    intro: '',
    groups: [
      {
        id: 'views',
        icon: '🖥️',
        title: 'Vistas',
        description: 'Pantallas del sitio.',
        is_visible: true,
        items: [
          { id: 'item-views-home', icon: '🏠', name: 'Home', description: 'Landing.' },
        ],
      },
    ],
    additionalModules: [],
  },
};

const TECH_SECTION = {
  section_type: 'technical_document',
  content_json: {
    epics: [
      {
        epicKey: 'views',
        title: 'Vistas',
        requirements: [
          {
            flowKey: 'req-home',
            title: 'Home dinámico con secciones administrables',
            description: 'Secciones editables desde el panel.',
            priority: 'high',
            linked_item_ids: ['item-views-home'],
          },
          {
            flowKey: 'req-home-estados',
            title: 'Estados vacío y de error del Home',
            description: 'Comportamiento sin contenido cargado.',
            priority: 'medium',
            linked_item_ids: ['item-views-home'],
          },
        ],
      },
    ],
  },
};

function mountPreview(proposalData) {
  return mount(SectionPreviewModal, {
    props: { visible: true, section: FR_SECTION, proposalData },
    global: { stubs: { teleport: true, transition: false } },
  });
}

describe('SectionPreviewModal — functional requirements preview', () => {
  it('shows the linked-requirements count from the technical document', async () => {
    const wrapper = mountPreview({ sections: [FR_SECTION, TECH_SECTION] });

    // quality: allow-fragile-selector (overview-card is the established hook shared with FunctionalRequirements tests and RequirementsOnboarding)
    await wrapper.find('.overview-card').trigger('click');

    expect(wrapper.text()).toContain('Ver requerimientos (2)');
  });

  it('shows no requirements link when the proposal has no technical document', async () => {
    const wrapper = mountPreview({ sections: [FR_SECTION] });

    // quality: allow-fragile-selector (overview-card is the established hook shared with FunctionalRequirements tests and RequirementsOnboarding)
    await wrapper.find('.overview-card').trigger('click');

    expect(wrapper.text()).toContain('Home');
    expect(wrapper.text()).not.toContain('Ver requerimientos');
  });
});
