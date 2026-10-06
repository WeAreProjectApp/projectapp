jest.mock('#imports', () => ({
  ...jest.requireActual('#imports'),
  useI18n: () => ({ t: (key) => {
    const messages = jest.requireActual('../../locales/pwa/es').default;
    return key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
  } }),
}));

import { mount, flushPromises } from '@vue/test-utils';

jest.mock('~/stores/services/request_http', () => ({
  get_request: jest.fn(),
}));

jest.mock('~/utils/downloadFile', () => ({
  downloadBlob: jest.fn(),
  filenameFromDisposition: jest.requireActual('~/utils/downloadFile').filenameFromDisposition,
}));

const mockNotify = { success: jest.fn(), error: jest.fn() };
jest.mock('~/composables/usePanelNotify', () => ({ usePanelNotify: () => mockNotify }));

const mockUpdateContractModality = jest.fn();
const mockPreviewContractChange = jest.fn();
const mockConfirmContractChange = jest.fn();
const mockCancelContractChange = jest.fn();
global.useProposalStore = jest.fn(() => ({
  uploadProposalDocument: jest.fn().mockResolvedValue({ success: true }),
  deleteProposalDocument: jest.fn().mockResolvedValue({ success: true }),
  updateContractModality: mockUpdateContractModality,
  previewContractChange: mockPreviewContractChange,
  confirmContractChange: mockConfirmContractChange,
  cancelContractChange: mockCancelContractChange,
}));

import ProposalDocumentsTab from '../../components/BusinessProposal/admin/ProposalDocumentsTab.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import { get_request } from '~/stores/services/request_http';
import { downloadBlob } from '~/utils/downloadFile';

const baseProposal = {
  id: 1,
  uuid: 'abc-123',
  client_name: 'Acme Corp',
  client_email: 'client@acme.com',
};

function mountProposalDocumentsTab(props = {}) {
  return mount(ProposalDocumentsTab, {
    props: {
      proposal: baseProposal,
      documents: [],
      ...props,
    },
    global: {
      components: { BaseSegmented },
      stubs: {
        ProposalContractChangeModal: {
          template: '<div data-testid="proposal-contract-change-modal">Cambiar modalidad de contrato</div>',
        },
      },
    },
  });
}

describe('ProposalDocumentsTab', () => {
  beforeEach(() => {
    get_request.mockReset();
    downloadBlob.mockReset();
  });

  it('renders the documents list with contract, commercial and technical entries', () => {
    const wrapper = mountProposalDocumentsTab();

    expect(wrapper.text()).toContain('Contrato de desarrollo');
    expect(wrapper.text()).toContain('Propuesta comercial');
    expect(wrapper.text()).toContain('Detalle técnico');
  });

  it('shows generate contract button when no contract doc exists', () => {
    const wrapper = mountProposalDocumentsTab({ documents: [] });

    expect(wrapper.text()).toContain('Generar contrato');
  });

  it('renders the documentos adjuntos section', () => {
    const wrapper = mountProposalDocumentsTab();

    expect(wrapper.text()).toContain('Documentos adjuntos');
  });

  it('does not render the removed "Enviar documentos al cliente" section', () => {
    const wrapper = mountProposalDocumentsTab();

    expect(wrapper.get('[data-testid="proposal-formalization-open"]').text()).toBe('Preparar correo de formalización');
    expect(wrapper.text()).not.toContain('Enviar documentos al cliente');
  });

  it('emits generateContract when generate button is clicked', async () => {
    const wrapper = mountProposalDocumentsTab({ documents: [] });

    const btn = wrapper.findAll('button').find(b => b.text() === 'Generar contrato');
    await btn.trigger('click');

    expect(wrapper.emitted('generateContract')).toHaveLength(1);
  });

  it('shows additional document when provided', () => {
    const docs = [
      {
        id: 10,
        document_type: 'amendment',
        document_type_display: 'Otrosí',
        title: 'Otrosí #1',
        file: '/media/osi.pdf',
        is_generated: false,
      },
    ];

    const wrapper = mountProposalDocumentsTab({ documents: docs });

    expect(wrapper.text()).toContain('Otrosí #1');
  });

  test.each([
    ['DOCX', '/media/alcance.docx'],
    ['XLSX', '/media/cronograma.xlsx'],
  ])('enables supported Office document actions for a %s attachment', (fileType, file) => {
    // Falla si los documentos Office convertibles pierden una acción disponible.
    const wrapper = mountProposalDocumentsTab({
      documents: [{
        id: 10,
        document_type: 'amendment',
        document_type_display: fileType,
        title: `Alcance ${fileType}`,
        file,
        is_generated: false,
      }],
    });
    const row = wrapper.get('[data-testid="proposal-attachment-10"]');
    const copyButton = row.get('[data-testid="proposal-copy-attachment-10"]');
    const previewButton = row.findAll('button').find((button) => (
      button.attributes('aria-label') === `Vista previa de Alcance ${fileType}`
    ));

    expect(copyButton.element.disabled).toBe(false);
    expect(previewButton.element.disabled).toBe(false);
  });

  test.each([
    ['imagen', 'Diagrama de arquitectura', '/media/arquitectura.png', false, 'La imagen no tiene texto extraíble. Se requiere reconocimiento de texto.'],
    ['DOC heredado', 'Contrato heredado', '/media/contrato.doc', true, 'Convierte el archivo a DOCX o XLSX para visualizar y copiar su contenido.'],
    ['XLS heredado', 'Plan heredado', '/media/plan.xls', true, 'Convierte el archivo a DOCX o XLSX para visualizar y copiar su contenido.'],
  ])('shows the documented copy limitation for a %s attachment', (fileType, title, file, previewDisabled, reason) => {
    // Falla si un formato sin extracción muestra una acción de copia engañosa.
    const wrapper = mountProposalDocumentsTab({
      documents: [{
        id: 11,
        document_type: 'amendment',
        document_type_display: fileType,
        title,
        file,
        is_generated: false,
      }],
    });
    const row = wrapper.get('[data-testid="proposal-attachment-11"]');
    const copyButton = row.get('[data-testid="proposal-copy-attachment-11"]');
    const copyProxy = copyButton.element.closest('[data-disabled-action-proxy]');
    const previewButton = row.findAll('button').find((button) => (
      button.attributes('aria-label') === `Vista previa de ${title}`
    ));

    expect(copyButton.element.disabled).toBe(true);
    expect(copyProxy.getAttribute('aria-label')).toContain(reason);
    expect(previewButton.element.disabled).toBe(previewDisabled);
  });

  it('downloads an attachment with the filename returned by the server', async () => {
    // Falla si una descarga ignora el Content-Disposition y pierde el nombre original.
    const blob = new Blob(['contenido'], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
    get_request.mockResolvedValue({
      data: blob,
      headers: { 'content-disposition': "attachment; filename*=UTF-8''contrato%20final%20espa%C3%B1ol.docx" },
    });
    const wrapper = mountProposalDocumentsTab({
      documents: [{
        id: 12,
        document_type: 'amendment',
        document_type_display: 'Anexo',
        title: 'Contrato firmado',
        file: '/media/archivo-temporal.docx',
        is_generated: false,
      }],
    });
    const row = wrapper.get('[data-testid="proposal-attachment-12"]');
    const downloadButton = row.findAll('button').find((button) => (
      button.attributes('aria-label') === 'Descargar Contrato firmado'
    ));

    await downloadButton.trigger('click');
    await Promise.resolve();

    expect(get_request).toHaveBeenCalledWith('proposals/1/documents/12/download/', expect.objectContaining({ responseType: 'blob' }));
    expect(downloadBlob).toHaveBeenCalledWith(blob, 'contrato final español.docx');
  });
});

describe('ProposalDocumentsTab closing modality', () => {
  const negotiating = { ...baseProposal, status: 'negotiating', contract_modality: 'single' };
  const split = { ...negotiating, contract_modality: 'split' };
  const productDoc = {
    id: 21, document_type: 'contract_product', document_type_display: 'Contrato de producto',
    title: 'Contrato de producto', file: '/media/producto.pdf', is_generated: true,
    created_at: '2026-09-26T10:00:00Z',
  };

  beforeEach(() => {
    mockUpdateContractModality.mockReset();
    mockPreviewContractChange.mockReset();
    mockConfirmContractChange.mockReset();
    mockCancelContractChange.mockReset();
    mockNotify.success.mockReset();
    mockNotify.error.mockReset();
  });

  test.each([
    ['draft'],
    ['sent'],
    ['viewed'],
    ['negotiating'],
    ['accepted'],
    ['rejected'],
    ['expired'],
    ['finished'],
  ])('shows an enabled modality choice for a %s proposal', (status) => {
    // Falla si una propuesta deja de mostrar una modalidad que ahora se puede revisar o cambiar.
    const wrapper = mountProposalDocumentsTab({ proposal: { ...negotiating, status } });

    expect(wrapper.get('[data-testid="proposal-contract-modality"]').text()).toContain('Modalidad de cierre');
    expect(wrapper.get('[data-testid="proposal-contract-modality-split"]').element.disabled).toBe(false);
  });

  it('shows the product and service contracts for a split closing', () => {
    // Falla si la modalidad separada no muestra sus dos documentos con sus propias URLs.
    const wrapper = mountProposalDocumentsTab({ proposal: split, documents: [productDoc] });
    const product = wrapper.get('[data-testid="proposal-contract-row-product"]');
    const service = wrapper.get('[data-testid="proposal-contract-row-service"]');

    expect(wrapper.find('[data-testid="proposal-contract-row-combined"]').exists()).toBe(false);
    expect(product.get('a[href$="contract/pdf/?variant=product"]').text()).toContain('Descargar PDF');
    expect(service.text()).toContain('PDF · No generado');
    expect(wrapper.find('[data-testid="proposal-attachment-21"]').exists()).toBe(false);
  });

  it('keeps stale service conditions in the service row of a split closing', () => {
    // Falla si el administrador no ve que debe regenerar el servicio o si el producto hereda esa alerta.
    const serviceDoc = {
      id: 22, document_type: 'contract_service', document_type_display: 'Contrato de servicio',
      title: 'Contrato de servicio', file: '/media/servicio.pdf', is_generated: true,
      created_at: '2026-09-26T10:00:00Z', needs_regeneration: true,
    };
    const wrapper = mountProposalDocumentsTab({ proposal: split, documents: [productDoc, serviceDoc] });
    const product = wrapper.get('[data-testid="proposal-contract-row-product"]');
    const service = wrapper.get('[data-testid="proposal-contract-row-service"]');

    expect(wrapper.text()).toContain('Hosting, mantenimiento, soporte, precios y renovación se incluyen en el contrato de servicio.');
    expect(service.get('[data-testid="proposal-service-contract-stale"]').text())
      .toBe('Las condiciones del servicio cambiaron. Regenera y revisa el contrato antes de enviarlo.');
    expect(product.find('[data-testid="proposal-service-contract-stale"]').exists()).toBe(false);
  });

  it('emits the document the admin wants to generate', async () => {
    // Falla si generar el contrato de servicio abre el formulario de otro documento.
    const wrapper = mountProposalDocumentsTab({ proposal: split, documents: [productDoc] });

    await wrapper.get('[data-testid="proposal-generate-contract-service"]').trigger('click');

    expect(wrapper.emitted('generateContract')).toEqual([['service']]);
  });

  it('persists a new modality and confirms it', async () => {
    // Falla si el cambio de modalidad no llega al backend o no avisa el resultado.
    mockUpdateContractModality.mockResolvedValue({ success: true, data: split });
    const wrapper = mountProposalDocumentsTab({
      proposal: {
        ...negotiating,
        contract_params: {
          service_initial_term: '12 meses',
          service_renewal_notice_days: 30,
          service_termination_notice_days: 30,
        },
      },
    });

    await wrapper.get('[data-testid="proposal-contract-modality-split"]').trigger('click');
    await Promise.resolve();

    expect(mockUpdateContractModality).toHaveBeenCalledWith(1, 'split');
    expect(mockNotify.success).toHaveBeenCalledWith('El negocio se cierra con contrato de producto y contrato de servicio.');
  });

  test.each(['accepted', 'rejected'])('opens the review flow instead of changing a %s proposal directly', async (status) => {
    // Falla si una propuesta cerrada cambia la modalidad sin la revisión y confirmación obligatorias.
    const wrapper = mountProposalDocumentsTab({ proposal: { ...negotiating, status } });

    await wrapper.get('[data-testid="proposal-contract-modality-split"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="proposal-contract-change-modal"]').text()).toContain('Cambiar modalidad de contrato');
    expect(mockUpdateContractModality).not.toHaveBeenCalled();
  });

  it('ignores a click on the modality already selected', async () => {
    // Falla si repetir la opción actual regenera documentos en el backend.
    const wrapper = mountProposalDocumentsTab({ proposal: negotiating });
    const single = wrapper.get('[data-testid="proposal-contract-modality-single"]');

    await single.trigger('click');

    expect(single.attributes('aria-selected')).toBe('true');
    expect(single.element.disabled).toBe(false);
    expect(mockUpdateContractModality).not.toHaveBeenCalled();
  });

  it('reports why the modality could not change', async () => {
    // Falla si un rechazo del backend se pierde sin avisar al administrador.
    mockUpdateContractModality.mockResolvedValue({
      success: false, message: 'No tienes permiso para cambiar la modalidad.',
    });
    const wrapper = mountProposalDocumentsTab({
      proposal: {
        ...negotiating,
        contract_params: {
          service_initial_term: '12 meses',
          service_renewal_notice_days: 30,
          service_termination_notice_days: 30,
        },
      },
    });

    await wrapper.get('[data-testid="proposal-contract-modality-split"]').trigger('click');
    await Promise.resolve();

    expect(mockNotify.error).toHaveBeenCalledWith('No tienes permiso para cambiar la modalidad.');
  });

  test.each([
    ['split', 'custom', true],
    ['split', 'default', false],
    ['single', 'custom', false],
  ])('shows the custom-single notice only for a split closing with a custom source (modality=%s, source=%s): %s', (contract_modality, contract_source, shown) => {
    // Falla si al separar se oculta el aviso de texto personalizado, o si aparece cuando no corresponde.
    const wrapper = mountProposalDocumentsTab({
      proposal: { ...negotiating, contract_modality, contract_params: { contract_source } },
    });

    expect(wrapper.find('[data-testid="proposal-contract-modality-custom-notice"]').exists()).toBe(shown);
    expect(wrapper.text().includes('personalizado')).toBe(shown);
  });
});
