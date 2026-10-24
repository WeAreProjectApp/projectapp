/**
 * Tests for DiagnosticEmailsTab.vue.
 *
 * Covers: rendering, canSend validation, addSection/removeSection,
 * handleFilesChange, handleSend success/error, loadHistory on mount,
 * toggleExpand, loadMore, loadDefaults, statusLabel.
 */

const mockDiagnosticsStore = {
  sendCustomEmail: jest.fn(),
  fetchEmailHistory: jest.fn(),
  fetchEmailDefaults: jest.fn(),
};

jest.mock('../../stores/diagnostics', () => ({
  useDiagnosticsStore: () => mockDiagnosticsStore,
}));

jest.mock('../../stores/diagnostics_constants', () => ({
  DIAGNOSTIC_STATUS: { NEGOTIATING: 'negotiating' },
}));

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn().mockResolvedValue({ data: [] }),
}));

const mockHandleMarkdownAttach = jest.fn();
jest.mock('../../composables/useMarkdownAttachmentHandler', () => ({
  useMarkdownAttachmentHandler: () => ({ handleMarkdownAttach: mockHandleMarkdownAttach }),
}));

const mockResetDocRefs = jest.fn();
const mockAppendDocRefsToFormData = jest.fn();
jest.mock('../../composables/useDocRefsAttachment', () => ({
  useDocRefsAttachment: () => ({
    docRefs: [],
    removeDocRef: jest.fn(),
    handleDocRefsAttach: jest.fn(),
    appendDocRefsToFormData: mockAppendDocRefsToFormData,
    resetDocRefs: mockResetDocRefs,
  }),
}));

jest.mock('../../utils/emailAttachments', () => ({
  validateEmailAttachments: jest.fn(),
}));

import { mount } from '@vue/test-utils';
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import { validateEmailAttachments } from '../../utils/emailAttachments';
import DiagnosticEmailsTab from '../../components/WebAppDiagnostic/DiagnosticEmailsTab.vue';

const originalUseI18n = global.useI18n;
beforeEach(() => { global.useI18n = () => ({ t: (key) => key }); });
afterAll(() => { global.useI18n = originalUseI18n; });

async function editFirstSectionSource(wrapper, value) {
  await wrapper.findAll('[role="tab"]').find((tab) => tab.text() === 'richText.source').trigger('click');
  await wrapper.get('[data-testid="rich-text-source-input"]').setValue(value);
}

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

const baseDiagnostic = {
  id: 42,
  client: { email: 'client@example.com', name: 'Carlos' },
  status: 'active',
};

const DraggableStub = {
  name: 'Draggable',
  props: ['modelValue', 'itemKey', 'handle', 'ghostClass'],
  emits: ['update:modelValue', 'end'],
  template: '<div><slot name="item" v-for="(el, i) in modelValue" :key="i" :element="el" :index="i" /></div>',
};

const EmailRecipientFieldsStub = {
  name: 'EmailRecipientFields',
  props: ['toRecipients', 'ccRecipients'],
  emits: ['update:toRecipients', 'update:ccRecipients'],
  template: `
    <input
      type="email"
      placeholder="correo@ejemplo.com"
      :value="toRecipients[0]?.email || ''"
      @input="$emit('update:toRecipients', $event.target.value ? [{ email: $event.target.value }] : [])"
    >
  `,
};

function mountTab(props = {}) {
  return mount(DiagnosticEmailsTab, {
    props: {
      diagnostic: baseDiagnostic,
      ...props,
    },
    global: {
      components: { BaseRichTextEditor, BaseSegmented },
      stubs: {
        TabSplitLayout: { template: '<div><slot name="main" /><slot name="aside" /></div>' },
        draggable: DraggableStub,
        MarkdownAttachmentModal: { template: '<div />' },
        AttachFromDocumentsModal: { template: '<div />' },
        EmailRecipientFields: EmailRecipientFieldsStub,
      },
    },
  });
}

describe('DiagnosticEmailsTab', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockDiagnosticsStore.sendCustomEmail.mockReset().mockResolvedValue({ success: true });
    mockDiagnosticsStore.fetchEmailHistory.mockReset().mockResolvedValue({
      success: true,
      data: { results: [], page: 1, has_next: false },
    });
    mockDiagnosticsStore.fetchEmailDefaults.mockReset().mockResolvedValue({
      success: true,
      data: { greeting: 'Hola Carlos', footer: 'Quedamos atentos.' },
    });
    validateEmailAttachments.mockReset().mockReturnValue({ validFiles: [], errors: [] });
    mockResetDocRefs.mockReset();
    mockAppendDocRefsToFormData.mockReset();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  describe('rendering', () => {
    it('renders the email composer heading', async () => {
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('Correo de seguimiento');
    });

    it('shows the empty history message when no emails have been sent', async () => {
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('No se han enviado correos desde este diagnóstico.');
    });
  });

  // ── canSend validation ────────────────────────────────────────────────────

  describe('canSend validation', () => {
    it('disables the send button when recipient is empty', async () => {
      const wrapper = mountTab({ diagnostic: { id: 42, client: null, status: 'active' } });
      await flushPromises();

      expect(wrapper.findAll('button').find((btn) => btn.text().includes('Enviar correo')).element.disabled).toBe(true);
    });

    it('disables the send button when subject is empty', async () => {
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.findAll('button').find((btn) => btn.text().includes('Enviar correo')).element.disabled).toBe(true);
    });

    it('enables the send button when recipient, subject, and a section text are filled', async () => {
      const wrapper = mountTab();
      await flushPromises();

      await wrapper.find('input[placeholder="Asunto del correo"]').setValue('Seguimiento');
      await editFirstSectionSource(wrapper, 'Hemos avanzado.');
      await wrapper.vm.$nextTick();

      expect(wrapper.findAll('button').find((btn) => btn.text().includes('Enviar correo')).element.disabled).toBe(false);
    });
  });

  // ── addSection / removeSection ────────────────────────────────────────────

  describe('addSection', () => {
    it('adds a new section to the list when Agregar sección is clicked', async () => {
      const wrapper = mountTab();
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text().includes('Agregar sección')).trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain('Sección 2');
    });
  });

  describe('removeSection', () => {
    it('removes a section when the delete button is clicked and more than one exists', async () => {
      const wrapper = mountTab();
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text().includes('Agregar sección')).trigger('click');
      await wrapper.vm.$nextTick();
      expect(wrapper.text()).toContain('Sección 2');

      await wrapper.find('button[aria-label="Eliminar"]').trigger('click');
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).not.toContain('Sección 2');
    });
  });

  // ── handleFilesChange ─────────────────────────────────────────────────────

  describe('handleFilesChange', () => {
    it('adds valid files to the attachment list', async () => {
      const file = new File(['content'], 'report.pdf', { type: 'application/pdf' });
      validateEmailAttachments.mockReturnValue({ validFiles: [file], errors: [] });

      const wrapper = mountTab();
      await flushPromises();

      const fileInput = wrapper.find('input[type="file"]');
      Object.defineProperty(fileInput.element, 'files', { configurable: true, value: [file] });
      await fileInput.trigger('change');

      expect(wrapper.text()).toContain('report.pdf');
    });

    it('shows an error message when validateEmailAttachments returns errors', async () => {
      validateEmailAttachments.mockReturnValue({ validFiles: [], errors: ['bad.exe: tipo no permitido'] });

      const wrapper = mountTab();
      await flushPromises();

      const fileInput = wrapper.find('input[type="file"]');
      const badFile = new File(['x'], 'bad.exe', { type: 'application/octet-stream' });
      Object.defineProperty(fileInput.element, 'files', { configurable: true, value: [badFile] });
      await fileInput.trigger('change');

      expect(wrapper.text()).toContain('bad.exe: tipo no permitido');
    });
  });

  // ── handleSend ────────────────────────────────────────────────────────────

  describe('handleSend', () => {
    it('calls store.sendCustomEmail with FormData when send button is clicked', async () => {
      const wrapper = mountTab();
      await flushPromises();

      await wrapper.find('input[placeholder="Asunto del correo"]').setValue('Seguimiento');
      await editFirstSectionSource(wrapper, 'Avance del proyecto.');
      await wrapper.vm.$nextTick();
      await wrapper.findAll('button').find((btn) => btn.text().includes('Enviar correo')).trigger('click');
      await flushPromises();

      expect(mockDiagnosticsStore.sendCustomEmail).toHaveBeenCalledWith(42, expect.any(FormData));
      const formData = mockDiagnosticsStore.sendCustomEmail.mock.calls[0][1];
      expect(formData.get('recipient_emails')).toBe('["client@example.com"]');
      expect(formData.get('cc_emails')).toBe('[]');
    });

    it('shows Correo enviado correctly after a successful send', async () => {
      const wrapper = mountTab();
      await flushPromises();

      await wrapper.find('input[placeholder="Asunto del correo"]').setValue('Seguimiento');
      await editFirstSectionSource(wrapper, 'Contenido.');
      await wrapper.vm.$nextTick();
      await wrapper.findAll('button').find((btn) => btn.text().includes('Enviar correo')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Correo enviado correctamente.');
    });

    it('shows error message after a failed send', async () => {
      mockDiagnosticsStore.sendCustomEmail.mockResolvedValue({ success: false });
      const wrapper = mountTab();
      await flushPromises();

      await wrapper.find('input[placeholder="Asunto del correo"]').setValue('Asunto');
      await editFirstSectionSource(wrapper, 'Texto.');
      await wrapper.vm.$nextTick();
      await wrapper.findAll('button').find((btn) => btn.text().includes('Enviar correo')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Error al enviar el correo. Intenta de nuevo.');
    });
  });

  // ── loadHistory ───────────────────────────────────────────────────────────

  describe('loadHistory', () => {
    it('calls store.fetchEmailHistory with diagnostic id on mount', async () => {
      mountTab();
      await flushPromises();

      expect(mockDiagnosticsStore.fetchEmailHistory).toHaveBeenCalledWith(42, 1);
    });

    it('renders a history entry subject when history has entries', async () => {
      mockDiagnosticsStore.fetchEmailHistory.mockResolvedValue({
        success: true,
        data: {
          results: [
            {
              id: 10,
              subject: 'Seguimiento diagnóstico',
              recipient: 'client@example.com',
              status: 'sent',
              sent_at: '2026-04-10T10:00:00Z',
              template_key: 'diagnostic_custom_email',
              metadata: {},
            },
          ],
          page: 1,
          has_next: false,
        },
      });
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('Seguimiento diagnóstico');
    });
  });

  // ── toggleExpand ──────────────────────────────────────────────────────────

  describe('toggleExpand', () => {
    const entryWithDetail = {
      id: 10,
      subject: 'Avance del proyecto',
      recipient: 'client@example.com',
      status: 'sent',
      sent_at: '2026-04-10T10:00:00Z',
      template_key: 'diagnostic_custom_email',
      metadata: {
        greeting: 'Hola Carlos',
        sections: ['Esta es la primera sección del correo.'],
        footer: '',
        attachment_names: [],
      },
    };

    it('shows entry detail when the history entry button is clicked', async () => {
      mockDiagnosticsStore.fetchEmailHistory.mockResolvedValue({
        success: true,
        data: { results: [entryWithDetail], page: 1, has_next: false },
      });
      const wrapper = mountTab();
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text().includes('Avance del proyecto')).trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('Esta es la primera sección del correo.');
    });

    it('hides the detail on the second click', async () => {
      mockDiagnosticsStore.fetchEmailHistory.mockResolvedValue({
        success: true,
        data: { results: [entryWithDetail], page: 1, has_next: false },
      });
      const wrapper = mountTab();
      await flushPromises();

      const expandBtn = wrapper.findAll('button').find((btn) => btn.text().includes('Avance del proyecto'));
      await expandBtn.trigger('click');
      await flushPromises();
      expect(wrapper.text()).toContain('Esta es la primera sección del correo.');

      await expandBtn.trigger('click');
      await flushPromises();
      const detailCollapse = wrapper
        .findAll('[aria-hidden]')
        .find((node) => node.text().includes('Esta es la primera sección del correo.'));
      expect(detailCollapse.attributes('aria-hidden')).toBe('true');
    });
  });

  // ── loadMore ──────────────────────────────────────────────────────────────

  describe('loadMore', () => {
    it('calls fetchEmailHistory with the next page when Cargar más is clicked', async () => {
      mockDiagnosticsStore.fetchEmailHistory
        .mockResolvedValueOnce({
          success: true,
          data: {
            results: [{ id: 1, subject: 'Primero', recipient: 'a@b.com', status: 'sent', sent_at: null, template_key: null, metadata: {} }],
            page: 1,
            has_next: true,
          },
        })
        .mockResolvedValueOnce({
          success: true,
          data: { results: [], page: 2, has_next: false },
        });

      const wrapper = mountTab();
      await flushPromises();

      await wrapper.findAll('button').find((btn) => btn.text().includes('Cargar más')).trigger('click');
      await flushPromises();

      expect(mockDiagnosticsStore.fetchEmailHistory).toHaveBeenLastCalledWith(42, 2);
    });
  });

  // ── loadDefaults ──────────────────────────────────────────────────────────

  describe('loadDefaults', () => {
    it('applies the greeting from fetchEmailDefaults to the greeting input', async () => {
      mockDiagnosticsStore.fetchEmailDefaults.mockResolvedValue({
        success: true,
        data: { greeting: 'Buenos días equipo', footer: '' },
      });
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.find('input[placeholder="Hola Carlos"]').element.value).toBe('Buenos días equipo');
    });
  });

  // ── statusLabel ───────────────────────────────────────────────────────────

  describe('statusLabel', () => {
    it('renders Enviado for sent status entries in history', async () => {
      mockDiagnosticsStore.fetchEmailHistory.mockResolvedValue({
        success: true,
        data: {
          results: [{ id: 1, subject: 'Test', recipient: 'a@b.com', status: 'sent', sent_at: null, template_key: null, metadata: {} }],
          page: 1,
          has_next: false,
        },
      });
      const wrapper = mountTab();
      await flushPromises();

      expect(wrapper.text()).toContain('Enviado');
    });
  });
});
