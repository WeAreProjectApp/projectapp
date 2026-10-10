import { createPinia, setActivePinia } from 'pinia';
import { normalizeMirrorStatus, useBuildingWithUsStore } from '../../stores/building_with_us';
import { get_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));

const makeVersion = (overrides = {}) => ({
  version_id: 21, version: 2, author: 'Ana', created_at: '2026-10-09T15:00:00Z',
  change_note: 'Alianza actualizada', restored_from_version_id: null, ...overrides,
});
const makeProgram = (title = 'Incubamos productos juntos') => ({ hero: { title } });
const makeOverview = () => ({
  program: makeVersion(), contract: null,
  connector: { slug: 'building-with-us', is_active: true },
  public_paths: { es: '/es-co/building-with-us', en: '/en-us/building-with-us' },
});
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe('useBuildingWithUsStore', () => {
  let store;
  beforeEach(() => {
    setActivePinia(createPinia());
    store = useBuildingWithUsStore();
    get_request.mockReset();
  });
  afterEach(() => { jest.restoreAllMocks(); });

  it('loads the module overview', async () => {
    const overview = makeOverview();
    get_request.mockResolvedValue({ data: overview });

    const result = await store.fetchOverview();

    expect(get_request).toHaveBeenCalledWith('building-with-us/admin/');
    expect(result).toEqual({ success: true, data: overview });
    expect(store.programSummary).toEqual(overview.program);
    expect(store.contractSummary).toBeNull();
    expect(store.isLoadingOverview).toBe(false);
  });

  it('returns request errors without throwing', async () => {
    const errors = { detail: 'No autorizado' };
    get_request.mockRejectedValue({ response: { data: errors } });

    await expect(store.fetchOverview()).resolves.toEqual({ success: false, errors });

    expect(store.overviewError).toBe('No autorizado');
    expect(store.isLoadingOverview).toBe(false);
  });

  it('sends the selected preview language', async () => {
    const program = makeProgram('We incubate products together');
    get_request.mockResolvedValue({ data: program });

    await store.fetchPreview('en');

    expect(get_request).toHaveBeenCalledWith('building-with-us/public/?lang=en');
    expect(store.previewLanguage).toBe('en');
    expect(store.preview).toEqual(program);
  });

  it('drops an older preview response', async () => {
    const older = deferred();
    const english = makeProgram('We build together');
    get_request.mockReturnValueOnce(older.promise).mockResolvedValueOnce({ data: english });
    const firstRequest = store.fetchPreview('es');

    await store.fetchPreview('en');
    older.resolve({ data: makeProgram() });
    await firstRequest;

    expect(store.preview).toEqual(english);
    expect(store.previewLanguage).toBe('en');
    expect(store.isLoadingPreview).toBe(false);
  });

  it('preserves the latest preview after an older request fails', async () => {
    const older = deferred();
    const english = makeProgram('We build together');
    get_request.mockReturnValueOnce(older.promise).mockResolvedValueOnce({ data: english });
    const firstRequest = store.fetchPreview('es');

    await store.fetchPreview('en');
    older.reject(new Error('Connection lost'));
    await firstRequest;

    expect(store.preview).toEqual(english);
    expect(store.previewError).toBe('');
  });

  it('rejects preview data without a program title', async () => {
    get_request.mockResolvedValue({ data: { hero: { title: ' ' } } });

    const result = await store.fetchPreview('es');

    expect(result).toEqual({ success: false, errors: { detail: 'invalid_program' } });
    expect(store.preview).toBeNull();
    expect(store.previewError).toBe('invalid_program');
    expect(store.isLoadingPreview).toBe(false);
  });

  it('appends versions from the next offset', async () => {
    const first = makeVersion();
    const next = makeVersion({ version_id: 20, version: 1 });
    get_request.mockResolvedValueOnce({ data: { versions: [first], total: 3 } })
      .mockResolvedValueOnce({ data: { versions: [next], total: 3 } });
    await store.fetchVersions('program');

    await store.fetchVersions('program', { append: true });

    expect(get_request).toHaveBeenLastCalledWith('building-with-us/admin/program/versions/?limit=20&offset=1');
    expect(store.history.program.versions).toEqual([first, next]);
    expect(store.hasMoreVersions('program')).toBe(true);
  });

  it('replaces versions when refreshing history', async () => {
    const fresh = makeVersion({ version_id: 30, version: 3 });
    get_request.mockResolvedValueOnce({ data: { versions: [makeVersion()], total: 1 } })
      .mockResolvedValueOnce({ data: { versions: [fresh] } });
    await store.fetchVersions('contract');

    await store.fetchVersions('contract');

    expect(get_request).toHaveBeenLastCalledWith('building-with-us/admin/contract/versions/?limit=20&offset=0');
    expect(store.history.contract.versions).toEqual([fresh]);
    expect(store.history.contract.total).toBe(1);
    expect(store.hasMoreVersions('contract')).toBe(false);
  });

  it('tolerates a missing versions list', async () => {
    get_request.mockResolvedValue({ data: {} });

    const result = await store.fetchVersions('program');

    expect(result.success).toBe(true);
    expect(store.history.program.versions).toEqual([]);
    expect(store.history.program.total).toBe(0);
    expect(store.history.program.isLoading).toBe(false);
  });

  it('loads the alliance contract', async () => {
    const contract = {
      ...makeVersion(), markdown: '# Alianza', etag: 'contract-2',
      mirror: { status: 'synced', document_id: 15 },
    };
    get_request.mockResolvedValue({ data: contract });

    const result = await store.fetchContract();

    expect(get_request).toHaveBeenCalledWith('building-with-us/admin/contract/');
    expect(result).toEqual({ success: true, data: contract });
    expect(store.contract).toEqual(contract);
    expect(store.mirror).toEqual(contract.mirror);
    expect(store.mirrorStatus).toBe('synchronized');
  });
});

describe('normalizeMirrorStatus', () => {
  it.each([
    ['synchronized', 'synchronized'], ['synced', 'synchronized'], ['in_sync', 'synchronized'],
    ['out_of_sync', 'out_of_sync'], ['stale', 'out_of_sync'], ['outdated', 'out_of_sync'],
    [null, 'not_initialized'], [undefined, 'not_initialized'], ['not_initialized', 'not_initialized'],
    ['unexpected', 'unknown'],
  ])('normalizes %s as %s', (value, expected) => {
    expect(normalizeMirrorStatus(value)).toBe(expected);
  });
});
