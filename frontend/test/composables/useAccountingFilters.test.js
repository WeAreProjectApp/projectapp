/**
 * Tests for the useAccountingFilters factory (generalization of
 * useClientFilters): defaults, activeFilterCount, applyFilters with the
 * prebuilt matchers, and resetFilters.
 */

if (typeof globalThis.structuredClone === 'undefined') {
  globalThis.structuredClone = (val) => JSON.parse(JSON.stringify(val));
}

const mockRoute = require('vue').reactive({ query: {} });
const mockReplace = jest.fn();

jest.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ replace: mockReplace }),
}));

jest.mock('~/composables/useSavedFilterTabs', () => {
  const { ref, computed } = require('vue');
  const savedTabsRef = ref([]);
  const stub = {
    savedTabs: savedTabsRef,
    isLoading: ref(false),
    isReady: ref(true),
    lastError: ref(null),
    isTabLimitReached: computed(() => savedTabsRef.value.length >= 12),
    MAX_TABS: 12,
    loadTabs: jest.fn(() => Promise.resolve(savedTabsRef.value)),
    saveTab: jest.fn(async (name, filters) => {
      const tab = { id: savedTabsRef.value.length + 1, view: 'accounting_income', name, filters, order: 0 };
      savedTabsRef.value = [...savedTabsRef.value, tab];
      return tab;
    }),
    updateTabFilters: jest.fn(),
    restoreTab: jest.fn(),
    rebaseTab: jest.fn(),
    renameTab: jest.fn(),
    deleteTab: jest.fn(async (id) => {
      savedTabsRef.value = savedTabsRef.value.filter((t) => t.id !== id);
    }),
  };
  return { useSavedFilterTabs: () => stub, __stub: stub };
});

import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';
import * as savedFilterTabsModule from '~/composables/useSavedFilterTabs';
import { collectionProjectFilter, numericFilterIds, optionalFilterIds, repeatedFilterText } from '~/utils/accountingFilterQuery';
import {
  useAccountingFilters,
  matchDateRange,
  matchNumberRange,
  matchIncludes,
  matchEquals,
  matchBooleanIncludes,
  matchAnyToken,
  coerceToDefaultShape,
} from '~/composables/useAccountingFilters';

const tabsStub = savedFilterTabsModule.__stub;
const savedTabsRef = tabsStub.savedTabs;

beforeEach(() => {
  savedTabsRef.value = [];
  mockRoute.query = {};
  mockReplace.mockClear();
  tabsStub.saveTab.mockClear();
  tabsStub.deleteTab.mockClear();
  tabsStub.restoreTab.mockReset();
  tabsStub.rebaseTab.mockReset();
});

const DEFAULTS = {
  statuses: [],
  method: null,
  amountMin: null,
  amountMax: null,
  dateAfter: null,
  dateBefore: null,
};

function makeFilters() {
  return useAccountingFilters({
    viewName: 'accounting_income',
    defaults: DEFAULTS,
    matchers: {
      statuses: matchIncludes('status', 'statuses'),
      method: matchEquals('method', 'method'),
      amountRange: matchNumberRange('amount', 'amountMin', 'amountMax'),
      dateRange: matchDateRange('date', 'dateAfter', 'dateBefore'),
    },
    searchFields: ['concept', 'client_name'],
  });
}

const baseRecord = (overrides = {}) => ({
  status: 'paid',
  method: 'transfer',
  amount: 500000,
  date: '2026-02-15',
  concept: 'Página web',
  client_name: 'Acme SAS',
  ...overrides,
});

describe('defaults', () => {
  it('initializes currentFilters with defaults plus empty search', () => {
    const { currentFilters } = makeFilters();
    expect(currentFilters).toMatchObject({ ...DEFAULTS, search: '' });
  });

  it('starts with no active filters', () => {
    const { activeFilterCount, hasActiveFilters } = makeFilters();
    expect(activeFilterCount.value).toBe(0);
    expect(hasActiveFilters.value).toBe(false);
  });
});

describe('activeFilterCount', () => {
  it('counts each dimension once, ranges included', () => {
    const { currentFilters, activeFilterCount } = makeFilters();
    currentFilters.statuses = ['paid'];
    currentFilters.amountMin = 1000;
    currentFilters.amountMax = 900000;
    currentFilters.dateAfter = '2026-01-01';
    currentFilters.search = 'acme';
    expect(activeFilterCount.value).toBe(4);
  });

  it('does not count values equal to their defaults', () => {
    const { currentFilters, activeFilterCount } = makeFilters();
    currentFilters.statuses = [];
    currentFilters.method = null;
    currentFilters.search = '   ';
    expect(activeFilterCount.value).toBe(0);
  });
});

describe('applyFilters', () => {
  it('returns records untouched when no filter is active', () => {
    const { applyFilters } = makeFilters();
    const list = [baseRecord(), baseRecord({ status: 'pending' })];
    expect(applyFilters(list)).toBe(list);
  });

  it('filters with matchIncludes over multi-select arrays', () => {
    const { currentFilters, applyFilters } = makeFilters();
    const list = [baseRecord({ status: 'paid' }), baseRecord({ status: 'pending' })];
    currentFilters.statuses = ['pending'];
    const result = applyFilters(list);
    expect(result).toHaveLength(1);
    expect(result[0].status).toBe('pending');
  });

  it('filters with matchEquals', () => {
    const { currentFilters, applyFilters } = makeFilters();
    const list = [baseRecord({ method: 'transfer' }), baseRecord({ method: 'cash' })];
    currentFilters.method = 'cash';
    const result = applyFilters(list);
    expect(result).toHaveLength(1);
    expect(result[0].method).toBe('cash');
  });

  it('filters with matchNumberRange (numeric strings supported)', () => {
    const { currentFilters, applyFilters } = makeFilters();
    const list = [
      baseRecord({ amount: '100000' }),
      baseRecord({ amount: 500000 }),
      baseRecord({ amount: 1200000 }),
    ];
    currentFilters.amountMin = 200000;
    currentFilters.amountMax = 1000000;
    const result = applyFilters(list);
    expect(result).toHaveLength(1);
    expect(result[0].amount).toBe(500000);
  });

  it('date range max bound is inclusive to end of day', () => {
    const { currentFilters, applyFilters } = makeFilters();
    const list = [
      baseRecord({ date: '2026-03-10T20:30:00' }),
      baseRecord({ date: '2026-03-11T08:00:00' }),
    ];
    currentFilters.dateBefore = '2026-03-10';
    const result = applyFilters(list);
    expect(result).toHaveLength(1);
    expect(result[0].date).toBe('2026-03-10T20:30:00');
  });

  it('date range drops records without the date field', () => {
    const { currentFilters, applyFilters } = makeFilters();
    const list = [baseRecord({ date: '2026-02-15' }), baseRecord({ date: null })];
    currentFilters.dateAfter = '2026-01-01';
    expect(applyFilters(list)).toHaveLength(1);
  });

  it('free-text search is case-insensitive across searchFields', () => {
    const { currentFilters, applyFilters } = makeFilters();
    const list = [
      baseRecord({ concept: 'Hosting anual', client_name: 'Beta Ltda' }),
      baseRecord({ concept: 'Página web', client_name: 'ACME SAS' }),
    ];
    currentFilters.search = 'acme';
    const result = applyFilters(list);
    expect(result).toHaveLength(1);
    expect(result[0].client_name).toBe('ACME SAS');
  });

  it('combines search and matchers with AND semantics', () => {
    const { currentFilters, applyFilters } = makeFilters();
    const list = [
      baseRecord({ client_name: 'Acme SAS', status: 'paid' }),
      baseRecord({ client_name: 'Acme SAS', status: 'pending' }),
    ];
    currentFilters.search = 'acme';
    currentFilters.statuses = ['paid'];
    const result = applyFilters(list);
    expect(result).toHaveLength(1);
    expect(result[0].status).toBe('paid');
  });
});

describe('matchIncludes nullAs', () => {
  function makeNullableFilters() {
    return useAccountingFilters({
      viewName: 'accounting_pocket',
      defaults: { ledger: [] },
      matchers: {
        ledger: matchIncludes('linked_ledger', 'ledger', { nullAs: 'none' }),
      },
    });
  }

  const rows = [
    { id: 1, linked_ledger: 'gustavo' },
    { id: 2, linked_ledger: 'company' },
    { id: 3, linked_ledger: null },
  ];

  it('maps a null field onto the sentinel token', () => {
    const { currentFilters, applyFilters } = makeNullableFilters();
    currentFilters.ledger = ['none'];
    expect(applyFilters(rows).map((r) => r.id)).toEqual([3]);
  });

  it('leaves null rows out of a real value cut', () => {
    const { currentFilters, applyFilters } = makeNullableFilters();
    currentFilters.ledger = ['company'];
    expect(applyFilters(rows).map((r) => r.id)).toEqual([2]);
  });

  it('combines the sentinel with real values as OR', () => {
    const { currentFilters, applyFilters } = makeNullableFilters();
    currentFilters.ledger = ['gustavo', 'none'];
    expect(applyFilters(rows).map((r) => r.id)).toEqual([1, 3]);
  });

  it('does not map nulls without the option', () => {
    const plain = useAccountingFilters({
      viewName: 'accounting_pocket',
      defaults: { ledger: [] },
      matchers: { ledger: matchIncludes('linked_ledger', 'ledger') },
    });

    // Real values still match, so the sentinel finding nothing is the opt-in
    // behaviour and not a matcher that silently rejects everything.
    plain.currentFilters.ledger = ['gustavo'];
    expect(plain.applyFilters(rows).map((r) => r.id)).toEqual([1]);

    plain.currentFilters.ledger = ['none'];
    expect(plain.applyFilters(rows)).toHaveLength(0);
  });
});

describe('countTabs', () => {
  const list = [
    baseRecord({ status: 'paid' }),
    baseRecord({ status: 'paid' }),
    baseRecord({ status: 'pending' }),
  ];

  it('counts each tab cut plus the honest total', () => {
    const { countTabs } = makeFilters();
    const counts = countTabs(list, [
      { id: 7, filters: { statuses: ['paid'] } },
      { id: 8, filters: { statuses: ['pending'] } },
    ]);
    expect(counts).toEqual({ all: 3, 7: 2, 8: 1 });
  });

  it('reports a zero rather than hiding an empty tab', () => {
    const { countTabs } = makeFilters();
    const counts = countTabs(list, [{ id: 9, filters: { statuses: ['lost'] } }]);
    expect(counts[9]).toBe(0);
  });

  it('merges a partial stored filter over the defaults', () => {
    // Stored tabs only carry the keys that differ, so a tab that says nothing
    // about the amount must not inherit the live range.
    const { currentFilters, countTabs } = makeFilters();
    currentFilters.amountMin = 999999999;
    const counts = countTabs(list, [{ id: 7, filters: { statuses: ['paid'] } }]);
    expect(counts[7]).toBe(2);
  });

  it('ignores the live filters entirely', () => {
    const { currentFilters, countTabs } = makeFilters();
    currentFilters.statuses = ['pending'];
    const counts = countTabs(list, [{ id: 7, filters: { statuses: ['paid'] } }]);
    expect(counts).toEqual({ all: 3, 7: 2 });
  });
});

describe('resetFilters', () => {
  it('restores defaults and returns to the "all" tab', () => {
    const { currentFilters, activeTabId, resetFilters, activeFilterCount } = makeFilters();
    currentFilters.statuses = ['paid'];
    currentFilters.search = 'acme';
    activeTabId.value = 5;
    resetFilters();
    expect(currentFilters.statuses).toEqual([]);
    expect(currentFilters.search).toBe('');
    expect(activeTabId.value).toBe('all');
    expect(activeFilterCount.value).toBe(0);
  });
});

describe('clearFilterKeys', () => {
  it('resets only the given keys to their defaults', () => {
    const { currentFilters, clearFilterKeys } = makeFilters();
    currentFilters.statuses = ['paid'];
    currentFilters.search = 'acme';
    clearFilterKeys(['statuses']);
    expect(currentFilters.statuses).toEqual([]);
    expect(currentFilters.search).toBe('acme');
  });

  it('ignores keys that are not part of the defaults', () => {
    const { currentFilters, clearFilterKeys } = makeFilters();
    currentFilters.statuses = ['paid'];
    clearFilterKeys(['nope']);
    expect(currentFilters.statuses).toEqual(['paid']);
  });
});

describe('saved tabs delegation', () => {
  it('saveTab delegates to the persistence layer with current filters', async () => {
    const { currentFilters, saveTab } = makeFilters();
    currentFilters.statuses = ['paid'];
    await saveTab('Pagados');
    expect(tabsStub.saveTab).toHaveBeenCalledWith(
      'Pagados',
      expect.objectContaining({ statuses: ['paid'] }),
    );
  });

  it('selectTab loads filters from a saved tab', () => {
    savedTabsRef.value = [
      { id: 9, view: 'accounting_income', name: 'X', filters: { statuses: ['pending'] } },
    ];
    const { currentFilters, activeTabId, selectTab } = makeFilters();
    selectTab(9);
    expect(activeTabId.value).toBe(9);
    expect(currentFilters.statuses).toEqual(['pending']);
  });

  it('deleteTab delegates and resets when the active tab is removed', async () => {
    savedTabsRef.value = [{ id: 7, view: 'accounting_income', name: 'Z', filters: {} }];
    const { deleteTab, activeTabId } = makeFilters();
    activeTabId.value = 7;
    await deleteTab(7);
    expect(tabsStub.deleteTab).toHaveBeenCalledWith(7);
    expect(activeTabId.value).toBe('all');
  });
});

describe('builtin tabs', () => {
  function makeWithBuiltin() {
    return useAccountingFilters({
      viewName: 'accounting_income',
      defaults: DEFAULTS,
      matchers: { statuses: matchIncludes('status', 'statuses') },
      builtinTabs: [
        { id: 'lost', name: 'Perdidos', filters: { statuses: ['lost'] } },
      ],
    });
  }

  it('lists builtin tabs before the saved ones', () => {
    savedTabsRef.value = [
      { id: 3, view: 'accounting_income', name: 'Míos', filters: {} },
    ];
    const { displayTabs } = makeWithBuiltin();
    expect(displayTabs.value.map((t) => t.id)).toEqual(['lost', 3]);
    expect(displayTabs.value[0].builtin).toBe(true);
  });

  it('selectTab applies the builtin filters on top of the defaults', () => {
    const { currentFilters, activeTabId, selectTab } = makeWithBuiltin();
    currentFilters.method = 'transfer';
    selectTab('lost');
    expect(activeTabId.value).toBe('lost');
    expect(currentFilters.statuses).toEqual(['lost']);
    // Unrelated filters are reset like the "Todas" tab does.
    expect(currentFilters.method).toBeNull();
  });

  it('never persists filter edits made under a builtin tab', async () => {
    tabsStub.updateTabFilters.mockClear();
    const { currentFilters, activeTabId, selectTab } = makeWithBuiltin();
    selectTab('lost');
    currentFilters.method = 'cash';
    // Flush the deep watcher.
    const { nextTick } = require('vue');
    await nextTick();
    // The edit stays local: the tab keeps its identity and the filter value,
    // and nothing reaches the persistence layer (builtin tabs have no
    // server-side row to update).
    expect(activeTabId.value).toBe('lost');
    expect(currentFilters.method).toBe('cash');
    expect(tabsStub.updateTabFilters).not.toHaveBeenCalled();
  });
});

describe('orden de la tira con placeholders de builtins', () => {
  function makeWithTwoBuiltins() {
    return useAccountingFilters({
      viewName: 'accounting_income',
      defaults: DEFAULTS,
      matchers: { statuses: matchIncludes('status', 'statuses') },
      builtinTabs: [
        { id: 'lost', name: 'Perdidos', filters: { statuses: ['lost'] } },
        { id: 'no-client', name: 'Sin cliente', filters: { statuses: ['x'] } },
      ],
    });
  }

  it('un builtin toma el orden de su fila placeholder', () => {
    // La fila lleva orden y visibilidad; los filtros siguen siendo los del
    // código, que es lo que impide que un builtin de fecha se congele.
    savedTabsRef.value = [
      { id: 50, view: 'accounting_income', name: 'Míos', filters: {}, order: 0 },
      {
        id: 51, view: 'accounting_income', name: 'Perdidos', filters: {},
        order: 1, builtin_key: 'lost',
      },
    ];
    const { displayTabs } = makeWithTwoBuiltins();

    // 'no-client' no tiene fila todavía: conserva su lugar de código, delante.
    expect(displayTabs.value.map((t) => t.id)).toEqual(['no-client', 50, 'lost']);
    expect(displayTabs.value.find((t) => t.id === 'lost').filters)
      .toEqual({ statuses: ['lost'] });
  });

  it('sin ninguna fila placeholder, los builtins siguen yendo primero', () => {
    savedTabsRef.value = [
      { id: 50, view: 'accounting_income', name: 'Míos', filters: {}, order: 0 },
    ];
    const { displayTabs } = makeWithTwoBuiltins();

    expect(displayTabs.value.map((t) => t.id)).toEqual(['lost', 'no-client', 50]);
  });

  it('una fila placeholder oculta esconde su chip', () => {
    savedTabsRef.value = [
      {
        id: 51, view: 'accounting_income', name: 'Perdidos', filters: {},
        order: 0, builtin_key: 'lost', is_hidden: true,
      },
    ];
    const { displayTabs } = makeWithTwoBuiltins();

    expect(displayTabs.value.find((t) => t.id === 'lost').is_hidden).toBe(true);
  });

  it('descarta la fila de un builtin que ya no existe en el código', () => {
    // Si no, quedaría un chip sin nombre que no filtra nada.
    savedTabsRef.value = [
      {
        id: 52, view: 'accounting_income', name: 'Retirado', filters: {},
        order: 0, builtin_key: 'retirado',
      },
      { id: 50, view: 'accounting_income', name: 'Míos', filters: {}, order: 1 },
    ];
    const { displayTabs } = makeWithTwoBuiltins();

    expect(displayTabs.value.map((t) => t.id)).toEqual(['lost', 'no-client', 50]);
  });
});

describe('default landing tab', () => {
  function makeWithDefaultTab() {
    return useAccountingFilters({
      viewName: 'accounting_income',
      defaults: DEFAULTS,
      matchers: { statuses: matchIncludes('status', 'statuses') },
      searchFields: ['concept', 'client_name'],
      builtinTabs: [
        { id: 'lost', name: 'Perdidos', filters: { statuses: ['lost'] } },
        {
          id: 'hosting',
          name: 'Hosting',
          filters: { statuses: ['pending'], search: 'hosting' },
        },
      ],
      defaultTabId: 'hosting',
    });
  }

  it('applies the default builtin filters before mount', () => {
    const { currentFilters, activeTabId, searchInput } = makeWithDefaultTab();
    expect(activeTabId.value).toBe('hosting');
    expect(currentFilters.statuses).toEqual(['pending']);
    // The search box is seeded from the tab, not left behind by the debounce.
    expect(searchInput.value).toBe('hosting');
  });

  it('lets the query param win over the default tab', () => {
    mockRoute.query = { accounting_incomeTab: 'lost' };
    const { currentFilters, activeTabId } = makeWithDefaultTab();
    expect(activeTabId.value).toBe('lost');
    expect(currentFilters.statuses).toEqual(['lost']);
  });

  it('writes the param when leaving the default tab, including "all"', async () => {
    const { nextTick } = require('vue');
    const { selectTab } = makeWithDefaultTab();
    // Without this the cleared view would silently snap back to the default
    // tab on reload, since an absent param means "use the default".
    selectTab('all');
    await nextTick();
    expect(mockReplace).toHaveBeenCalledWith({
      query: { accounting_incomeTab: 'all' },
    });
  });

  it('drops the param when coming back to the default tab', async () => {
    const { nextTick } = require('vue');
    mockRoute.query = { accounting_incomeTab: 'lost' };
    const { selectTab } = makeWithDefaultTab();
    selectTab('hosting');
    await nextTick();
    expect(mockReplace).toHaveBeenCalledWith({ query: {} });
  });
});

describe('restorable base delegation', () => {
  it('restoreTab reloads currentFilters when the restored tab is active', async () => {
    savedTabsRef.value = [{
      id: 9, view: 'accounting_income', name: 'X',
      filters: { statuses: ['paid'] },
      base_filters: { statuses: ['pending'] },
    }];
    tabsStub.restoreTab.mockResolvedValueOnce({
      id: 9, view: 'accounting_income', name: 'X',
      filters: { statuses: ['pending'] },
      base_filters: { statuses: ['pending'] },
    });
    const { currentFilters, selectTab, restoreTab } = makeFilters();
    selectTab(9);
    expect(currentFilters.statuses).toEqual(['paid']);

    await restoreTab(9);

    expect(tabsStub.restoreTab).toHaveBeenCalledWith(9);
    expect(currentFilters.statuses).toEqual(['pending']);
  });

  it('restoreTab leaves currentFilters alone for an inactive tab', async () => {
    savedTabsRef.value = [{
      id: 9, view: 'accounting_income', name: 'X',
      filters: { statuses: ['paid'] },
      base_filters: { statuses: ['pending'] },
    }];
    tabsStub.restoreTab.mockResolvedValueOnce({
      id: 9, view: 'accounting_income', name: 'X',
      filters: { statuses: ['pending'] },
      base_filters: { statuses: ['pending'] },
    });
    const { currentFilters, restoreTab } = makeFilters();
    currentFilters.statuses = ['paid'];

    await restoreTab(9);

    expect(currentFilters.statuses).toEqual(['paid']);
  });

  it('rebaseTab delegates with the numeric tab id', () => {
    const { rebaseTab } = makeFilters();

    rebaseTab('7');

    expect(tabsStub.rebaseTab).toHaveBeenCalledWith(7);
  });
});

// ── Params de deep link ──────────────────────────────────────────────────────
// Se leían sueltos en el `onMounted` de cada página y no los borraba nadie:
// como el watcher del tab clona el query entero, cada `replace` posterior los
// arrastraba, así que limpiar los filtros dejaba la URL diciendo `?project=5`
// con el filtro apagado y el F5 siguiente lo resucitaba.

describe('seeded query params', () => {
  function seeded(query, ephemeralParams = ['project', 'focus']) {
    mockRoute.query = query;
    return useAccountingFilters({ viewName: 'accounting_income', ephemeralParams });
  }

  function mountSeeded(query, ephemeralParams = ['project', 'focus']) {
    mockRoute.query = query;
    return mount(defineComponent({
      setup() {
        useAccountingFilters({ viewName: 'accounting_income', ephemeralParams });
        return () => null;
      },
    }));
  }

  it('hands the page the value the view was seeded with', () => {
    const { consumeParam } = seeded({ project: '5' });

    expect(consumeParam('project')).toBe('5');
    expect(consumeParam('focus')).toBeUndefined();
  });

  it('survives the param leaving the url', () => {
    // El valor se captura en el setup, así el orden en que la página lo consuma
    // (a veces detrás de varios await) deja de importar.
    const { consumeParam } = seeded({ project: '5' });

    mockRoute.query = {};

    expect(consumeParam('project')).toBe('5');
  });

  it('ignores a param the view did not declare', () => {
    const { consumeParam } = seeded({ client: '7' }, ['project']);

    expect(consumeParam('client')).toBeUndefined();
  });

  it('takes the param out of the url once the view is mounted', () => {
    mountSeeded({ project: '5', focus: '9', accounting_incomeTab: 'all' });

    expect(mockReplace).toHaveBeenCalledWith({ query: { accounting_incomeTab: 'all' } });
  });

  it('leaves the url alone when the view was not seeded', () => {
    mountSeeded({ accounting_incomeTab: 'all' });

    expect(mockReplace).not.toHaveBeenCalled();
    // Y el param que sí describe la vista sigue en pie.
    expect(mockRoute.query).toEqual({ accounting_incomeTab: 'all' });
  });

  it('keeps a filter-seeding param while its filter is still on', async () => {
    // Mientras el filtro esté puesto el param SÍ describe la vista, y es lo que
    // sostiene el deep link a través de un F5: retirarlo ahí sería el defecto
    // contrario, una URL que se calla un filtro activo.
    let filters;
    mockRoute.query = { project: '5' };
    mount(defineComponent({
      setup() {
        filters = useAccountingFilters({
          viewName: 'accounting_income',
          defaults: { projects: [] },
          ephemeralParams: [{ name: 'project', boundTo: 'projects' }],
        });
        filters.currentFilters.projects = [5];
        return () => null;
      },
    }));
    await nextTick();

    expect(mockReplace).not.toHaveBeenCalled();

    // Y se va en cuanto el filtro se limpia — que es lo que nunca pasaba.
    filters.currentFilters.projects = [];
    await nextTick();

    expect(mockReplace).toHaveBeenCalledWith({ query: {} });
  });
});

describe('filters in the URL', () => {
  const { nextTick } = require('vue');

  function makeSyncedFilters(overrides = {}) {
    return useAccountingFilters({
      viewName: 'accounting_history_sends',
      tabQueryParam: 'sendsTab',
      defaults: { status: [], recipient: '' },
      matchers: {},
      syncFiltersToUrl: true,
      ...overrides,
    });
  }

  it('stays off by default, so the other views only carry their tab', async () => {
    const { currentFilters, saveTab } = makeFilters();
    currentFilters.statuses = ['paid'];

    await saveTab('Cobrados');
    await nextTick();

    // The tab still reaches the URL — the machinery runs — but the filters
    // do not, which is what keeps the other eleven views byte-identical.
    expect(mockReplace).toHaveBeenLastCalledWith({
      query: { accounting_incomeTab: '1' },
    });
  });

  it('writes the active filters, leaving the untouched ones out', async () => {
    const { currentFilters } = makeSyncedFilters();

    currentFilters.status = ['failed', 'bounced'];
    await nextTick();

    expect(mockReplace).toHaveBeenCalledWith({
      query: { status: 'failed,bounced' },
    });
  });

  it('drops a filter from the URL once it goes back to its default', async () => {
    const { currentFilters } = makeSyncedFilters();
    currentFilters.recipient = 'ana@test.com';
    await nextTick();

    currentFilters.recipient = '';
    await nextTick();

    expect(mockReplace).toHaveBeenLastCalledWith({ query: {} });
  });

  it('seeds itself from a shared link before the first fetch', () => {
    mockRoute.query = { status: 'failed,bounced', recipient: 'ana@test.com' };

    const { currentFilters } = makeSyncedFilters();

    expect(currentFilters.status).toEqual(['failed', 'bounced']);
    expect(currentFilters.recipient).toBe('ana@test.com');
  });

  it('ignores the query while another instance owns it', () => {
    mockRoute.query = { status: 'failed' };

    const { currentFilters } = makeSyncedFilters({ isUrlOwner: () => false });

    expect(currentFilters.status).toEqual([]);
  });

  it('clears the keys the other subtab left behind before writing', async () => {
    mockRoute.query = { actor: 'gustavo', tab: 'sends' };
    const { currentFilters } = makeSyncedFilters({
      urlFilterKeys: ['status', 'recipient', 'actor'],
    });

    currentFilters.status = ['failed'];
    await nextTick();

    expect(mockReplace).toHaveBeenLastCalledWith({
      query: { tab: 'sends', status: 'failed' },
    });
  });

  it('writes tab and filters in a single replace', async () => {
    const { currentFilters, selectTab } = makeSyncedFilters();

    currentFilters.status = ['failed'];
    await nextTick();
    mockReplace.mockClear();

    selectTab('all');
    await nextTick();

    // selectTab resets the filters, so both watchers fire in the same tick.
    expect(mockReplace).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith({ query: {} });
  });
});

describe('multi-value filter helpers', () => {
  describe('matchBooleanIncludes', () => {
    const match = matchBooleanIncludes('reminders_muted', 'muted');

    it('is inactive with an empty selection', () => {
      expect(match({ reminders_muted: true }, null, { muted: [] })).toBe(true);
    });

    it('cuts by one token', () => {
      expect(match({ reminders_muted: true }, null, { muted: ['true'] })).toBe(true);
      expect(match({ reminders_muted: false }, null, { muted: ['true'] })).toBe(false);
    });

    it('marking both tokens is the same as no cut', () => {
      const both = { muted: ['true', 'false'] };
      expect(match({ reminders_muted: true }, null, both)).toBe(true);
      expect(match({ reminders_muted: false }, null, both)).toBe(true);
    });
  });

  describe('matchAnyToken', () => {
    const match = matchAnyToken('partner', {
      gustavo: (r) => Number(r.gustavo_amount) > 0,
      carlos: (r) => Number(r.carlos_amount) > 0,
    });

    it('unions the tokens instead of answering for the first one', () => {
      const filters = { partner: ['gustavo', 'carlos'] };
      expect(match({ gustavo_amount: 10, carlos_amount: 0 }, null, filters)).toBe(true);
      expect(match({ gustavo_amount: 0, carlos_amount: 10 }, null, filters)).toBe(true);
      expect(match({ gustavo_amount: 0, carlos_amount: 0 }, null, filters)).toBe(false);
    });

    it('counts a record once when several tokens hold at the same time', () => {
      // Overlapping tokens are the point (an overdue account is also issued):
      // the predicate answers yes, it does not answer twice.
      const record = { gustavo_amount: 10, carlos_amount: 10 };
      expect(match(record, null, { partner: ['gustavo', 'carlos'] })).toBe(true);
    });

    it('does not widen the cut on an unknown token', () => {
      expect(match({ gustavo_amount: 10 }, null, { partner: ['nadie'] })).toBe(false);
    });
  });

  describe('coerceToDefaultShape', () => {
    const defaults = { kind: [], search: '', amountMin: '' };

    it('wraps a scalar saved before the dimension went multi-valued', () => {
      expect(coerceToDefaultShape({ kind: 'expected' }, defaults).kind)
        .toEqual(['expected']);
    });

    it('reads an empty scalar as no cut, not as a cut on ""', () => {
      expect(coerceToDefaultShape({ kind: '' }, defaults).kind).toEqual([]);
    });

    it('leaves arrays and unrelated keys alone', () => {
      const out = coerceToDefaultShape(
        { kind: ['liquid'], search: 'kore', amountMin: '10' }, defaults,
      );
      expect(out).toEqual({ kind: ['liquid'], search: 'kore', amountMin: '10' });
    });

    it('unwraps an array back to a scalar if a key ever moves back', () => {
      expect(coerceToDefaultShape({ search: ['kore'] }, defaults).search).toBe('kore');
    });

    it('does not invent keys the stored dict never had', () => {
      expect('kind' in coerceToDefaultShape({ search: 'x' }, defaults)).toBe(false);
    });
  });
});

describe('accounting detail query restoration', () => {
  function mountWithQuery(query) {
    mockRoute.query = query;
    let filters;
    const wrapper = mount(defineComponent({
      setup() {
        filters = useAccountingFilters({
          viewName: 'accounting_test',
          defaults: { category: [], clients: [], projects: [], origin_card: [], status: [], totalMin: '' },
          builtinTabs: [{ id: 'preset', name: 'Pendientes', filters: { status: ['issued'], category: [5] } }],
          ephemeralParams: [{ name: 'client', boundTo: 'clients' }, 'focus'],
          syncFiltersToUrl: true,
          restoreUrlState: true,
          urlFilterCodecs: { category: numericFilterIds, clients: optionalFilterIds,
            projects: collectionProjectFilter, origin_card: repeatedFilterText },
        });
        return () => null;
      },
    }));
    return { filters, wrapper };
  }

  it('round-trips filter values with distinct types or commas', async () => {
    const query = {
      category: '2,3', clients: '12,none', projects: '[12,"12","Web, fase 2"]',
      origin_card: ['Visa, empresa', 'Mastercard'], account: '1',
    };
    const { filters, wrapper } = mountWithQuery(query);
    await filters.whenFiltersReady();

    expect(filters.currentFilters).toMatchObject({
      category: [2, 3], clients: [12, 'none'], projects: [12, '12', 'Web, fase 2'],
      origin_card: ['Visa, empresa', 'Mastercard'],
    });
    expect(filters.buildFilterQuery()).toEqual(query);
    wrapper.unmount();
  });

  it('keeps valid filters while malformed values fall back', async () => {
    const { filters, wrapper } = mountWithQuery({
      accounting_testTab: 'preset', category: 'x', clients: '0,7', client: '12',
      projects: '[false]', totalMin: '125000',
    });
    await filters.whenFiltersReady();

    expect(filters.currentFilters).toMatchObject({
      category: [5], clients: [12], projects: [], status: ['issued'], totalMin: '125000',
    });
    wrapper.unmount();
  });

  it('keeps an explicitly cleared filter above a legacy link', async () => {
    const { filters, wrapper } = mountWithQuery({
      accounting_testTab: 'preset', status: '', client: '12', clients: '', account: '1', focus: '1',
    });
    await filters.whenFiltersReady();

    expect(filters.currentFilters).toMatchObject({ status: [], clients: [] });
    expect(filters.buildFilterQuery()).toMatchObject({ status: '', clients: '', account: '1' });
    expect(filters.buildFilterQuery()).not.toHaveProperty('client');
    expect(filters.buildFilterQuery()).not.toHaveProperty('focus');
    wrapper.unmount();
  });

  it('describes the empty cut after removing a built-in filter', async () => {
    const { filters, wrapper } = mountWithQuery({ accounting_testTab: 'preset', movement: '10' });
    await filters.whenFiltersReady();

    filters.clearFilterKeys(['status']);
    await nextTick();

    expect(filters.buildFilterQuery()).toMatchObject({ status: '', movement: '10' });
    wrapper.unmount();
  });

  it('waits for the saved preset before publishing the first query', async () => {
    let resolve;
    tabsStub.loadTabs.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    tabsStub.updateTabFilters.mockClear();
    const { filters, wrapper } = mountWithQuery({ accounting_testTab: '7', totalMin: '', account: '1' });
    const ready = filters.whenFiltersReady();
    expect(filters.filterQueryReady.value).toBe(false);
    savedTabsRef.value = [{ id: 7, name: 'Corte', filters: { totalMin: '125000', status: ['issued'] } }];

    resolve();
    await ready;

    expect(filters.currentFilters).toMatchObject({ totalMin: '', status: ['issued'] });
    expect(tabsStub.updateTabFilters).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('restores another browser entry without saving it as a preset', async () => {
    const { filters, wrapper } = mountWithQuery({ accounting_testTab: 'preset', status: '', account: '1' });
    await filters.whenFiltersReady();

    mockRoute.query = { accounting_testTab: 'preset', category: '8' };
    await flushPromises();

    expect(filters.currentFilters).toMatchObject({ category: [8], status: ['issued'] });
    wrapper.unmount();
  });
});
