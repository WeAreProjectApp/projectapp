import { nextTick, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { DEFAULT_SCOPE, DOCUMENT_SCOPES } from '~/utils/archiveScope';

const CONTROLLED_QUERY_KEYS = [
  'folder', 'scope', 'tags', 'states', 'without_states', 'preset',
  'client', 'project', 'by', 'q', 'order', 'view', 'page', 'focus',
];
const DOCUMENT_STATE_PRESETS = new Set([
  'needs_fix', 'sent_not_closed', 'closed', 'unclassified',
]);

function firstQueryValue(value) {
  return Array.isArray(value) ? value[0] : value;
}

function positiveInteger(value) {
  const number = Number(firstQueryValue(value));
  return Number.isInteger(number) && number > 0 ? number : null;
}

function sameIds(left, right) {
  const normalizedLeft = [...left].map(Number).sort((a, b) => a - b);
  const normalizedRight = [...right].map(Number).sort((a, b) => a - b);
  return normalizedLeft.length === normalizedRight.length
    && normalizedLeft.every((id, index) => id === normalizedRight[index]);
}

function sameQueryValue(left, right) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

/**
 * Hace que la URL sea la fuente reproducible del listado de documentos.
 *
 * Además de los ejes de datos (`folder`, `scope`, estados y asociaciones),
 * conserva búsqueda, orden, presentación, página y la fila/tarjeta a recuperar.
 * Así un enlace al editor puede llevar una dirección completa en `from` y el
 * historial del navegador puede reconstruir la misma vista sin memoria global.
 */
export function useDocumentFilterQuery(documentStore, {
  searchQuery,
  viewMode,
  navigationMode,
  currentPage,
  focusedDocumentId,
  onNavigate,
} = {}) {
  const route = useRoute();
  const router = useRouter();
  const isApplyingQuery = ref(false);
  let hasAppliedQuery = false;

  function parseFolder(raw) {
    const value = firstQueryValue(raw);
    if (value === undefined || value === null || value === '') return null;
    if (value === 'all' || value === 'root' || value === 'none') return value;
    return positiveInteger(value);
  }

  function parseScope(raw) {
    const value = firstQueryValue(raw);
    return DOCUMENT_SCOPES.includes(value) ? value : null;
  }

  function parseAssociation(raw) {
    const value = firstQueryValue(raw);
    if (value === undefined || value === null || value === '') return null;
    if (value === 'none') return 'none';
    return positiveInteger(value);
  }

  function parseIds(raw) {
    const value = firstQueryValue(raw);
    if (typeof value !== 'string' || !value.trim()) return [];
    return [...new Set(value.split(',').map(positiveInteger).filter(Boolean))]
      .sort((left, right) => left - right);
  }

  function parsePreset(raw) {
    const value = firstQueryValue(raw);
    return DOCUMENT_STATE_PRESETS.has(value) ? value : '';
  }

  function parseSearch(raw) {
    const value = firstQueryValue(raw);
    return typeof value === 'string' ? value.trim() : '';
  }

  function parseOrder(raw) {
    return firstQueryValue(raw) === 'oldest' ? 'oldest' : 'recent';
  }

  function parseView(raw) {
    return firstQueryValue(raw) === 'grid' ? 'grid' : 'list';
  }

  function parseNavigationMode(raw) {
    const value = firstQueryValue(raw);
    return value === 'project' || value === 'client' ? value : null;
  }

  /**
   * Vuelca el query en todos los estados visibles. Devuelve un resumen para que
   * atrás/adelante sólo repida el fetch o la búsqueda cuando realmente hace
   * falta y no por cambios de página, vista o foco.
   */
  function applyQueryToStore() {
    const preset = parsePreset(route.query.preset);
    const nextState = {
      folder: parseFolder(route.query.folder) ?? 'all',
      scope: parseScope(route.query.scope) ?? DEFAULT_SCOPE,
      tags: parseIds(route.query.tags),
      states: preset ? [] : parseIds(route.query.states),
      withoutStates: preset ? [] : parseIds(route.query.without_states),
      preset,
      client: parseAssociation(route.query.client),
      project: parseAssociation(route.query.project),
      navigationMode: parseNavigationMode(route.query.by),
      search: parseSearch(route.query.q),
      order: parseOrder(route.query.order),
      view: parseView(route.query.view),
      page: positiveInteger(route.query.page) ?? 1,
      focus: positiveInteger(route.query.focus),
    };

    const summary = {
      filtersChanged: documentStore.activeFolderId !== nextState.folder
        || documentStore.archiveScope !== nextState.scope
        || !sameIds(documentStore.activeTagIds || [], nextState.tags)
        || !sameIds(documentStore.activeStateIds || [], nextState.states)
        || !sameIds(documentStore.withoutStateIds || [], nextState.withoutStates)
        || (documentStore.activeStatePreset || '') !== nextState.preset
        || documentStore.activeClientId !== nextState.client
        || documentStore.activeProjectId !== nextState.project
        || documentStore.dateOrder !== nextState.order,
      searchChanged: !!searchQuery && searchQuery.value !== nextState.search,
      viewChanged: !!viewMode && viewMode.value !== nextState.view,
      pageChanged: !!currentPage && currentPage.value !== nextState.page,
      focusChanged: !!focusedDocumentId && focusedDocumentId.value !== nextState.focus,
      modeChanged: !!navigationMode
        && !!nextState.navigationMode
        && navigationMode.value !== nextState.navigationMode,
    };
    summary.changed = Object.values(summary).some(Boolean);

    isApplyingQuery.value = true;
    documentStore.activeFolderId = nextState.folder;
    documentStore.archiveScope = nextState.scope;
    documentStore.activeTagIds = nextState.tags;
    documentStore.activeStateIds = nextState.states;
    documentStore.withoutStateIds = nextState.withoutStates;
    documentStore.activeStatePreset = nextState.preset;
    documentStore.activeClientId = nextState.client;
    documentStore.activeProjectId = nextState.project;
    if (navigationMode && nextState.navigationMode) {
      navigationMode.value = nextState.navigationMode;
    }
    documentStore.dateOrder = nextState.order;
    if (searchQuery) searchQuery.value = nextState.search;
    if (viewMode) viewMode.value = nextState.view;
    if (currentPage) currentPage.value = nextState.page;
    if (focusedDocumentId) focusedDocumentId.value = nextState.focus;

    // La preferencia puede cambiar mientras el listado espera la carga inicial.
    // Publicar desde el store antes de leer la URL borraría el contexto del enlace.
    hasAppliedQuery = true;

    // Normaliza basura y defaults escritos a mano. Los watchers originados por
    // estas asignaciones convergen en el mismo query y no agregan historial.
    syncQuery();
    nextTick(() => { isApplyingQuery.value = false; });
    return summary;
  }

  /** Una carpeta borrada ya no es un destino reproducible: cae a Todos. */
  function validateFolder(folderStore) {
    const id = documentStore.activeFolderId;
    if (typeof id === 'number' && !folderStore.folderById(id)) {
      documentStore.activeFolderId = 'all';
      return true;
    }
    return false;
  }

  function syncQuery() {
    if (!hasAppliedQuery) return;

    const query = { ...route.query };
    const folder = documentStore.activeFolderId;
    const scope = documentStore.archiveScope;
    const tags = [...new Set(documentStore.activeTagIds || [])]
      .map(Number)
      .filter((id) => Number.isInteger(id) && id > 0)
      .sort((left, right) => left - right);
    const states = [...new Set(documentStore.activeStateIds || [])]
      .map(Number)
      .filter((id) => Number.isInteger(id) && id > 0)
      .sort((left, right) => left - right);
    const withoutStates = [...new Set(documentStore.withoutStateIds || [])]
      .map(Number)
      .filter((id) => Number.isInteger(id) && id > 0)
      .sort((left, right) => left - right);
    const preset = DOCUMENT_STATE_PRESETS.has(documentStore.activeStatePreset)
      ? documentStore.activeStatePreset
      : '';
    const client = documentStore.activeClientId;
    const project = documentStore.activeProjectId;
    const by = navigationMode?.value;
    const search = searchQuery?.value?.trim() || '';
    const order = documentStore.dateOrder;
    const view = viewMode?.value;
    const page = currentPage?.value;
    const focus = focusedDocumentId?.value;

    if (folder === 'all' || folder == null) delete query.folder;
    else query.folder = String(folder);
    if (scope === DEFAULT_SCOPE) delete query.scope;
    else query.scope = scope;
    if (tags.length) query.tags = tags.join(',');
    else delete query.tags;
    if (preset) {
      query.preset = preset;
      delete query.states;
      delete query.without_states;
    } else {
      delete query.preset;
      if (states.length) query.states = states.join(',');
      else delete query.states;
      if (withoutStates.length) query.without_states = withoutStates.join(',');
      else delete query.without_states;
    }
    if (client == null) delete query.client;
    else query.client = String(client);
    if (project == null) delete query.project;
    else query.project = String(project);
    if (by === 'project' || by === 'client') query.by = by;
    else delete query.by;
    if (search) query.q = search;
    else delete query.q;
    if (order === 'oldest') query.order = 'oldest';
    else delete query.order;
    if (view === 'grid') query.view = 'grid';
    else delete query.view;
    if (Number.isInteger(page) && page > 1) query.page = String(page);
    else delete query.page;
    if (Number.isInteger(focus) && focus > 0) query.focus = String(focus);
    else delete query.focus;

    if (CONTROLLED_QUERY_KEYS.every(
      (key) => sameQueryValue(query[key], route.query[key]),
    )) return;
    router.replace({ query });
  }

  watch(() => [
    documentStore.activeFolderId,
    documentStore.archiveScope,
    documentStore.activeTagIds,
    documentStore.activeStateIds,
    documentStore.withoutStateIds,
    documentStore.activeStatePreset,
    documentStore.activeClientId,
    documentStore.activeProjectId,
    navigationMode?.value,
    documentStore.dateOrder,
    searchQuery?.value,
    viewMode?.value,
    currentPage?.value,
    focusedDocumentId?.value,
  ], () => {
    if (!isApplyingQuery.value) syncQuery();
  }, { deep: true });

  // El otro sentido: un popstate aplica la dirección completa y avisa al
  // listado qué clase de trabajo necesita repetir.
  watch(() => CONTROLLED_QUERY_KEYS.map((key) => route.query[key]), () => {
    if (!hasAppliedQuery) return;
    const summary = applyQueryToStore();
    if (summary.changed) onNavigate?.(summary);
  }, { deep: true });

  return {
    applyQueryToStore,
    validateFolder,
    isApplyingQuery,
    syncQuery,
  };
}
