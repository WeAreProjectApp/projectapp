import { setActivePinia, createPinia } from 'pinia';
import { useDocumentStore } from '../../stores/documents';
import { create_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(), patch_request: jest.fn(), create_request: jest.fn(), delete_request: jest.fn(),
}));

beforeEach(() => {
  setActivePinia(createPinia());
  jest.clearAllMocks();
});

it('creates a PDF with multipart associations and private notes', async () => {
  const store = useDocumentStore();
  const file = new File(['%PDF'], 'original.pdf', { type: 'application/pdf' });
  const notes = [{ title: 'Nota', content: 'Privado' }];
  create_request.mockResolvedValueOnce({ data: { id: 7, content_format: 'pdf', pdf: { version: 1 } } });
  const result = await store.createFromPdf(file, { title: 'Anexo', client: null, project: 4, client_custom_notes: notes });
  const [url, body] = create_request.mock.calls[0];
  expect(url).toBe('documents/create-from-pdf/');
  expect(body.get('file')).toBe(file);
  expect(body.get('client')).toBe('');
  expect(body.get('project')).toBe('4');
  expect(JSON.parse(body.get('client_custom_notes'))).toEqual(notes);
  expect(result.data.pdf.version).toBe(1);
});

it('sends the reviewed PDF version when replacing', async () => {
  const store = useDocumentStore();
  create_request.mockResolvedValueOnce({ data: { id: 7, pdf: { version: 3 } } });
  await store.replacePdf(7, new File(['%PDF'], 'replacement.pdf'), 2);
  const [url, body] = create_request.mock.calls[0];
  expect(url).toBe('documents/7/replace-pdf/');
  expect(body.get('expected_version')).toBe('2');
  expect(store.currentDocument.pdf.version).toBe(3);
});

it('preserves the current PDF after a stale replacement', async () => {
  const store = useDocumentStore();
  store.currentDocument = { id: 7, pdf: { version: 2 } };
  create_request.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Recarga el documento.' } } });
  const result = await store.replacePdf(7, new File(['%PDF'], 'replacement.pdf'), 1);
  expect(result).toMatchObject({ success: false, message: 'Recarga el documento.', status: 409 });
  expect(store.currentDocument.pdf.version).toBe(2);
  expect(store.isUpdating).toBe(false);
});

it('explains transport rejection when nginx returns HTML', async () => {
  const store = useDocumentStore();
  create_request.mockRejectedValueOnce({ response: { status: 413, data: '<html>too large</html>', headers: { 'content-type': 'text/html' } } });
  const result = await store.createFromPdf(new File(['%PDF'], 'large.pdf'), { title: 'PDF' });
  expect(result.success).toBe(false);
  expect(result.message).toContain('25 MiB');
  expect(store.currentDocument).toBeNull();
});
