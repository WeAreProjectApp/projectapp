import { computed, getCurrentScope, nextTick, onMounted, onScopeDispose, reactive, ref, toRaw, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useSavedFilterTabs } from '~/composables/useSavedFilterTabs';
import { queryId } from '~/utils/accountingFilterQuery';

/**
 * Generalization of useClientFilters into a factory reusable by the
 * accounting subviews (incomes, expenses, hostings, pocket, recurring, ads).
 *
 * Filtering is declarative: `matchers` maps a filter key to a predicate
 * `(record, filterValue, allFilters) => boolean` that only runs when the
 * corresponding filter value differs from its default. Range matchers built
 * with the exported helpers attach a `.keys` list so a single matcher entry
 * (e.g. `amountRange`) activates when either bound key (min/max) is set and
 * counts once in `activeFilterCount`.
 *
 * Saved tabs degrade gracefully: `useSavedFilterTabs` traps HTTP errors
 * internally (exposed via `lastError`), and the mount-time load is wrapped
 * so a failing tabs API never breaks the page's local filtering.
 */

function normalizeScalar(value) {
  return value === '' || value === undefined ? null : value;
}

function isValueActive(value, defaultValue) {
  if (Array.isArray(value)) {
    const def = Array.isArray(defaultValue) ? defaultValue : [];
    if (value.length !== def.length) return value.length > 0 || def.length > 0;
    return JSON.stringify(value) !== JSON.stringify(def);
  }
  return normalizeScalar(value) !== normalizeScalar(defaultValue);
}

function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

// ---------------------------------------------------------------------------
// Prebuilt matcher helpers
// ---------------------------------------------------------------------------

/** Inclusive date range; the max bound extends to end-of-day (23:59:59.999). */
export function matchDateRange(field, minKey, maxKey) {
  const fn = (record, _value, filters) => {
    const min = filters[minKey];
    const max = filters[maxKey];
    if (!min && !max) return true;
    if (!record[field]) return false;
    const d = new Date(record[field]);
    if (Number.isNaN(d.getTime())) return false;
    if (min && d < new Date(min)) return false;
    if (max) {
      const end = new Date(max);
      end.setHours(23, 59, 59, 999);
      if (d > end) return false;
    }
    return true;
  };
  fn.keys = [minKey, maxKey];
  return fn;
}

/** Inclusive numeric range over a record field (numbers or numeric strings). */
export function matchNumberRange(field, minKey, maxKey) {
  const fn = (record, _value, filters) => {
    const min = normalizeScalar(filters[minKey]);
    const max = normalizeScalar(filters[maxKey]);
    if (min === null && max === null) return true;
    const n = toNumber(record[field]);
    if (min !== null && n < Number(min)) return false;
    if (max !== null && n > Number(max)) return false;
    return true;
  };
  fn.keys = [minKey, maxKey];
  return fn;
}

/**
 * Multi-select: record field (scalar or array) intersects the selected array.
 *
 * `nullAs` maps a null/undefined field onto a sentinel token, so a multi-select
 * can offer an "unassigned" option using the same vocabulary the server does
 * (the pocket's `attribution` is null on movements that mirror nothing).
 */
export function matchIncludes(field, key, { nullAs = null } = {}) {
  const fn = (record, _value, filters) => {
    const selected = filters[key];
    if (!Array.isArray(selected) || selected.length === 0) return true;
    const recordValue = record[field];
    if (Array.isArray(recordValue)) return recordValue.some((v) => selected.includes(v));
    if (nullAs !== null && (recordValue === null || recordValue === undefined)) {
      return selected.includes(nullAs);
    }
    return selected.includes(recordValue);
  };
  fn.keys = [key];
  return fn;
}

/** Strict equality against a single-value filter (null/'' means inactive). */
export function matchEquals(field, key) {
  const fn = (record, _value, filters) => {
    const selected = normalizeScalar(filters[key]);
    if (selected === null) return true;
    return record[field] === selected;
  };
  fn.keys = [key];
  return fn;
}

/** Tri-state boolean: '' matches all, 'true'/'false' match the boolean field. */
export function matchBoolean(field, key) {
  const fn = (record, _value, filters) => {
    const selected = filters[key];
    if (selected === '' || selected === null || selected === undefined) return true;
    return record[field] === (selected === 'true');
  };
  fn.keys = [key];
  return fn;
}

/**
 * Multi-value twin of `matchBoolean`: the selection is an array of the same
 * 'true'/'false' tokens. Marking both degenerates to "no cut", which is the
 * honest reading — a two-option dimension with everything checked is "Todos".
 */
export function matchBooleanIncludes(field, key) {
  const fn = (record, _value, filters) => {
    const selected = filters[key];
    if (!Array.isArray(selected) || selected.length === 0) return true;
    return selected.includes(record[field] === true ? 'true' : 'false');
  };
  fn.keys = [key];
  return fn;
}

/**
 * Multi-value matcher for a DERIVED dimension: one predicate per token, OR'd.
 *
 * The dimensions that go through here (`partner`, the expense `nature`, the
 * collection `status`) are not columns — they are read off several fields at
 * once, and some of their tokens OVERLAP (an overdue account is also issued).
 * A set union is therefore the only correct reading; an if/elif chain would
 * silently return just the first match.
 */
export function matchAnyToken(key, predicates) {
  const fn = (record, _value, filters) => {
    const selected = filters[key];
    if (!Array.isArray(selected) || selected.length === 0) return true;
    return selected.some((token) => {
      const predicate = predicates[token];
      // An unknown token must not silently widen the cut to everything.
      return typeof predicate === 'function' ? predicate(record) : false;
    });
  };
  fn.keys = [key];
  return fn;
}

/**
 * Same union as `matchAnyToken`, for a dimension whose tokens are already
 * served by one `(record, token) => boolean` function. Lets a scalar matcher
 * that predates multi-select keep its single definition instead of being
 * copied into a per-token dict.
 */
export function matchAnyValue(key, predicate) {
  const fn = (record, _value, filters) => {
    const selected = filters[key];
    if (!Array.isArray(selected) || selected.length === 0) return true;
    return selected.some((token) => predicate(record, token));
  };
  fn.keys = [key];
  return fn;
}

/**
 * Reconcile a stored filter dict with the shape its view expects today.
 *
 * Saved tabs are free-form JSON with no server-side validation, so rows written
 * before a dimension became multi-value still hold `kind: 'expected'` where the
 * matcher now wants `['expected']`. Loading one unconverted does not throw — it
 * filters NOTHING, silently, which is the exact failure this whole feature
 * exists to remove. The scalar branch is kept too so a rollback survives.
 */
export function coerceToDefaultShape(stored, defaults) {
  const out = { ...stored };
  for (const [key, fallback] of Object.entries(defaults)) {
    if (!(key in out)) continue;
    const value = out[key];
    if (Array.isArray(fallback) && !Array.isArray(value)) {
      out[key] = value === '' || value === null || value === undefined ? [] : [value];
    } else if (!Array.isArray(fallback) && Array.isArray(value)) {
      out[key] = value.length ? value[0] : '';
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export function useAccountingFilters({
  viewName,
  defaults = {},
  matchers = {},
  searchFields = [],
  // Fixed quick-filter tabs rendered before the saved ones. Items are
  // `{ id, name, filters }` with non-numeric string ids ('lost'); they are
  // never persisted server-side and cannot be renamed or deleted.
  builtinTabs = [],
  // Tab the view lands on with no `?<viewName>Tab` in the URL. Only 'all' or a
  // builtin id make sense here: saved-tab ids are per-user database rows.
  defaultTabId = 'all',
  // Deep-link params this view is seeded with once (`project`, `client`,
  // `focus`). See `consumeParam`.
  ephemeralParams = [],
  // Query param carrying the active tab. Defaults to `<viewName>Tab`; views
  // whose name is long enough to make an ugly URL can shorten it.
  tabQueryParam = `${viewName}Tab`,
  // Put the active filters in the URL too, not just the tab, so a query can
  // be bookmarked and shared. Off by default: the views that filter in the
  // browser already restore their state from the tab alone.
  syncFiltersToUrl = false,
  // Restore the whole query, including explicit clears and legacy seeds, before
  // the listing loads. Existing syncFiltersToUrl clients keep their own policy.
  restoreUrlState = false,
  urlFilterCodecs = {},
  // With two instances on one page (Historial's two subtabs), only the one on
  // screen owns the query string — otherwise both would write the keys they
  // share and overwrite each other.
  isUrlOwner = () => true,
  // Keys to clear before writing. Defaults to this instance's own; a page
  // with several instances passes the union so switching between them cannot
  // leave the previous one's filters behind.
  urlFilterKeys = null,
  // Opt-in second level. When set, it names the filter key holding the active
  // module and `displayTabs` only lists the tabs belonging to it, so a view can
  // group its quick filters instead of laying them out flat. Views that leave
  // it null behave exactly as before.
  moduleKey = null,
  defaultModule = 'all',
  // Query param carrying the active module, same shortening rationale as
  // `tabQueryParam`.
  moduleQueryParam = `${viewName}Module`,
  // Optional migration hook applied to a stored tab's filters before they are
  // loaded, for keys whose shape changed after the tab was saved.
  normalizeFilters = null,
} = {}) {
  const route = useRoute();
  const router = useRouter();

  const DEFAULT_FILTERS = Object.freeze({ search: '', ...structuredClone(defaults) });
  const queryKeys = urlFilterKeys || Object.keys(DEFAULT_FILTERS);
  const restoreQuery = syncFiltersToUrl && restoreUrlState;
  const filterQueryReady = ref(!restoreQuery);
  const clearedUrlKeys = new Set();
  let applyingQuery = false;
  let scopeActive = true;
  let queryGeneration = 0;
  let tabLoad;
  let initialQuery;

  // ── Params de deep link ────────────────────────────────────────────────────
  // Se leían sueltos con `route.query.x` en el `onMounted` de cada página y no
  // los borraba nadie. Como el watcher del tab clona el query entero, cada
  // `replace` posterior los volvía a arrastrar: limpiar los filtros dejaba la
  // URL diciendo `?project=5` con el filtro ya apagado, y el F5 siguiente lo
  // resucitaba. Un param que sobrevive a su contexto es estado oculto.
  //
  // El valor se captura AQUÍ, en el setup, antes de que nada pueda retirarlo,
  // así el orden en que la página lo consuma deja de importar.
  const ephemeral = ephemeralParams.map(
    (param) => (typeof param === 'string' ? { name: param } : param),
  );

  const seededQuery = Object.freeze(Object.fromEntries(
    ephemeral.map(({ name }) => [name, route?.query?.[name]]),
  ));

  /** Valor con el que se sembró la vista, o undefined si no venía en la URL. */
  function consumeParam(name) {
    return seededQuery[name];
  }

  function dropParams(names) {
    if (!route || !router || !names.length) return;
    const present = names.filter((name) => route.query?.[name] !== undefined);
    if (!present.length) return;
    const query = { ...route.query };
    present.forEach((name) => delete query[name]);
    router.replace({ query });
  }

  function freshFilters() {
    return structuredClone(DEFAULT_FILTERS);
  }

  /**
   * Defaults for "clear everything" and for stepping off a tab. The module is
   * carried over: it selects an angle, it is not one of the cuts being
   * cleared, so dropping the filters must not also walk the user back to the
   * first module.
   */
  function freshFiltersKeepingModule(from) {
    const fresh = freshFilters();
    if (moduleKey) fresh[moduleKey] = from[moduleKey];
    return fresh;
  }

  function cloneFilters(filters) {
    return structuredClone(toRaw(filters));
  }

  /**
   * Stored filters -> live filters, in two steps that must stay in this order:
   * the per-view `normalizeFilters` hook renames keys whose MEANING changed,
   * then the shape pass fixes keys whose TYPE changed (scalar -> array). The
   * hook runs first so it can keep emitting the shape it always emitted.
   */
  function readStoredFilters(filters) {
    const stored = cloneFilters(filters || {});
    const renamed = normalizeFilters ? normalizeFilters(stored) : stored;
    return coerceToDefaultShape(renamed, DEFAULT_FILTERS);
  }

  function loadTabFilters(target, tab) {
    Object.assign(target, freshFilters(), readStoredFilters(tab.filters));
  }

  /** Read this instance's filters out of the query string. */
  function filtersFromQuery(query) {
    const parsed = {};
    for (const [key, fallback] of Object.entries(DEFAULT_FILTERS)) {
      const raw = query?.[key];
      if (restoreQuery && raw === '') {
        parsed[key] = structuredClone(fallback);
        continue;
      }
      const codec = restoreQuery ? urlFilterCodecs[key] : undefined;
      const single = Array.isArray(raw) ? raw[0] : raw;
      if (single === undefined || single === null || single === '') continue;
      const value = codec ? codec.read(raw) : Array.isArray(fallback)
        ? String(single).split(',').filter(Boolean)
        : String(single);
      if (value !== undefined) parsed[key] = value;
    }
    return parsed;
  }

  /** Serialize the active filters, arrays joined like the export params. */
  function filtersToQuery() {
    const serialized = {};
    for (const [key, fallback] of Object.entries(DEFAULT_FILTERS)) {
      const value = currentFilters[key];
      if (!isValueActive(value, fallback)) {
        if (restoreQuery && clearedUrlKeys.has(key)) serialized[key] = '';
        continue;
      }
      const codec = restoreQuery ? urlFilterCodecs[key] : undefined;
      serialized[key] = codec ? codec.write(value) : Array.isArray(value) ? value.join(',') : String(value);
    }
    return serialized;
  }

  const builtinById = new Map(builtinTabs.map((t) => [String(t.id), t]));
  const initialTab = route?.query?.[tabQueryParam] || defaultTabId;
  const activeTabId = ref(initialTab);

  const currentFilters = reactive(freshFilters());
  // A builtin landing tab needs no server round-trip, so its filters are
  // applied here rather than on mount: waiting would flash an unfiltered list
  // and leave the search box out of sync with the tab it belongs to.
  if (builtinById.has(String(initialTab))) {
    loadTabFilters(currentFilters, builtinById.get(String(initialTab)));
  }
  // Same reason, for a shared link: the filters have to be in place before
  // the page's first fetch, not after it.
  if (syncFiltersToUrl && isUrlOwner()) {
    if (restoreQuery) Object.assign(currentFilters, filtersFromLegacyQuery(route?.query));
    Object.assign(currentFilters, filtersFromQuery(route?.query));
  }
  // Read after the landing tab, which stamps its own module: an explicit
  // ?<view>Module in the URL is the more specific instruction and wins.
  if (moduleKey && route?.query?.[moduleQueryParam]) {
    currentFilters[moduleKey] = String(route.query[moduleQueryParam]);
  }
  const isFilterPanelOpen = ref(false);

  // Un param que dispara una acción de una sola vez (destacar una fila) agota
  // su contexto al montar: dejarlo puesto re-enciende el destello en cada F5.
  onMounted(() => {
    if (!restoreQuery) dropParams(ephemeral.filter((p) => !p.boundTo).map((p) => p.name));
  });

  // El que siembra un FILTRO se queda mientras ese filtro siga puesto — ahí el
  // param sí describe la vista y sostiene el deep link a través de un F5. Se va
  // en cuanto el filtro cambia o se limpia, que es lo que antes no pasaba
  // nunca: la URL seguía prometiendo un filtro ya apagado.
  ephemeral.filter((p) => p.boundTo).forEach(({ name, boundTo }) => {
    if (restoreQuery || seededQuery[name] === undefined) return;
    watch(() => currentFilters[boundTo], (value) => {
      const stillSeeded = Array.isArray(value)
        && value.length === 1
        && String(value[0]) === String(seededQuery[name]);
      if (!stillSeeded) dropParams([name]);
    }, { deep: true });
  });

  const tabs = useSavedFilterTabs(viewName);
  const { savedTabs, isLoading, isReady, lastError, isTabLimitReached } = tabs;

  // Tabs carry their module inside their filters, so a saved one is grouped by
  // whatever module was active when it was saved. Anything without a module —
  // every tab of every other view — belongs to the default one.
  function moduleOf(tab) {
    return String(tab.module ?? tab.filters?.[moduleKey] ?? defaultModule);
  }

  const activeModule = computed(() =>
    (moduleKey ? String(currentFilters[moduleKey] ?? defaultModule) : defaultModule),
  );

  /**
   * The server's placeholder row for a builtin, keyed by `builtin_key`.
   *
   * A placeholder carries the user's `order` and `is_hidden` for a quick
   * filter whose definition lives here in code — that is the whole point, so
   * a date-based builtin like "Hoy" cannot freeze on a stored `date_from`.
   */
  const placeholderByKey = computed(() => new Map(
    savedTabs.value
      .filter((tab) => tab.builtin_key)
      .map((tab) => [String(tab.builtin_key), tab]),
  ));

  // Builtins with no placeholder yet (the row is seeded on the first GET, and
  // a view may have been dropped from the backend registry) sort ahead of
  // everything: negative slots reproduce exactly the old "builtins first,
  // then the saved ones" layout while nothing has been moved.
  const UNPLACED_BUILTIN_BASE = -1000;

  // `filters` travels with the builtins too: a view that badges its tabs has
  // to be able to ask the server what each one is worth, and a builtin with
  // no definition attached would be counted as if it filtered nothing.
  const displayTabs = computed(() => {
    const placeholders = placeholderByKey.value;
    const all = [
      ...builtinTabs.map((t, index) => {
        const row = placeholders.get(String(t.id));
        return {
          id: t.id,
          name: t.name,
          filters: t.filters || {},
          module: t.module,
          builtin: true,
          // The row contributes order and visibility and nothing else: its
          // `filters` are empty by design and must never shadow these.
          order: row ? row.order : UNPLACED_BUILTIN_BASE + index,
          is_hidden: row ? row.is_hidden : false,
        };
      }),
      // A placeholder whose constant is gone (builtin retired from the code)
      // would render as a nameless chip that filters nothing — drop it.
      ...savedTabs.value.filter((tab) => !tab.builtin_key),
    ];
    all.sort((a, b) => (a.order || 0) - (b.order || 0));
    if (!moduleKey) return all;
    return all.filter((tab) => moduleOf(tab) === activeModule.value);
  });

  /**
   * Persist the strip's order after a drag, a menu move or a keyboard move.
   *
   * The strip only ever names what it shows — hidden tabs and, in a two-level
   * view, the other modules stay out of the list. Weaving that back into the
   * full order is `useSavedFilterTabs.reorderTabs`'s job; builtins travel by
   * their string id and are matched to their placeholder row there.
   */
  const reorderTabs = tabs.reorderTabs;

  /**
   * Switching module never clears what is already applied: the panel and the
   * active-filter chips keep showing it, so nothing goes invisible, and cuts
   * from different modules stay combinable. A tab selected in another module
   * simply drops out of `displayTabs` and lights up again on the way back.
   */
  function selectModule(moduleId) {
    if (!moduleKey) return;
    currentFilters[moduleKey] = String(moduleId);
  }

  // Debounced free-text search: pages bind their search box to
  // `searchInput`; the actual `currentFilters.search` value (which drives
  // applyFilters) follows 250ms after the user stops typing. External
  // changes (tab selection, reset) sync back into the input immediately.
  const searchInput = ref(currentFilters.search);
  let searchTimer = null;

  watch(searchInput, (value) => {
    if (searchTimer) clearTimeout(searchTimer);
    if (value === currentFilters.search) return;
    searchTimer = setTimeout(() => {
      currentFilters.search = value;
    }, 250);
  });

  watch(
    () => currentFilters.search,
    (value) => {
      if (value !== searchInput.value) searchInput.value = value;
    },
  );

  if (getCurrentScope()) {
    onScopeDispose(() => {
      scopeActive = false;
      queryGeneration += 1;
      if (searchTimer) clearTimeout(searchTimer);
    });
  }

  function numericTabId(value) {
    return typeof value === 'number' ? value : Number(value);
  }

  function filtersFromLegacyQuery(query) {
    const filters = {};
    for (const { name, boundTo } of ephemeral) {
      const id = boundTo && queryId(query?.[name]);
      if (id) filters[boundTo] = [id];
    }
    return filters;
  }

  function tabById(id) {
    return builtinById.get(String(id)) || savedTabs.value.find((tab) => String(tab.id) === String(id));
  }

  async function applyQuery(query) {
    const generation = ++queryGeneration;
    const tabId = query[tabQueryParam] || defaultTabId;
    if (queryId(String(tabId))) await tabLoad;
    if (!scopeActive || generation !== queryGeneration || !isUrlOwner()) return;

    const tab = tabById(tabId);
    const explicit = filtersFromQuery(query);
    applyingQuery = true;
    clearedUrlKeys.clear();
    for (const [key, value] of Object.entries(explicit)) {
      if (!isValueActive(value, DEFAULT_FILTERS[key])) clearedUrlKeys.add(key);
    }
    const legacy = filtersFromLegacyQuery(query);
    Object.assign(currentFilters, freshFilters(), readStoredFilters(tab?.filters), legacy, explicit);
    activeTabId.value = tab?.id ?? defaultTabId;
    if (searchTimer) clearTimeout(searchTimer);
    searchInput.value = currentFilters.search;
    if (Object.keys(explicit).length || Object.keys(legacy).length
      || (tab && !builtinById.has(String(tab.id)))) isFilterPanelOpen.value = true;
    await nextTick();
    if (generation === queryGeneration) applyingQuery = false;
  }

  function whenFiltersReady() {
    if (!restoreQuery) return Promise.resolve(true);
    initialQuery ??= (async () => {
      tabLoad = tabs.loadTabs().catch(() => []);
      let query;
      do {
        query = route?.query;
        await applyQuery(query || {});
      } while (scopeActive && query !== route?.query);

      if (!scopeActive) return false;
      filterQueryReady.value = true;
      syncUrl();
      return true;
    })();
    return initialQuery;
  }

  function rememberClearedFilters() {
    const inherited = {
      ...readStoredFilters(tabById(activeTabId.value)?.filters),
      ...filtersFromLegacyQuery(route?.query),
    };
    for (const [key, inheritedValue] of Object.entries(inherited)) {
      if (key in DEFAULT_FILTERS && isValueActive(inheritedValue, DEFAULT_FILTERS[key])
        && !isValueActive(currentFilters[key], DEFAULT_FILTERS[key])) clearedUrlKeys.add(key);
    }
    for (const key of clearedUrlKeys) {
      if (isValueActive(currentFilters[key], DEFAULT_FILTERS[key])) clearedUrlKeys.delete(key);
    }
  }

  /**
   * Write tab, module and filters in one `router.replace`.
   *
   * One writer on purpose: two watchers each replacing the query would race,
   * and whichever landed second would drop the other's keys. Selecting a
   * subfilter moves the tab AND the module at once, so they have to share it.
   *
   * The tab param is written for every tab that is NOT the landing one —
   * including 'all'. Omitting it there would make a reload of the cleared
   * view snap back to the default tab. The module param follows the same rule.
   */
  function buildFilterQuery(base = route?.query) {
    const query = { ...base };
    if (String(activeTabId.value) === String(defaultTabId)) {
      delete query[tabQueryParam];
    } else {
      query[tabQueryParam] = String(activeTabId.value);
    }
    if (syncFiltersToUrl && isUrlOwner()) {
      for (const key of queryKeys) delete query[key];
      Object.assign(query, filtersToQuery());
    }
    if (moduleKey) {
      if (String(activeModule.value) === String(defaultModule)) {
        delete query[moduleQueryParam];
      } else {
        query[moduleQueryParam] = String(activeModule.value);
      }
    }
    if (restoreQuery && isUrlOwner()) {
      for (const { name, boundTo } of ephemeral) {
        if (!(name in query)) continue;
        const id = boundTo && queryId(query[name]);
        const values = boundTo && currentFilters[boundTo];
        if (id && values?.length === 1 && values[0] === id) {
          // Retain the existing link shape when the singular key already
          // describes the selection.
          delete query[boundTo];
        } else {
          delete query[name];
        }
      }
    }
    return query;
  }

  const ownedKeys = [tabQueryParam, ...queryKeys, ...ephemeral.map(({ name }) => name)];
  const querySignature = (query) => JSON.stringify(ownedKeys.map((key) => query?.[key]));
  function syncUrl() {
    if (!scopeActive || !route || !router) return;
    if (restoreQuery && (applyingQuery || !filterQueryReady.value || !isUrlOwner())) return;
    const query = buildFilterQuery();
    if (restoreQuery && querySignature(query) === querySignature(route.query)) return;
    router.replace({ query });
  }

  if (restoreQuery) {
    watch(() => querySignature(route?.query), async (signature) => {
      if (!filterQueryReady.value || !isUrlOwner() || signature === querySignature(buildFilterQuery())) return;
      await applyQuery(route.query);
      syncUrl();
    });
  }

  watch(activeTabId, syncUrl);
  watch(activeModule, syncUrl);

  watch(
    currentFilters,
    () => {
      if (restoreQuery) {
        if (applyingQuery || !filterQueryReady.value) return;
        rememberClearedFilters();
      }
      if (
        activeTabId.value !== 'all'
        && !builtinById.has(String(activeTabId.value))
      ) {
        tabs.updateTabFilters(numericTabId(activeTabId.value), cloneFilters(currentFilters));
      }
      if (syncFiltersToUrl) syncUrl();
    },
    { deep: true },
  );

  onMounted(async () => {
    if (restoreQuery) {
      await whenFiltersReady();
      return;
    }
    try {
      await tabs.loadTabs();
    } catch {
      // Saved tabs must never break local filtering.
      return;
    }
    // Builtin tabs already restored synchronously above, and being quick
    // filters they never pop the filter panel open.
    const tabId = activeTabId.value;
    if (tabId === 'all' || builtinById.has(String(tabId))) return;
    const tab = savedTabs.value.find((t) => String(t.id) === String(tabId));
    if (tab) {
      loadTabFilters(currentFilters, tab);
      activeTabId.value = tab.id;
      isFilterPanelOpen.value = true;
    } else {
      activeTabId.value = 'all';
    }
  });

  const matcherEntries = Object.entries(matchers);

  function matcherKeys(key, fn) {
    return Array.isArray(fn.keys) && fn.keys.length ? fn.keys : [key];
  }

  function isMatcherActive(key, fn, filters = currentFilters) {
    return matcherKeys(key, fn).some((k) =>
      isValueActive(filters[k], DEFAULT_FILTERS[k]),
    );
  }

  const searchQuery = computed(() => String(currentFilters.search || '').trim().toLowerCase());

  const activeFilterCount = computed(() => {
    let count = 0;
    for (const [key, fn] of matcherEntries) {
      if (isMatcherActive(key, fn)) count++;
    }
    if (searchFields.length && searchQuery.value) count++;
    return count;
  });

  const hasActiveFilters = computed(() => activeFilterCount.value > 0);

  /**
   * Filter `records` by an explicit filter object.
   *
   * Split out of `applyFilters` so counting a saved tab runs the very same
   * predicates instead of a second copy of them: a tab whose badge disagreed
   * with what selecting it shows would be worse than no badge.
   */
  function filterWith(records, filters) {
    const query = String(filters.search || '').trim().toLowerCase();
    const activeMatchers = matcherEntries.filter(
      ([key, fn]) => isMatcherActive(key, fn, filters),
    );
    if (!activeMatchers.length && !query) return records;

    return records.filter((record) => {
      if (query && searchFields.length) {
        const hit = searchFields.some((f) =>
          String(record[f] ?? '').toLowerCase().includes(query),
        );
        if (!hit) return false;
      }
      return activeMatchers.every(([key, fn]) => fn(record, filters[key], filters));
    });
  }

  function applyFilters(records) {
    if (!hasActiveFilters.value) return records;
    return filterWith(records, currentFilters);
  }

  /**
   * How many of `records` each tab would show, keyed the way the strip reads
   * them: `all` plus one entry per tab id. Stored tab filters are partial, so
   * they are merged over fresh defaults exactly like `loadTabFilters` does.
   */
  function countTabs(records, tabList = savedTabs.value) {
    const counts = { all: records.length };
    for (const tab of tabList) {
      // Same read path as loadTabFilters: a badge computed off a raw scalar tab
      // would count it as unfiltered and disagree with what selecting it shows.
      const filters = { ...freshFilters(), ...readStoredFilters(tab.filters) };
      counts[String(tab.id)] = filterWith(records, filters).length;
    }
    return counts;
  }

  function resetFilters() {
    clearedUrlKeys.clear();
    Object.assign(currentFilters, freshFiltersKeepingModule(currentFilters));
    activeTabId.value = 'all';
  }

  /** Reset only the given filter keys to their defaults (chip removal). */
  function clearFilterKeys(keys) {
    const fresh = freshFilters();
    for (const key of keys) {
      if (key in fresh) currentFilters[key] = fresh[key];
    }
  }

  function selectTab(tabId) {
    clearedUrlKeys.clear();
    const builtin = builtinById.get(String(tabId));
    if (builtin) {
      activeTabId.value = builtin.id;
      loadTabFilters(currentFilters, builtin);
      return;
    }
    activeTabId.value = tabId;
    if (tabId === 'all') {
      Object.assign(currentFilters, freshFiltersKeepingModule(currentFilters));
      return;
    }
    const tab = savedTabs.value.find((t) => String(t.id) === String(tabId));
    if (tab) {
      loadTabFilters(currentFilters, tab);
    }
  }

  async function saveTab(name) {
    const tab = await tabs.saveTab(name, cloneFilters(currentFilters));
    if (tab) activeTabId.value = tab.id;
    return tab;
  }

  async function deleteTab(tabId) {
    await tabs.deleteTab(numericTabId(tabId));
    if (String(activeTabId.value) === String(tabId)) {
      resetFilters();
    }
  }

  async function renameTab(tabId, newName) {
    await tabs.renameTab(numericTabId(tabId), newName);
  }

  async function restoreTab(tabId) {
    const updated = await tabs.restoreTab(numericTabId(tabId));
    if (updated && String(activeTabId.value) === String(tabId)) {
      clearedUrlKeys.clear();
      loadTabFilters(currentFilters, updated);
    }
    return updated;
  }

  function rebaseTab(tabId) {
    return tabs.rebaseTab(numericTabId(tabId));
  }

  return {
    currentFilters,
    searchInput,
    savedTabs,
    displayTabs,
    activeTabId,
    activeModule,
    selectModule,
    isFilterPanelOpen,
    isLoading,
    isReady,
    lastError,
    hasActiveFilters,
    activeFilterCount,
    isTabLimitReached,
    applyFilters,
    countTabs,
    resetFilters,
    clearFilterKeys,
    selectTab,
    saveTab,
    deleteTab,
    renameTab,
    restoreTab,
    rebaseTab,
    reorderTabs,
    reloadTabs: tabs.loadTabs,
    consumeParam,
    // For a page with several instances: whichever becomes the visible one
    // re-claims the query string.
    syncUrl,
    filtersFromQuery,
    filterQueryReady,
    whenFiltersReady,
    buildFilterQuery,
  };
}
