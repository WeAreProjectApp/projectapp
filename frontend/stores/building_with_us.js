import { defineStore } from 'pinia';
import { get_request } from './services/request_http';
import { buildingWithUsLanguage, isBuildingWithUsProgram } from '~/utils/buildingWithUs';

const emptyHistory = () => ({ versions: [], total: 0, isLoading: false, error: '' });
const errorPayload = (error) => error?.response?.data || { detail: 'request_failed' };
const errorMessage = (errors) => typeof errors?.detail === 'string' ? errors.detail : 'request_failed';

export function normalizeMirrorStatus(value) {
  if (['synchronized', 'synced', 'in_sync'].includes(value)) return 'synchronized';
  if (['out_of_sync', 'stale', 'outdated'].includes(value)) return 'out_of_sync';
  if (value == null || value === 'not_initialized') return 'not_initialized';
  return 'unknown';
}

export const useBuildingWithUsStore = defineStore('building_with_us', {
  state: () => ({
    overview: null,
    preview: null,
    previewLanguage: 'es',
    previewRequestId: 0,
    contract: null,
    history: { program: emptyHistory(), contract: emptyHistory() },
    isLoadingOverview: false,
    isLoadingPreview: false,
    isLoadingContract: false,
    overviewError: '',
    previewError: '',
    contractError: '',
  }),

  getters: {
    programSummary: (state) => state.overview?.program || null,
    contractSummary: (state) => state.contract || state.overview?.contract || null,
    mirror: (state) => state.contract?.mirror || state.overview?.contract?.mirror || null,
    mirrorStatus() { return normalizeMirrorStatus(this.mirror?.status); },
    hasMoreVersions: (state) => (kind) => {
      const history = state.history[kind];
      return Boolean(history && history.versions.length < history.total);
    },
  },

  actions: {
    async fetchOverview() {
      this.isLoadingOverview = true;
      this.overviewError = '';
      try {
        const response = await get_request('building-with-us/admin/');
        this.overview = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        const errors = errorPayload(error);
        this.overviewError = errorMessage(errors);
        return { success: false, errors };
      } finally {
        this.isLoadingOverview = false;
      }
    },

    async fetchPreview(lang = 'es') {
      const requestId = ++this.previewRequestId;
      const language = buildingWithUsLanguage(lang);
      this.previewLanguage = language;
      this.isLoadingPreview = true;
      this.previewError = '';
      this.preview = null;
      try {
        const response = await get_request(`building-with-us/public/?lang=${language}`);
        if (!isBuildingWithUsProgram(response.data)) {
          const errors = { detail: 'invalid_program' };
          if (requestId === this.previewRequestId) this.previewError = errors.detail;
          return { success: false, errors };
        }
        if (requestId === this.previewRequestId) this.preview = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        const errors = errorPayload(error);
        if (requestId === this.previewRequestId) this.previewError = errorMessage(errors);
        return { success: false, errors };
      } finally {
        if (requestId === this.previewRequestId) this.isLoadingPreview = false;
      }
    },

    async fetchContract() {
      this.isLoadingContract = true;
      this.contractError = '';
      try {
        const response = await get_request('building-with-us/admin/contract/');
        this.contract = response.data || null;
        return { success: true, data: response.data };
      } catch (error) {
        const errors = errorPayload(error);
        this.contractError = errorMessage(errors);
        return { success: false, errors };
      } finally {
        this.isLoadingContract = false;
      }
    },

    async fetchVersions(kind, { append = false } = {}) {
      if (!['program', 'contract'].includes(kind)) {
        return { success: false, errors: { detail: 'invalid_history_kind' } };
      }
      const history = this.history[kind];
      const offset = append ? history.versions.length : 0;
      history.isLoading = true;
      history.error = '';
      try {
        const response = await get_request(`building-with-us/admin/${kind}/versions/?limit=20&offset=${offset}`);
        const versions = Array.isArray(response.data?.versions) ? response.data.versions : [];
        history.versions = append ? [...history.versions, ...versions] : versions;
        history.total = response.data?.total ?? history.versions.length;
        return { success: true, data: response.data };
      } catch (error) {
        const errors = errorPayload(error);
        history.error = errorMessage(errors);
        return { success: false, errors };
      } finally {
        history.isLoading = false;
      }
    },
  },
});
