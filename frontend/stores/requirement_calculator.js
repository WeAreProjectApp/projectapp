import { defineStore } from 'pinia';
import { get_request, create_request, patch_request } from './services/request_http';

const root = 'requirement-calculator/';

const useRequirementCalculatorStore = defineStore('requirementCalculator', {
  state: () => ({ general: null, project: null, projectVersion: null, revisions: [], revisionCount: 0,
    estimates: [], estimateCount: 0, calibration: null, busy: false, pending: 0, versionRequest: 0, error: null }),
  actions: {
    async perform(operation) {
      this.pending++;
      this.busy = true;
      this.error = null;
      try {
        return await operation();
      } catch (error) {
        this.error = error.response?.data || { detail: error.message };
        return null;
      } finally {
        this.pending--;
        this.busy = this.pending > 0;
      }
    },
    loadGeneral() {
      return this.perform(async () => {
        this.general = (await get_request(root)).data;
        return this.general;
      });
    },
    saveGeneral(payload) {
      return this.perform(async () => {
        this.general = (await create_request(root, payload)).data;
        return this.general;
      });
    },
    preview(definition) {
      return this.perform(async () => (await create_request(`${root}preview/`, { definition })).data);
    },
    loadRevisions(offset = 0) {
      return this.perform(async () => {
        const data = (await get_request(`${root}revisions/?limit=20&offset=${offset}`)).data;
        this.revisions = data.results;
        this.revisionCount = data.count;
        return data;
      });
    },
    loadRevision(id) {
      return this.perform(async () => (await get_request(`${root}revisions/${id}/`)).data);
    },
    loadProject(id) {
      return this.perform(async () => {
        this.project = (await get_request(`${root}projects/${id}/`)).data;
        return this.project;
      });
    },
    loadProjectVersion(id) {
      const request = ++this.versionRequest;
      this.projectVersion = null;
      return this.perform(async () => {
        const data = (await get_request(`${root}project-versions/${id}/`)).data;
        if (request !== this.versionRequest) return null;
        this.projectVersion = data;
        return data;
      });
    },
    createDraft(projectId, payload) {
      return this.perform(async () => (await create_request(`${root}projects/${projectId}/`, payload)).data);
    },
    saveDraft(id, payload) {
      return this.perform(async () => (await patch_request(`${root}project-versions/${id}/`, payload)).data);
    },
    approveDraft(id, payload) {
      return this.perform(async () => (await create_request(`${root}project-versions/${id}/approve/`, payload)).data);
    },
    getEstimate(id) {
      return this.perform(async () => (await get_request(`${root}estimates/${id}/`)).data);
    },
    loadActualHistory(id, offset = 0) {
      return this.perform(async () => (await get_request(`${root}estimates/${id}/actuals/?limit=3&offset=${offset}`)).data);
    },
    loadCalibration(offset = 0) {
      return this.perform(async () => {
        this.calibration = (await get_request(`${root}calibration/?limit=20&offset=${offset}`)).data;
        return this.calibration;
      });
    },
    loadEstimates(offset = 0) {
      return this.perform(async () => {
        const data = (await get_request(`${root}estimates/?limit=20&offset=${offset}`)).data;
        this.estimates = data.results;
        this.estimateCount = data.count;
        return data;
      });
    },
    recordActual(payload) {
      return this.perform(async () => (await create_request(`${root}actuals/`, payload)).data);
    },
  },
});

export { useRequirementCalculatorStore };
