import { flushPromises, mount } from '@vue/test-utils';
import ContractPanel from '../../components/BuildingOnDemand/admin/ContractPanel.vue';

const mockLocale = { value: 'es-co' };
jest.mock('../../stores/services/request_http', () => ({ get_request: jest.fn() }));
jest.mock('#imports', () => ({
  useLocalePath: () => (path) => `/${mockLocale.value}${path}`,
  useI18n: () => ({
    locale: mockLocale,
    t: (key, params = {}) => {
      const language = mockLocale.value.startsWith('en') ? 'en' : 'es';
      const messages = jest.requireActual(`../../locales/buildingOnDemandAdmin/${language}`).default;
      const message = key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
      return Object.entries(params).reduce((text, [name, value]) => text.replace(`{${name}}`, value), message);
    },
  }),
}));

const makeContract = (overrides = {}) => ({
  version: 4, version_id: 24, author: 'Ana', updated_at: '2026-10-09T15:00:00Z',
  change_note: 'Bolsa mensual acordada', markdown: '# Contrato de célula\n\nEl cliente dispone de una bolsa mensual.',
  mirror: {
    status: 'synchronized', document_id: 15, folder_path: 'ProjectApp › Contratos › Building on Demand',
    title: 'Contrato de célula Scrum', version: 4, last_synced_at: '2026-10-09T16:30:00Z',
  },
  ...overrides,
});
const mounted = [];
function mountContract(overrides = {}) {
  const wrapper = mount(ContractPanel, {
    props: { contract: makeContract(), ...overrides },
    global: {
      stubs: {
        PanelDownloadLink: {
          props: ['url', 'label', 'filename'],
          template: '<a :href="url" :download="filename">{{ label }}</a>',
        },
        NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  });
  mounted.push(wrapper);
  return wrapper;
}
beforeEach(() => { mockLocale.value = 'es-co'; });
afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount());
  jest.restoreAllMocks();
});

describe('BuildingOnDemandAdminContractPanel', () => {
  it('opens the mirrored contract through the localized Documents module', () => {
    const wrapper = mountContract();

    const mirror = wrapper.get('[data-testid="building-on-demand-admin-contract-mirror"]');

    expect(mirror.get('[data-testid="building-on-demand-admin-mirror-link"]').attributes('href')).toBe('/es-co/panel/documents/15/edit');
    expect(mirror.text()).toContain('ProjectApp › Contratos › Building on Demand');
    expect(mirror.text()).toContain('Contrato de célula Scrum');
    expect(mirror.text()).toContain('Versión de la copia: 4');
    expect(mirror.text()).toContain('Vie, 9 oct 2026, 11:30');
    expect(mirror.get('[data-testid="building-on-demand-admin-contract-status"]').text()).toBe('Sincronizado');
  });

  it('retains mirror information when no document can be opened', () => {
    const wrapper = mountContract({ mirror: { status: 'synchronized', folder_path: 'ProjectApp › Contratos', document_id: null } });

    expect(wrapper.find('[data-testid="building-on-demand-admin-mirror-link"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-mirror"]').text()).toContain('ProjectApp › Contratos');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-status"]').text()).toBe('Sincronizado');
  });

  it.each([
    ['out_of_sync', 'Desactualizado', 'está desactualizada'],
    ['not_initialized', 'Sin inicializar', 'se inicializa'],
  ])('explains MCP recovery for mirror state %s', (status, label, explanation) => {
    const wrapper = mountContract({ mirror: { status } });

    const warning = wrapper.get('[data-testid="building-on-demand-admin-mirror-alert"]');

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-status"]').text()).toBe(label);
    expect(warning.text()).toContain(explanation);
    expect(warning.text()).toContain('conector MCP building-on-demand');
    expect(warning.find('button').exists()).toBe(false);
  });

  it('identifies an unrecognized mirror state without suggesting a false recovery', () => {
    const wrapper = mountContract({ mirror: { status: 'unexpected', folder_path: 'ProjectApp › Contratos' } });

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-status"]').text()).toBe('Desconocido');
    expect(wrapper.find('[data-testid="building-on-demand-admin-mirror-alert"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-version"]').text()).toContain('Bolsa mensual acordada');
  });

  it('explains a contract whose document mirror has not been initialized', () => {
    const wrapper = mountContract({ contract: makeContract({ mirror: null }) });

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-status"]').text()).toBe('Sin inicializar');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-mirror"]').text()).toContain('ProjectApp › Contratos');
    expect(wrapper.get('[data-testid="building-on-demand-admin-mirror-alert"]').text()).toContain('se inicializa desde el conector MCP building-on-demand');
    expect(wrapper.find('[data-testid="building-on-demand-admin-mirror-link"]').exists()).toBe(false);
  });

  it('uses the latest mirror supplied by the overview', () => {
    const wrapper = mountContract({
      mirror: { status: 'out_of_sync', document_id: 32, folder_path: 'ProjectApp › Contratos › Células', version: 3 },
    });

    const mirror = wrapper.get('[data-testid="building-on-demand-admin-contract-mirror"]');

    expect(mirror.text()).toContain('Versión de la copia: 3');
    expect(mirror.text()).toContain('ProjectApp › Contratos › Células');
    expect(mirror.get('[data-testid="building-on-demand-admin-mirror-link"]').attributes('href')).toBe('/es-co/panel/documents/32/edit');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-version"]').text()).toContain('Versión 4');
  });

  it('offers the current contract as a named PDF attachment', () => {
    const wrapper = mountContract();

    const download = wrapper.get('[data-testid="building-on-demand-admin-contract-download-pdf"]');

    expect(download.attributes()).toMatchObject({ href: '/api/building-on-demand/admin/contract/pdf/', download: 'building-on-demand-contract.pdf' });
    expect(download.text()).toBe('Descargar PDF del contrato');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-version"]').text()).toContain('Versión 4');
  });

  it('views the PDF inline in a separate browser tab', () => {
    const wrapper = mountContract();

    const viewer = wrapper.get('[data-testid="building-on-demand-admin-contract-view-pdf"]');

    expect(viewer.attributes()).toMatchObject({ href: '/api/building-on-demand/admin/contract/pdf/?inline=1', target: '_blank', rel: 'noopener noreferrer' });
    expect(viewer.text()).toBe('Ver PDF del contrato');
  });

  it('renders the published markdown as a read-only document', async () => {
    const wrapper = mountContract({ contract: makeContract({ markdown: '# Contrato de célula\n\n| Concepto | Detalle |\n| --- | --- |\n| Bolsa | Mensual |' }) });

    await flushPromises();

    const body = wrapper.get('[data-testid="building-on-demand-admin-contract-body"]');
    expect(body.get('h1').text()).toBe('Contrato de célula');
    expect(body.get('td').text()).toBe('Bolsa');
    expect(body.findAll('td').map((cell) => cell.text())).toEqual(['Bolsa', 'Mensual']);
    expect(body.find('textarea').exists()).toBe(false);
  });

  it('keeps the contract reading region accessible without markdown content', async () => {
    const wrapper = mountContract({ contract: makeContract({ markdown: undefined }) });

    await flushPromises();

    const body = wrapper.get('[data-testid="building-on-demand-admin-contract-body"]');
    expect(body.text()).toBe('');
    expect(body.attributes()).toMatchObject({ role: 'region', tabindex: '0', 'aria-describedby': 'building-on-demand-admin-contract-scroll-hint' });
    expect(wrapper.get('#building-on-demand-admin-contract-scroll-hint').text()).toContain('Las tablas anchas se pueden desplazar horizontalmente');
  });

  it('requests a retry for an unexpected contract failure', async () => {
    const wrapper = mountContract({ contract: null, error: 'request_failed' });

    await wrapper.get('[data-testid="building-on-demand-admin-contract-retry"]').trigger('click');

    expect(wrapper.emitted('retry')).toEqual([[]]);
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-error"]').text()).toContain('No se pudo cargar el contrato.');
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-download-pdf"]').exists()).toBe(false);
  });

  it('treats the expected missing-contract response as a neutral state', () => {
    const wrapper = mountContract({ contract: null, unavailable: true, error: 'not_found' });

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-unavailable"]').text()).toBe('El contrato todavía no está disponible');
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-retry"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-status"]').exists()).toBe(false);
  });

  it('explains a missing contract before the first publication', () => {
    const wrapper = mountContract({ contract: null });

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-unavailable"]').text()).toBe('El contrato todavía no está disponible');
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-body"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-view-pdf"]').exists()).toBe(false);
  });

  it('announces the initial contract request without showing an empty result', () => {
    const wrapper = mountContract({ contract: null, isLoading: true });

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-loading"]').attributes('aria-label')).toBe('Cargando…');
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-unavailable"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-download-pdf"]').exists()).toBe(false);
  });

  it('retains the published contract during a refresh', () => {
    const wrapper = mountContract({ isLoading: true });

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-version"]').text()).toContain('Versión 4');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-download-pdf"]').attributes('href')).toBe('/api/building-on-demand/admin/contract/pdf/');
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-loading"]').exists()).toBe(false);
  });

  it('localizes mirror synchronization details for the English panel', () => {
    mockLocale.value = 'en-us';
    const wrapper = mountContract();

    const mirror = wrapper.get('[data-testid="building-on-demand-admin-contract-mirror"]');
    expect(mirror.text()).toContain('Fri, Oct 9, 2026, 11:30');
    expect(mirror.get('[data-testid="building-on-demand-admin-contract-status"]').text()).toBe('Synchronized');
    expect(mirror.get('[data-testid="building-on-demand-admin-mirror-link"]').attributes('href')).toBe('/en-us/panel/documents/15/edit');
  });

  it('labels a malformed synchronization timestamp as unavailable', () => {
    const wrapper = mountContract({ mirror: { status: 'synchronized', last_synced_at: 'invalid' } });

    const mirror = wrapper.get('[data-testid="building-on-demand-admin-contract-mirror"]');
    expect(mirror.find('dd').text()).toBe('No disponible');
    expect(mirror.text()).toContain('Última sincronización');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-status"]').text()).toBe('Sincronizado');
  });
});
