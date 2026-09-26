/**
 * Tests for AttachFromDocumentsModal component.
 *
 * Covers: renders when open, empty state, proposal docs list, diagnostic docs list
 * (NDA + templates + attachments), selection, confirm emit, cancel emit, preselected keys.
 */
import { mount } from '@vue/test-utils';
import AttachFromDocumentsModal from '../../components/AttachFromDocumentsModal.vue';

const baseProposal = {
  id: 1,
  uuid: 'abc',
  client_name: 'Acme',
  proposal_documents: [],
};

const proposalWithContract = {
  ...baseProposal,
  proposal_documents: [
    {
      id: 10,
      document_type: 'contract',
      document_type_display: 'Contrato',
      title: 'Contrato de desarrollo',
      is_generated: true,
    },
    {
      id: 11,
      document_type: 'amendment',
      document_type_display: 'Otrosí',
      title: 'Otrosí #1',
      is_generated: false,
    },
  ],
};

const baseDiagnostic = {
  id: 5,
  client_name: 'TechCorp',
  attachments: [],
};

const diagnosticWithNda = {
  ...baseDiagnostic,
  attachments: [
    {
      id: 20,
      document_type: 'confidentiality_agreement',
      document_type_display: 'Acuerdo de confidencialidad',
      title: 'Acuerdo NDA',
      is_generated: true,
    },
    {
      id: 21,
      document_type: 'other',
      document_type_display: 'Otro',
      title: 'Informe técnico',
      is_generated: false,
    },
  ],
};

const sampleTemplates = [
  { slug: 'diagnostico-aplicacion', title: 'Diagnóstico de Aplicación', filename: 'diagnostico_aplicacion_es.md' },
  { slug: 'diagnostico-tecnico', title: 'Diagnóstico Técnico', filename: 'diagnostico_tecnico_es.md' },
];

function mountModal(props = {}) {
  return mount(AttachFromDocumentsModal, {
    props: {
      open: true,
      source: 'proposal',
      entity: baseProposal,
      ...props,
    },
  });
}

describe('AttachFromDocumentsModal', () => {
  it('renders nothing when open is false', () => {
    const wrapper = mountModal({ open: false });
    expect(wrapper.find('[class*="fixed inset-0"]').exists()).toBe(false);
  });

  it('renders the modal header when open is true', () => {
    const wrapper = mountModal();
    expect(wrapper.text()).toContain('Adjuntar desde Documentos');
  });

  it('shows empty state when source is unknown', () => {
    const wrapper = mountModal({ entity: baseProposal, source: 'unknown_type' });
    expect(wrapper.text()).toContain('No hay documentos disponibles');
  });

  describe('proposal source', () => {
    it('shows commercial and technical PDF items always', () => {
      const wrapper = mountModal({ entity: baseProposal, source: 'proposal' });
      expect(wrapper.text()).toContain('Propuesta comercial (PDF)');
      expect(wrapper.text()).toContain('Detalle técnico (PDF)');
    });

    it('shows contract and draft items when a generated contract doc exists', () => {
      const wrapper = mountModal({ entity: proposalWithContract, source: 'proposal' });
      expect(wrapper.text()).toContain('Contrato de desarrollo (PDF)');
      expect(wrapper.text()).toContain('Contrato de desarrollo (borrador)');
    });

    it('does not show contract items when no contract doc exists', () => {
      const wrapper = mountModal({ entity: baseProposal, source: 'proposal' });
      expect(wrapper.text()).not.toContain('Contrato de desarrollo (PDF)');
    });

    it('shows non-contract uploaded proposal documents', () => {
      const wrapper = mountModal({ entity: proposalWithContract, source: 'proposal' });
      expect(wrapper.text()).toContain('Otrosí #1');
    });

    it('offers the product and service contracts of a split closing by name', async () => {
      // Falla si un cierre separado adjunta el contrato único o un contrato sin nombrar.
      const entity = {
        ...proposalWithContract,
        contract_modality: 'split',
        proposal_documents: [
          ...proposalWithContract.proposal_documents,
          { id: 12, document_type: 'contract_product', title: 'Contrato de producto', is_generated: true },
          { id: 13, document_type: 'contract_service', title: 'Contrato de servicio', is_generated: true },
        ],
      };
      const wrapper = mountModal({ entity, source: 'proposal', preselected: ['contract_pdf:service'] });
      await wrapper.vm.$nextTick();
      const confirmBtn = wrapper.findAll('button').find(b => b.text().includes('Adjuntar'));
      await confirmBtn.trigger('click');

      expect(wrapper.text()).not.toContain('Contrato de desarrollo (PDF)');
      expect(wrapper.text()).toContain('Contrato de producto (borrador)');
      expect(wrapper.emitted('attach')[0][0].map(item => item.ref)).toEqual([
        { source: 'contract_pdf', variant: 'service' },
      ]);
    });
  });

  describe('diagnostic source', () => {
    it('shows NDA final and draft items when a generated NDA attachment exists', () => {
      const wrapper = mountModal({
        source: 'diagnostic',
        entity: diagnosticWithNda,
        templates: [],
      });
      expect(wrapper.text()).toContain('Acuerdo de confidencialidad (PDF)');
      expect(wrapper.text()).toContain('Acuerdo de confidencialidad (borrador)');
    });

    it('does not show NDA items when no generated NDA attachment', () => {
      const wrapper = mountModal({
        source: 'diagnostic',
        entity: baseDiagnostic,
        templates: [],
      });
      expect(wrapper.text()).not.toContain('Acuerdo de confidencialidad');
    });

    it('renders each template as a list item', () => {
      const wrapper = mountModal({
        source: 'diagnostic',
        entity: baseDiagnostic,
        templates: sampleTemplates,
      });
      expect(wrapper.text()).toContain('Diagnóstico de Aplicación');
      expect(wrapper.text()).toContain('Diagnóstico Técnico');
    });

    it('renders non-NDA uploaded attachments', () => {
      const wrapper = mountModal({
        source: 'diagnostic',
        entity: diagnosticWithNda,
        templates: [],
      });
      expect(wrapper.text()).toContain('Informe técnico');
    });

    it('does not render the NDA attachment as an uploaded item', () => {
      const wrapper = mountModal({
        source: 'diagnostic',
        entity: diagnosticWithNda,
        templates: [],
      });
      const items = wrapper.findAll('li');
      const ndaAttachmentItems = items.filter(li =>
        li.text().includes('Acuerdo NDA') && !li.text().includes('PDF'),
      );
      expect(ndaAttachmentItems).toHaveLength(0);
    });
  });

  describe('selection and confirm', () => {
    it('confirm button is disabled when nothing is selected', () => {
      const wrapper = mountModal({ entity: proposalWithContract, source: 'proposal' });
      const confirmBtn = wrapper.findAll('button').find(b => b.text().includes('Adjuntar'));
      expect(confirmBtn.attributes('disabled')).toBeDefined();
    });

    it('confirm button is enabled after checking an item', async () => {
      const wrapper = mountModal({ entity: proposalWithContract, source: 'proposal' });
      const checkbox = wrapper.find('input[type="checkbox"]');
      await checkbox.trigger('change');
      await checkbox.setValue(true);
      const confirmBtn = wrapper.findAll('button').find(b => b.text().includes('Adjuntar'));
      expect(confirmBtn.attributes('disabled')).toBeUndefined();
    });

    it('emits attach and close with the selected refs on confirm', async () => {
      const wrapper = mountModal({ entity: proposalWithContract, source: 'proposal' });
      const firstCheckbox = wrapper.find('input[type="checkbox"]');
      await firstCheckbox.setValue(true);
      const confirmBtn = wrapper.findAll('button').find(b => b.text().includes('Adjuntar'));
      await confirmBtn.trigger('click');
      expect(wrapper.emitted('attach')).toBeTruthy();
      expect(wrapper.emitted('close')).toBeTruthy();
      const [picked] = wrapper.emitted('attach')[0];
      expect(Array.isArray(picked)).toBe(true);
      expect(picked.length).toBeGreaterThan(0);
      expect(picked[0]).toHaveProperty('key');
      expect(picked[0]).toHaveProperty('label');
      expect(picked[0]).toHaveProperty('ref');
    });

    it('emits close when cancel button is clicked', async () => {
      const wrapper = mountModal({ entity: proposalWithContract, source: 'proposal' });
      const cancelBtn = wrapper.findAll('button').find(b => b.text() === 'Cancelar');
      await cancelBtn.trigger('click');
      expect(wrapper.emitted('close')).toBeTruthy();
    });

    it('emits close when backdrop is clicked', async () => {
      const wrapper = mountModal({ entity: proposalWithContract, source: 'proposal' });
      const backdrop = wrapper.find('[class*="fixed inset-0"]');
      await backdrop.trigger('click');
      expect(wrapper.emitted('close')).toBeTruthy();
    });
  });

  describe('preselected', () => {
    it('pre-checks items matching the preselected keys', async () => {
      const wrapper = mountModal({
        entity: proposalWithContract,
        source: 'proposal',
        preselected: ['commercial_pdf'],
        open: true,
      });
      const checkboxes = wrapper.findAll('input[type="checkbox"]');
      const checked = checkboxes.filter(cb => cb.element.checked);
      expect(checked.length).toBeGreaterThan(0);
    });
  });
});
