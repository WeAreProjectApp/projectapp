import { defineStore } from 'pinia'
import { issueError } from '~/utils/issue-reports'
import { buildPlatformListUrl } from '~/composables/useIncludeArchivedQuery'
import { usePlatformApi } from '~/composables/usePlatformApi'

export const usePlatformChangeRequestsStore = defineStore('platformChangeRequests', {
  state: () => ({
    changeRequests: [],
    currentChangeRequest: null,
    projectId: null,
    isLoading: false,
    isUpdating: false,
    error: '',
  }),

  getters: {
    pendingCount: (state) => state.changeRequests.filter((cr) => cr.status === 'pending').length,
    evaluatingCount: (state) => state.changeRequests.filter((cr) => cr.status === 'evaluating').length,
    approvedCount: (state) => state.changeRequests.filter((cr) => cr.status === 'approved').length,
    rejectedCount: (state) => state.changeRequests.filter((cr) => cr.status === 'rejected').length,

    filteredByStatus: (state) => (statusFilter) => {
      if (!statusFilter || statusFilter === 'all') return state.changeRequests
      return state.changeRequests.filter((cr) => cr.status === statusFilter)
    },
  },

  actions: {
    async fetchChangeRequests(projectId, statusFilter = null, includeArchived = false) {
      this.isLoading = true
      this.error = ''
      this.projectId = projectId

      try {
        const { get } = usePlatformApi()
        const url = buildPlatformListUrl(
          `projects/${projectId}/change-requests/`,
          statusFilter ? { status: statusFilter } : {},
          includeArchived,
        )
        const response = await get(url)
        this.changeRequests = response.data
        return { success: true }
      } catch (error) {
        const message = issueError(error, 'No pudimos cargar las solicitudes de cambio.')
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async fetchChangeRequest(projectId, crId) {
      this.isLoading = true
      this.error = ''

      try {
        const { get } = usePlatformApi()
        const response = await get(`projects/${projectId}/change-requests/${crId}/`)
        this.currentChangeRequest = response.data
        return { success: true, data: response.data }
      } catch (error) {
        const message = issueError(error, 'No pudimos cargar la solicitud de cambio.')
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async createChangeRequest(projectId, payload) {
      this.isUpdating = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const hasFile = payload instanceof FormData
        const response = await post(`projects/${projectId}/change-requests/`, payload, hasFile ? {
          headers: { 'Content-Type': 'multipart/form-data' },
        } : {})
        this.changeRequests.unshift(response.data)
        return { success: true, data: response.data }
      } catch (error) {
        const message = issueError(error, 'No pudimos crear la solicitud de cambio.')
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async fetchAllChangeRequests(statusFilter = null, includeArchived = false) {
      this.isLoading = true
      this.error = ''
      this.projectId = null

      try {
        const { get } = usePlatformApi()
        const url = buildPlatformListUrl(
          'change-requests/',
          statusFilter ? { status: statusFilter } : {},
          includeArchived,
        )
        const response = await get(url)
        this.changeRequests = response.data
        return { success: true }
      } catch (error) {
        const message = issueError(error, 'No pudimos cargar las solicitudes de cambio.')
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async evaluateChangeRequest(projectId, crId, payload) {
      this.isUpdating = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/change-requests/${crId}/evaluate/`, payload)

        const idx = this.changeRequests.findIndex((cr) => cr.id === crId)
        if (idx !== -1) this.changeRequests[idx] = { ...this.changeRequests[idx], ...response.data }
        if (this.currentChangeRequest?.id === crId) {
          this.currentChangeRequest = response.data
        }

        return { success: true, data: response.data }
      } catch (error) {
        const message = issueError(error, 'No pudimos evaluar la solicitud de cambio.')
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async bulkEvaluateChangeRequests(projectId, items) {
      this.isUpdating = true
      this.error = ''
      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/change-requests/bulk-evaluate/`, items)
        return { success: true, data: response.data }
      } catch (error) {
        const message = issueError(error, 'No pudimos aplicar las respuestas masivas.')
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async deleteChangeRequest(projectId, crId) {
      this.isUpdating = true
      this.error = ''

      try {
        const { delete: destroy } = usePlatformApi()
        const { data } = await destroy(`projects/${projectId}/change-requests/${crId}/`)
        this.changeRequests = this.changeRequests.filter((cr) => cr.id !== crId)
        return { success: true, message: data?.detail || '' }
      } catch (error) {
        const message = issueError(error, 'No pudimos archivar la solicitud de cambio.')
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async addComment(projectId, crId, content, isInternal = false, options = {}) {
      this.error = ''
      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/change-requests/${crId}/comments/`, {
          content,
          is_internal: isInternal,
          ...options,
        })

        if (this.currentChangeRequest?.id === crId && this.currentChangeRequest.comments) {
          this.currentChangeRequest.comments.push(response.data)
        }

        return { success: true, data: response.data }
      } catch (error) {
        const message = issueError(error, 'No pudimos agregar el comentario.')
        this.error = message
        return { success: false, message }
      }
    },

    async convertToRequirement(projectId, crId, payload) {
      this.isUpdating = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/change-requests/${crId}/convert/`, payload)

        const idx = this.changeRequests.findIndex((cr) => cr.id === crId)
        if (idx !== -1) this.changeRequests[idx] = { ...this.changeRequests[idx], ...response.data }
        if (this.currentChangeRequest?.id === crId) {
          this.currentChangeRequest = response.data
        }

        return { success: true, data: response.data }
      } catch (error) {
        const message = issueError(error, 'No pudimos convertir la solicitud en requerimiento.')
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },
  },
})
