import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'

export const usePlatformProjectsStore = defineStore('platformProjects', {
  state: () => ({
    projects: [],
    currentProject: null,
    detailRequestId: 0,
    errorStatus: null,
    isLoading: false,
    isUpdating: false,
    error: '',
  }),

  getters: {
    developmentProjects: (state) => state.projects.filter(
      (p) => p.current_state?.operational_effect === 'development',
    ),
    activeProjects: (state) => state.projects.filter(
      (p) => p.current_state?.operational_effect === 'operating',
    ),
    suspendedProjects: (state) => state.projects.filter(
      (p) => p.current_state?.operational_effect === 'suspended',
    ),
    completedProjects: (state) => state.projects.filter(
      (p) => p.current_state?.operational_effect === 'completed',
    ),
    decommissionedProjects: (state) => state.projects.filter(
      (p) => p.current_state?.operational_effect === 'decommissioned',
    ),
    projectCount: (state) => state.projects.length,
  },

  actions: {
    async fetchProjects(filters = {}) {
      this.isLoading = true
      this.error = ''

      try {
        const { get } = usePlatformApi()
        const params = new URLSearchParams()
        if (filters.client) params.append('client', filters.client)
        if (filters.status) params.append('status', filters.status)
        const query = params.toString() ? `projects/?${params}` : 'projects/'
        const response = await get(query)
        this.projects = response.data
        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos cargar los proyectos.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async fetchProject(projectId) {
      const requestId = ++this.detailRequestId
      this.isLoading = true
      this.error = ''
      this.errorStatus = null
      this.currentProject = null

      try {
        const { get } = usePlatformApi()
        const response = await get(`projects/${projectId}/`)
        if (requestId !== this.detailRequestId) return { success: false, stale: true }
        this.currentProject = response.data
        return { success: true, data: response.data }
      } catch (error) {
        if (requestId !== this.detailRequestId) return { success: false, stale: true }
        const message = error.response?.data?.detail || 'No pudimos cargar el proyecto.'
        this.error = message
        this.errorStatus = error.response?.status ?? null
        return { success: false, message, status: this.errorStatus }
      /* c8 ignore next 3 */
      } finally {
        if (requestId === this.detailRequestId) this.isLoading = false
      }
    },

    async createProject(payload) {
      this.isUpdating = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const response = await post('projects/', payload)
        this.projects = [response.data, ...this.projects]
        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos crear el proyecto.'
        this.error = message
        return { success: false, message, errors: error.response?.data }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async updateProject(projectId, payload) {
      this.isUpdating = true
      this.error = ''

      try {
        const { patch } = usePlatformApi()
        const response = await patch(`projects/${projectId}/`, payload)

        this.projects = this.projects.map((p) =>
          p.id === projectId ? response.data : p,
        )
        if (this.currentProject?.id === projectId) {
          this.currentProject = response.data
        }

        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos actualizar el proyecto.'
        this.error = message
        return { success: false, message, errors: error.response?.data }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async fetchAccessList() {
      this.error = ''
      try {
        const { get } = usePlatformApi()
        const response = await get('projects/access/')
        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos cargar los accesos.'
        this.error = message
        return { success: false, message }
      }
    },

    // ==========================================================================
    // Project phases (platform IA refactor)
    // ==========================================================================

    async loadPhases(projectId) {
      const { get } = usePlatformApi()
      const r = await get(`projects/${projectId}/phases/`)
      return r.data
    },

    async addPhase(projectId, proposalId, order = null) {
      const { post } = usePlatformApi()
      const body = { proposal_id: proposalId }
      if (order !== null) body.order = order
      const r = await post(`projects/${projectId}/phases/`, body)
      return { success: true, phase: r.data }
    },

    async removePhase(projectId, phaseId) {
      const { delete: del } = usePlatformApi()
      await del(`projects/${projectId}/phases/${phaseId}/`)
      return { success: true }
    },

    async reorderPhases(projectId, items) {
      const { patch } = usePlatformApi()
      const r = await patch(`projects/${projectId}/phases/reorder/`, items)
      return { success: true, phases: r.data }
    },

    async loadEligibleProposals(clientId) {
      const { get } = usePlatformApi()
      const r = await get(`clients/${clientId}/eligible-proposals/`)
      return r.data
    },
  },
})
