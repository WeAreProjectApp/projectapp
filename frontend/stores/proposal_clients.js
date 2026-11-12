import { defineStore } from 'pinia';
import {
  get_request,
  create_request,
  patch_request,
  delete_request,
} from './services/request_http';
import { normalizeApiError } from './services/normalize_api_error';

function clientListUrl({ search = '', orphans = null, archived = false, limit = 100 } = {}) {
  const query = new URLSearchParams();
  if (search) query.set('search', search);
  if (orphans === true) query.set('orphans', 'true');
  if (orphans === false) query.set('orphans', 'false');
  if (archived === true) query.set('archived', 'true');
  if (limit) query.set('limit', String(limit));
  return `proposals/client-profiles/${query.size ? `?${query}` : ''}`;
}

function clientCountsUrl(search = '') {
  const query = new URLSearchParams();
  if (search) query.set('search', search);
  return `proposals/client-profiles/status-counts/${query.size ? `?${query}` : ''}`;
}

/**
 * Store for the proposal admin panel's client management surface.
 *
 * Backed by /api/proposals/client-profiles/* endpoints which expose
 * accounts.UserProfile (filtered to role='client') with annotated
 * proposal counts and orphan flags. The store is the single entry point
 * for the new clients page, the autocomplete component used in the
 * proposal create/edit forms, and the orphan-cleanup workflow.
 */
export const useProposalClientsStore = defineStore('proposalClients', {
  state: () => ({
    clients: [],
    statusCounts: {},
    currentClient: null,
    searchResults: [],
    isLoading: false,
    isSearching: false,
    isUpdating: false,
    error: null,
    _searchAbortController: null,
    _registerGeneration: 0,
    _registerAbortController: null,
  }),

  getters: {
    /** Clients with zero proposals AND zero platform projects. */
    orphanClients: (state) => state.clients.filter((c) => c.is_orphan),

    /** Clients with at least one proposal or project. */
    activeClients: (state) => state.clients.filter((c) => !c.is_orphan),

    /** Lookup helper used by selection-aware UI. */
    getClientById: (state) => (id) =>
      state.clients.find((c) => c.id === id) || null,
  },

  actions: {
    /** Invalidate immediately, including the interval before a debounced load. */
    invalidateClientRegister({ pending = true } = {}) {
      this._registerGeneration += 1;
      this._registerAbortController?.abort();
      this._registerAbortController = null;
      this.$patch((state) => {
        state.clients = [];
        state.statusCounts = {};
        state.error = null;
        state.isLoading = pending;
      });
    },

    /** Publish rows and counts from one query together; obsolete loads never commit. */
    async fetchClientRegister({ silent = false, ...params } = {}) {
      const generation = ++this._registerGeneration;
      this._registerAbortController?.abort();
      const controller = new AbortController();
      this._registerAbortController = controller;
      if (!silent) this.isLoading = true;
      this.error = null;
      try {
        const [rows, counts] = await Promise.all([
          get_request(clientListUrl(params), { signal: controller.signal }),
          get_request(clientCountsUrl(params.search), { signal: controller.signal }),
        ]);
        if (generation !== this._registerGeneration) return { success: false, cancelled: true };
        this.$patch((state) => {
          state.clients = Array.isArray(rows.data) ? rows.data : [];
          state.statusCounts = counts.data && typeof counts.data === 'object' && !Array.isArray(counts.data)
            ? counts.data : {};
        });
        return { success: true, data: this.clients };
      } catch (error) {
        if (generation !== this._registerGeneration) return { success: false, cancelled: true };
        controller.abort();
        this.$patch((state) => {
          state.clients = [];
          state.statusCounts = {};
          state.error = error?.response?.data?.error || 'fetch_failed';
        });
        return { success: false, errors: error?.response?.data };
      } finally {
        if (generation === this._registerGeneration) {
          this._registerAbortController = null;
          this.isLoading = false;
        }
      }
    },

    // -----------------------------------------------------------------
    // List + filters
    // -----------------------------------------------------------------

    /**
     * Fetch clients with optional search and orphans filter.
     *
     * @param {Object} [params]
     * @param {string} [params.search] - icontains match on email/name/company.
     * @param {boolean|null} [params.orphans] - true=only orphans,
     *     false=only active, null/undefined=all.
     * @param {boolean} [params.archived=false] - true=only archived
     *     clients; false/omitted=exclude them (server default).
     * @param {number} [params.limit=100] - hard cap 500 (server-side).
     * @param {boolean} [params.silent=false] - true skips the isLoading
     *     flip so in-place refreshes don't swap the list to a skeleton.
     */
    async fetchClients({ search = '', orphans = null, archived = false, limit = 100, silent = false } = {}) {
      if (!silent) this.isLoading = true;
      this.error = null;
      try {
        const url = clientListUrl({ search, orphans, archived, limit });
        const response = await get_request(url);
        this.clients = Array.isArray(response.data) ? response.data : [];
        if (!silent) this.isLoading = false;
        return { success: true, data: this.clients };
      } catch (error) {
        const data = error?.response?.data;
        this.error = data?.error || 'fetch_failed';
        if (!silent) this.isLoading = false;
        return { success: false, errors: data };
      }
    },

    /**
     * Match count per client-status option, honouring the same search.
     *
     * The status cut happens server-side, so the page only holds the rows of
     * the selected one and cannot count the others itself. Failures leave the
     * previous counts alone: a selector without numbers still works.
     *
     * @param {Object} [params]
     * @param {string} [params.search] - same icontains match as fetchClients.
     */
    async fetchStatusCounts({ search = '' } = {}) {
      try {
        const url = clientCountsUrl(search);
        const response = await get_request(url);
        this.statusCounts = response.data && typeof response.data === 'object'
          ? response.data
          : {};
        return { success: true, data: this.statusCounts };
      } catch (error) {
        return { success: false, errors: error?.response?.data };
      }
    },

    // -----------------------------------------------------------------
    // Search / autocomplete
    // -----------------------------------------------------------------

    /**
     * Lightweight, progressively pageable search for client pickers. Cancels
     * any in-flight request via AbortController so rapid keystrokes don't race
     * each other in the UI. The API keeps returning an array and publishes the
     * total in `X-Total-Count`.
     *
     * @param {string} query - free-form search text (any field).
     * @param {Object} [paging]
     * @param {number} [paging.offset=0]
     * @param {number} [paging.limit=20]
     * @param {'name'|'-name'} [paging.order] - optional catalog direction.
     * @returns {Promise<{success:boolean,data?:Array,total?:number,hasMore?:boolean,nextOffset?:number,errors?:Object}>}
     */
    async searchClients(query, { offset = 0, limit = 20, order = '' } = {}) {
      // Cancel any in-flight request from a previous keystroke.
      if (this._searchAbortController) {
        this._searchAbortController.abort();
      }
      const controller = new AbortController();
      this._searchAbortController = controller;

      this.isSearching = true;
      this.error = null;
      try {
        const params = new URLSearchParams({
          q: query || '',
          limit: String(limit),
          offset: String(offset),
        });
        if (order) params.set('order', order);
        const url = `proposals/client-profiles/search/?${params.toString()}`;
        const response = await get_request(url, { signal: controller.signal });
        // A response can still resolve after its AbortController was superseded
        // (not every adapter rejects immediately). It must not replace the
        // latest query or append rows into another filter.
        if (this._searchAbortController !== controller) {
          return { success: false, cancelled: true };
        }

        const page = Array.isArray(response.data) ? response.data : [];
        const previous = offset > 0 ? this.searchResults : [];
        const ids = new Set(previous.map((client) => client.id));
        this.searchResults = [
          ...previous,
          ...page.filter((client) => !ids.has(client.id)),
        ];

        const rawTotal = response.headers?.['x-total-count']
          ?? response.headers?.get?.('x-total-count');
        const parsedTotal = Number(rawTotal);
        const total = rawTotal !== undefined && rawTotal !== null && rawTotal !== ''
          && Number.isFinite(parsedTotal)
          ? parsedTotal
          : null;
        const nextOffset = offset + page.length;
        const hasMore = total == null
          ? page.length === limit
          : nextOffset < total;

        this._searchAbortController = null;
        this.isSearching = false;
        return {
          success: true,
          data: page,
          total,
          hasMore,
          nextOffset,
        };
      } catch (error) {
        const data = error?.response?.data;
        // Cancellation is not a real error — keep results untouched.
        if (error.name === 'CanceledError' || error.code === 'ERR_CANCELED') {
          if (this._searchAbortController === controller) {
            this._searchAbortController = null;
            this.isSearching = false;
          }
          return { success: false, cancelled: true };
        }
        if (this._searchAbortController === controller) {
          this._searchAbortController = null;
          this.isSearching = false;
        }
        this.error = data?.error || 'search_failed';
        return { success: false, errors: data };
      }
    },

    // -----------------------------------------------------------------
    // Detail
    // -----------------------------------------------------------------

    /** Fetch one client with the full nested proposals history. */
    async fetchClient(id) {
      this.error = null;
      try {
        const response = await get_request(
          `proposals/client-profiles/${id}/`,
        );
        this.currentClient = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        const data = error?.response?.data;
        this.error = data?.error || 'fetch_failed';
        return { success: false, errors: data };
      }
    },

    // -----------------------------------------------------------------
    // Create / update / delete
    // -----------------------------------------------------------------

    /**
     * Standalone create — does NOT send invitation email. When `email`
     * is omitted the backend generates a placeholder cliente_<id>@temp.example.com.
     */
    async createClient(payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          'proposals/client-profiles/create/',
          payload,
        );
        this.clients = [response.data, ...this.clients];
        this.isUpdating = false;
        return { success: true, data: response.data };
      } catch (error) {
        const data = error?.response?.data;
        this.error = data?.error || 'create_failed';
        this.isUpdating = false;
        return { success: false, errors: data };
      }
    },

    /** Update profile + cascade snapshot to all linked proposals. */
    async updateClient(id, payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(
          `proposals/client-profiles/${id}/update/`,
          payload,
        );
        this.clients = this.clients.map((c) =>
          c.id === id ? response.data : c,
        );
        if (this.currentClient?.id === id) {
          this.currentClient = { ...this.currentClient, ...response.data };
        }
        this.isUpdating = false;
        return { success: true, data: response.data };
      } catch (error) {
        const data = error?.response?.data;
        this.error = data?.error || 'update_failed';
        this.isUpdating = false;
        return { success: false, errors: data };
      }
    },

    /**
     * What archiving this client would do to its projects. Writes nothing.
     *
     * The preview carries one `impact_token` per project: the confirm echoes
     * them back so the backend can prove the operator saw the numbers that
     * are about to be applied.
     */
    async previewClientArchive(id) {
      try {
        const response = await get_request(
          `proposals/client-profiles/${id}/archive-preview/`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, errors: error?.response?.data };
      }
    },

    /**
     * Archive the client and suspend the projects named in `transitions`.
     *
     * Not a PATCH on purpose: the ordinary update endpoint rejects
     * `is_archived`, because archiving cancels the projects' future billing
     * and that has to go through the preview.
     */
    async archiveClient(id, transitions) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `proposals/client-profiles/${id}/archive/`,
          { transitions },
        );
        const updated = response.data.client;
        this.clients = this.clients.map((c) => (c.id === id ? updated : c));
        if (this.currentClient?.id === id) {
          this.currentClient = { ...this.currentClient, ...updated };
        }
        this.isUpdating = false;
        return { success: true, data: response.data };
      } catch (error) {
        const data = error?.response?.data;
        this.error = data?.error || 'archive_failed';
        this.isUpdating = false;
        return { success: false, errors: data };
      }
    },

    /** Bring the client back. Its projects stay suspended. */
    async unarchiveClient(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `proposals/client-profiles/${id}/unarchive/`,
          {},
        );
        const updated = response.data.client;
        this.clients = this.clients.map((c) => (c.id === id ? updated : c));
        if (this.currentClient?.id === id) {
          this.currentClient = { ...this.currentClient, ...updated };
        }
        this.isUpdating = false;
        return { success: true, data: response.data };
      } catch (error) {
        const data = error?.response?.data;
        this.error = data?.error || 'unarchive_failed';
        this.isUpdating = false;
        return { success: false, errors: data };
      }
    },

    /**
     * Delete a client (and the underlying User). Backend enforces the
     * orphan rule (zero proposals, projects, diagnostics, accounting
     * incomes and hostings); a 400 with `client_has_proposals` /
     * `client_has_projects` / `client_has_diagnostics` /
     * `client_has_incomes` / `client_has_hostings` is returned otherwise.
     */
    async deleteClient(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        await delete_request(`proposals/client-profiles/${id}/delete/`);
        this.clients = this.clients.filter((c) => c.id !== id);
        if (this.currentClient?.id === id) {
          this.currentClient = null;
        }
        this.isUpdating = false;
        return { success: true };
      } catch (error) {
        const data = error?.response?.data;
        this.error = data?.error || 'delete_failed';
        this.isUpdating = false;
        return {
          success: false,
          errorCode: data?.error,
          count: data?.count,
          errors: data,
        };
      }
    },

    // -----------------------------------------------------------------
    // Email history (Emails module + the client's ficha)
    // -----------------------------------------------------------------

    /**
     * One page of a client's emails, newest first.
     *
     * Deliberately outside `isLoading`/`error`, like the accounting store's
     * modal-scoped reads: opening the modal must not blank the client list
     * behind it.
     *
     * @param {number} clientId
     * @param {Object} [params]
     * @param {'client'|'internal'} [params.audience] - which group to show.
     * @param {number} [params.page]
     */
    async fetchClientEmails(clientId, { audience = '', page = 1 } = {}) {
      try {
        const query = new URLSearchParams();
        if (audience) query.set('audience', audience);
        if (page && page !== 1) query.set('page', String(page));
        const suffix = query.toString() ? `?${query}` : '';
        const response = await get_request(
          `proposals/client-profiles/${clientId}/emails/${suffix}`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching client emails:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /** The message as delivered, for the preview modal. */
    async fetchClientEmailBody(clientId, logId) {
      try {
        const response = await get_request(
          `proposals/client-profiles/${clientId}/emails/${logId}/body/`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching client email body:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },

    /** Re-send a failed notice to the address on that row, and only to it. */
    async retryClientEmail(clientId, logId) {
      try {
        const response = await create_request(
          `proposals/client-profiles/${clientId}/emails/${logId}/retry/`, {},
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error retrying client email:', error);
        return { success: false, ...normalizeApiError(error) };
      }
    },
  },
});
