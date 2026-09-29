jest.mock('#imports', () => ({
  ...jest.requireActual('#imports'),
  useI18n: () => ({ t: (key) => {
    const messages = jest.requireActual('../../locales/pwa/es').default;
    return key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
  } }),
}));

/**
 * Tests for DiagnosticDocumentsTab.vue.
 *
 * Covers: NDA section (absent/present), attachment list,
 * handleDelete, handleUpload (validation + success),
 * template loading, formatBytes, copyTemplate, togglePreview.
 */

const mockDiagnosticsStore = {
  uploadAttachment: jest.fn(),
  deleteAttachment: jest.fn(),
};

jest.mock('../../stores/diagnostics', () => ({
  useDiagnosticsStore: () => mockDiagnosticsStore,
}));

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
}));

import { mount } from '@vue/test-utils';
import { get_request } from '../../stores/services/request_http';
import DiagnosticDocumentsTab from '../../components/WebAppDiagnostic/DiagnosticDocumentsTab.vue';

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

const baseDiagnostic = { id: 42, attachments: [] };

const ndaAttachment = {
  id: 1,
  document_type: 'confidentiality_agreement',
  is_generated: true,
  created_at: '2026-04-10T10:00:00Z',
};

const userAttachment = {
  id: 5,
  title: 'Anexo técnico',
  file: '/files/anexo.pdf',
  document_type: 'amendment',
  document_type_display: 'Otrosí',
  is_generated: false,
};

function mountTab(props = {}) {
  return mount(DiagnosticDocumentsTab, {
    props: {
      diagnostic: baseDiagnostic,
      ...props,
    },
    global: {
      stubs: {
        ConfidentialityParamsModal: { template: '<div />' },
        MarkdownPreviewModal: {
          props: ['modelValue', 'title'],
          template: '<div v-if="modelValue" data-testid="preview-modal" :data-title="title"><slot /></div>',
        },
      },
    },
  });
}

describe('DiagnosticDocumentsTab', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    get_request.mockReset().mockResolvedValue({ data: [] });
    mockDiagnosticsStore.uploadAttachment.mockReset().mockResolvedValue({ success: true });
    mockDiagnosticsStore.deleteAttachment.mockReset().mockResolvedValue({ success: true });
    global.navigator.clipboard = { writeText: jest.fn().mockResolvedValue(undefined) };
    global.URL.createObjectURL = jest.fn().mockReturnValue('blob://mock');
    global.URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  // ── NDA section ───────────────────────────────────────────────────────────

  describe('NDA section', () => {
    it('shows PDF no generado when no NDA attachment is present', async () => {
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('PDF · No generado');
    });

    it('shows Generar acuerdo button when no NDA attachment is present', async () => {
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('Generar acuerdo');
    });

    it('shows Descargar PDF link when the NDA attachment is present', async () => {
      const wrapper = mountTab({
        diagnostic: { id: 42, attachments: [ndaAttachment] },
      });
      await flushPromises();

      expect(wrapper.text()).toContain('Descargar PDF');
    });

    it('uses the diagnostic id to build the NDA PDF URL', async () => {
      const wrapper = mountTab({
        diagnostic: { id: 99, attachments: [ndaAttachment] },
      });
      await flushPromises();

      expect(wrapper.html()).toContain('/api/diagnostics/99/confidentiality/pdf/');
    });
  });

  // ── Attachment list ───────────────────────────────────────────────────────

  describe('attachment list', () => {
    it('shows no attachments message when the list is empty', async () => {
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('No hay documentos adjuntos.');
    });

    it('renders attachment title when user attachments are present', async () => {
      const wrapper = mountTab({
        diagnostic: { id: 42, attachments: [userAttachment] },
      });
      await flushPromises();

      expect(wrapper.text()).toContain('Anexo técnico');
    });
  });

  // ── handleDelete ──────────────────────────────────────────────────────────

  describe('handleDelete', () => {
    it('calls store.deleteAttachment with diagnostic id and attachment id when delete is clicked', async () => {
      const wrapper = mountTab({
        diagnostic: { id: 42, attachments: [userAttachment] },
      });
      await flushPromises();

      await wrapper.find('button[aria-label="Eliminar documento"]').trigger('click');
      await flushPromises();

      expect(mockDiagnosticsStore.deleteAttachment).toHaveBeenCalledWith(42, 5);
    });
  });

  // ── handleUpload ──────────────────────────────────────────────────────────

  describe('handleUpload', () => {
    it('shows error message when no file is selected and upload is triggered', async () => {
      const wrapper = mountTab();
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text() === 'Subir').trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Selecciona un archivo.');
    });

    it('calls store.uploadAttachment when a file is selected', async () => {
      const wrapper = mountTab();
      await flushPromises();

      const fileInput = wrapper.find('input[type="file"]');
      const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });
      Object.defineProperty(fileInput.element, 'files', {
        configurable: true,
        value: [file],
      });

      await wrapper.findAll('button').find((btn) => btn.text() === 'Subir').trigger('click');
      await flushPromises();

      expect(mockDiagnosticsStore.uploadAttachment).toHaveBeenCalledWith(
        42,
        expect.any(FormData),
      );
    });
  });

  // ── Template loading ──────────────────────────────────────────────────────

  describe('template loading', () => {
    it('calls get_request with diagnostic-templates/ on mount', async () => {
      mountTab();
      await flushPromises();

      expect(get_request).toHaveBeenCalledWith('diagnostic-templates/');
    });

    it('renders template title after templates are loaded', async () => {
      get_request.mockResolvedValueOnce({
        data: [{ slug: 'tpl-1', title: 'Informe de Diagnóstico', filename: 'informe.md', size_bytes: 512 }],
      });
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('Informe de Diagnóstico');
    });

    it('shows template loading error when get_request throws', async () => {
      get_request.mockRejectedValueOnce(new Error('Network error'));
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('No se pudieron cargar las plantillas.');
    });
  });

  // ── formatBytes ───────────────────────────────────────────────────────────

  describe('formatBytes', () => {
    it('shows size in B for files under 1024 bytes', async () => {
      get_request.mockResolvedValueOnce({
        data: [{ slug: 'tpl-b', title: 'Small', filename: 'small.md', size_bytes: 500 }],
      });
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('500 B');
    });

    it('shows size in KB for files between 1024 and 1048576 bytes', async () => {
      get_request.mockResolvedValueOnce({
        data: [{ slug: 'tpl-kb', title: 'Medium', filename: 'medium.md', size_bytes: 2048 }],
      });
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('2.0 KB');
    });
  });

  // ── copyTemplate ──────────────────────────────────────────────────────────

  describe('copyTemplate', () => {
    it('calls navigator.clipboard.writeText with the template content', async () => {
      get_request
        .mockResolvedValueOnce({
          data: [{ slug: 'tpl-1', title: 'Informe', filename: 'informe.md', size_bytes: 100 }],
        })
        .mockResolvedValueOnce({ data: { content_markdown: '# Informe\nContenido.' } });

      const wrapper = mountTab();
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text().includes('Copiar contenido')).trigger('click');
      await flushPromises();

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('# Informe\nContenido.');
    });
  });

  // ── preview modal ─────────────────────────────────────────────────────────

  describe('preview modal', () => {
    it('opens the modal with rendered markdown when the template preview icon is clicked', async () => {
      get_request
        .mockResolvedValueOnce({
          data: [{ slug: 'tpl-1', title: 'Informe', filename: 'informe.md', size_bytes: 100 }],
        })
        .mockResolvedValueOnce({ data: { content_markdown: '# Informe\nContenido de prueba' } });

      const wrapper = mountTab();
      await flushPromises();

      await wrapper.find('button[aria-label="Vista previa de Informe"]').trigger('click');
      await flushPromises();

      const modal = wrapper.find('[data-testid="preview-modal"]');
      expect(modal.exists()).toBe(true);
      expect(modal.attributes('data-title')).toBe('Informe');
      expect(modal.html()).toContain('Contenido de prueba');
    });

    it('opens an iframe preview when the NDA preview icon is clicked', async () => {
      const wrapper = mountTab({
        diagnostic: { id: 99, attachments: [ndaAttachment] },
      });
      await flushPromises();

      await wrapper.find('button[aria-label="Vista previa del acuerdo"]').trigger('click');
      await flushPromises();

      const modal = wrapper.find('[data-testid="preview-modal"]');
      expect(modal.exists()).toBe(true);
      expect(modal.attributes('data-title')).toBe('Acuerdo de confidencialidad');
      expect(modal.html()).toContain('/api/diagnostics/99/confidentiality/pdf/');
    });

    it('opens an iframe preview when an attachment preview icon is clicked', async () => {
      const wrapper = mountTab({
        diagnostic: { id: 42, attachments: [userAttachment] },
      });
      await flushPromises();

      await wrapper.find('button[aria-label="Vista previa de Anexo técnico"]').trigger('click');
      await flushPromises();

      const modal = wrapper.find('[data-testid="preview-modal"]');
      expect(modal.exists()).toBe(true);
      expect(modal.html()).toContain('/files/anexo.pdf');
    });
  });
});
