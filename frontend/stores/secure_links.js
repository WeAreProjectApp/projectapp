import { defineStore } from 'pinia';
import { get_request, create_request, patch_request, delete_request } from './services/request_http';
import { normalizeApiError } from './services/normalize_api_error';

/**
 * One-time secure links. Revealed content is never kept in the store: panel
 * and public views receive it as a return value and hold it in ephemeral
 * component state only.
 */
export const useSecureLinksStore = defineStore('secure_links', {
  state: () => ({
    links: [],
    count: 0,
    page: 1,
    pageSize: 25,
    counts: {},
    unopenedReceived: 0,
    publicCreateUrl: '',
    types: [],
    isLoading: false,
    isUpdating: false,
    error: null,
  }),

  getters: {
    typeByKey: (state) => (key) => state.types.find((type) => type.key === key) || null,
  },

  actions: {
    async fetchTypes() {
      if (this.types.length) return { success: true, data: this.types };
      try {
        const response = await get_request('secure-links/public/types/');
        this.types = response.data?.types || [];
        return { success: true, data: this.types };
      } catch (error) {
        return { success: false, error: normalizeApiError(error) };
      }
    },

    async fetchLinks(filters = {}) {
      this.isLoading = true;
      this.error = null;
      try {
        const params = new URLSearchParams();
        Object.entries(filters).forEach(([key, value]) => {
          if (value !== '' && value !== null && value !== undefined && value !== false) params.set(key, value);
        });
        const query = params.toString();
        const response = await get_request(`secure-links/${query ? `?${query}` : ''}`);
        const data = response.data || {};
        this.links = data.results || [];
        this.count = data.count || 0;
        this.page = data.page || 1;
        this.pageSize = data.page_size || 25;
        this.counts = data.counts || {};
        this.unopenedReceived = data.unopened_received || 0;
        this.publicCreateUrl = data.public_create_url || '';
        return { success: true };
      } catch (error) {
        this.error = 'fetch_failed';
        return { success: false, error: normalizeApiError(error, 'No se pudieron cargar los enlaces.') };
      } finally {
        this.isLoading = false;
      }
    },

    async fetchDetail(id) {
      try {
        const response = await get_request(`secure-links/${id}/`);
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, error: normalizeApiError(error, 'No se pudo abrir el enlace.') };
      }
    },

    async createLink(payload) {
      return this._write(() => create_request('secure-links/create/', payload), 'No se pudo crear el enlace.');
    },

    async updateLink(id, payload) {
      return this._write(() => patch_request(`secure-links/${id}/`, payload), 'No se pudo guardar el enlace.');
    },

    async reactivateLink(id, payload) {
      return this._write(() => create_request(`secure-links/${id}/reactivate/`, payload), 'No se pudo reactivar el enlace.');
    },

    async revokeLink(id) {
      return this._write(() => create_request(`secure-links/${id}/revoke/`, {}), 'No se pudo revocar el enlace.');
    },

    async deleteLink(id) {
      this.isUpdating = true;
      try {
        await delete_request(`secure-links/${id}/`);
        this.links = this.links.filter((link) => link.id !== id);
        this.count = Math.max(0, this.count - 1);
        return { success: true };
      } catch (error) {
        return { success: false, error: normalizeApiError(error, 'No se pudo eliminar el enlace.') };
      } finally {
        this.isUpdating = false;
      }
    },

    /** Audited panel view of the content. The result is not stored. */
    async viewContent(id) {
      try {
        const response = await create_request(`secure-links/${id}/content/`, {});
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, error: normalizeApiError(error, 'No se pudo mostrar el contenido.') };
      }
    },

    async fetchLinkUrl(id) {
      try {
        const response = await create_request(`secure-links/${id}/link/`, {});
        return { success: true, url: response.data?.url || '' };
      } catch (error) {
        return { success: false, error: normalizeApiError(error, 'No se pudo obtener el enlace.') };
      }
    },

    // ── Public page actions (anonymous; token always in the body) ──

    async publicStatus(token) {
      try {
        const response = await create_request('secure-links/public/status/', { token });
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, error: normalizeApiError(error) };
      }
    },

    async publicReveal(token) {
      try {
        const response = await create_request('secure-links/public/reveal/', { token });
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, error: normalizeApiError(error) };
      }
    },

    async publicCreate(payload) {
      try {
        const response = await create_request('secure-links/public/create/', payload);
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, error: normalizeApiError(error) };
      }
    },

    async _write(request, fallback) {
      this.isUpdating = true;
      try {
        const response = await request();
        this._merge(response.data);
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, error: normalizeApiError(error, fallback) };
      } finally {
        this.isUpdating = false;
      }
    },

    _merge(row) {
      if (!row?.id) return;
      const { url: _url, events: _events, ...summary } = row;
      const index = this.links.findIndex((link) => link.id === summary.id);
      if (index === -1) {
        this.links.unshift(summary);
        this.count += 1;
      } else {
        this.links[index] = { ...this.links[index], ...summary };
      }
    },
  },
});
