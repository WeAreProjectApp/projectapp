import { mount } from '@vue/test-utils';

jest.mock('marked', () => ({ ...jest.requireActual('marked'), marked: jest.fn((text) => text) }));
jest.mock('dompurify', () => ({ sanitize: jest.fn((val) => val) }));

// Stub all BusinessProposal section components imported from the barrel
jest.mock('../../components/BusinessProposal', () => ({
  Greeting: { template: '<div>Greeting</div>' },
  ExecutiveSummary: { template: '<div>ExecutiveSummary</div>' },
  ContextDiagnostic: { template: '<div>ContextDiagnostic</div>' },
  ConversionStrategy: { template: '<div>ConversionStrategy</div>' },
  DesignUX: { template: '<div>DesignUX</div>' },
  CreativeSupport: { template: '<div>CreativeSupport</div>' },
  DevelopmentStages: { template: '<div>DevelopmentStages</div>' },
  FunctionalRequirements: { template: '<div>FunctionalRequirements</div>' },
  Timeline: { template: '<div>Timeline</div>' },
  Investment: { template: '<div>Investment</div>' },
  FinalNote: { template: '<div>FinalNote</div>' },
  NextSteps: { template: '<div>NextSteps</div>' },
}));

jest.mock('../../composables/useSectionAnimations', () => ({
  useSectionAnimations: jest.fn(),
}));

import SectionPreviewModal from '../../components/BusinessProposal/admin/SectionPreviewModal.vue';

function mountSectionPreviewModal(props = {}) {
  return mount(SectionPreviewModal, {
    props: {
      visible: true,
      section: {},
      proposalData: {},
      subSection: null,
      ...props,
    },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        RawContentSection: { template: '<div>RawContent</div>' },
        FunctionalRequirementsGroup: { template: '<div>FRGroup</div>' },
      },
    },
  });
}

describe('SectionPreviewModal', () => {
  it('renders the preview panel when visible', () => {
    const wrapper = mountSectionPreviewModal();

    expect(wrapper.find('.preview-panel').exists()).toBe(true);
  });

  it('shows the no-preview fallback when section has no known type', () => {
    const wrapper = mountSectionPreviewModal({
      section: { section_type: 'unknown_type', content_json: {} },
    });

    expect(wrapper.text()).toContain('No hay vista previa disponible');
  });

  it('emits close when close button is clicked', async () => {
    const wrapper = mountSectionPreviewModal();

    await wrapper.find('button').trigger('click');

    expect(wrapper.emitted('close')).toBeTruthy();
  });

  it('does not render the preview panel when visible is false', () => {
    const wrapper = mountSectionPreviewModal({ visible: false });

    expect(wrapper.find('.preview-panel').exists()).toBe(false);
  });
});
