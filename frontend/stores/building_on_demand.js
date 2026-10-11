import { defineStore } from 'pinia';
import { get_request } from './services/request_http';

const emptyHistory = () => ({ versions: [], total: 0, isLoading: false, error: '' });
const errorPayload = (error) => error?.response?.data || { detail: 'request_failed' };
const errorMessage = (errors) => {
  if (typeof errors?.message === 'string') return errors.message;
  return typeof errors?.detail === 'string' ? errors.detail : 'request_failed';
};
const previewLanguage = (locale) => String(locale || '').startsWith('en') ? 'en' : 'es';
const isProgram = (payload) => Boolean(
  payload && typeof payload === 'object' && !Array.isArray(payload)
  && typeof payload.hero?.title === 'string' && payload.hero.title.trim(),
);

export function normalizeMirrorStatus(value) {
  if (['synchronized', 'synced', 'in_sync'].includes(value)) return 'synchronized';
  if (['out_of_sync', 'stale', 'outdated'].includes(value)) return 'out_of_sync';
  if (value == null || value === 'not_initialized') return 'not_initialized';
  return 'unknown';
}

export const useBuildingOnDemandStore = defineStore('building_on_demand', {
  state: () => ({
    overview: null,
    preview: null,
    previewLanguage: 'es',
    previewRequestId: 0,
    economics: null,
    contract: null,
    contractRequestStatus: null,
    contractRequestError: '',
    history: { program: emptyHistory(), contract: emptyHistory() },
    isLoadingOverview: false,
    isLoadingPreview: false,
    isLoadingEconomics: false,
    isLoadingContract: false,
    overviewError: '',
    previewError: '',
    economicsError: '',
  }),

  getters: {
    programSummary: (state) => state.overview?.program || null,
    contractSummary: (state) => state.contract || state.overview?.contract || null,
    mirror: (state) => state.contract?.mirror || state.overview?.contract?.mirror || null,
    mirrorStatus() { return normalizeMirrorStatus(this.mirror?.status); },
    contractUnavailable: (state) => state.contractRequestStatus === 404 && state.overview?.contract === null,
    contractError() { return this.contractUnavailable ? '' : this.contractRequestError; },
    connector: (state) => state.overview?.connector || null,
    economicsRows: (state) => Array.isArray(state.economics?.rows) ? state.economics.rows : [],
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
        const response = await get_request('building-on-demand/admin/');
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
      const language = previewLanguage(lang);
      this.previewLanguage = language;
      this.isLoadingPreview = true;
      this.previewError = '';
      this.preview = null;
      try {
        const response = await get_request(`building-on-demand/public/?lang=${language}`);
        if (!isProgram(response.data)) {
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

    async fetchEconomics() {
      this.isLoadingEconomics = true;
      this.economicsError = '';
      try {
        const response = await get_request('building-on-demand/admin/economics/');
        this.economics = response.data || null;
        return { success: true, data: response.data };
      } catch (error) {
        const errors = errorPayload(error);
        this.economicsError = errorMessage(errors);
        return { success: false, errors };
      } finally {
        this.isLoadingEconomics = false;
      }
    },

    async fetchContract() {
      this.isLoadingContract = true;
      this.contractRequestError = '';
      this.contractRequestStatus = null;
      try {
        const response = await get_request('building-on-demand/admin/contract/');
        this.contract = response.data || null;
        return { success: true, data: response.data };
      } catch (error) {
        const errors = errorPayload(error);
        this.contractRequestStatus = error?.response?.status ?? null;
        this.contractRequestError = errorMessage(errors);
        if (this.contractRequestStatus === 404) this.contract = null;
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
        const response = await get_request(`building-on-demand/admin/${kind}/versions/?limit=20&offset=${offset}`);
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
