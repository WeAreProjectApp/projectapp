import { flushPromises, mount } from '@vue/test-utils';

const mockFormalizationStore = {
  options: jest.fn(),
  prepare: jest.fn(),
  send: jest.fn(),
  detail: jest.fn(),
  file: jest.fn(),
};

jest.mock('../../stores/proposal_formalization', () => ({
  useProposalFormalizationStore: () => mockFormalizationStore,
}));

import ProposalFormalizationModal from '../../components/BusinessProposal/admin/ProposalFormalizationModal.vue';

const proposal = {
  id: 55,
  client_email: 'legal@acme.test',
};

const defaults = {
  subject: 'Documentación para formalizar Acme',
  greeting: 'Hola equipo Acme,',
  body: 'Adjuntamos los documentos para la firma.',
  footer: 'Quedamos atentos.',
};

const preparedPackage = {
  id: 'prep-77',
  status: 'prepared',
  recipient_emails: ['legal@acme.test'],
  cc_emails: [],
  subject: defaults.subject,
  html_preview: '<main>Correo congelado para revisión</main>',
  files: [
    {
      key: 'contract',
      filename: 'Contrato Acme.pdf',
      mime_type: 'application/pdf',
      url: '/api/proposals/55/formalization/files/701/',
    },
    {
      key: 'commercial',
      filename: 'Propuesta comercial Acme.pdf',
      mime_type: 'application/pdf',
      url: '/api/proposals/55/formalization/files/702/',
    },
  ],
};

const EmailRecipientFieldsStub = {
  name: 'EmailRecipientFields',
  props: ['toRecipients', 'ccRecipients'],
  emits: ['update:toRecipients', 'update:ccRecipients'],
  template: `
    <div data-testid="formalization-recipients">
      <input
        data-testid="formalization-recipients-to"
        :value="toRecipients[0]?.email || ''"
        @input="$emit('update:toRecipients', $event.target.value ? [{ email: $event.target.value }] : [])"
      >
    </div>
  `,
};

function availableDocuments(overrides = {}) {
  return [
    { key: 'contract', label: 'Contrato', description: 'Contrato final', available: true },
    { key: 'commercial', label: 'Comercial', description: 'Alcance comercial', available: true },
    { key: 'technical', label: 'Técnico', description: 'Alcance técnico', available: true },
    ...overrides.documents || [],
  ];
}

function mountModal() {
  return mount(ProposalFormalizationModal, {
    props: { proposal, documents: [] },
    global: {
      stubs: {
        BaseModal: { template: '<div><slot /></div>' },
        BaseButton: {
          props: ['disabled', 'loading', 'type'],
          emits: ['click'],
          template: '<button :type="type || \'button\'" :disabled="disabled || loading" @click="$emit(\'click\', $event)"><slot /></button>',
        },
        EmailRecipientFields: EmailRecipientFieldsStub,
      },
    },
  });
}

async function renderEditableModal(options = {}) {
  mockFormalizationStore.options.mockResolvedValue({
    documents: availableDocuments(options),
    defaults,
  });
  const wrapper = mountModal();
  await flushPromises();
  return wrapper;
}

async function renderPreparedModal() {
  const wrapper = await renderEditableModal();
  mockFormalizationStore.prepare.mockResolvedValue(structuredClone(preparedPackage));
  await wrapper.get('[data-testid="formalization-prepare"]').trigger('click');
  await flushPromises();
  return wrapper;
}

describe('ProposalFormalizationModal', () => {
  beforeEach(() => {
    Object.values(mockFormalizationStore).forEach((method) => method.mockReset());
  });

  it('requires an unavailable default document to be deselected before preparing the reduced package', async () => {
    // Catches a regression that submits an unavailable PDF instead of allowing a valid reduced package.
    const wrapper = await renderEditableModal({
      documents: [{
        key: 'technical',
        label: 'Técnico',
        description: 'Alcance técnico',
        available: false,
        error: 'Falta la arquitectura.',
      }],
    });
    mockFormalizationStore.prepare.mockResolvedValue(preparedPackage);

    expect(wrapper.get('[data-testid="formalization-prepare"]').attributes('disabled')).toBe('');

    await wrapper.get('[data-testid="formalization-select-technical"]').setValue(false);
    await wrapper.get('[data-testid="formalization-prepare"]').trigger('click');
    await flushPromises();

    expect(mockFormalizationStore.prepare).toHaveBeenCalledWith(55, {
      ...defaults,
      documents: ['contract', 'commercial'],
      additional_doc_ids: [],
      recipient_emails: ['legal@acme.test'],
      cc_emails: [],
      sections: [],
    });
  });

  it('preselects both separate contracts when the deal closes with two documents', async () => {
    // Falla si el correo de un cierre separado omite el contrato de producto o el de servicio.
    mockFormalizationStore.options.mockResolvedValue({
      documents: [
        { key: 'contract_product', label: 'Contrato de producto', description: 'Producto', available: true },
        { key: 'contract_service', label: 'Contrato de servicio', description: 'Servicio', available: true },
        { key: 'commercial', label: 'Comercial', description: 'Alcance comercial', available: true },
        { key: 'technical', label: 'Técnico', description: 'Alcance técnico', available: true },
      ],
      defaults,
    });
    mockFormalizationStore.prepare.mockResolvedValue(preparedPackage);
    const wrapper = mountModal();
    await flushPromises();

    await wrapper.get('[data-testid="formalization-prepare"]').trigger('click');
    await flushPromises();

    expect(mockFormalizationStore.prepare.mock.calls[0][1].documents).toEqual([
      'contract_product', 'contract_service', 'commercial', 'technical',
    ]);
  });

  it('keeps generated contracts out of the extra attachments', async () => {
    // Falla si un contrato generado se ofrece además como adjunto adicional.
    mockFormalizationStore.options.mockResolvedValue({ documents: availableDocuments(), defaults });
    const wrapper = mount(ProposalFormalizationModal, {
      props: {
        proposal,
        documents: [
          { id: 7, document_type: 'contract_service', title: 'Contrato de servicio' },
          { id: 8, document_type: 'legal_annex', title: 'Anexo de confidencialidad' },
        ],
      },
      global: { stubs: { BaseModal: { template: '<div><slot /></div>' }, EmailRecipientFields: EmailRecipientFieldsStub } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain('Anexo de confidencialidad');
    expect(wrapper.text()).not.toContain('Contrato de servicio');
  });

  it('renders the frozen email preview and each prepared file with its download URL', async () => {
    // Catches a regression that presents a different email or attachment manifest than the frozen preparation.
    const wrapper = await renderPreparedModal();

    expect(wrapper.get('[data-testid="formalization-email-preview"]').attributes('srcdoc')).toBe('<main>Correo congelado para revisión</main>');
    expect(wrapper.findAll('a').map((link) => ({ text: link.text(), href: link.attributes('href') }))).toEqual([
      { text: 'Descargar', href: '/api/proposals/55/formalization/files/701/' },
      { text: 'Descargar', href: '/api/proposals/55/formalization/files/702/' },
    ]);
    expect(wrapper.text()).toContain('Contrato Acme.pdf');
    expect(wrapper.text()).toContain('Propuesta comercial Acme.pdf');
  });

  it('returns a stale preparation to the editable draft while retaining its subject', async () => {
    // Catches a regression that strands the operator in an expired review after the proposal source changes.
    const wrapper = await renderPreparedModal();
    mockFormalizationStore.send.mockRejectedValue({
      response: { data: { code: 'stale_preparation', error: 'La propuesta cambió. Prepara otra revisión.' } },
    });

    await wrapper.get('[data-testid="formalization-send"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="formalization-subject"]').element.value).toBe('Documentación para formalizar Acme');
    expect(wrapper.get('[role="alert"]').text()).toBe('La propuesta cambió. Prepara otra revisión.');
    expect(wrapper.findAll('[data-testid="formalization-email-preview"]')).toHaveLength(0);
    expect(wrapper.get('[data-testid="formalization-prepare"]').attributes('disabled')).toBeUndefined();
  });

  it('removes the send control after an uncertain delivery is reconciled as unknown', async () => {
    // Catches a regression that makes an unconfirmed delivery retryable and can duplicate client email.
    const wrapper = await renderPreparedModal();
    mockFormalizationStore.send.mockRejectedValue(new Error('Network connection lost'));
    mockFormalizationStore.detail.mockResolvedValue({
      ...preparedPackage,
      status: 'unknown',
      error: 'Confirmación pendiente.',
    });

    await wrapper.get('[data-testid="formalization-send"]').trigger('click');
    await flushPromises();

    expect(mockFormalizationStore.detail).toHaveBeenCalledWith(55, 'prep-77');
    expect(mockFormalizationStore.detail).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain('Confirmación pendiente.');
    expect(wrapper.findAll('[data-testid="formalization-send"]')).toHaveLength(0);
  });
});
