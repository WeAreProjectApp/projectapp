/**
 * Tests for the secure_links store.
 * Covers: list filters/counters, create merge without URL, revealed content is
 * never kept in state, public token calls and error normalization.
 */
import { setActivePinia, createPinia } from 'pinia';
import { useSecureLinksStore } from '../../stores/secure_links';

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(),
  create_request: jest.fn(),
  patch_request: jest.fn(),
  delete_request: jest.fn(),
}));

const { get_request, create_request, patch_request, delete_request } = require('../../stores/services/request_http');

const row = { id: 7, title: 'Admin', status: 'active' };

describe('useSecureLinksStore', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useSecureLinksStore();
    jest.clearAllMocks();
  });

  it('requests only the active filters and stores counters and the public page URL', async () => {
    get_request.mockResolvedValue({ data: {
      results: [row], count: 1, page: 2, page_size: 25,
      counts: { active: 1 }, unopened_received: 3, public_create_url: 'https://x/es-co/secure-link',
    } });

    await store.fetchLinks({ status: 'active', received: '', search: '', page: 2 });

    expect(get_request).toHaveBeenCalledWith('secure-links/?status=active&page=2');
    expect(store.links).toEqual([row]);
    expect(store.unopenedReceived).toBe(3);
    expect(store.publicCreateUrl).toBe('https://x/es-co/secure-link');
  });

  it('adds a created link to the list without keeping its one-time URL', async () => {
    create_request.mockResolvedValue({ data: { ...row, url: 'https://x#token' } });

    const result = await store.createLink({ title: 'Admin' });

    expect(result.data.url).toBe('https://x#token');
    expect(store.links).toEqual([row]);
    expect(JSON.stringify(store.$state)).not.toContain('token');
  });

  it('returns revealed panel content without storing it', async () => {
    create_request.mockResolvedValue({ data: { fields: [{ key: 'password', value: 'S3cr3t' }] } });

    const result = await store.viewContent(7);

    expect(create_request).toHaveBeenCalledWith('secure-links/7/content/', {});
    expect(result.data.fields[0].value).toBe('S3cr3t');
    expect(JSON.stringify(store.$state)).not.toContain('S3cr3t');
  });

  it('sends the public token in the request body, never in the path', async () => {
    create_request.mockResolvedValue({ data: { status: 'active' } });

    await store.publicStatus('abc123');
    await store.publicReveal('abc123');

    expect(create_request).toHaveBeenNthCalledWith(1, 'secure-links/public/status/', { token: 'abc123' });
    expect(create_request).toHaveBeenNthCalledWith(2, 'secure-links/public/reveal/', { token: 'abc123' });
  });

  it('normalizes the backend error code for a consumed link', async () => {
    create_request.mockRejectedValue({ response: { status: 410, data: { error: 'Este enlace ya fue utilizado.', code: 'link_consumed' } } });

    const result = await store.publicReveal('abc123');

    expect(result.success).toBe(false);
    expect(result.error.code).toBe('link_consumed');
    expect(result.error.message).toBe('Este enlace ya fue utilizado.');
  });

  it('loads the type catalog once and reuses it', async () => {
    get_request.mockResolvedValue({ data: { types: [{ key: 'credentials', fields: [] }] } });

    await store.fetchTypes();
    await store.fetchTypes();

    expect(get_request).toHaveBeenCalledTimes(1);
    expect(store.typeByKey('credentials').key).toBe('credentials');
    expect(store.typeByKey('missing')).toBeNull();
  });

  it('reports catalog, list and detail failures without breaking state', async () => {
    get_request.mockRejectedValue({ response: { status: 500, data: { detail: 'falló' } } });

    const types = await store.fetchTypes();
    const list = await store.fetchLinks();
    const detail = await store.fetchDetail(7);

    expect(types.success).toBe(false);
    expect(list.success).toBe(false);
    expect(store.error).toBe('fetch_failed');
    expect(store.isLoading).toBe(false);
    expect(detail.error.message).toBe('falló');
  });

  it('updates an existing row in place after reactivation and revocation', async () => {
    store.links = [row];
    store.count = 1;
    create_request.mockResolvedValueOnce({ data: { ...row, status: 'active', url: 'https://x#t' } });
    create_request.mockResolvedValueOnce({ data: { ...row, status: 'revoked' } });

    await store.reactivateLink(7, { validity_days: 3 });
    await store.revokeLink(7);

    expect(store.links).toEqual([{ ...row, status: 'revoked' }]);
    expect(store.count).toBe(1);
  });

  it('returns field errors when a write fails', async () => {
    patch_request.mockRejectedValue({ response: { status: 400, data: { title: ['Obligatorio.'] } } });

    const result = await store.updateLink(7, { title: '' });

    expect(result.success).toBe(false);
    expect(result.error.fieldErrors.title).toBeTruthy();
    expect(store.isUpdating).toBe(false);
  });

  it('reports failures to copy, delete, view or create publicly', async () => {
    create_request.mockRejectedValue({ response: { status: 404, data: { error: 'No existe.' } } });
    delete_request.mockRejectedValue({ response: { status: 500, data: {} } });

    const url = await store.fetchLinkUrl(7);
    const content = await store.viewContent(7);
    const created = await store.publicCreate({});
    const removed = await store.deleteLink(7);

    expect([url.success, content.success, created.success, removed.success]).toEqual([false, false, false, false]);
    expect(url.error.message).toBe('No existe.');
    expect(removed.error.message).toBe('No se pudo eliminar el enlace.');
  });

  it('falls back to empty defaults when the list payload is empty', async () => {
    get_request.mockResolvedValueOnce({ data: undefined });
    get_request.mockResolvedValueOnce({ data: {} });

    await store.fetchLinks();
    const types = await store.fetchTypes();

    expect([store.links, store.count, store.page, store.pageSize, store.counts]).toEqual([[], 0, 1, 25, {}]);
    expect([store.unopenedReceived, store.publicCreateUrl]).toEqual([0, '']);
    expect(types.data).toEqual([]);
  });

  it('reports a missing token on the public status call', async () => {
    create_request.mockRejectedValueOnce({ response: { status: 404, data: { error: 'Este enlace no existe', code: 'link_not_found' } } });

    const result = await store.publicStatus('nope');

    expect(result.error.code).toBe('link_not_found');
  });

  it('ignores rows without id and returns an empty URL when the server omits it', async () => {
    create_request.mockResolvedValueOnce({ data: {} });
    create_request.mockResolvedValueOnce({ data: {} });

    await store.revokeLink(7);
    const url = await store.fetchLinkUrl(7);

    expect(store.links).toEqual([]);
    expect(url).toEqual({ success: true, url: '' });
  });

  it('removes a deleted link from the list', async () => {
    store.links = [row];
    store.count = 1;
    delete_request.mockResolvedValue({});

    await store.deleteLink(7);

    expect(store.links).toEqual([]);
    expect(store.count).toBe(0);
  });
});
