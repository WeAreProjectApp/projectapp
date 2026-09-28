import { defineStore } from 'pinia';
import { DEFAULT_SCOPE, matchesScope, normalizeScope } from '~/utils/archiveScope';
import { get_request, create_request, patch_request, delete_request } from './services/request_http';
import { normalizeApiError, normalizeBlobApiError } from './services/normalize_api_error';
import { appendEmailRecipients } from '~/utils/emailRecipients';

// Fuera del store para que no sean reactivos: descartan respuestas viejas
// cuando dos peticiones se pisan (búsqueda con debounce, refrescos encadenados).
let listToken = 0;
let browseToken = 0;
let searchToken = 0;
let browseAbortController = null;
let searchAbortController = null;

function requestWasCancelled(error) {
  return error?.name === 'CanceledError' || error?.code === 'ERR_CANCELED';
}

export const useDocumentStore = defineStore('documents', {
  /**
   * State of the Document store.
   *
   * Properties:
   * - documents (Array): List of documents (admin).
   * - currentDocument (Object|null): Currently viewed/edited document.
   * - isLoading (Boolean): Whether a fetch operation is in progress.
   * - isUpdating (Boolean): Whether a mutation operation is in progress.
   * - error (String|null): Last error message.
   */
  state: () => ({
    documents: [],
    // Resultados de búsqueda: viven aparte porque la búsqueda es global
    // (ignora carpeta y estado) y no debe pisar la lista de navegación.
    searchResults: [],
    counts: {
      documents: { active: 0, archived: 0, unfiled_active: 0, unfiled_archived: 0 },
      folders: { active: 0, archived: 0 },
    },
    currentDocument: null,
    isLoading: false,
    isBrowseLoading: false,
    // La búsqueda tiene su propia bandera: comparte skeleton con la lista pero
    // no debe pisar isLoading, que gobierna los fetch de navegación.
    isSearchLoading: false,
    browsePageSize: 10,
    browsePagination: {
      page: 1, page_size: 10, count: 0, total_pages: 1,
    },
    searchPagination: {
      page: 1, page_size: 10, count: 0, total_pages: 1,
    },
    isUpdating: false,
    error: null,
    // Dónde: 'all' | 'root' | 'none' | <folder id>
    activeFolderId: 'all',
    // Estado, eje independiente de la carpeta: 'active' | 'archived' | 'all'
    archiveScope: DEFAULT_SCOPE,
    // Sentido común de la fecha visible: creación para activos, archivado para
    // archivados y la fecha correspondiente de cada fila en listas mixtas.
    dateOrder: 'recent',
    activeTagIds: [],
    activeStateIds: [],
    withoutStateIds: [],
    activeStatePreset: '',
    // Asociación, dos ejes más: null (sin filtro) | 'none' (sin asociar) | id.
    // `client` habla en pk de UserProfile, igual que el resto del panel.
    activeClientId: null,
    activeProjectId: null,
  }),

  getters: {
    /**
     * getDocumentById: Find a document in the list by its ID.
     */
    getDocumentById: (state) => (id) =>
      state.documents.find((d) => d.id === id),
  },

  actions: {
    /**
     * fetchDocuments: List all documents (admin), applying current filters.
     * Pass `{ folder, scope, tags, order }` to override for this call.
     *
     * `scope` sale de los overrides o cae a 'active', NUNCA del store: esta
     * acción también la consumen create.vue, [id]/edit.vue y las pestañas de
     * diagnóstico y propuestas, que jamás deben heredar el scope archivado.
     * La página del gestor es la única que pasa el suyo explícito.
     */
    async fetchDocuments(overrides = {}) {
      const token = ++listToken;
      this.isLoading = true;
      this.error = null;
      try {
        const folder = overrides.folder !== undefined ? overrides.folder : this.activeFolderId;
        const tags = overrides.tags !== undefined ? overrides.tags : this.activeTagIds;
        const states = overrides.states !== undefined ? overrides.states : this.activeStateIds;
        const withoutStates = overrides.withoutStates !== undefined
          ? overrides.withoutStates
          : this.withoutStateIds;
        const preset = overrides.preset !== undefined ? overrides.preset : this.activeStatePreset;
        const scope = normalizeScope(overrides.scope);
        // Igual que scope, el orden no se hereda implícitamente del store:
        // create/editor/proyectos/comunicaciones comparten esta acción y una
        // preferencia transitoria del gestor no debe reordenar sus consultas.
        const order = overrides.order !== undefined ? overrides.order : 'recent';
        const client = overrides.client !== undefined ? overrides.client : this.activeClientId;
        const project = overrides.project !== undefined ? overrides.project : this.activeProjectId;

        const params = new URLSearchParams();
        // 'root' se resuelve en el cliente: la partición necesita el árbol de
        // carpetas completo, que el store de carpetas ya tiene cargado.
        if (folder && folder !== 'all' && folder !== 'root') {
          params.set('folder', folder === 'none' ? 'none' : String(folder));
        }
        params.set('scope', scope);
        if (Array.isArray(tags) && tags.length > 0) {
          params.set('tags', tags.join(','));
        }
        if (Array.isArray(states) && states.length > 0) {
          params.set('states', states.join(','));
        }
        if (Array.isArray(withoutStates) && withoutStates.length > 0) {
          params.set('without_states', withoutStates.join(','));
        }
        if (preset) params.set('preset', preset);
        if (client != null) {
          params.set('client', client === 'none' ? 'none' : String(client));
        }
        if (project != null) {
          params.set('project', project === 'none' ? 'none' : String(project));
        }
        if (order === 'oldest') params.set('order', 'oldest');

        const response = await get_request(`documents/?${params.toString()}`);
        // Con búsqueda debounced y refrescos por mutación, las respuestas fuera
        // de orden son probables: sólo escribe la última pedida.
        if (token === listToken) this.documents = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error('Error fetching documents:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudieron cargar los documentos.'),
        };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * One server-owned page for the interactive document manager.
     *
     * The legacy list stays available to editors and selectors that expect a
     * top-level array. Only this action uses the paginated browser contract.
     */
    async browseDocuments(overrides = {}) {
      browseAbortController?.abort();
      const controller = new AbortController();
      browseAbortController = controller;
      const token = ++browseToken;
      this.isBrowseLoading = true;
      this.error = null;

      try {
        const folder = overrides.folder !== undefined
          ? overrides.folder : this.activeFolderId;
        const scope = normalizeScope(
          overrides.scope !== undefined ? overrides.scope : this.archiveScope,
        );
        const tags = overrides.tags !== undefined ? overrides.tags : this.activeTagIds;
        const states = overrides.states !== undefined ? overrides.states : this.activeStateIds;
        const withoutStates = overrides.withoutStates !== undefined
          ? overrides.withoutStates : this.withoutStateIds;
        const preset = overrides.preset !== undefined
          ? overrides.preset : this.activeStatePreset;
        const client = overrides.client !== undefined
          ? overrides.client : this.activeClientId;
        const project = overrides.project !== undefined
          ? overrides.project : this.activeProjectId;
        const order = overrides.order !== undefined ? overrides.order : this.dateOrder;
        const page = overrides.page !== undefined ? overrides.page : 1;
        const pageSize = overrides.pageSize !== undefined
          ? overrides.pageSize : this.browsePageSize;

        const params = new URLSearchParams({
          scope,
          page: String(page),
          page_size: String(pageSize),
        });
        if (folder && folder !== 'all') params.set('folder', String(folder));
        if (Array.isArray(tags) && tags.length) params.set('tags', tags.join(','));
        if (Array.isArray(states) && states.length) params.set('states', states.join(','));
        if (Array.isArray(withoutStates) && withoutStates.length) {
          params.set('without_states', withoutStates.join(','));
        }
        if (preset) params.set('preset', preset);
        if (client != null) params.set('client', String(client));
        if (project != null) params.set('project', String(project));
        if (order === 'oldest') params.set('order', 'oldest');

        const response = await get_request(
          `documents/browse/?${params.toString()}`,
          { signal: controller.signal },
        );
        if (token !== browseToken || browseAbortController !== controller) {
          return { success: false, cancelled: true };
        }
        const data = response.data || {};
        this.documents = Array.isArray(data.results) ? data.results : [];
        this.browsePagination = {
          page: data.page || 1,
          page_size: data.page_size || pageSize,
          count: data.count || 0,
          total_pages: data.total_pages || 1,
        };
        return { success: true, data };
      } catch (error) {
        if (requestWasCancelled(error) || token !== browseToken) {
          return { success: false, cancelled: true };
        }
        this.error = 'browse_failed';
        console.error('Error browsing documents:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudieron cargar los documentos.'),
        };
      } finally {
        if (token === browseToken && browseAbortController === controller) {
          browseAbortController = null;
          this.isBrowseLoading = false;
        }
      }
    },

    cancelDocumentBrowse() {
      browseToken += 1;
      browseAbortController?.abort();
      browseAbortController = null;
      this.isBrowseLoading = false;
    },

    /**
     * searchDocuments: busca por título o cliente en TODO el gestor.
     *
     * Ignora la carpeta actual y el estado a propósito: buscar sirve para
     * encontrar algo cuya ubicación no se recuerda, y acotarlo al scope visible
     * es justo lo que impedía dar con lo archivado.
     */
    async searchDocuments(term, overrides = {}) {
      searchAbortController?.abort();
      const controller = new AbortController();
      searchAbortController = controller;
      const token = ++searchToken;
      this.isSearchLoading = true;
      this.error = null;
      try {
        const page = overrides.page !== undefined ? overrides.page : 1;
        const pageSize = overrides.pageSize !== undefined
          ? overrides.pageSize : this.browsePageSize;
        const params = new URLSearchParams({
          scope: 'all',
          search: term,
          page: String(page),
          page_size: String(pageSize),
        });
        const order = overrides.order !== undefined ? overrides.order : 'recent';
        if (order === 'oldest') params.set('order', 'oldest');
        const response = await get_request(
          `documents/browse/?${params.toString()}`,
          { signal: controller.signal },
        );
        if (token !== searchToken || searchAbortController !== controller) {
          return { success: false, cancelled: true };
        }
        const data = response.data || {};
        this.searchResults = Array.isArray(data.results) ? data.results : [];
        this.searchPagination = {
          page: data.page || 1,
          page_size: data.page_size || pageSize,
          count: data.count || 0,
          total_pages: data.total_pages || 1,
        };
        return { success: true, data };
      } catch (error) {
        if (requestWasCancelled(error) || token !== searchToken) {
          return { success: false, cancelled: true };
        }
        this.error = 'search_failed';
        console.error('Error searching documents:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudo completar la búsqueda.'),
        };
      } finally {
        // Sólo la última búsqueda pedida apaga la bandera: una respuesta vieja
        // no debe cortar el skeleton de la que sigue en vuelo.
        if (token === searchToken && searchAbortController === controller) {
          searchAbortController = null;
          this.isSearchLoading = false;
        }
      }
    },

    cancelDocumentSearch() {
      searchToken += 1;
      searchAbortController?.abort();
      searchAbortController = null;
      this.searchResults = [];
      this.searchPagination = {
        page: 1,
        page_size: this.browsePageSize,
        count: 0,
        total_pages: 1,
      };
      this.isSearchLoading = false;
    },

    /**
     * fetchCounts: totales autoritativos para el panel lateral.
     *
     * No se pueden derivar de la lista: viene filtrada por carpeta, y sumar el
     * `document_count` de cada carpeta ignora los documentos sin carpeta y
     * duplica los que sí la tienen.
     */
    async fetchCounts() {
      try {
        const response = await get_request('documents/counts/');
        // Merge y no reemplazo: un payload parcial no debe vaciar el sidebar.
        this.counts = {
          documents: { ...this.counts.documents, ...(response.data?.documents || {}) },
          folders: { ...this.counts.folders, ...(response.data?.folders || {}) },
        };
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching document counts:', error);
        return { success: false, errors: error.response?.data };
      }
    },

    /**
     * fetchFolderClientSuggestion: cliente mayoritario de una carpeta, para
     * prellenar el form de crear. No toca isLoading: es un prellenado
     * silencioso, no una carga de página.
     */
    async fetchFolderClientSuggestion(folderId) {
      try {
        const response = await get_request(
          `documents/folder-client-suggestion/?folder=${folderId}`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching folder client suggestion:', error);
        return { success: false, errors: error.response?.data };
      }
    },

    /**
     * Qué asociación propone una carpeta para lo que se cree dentro de ella.
     *
     * La carpeta ahora DICE de quién es, y cuando lo dice eso manda: es un
     * dato, no una inferencia, y trae también el proyecto. La heurística del
     * cliente mayoritario queda como respaldo para las carpetas que todavía no
     * lo dicen — justo las que la pasada retroactiva va asociando.
     *
     * `source` distingue las dos para que el formulario pueda rotular la
     * sugerencia sin prometer que es un dato firme.
     */
    async resolveFolderAssociation(folderId) {
      const folderStore = useDocumentFolderStore();
      const folder = folderStore.folderById(folderId);
      if (folder?.client) {
        return {
          success: true,
          data: {
            client: folder.client,
            client_display_name: folder.client_display_name || '',
            project: folder.project ?? null,
            source: 'folder',
          },
        };
      }
      const result = await this.fetchFolderClientSuggestion(folderId);
      if (!result.success) return result;
      const client = result.data?.client ?? null;
      return {
        success: true,
        data: {
          client,
          client_display_name: result.data?.client_display_name || '',
          project: null,
          source: client ? 'suggestion' : null,
        },
      };
    },

    /**
     * Reconcilia una fila que cambió de estado con el scope que se está viendo.
     *
     * Bajo 'all' la fila se queda y sólo cambia su insignia; bajo un scope
     * concreto se va si dejó de pertenecer.
     */
    _reconcileScope(id, updated) {
      if (matchesScope(updated, this.archiveScope)) {
        const index = this.documents.findIndex((d) => d.id === id);
        if (index !== -1) this.documents.splice(index, 1, { ...this.documents[index], ...updated });
      } else {
        this.documents = this.documents.filter((d) => d.id !== id);
      }
      this.searchResults = this.searchResults.map((d) => (d.id === id ? { ...d, ...updated } : d));
    },

    /** archiveDocument: take a document out of the main view, keeping it. */
    async archiveDocument(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(`documents/${id}/archive/`, {});
        this._reconcileScope(id, response.data);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'archive_failed';
        console.error('Error archiving document:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudo archivar el documento.'),
        };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * unarchiveDocument: lo devuelve a la vista principal.
     *
     * `restoredChain` son las carpetas contenedoras que el backend reabrió para
     * que el documento quede alcanzable; la UI las nombra en el aviso.
     */
    async unarchiveDocument(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(`documents/${id}/unarchive/`, {});
        this._reconcileScope(id, response.data);
        return {
          success: true,
          data: response.data,
          restoredChain: response.data?.restored_chain || [],
          movedToRoot: !!response.data?.moved_to_root,
        };
      } catch (error) {
        this.error = 'unarchive_failed';
        console.error('Error unarchiving document:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudo restaurar el documento.'),
        };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * setFilters: Update active filters and refetch the list.
     * @param {object} filters - { folder?, scope?, tags?, order?, client?, project? }
     */
    async setFilters({
      folder, scope, tags, states, withoutStates, preset, order, client, project,
    } = {}) {
      if (folder !== undefined) this.activeFolderId = folder;
      if (scope !== undefined) this.archiveScope = normalizeScope(scope);
      if (order !== undefined) this.dateOrder = order;
      if (tags !== undefined) this.activeTagIds = Array.isArray(tags) ? [...tags] : [];
      if (states !== undefined) this.activeStateIds = Array.isArray(states) ? [...states] : [];
      if (withoutStates !== undefined) {
        this.withoutStateIds = Array.isArray(withoutStates) ? [...withoutStates] : [];
      }
      if (preset !== undefined) this.activeStatePreset = preset || '';
      if (client !== undefined) this.activeClientId = client;
      if (project !== undefined) this.activeProjectId = project;
      return this.fetchDocuments({ scope: this.archiveScope, order: this.dateOrder });
    },

    /** Update manager filters and request the first matching server page. */
    async setBrowseFilters({
      folder, scope, tags, states, withoutStates, preset, order, client, project,
    } = {}) {
      if (folder !== undefined) this.activeFolderId = folder;
      if (scope !== undefined) this.archiveScope = normalizeScope(scope);
      if (order !== undefined) this.dateOrder = order;
      if (tags !== undefined) this.activeTagIds = Array.isArray(tags) ? [...tags] : [];
      if (states !== undefined) this.activeStateIds = Array.isArray(states) ? [...states] : [];
      if (withoutStates !== undefined) {
        this.withoutStateIds = Array.isArray(withoutStates) ? [...withoutStates] : [];
      }
      if (preset !== undefined) this.activeStatePreset = preset || '';
      if (client !== undefined) this.activeClientId = client;
      if (project !== undefined) this.activeProjectId = project;
      return this.browseDocuments({ page: 1 });
    },

    async toggleBrowseTagFilter(tagId) {
      const idx = this.activeTagIds.indexOf(tagId);
      if (idx === -1) this.activeTagIds.push(tagId);
      else this.activeTagIds.splice(idx, 1);
      return this.browseDocuments({ page: 1 });
    },

    async toggleBrowseStateFilter(stateId) {
      const idx = this.activeStateIds.indexOf(stateId);
      if (idx === -1) this.activeStateIds.push(stateId);
      else this.activeStateIds.splice(idx, 1);
      this.activeStatePreset = '';
      return this.browseDocuments({ page: 1 });
    },

    async toggleBrowseStateAbsenceFilter(stateId) {
      const idx = this.withoutStateIds.indexOf(stateId);
      if (idx === -1) this.withoutStateIds.push(stateId);
      else this.withoutStateIds.splice(idx, 1);
      this.activeStatePreset = '';
      return this.browseDocuments({ page: 1 });
    },

    async setBrowseStatePreset(preset) {
      this.activeStatePreset = preset || '';
      this.activeStateIds = [];
      this.withoutStateIds = [];
      return this.browseDocuments({ page: 1 });
    },

    /**
     * toggleTagFilter: Toggle a tag id in the current filter set and refetch.
     */
    async toggleTagFilter(tagId) {
      const idx = this.activeTagIds.indexOf(tagId);
      if (idx === -1) this.activeTagIds.push(tagId);
      else this.activeTagIds.splice(idx, 1);
      // El scope viaja explícito, como en setFilters: fetchDocuments no lo
      // hereda del store, y omitirlo aquí sacaba al usuario de Archivados.
      return this.fetchDocuments({ scope: this.archiveScope, order: this.dateOrder });
    },

    async toggleStateFilter(stateId) {
      const idx = this.activeStateIds.indexOf(stateId);
      if (idx === -1) this.activeStateIds.push(stateId);
      else this.activeStateIds.splice(idx, 1);
      this.activeStatePreset = '';
      return this.fetchDocuments({ scope: this.archiveScope, order: this.dateOrder });
    },

    async toggleStateAbsenceFilter(stateId) {
      const idx = this.withoutStateIds.indexOf(stateId);
      if (idx === -1) this.withoutStateIds.push(stateId);
      else this.withoutStateIds.splice(idx, 1);
      this.activeStatePreset = '';
      return this.fetchDocuments({ scope: this.archiveScope, order: this.dateOrder });
    },

    async setStatePreset(preset) {
      this.activeStatePreset = preset || '';
      this.activeStateIds = [];
      this.withoutStateIds = [];
      return this.fetchDocuments({ scope: this.archiveScope, order: this.dateOrder });
    },

    /**
     * fetchDocument: Retrieve full document detail for admin editing.
     * @param {number} id - Document ID.
     */
    async fetchDocument(id) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(`documents/${id}/detail/`);
        this.currentDocument = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_detail_failed';
        console.error('Error fetching document:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudo cargar el documento.'),
        };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /** Return every communication where this document was referenced. */
    async fetchDocumentCommunications(id) {
      try {
        const response = await get_request(`documents/${id}/communications/`);
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(
            error,
            'No se pudieron cargar las comunicaciones del documento.',
          ),
        };
      }
    },

    /** Return every retained email snapshot that contains this document. */
    async fetchDocumentEmailUsage(id) {
      try {
        const response = await get_request(`documents/${id}/email-usage/`);
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(
            error,
            'No se pudo cargar el historial de envíos del documento.',
          ),
        };
      }
    },

    /**
     * createFromMarkdown: Create a new document from markdown content.
     * @param {object} data - Document content, presentation metadata, and the
     * optional private messages and custom notes.
     */
    async createFromMarkdown(data) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request('documents/create-from-markdown/', data);
        // The destination editor fetches its full detail after navigation.
        this.currentDocument = null;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'create_from_markdown_failed';
        console.error('Error creating document from markdown:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudo crear el documento.'),
        };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * updateDocument: Update document metadata and/or content.
     * @param {number} id - Document ID.
     * @param {object} data - Fields to update.
     */
    async updateDocument(id, data, { refreshDetail = false } = {}) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(`documents/${id}/update/`, data);
        const summary = response.data;
        const patch = { ...summary, folder: summary.folder_id };
        this._reconcileScope(Number(id), patch);
        if (Number(this.currentDocument?.id) === Number(id)) {
          this.currentDocument = { ...this.currentDocument, ...patch };
        }
        if (refreshDetail) {
          const detail = await this.fetchDocument(id);
          // A failed refresh does not turn an already committed save into a failure.
          if (detail.success) return detail;
          return { success: true, data: summary, refreshFailed: true };
        }
        return { success: true, data: summary };
      } catch (error) {
        this.error = 'update_failed';
        console.error('Error updating document:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudieron guardar los cambios.'),
        };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * deleteDocument: Delete a document.
     * @param {number} id - Document ID.
     */
    async deleteDocument(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        await delete_request(`documents/${id}/delete/`);
        this.documents = this.documents.filter((d) => d.id !== id);
        // También de los resultados de búsqueda: lo archivado se puede borrar
        // desde ahí, y sin esto la fila se quedaría en pantalla.
        this.searchResults = this.searchResults.filter((d) => d.id !== id);
        if (this.currentDocument?.id === id) {
          this.currentDocument = null;
        }
        return { success: true };
      } catch (error) {
        this.error = 'delete_failed';
        console.error('Error deleting document:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudo eliminar el documento.'),
        };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * duplicateDocument: Create a deep copy of a document as a new draft.
     * @param {number} id - Document ID to duplicate.
     */
    async duplicateDocument(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(`documents/${id}/duplicate/`, {});
        await this.fetchDocuments({ scope: this.archiveScope, order: this.dateOrder });
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'duplicate_failed';
        console.error('Error duplicating document:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...normalizeApiError(error, 'No se pudo duplicar el documento.'),
        };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * getDocumentMarkdown: Fetch only the markdown content of a document without
     * touching isLoading or currentDocument (safe to call from list views).
     * @param {number} id - Document ID.
     */
    async getDocumentMarkdown(id) {
      try {
        const response = await get_request(`documents/${id}/detail/`);
        return { success: true, markdown: response.data.content_markdown || '' };
      } catch (error) {
        console.error('Error fetching document markdown:', error);
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudo obtener el markdown del documento.'),
        };
      }
    },

    /**
     * getEmailDefaults: Fetch default greeting/subject/footer for the email composer.
     */
    async getEmailDefaults() {
      try {
        const response = await get_request('emails/defaults/');
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching email defaults:', error);
        return { success: false };
      }
    },

    /**
     * sendDocumentEmail: Send a branded email with optional document PDFs attached.
     * @param {object} payload - { recipient_emails, cc_emails, subject, greeting, footer, sections, document_ids }
     */
    async sendDocumentEmail(payload) {
      try {
        const formData = new FormData();
        appendEmailRecipients(formData, payload.recipient_emails, payload.cc_emails);
        formData.append('subject', payload.subject);
        formData.append('greeting', payload.greeting || '');
        formData.append('footer', payload.footer || '');
        formData.append('sections', JSON.stringify(payload.sections || []));
        formData.append('document_ids', JSON.stringify(payload.document_ids || []));
        const response = await create_request('emails/send/', formData);
        return { success: true, data: response.data };
      } catch (error) {
        const data = error.response?.data;
        const errorCode = error.response?.status === 429 ? 'rate_limited' : 'send_failed';
        return {
          success: false,
          errors: data,
          ...normalizeApiError(error, 'No se pudo enviar el correo.'),
          code: errorCode,
        };
      }
    },

    /**
     * downloadPdf: Download a document as PDF in the chosen template style.
     * @param {number} id - Document ID.
     * @param {string} title - Filename (without extension).
     * @param {string|null} template - 'friendly' | 'professional' | null (server default).
     */
    async downloadPdf(id, title = 'document', template = null) {
      try {
        const valid = template === 'friendly' || template === 'professional';
        const url = valid
          ? `documents/${id}/pdf/?template=${template}`
          : `documents/${id}/pdf/`;
        const response = await get_request(url, { responseType: 'blob' });
        const objectUrl = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = objectUrl;
        link.setAttribute('download', `${title}.pdf`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(objectUrl);
        return { success: true };
      } catch (error) {
        console.error('Error downloading PDF:', error);
        return {
          success: false,
          errors: error.response?.data,
          ...(await normalizeBlobApiError(error, 'No se pudo descargar el PDF.')),
        };
      }
    },
  },
});
