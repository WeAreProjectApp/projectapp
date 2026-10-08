import { defineStore } from 'pinia'
import { buildPlatformListUrl } from '~/composables/useIncludeArchivedQuery'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { normalizeBlobApiError } from '~/stores/services/normalize_api_error'
import { downloadBlob, filenameFromDisposition } from '~/utils/downloadFile'

export const usePlatformDeliverablesStore = defineStore('platformDeliverables', {
  state: () => ({
    deliverables: [],
    currentDeliverable: null,
    projectId: null,
    isLoading: false,
    isUpdating: false,
    error: '',
  }),

  getters: {
    groupedByCategory: (state) => {
      const groups = {}
      const order = ['designs', 'documents', 'contract', 'amendment', 'legal_annex', 'credentials', 'apks', 'other']
      for (const d of state.deliverables) {
        if (!groups[d.category]) groups[d.category] = []
        groups[d.category].push(d)
      }
      return order
        .filter((cat) => groups[cat]?.length)
        .map((cat) => ({ category: cat, items: groups[cat] }))
    },

    totalCount: (state) => state.deliverables.length,
  },

  actions: {
    async downloadFile(file) {
      const fallback = 'No pudimos descargar el archivo. Inténtalo de nuevo.'
      if (typeof file?.file_url !== 'string' || !file.file_url.startsWith('/api/accounts/')) {
        return { success: false, message: 'El archivo no tiene una descarga disponible.' }
      }
      try {
        const response = await usePlatformApi().get(file.file_url, { responseType: 'blob', baseURL: '' })
        const filename = filenameFromDisposition(response.headers?.['content-disposition']) || file.file_name || 'resource'
        downloadBlob(response.data, filename.replace(/[\\/]/g, '-'))
        return { success: true }
      } catch (error) {
        const failure = await normalizeBlobApiError(error, fallback)
        return { success: false, message: failure.message }
      }
    },

    async fetchDeliverables(projectId, category = null, includeArchived = false) {
      this.isLoading = true
      this.error = ''
      this.projectId = projectId

      try {
        const { get } = usePlatformApi()
        const url = buildPlatformListUrl(
          `projects/${projectId}/deliverables/`,
          category ? { category } : {},
          includeArchived,
        )
        const response = await get(url)
        this.deliverables = response.data
        return { success: true }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos cargar los entregables.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async fetchAllDeliverables(category = null, includeArchived = false) {
      this.isLoading = true
      this.error = ''
      this.projectId = null

      try {
        const { get } = usePlatformApi()
        const url = buildPlatformListUrl(
          'deliverables/',
          category ? { category } : {},
          includeArchived,
        )
        const response = await get(url)
        this.deliverables = response.data
        return { success: true }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos cargar los entregables.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async fetchDeliverable(projectId, deliverableId) {
      this.isLoading = true
      this.error = ''

      try {
        const { get } = usePlatformApi()
        const response = await get(`projects/${projectId}/deliverables/${deliverableId}/`)
        this.currentDeliverable = response.data
        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos cargar el entregable.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false
      }
    },

    async createDeliverable(projectId, formData) {
      this.isUpdating = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const response = await post(`projects/${projectId}/deliverables/`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        this.deliverables.unshift(response.data)
        return { success: true, data: response.data }
      } catch (error) {
        const data = error.response?.data || {}
        const fieldMsg = Array.isArray(data.file) ? data.file[0] : data.file
        const message = data.detail || fieldMsg || 'No pudimos subir el recurso.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async updateDeliverable(projectId, deliverableId, payload) {
      this.isUpdating = true
      this.error = ''

      try {
        const { patch } = usePlatformApi()
        const response = await patch(`projects/${projectId}/deliverables/${deliverableId}/`, payload)

        const idx = this.deliverables.findIndex((d) => d.id === deliverableId)
        if (idx !== -1) this.deliverables[idx] = { ...this.deliverables[idx], ...response.data }
        if (this.currentDeliverable?.id === deliverableId) {
          this.currentDeliverable = response.data
        }

        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos actualizar el entregable.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async deleteDeliverable(projectId, deliverableId) {
      this.isUpdating = true
      this.error = ''

      try {
        const { delete: destroy } = usePlatformApi()
        const { data } = await destroy(`projects/${projectId}/deliverables/${deliverableId}/`)
        this.deliverables = this.deliverables.filter((d) => d.id !== deliverableId)
        return { success: true, message: data?.detail || '' }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos archivar el entregable.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },

    async uploadNewVersion(projectId, deliverableId, formData) {
      this.isUpdating = true
      this.error = ''

      try {
        const { post } = usePlatformApi()
        const response = await post(
          `projects/${projectId}/deliverables/${deliverableId}/upload-version/`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } },
        )

        const idx = this.deliverables.findIndex((d) => d.id === deliverableId)
        if (idx !== -1) this.deliverables[idx] = { ...this.deliverables[idx], ...response.data }
        if (this.currentDeliverable?.id === deliverableId) {
          this.currentDeliverable = response.data
        }

        return { success: true, data: response.data }
      } catch (error) {
        const message = error.response?.data?.detail || 'No pudimos subir la nueva versión.'
        this.error = message
        return { success: false, message }
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false
      }
    },
  },
})
