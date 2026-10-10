import { mount } from '@vue/test-utils';
import VersionHistory from '../../components/BuildingWithUs/admin/VersionHistory.vue';
import BaseAlert from '../../components/base/BaseAlert.vue';

jest.mock('#imports', () => ({
  useI18n: () => ({
    locale: { value: 'es-co' },
    t: (key, params = {}) => {
      const messages = jest.requireActual('../../locales/buildingWithUsAdmin/es').default;
      const message = key.split('.').slice(1).reduce((value, part) => value?.[part], messages) || key;
      return Object.entries(params).reduce((text, [name, value]) => text.replace(`{${name}}`, value), message);
    },
  }),
}));

const makeVersion = (overrides = {}) => ({
  version_id: 42, version: 3, author: 'Ana', created_at: '2026-10-09T15:00:00Z',
  change_note: 'Aporte del experto actualizado', restored_from_version_id: null, restored_from_version: null, ...overrides,
});
const mounted = [];
function mountHistory(overrides = {}) {
  const wrapper = mount(VersionHistory, {
    props: { kind: 'program', versions: [makeVersion()], total: 2, ...overrides },
    global: { components: { BaseAlert }, stubs: { NuxtLink: true } },
  });
  mounted.push(wrapper);
  return wrapper;
}
afterEach(() => { mounted.splice(0).forEach((wrapper) => wrapper.unmount()); jest.restoreAllMocks(); });

describe('BuildingWithUsAdminVersionHistory', () => {
  it('shows the published version metadata', () => {
    const wrapper = mountHistory();

    const row = wrapper.get('[data-testid="building-with-us-program-version-42"]');

    expect(row.text()).toContain('Versión 3');
    expect(row.text()).toContain('Ana');
    expect(row.text()).toContain('Aporte del experto actualizado');
    expect(wrapper.text()).toContain('1 de 2 versiones');
  });

  it('requests more versions through the pagination button', async () => {
    const wrapper = mountHistory();

    await wrapper.get('[data-testid="building-with-us-program-history-more"]').trigger('click');

    expect(wrapper.emitted('load-more')).toEqual([[]]);
  });

  it('hides pagination when the history is complete', () => {
    const wrapper = mountHistory({ total: 1 });

    expect(wrapper.find('[data-testid="building-with-us-program-history-more"]').exists()).toBe(false);
  });

  it('offers a retry for failed contract history', async () => {
    const wrapper = mountHistory({ kind: 'contract', error: 'request_failed' });

    await wrapper.get('[data-testid="building-with-us-contract-history-retry"]').trigger('click');

    expect(wrapper.emitted('retry')).toEqual([[]]);
    expect(wrapper.get('[data-testid="building-with-us-contract-history-error"]').text()).toContain('No se pudo cargar el historial');
  });

  it('blocks pagination while the next page loads', () => {
    const wrapper = mountHistory({ isLoading: true });

    expect(wrapper.get('[data-testid="building-with-us-program-history-more"]').attributes('disabled')).toBeDefined();
    expect(wrapper.get('[role="status"]').text()).toBe('Cargando…');
  });

  it('identifies the source of a restored version', () => {
    const wrapper = mountHistory({ versions: [makeVersion({ restored_from_version_id: 40, restored_from_version: 1 })] });

    expect(wrapper.get('[data-testid="building-with-us-program-version-42"]').text()).toContain('Restaurada desde la versión 1');
  });

  it.each([null, undefined])('hides the restored source without a version number (%s)', (restoredFromVersion) => {
    const wrapper = mountHistory({ versions: [makeVersion({ restored_from_version_id: 40, restored_from_version: restoredFromVersion })] });

    expect(wrapper.get('[data-testid="building-with-us-program-version-42"]').text()).not.toContain('Restaurada desde la versión');
  });

  it('shows an empty history message', () => {
    const wrapper = mountHistory({ versions: [], total: 0 });

    expect(wrapper.text()).toContain('Todavía no hay versiones en el historial.');
  });
});
