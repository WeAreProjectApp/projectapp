import { mount, flushPromises } from '@vue/test-utils';
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
import { get_request } from '~/stores/services/request_http';

jest.mock('~/stores/services/request_http', () => ({ get_request: jest.fn() }));
const mockNotify = { error: jest.fn() };
jest.mock('~/composables/usePanelNotify', () => ({ usePanelNotify: () => mockNotify }));
jest.mock('#imports', () => ({
  useI18n: () => ({ t: (key) => {
    const messages = jest.requireActual('../../locales/pwa/es').default;
    return key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
  } }),
}));

const pdfResponse = (headers = {}) => ({
  status: 200,
  data: new Blob(['%PDF-1.4 test'], { type: 'application/pdf' }),
  headers: { 'content-type': 'application/pdf', ...headers },
});
const mountLink = (props = {}) => mount(PanelDownloadLink, {
  props: { url: '/api/proposals/7/contract/pdf/', filename: 'contrato.pdf', ...props },
  global: { stubs: { NuxtLink: true } },
});

describe('PanelDownloadLink', () => {
  let saved;
  let click;
  beforeEach(() => {
    jest.useFakeTimers();
    get_request.mockReset().mockResolvedValue(pdfResponse());
    mockNotify.error.mockReset();
    URL.createObjectURL = jest.fn().mockReturnValue('blob:download');
    URL.revokeObjectURL = jest.fn();
    saved = [];
    click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      saved.push({ name: this.download, target: this.target });
    });
  });
  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it('downloads the returned PDF using the UTF-8 server filename', async () => {
    const response = pdfResponse({ 'content-disposition': "attachment; filename*=UTF-8''contrato%20espa%C3%B1ol.pdf" });
    get_request.mockResolvedValue(response);
    const wrapper = mountLink();

    await wrapper.get('a').trigger('click');
    await flushPromises();

    expect(URL.createObjectURL).toHaveBeenCalledWith(response.data);
    expect(saved).toEqual([{ name: 'contrato español.pdf', target: '' }]);
  });

  it('uses the explicit fallback filename when the server omits one', async () => {
    const wrapper = mountLink();
    await wrapper.get('a').trigger('click');
    await flushPromises();
    expect(saved[0].name).toBe('contrato.pdf');
  });

  it('keeps the selected contract variant in the download request', async () => {
    const wrapper = mountLink({ url: '/api/proposals/7/contract/pdf/?variant=service' });
    await wrapper.get('a').trigger('click');
    await flushPromises();
    expect(get_request).toHaveBeenCalledWith('proposals/7/contract/pdf/?variant=service', expect.objectContaining({ responseType: 'blob' }));
  });

  it('blocks repeated activation while the file is loading', async () => {
    let finish;
    get_request.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const wrapper = mountLink();
    await wrapper.get('a').trigger('click');
    await wrapper.get('a').trigger('click');
    expect(wrapper.text()).toBe('Descargando…');
    expect(get_request).toHaveBeenCalledTimes(1);
    finish(pdfResponse());
    await flushPromises();
    expect(wrapper.text()).toBe('Descargar PDF');
  });

  it.each([
    [401, 'Tu sesión venció. Inicia sesión de nuevo para descargar el archivo.'],
    [403, 'No tienes permiso para descargar este archivo.'],
  ])('reports HTTP %s without saving an error as a file', async (status, message) => {
    get_request.mockRejectedValue({ response: { status } });
    const wrapper = mountLink();
    await wrapper.get('a').trigger('click');
    await flushPromises();
    expect(mockNotify.error).toHaveBeenCalledWith(message);
    expect(click).not.toHaveBeenCalled();
  });

  it('renders the explanation from a JSON error blob', async () => {
    get_request.mockRejectedValue({ response: {
      status: 422, data: new Blob(['{"detail":"Primero genera el contrato."}'], { type: 'application/json' }),
    } });
    const wrapper = mountLink();
    await wrapper.get('a').trigger('click');
    // FileReader is the browser boundary used by normalizeBlobApiError in jsdom.
    await jest.runAllTimersAsync();
    await flushPromises();
    expect(mockNotify.error).toHaveBeenCalledWith('Primero genera el contrato.');
    expect(click).not.toHaveBeenCalled();
  });

  it.each([
    ['text/html', '<html>Login</html>'],
    ['application/json', '{"detail":"Archivo no disponible"}'],
    ['application/pdf', ''],
    ['text/plain', 'not a PDF'],
  ])('rejects an invalid successful response (%s)', async (type, body) => {
    get_request.mockResolvedValue({ status: 200, data: new Blob([body], { type }), headers: { 'content-type': type } });
    const wrapper = mountLink();
    await wrapper.get('a').trigger('click');
    await jest.runAllTimersAsync();
    await flushPromises();
    expect(click).not.toHaveBeenCalled();
    expect(mockNotify.error).toHaveBeenCalledTimes(1);
  });

  it('allows retry after a network failure', async () => {
    get_request.mockRejectedValueOnce(new Error('Network Error'));
    const wrapper = mountLink();
    await wrapper.get('a').trigger('click');
    await flushPromises();
    expect(mockNotify.error).toHaveBeenCalledWith(expect.stringContaining('conexión'));
    await wrapper.get('a').trigger('click');
    await flushPromises();
    expect(saved).toEqual([{ name: 'contrato.pdf', target: '' }]);
  });

  it('cancels an unfinished download when its control unmounts', async () => {
    let finish;
    get_request.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const wrapper = mountLink();
    await wrapper.get('a').trigger('click');
    const signal = get_request.mock.calls[0][1].signal;
    wrapper.unmount();
    finish(pdfResponse());
    await flushPromises();
    expect(signal.aborted).toBe(true);
    expect(click).not.toHaveBeenCalled();
  });

  it('rejects foreign URLs before making an authenticated request', async () => {
    const wrapper = mountLink({ url: 'https://other.example/api/file.pdf' });
    await wrapper.get('a').trigger('click');
    await flushPromises();
    expect(get_request).not.toHaveBeenCalled();
    expect(click).not.toHaveBeenCalled();
    expect(mockNotify.error).toHaveBeenCalledTimes(1);
  });

  it('downloads an original same-origin attachment without API rewriting', async () => {
    const response = pdfResponse();
    const originalFetch = global.fetch;
    global.fetch = jest.fn().mockResolvedValue({
      ok: true, status: 200, headers: new Map(Object.entries(response.headers)), blob: async () => response.data,
    });
    const wrapper = mountLink({ url: '/media/adjunto.pdf' });
    try {
      await wrapper.get('a').trigger('click');
      await flushPromises();
      expect(global.fetch).toHaveBeenCalledWith(`${window.location.origin}/media/adjunto.pdf`, expect.objectContaining({ credentials: 'same-origin' }));
      expect(saved).toHaveLength(1);
    } finally {
      global.fetch = originalFetch;
    }
  });
});
