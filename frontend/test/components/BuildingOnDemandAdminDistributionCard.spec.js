import { flushPromises, mount } from '@vue/test-utils';
import DistributionCard from '../../components/BuildingOnDemand/admin/DistributionCard.vue';

const mockMessages = jest.requireActual('../../locales/buildingOnDemandAdmin/es').default;
const mockNotify = { success: jest.fn(), error: jest.fn() };
jest.mock('../../composables/usePanelNotify', () => ({ usePanelNotify: () => mockNotify }));
jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));
jest.mock('#imports', () => ({
  useI18n: () => ({
    t: (key) => {
      return key.split('.').slice(1).reduce((value, part) => value?.[part], mockMessages) || key;
    },
  }),
}));

const mounted = [];
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
function mountCard(overrides = {}) {
  const wrapper = mount(DistributionCard, {
    props: overrides,
    global: {
      stubs: {
        NuxtLink: true,
        PanelDownloadLink: {
          props: ['url', 'label', 'filename'],
          template: '<a :href="url" :download="filename">{{ label }}</a>',
        },
      },
    },
  });
  mounted.push(wrapper);
  return wrapper;
}
beforeEach(() => {
  jest.clearAllMocks();
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: jest.fn().mockResolvedValue() },
  });
});
afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount());
  if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard);
  else delete navigator.clipboard;
  jest.useRealTimers();
  jest.restoreAllMocks();
});

describe('BuildingOnDemandAdminDistributionCard', () => {
  it.each([
    ['es', 'https://projectapp.co/es-co/building-on-demand'],
    ['en', 'https://projectapp.co/en-us/building-on-demand'],
  ])('confirms copying the %s public link', async (language, url) => {
    const wrapper = mountCard();
    const button = wrapper.get(`[data-testid="building-on-demand-admin-copy-public-url-${language}"]`);

    await button.trigger('click');
    await flushPromises();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(url);
    expect(button.attributes('data-action-status')).toBe('success');
    expect(button.attributes('aria-label')).toBe('URL pública copiada');
  });

  it('waits for the clipboard before confirming the copy', async () => {
    let resolveClipboard;
    navigator.clipboard.writeText.mockImplementation(() => new Promise((resolve) => { resolveClipboard = resolve; }));
    const wrapper = mountCard();
    const button = wrapper.get('[data-testid="building-on-demand-admin-copy-public-url-es"]');

    await button.trigger('click');
    expect(button.attributes('data-action-status')).toBeUndefined();
    resolveClipboard();
    await flushPromises();

    expect(button.attributes('data-action-status')).toBe('success');
    expect(mockNotify.success).toHaveBeenCalledWith({ title: 'URL pública copiada' });
  });

  it('keeps the failed copy control available for retry', async () => {
    navigator.clipboard.writeText.mockRejectedValue(new Error('Clipboard denied'));
    const wrapper = mountCard();
    const button = wrapper.get('[data-testid="building-on-demand-admin-copy-public-url-en"]');

    await button.trigger('click');
    await flushPromises();

    expect(button.attributes('data-action-status')).toBe('danger');
    expect(button.attributes('disabled')).toBeUndefined();
    expect(mockNotify.error).toHaveBeenCalledWith({ title: 'No se pudo copiar la URL pública.' });
  });

  it('explains copying when the browser has no clipboard', async () => {
    delete navigator.clipboard;
    const wrapper = mountCard();

    await wrapper.get('[data-testid="building-on-demand-admin-copy-public-url-es"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[role="status"]').text()).toBe('No se pudo copiar la URL pública.');
    expect(mockNotify.error).toHaveBeenCalledTimes(1);
    expect(mockNotify.success).not.toHaveBeenCalled();
  });

  it.each([
    ['es', 'https://projectapp.co/es-co/building-on-demand', 'ES'],
    ['en', 'https://projectapp.co/en-us/building-on-demand', 'EN'],
  ])('opens the %s client presentation safely', (language, url, label) => {
    const wrapper = mountCard();

    const link = wrapper.get(`[data-testid="building-on-demand-admin-open-public-${language}"]`);

    expect(link.attributes()).toMatchObject({ href: url, target: '_blank', rel: 'noopener noreferrer' });
    expect(link.text()).toBe(`Ver como cliente · ${label}`);
  });

  it.each(['es', 'en'])('offers a language-specific %s PDF file', (language) => {
    const wrapper = mountCard();

    const download = wrapper.get(`[data-testid="building-on-demand-admin-download-pdf-${language}"]`);

    expect(download.attributes('href')).toBe(`/api/building-on-demand/public/pdf/?lang=${language}`);
    expect(download.attributes('download')).toBe(`building-on-demand-${language}.pdf`);
    expect(download.text()).toContain(language.toUpperCase());
  });

  it('uses distribution paths supplied by the overview', async () => {
    const wrapper = mountCard({
      publicPaths: { en: 'https://staging.projectapp.co/en-us/building-on-demand' },
      pdfPaths: { en: '/api/building-on-demand/public/pdf/?lang=en&version=4' },
    });

    await wrapper.get('[data-testid="building-on-demand-admin-copy-public-url-en"]').trigger('click');
    await flushPromises();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://staging.projectapp.co/en-us/building-on-demand');
    expect(wrapper.get('[data-testid="building-on-demand-admin-open-public-en"]').attributes('href')).toBe('https://staging.projectapp.co/en-us/building-on-demand');
    expect(wrapper.get('[data-testid="building-on-demand-admin-download-pdf-en"]').attributes('href')).toBe('/api/building-on-demand/public/pdf/?lang=en&version=4');
  });

  it('returns to the copy action after confirmation expires', async () => {
    jest.useFakeTimers();
    const wrapper = mountCard();
    const button = wrapper.get('[data-testid="building-on-demand-admin-copy-public-url-es"]');
    await button.trigger('click');
    await flushPromises();

    jest.advanceTimersByTime(2_000);
    await flushPromises();

    expect(button.attributes('data-action-status')).toBeUndefined();
    expect(button.attributes('aria-label')).toBe('Copiar URL: URL pública en español');
    expect(wrapper.find('[role="status"]').exists()).toBe(false);
  });
});
