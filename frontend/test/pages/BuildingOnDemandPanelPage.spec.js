import { flushPromises, mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { reactive, ref } from 'vue';
import PanelPage from '../../pages/panel/cells/index.vue';
import BasePageShell from '../../components/base/BasePageShell.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import BaseAlert from '../../components/base/BaseAlert.vue';
import BaseBadge from '../../components/base/BaseBadge.vue';
import BaseExploratoryList from '../../components/base/BaseExploratoryList.vue';
import { get_request } from '../../stores/services/request_http';

const mockRoute = reactive({ query: {} });
const mockLocale = ref('es-co');
const mockRouter = { replace: jest.fn() };
const mockMessages = jest.requireActual('../../locales/buildingOnDemandAdmin/es').default;
jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));
jest.mock('#imports', () => ({
  definePageMeta: jest.fn(),
  useRoute: () => mockRoute,
  useRouter: () => mockRouter,
  useLocalePath: () => (path) => `/es-co${path}`,
  useI18n: () => ({
    locale: mockLocale,
    t: (key, params = {}) => {
      const message = key.split('.').slice(1).reduce((value, part) => value?.[part], mockMessages) || key;
      return Object.entries(params).reduce((text, [name, value]) => text.replace(`{${name}}`, value), message);
    },
  }),
}));
jest.mock('../../composables/usePanelNotify', () => ({
  usePanelNotify: () => ({ success: jest.fn(), error: jest.fn() }),
}));

const makeVersion = (overrides = {}) => ({
  version: 3, version_id: 23, author: 'Ana', updated_at: '2026-10-10T15:00:00Z',
  change_note: 'Nueva presentación de la célula', ...overrides,
});
const makeEconomics = () => ({
  currency: 'COP', hour_cost: 55000, vat_percent: 19, provider: 'Hostinger',
  reference_url: 'https://www.hostinger.com/co/vps-servidor-web', consulted_on: '2026-10-10',
  tiers: [{ id: 'business', name: 'Business', bag_hours: 192, plan: 'KVM 4', promo_monthly: 38900, renewal_monthly: 97900, hosting_cost_monthly: 116501 }],
  rows: [{ tier: 'business', term: 'monthly', months: 1, monthly_price: 4200000, hosting_cost_monthly: 116501, net_monthly: 4083499, breakeven_hours: 74.2, breakeven_hours_rounded: 74, bag_hours: 192, bag_share_percent: 39, breakeven_hours_without_hosting: 76.4 }],
});
const makeContract = () => ({
  ...makeVersion(), markdown: '# Contrato de la célula',
  mirror: { status: 'synchronized', document_id: 81, folder_path: 'ProjectApp › Contratos', version: 3 },
});
const makePayloads = () => ({
  'building-on-demand/admin/': {
    program: makeVersion(), contract: null, connector: { slug: 'building-on-demand', is_active: false },
    public_paths: { es: '/es-co/building-on-demand', en: '/en-us/building-on-demand' },
    pdf_paths: { es: '/api/building-on-demand/public/pdf/?lang=es', en: '/api/building-on-demand/public/pdf/?lang=en' },
  },
  'building-on-demand/public/?lang=es': { language: 'es', hero: { title: 'Una célula para hacer evolucionar tu producto' } },
  'building-on-demand/public/?lang=en': { language: 'en', hero: { title: 'A cell to evolve your product' } },
  'building-on-demand/admin/economics/': makeEconomics(),
  'building-on-demand/admin/contract/': makeContract(),
  'building-on-demand/admin/program/versions/?limit=20&offset=0': { versions: [makeVersion()], total: 2 },
  'building-on-demand/admin/program/versions/?limit=20&offset=1': { versions: [makeVersion({ version_id: 22, version: 2 })], total: 2 },
  'building-on-demand/admin/contract/versions/?limit=20&offset=0': { versions: [], total: 0 },
});
const requestError = (status = 503) => ({ response: { status, data: { message: 'No disponible', code: 'NOT_FOUND', details: {} } } });
const ProgramViewStub = {
  props: ['program', 'language', 'floatingActions'],
  template: '<article data-testid="program-view" :data-floating-actions="String(floatingActions)" :data-language="language"><h3>{{ program.hero.title }}</h3></article>',
};
const mounted = [];
async function mountPage({ settle = true } = {}) {
  const wrapper = mount(PanelPage, {
    global: {
      plugins: [createPinia()],
      components: { BasePageShell, BaseSegmented, BaseAlert, BaseBadge, BaseExploratoryList },
      stubs: {
        BuildingOnDemandProgramView: ProgramViewStub,
        DocumentMarkdownBody: { props: ['markdown'], template: '<article>{{ markdown }}</article>' },
        PanelDownloadLink: { props: ['url', 'label'], template: '<a :href="url">{{ label }}</a>' },
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  });
  mounted.push(wrapper);
  if (settle) await flushPromises();
  return wrapper;
}
let payloads;
beforeEach(() => {
  jest.clearAllMocks();
  mockRoute.query = {};
  mockLocale.value = 'es-co';
  mockRouter.replace.mockImplementation(({ query }) => { mockRoute.query = query; });
  payloads = makePayloads();
  get_request.mockReset().mockImplementation(async (path) => ({ data: payloads[path] }));
});
afterEach(() => { mounted.splice(0).forEach((wrapper) => wrapper.unmount()); jest.restoreAllMocks(); });

describe('BuildingOnDemandPanelPage', () => {
  it('opens internal economics from a query link', async () => {
    mockRoute.query = { tab: 'economics' };

    const wrapper = await mountPage();

    expect(wrapper.get('[data-testid="building-on-demand-panel-tab-economics"]').attributes('aria-selected')).toBe('true');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-row-business-monthly"]').text()).toContain('74,2');
    expect(wrapper.find('[data-testid="building-on-demand-panel-preview"]').exists()).toBe(false);
    expect(get_request).not.toHaveBeenCalledWith('building-on-demand/admin/program/versions/?limit=20&offset=0');
    expect(wrapper.get('[data-testid="building-on-demand-admin-mcp-hint"]').text()).toContain('Conector inactivo');
  });

  it('opens the published contract from a query link', async () => {
    mockRoute.query = { tab: 'contract' };

    const wrapper = await mountPage();

    expect(wrapper.get('[data-testid="building-on-demand-panel-tab-contract"]').attributes('aria-selected')).toBe('true');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-body"]').text()).toBe('# Contrato de la célula');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-status"]').text()).toBe('Sincronizado');
    expect(get_request).toHaveBeenCalledWith('building-on-demand/admin/contract/versions/?limit=20&offset=0');
    expect(wrapper.find('[data-testid="building-on-demand-panel-preview"]').exists()).toBe(false);
  });

  it('falls back to the program for an unsupported tab', async () => {
    mockRoute.query = { tab: 'edit' };

    const wrapper = await mountPage();

    expect(wrapper.get('[data-testid="building-on-demand-panel-tab-program"]').attributes('aria-selected')).toBe('true');
    expect(wrapper.get('[data-testid="program-view"]').text()).toContain('Una célula para hacer evolucionar tu producto');
  });

  it('preserves unrelated query parameters while selecting tabs', async () => {
    mockRoute.query = { source: 'nav' };
    const wrapper = await mountPage();

    await wrapper.get('[data-testid="building-on-demand-panel-tab-economics"]').trigger('click');
    await flushPromises();
    expect(mockRouter.replace).toHaveBeenLastCalledWith({ query: { source: 'nav', tab: 'economics' } });
    expect(wrapper.get('[data-testid="building-on-demand-panel-tab-economics"]').attributes('aria-selected')).toBe('true');

    await wrapper.get('[data-testid="building-on-demand-panel-tab-program"]').trigger('click');
    await flushPromises();
    expect(mockRouter.replace).toHaveBeenLastCalledWith({ query: { source: 'nav', tab: undefined } });
    expect(wrapper.get('[data-testid="program-view"]').text()).toContain('Una célula');
  });

  it('renders an embedded program preview without floating actions', async () => {
    const wrapper = await mountPage();

    expect(wrapper.get('[data-testid="program-view"]').attributes('data-floating-actions')).toBe('false');
    expect(wrapper.get('[data-testid="program-view"]').attributes('data-language')).toBe('es');
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-version"]').text()).toContain('Versión 3');
  });

  it('switches preview language independently of the panel locale', async () => {
    const wrapper = await mountPage();

    await wrapper.get('[data-testid="building-on-demand-panel-preview-language-en"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="program-view"]').text()).toContain('A cell to evolve your product');
    expect(wrapper.get('[data-testid="program-view"]').attributes('data-language')).toBe('en');
    expect(mockLocale.value).toBe('es-co');
    expect(wrapper.get('[data-testid="building-on-demand-panel-preview-language-en"]').attributes('aria-selected')).toBe('true');
  });

  it('follows external query navigation to the economics tab', async () => {
    const wrapper = await mountPage();

    mockRoute.query = { tab: 'economics' };
    await flushPromises();

    expect(wrapper.get('[data-testid="building-on-demand-panel-tab-economics"]').attributes('aria-selected')).toBe('true');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-row-business-monthly"]').text()).toContain('74,2');
    expect(mockRouter.replace).not.toHaveBeenCalled();
  });

  it.each([
    ['economics', 'building-on-demand-admin-economics-row-business-monthly', '74,2'],
    ['contract', 'building-on-demand-admin-contract-body', '# Contrato de la célula'],
  ])('loads %s only on its first visit', async (kind, resultId, text) => {
    const wrapper = await mountPage();
    expect(get_request).not.toHaveBeenCalledWith(`building-on-demand/admin/${kind}/`);

    await wrapper.get(`[data-testid="building-on-demand-panel-tab-${kind}"]`).trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="building-on-demand-panel-tab-program"]').trigger('click');
    await wrapper.get(`[data-testid="building-on-demand-panel-tab-${kind}"]`).trigger('click');
    await flushPromises();

    expect(get_request.mock.calls.filter(([path]) => path === `building-on-demand/admin/${kind}/`)).toHaveLength(1);
    expect(wrapper.get(`[data-testid="${resultId}"]`).text()).toContain(text);
  });

  it('shows a neutral state for the contract planned for a later wave', async () => {
    mockRoute.query = { tab: 'contract' };
    get_request.mockResolvedValueOnce({ data: payloads['building-on-demand/admin/'] }).mockRejectedValueOnce(requestError(404));

    const wrapper = await mountPage();

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-unavailable"]').text()).toContain('El contrato todavía no está disponible');
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-error"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-history"]').exists()).toBe(false);
    expect(get_request).not.toHaveBeenCalledWith('building-on-demand/admin/contract/versions/?limit=20&offset=0');
  });

  it('retries a missing contract when a published version is expected', async () => {
    mockRoute.query = { tab: 'contract' };
    payloads['building-on-demand/admin/'].contract = makeVersion();
    get_request.mockResolvedValueOnce({ data: payloads['building-on-demand/admin/'] }).mockRejectedValueOnce(requestError(404));
    const wrapper = await mountPage();
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-error"]').text()).toContain('No se pudo cargar el contrato');

    await wrapper.get('[data-testid="building-on-demand-admin-contract-retry"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-body"]').text()).toBe('# Contrato de la célula');
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-error"]').exists()).toBe(false);
  });

  it('retries the overview after its endpoint fails', async () => {
    get_request.mockRejectedValueOnce(requestError());
    const wrapper = await mountPage();
    expect(wrapper.get('[data-testid="building-on-demand-panel-overview-error"]').text()).toContain('No se pudo cargar la información');

    await wrapper.get('[data-testid="building-on-demand-panel-overview-retry"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="building-on-demand-panel-overview-error"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-version"]').text()).toContain('Versión 3');
    expect(wrapper.get('[data-testid="building-on-demand-admin-mcp-hint"]').text()).toContain('Conector inactivo');
  });

  it('retries a failed English preview using the selected language', async () => {
    const wrapper = await mountPage();
    get_request.mockRejectedValueOnce(requestError());
    await wrapper.get('[data-testid="building-on-demand-panel-preview-language-en"]').trigger('click');
    await flushPromises();
    expect(wrapper.get('[data-testid="building-on-demand-panel-preview-error"]').text()).toContain('No se pudo cargar la vista previa');

    await wrapper.get('[data-testid="building-on-demand-panel-preview-retry"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="program-view"]').text()).toContain('A cell to evolve your product');
    expect(wrapper.get('[data-testid="program-view"]').attributes('data-language')).toBe('en');
    expect(wrapper.find('[data-testid="building-on-demand-panel-preview-error"]').exists()).toBe(false);
  });

  it('appends older program versions from the pagination control', async () => {
    const wrapper = await mountPage();

    await wrapper.get('[data-testid="building-on-demand-admin-program-history-more"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="building-on-demand-admin-program-version-22"]').text()).toContain('Versión 2');
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-version-23"]').text()).toContain('Versión 3');
    expect(wrapper.find('[data-testid="building-on-demand-admin-program-history-more"]').exists()).toBe(false);
  });

  it('retries history when its initial page fails', async () => {
    get_request.mockResolvedValueOnce({ data: payloads['building-on-demand/admin/'] })
      .mockResolvedValueOnce({ data: payloads['building-on-demand/public/?lang=es'] }).mockRejectedValueOnce(requestError());
    const wrapper = await mountPage();
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-history-error"]').text()).toContain('No se pudo cargar el historial');

    await wrapper.get('[data-testid="building-on-demand-admin-program-history-retry"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="building-on-demand-admin-program-version-23"]').text()).toContain('Versión 3');
    expect(wrapper.find('[data-testid="building-on-demand-admin-program-history-error"]').exists()).toBe(false);
  });

  it('retries failed pagination from the existing history offset', async () => {
    const wrapper = await mountPage();
    get_request.mockRejectedValueOnce(requestError());
    await wrapper.get('[data-testid="building-on-demand-admin-program-history-more"]').trigger('click');
    await flushPromises();

    await wrapper.get('[data-testid="building-on-demand-admin-program-history-retry"]').trigger('click');
    await flushPromises();

    expect(get_request).toHaveBeenLastCalledWith('building-on-demand/admin/program/versions/?limit=20&offset=1');
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-version-23"]').text()).toContain('Versión 3');
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-version-22"]').text()).toContain('Versión 2');
  });

  it('retries the economics endpoint from its visible error', async () => {
    mockRoute.query = { tab: 'economics' };
    get_request.mockResolvedValueOnce({ data: payloads['building-on-demand/admin/'] }).mockRejectedValueOnce(requestError());
    const wrapper = await mountPage();
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-error"]').text()).toContain('No se pudo cargar la economía');

    await wrapper.get('[data-testid="building-on-demand-admin-economics-retry"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-row-business-monthly"]').text()).toContain('74,2');
    expect(wrapper.find('[data-testid="building-on-demand-admin-economics-error"]').exists()).toBe(false);
  });

  it('waits for the overview before deciding that the contract is unavailable', async () => {
    mockRoute.query = { tab: 'contract' };
    let resolveOverview;
    const overviewRequest = new Promise((resolve) => { resolveOverview = resolve; });
    get_request.mockImplementationOnce(() => overviewRequest).mockRejectedValueOnce(requestError(404));
    const wrapper = await mountPage({ settle: false });
    expect(get_request).not.toHaveBeenCalledWith('building-on-demand/admin/contract/');

    resolveOverview({ data: payloads['building-on-demand/admin/'] });
    await flushPromises();

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-unavailable"]').text()).toContain('El contrato todavía no está disponible');
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-error"]').exists()).toBe(false);
  });

  it('preserves the preview language when revisiting the program', async () => {
    const wrapper = await mountPage();
    await wrapper.get('[data-testid="building-on-demand-panel-preview-language-en"]').trigger('click');
    await flushPromises();

    await wrapper.get('[data-testid="building-on-demand-panel-tab-economics"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="building-on-demand-panel-tab-program"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="program-view"]').attributes('data-language')).toBe('en');
    expect(get_request.mock.calls.filter(([path]) => path === 'building-on-demand/public/?lang=en')).toHaveLength(1);
    expect(wrapper.get('[data-testid="program-view"]').text()).toContain('A cell to evolve your product');
  });

  it('keeps the current preview when its language is selected again', async () => {
    const wrapper = await mountPage();

    await wrapper.get('[data-testid="building-on-demand-panel-preview-language-es"]').trigger('click');
    await flushPromises();

    expect(get_request.mock.calls.filter(([path]) => path === 'building-on-demand/public/?lang=es')).toHaveLength(1);
    expect(wrapper.get('[data-testid="program-view"]').text()).toContain('Una célula para hacer evolucionar tu producto');
  });
});
