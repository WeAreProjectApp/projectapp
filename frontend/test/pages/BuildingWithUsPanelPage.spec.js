import { flushPromises, mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { reactive, ref } from 'vue';
import PanelPage from '../../pages/panel/building-with-us/index.vue';
import BasePageShell from '../../components/base/BasePageShell.vue';
import BaseSegmented from '../../components/base/BaseSegmented.vue';
import BaseAlert from '../../components/base/BaseAlert.vue';
import BaseBadge from '../../components/base/BaseBadge.vue';
import { get_request } from '../../stores/services/request_http';

const mockRoute = reactive({ query: {} });
const mockLocale = ref('es-co');
const mockRouter = { replace: jest.fn() };
jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));
jest.mock('#imports', () => ({
  definePageMeta: jest.fn(),
  useRoute: () => mockRoute,
  useRouter: () => mockRouter,
  useLocalePath: () => (path) => `/es-co${path}`,
  useI18n: () => ({
    locale: mockLocale,
    t: (key, params = {}) => {
      const messages = jest.requireActual('../../locales/buildingWithUsAdmin/es').default;
      const message = key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
      return Object.entries(params).reduce((text, [name, value]) => text.replace(`{${name}}`, value), message);
    },
  }),
}));
jest.mock('../../composables/usePanelNotify', () => ({
  usePanelNotify: () => ({ success: jest.fn(), error: jest.fn() }),
}));

const makeVersion = (overrides = {}) => ({
  version: 3, version_id: 23, author: 'Ana', updated_at: '2026-10-09T15:00:00Z',
  change_note: 'Nueva presentación', ...overrides,
});
const makePayloads = () => ({
  'building-with-us/admin/': { program: makeVersion(), contract: null },
  'building-with-us/public/?lang=es': { hero: { title: 'Incubamos productos juntos' } },
  'building-with-us/public/?lang=en': { hero: { title: 'We incubate products together' } },
  'building-with-us/admin/contract/': { ...makeVersion(), markdown: '# Alianza' },
  'building-with-us/admin/program/versions/?limit=20&offset=0': { versions: [makeVersion()], total: 2 },
  'building-with-us/admin/program/versions/?limit=20&offset=1': { versions: [makeVersion({ version_id: 22, version: 2 })], total: 2 },
  'building-with-us/admin/contract/versions/?limit=20&offset=0': { versions: [], total: 0 },
});
const ProgramViewStub = {
  props: ['program', 'language', 'downloadUrl', 'floatingActions'],
  emits: ['change-language'],
  template: `<article data-testid="program-view" :data-floating-actions="String(floatingActions)" :data-language="language">
    <h3>{{ program.hero.title }}</h3>
    <button data-testid="preview-language-en" @click="$emit('change-language', 'en')">English</button>
  </article>`,
};
const mounted = [];
async function mountPage() {
  const wrapper = mount(PanelPage, {
    global: {
      plugins: [createPinia()],
      components: { BasePageShell, BaseSegmented, BaseAlert, BaseBadge },
      stubs: {
        BuildingWithUsProgramView: ProgramViewStub,
        DocumentMarkdownBody: { props: ['markdown'], template: '<article>{{ markdown }}</article>' },
        PanelDownloadLink: { props: ['url', 'label'], template: '<a :href="url">{{ label }}</a>' },
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  });
  mounted.push(wrapper);
  await flushPromises();
  return wrapper;
}
beforeEach(() => {
  jest.clearAllMocks();
  mockRoute.query = {};
  mockLocale.value = 'es-co';
  mockRouter.replace.mockImplementation(({ query }) => { mockRoute.query = query; });
  const payloads = makePayloads();
  get_request.mockReset().mockImplementation(async (path) => ({ data: payloads[path] }));
});
afterEach(() => { mounted.splice(0).forEach((wrapper) => wrapper.unmount()); jest.restoreAllMocks(); });

describe('BuildingWithUsPanelPage', () => {
  it('opens the contract tab from a query link', async () => {
    mockRoute.query = { tab: 'contract' };

    const wrapper = await mountPage();

    expect(wrapper.get('[data-testid="building-with-us-tab-contract"]').attributes('aria-selected')).toBe('true');
    expect(wrapper.get('[data-testid="building-with-us-contract-body"]').text()).toBe('# Alianza');
    expect(get_request).toHaveBeenCalledWith('building-with-us/admin/contract/versions/?limit=20&offset=0');
    expect(wrapper.find('[data-testid="building-with-us-preview"]').exists()).toBe(false);
  });

  it('writes the selected tab to the query', async () => {
    mockRoute.query = { source: 'nav' };
    const wrapper = await mountPage();

    await wrapper.get('[data-testid="building-with-us-tab-contract"]').trigger('click');
    await flushPromises();

    expect(mockRouter.replace).toHaveBeenCalledWith({ query: { source: 'nav', tab: 'contract' } });
    expect(wrapper.get('[data-testid="building-with-us-tab-contract"]').attributes('aria-selected')).toBe('true');
  });

  it('disables floating actions in the live preview', async () => {
    const wrapper = await mountPage();

    expect(wrapper.get('[data-testid="program-view"]').attributes('data-floating-actions')).toBe('false');
    expect(wrapper.get('[data-testid="program-view"]').text()).toContain('Incubamos productos juntos');
  });

  it('retries the overview after a request error', async () => {
    get_request.mockRejectedValueOnce({ response: { data: { detail: 'Unavailable' } } });
    const wrapper = await mountPage();
    expect(wrapper.get('[data-testid="building-with-us-overview-error"]').text()).toContain('No se pudo cargar la información');

    await wrapper.get('[data-testid="building-with-us-overview-retry"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="building-with-us-overview-error"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="building-with-us-program-version"]').text()).toContain('Versión 3');
  });

  it('changes the preview language independently of the panel locale', async () => {
    const wrapper = await mountPage();

    await wrapper.get('[data-testid="preview-language-en"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="program-view"]').text()).toContain('We incubate products together');
    expect(mockLocale.value).toBe('es-co');
    expect(wrapper.get('[data-testid="building-with-us-panel-download-pdf"]').attributes('href')).toBe('/api/building-with-us/public/pdf/?lang=en');
  });

  it('loads the contract only on its first visit', async () => {
    const wrapper = await mountPage();
    expect(get_request).not.toHaveBeenCalledWith('building-with-us/admin/contract/');

    await wrapper.get('[data-testid="building-with-us-tab-contract"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="building-with-us-tab-program"]').trigger('click');
    await wrapper.get('[data-testid="building-with-us-tab-contract"]').trigger('click');
    await flushPromises();

    expect(get_request.mock.calls.filter(([path]) => path === 'building-with-us/admin/contract/')).toHaveLength(1);
    expect(wrapper.get('[data-testid="building-with-us-contract-version"]').text()).toContain('Versión 3');
  });

  it('appends program history from the pagination control', async () => {
    const wrapper = await mountPage();

    await wrapper.get('[data-testid="building-with-us-program-history-more"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-testid="building-with-us-program-version-22"]').text()).toContain('Versión 2');
    expect(wrapper.get('[data-testid="building-with-us-program-version-23"]').text()).toContain('Versión 3');
    expect(wrapper.find('[data-testid="building-with-us-program-history-more"]').exists()).toBe(false);
  });

  it('follows query changes after navigation', async () => {
    const wrapper = await mountPage();

    mockRoute.query = { tab: 'contract' };
    await flushPromises();

    expect(wrapper.get('[data-testid="building-with-us-tab-contract"]').attributes('aria-selected')).toBe('true');
    expect(wrapper.get('[data-testid="building-with-us-contract-body"]').text()).toBe('# Alianza');
    expect(mockRouter.replace).not.toHaveBeenCalled();
  });
});
