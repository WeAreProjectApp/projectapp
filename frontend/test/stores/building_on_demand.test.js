import { createPinia, setActivePinia } from 'pinia';
import { normalizeMirrorStatus, useBuildingOnDemandStore } from '../../stores/building_on_demand';
import { get_request } from '../../stores/services/request_http';

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));

const makeVersion = (overrides = {}) => ({
  version_id: 21, version: 2, author: 'Ana', created_at: '2026-10-10T15:00:00Z',
  change_note: 'Bolsa de horas actualizada', restored_from_version_id: null,
  restored_from_version: null, ...overrides,
});
const makeOverview = (overrides = {}) => ({
  program: { ...makeVersion(), updated_at: '2026-10-10T15:00:00Z', etag: 'program-2' },
  contract: null,
  connector: { slug: 'building-on-demand', is_active: false },
  public_paths: { es: '/es-co/building-on-demand', en: '/en-us/building-on-demand' },
  pdf_paths: {
    es: '/api/building-on-demand/public/pdf/?lang=es',
    en: '/api/building-on-demand/public/pdf/?lang=en',
  },
  ...overrides,
});
const makeProgram = (language = 'es') => ({
  language, hero: { title: language === 'en' ? 'A cell for your product' : 'Una célula para tu producto' },
});
const makeContract = (overrides = {}) => ({
  ...makeVersion(), updated_at: '2026-10-10T15:00:00Z', markdown: '# Célula compartida', etag: 'contract-2',
  mirror: { status: 'synchronized', document_id: 15, folder_path: '/Comercial/Células' },
  ...overrides,
});
const makeEconomics = (overrides = {}) => ({
  currency: 'COP', hour_cost: 55000, vat_percent: 19, provider: 'Hostinger',
  reference_url: 'https://www.hostinger.com/co/vps-servidor-web', consulted_on: '2026-10-10',
  tiers: [{ id: 'business', name: 'Business', bag_hours: 192, plan: 'KVM 4',
    promo_monthly: 38900, renewal_monthly: 97900, hosting_cost_monthly: 116501 }],
  rows: [
    { tier: 'business', term: 'monthly', months: 1, monthly_price: 4200000, hosting_cost_monthly: 116501,
      net_monthly: 4083499, breakeven_hours: 74.2, breakeven_hours_rounded: 74, bag_hours: 192,
      bag_share_percent: 39, breakeven_hours_without_hosting: 76.4 },
    { tier: 'starter', term: 'nine-month', months: 9, monthly_price: 1530000, hosting_cost_monthly: 46291,
      net_monthly: 1483709, breakeven_hours: 27.0, breakeven_hours_rounded: 27, bag_hours: 96,
      bag_share_percent: 28, breakeven_hours_without_hosting: 27.8 },
    { tier: 'business', term: 'nine-month', months: 9, monthly_price: 3360000, hosting_cost_monthly: 116501,
      net_monthly: 3243499, breakeven_hours: 59.0, breakeven_hours_rounded: 59, bag_hours: 192,
      bag_share_percent: 31, breakeven_hours_without_hosting: 61.1 },
    { tier: 'enterprise', term: 'nine-month', months: 9, monthly_price: 7200000, hosting_cost_monthly: 200991,
      net_monthly: 6999009, breakeven_hours: 127.3, breakeven_hours_rounded: 127, bag_hours: 288,
      bag_share_percent: 44, breakeven_hours_without_hosting: 130.9 },
  ],
  ...overrides,
});
const httpError = (status, data = { message: 'Solicitud rechazada', code: 'NOT_FOUND', details: {} }) => ({
  response: { status, data },
});
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe('useBuildingOnDemandStore', () => {
  let store;
  beforeEach(() => {
    setActivePinia(createPinia());
    store = useBuildingOnDemandStore();
    get_request.mockReset();
  });
  afterEach(() => { jest.restoreAllMocks(); });

  describe('overview requests', () => {
    it('exposes distribution metadata with a pending contract', async () => {
      const overview = makeOverview();
      get_request.mockResolvedValue({ data: overview });

      const result = await store.fetchOverview();

      expect(get_request).toHaveBeenCalledWith('building-on-demand/admin/');
      expect(result).toEqual({ success: true, data: overview });
      expect(store.overview).toEqual(overview);
      expect(store.programSummary).toEqual(overview.program);
      expect({ contract: store.contractSummary, mirror: store.mirror, status: store.mirrorStatus })
        .toEqual({ contract: null, mirror: null, status: 'not_initialized' });
      expect(store.connector).toEqual({ slug: 'building-on-demand', is_active: false });
    });

    it('keeps the overview pending until its response arrives', async () => {
      const request = deferred();
      const overview = makeOverview();
      get_request.mockReturnValue(request.promise);

      const pending = store.fetchOverview();
      expect(store.isLoadingOverview).toBe(true);
      expect({ summary: store.programSummary, connector: store.connector })
        .toEqual({ summary: null, connector: null });
      request.resolve({ data: overview });
      await pending;

      expect(store.isLoadingOverview).toBe(false);
      expect(store.programSummary.version).toBe(2);
    });

    it('reports the backend explanation for a rejected overview', async () => {
      const errors = { message: 'Debes iniciar sesión', code: 'NOT_AUTHORIZED', details: {} };
      get_request.mockRejectedValue(httpError(403, errors));

      const result = await store.fetchOverview();

      expect(result).toEqual({ success: false, errors });
      expect(store.overviewError).toBe('Debes iniciar sesión');
      expect(store.isLoadingOverview).toBe(false);
      expect(store.overview).toBeNull();
    });

    it('returns structured validation errors without inventing an explanation', async () => {
      const errors = { lang: ['Usa es o en.'] };
      get_request.mockRejectedValue(httpError(400, errors));

      const result = await store.fetchOverview();

      expect(result).toEqual({ success: false, errors });
      expect(store.overviewError).toBe('request_failed');
      expect(store.isLoadingOverview).toBe(false);
    });

    it('preserves the cached overview during a connection failure', async () => {
      const overview = makeOverview();
      get_request.mockResolvedValueOnce({ data: overview }).mockRejectedValueOnce(new Error('Offline'));
      await store.fetchOverview();

      const result = await store.fetchOverview();

      expect(result).toEqual({ success: false, errors: { detail: 'request_failed' } });
      expect(store.overview).toEqual(overview);
      expect(store.overviewError).toBe('request_failed');
      expect(store.isLoadingOverview).toBe(false);
    });

    it('refreshes the connector availability after a retry', async () => {
      const overview = makeOverview({ connector: { slug: 'building-on-demand', is_active: true } });
      get_request.mockRejectedValueOnce(httpError(500))
        .mockResolvedValueOnce({ data: overview });
      await store.fetchOverview();

      await store.fetchOverview();

      expect(store.connector).toEqual({ slug: 'building-on-demand', is_active: true });
      expect(store.overviewError).toBe('');
      expect(store.isLoadingOverview).toBe(false);
    });
  });

  describe('economics requests', () => {
    it('preserves the backend breakeven calculations', async () => {
      const economics = makeEconomics();
      get_request.mockResolvedValue({ data: economics });

      const result = await store.fetchEconomics();

      expect(get_request).toHaveBeenCalledWith('building-on-demand/admin/economics/');
      expect(result).toEqual({ success: true, data: economics });
      expect(store.economics).toEqual(economics);
      expect(store.economicsRows).toEqual(economics.rows);
      expect(store.economicsRows.map(({ breakeven_hours, bag_share_percent }) => [breakeven_hours, bag_share_percent]))
        .toEqual([[74.2, 39], [27.0, 28], [59.0, 31], [127.3, 44]]);
      expect(store.isLoadingEconomics).toBe(false);
    });

    it('keeps economics pending until its inputs arrive', async () => {
      const request = deferred();
      const economics = makeEconomics();
      get_request.mockReturnValue(request.promise);

      const pending = store.fetchEconomics();
      expect(store.isLoadingEconomics).toBe(true);
      expect(store.economicsRows).toEqual([]);
      request.resolve({ data: economics });
      await pending;

      expect(store.isLoadingEconomics).toBe(false);
      expect(store.economics.hour_cost).toBe(55000);
    });

    it('clears an economics error after recovery', async () => {
      const errors = { detail: 'No autorizado' };
      get_request.mockRejectedValueOnce(httpError(403, errors))
        .mockResolvedValueOnce({ data: makeEconomics() });

      const rejected = await store.fetchEconomics();
      expect(rejected).toEqual({ success: false, errors });
      expect(store.economicsError).toBe('No autorizado');
      expect(store.isLoadingEconomics).toBe(false);
      await store.fetchEconomics();

      expect(store.economicsError).toBe('');
      expect(store.economicsRows).toHaveLength(4);
    });

    it.each([null, {}, { rows: null }, { rows: {} }])('renders no economics rows for an incomplete response %j', async (data) => {
      get_request.mockResolvedValue({ data });

      const result = await store.fetchEconomics();

      expect(result).toEqual({ success: true, data });
      expect(store.economicsRows).toEqual([]);
      expect(store.isLoadingEconomics).toBe(false);
    });
  });

  describe('preview requests', () => {
    it.each([['en', 'en'], ['en-us', 'en'], ['es-co', 'es'], [null, 'es']])
      ('normalizes the preview locale %s to %s', async (locale, language) => {
        const program = makeProgram(language);
        get_request.mockResolvedValue({ data: program });

        const result = await store.fetchPreview(locale);

        expect(get_request).toHaveBeenCalledWith(`building-on-demand/public/?lang=${language}`);
        expect(result).toEqual({ success: true, data: program });
        expect({ language: store.previewLanguage, program: store.preview }).toEqual({ language, program });
        expect(store.isLoadingPreview).toBe(false);
      });

    it('defaults the preview request to Spanish', async () => {
      get_request.mockResolvedValue({ data: makeProgram() });

      const result = await store.fetchPreview();

      expect(get_request).toHaveBeenCalledWith('building-on-demand/public/?lang=es');
      expect(result.data.hero.title).toBe('Una célula para tu producto');
      expect(store.previewLanguage).toBe('es');
    });

    it.each([null, 42, [{ hero: { title: 'Célula' } }], { hero: { title: ' ' } }, { hero: { title: 123 } }])
      ('rejects a malformed preview payload %j', async (data) => {
        get_request.mockResolvedValue({ data });

        const result = await store.fetchPreview('es');

        expect(result).toEqual({ success: false, errors: { detail: 'invalid_program' } });
        expect({ preview: store.preview, error: store.previewError, pending: store.isLoadingPreview })
          .toEqual({ preview: null, error: 'invalid_program', pending: false });
      });

    it('retains the newer English preview after a stale success', async () => {
      const stale = deferred();
      const english = makeProgram('en');
      get_request.mockReturnValueOnce(stale.promise).mockResolvedValueOnce({ data: english });
      const pending = store.fetchPreview('es');
      await store.fetchPreview('en');

      stale.resolve({ data: makeProgram() });
      const staleResult = await pending;

      expect(staleResult.success).toBe(true);
      expect({ preview: store.preview, language: store.previewLanguage, error: store.previewError })
        .toEqual({ preview: english, language: 'en', error: '' });
      expect(store.isLoadingPreview).toBe(false);
    });

    it('ignores the error from a superseded preview request', async () => {
      const stale = deferred();
      const english = makeProgram('en');
      get_request.mockReturnValueOnce(stale.promise).mockResolvedValueOnce({ data: english });
      const pending = store.fetchPreview('es');
      await store.fetchPreview('en');

      stale.reject(httpError(500));
      const staleResult = await pending;

      expect(staleResult).toEqual({ success: false, errors: httpError(500).response.data });
      expect(store.preview).toEqual(english);
      expect(store.previewError).toBe('');
    });

    it('ignores an invalid payload from a superseded preview', async () => {
      const stale = deferred();
      const english = makeProgram('en');
      get_request.mockReturnValueOnce(stale.promise).mockResolvedValueOnce({ data: english });
      const pending = store.fetchPreview('es');
      await store.fetchPreview('en');

      stale.resolve({ data: { hero: { title: '' } } });
      const staleResult = await pending;

      expect(staleResult).toEqual({ success: false, errors: { detail: 'invalid_program' } });
      expect(store.preview).toEqual(english);
      expect(store.previewError).toBe('');
    });

    it('keeps the newest preview pending after the older request settles', async () => {
      const first = deferred();
      const latest = deferred();
      get_request.mockReturnValueOnce(first.promise).mockReturnValueOnce(latest.promise);
      const firstRequest = store.fetchPreview('es');
      const latestRequest = store.fetchPreview('en');

      first.resolve({ data: makeProgram() });
      await firstRequest;
      expect(store.isLoadingPreview).toBe(true);
      expect(store.preview).toBeNull();
      latest.resolve({ data: makeProgram('en') });
      await latestRequest;

      expect(store.isLoadingPreview).toBe(false);
      expect(store.preview.language).toBe('en');
    });

    it('clears the old-language preview before reporting a connection failure', async () => {
      const pending = deferred();
      get_request.mockResolvedValueOnce({ data: makeProgram() }).mockReturnValueOnce(pending.promise);
      await store.fetchPreview('es');

      const request = store.fetchPreview('en');
      expect({ preview: store.preview, language: store.previewLanguage, pending: store.isLoadingPreview })
        .toEqual({ preview: null, language: 'en', pending: true });
      pending.reject(new Error('Offline'));
      const result = await request;

      expect(result).toEqual({ success: false, errors: { detail: 'request_failed' } });
      expect(store.previewError).toBe('request_failed');
      expect(store.isLoadingPreview).toBe(false);
    });
  });

  describe('history requests', () => {
    it.each(['program', 'contract'])('loads the next %s history page without losing prior revisions', async (kind) => {
      const first = makeVersion();
      const second = makeVersion({ version_id: 20, version: 1 });
      get_request.mockResolvedValueOnce({ data: { versions: [first], total: 2 } })
        .mockResolvedValueOnce({ data: { versions: [second], total: 2 } });
      await store.fetchVersions(kind);
      expect(store.hasMoreVersions(kind)).toBe(true);

      const result = await store.fetchVersions(kind, { append: true });

      expect(get_request).toHaveBeenLastCalledWith(`building-on-demand/admin/${kind}/versions/?limit=20&offset=1`);
      expect(result).toEqual({ success: true, data: { versions: [second], total: 2 } });
      expect(store.history[kind]).toEqual({ versions: [first, second], total: 2, isLoading: false, error: '' });
      expect(store.hasMoreVersions(kind)).toBe(false);
    });

    it('refreshes history from the beginning when append is omitted', async () => {
      const fresh = makeVersion({ version_id: 22, version: 3 });
      get_request.mockResolvedValueOnce({ data: { versions: [makeVersion()], total: 6 } })
        .mockResolvedValueOnce({ data: { versions: [fresh] } });
      await store.fetchVersions('program');

      await store.fetchVersions('program');

      expect(get_request).toHaveBeenLastCalledWith('building-on-demand/admin/program/versions/?limit=20&offset=0');
      expect(store.history.program).toEqual({ versions: [fresh], total: 1, isLoading: false, error: '' });
      expect(store.hasMoreVersions('program')).toBe(false);
    });

    it.each([undefined, { versions: null }, { versions: {} }])
      ('treats malformed history collection %j as empty', async (data) => {
        get_request.mockResolvedValue({ data });

        const result = await store.fetchVersions('contract');

        expect(result).toEqual({ success: true, data });
        expect(store.history.contract).toEqual({ versions: [], total: 0, isLoading: false, error: '' });
        expect(store.hasMoreVersions('contract')).toBe(false);
      });

    it('retries the same history offset after a rejected page', async () => {
      const first = makeVersion();
      const second = makeVersion({ version_id: 20, version: 1 });
      const errors = { message: 'Vuelve a intentar', code: 'REQUEST_FAILED', details: {} };
      get_request.mockResolvedValueOnce({ data: { versions: [first], total: 2 } })
        .mockRejectedValueOnce(httpError(500, errors))
        .mockResolvedValueOnce({ data: { versions: [second], total: 2 } });
      await store.fetchVersions('program');

      const failed = await store.fetchVersions('program', { append: true });
      expect(failed).toEqual({ success: false, errors });
      expect(store.history.program).toEqual({ versions: [first], total: 2, isLoading: false, error: 'Vuelve a intentar' });
      await store.fetchVersions('program', { append: true });

      expect(get_request).toHaveBeenLastCalledWith('building-on-demand/admin/program/versions/?limit=20&offset=1');
      expect(store.history.program).toEqual({ versions: [first, second], total: 2, isLoading: false, error: '' });
    });

    it('keeps contract pagination separate from the program request', async () => {
      const request = deferred();
      get_request.mockReturnValue(request.promise);

      const pending = store.fetchVersions('program');
      expect(store.history.program.isLoading).toBe(true);
      expect(store.history.contract).toEqual({ versions: [], total: 0, isLoading: false, error: '' });
      request.resolve({ data: { versions: [makeVersion()], total: 2 } });
      await pending;

      expect(store.history.program.isLoading).toBe(false);
      expect(store.hasMoreVersions('program')).toBe(true);
      expect(store.hasMoreVersions('contract')).toBe(false);
    });

    it('rejects unsupported history kinds before issuing a request', async () => {
      const result = await store.fetchVersions('economics');

      expect(result).toEqual({ success: false, errors: { detail: 'invalid_history_kind' } });
      expect(get_request).not.toHaveBeenCalled();
      expect(store.hasMoreVersions('economics')).toBe(false);
      expect(store.history).toEqual({
        program: { versions: [], total: 0, isLoading: false, error: '' },
        contract: { versions: [], total: 0, isLoading: false, error: '' },
      });
    });
  });

  describe('contract requests', () => {
    it('prefers the full contract over the overview summary', async () => {
      const summary = makeContract({ version: 1, mirror: { status: 'out_of_sync', document_id: 14 } });
      const contract = makeContract();
      get_request.mockResolvedValueOnce({ data: makeOverview({ contract: summary }) })
        .mockResolvedValueOnce({ data: contract });
      await store.fetchOverview();
      expect(store.contractSummary).toEqual(summary);
      expect(store.mirror).toEqual(summary.mirror);

      const result = await store.fetchContract();

      expect(get_request).toHaveBeenLastCalledWith('building-on-demand/admin/contract/');
      expect(result).toEqual({ success: true, data: contract });
      expect(store.contractSummary).toEqual(contract);
      expect(store.mirror).toEqual(contract.mirror);
      expect(store.contractUnavailable).toBe(false);
    });

    it('keeps the contract loading until the markdown arrives', async () => {
      const request = deferred();
      const contract = makeContract();
      get_request.mockReturnValue(request.promise);

      const pending = store.fetchContract();
      expect(store.isLoadingContract).toBe(true);
      request.resolve({ data: contract });
      await pending;

      expect(store.isLoadingContract).toBe(false);
      expect(store.contract.markdown).toBe('# Célula compartida');
    });

    it('marks an unseeded contract as neutral after a missing endpoint', async () => {
      const errors = { message: 'Contrato no encontrado', code: 'NOT_FOUND', details: {} };
      get_request.mockResolvedValueOnce({ data: makeOverview() }).mockRejectedValueOnce(httpError(404, errors));
      await store.fetchOverview();

      const result = await store.fetchContract();

      expect(result).toEqual({ success: false, errors });
      expect({ unavailable: store.contractUnavailable, error: store.contractError, contract: store.contract })
        .toEqual({ unavailable: true, error: '', contract: null });
      expect(store.isLoadingContract).toBe(false);
    });

    it('recognizes the neutral contract after a delayed overview arrives', async () => {
      const overviewRequest = deferred();
      get_request.mockReturnValueOnce(overviewRequest.promise).mockRejectedValueOnce(httpError(404));
      const pendingOverview = store.fetchOverview();
      await store.fetchContract();
      expect(store.contractUnavailable).toBe(false);
      expect(store.contractError).toBe('Solicitud rechazada');

      overviewRequest.resolve({ data: makeOverview() });
      await pendingOverview;

      expect({ unavailable: store.contractUnavailable, error: store.contractError })
        .toEqual({ unavailable: true, error: '' });
      expect(store.contractSummary).toBeNull();
    });

    it.each([null, {}, makeOverview({ contract: makeContract() })])
      ('reports a missing contract without an explicit unseeded overview %j', async (overview) => {
        get_request.mockResolvedValueOnce({ data: overview }).mockRejectedValueOnce(httpError(404));
        await store.fetchOverview();

        const result = await store.fetchContract();

        expect(result).toEqual({ success: false, errors: httpError(404).response.data });
        expect(store.contractUnavailable).toBe(false);
        expect(store.contractError).toBe('Solicitud rechazada');
        expect(store.isLoadingContract).toBe(false);
      });

    it.each([403, 500])('reports a contract request rejected with status %s', async (status) => {
      get_request.mockResolvedValueOnce({ data: makeOverview() }).mockRejectedValueOnce(httpError(status));
      await store.fetchOverview();

      const result = await store.fetchContract();

      expect(result.success).toBe(false);
      expect({ unavailable: store.contractUnavailable, error: store.contractError })
        .toEqual({ unavailable: false, error: 'Solicitud rechazada' });
      expect(store.isLoadingContract).toBe(false);
    });

    it('clears the unavailable state when the contract becomes available', async () => {
      const contract = makeContract();
      get_request.mockResolvedValueOnce({ data: makeOverview() }).mockRejectedValueOnce(httpError(404))
        .mockResolvedValueOnce({ data: contract });
      await store.fetchOverview();
      await store.fetchContract();
      expect(store.contractUnavailable).toBe(true);

      const result = await store.fetchContract();

      expect(result).toEqual({ success: true, data: contract });
      expect({ unavailable: store.contractUnavailable, error: store.contractError, summary: store.contractSummary })
        .toEqual({ unavailable: false, error: '', summary: contract });
    });

    it('keeps the overview summary when the contract payload is empty', async () => {
      const summary = makeContract();
      get_request.mockResolvedValueOnce({ data: makeOverview({ contract: summary }) }).mockResolvedValueOnce({ data: null });
      await store.fetchOverview();

      const result = await store.fetchContract();

      expect(result).toEqual({ success: true, data: null });
      expect(store.contract).toBeNull();
      expect(store.contractSummary).toEqual(summary);
      expect(store.mirror).toEqual(summary.mirror);
    });
  });

  describe('mirror normalization', () => {
    it.each([
      ['synchronized', 'synchronized'], ['synced', 'synchronized'], ['in_sync', 'synchronized'],
      ['out_of_sync', 'out_of_sync'], ['stale', 'out_of_sync'], ['outdated', 'out_of_sync'],
      [null, 'not_initialized'], [undefined, 'not_initialized'], ['not_initialized', 'not_initialized'],
      ['unexpected', 'unknown'],
    ])('interprets mirror status %s as %s after a contract fetch', async (status, expected) => {
      const contract = makeContract({ mirror: { status, document_id: 15 } });
      get_request.mockResolvedValue({ data: contract });

      await store.fetchContract();

      expect({ document: store.mirror.document_id, status: store.mirrorStatus }).toEqual({ document: 15, status: expected });
      expect(normalizeMirrorStatus(status)).toBe(expected);
    });
  });

  describe('contract transport', () => {
    it('preserves cached markdown after a connection loss', async () => {
      const contract = makeContract();
      const retry = deferred();
      get_request.mockResolvedValueOnce({ data: contract }).mockReturnValueOnce(retry.promise);
      await store.fetchContract();

      const pending = store.fetchContract();
      expect(store.isLoadingContract).toBe(true);
      retry.reject(new Error('Offline'));
      const result = await pending;

      expect(result).toEqual({ success: false, errors: { detail: 'request_failed' } });
      expect(store.contractSummary.markdown).toBe('# Célula compartida');
      expect({ unavailable: store.contractUnavailable, error: store.contractError, pending: store.isLoadingContract })
        .toEqual({ unavailable: false, error: 'request_failed', pending: false });
    });
  });
});
