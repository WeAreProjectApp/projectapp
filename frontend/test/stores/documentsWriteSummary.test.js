import { setActivePinia, createPinia } from 'pinia';
import { useDocumentStore } from '../../stores/documents';
import { get_request, patch_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(), patch_request: jest.fn(), create_request: jest.fn(), delete_request: jest.fn(),
}));

beforeEach(() => {
  setActivePinia(createPinia());
  jest.clearAllMocks();
});

test('moving a different document preserves the open editor', async () => {
  const store = useDocumentStore();
  store.currentDocument = { id: 7, content_markdown: '# Unsaved' };
  patch_request.mockResolvedValueOnce({ data: { id: 8, folder_id: 2, title: 'Moved' } });
  await store.updateDocument(8, { folder_id: 2 });
  expect(store.currentDocument).toEqual({ id: 7, content_markdown: '# Unsaved' });
  expect(get_request).not.toHaveBeenCalled();
});

test('editor save reloads detail after the compact response', async () => {
  const store = useDocumentStore();
  patch_request.mockResolvedValueOnce({ data: { id: 7, title: 'Saved', folder_id: null } });
  get_request.mockResolvedValueOnce({ data: { id: 7, title: 'Saved', content_markdown: '# New' } });
  const result = await store.updateDocument(7, { content_markdown: '# New' }, { refreshDetail: true });
  expect(result.data.content_markdown).toBe('# New');
  expect(store.currentDocument.content_markdown).toBe('# New');
});

test('a detail refresh failure does not misreport a committed save', async () => {
  const store = useDocumentStore();
  store.currentDocument = { id: 7, title: 'Old', content_markdown: '# Original' };
  patch_request.mockResolvedValueOnce({ data: { id: 7, title: 'Saved', folder_id: null } });
  get_request.mockRejectedValueOnce(new Error('offline'));
  const result = await store.updateDocument(7, { title: 'Saved' }, { refreshDetail: true });
  expect(result).toMatchObject({ success: true, refreshFailed: true });
  expect(store.currentDocument.content_markdown).toBe('# Original');
});
