import { mount } from '@vue/test-utils';
import McpHint from '../../components/BuildingOnDemand/admin/McpHint.vue';

const mockLocale = { value: 'es-co' };
jest.mock('#imports', () => ({
  useI18n: () => ({
    locale: mockLocale,
    t: (key) => {
      const language = mockLocale.value.startsWith('en') ? 'en' : 'es';
      const messages = jest.requireActual(`../../locales/buildingOnDemandAdmin/${language}`).default;
      return key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
    },
  }),
}));

const mounted = [];
function mountHint(connector = null) {
  const wrapper = mount(McpHint, { props: { connector } });
  mounted.push(wrapper);
  return wrapper;
}
beforeEach(() => { mockLocale.value = 'es-co'; });
afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount());
  jest.restoreAllMocks();
});

describe('BuildingOnDemandAdminMcpHint', () => {
  it.each([
    [true, 'Conector activo'],
    [false, 'Conector inactivo'],
    ['true', 'Estado del conector no disponible'],
  ])('explains the connector state for is_active=%s', (active, label) => {
    const wrapper = mountHint({ slug: 'building-on-demand', is_active: active });

    const hint = wrapper.get('[data-testid="building-on-demand-admin-mcp-hint"]');

    expect(hint.get('[data-testid="building-on-demand-admin-mcp-status"]').text()).toBe(label);
    expect(hint.text()).toContain('con vista previa y confirmación');
    expect(hint.text()).toContain('Este panel es de solo lectura.');
    expect(hint.find('button').exists()).toBe(false);
  });

  it('identifies the MCP connector when overview data is unavailable', () => {
    const wrapper = mountHint();

    expect(wrapper.get('[data-testid="building-on-demand-admin-mcp-slug"]').text()).toBe('building-on-demand');
    expect(wrapper.get('[data-testid="building-on-demand-admin-mcp-status"]').text()).toBe('Estado del conector no disponible');
    expect(wrapper.text()).toContain('únicamente desde el conector MCP building-on-demand');
  });

  it('explains read-only administration in the English locale', () => {
    mockLocale.value = 'en-us';
    const wrapper = mountHint({ slug: 'building-on-demand', is_active: false });

    expect(wrapper.get('[data-testid="building-on-demand-admin-mcp-status"]').text()).toBe('Connector inactive');
    expect(wrapper.text()).toContain('with a preview and confirmation');
    expect(wrapper.text()).toContain('This panel is read-only.');
  });
});
