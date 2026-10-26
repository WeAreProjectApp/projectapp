import { defineStore } from 'pinia';
import { get_request } from './services/request_http';

export const usePanelDashboardStore = defineStore('panel_dashboard', {
  /**
   * State of the global panel dashboard store.
   *
   * Properties:
   * - summary (Object|null): consolidated payload from /api/panel/dashboard/
   *   with finance (null for non-superusers), proposals, additional modules,
   *   operations and the cross-module attention list.
   * - loading (Boolean): fetch in flight.
   * - error (Boolean): last fetch failed.
   */
  state: () => ({
    summary: null,
    loading: false,
    error: false,
  }),

  getters: {
    finance: (state) => state.summary?.finance ?? null,
    proposals: (state) => state.summary?.proposals ?? null,
    additionalModules: (state) => state.summary?.additional_modules ?? null,
    operations: (state) => state.summary?.operations ?? null,
    attention: (state) => state.summary?.attention ?? [],
    attentionCount: (state) => (state.summary?.attention ?? []).reduce((total, item) => total + item.count, 0),
    hasFinance: (state) => Boolean(state.summary?.finance),
  },

  actions: {
    async fetchAttentionPage(type, page = 1) {
      const summary = this.summary;
      const response = await get_request(`panel/dashboard/attention/${type}/?page=${page}`);
      const item = this.summary?.attention?.find((entry) => entry.type === type);
      if (item && summary === this.summary) {
        if (response.data.total === 0) this.summary.attention = this.summary.attention.filter((entry) => entry.type !== type);
        else item.count = response.data.total;
      }
      return response.data;
    },
    async fetchAttentionDetail(type, id) {
      const response = await get_request(`panel/dashboard/attention/${type}/${id}/`);
      return response.data;
    },
    /**
     * Fetch the consolidated dashboard summary.
     * @returns {Promise<{success: boolean}>}
     */
    async fetchSummary() {
      this.loading = true;
      this.error = false;
      try {
        const response = await get_request('panel/dashboard/');
        this.summary = response.data;
        return { success: true };
      } catch (error) {
        this.error = true;
        console.error('Error fetching panel dashboard:', error);
        return { success: false };
      } finally {
        this.loading = false;
      }
    },
  },
});
