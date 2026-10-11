import { mount } from '@vue/test-utils';
import VersionHistory from '../../components/BuildingOnDemand/admin/VersionHistory.vue';
import VersionSummary from '../../components/BuildingOnDemand/admin/VersionSummary.vue';

const mockLocale = { value: 'es-co' };
jest.mock('#imports', () => ({
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

const makeVersion = (overrides = {}) => ({
  version_id: 42, version: 3, author: 'Ana', created_at: '2026-10-09T15:00:00Z',
  change_note: 'Bolsa mensual actualizada', restored_from_version_id: null, restored_from_version: null,
  ...overrides,
});
const mounted = [];
function mountHistory(overrides = {}) {
  const wrapper = mount(VersionHistory, {
    props: { kind: 'program', versions: [makeVersion()], total: 2, ...overrides },
    global: { stubs: { NuxtLink: true } },
  });
  mounted.push(wrapper);
  return wrapper;
}
function mountSummary(summary) {
  const wrapper = mount(VersionSummary, { props: { summary } });
  mounted.push(wrapper);
  return wrapper;
}
beforeEach(() => { mockLocale.value = 'es-co'; });
afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount());
  jest.restoreAllMocks();
});

describe('BuildingOnDemandAdminVersionHistory', () => {
  it('presents the published program revision as read-only metadata', () => {
    const wrapper = mountHistory();

    const revision = wrapper.get('[data-testid="building-on-demand-admin-program-version-42"]');

    expect(revision.text()).toContain('Versión 3');
    expect(revision.text()).toContain('Vie, 9 oct 2026, 10:00');
    expect(revision.text()).toContain('Ana');
    expect(revision.text()).toContain('Bolsa mensual actualizada');
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-history-count"]').text()).toBe('1 de 2 versiones');
    expect(revision.find('button').exists()).toBe(false);
  });

  it.each([
    [{ name: 'Ana López' }, 'Ana López'],
    [{ display_name: 'Ana del equipo' }, 'Ana del equipo'],
    [{ email: 'ana@example.com' }, 'ana@example.com'],
  ])('identifies a revision author from %j', (author, label) => {
    const wrapper = mountHistory({ versions: [makeVersion({ author })] });

    const details = wrapper.get('[data-testid="building-on-demand-admin-program-version-42"]').findAll('dd');

    expect(details.map((detail) => detail.text())).toEqual(['Vie, 9 oct 2026, 10:00', label, 'Bolsa mensual actualizada']);
  });

  it('requests the next page from the history control', async () => {
    const wrapper = mountHistory();

    await wrapper.get('[data-testid="building-on-demand-admin-program-history-more"]').trigger('click');

    expect(wrapper.emitted('load-more')).toEqual([[]]);
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-history-count"]').text()).toBe('1 de 2 versiones');
  });

  it('removes the next page control when the available history ends', () => {
    const wrapper = mountHistory({ total: 1 });

    expect(wrapper.get('[data-testid="building-on-demand-admin-program-history-count"]').text()).toBe('1 de 1 versiones');
    expect(wrapper.find('[data-testid="building-on-demand-admin-program-history-more"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-version-42"]').text()).toContain('Bolsa mensual actualizada');
  });

  it('retries contract history without discarding visible revisions', async () => {
    const wrapper = mountHistory({ kind: 'contract', error: 'request_failed' });

    await wrapper.get('[data-testid="building-on-demand-admin-contract-history-retry"]').trigger('click');

    expect(wrapper.emitted('retry')).toEqual([[]]);
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-history-error"]').text()).toContain('No se pudo cargar el historial de versiones.');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-version-42"]').text()).toContain('Versión 3');
    expect(wrapper.find('[data-testid="building-on-demand-admin-contract-history-more"]').exists()).toBe(false);
  });

  it('prevents another next-page request while history loads', async () => {
    const wrapper = mountHistory({ isLoading: true });
    const more = wrapper.get('[data-testid="building-on-demand-admin-program-history-more"]');

    await more.trigger('click');

    expect(more.attributes('disabled')).toBeDefined();
    expect(wrapper.get('[role="status"]').text()).toBe('Cargando…');
    expect(wrapper.emitted('load-more')).toBeUndefined();
  });

  it('explains the source revision of restored program content', () => {
    const wrapper = mountHistory({ versions: [makeVersion({ restored_from_version_id: 40, restored_from_version: 1 })] });

    const revision = wrapper.get('[data-testid="building-on-demand-admin-program-version-42"]');

    expect(revision.text()).toContain('Restaurada desde la versión 1');
    expect(revision.text()).toContain('Versión 3');
    expect(revision.text()).toContain('Bolsa mensual actualizada');
  });

  it.each([null, undefined])('omits a restoration attribution without a source number (%s)', (restoredFrom) => {
    const wrapper = mountHistory({ versions: [makeVersion({ restored_from_version_id: 40, restored_from_version: restoredFrom })] });

    const revision = wrapper.get('[data-testid="building-on-demand-admin-program-version-42"]');

    expect(revision.text()).not.toContain('Restaurada desde la versión');
    expect(revision.text()).toContain('Versión 3');
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-history-count"]').text()).toBe('1 de 2 versiones');
  });

  it('reports a program history with no published revisions', () => {
    const wrapper = mountHistory({ versions: [], total: 0 });

    expect(wrapper.get('[data-testid="building-on-demand-admin-program-history-empty"]').text()).toBe('Todavía no hay versiones en el historial.');
    expect(wrapper.get('[data-testid="building-on-demand-admin-program-history-count"]').text()).toBe('0 de 0 versiones');
    expect(wrapper.find('[data-testid="building-on-demand-admin-program-history-more"]').exists()).toBe(false);
  });

  it('formats revision dates for the English panel locale', () => {
    mockLocale.value = 'en-us';
    const wrapper = mountHistory({ kind: 'contract' });

    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-version-42"]').text()).toContain('Fri, Oct 9, 2026, 10:00');
    expect(wrapper.get('[data-testid="building-on-demand-admin-contract-history-count"]').text()).toBe('1 of 2 versions');
    expect(wrapper.text()).toContain('Contract history');
  });

  it('explains the absence of a current program version', () => {
    const wrapper = mountSummary(null);

    expect(wrapper.text()).toBe('Todavía no hay una versión publicada.');
    expect(wrapper.find('dl').exists()).toBe(false);
  });

  it('provides readable metadata when a revision has missing details', () => {
    const wrapper = mountSummary(makeVersion({ version: null, author: null, created_at: 'invalid', change_note: '' }));

    expect(wrapper.text()).toContain('Versión No disponible');
    expect(wrapper.findAll('dd').map((detail) => detail.text())).toEqual(['No disponible', 'No disponible', 'Sin nota de cambio']);
  });
});
