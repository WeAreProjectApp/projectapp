import { createPinia, setActivePinia } from 'pinia';
import { useConsultingStore } from '../../stores/consulting';
import { get_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));

const makeProgram = (language = 'es') => ({
  language,
  hero: { title: language === 'en' ? 'Business health assessment' : 'Diagnóstico de salud empresarial' },
});

const makeVersion = (versionId, version) => ({
  version_id: versionId,
  version,
  author: 'Ana',
  created_at: '2026-10-23T10:00:00Z',
  change_note: 'Contenido actualizado',
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe('useConsultingStore', () => {
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    store = useConsultingStore();
    get_request.mockReset();
  });

  it('recovers the overview after a failed request', async () => {
    // Bug caught: a transient admin request failure could leave the panel unable to show its recovered program summary.
    const overview = { program: { version: 3, author: 'Ana' } };
    get_request.mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ data: overview });

    await store.fetchOverview();
    expect({ error: store.overviewError, summary: store.programSummary, loading: store.isLoadingOverview })
      .toEqual({ error: 'request_failed', summary: null, loading: false });

    await store.fetchOverview();

    expect(get_request).toHaveBeenLastCalledWith('consulting/admin/');
    expect({ error: store.overviewError, summary: store.programSummary, loading: store.isLoadingOverview })
      .toEqual({ error: '', summary: { version: 3, author: 'Ana' }, loading: false });
  });

  it('keeps the latest English preview when an earlier Spanish request settles late', async () => {
    // Bug caught: a slow Spanish response could overwrite the language a manager most recently selected.
    const slowSpanish = deferred();
    const english = makeProgram('en');
    get_request.mockReturnValueOnce(slowSpanish.promise)
      .mockResolvedValueOnce({ data: english });

    const staleRequest = store.fetchPreview('es-co');
    await store.fetchPreview('en-us');
    slowSpanish.resolve({ data: makeProgram('es') });
    await staleRequest;

    expect(get_request.mock.calls.map(([path]) => path))
      .toEqual(['consulting/public/?lang=es', 'consulting/public/?lang=en']);
    expect({ preview: store.preview, language: store.previewLanguage, error: store.previewError, loading: store.isLoadingPreview })
      .toEqual({ preview: english, language: 'en', error: '', loading: false });
  });

  it('ignores a rejected preview request superseded by a newer language', async () => {
    // Bug caught: an old network error could hide a successful preview that replaced it.
    const slowSpanish = deferred();
    const english = makeProgram('en');
    get_request.mockReturnValueOnce(slowSpanish.promise)
      .mockResolvedValueOnce({ data: english });

    const staleRequest = store.fetchPreview('es');
    await store.fetchPreview('en');
    slowSpanish.reject(new Error('offline'));
    await staleRequest;

    expect({ preview: store.preview, language: store.previewLanguage, error: store.previewError, loading: store.isLoadingPreview })
      .toEqual({ preview: english, language: 'en', error: '', loading: false });
  });

  it('replaces an invalid preview with a valid retry', async () => {
    // Bug caught: malformed public content could be displayed or keep the retry in an error state after valid content arrives.
    const english = makeProgram('en');
    get_request.mockResolvedValueOnce({ data: { hero: { title: '   ' } } })
      .mockResolvedValueOnce({ data: english });

    await store.fetchPreview('es');
    expect({ preview: store.preview, error: store.previewError, loading: store.isLoadingPreview })
      .toEqual({ preview: null, error: 'request_failed', loading: false });

    await store.fetchPreview('en');

    expect({ preview: store.preview, language: store.previewLanguage, error: store.previewError, loading: store.isLoadingPreview })
      .toEqual({ preview: english, language: 'en', error: '', loading: false });
  });

  it('appends the next version page after the loaded history', async () => {
    // Bug caught: loading more revisions could replace the first page or request the wrong offset.
    const first = makeVersion(31, 3);
    const next = makeVersion(30, 2);
    get_request.mockResolvedValueOnce({ data: { versions: [first], total: 2 } })
      .mockResolvedValueOnce({ data: { versions: [next], total: 2 } });

    await store.fetchVersions();
    await store.fetchVersions({ append: true });

    expect(get_request.mock.calls.map(([path]) => path)).toEqual([
      'consulting/admin/program/versions/?limit=20&offset=0',
      'consulting/admin/program/versions/?limit=20&offset=1',
    ]);
    expect(store.history).toEqual({ versions: [first, next], total: 2, isLoading: false, error: '' });
  });

  it('retries a failed history page without losing the existing revisions', async () => {
    // Bug caught: retrying the next page could erase already visible revisions or advance past the failed offset.
    const first = makeVersion(31, 3);
    const next = makeVersion(30, 2);
    get_request.mockResolvedValueOnce({ data: { versions: [first], total: 2 } })
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ data: { versions: [next], total: 2 } });

    await store.fetchVersions();
    await store.fetchVersions({ append: true });
    expect(store.history).toEqual({ versions: [first], total: 2, isLoading: false, error: 'request_failed' });

    await store.fetchVersions({ append: true });

    expect(get_request.mock.calls.map(([path]) => path)).toEqual([
      'consulting/admin/program/versions/?limit=20&offset=0',
      'consulting/admin/program/versions/?limit=20&offset=1',
      'consulting/admin/program/versions/?limit=20&offset=1',
    ]);
    expect(store.history).toEqual({ versions: [first, next], total: 2, isLoading: false, error: '' });
  });
});
