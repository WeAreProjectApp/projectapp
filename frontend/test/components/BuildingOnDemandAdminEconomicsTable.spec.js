import { nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import EconomicsTable from '../../components/BuildingOnDemand/admin/EconomicsTable.vue';
import { PANEL_BREAKPOINTS } from '../../config/responsive';

let mockLocale = 'es-co';
jest.mock('#imports', () => ({
  useI18n: () => ({
    locale: { value: mockLocale },
    t: (key, params = {}) => {
      const messages = mockLocale.startsWith('en')
        ? jest.requireActual('../../locales/buildingOnDemandAdmin/en').default
        : jest.requireActual('../../locales/buildingOnDemandAdmin/es').default;
      const message = key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
      return Object.entries(params).reduce((text, [name, value]) => text.replace(`{${name}}`, value), message);
    },
  }),
}));

const makeRow = (overrides = {}) => ({
  tier: 'business', term: 'monthly', months: 1, monthly_price: 4200000,
  hosting_cost_monthly: 116501, net_monthly: 4083499, breakeven_hours: 74.2,
  breakeven_hours_rounded: 74, bag_hours: 192, bag_share_percent: 39,
  breakeven_hours_without_hosting: 76.4, ...overrides,
});
const makeEconomics = (overrides = {}) => ({
  currency: 'COP', hour_cost: 55000, vat_percent: 19, provider: 'Hostinger',
  reference_url: 'https://www.hostinger.com/co/vps-servidor-web', consulted_on: '2026-10-10',
  tiers: [
    { id: 'starter', name: 'Starter', bag_hours: 96, plan: 'KVM 1', promo_monthly: 19900, renewal_monthly: 38900, hosting_cost_monthly: 46291 },
    { id: 'business', name: 'Business', bag_hours: 192, plan: 'KVM 4', promo_monthly: 38900, renewal_monthly: 97900, hosting_cost_monthly: 116501 },
    { id: 'enterprise', name: 'Enterprise', bag_hours: 288, plan: 'KVM 8', promo_monthly: 77900, renewal_monthly: 168900, hosting_cost_monthly: 200991 },
  ],
  rows: [
    makeRow({ tier: 'starter', monthly_price: 1800000, hosting_cost_monthly: 46291, net_monthly: 1753709, breakeven_hours: 31.9, breakeven_hours_rounded: 32, bag_hours: 96, bag_share_percent: 33, breakeven_hours_without_hosting: 32.7 }),
    makeRow(),
    makeRow({ tier: 'enterprise', monthly_price: 9600000, hosting_cost_monthly: 200991, net_monthly: 9399009, breakeven_hours: 170.9, breakeven_hours_rounded: 171, bag_hours: 288, bag_share_percent: 59, breakeven_hours_without_hosting: 174.5 }),
    makeRow({ tier: 'starter', term: 'nine-month', months: 9, monthly_price: 1530000, hosting_cost_monthly: 46291, net_monthly: 1483709, breakeven_hours: 27.0, breakeven_hours_rounded: 27, bag_hours: 96, bag_share_percent: 28, breakeven_hours_without_hosting: 27.8 }),
    makeRow({ term: 'nine-month', months: 9, monthly_price: 3360000, net_monthly: 3243499, breakeven_hours: 59.0, breakeven_hours_rounded: 59, bag_share_percent: 31, breakeven_hours_without_hosting: 61.1 }),
    makeRow({ tier: 'enterprise', term: 'nine-month', months: 9, monthly_price: 7200000, hosting_cost_monthly: 200991, net_monthly: 6999009, breakeven_hours: 127.3, breakeven_hours_rounded: 127, bag_hours: 288, bag_share_percent: 44, breakeven_hours_without_hosting: 130.9 }),
  ],
  ...overrides,
});

const mounted = [];
const originalMatchMedia = window.matchMedia;
async function mountEconomics(overrides = {}, width = 1440) {
  window.matchMedia = jest.fn().mockReturnValue({
    matches: width < PANEL_BREAKPOINTS.landscape,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  });
  const wrapper = mount(EconomicsTable, {
    props: { economics: makeEconomics(), ...overrides },
    global: { stubs: { NuxtLink: true } },
  });
  mounted.push(wrapper);
  await nextTick();
  return wrapper;
}
afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount());
  mockLocale = 'es-co';
  if (originalMatchMedia === undefined) delete window.matchMedia;
  else window.matchMedia = originalMatchMedia;
  jest.restoreAllMocks();
});

describe('BuildingOnDemandAdminEconomicsTable', () => {
  it.each([
    ['starter', 'Starter', '$1.800.000 COP', '$46.291 COP', '$1.753.709 COP', '31,9 h', '33 %', '96 h'],
    ['business', 'Business', '$4.200.000 COP', '$116.501 COP', '$4.083.499 COP', '74,2 h', '39 %', '192 h'],
    ['enterprise', 'Enterprise', '$9.600.000 COP', '$200.991 COP', '$9.399.009 COP', '170,9 h', '59 %', '288 h'],
  ])('presents the monthly economics supplied for %s', async (tier, name, price, hosting, net, breakeven, share, bag) => {
    const wrapper = await mountEconomics();

    const row = wrapper.get(`[data-testid="building-on-demand-admin-economics-row-${tier}-monthly"]`);

    expect(row.findAll('td').map((cell) => cell.text())).toEqual([name, price, hosting, net, breakeven, share, bag]);
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-term-monthly"]').find('table').exists()).toBe(true);
  });

  it.each([
    ['starter', '27,0 h', '28 %'],
    ['business', '59,0 h', '31 %'],
    ['enterprise', '127,3 h', '44 %'],
  ])('shows the nine month consumption threshold for %s', async (tier, breakeven, share) => {
    const wrapper = await mountEconomics();

    const row = wrapper.get(`[data-testid="building-on-demand-admin-economics-row-${tier}-nine-month"]`);

    expect(row.text()).toContain(breakeven);
    expect(row.text()).toContain(share);
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-term-nine-month"]').text()).toContain('9 meses');
  });

  it.each([412, 835])('preserves the financial details as cards at %s pixels', async (width) => {
    const wrapper = await mountEconomics({}, width);

    const card = wrapper.get('[data-testid="building-on-demand-admin-economics-row-business-monthly"]');

    expect(wrapper.findAll('table')).toHaveLength(0);
    expect(wrapper.findAll('[data-testid^="building-on-demand-admin-economics-row-"]')).toHaveLength(6);
    expect(card.text()).toContain('Business');
    expect(card.findAll('dt').map((label) => label.text())).toEqual([
      'Precio mensual', 'Hosting con IVA', 'Neto mensual', 'Horas de equilibrio', 'Porcentaje de la bolsa', 'Horas de la bolsa',
    ]);
    expect(card.findAll('dd').map((value) => value.text())).toEqual([
      '$4.200.000 COP', '$116.501 COP', '$4.083.499 COP', '74,2 h', '39 %', '192 h',
    ]);
  });

  it('exposes the dated provider source behind the internal inputs', async () => {
    const wrapper = await mountEconomics();

    const link = wrapper.get('[data-testid="building-on-demand-admin-economics-reference"]');

    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-hour-cost"]').text()).toBe('$55.000 COP');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-vat"]').text()).toBe('19 %');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-provider"]').text()).toBe('Hostinger');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-consulted-on"]').text()).toBe('Sáb, 10 oct 2026');
    expect({ href: link.attributes('href'), target: link.attributes('target'), rel: link.attributes('rel') }).toEqual({
      href: 'https://www.hostinger.com/co/vps-servidor-web', target: '_blank', rel: 'noopener noreferrer',
    });
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-note"]').text()).toContain('Estos números son internos y nunca se publican.');
  });

  it('preserves backend thresholds when the reference cost changes', async () => {
    const wrapper = await mountEconomics({ economics: makeEconomics({ hour_cost: 110000, vat_percent: 20 }) });

    const row = wrapper.get('[data-testid="building-on-demand-admin-economics-row-business-monthly"]');

    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-hour-cost"]').text()).toBe('$110.000 COP');
    expect(row.text()).toContain('74,2 h');
    expect(row.text()).toContain('$116.501 COP');
    expect(row.text()).toContain('39 %');
  });

  it.each([null, {}])('explains missing economics without fabricating rows (%s)', async (economics) => {
    const wrapper = await mountEconomics({ economics });

    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-empty"]').text()).toBe('Todavía no hay datos de economía disponibles.');
    expect(wrapper.findAll('[data-testid^="building-on-demand-admin-economics-row-"]')).toHaveLength(0);
    expect(wrapper.find('[data-testid="building-on-demand-admin-economics-retry"]').exists()).toBe(false);
  });

  it('requests recovery from the failed economics state', async () => {
    const wrapper = await mountEconomics({ economics: null, error: 'request_failed' });

    await wrapper.get('[data-testid="building-on-demand-admin-economics-retry"]').trigger('click');

    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-error"]').text()).toContain('No se pudo cargar la economía del programa.');
    expect(wrapper.emitted('retry')).toEqual([[]]);
    expect(wrapper.find('[data-testid="building-on-demand-admin-economics-empty"]').exists()).toBe(false);
  });

  it('announces the pending economics response', async () => {
    const wrapper = await mountEconomics({ economics: null, isLoading: true });

    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-loading"]').text()).toBe('Cargando…');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics"]').attributes('aria-busy')).toBe('true');
    expect(wrapper.find('[data-testid="building-on-demand-admin-economics-empty"]').exists()).toBe(false);
  });

  it('prevents a duplicate economics retry during loading', async () => {
    const wrapper = await mountEconomics({ economics: null, error: 'request_failed', isLoading: true });

    await wrapper.get('[data-testid="building-on-demand-admin-economics-retry"]').trigger('click');

    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-retry"]').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-loading"]').text()).toBe('Cargando…');
    expect(wrapper.emitted('retry')).toBeUndefined();
  });

  it('distinguishes unavailable inputs from zero financial values', async () => {
    const wrapper = await mountEconomics({ economics: makeEconomics({
      currency: '', hour_cost: null, vat_percent: 0, provider: '', reference_url: null, consulted_on: null,
      tiers: [], rows: [makeRow({ monthly_price: null, hosting_cost_monthly: 'invalid', net_monthly: 0, breakeven_hours: null, bag_share_percent: 'invalid', bag_hours: 0 })],
    }) });

    const row = wrapper.get('[data-testid="building-on-demand-admin-economics-row-business-monthly"]');

    expect([
      wrapper.get('[data-testid="building-on-demand-admin-economics-hour-cost"]').text(),
      wrapper.get('[data-testid="building-on-demand-admin-economics-vat"]').text(),
      wrapper.get('[data-testid="building-on-demand-admin-economics-provider"]').text(),
      wrapper.get('[data-testid="building-on-demand-admin-economics-consulted-on"]').text(),
      wrapper.get('[data-testid="building-on-demand-admin-economics-reference-unavailable"]').text(),
    ]).toEqual(['No disponible', '0 %', 'No disponible', 'No disponible', 'No disponible']);
    expect(row.text()).toContain('business');
    expect(row.text()).toContain('$0 COP');
    expect(row.text()).toContain('0 h');
    expect(row.text()).toContain('No disponible');
  });

  it.each(['http://example.com/prices', 'javascript:alert(1)'])('withholds an unsafe provider reference (%s)', async (referenceUrl) => {
    const wrapper = await mountEconomics({ economics: makeEconomics({ reference_url: referenceUrl }) });

    expect(wrapper.find('[data-testid="building-on-demand-admin-economics-reference"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-reference-unavailable"]').text()).toBe('No disponible');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-provider"]').text()).toBe('Hostinger');
  });

  it('formats the threshold for an English panel', async () => {
    mockLocale = 'en-us';
    const wrapper = await mountEconomics();

    const row = wrapper.get('[data-testid="building-on-demand-admin-economics-row-business-monthly"]');

    expect(row.text()).toContain('74.2 h');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-term-monthly"]').text()).toContain('Monthly');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-consulted-on"]').text()).toBe('Sat, Oct 10, 2026');
    expect(wrapper.get('[data-testid="building-on-demand-admin-economics-note"]').text()).toContain('These figures are internal');
  });

  it('identifies a custom term through its server supplied duration', async () => {
    const wrapper = await mountEconomics({ economics: makeEconomics({ rows: [makeRow({ term: 'annual', months: 12 })] }) });

    const term = wrapper.get('[data-testid="building-on-demand-admin-economics-term-annual"]');

    expect(term.text()).toContain('12 meses');
    expect(term.get('[data-testid="building-on-demand-admin-economics-row-business-annual"]').text()).toContain('74,2 h');
    expect(wrapper.find('[data-testid="building-on-demand-admin-economics-term-monthly"]').exists()).toBe(false);
  });
});
