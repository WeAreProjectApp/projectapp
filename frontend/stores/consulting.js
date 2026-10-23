import { defineStore } from 'pinia';
import { get_request } from './services/request_http';
import { consultingLanguage, isConsultingProgram } from '~/utils/consulting';

export const useConsultingStore = defineStore('consulting', {
  state: () => ({
    overview: null, preview: null, previewLanguage: 'es', previewRequestId: 0,
    isLoadingOverview: false, isLoadingPreview: false, overviewError: '', previewError: '',
    history: { versions: [], total: 0, isLoading: false, error: '' },
  }),
  getters: {
    programSummary: (state) => state.overview?.program || null,
  },
  actions: {
    async fetchOverview() {
      this.isLoadingOverview = true;
      this.overviewError = '';
      try {
        this.overview = (await get_request('consulting/admin/')).data;
      } catch {
        this.overviewError = 'request_failed';
      } finally {
        this.isLoadingOverview = false;
      }
    },
    async fetchPreview(lang = 'es') {
      const requestId = ++this.previewRequestId;
      const language = consultingLanguage(lang);
      this.previewLanguage = language;
      this.isLoadingPreview = true;
      this.previewError = '';
      this.preview = null;
      try {
        const { data } = await get_request(`consulting/public/?lang=${language}`);
        if (requestId !== this.previewRequestId) return;
        if (!isConsultingProgram(data)) throw new Error('invalid_program');
        this.preview = data;
      } catch {
        if (requestId === this.previewRequestId) this.previewError = 'request_failed';
      } finally {
        if (requestId === this.previewRequestId) this.isLoadingPreview = false;
      }
    },
    async fetchVersions({ append = false } = {}) {
      if (this.history.isLoading) return;
      this.history.isLoading = true;
      this.history.error = '';
      try {
        const offset = append ? this.history.versions.length : 0;
        const { data } = await get_request(`consulting/admin/program/versions/?limit=20&offset=${offset}`);
        this.history.versions = append ? [...this.history.versions, ...data.versions] : data.versions;
        this.history.total = data.total;
      } catch {
        this.history.error = 'request_failed';
      } finally {
        this.history.isLoading = false;
      }
    },
  },
});
