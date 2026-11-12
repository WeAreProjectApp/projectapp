import { defineStore } from 'pinia';
import { get_request, create_request, patch_request } from './services/request_http';
export const usePanelAccessStore = defineStore('panel_access', {
  state: () => ({ results: [], count: 0, page: 1, pages: 1, counts: {}, canManageTeam: false, loading: false, error: '', requestId: 0 }),
  getters: { hasResults: (state) => state.results.length > 0 },
  actions: {
    async fetchList(query = {}) {
      const requestId = ++this.requestId;
      this.loading = true; this.error = '';
      try {
        const { data } = await get_request('accounts/access/', { params: query });
        if (requestId !== this.requestId) return;
        this.results = data.results; this.count = data.count; this.page = data.page; this.pages = data.pages;
        this.counts = data.counts; this.canManageTeam = data.can_manage_team;
      } catch (failure) {
        if (requestId === this.requestId) this.error = failure.response?.data?.detail || 'No pudimos cargar los accesos.';
      } finally { if (requestId === this.requestId) this.loading = false; }
    },
    async createClient(data) { return (await create_request('accounts/access/', data)).data; },
    async change(id, data) { return (await patch_request(`accounts/access/${id}/`, data)).data; },
    async detail(id, page = 1) { return (await get_request(`accounts/access/${id}/`, { params: { page } })).data; },
  },
});
