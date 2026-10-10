import { mount } from '@vue/test-utils';
import ContractPanel from '../../components/BuildingWithUs/admin/ContractPanel.vue';
import BaseAlert from '../../components/base/BaseAlert.vue';
import BaseBadge from '../../components/base/BaseBadge.vue';

jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));
jest.mock('#imports', () => ({
  useLocalePath: () => (path) => `/es-co${path}`,
  useI18n: () => ({
    locale: { value: 'es-co' },
    t: (key, params = {}) => {
      const messages = jest.requireActual('../../locales/buildingWithUsAdmin/es').default;
      const message = key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
      return Object.entries(params).reduce((text, [name, value]) => text.replace(`{${name}}`, value), message);
    },
  }),
}));

const makeContract = (overrides = {}) => ({
  version: 4, version_id: 24, author: 'Ana', updated_at: '2026-10-09T15:00:00Z',
  change_note: 'Participación acordada', markdown: '# Contrato de alianza',
  mirror: { status: 'synchronized', document_id: 15, folder_path: 'ProjectApp › Contratos' },
  ...overrides,
});
const DownloadStub = { props: ['url', 'label'], template: '<a :href="url">{{ label }}</a>' };
const mounted = [];
function mountContract(overrides = {}) {
  const wrapper = mount(ContractPanel, {
    props: { contract: makeContract(), ...overrides },
    global: {
      components: { BaseAlert, BaseBadge },
      stubs: {
        DocumentMarkdownBody: { props: ['markdown'], template: '<article>{{ markdown }}</article>' },
        PanelDownloadLink: DownloadStub,
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  });
  mounted.push(wrapper);
  return wrapper;
}
afterEach(() => { mounted.splice(0).forEach((wrapper) => wrapper.unmount()); jest.restoreAllMocks(); });

describe('BuildingWithUsAdminContractPanel', () => {
  it('links to the mirrored document through the panel locale', () => {
    const wrapper = mountContract();

    expect(wrapper.get('[data-testid="building-with-us-mirror-link"]').attributes('href')).toBe('/es-co/panel/documents/15/edit');
  });

  it('omits the mirror link when the document id is missing', () => {
    const wrapper = mountContract({ contract: makeContract({ mirror: { status: 'synchronized' } }) });

    expect(wrapper.find('[data-testid="building-with-us-mirror-link"]').exists()).toBe(false);
  });

  it.each([
    ['out_of_sync', 'La copia del Gestor Documental está desactualizada.'],
    ['not_initialized', 'La copia del Gestor Documental se inicializa'],
  ])('explains MCP synchronization for %s', (status, message) => {
    const wrapper = mountContract({ mirror: { status } });

    const alert = wrapper.get('[data-testid="building-with-us-mirror-alert"]');

    expect(alert.text()).toContain(message);
    expect(alert.text()).toContain('MCP «Building with Us»');
  });

  it.each([
    ['synchronized', 'Sincronizado', 'success'],
    ['out_of_sync', 'Desactualizado', 'warning'],
    ['not_initialized', 'Sin inicializar', 'neutral'],
    ['unexpected', 'Desconocido', 'neutral'],
  ])('labels the mirror status %s', (status, label, variant) => {
    const wrapper = mountContract({ mirror: { status } });

    expect(wrapper.get('[data-testid="building-with-us-mirror-status"]').text()).toBe(label);
    expect(wrapper.findComponent(BaseBadge).props('variant')).toBe(variant);
  });

  it('shows the current contract version', () => {
    const wrapper = mountContract();

    expect(wrapper.get('[data-testid="building-with-us-contract-version"]').text()).toContain('Versión 4');
  });

  it('provides the contract PDF download', () => {
    const wrapper = mountContract();

    expect(wrapper.get('[data-testid="building-with-us-contract-download-pdf"]').attributes('href')).toBe('/api/building-with-us/admin/contract/pdf/');
  });

  it('passes the read-only contract to the markdown renderer', () => {
    const wrapper = mountContract();

    expect(wrapper.get('[data-testid="building-with-us-contract-body"]').text()).toBe('# Contrato de alianza');
  });

  it('retries a failed contract request', async () => {
    const wrapper = mountContract({ error: 'request_failed' });

    await wrapper.get('[data-testid="building-with-us-contract-retry"]').trigger('click');

    expect(wrapper.emitted('retry')).toEqual([[]]);
    expect(wrapper.get('[data-testid="building-with-us-contract-error"]').text()).toContain('No se pudo cargar el contrato.');
  });

  it('explains an uninitialized contract', () => {
    const wrapper = mountContract({ contract: null });

    expect(wrapper.text()).toContain('El contrato aún no se ha inicializado.');
    expect(wrapper.find('[data-testid="building-with-us-contract-download-pdf"]').exists()).toBe(false);
  });
});
