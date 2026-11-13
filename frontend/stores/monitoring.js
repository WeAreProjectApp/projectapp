import { defineStore } from 'pinia'
import { get_request, create_request } from './services/request_http'

const catalogRequests = new WeakMap()

export const useMonitoringStore = defineStore('monitoring', {
  state: () => ({
    resources: [], sources: [], records: [], count: 0, pageSize: 25,
    detail: null, loading: false, saving: false, error: '', requestId: 0, detailId: 0,
    snapshot: '', revision: '', capturedAt: '', summary: null, attention: [], snapshotSources: null, currentPage: 1, expired: false,
  }),
  actions: {
    async catalog() {
      if (catalogRequests.has(this)) return catalogRequests.get(this)

      const request = get_request('monitoring/catalog/').then(({ data }) => {
        this.resources = data.resources
        this.sources = data.sources
      }).finally(() => { catalogRequests.delete(this) })
      catalogRequests.set(this, request)
      return request
    },
    async list(params, reports = false) {
      const requestId = ++this.requestId
      this.loading = true
      this.error = ''
      this.expired = false
      try {
        const { data } = await get_request(`monitoring/${reports ? 'reports' : 'cases'}/`, { params })
        if (requestId !== this.requestId) return
        this.records = data.results
        this.count = data.count
        this.pageSize = data.page_size
        this.currentPage = data.page || params.page || 1
        this.snapshot = data.snapshot || ''
        this.revision = data.revision || ''
        this.capturedAt = data.captured_at || ''
        this.summary = data.summary || null
        this.attention = data.attention || []
        this.snapshotSources = data.sources ?? null
        return true
      } catch (error) {
        if (requestId === this.requestId) {
          this.error = error.response?.data?.detail || 'load'
          this.records = []
          this.count = 0
          this.summary = null
          this.attention = []
          this.snapshotSources = null
          this.expired = error.response?.status === 409
        }
        return false
      } finally {
        if (requestId === this.requestId) this.loading = false
      }
    },
    async open(id, reports = false, page = 1, pages = {}) {
      const detailId = ++this.detailId
      const { data } = await get_request(`monitoring/${reports ? 'reports' : 'cases'}/${id}/`, { params: { page, ...pages } })
      if (detailId === this.detailId) this.detail = data
    },
    close() {
      this.detailId += 1
      this.detail = null
    },
    async transition(state, pages = {}) {
      this.saving = true
      try {
        const { id, version } = this.detail
        const detailId = this.detailId
        await create_request(`monitoring/cases/${id}/state/`, { state, version })
        if (detailId === this.detailId) await this.open(id, false, 1, pages)
      } finally { this.saving = false }
    },
    async note(text, pages = {}) {
      this.saving = true
      try {
        const id = this.detail.id
        const detailId = this.detailId
        await create_request(`monitoring/cases/${id}/notes/`, { text })
        if (detailId === this.detailId) await this.open(id, false, 1, pages)
      } finally { this.saving = false }
    },
  },
})
