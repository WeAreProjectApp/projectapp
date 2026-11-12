import { defineStore } from 'pinia'
import { get_request, create_request } from '~/stores/services/request_http'

export const useDataIntegrityStore = defineStore('data-integrity', {
  state: () => ({ findings: { results: [], count: 0, page: 1, pages: 1 }, scans: [], lastCompletedScan: null, operations: [], reviews: [] }),
  actions: {
    async loadFindings(params = {}) {
      this.findings = (await get_request(`data-integrity/findings/?${new URLSearchParams(params)}`)).data
    },
    async loadScans() {
      const data = (await get_request('data-integrity/scans/')).data
      this.scans = data.results
      this.lastCompletedScan = data.last_completed || null
    },
    async loadHistory(page = 1) {
      const [operations, reviews] = await Promise.all([
        get_request(`data-integrity/operations/?page=${page}`), get_request('data-integrity/reviews/'),
      ])
      this.operations = operations.data
      this.reviews = reviews.data.results
    },
    async startScan(data) { return (await create_request('data-integrity/scans/', data)).data },
    async getScan(id) { return (await get_request(`data-integrity/scans/${id}/`)).data },
    async preview(data) { return (await create_request('data-integrity/fixes/preview/', data)).data },
    async apply(data) { return (await create_request('data-integrity/fixes/apply/', data)).data },
    async undoPreview(id) { return (await get_request(`data-integrity/operations/${id}/undo/`)).data },
    async undo(id, data) { return (await create_request(`data-integrity/operations/${id}/undo/`, data)).data },
    async review(data) { return (await create_request('data-integrity/reviews/apply/', data)).data },
    async folders() { return (await get_request('document-folders/?scope=active')).data },
  },
})
