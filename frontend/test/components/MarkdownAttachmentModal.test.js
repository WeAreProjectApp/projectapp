import { mount, flushPromises } from '@vue/test-utils';
import BaseRichTextEditor from '../../components/base/BaseRichTextEditor.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';

const mockAxiosPost = jest.fn();
jest.mock('axios', () => ({
  __esModule: true,
  default: { post: (...args) => mockAxiosPost(...args) },
}));

const mockGetRequest = jest.fn();
jest.mock('../../stores/services/request_http', () => ({
  getCookie: jest.fn(() => 'test-csrf-token'),
  get_request: (...args) => mockGetRequest(...args),
}));

import MarkdownAttachmentModal from '../../components/MarkdownAttachmentModal.vue';

const originalUseI18n = global.useI18n;
beforeEach(() => { global.useI18n = () => ({ t: (key) => key }); });
afterAll(() => { global.useI18n = originalUseI18n; });

async function editMarkdownSource(wrapper, value) {
  await wrapper.findAll('[role="tab"]').find((tab) => tab.text() === 'richText.source').trigger('click');
  await wrapper.get('[data-testid="rich-text-source-input"]').setValue(value);
}

function markdownSource(wrapper) {
  return wrapper.get('[data-testid="rich-text-source-input"]');
}

function getAxiosMock() {
  return mockAxiosPost;
}

function mountModal(props = {}) {
  return mount(MarkdownAttachmentModal, {
    props: { open: true, endpoint: 'proposals/42/proposal-email/markdown-attachment/', ...props },
    global: { components: { BaseRichTextEditor, BaseSegmented }, stubs: { Teleport: true } },
  });
}

describe('MarkdownAttachmentModal', () => {
  beforeEach(() => {
    getAxiosMock().mockReset();
    mockGetRequest.mockReset();
    URL.createObjectURL = jest.fn(() => 'blob:http://localhost/fake-id');
    URL.revokeObjectURL = jest.fn();
  });

  it('does not render modal content when open is false', () => {
    const wrapper = mount(MarkdownAttachmentModal, {
      props: { open: false, endpoint: 'proposals/42/proposal-email/markdown-attachment/' },
      global: { components: { BaseRichTextEditor, BaseSegmented }, stubs: { Teleport: true } },
    });

    expect(wrapper.find('h2').exists()).toBe(false);
  });

  it('renders modal content when open is true', () => {
    const wrapper = mountModal();

    expect(wrapper.find('h2').text()).toContain('Adjuntar documento PDF');
  });

  it('preview button is disabled when title is empty', async () => {
    const wrapper = mountModal();
    await editMarkdownSource(wrapper, '# Contenido de prueba');

    const previewBtn = wrapper.findAll('button').find((b) => b.text().includes('Vista previa'));

    expect(previewBtn.element.disabled).toBe(true);
  });

  it('preview button is disabled when markdown content is empty', async () => {
    const wrapper = mountModal();
    await wrapper.find('input[type="text"]').setValue('Título del documento');

    const previewBtn = wrapper.findAll('button').find((b) => b.text().includes('Vista previa'));

    expect(previewBtn.element.disabled).toBe(true);
  });

  it('preview button is enabled when both title and markdown are filled', async () => {
    const wrapper = mountModal();
    await wrapper.find('input[type="text"]').setValue('Mi documento');
    await editMarkdownSource(wrapper, '# Encabezado\n\nTexto de contenido.');

    const previewBtn = wrapper.findAll('button').find((b) => b.text().includes('Vista previa'));

    expect(previewBtn.element.disabled).toBe(false);
  });

  it('all three cover checkboxes are checked by default', () => {
    const wrapper = mountModal();
    const checkboxes = wrapper.findAll('input[type="checkbox"]');

    expect(checkboxes).toHaveLength(3);
    checkboxes.forEach((cb) => {
      expect(cb.element.checked).toBe(true);
    });
  });

  it('emits close when Cancelar button is clicked', async () => {
    const wrapper = mountModal();

    await wrapper.findAll('button').find((b) => b.text() === 'Cancelar').trigger('click');

    expect(wrapper.emitted('close')).toBeTruthy();
  });

  it('emits close when backdrop overlay is clicked', async () => {
    const wrapper = mountModal();

    await wrapper.find('.fixed.inset-0').trigger('click');

    expect(wrapper.emitted('close')).toBeTruthy();
  });

  it('renders iframe preview after successful preview generation', async () => {
    const pdfBlob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    getAxiosMock().mockResolvedValue({ data: pdfBlob });

    const wrapper = mountModal();
    await wrapper.find('input[type="text"]').setValue('Informe técnico');
    await editMarkdownSource(wrapper, '# Contenido\n\nPárrafo.');

    const previewBtn = wrapper.findAll('button').find((b) => b.text().includes('Vista previa'));
    await previewBtn.trigger('click');
    for (let i = 0; i < 5; i++) await flushPromises();

    expect(wrapper.find('iframe').exists()).toBe(true);
  });

  it('emits attach with a File and closes when Adjuntar clicked after preview', async () => {
    const pdfBlob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    getAxiosMock().mockResolvedValue({ data: pdfBlob });

    global.fetch = jest.fn().mockResolvedValue({ blob: () => Promise.resolve(pdfBlob) });

    const wrapper = mountModal();
    await wrapper.find('input[type="text"]').setValue('Mi reporte');
    await editMarkdownSource(wrapper, '# Encabezado\n\nContenido.');

    const previewBtn = wrapper.findAll('button').find((b) => b.text().includes('Vista previa'));
    await previewBtn.trigger('click');
    await flushPromises();
    await flushPromises();

    const attachBtn = wrapper.findAll('button').find((b) => b.text().includes('Adjuntar'));
    await attachBtn.trigger('click');
    for (let i = 0; i < 5; i++) await flushPromises();

    expect(wrapper.emitted('attach')).toBeTruthy();
    expect(wrapper.emitted('attach')[0][0]).toBeInstanceOf(File);
    expect(wrapper.emitted('attach')[0][0].name).toBe('mi-reporte.pdf');
    expect(wrapper.emitted('close')).toBeTruthy();
  });

  it('does not render diagnostic template buttons by default', () => {
    const wrapper = mountModal();

    const texts = wrapper.findAll('button').map((b) => b.text());
    expect(texts.some((t) => t.startsWith('Copiar Diagnóstico'))).toBe(false);
    expect(wrapper.text()).not.toContain('Plantillas base');
  });

  it('renders 3 diagnostic template copy buttons in the requested order when showDiagnosticTemplates is true', () => {
    const wrapper = mountModal({ showDiagnosticTemplates: true });

    const templateButtons = wrapper.findAll('button')
      .map((b) => b.text())
      .filter((t) => t.startsWith('Copiar '));

    expect(templateButtons).toEqual([
      'Copiar Diagnóstico de Aplicación',
      'Copiar Diagnóstico Técnico',
      'Copiar Anexo',
    ]);
    expect(wrapper.text()).toContain('Plantillas base');
  });

  it('fetches the template and writes its markdown to the clipboard when a copy button is clicked', async () => {
    mockGetRequest.mockResolvedValue({
      data: { content_markdown: '# Plantilla técnica\n\nContenido base.' },
    });
    const writeText = jest.fn().mockResolvedValue();
    Object.assign(navigator, { clipboard: { writeText } });

    const wrapper = mountModal({ showDiagnosticTemplates: true });
    const btn = wrapper.findAll('button')
      .filter((b) => b.text().startsWith('Copiar '))[1];
    await btn.trigger('click');
    await flushPromises();

    expect(mockGetRequest).toHaveBeenCalledWith('diagnostic-templates/diagnostico-tecnico/');
    expect(writeText).toHaveBeenCalledWith('# Plantilla técnica\n\nContenido base.');
    expect(wrapper.text()).toContain('¡Copiado!');
  });

  it('uses cached template on second click without re-fetching', async () => {
    mockGetRequest.mockResolvedValue({
      data: { content_markdown: '# Aplicación\n\nBase.' },
    });
    const writeText = jest.fn().mockResolvedValue();
    Object.assign(navigator, { clipboard: { writeText } });

    const wrapper = mountModal({ showDiagnosticTemplates: true });
    // Re-query between clicks instead of holding one wrapper: the copy button
    // is a BaseButton, and Vue re-creates its root element when the label flips
    // to '¡Copiado!', which leaves a held wrapper pointing at a detached node
    // Vue has already stripped the listener from. A real user always clicks
    // whatever element is currently in the DOM.
    const firstCopyButton = () => wrapper.findAll('button')
      .filter((b) => b.text().startsWith('Copiar ') || b.text() === '¡Copiado!')[0];

    await firstCopyButton().trigger('click');
    await flushPromises();
    await firstCopyButton().trigger('click');
    await flushPromises();

    expect(mockGetRequest).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledTimes(2);
  });

  it('shows error message when get_request rejects during copy', async () => {
    mockGetRequest.mockRejectedValue(new Error('Network error'));
    Object.assign(navigator, { clipboard: { writeText: jest.fn().mockResolvedValue() } });

    const wrapper = mountModal({ showDiagnosticTemplates: true });
    const btn = wrapper.findAll('button').filter((b) => b.text().startsWith('Copiar '))[0];
    await btn.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('No se pudo copiar la plantilla.');
  });

  it('shows error message when clipboard.writeText rejects', async () => {
    mockGetRequest.mockResolvedValue({ data: { content_markdown: '# Contenido' } });
    Object.assign(navigator, { clipboard: { writeText: jest.fn().mockRejectedValue(new Error('Clipboard denied')) } });

    const wrapper = mountModal({ showDiagnosticTemplates: true });
    const btn = wrapper.findAll('button').filter((b) => b.text().startsWith('Copiar '))[0];
    await btn.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('No se pudo copiar la plantilla.');
  });

  it('copy button is re-enabled after a failed request', async () => {
    mockGetRequest.mockRejectedValue(new Error('Network error'));
    Object.assign(navigator, { clipboard: { writeText: jest.fn() } });

    const wrapper = mountModal({ showDiagnosticTemplates: true });
    const btn = wrapper.findAll('button').filter((b) => b.text().startsWith('Copiar '))[0];
    await btn.trigger('click');
    await flushPromises();

    expect(btn.element.disabled).toBe(false);
  });

  it('resets title and markdown when modal is closed', async () => {
    const wrapper = mountModal();
    await wrapper.find('input[type="text"]').setValue('Borrador');
    await editMarkdownSource(wrapper, '# Borrador');

    await wrapper.setProps({ open: false });
    await flushPromises();
    await wrapper.setProps({ open: true });

    expect(wrapper.find('input[type="text"]').element.value).toBe('');
    expect(markdownSource(wrapper).element.value).toBe('');
  });
});
