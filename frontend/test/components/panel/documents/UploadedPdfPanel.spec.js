import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import UploadedPdfPanel from '~/components/panel/documents/UploadedPdfPanel.vue';
import { useDocumentStore } from '~/stores/documents';
import { create_request } from '~/stores/services/request_http';

jest.mock('~/stores/services/request_http', () => ({ create_request: jest.fn(), get_request: jest.fn(), patch_request: jest.fn(), delete_request: jest.fn() }));
jest.mock('~/composables/usePanelNotify', () => ({ usePanelNotify: () => ({ success: jest.fn(), error: jest.fn() }) }));
jest.mock('#imports', () => ({ useI18n: () => ({ t: (key, args = {}) => {
  const messages = require('../../../../locales/documentPdf/es').default;
  return String(messages[key.split('.')[1]] || key).replace(/\{(\w+)\}/g, (_, name) => args[name]);
} }) }));

const doc = { id: 7, pdf_replaceable: true, pdf: { version: 2, filename: 'anexo.pdf', text_status: 'empty' } };
let wrapper;
function render(document = doc) {
  const pinia = createPinia();
  setActivePinia(pinia);
  wrapper = mount(UploadedPdfPanel, { props: { document }, global: { plugins: [pinia], stubs: { NuxtLink: { template: '<a><slot /></a>' } } } });
  return wrapper;
}
async function choose(file) {
  Object.defineProperty(wrapper.get('[data-testid="doc-pdf-replace-file"]').element, 'files', { value: [file], configurable: true });
  await wrapper.get('[data-testid="doc-pdf-replace-file"]').trigger('change');
}

beforeEach(() => {
  jest.clearAllMocks();
  global.fetch = jest.fn().mockResolvedValue({ ok: true });
});
afterEach(() => { wrapper?.unmount(); jest.restoreAllMocks(); });

it('shows the retained PDF with its version and search status', async () => {
  render();
  await flushPromises();
  expect(wrapper.get('[data-testid="doc-pdf-version"]').text()).toContain('Versión 2 · anexo.pdf');
  expect(wrapper.get('[data-testid="doc-uploaded-pdf-frame"]').attributes('src')).toBe('/api/documents/7/pdf/?inline=1&v=2');
  expect(wrapper.get('[data-testid="doc-pdf-text-status"]').text()).toContain('no tiene texto extraíble');
  expect(wrapper.get('[data-testid="doc-pdf-original-download"]').attributes('href')).toContain('/api/documents/7/pdf/');
});

it('rejects unsupported replacement files before sending', async () => {
  render();
  await choose(new File(['word'], 'file.docx'));
  expect(wrapper.get('[role="alert"]').text()).toContain('Selecciona un archivo PDF');
  expect(wrapper.find('[data-testid="doc-pdf-replace-save"]').exists()).toBe(false);
  expect(create_request).not.toHaveBeenCalled();
});

it('retains the reviewed version after the document refreshes', async () => {
  render();
  await choose(new File(['%PDF'], 'next.pdf', { lastModified: 123 }));
  await wrapper.setProps({ document: { ...doc, pdf: { ...doc.pdf, version: 3 } } });
  create_request.mockResolvedValueOnce({ data: { ...doc, pdf: { ...doc.pdf, version: 4 } } });
  await wrapper.get('[data-testid="doc-pdf-replace-save"]').trigger('click');
  await flushPromises();
  expect(create_request.mock.calls[0][1].get('expected_version')).toBe('2');
  expect(wrapper.emitted('pending').at(-1)).toEqual([null]);
  expect(useDocumentStore().currentDocument.pdf.version).toBe(4);
});

it('keeps the selection when replacing fails', async () => {
  render();
  await choose(new File(['%PDF'], 'next.pdf'));
  create_request.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'La versión cambió.' } } });
  await wrapper.get('[data-testid="doc-pdf-replace-save"]').trigger('click');
  await flushPromises();
  expect(wrapper.get('[role="alert"]').text()).toBe('La versión cambió.');
  expect(wrapper.find('[data-testid="doc-pdf-replace-save"]').exists()).toBe(true);
});

it('hides replacement for a protected PDF', async () => {
  render({ ...doc, pdf_replaceable: false });
  await flushPromises();
  expect(wrapper.find('[data-testid="doc-pdf-replace-file"]').exists()).toBe(false);
  expect(wrapper.find('[data-testid="doc-pdf-original-download"]').exists()).toBe(true);
});

it('offers download when inline preview fails', async () => {
  global.fetch.mockResolvedValue({ ok: false });
  render();
  await flushPromises();
  expect(wrapper.get('[data-testid="doc-uploaded-pdf-error"]').text()).toContain('El PDF no está disponible');
  expect(wrapper.get('[data-testid="doc-pdf-original-download"]').attributes('href')).toContain('/pdf/');
});
