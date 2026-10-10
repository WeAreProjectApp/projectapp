import { flushPromises, mount } from '@vue/test-utils';
import DistributionCard from '../../components/BuildingWithUs/admin/DistributionCard.vue';
import BaseBadge from '../../components/base/BaseBadge.vue';

const mockNotify = { success: jest.fn(), error: jest.fn() };
jest.mock('../../composables/usePanelNotify', () => ({ usePanelNotify: () => mockNotify }));
jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));
jest.mock('#imports', () => ({
  useI18n: () => ({
    t: (key) => {
      const messages = jest.requireActual('../../locales/buildingWithUsAdmin/es').default;
      return key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
    },
  }),
}));

const mounted = [];
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
function mountCard(overrides = {}) {
  const wrapper = mount(DistributionCard, {
    props: overrides,
    global: {
      components: { BaseBadge },
      stubs: {
        NuxtLink: true,
        PanelDownloadLink: { props: ['url', 'label'], template: '<a :href="url">{{ label }}</a>' },
      },
    },
  });
  mounted.push(wrapper);
  return wrapper;
}
beforeEach(() => {
  jest.clearAllMocks();
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: jest.fn().mockResolvedValue() } });
});
afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount());
  if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard);
  else delete navigator.clipboard;
  jest.restoreAllMocks();
});

describe('BuildingWithUsAdminDistributionCard', () => {
  it('copies the English public URL', async () => {
    const wrapper = mountCard();

    await wrapper.get('[data-testid="building-with-us-copy-public-url-en"]').trigger('click');
    await flushPromises();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://projectapp.co/en-us/building-with-us');
    expect(mockNotify.success).toHaveBeenCalledWith({ title: 'URL pública copiada' });
  });

  it('reports a failed clipboard operation', async () => {
    navigator.clipboard.writeText.mockRejectedValue(new Error('Clipboard unavailable'));
    const wrapper = mountCard();

    await wrapper.get('[data-testid="building-with-us-copy-public-url-es"]').trigger('click');
    await flushPromises();

    expect(mockNotify.error).toHaveBeenCalledWith({ title: 'No se pudo copiar la URL pública.' });
  });

  it('shows the public distribution badges', () => {
    const wrapper = mountCard();

    expect(wrapper.findAllComponents(BaseBadge).map((badge) => badge.text())).toEqual(['Público', 'Indexable']);
  });

  it('opens the Spanish presentation in a separate tab', () => {
    const wrapper = mountCard();

    const link = wrapper.get('[data-testid="building-with-us-open-public"]');

    expect(link.attributes('href')).toBe('https://projectapp.co/es-co/building-with-us');
    expect(link.attributes('target')).toBe('_blank');
    expect(link.attributes('rel')).toBe('noopener noreferrer');
  });

  it('offers the program PDF in the selected preview language', () => {
    const wrapper = mountCard({ language: 'en' });

    expect(wrapper.get('[data-testid="building-with-us-panel-download-pdf"]').attributes('href')).toBe('/api/building-with-us/public/pdf/?lang=en');
  });
});
