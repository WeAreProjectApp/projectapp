import { defineStore } from 'pinia'
import { get_request, create_request, patch_request, delete_request } from './services/request_http'

export const useProcurementStore = defineStore('procurement', {
  state: () => ({ records: [], count: 0, detail: null, alerts: [], searches: [], deliveries: [], deliveryCount: 0,
    settings: null, sync: null, loading: false, saving: false, requestId: 0, detailId: 0 }),
  actions: {
    async list(options = {}) {
      const requestId = ++this.requestId
      this.loading = true
      try {
        const { data } = await get_request('procurement/opportunities/', { params: { ...options, filters: JSON.stringify(options.filters || {}) } })
        if (requestId === this.requestId) { this.records = data.results; this.count = data.count }
        return data
      } finally { if (requestId === this.requestId) this.loading = false }
    },
    async open(id) {
      const detailId = ++this.detailId
      const { data } = await get_request(`procurement/opportunities/${id}/`)
      if (detailId === this.detailId) this.detail = data
      return data
    },
    close() { this.detailId += 1; this.detail = null },
    async loadAlerts() { this.alerts = (await get_request('procurement/alerts/')).data },
    async loadSearches() { this.searches = (await get_request('procurement/searches/')).data },
    async loadSettings() { this.settings = (await get_request('procurement/settings/')).data },
    async loadSync() { this.sync = (await get_request('procurement/sync/')).data },
    async loadDeliveries(page = 1) {
      const { data } = await get_request('procurement/deliveries/', { params: { page } })
      this.deliveries = data.results; this.deliveryCount = data.count
    },
    async mutate(action) {
      this.saving = true
      try { return await action() } finally { this.saving = false }
    },
    async saveAlert(payload, id) {
      return this.mutate(async () => {
        const { data } = await (id ? patch_request(`procurement/alerts/${id}/`, payload) : create_request('procurement/alerts/', payload))
        await this.loadAlerts(); return data
      })
    },
    async saveSearch(payload, id) {
      return this.mutate(async () => {
        const { data } = await (id ? patch_request(`procurement/searches/${id}/`, payload) : create_request('procurement/searches/', payload))
        await this.loadSearches(); return data
      })
    },
    async removeSearch(id) { return this.mutate(async () => { await delete_request(`procurement/searches/${id}/`); await this.loadSearches() }) },
    async saveSettings(payload) { return this.mutate(async () => { this.settings = (await patch_request('procurement/settings/', payload)).data }) },
    async classify(id, payload) { return this.mutate(async () => { await create_request(`procurement/opportunities/${id}/classification/`, payload); await this.open(id) }) },
    async restore(id) { return this.mutate(async () => { await create_request(`procurement/opportunities/${id}/restore/`, {}); await this.open(id) }) },
    async getDelivery(id) { return (await get_request(`procurement/deliveries/${id}/`)).data },
    async requestSync() { await create_request('procurement/sync/', {}); await this.loadSync() },
    async retry(id) { return this.mutate(async () => { await create_request(`procurement/deliveries/${id}/retry/`, {}); await this.loadDeliveries() }) },
    async export(options) {
      return (await get_request('procurement/export/', { responseType: 'blob', params: { ...options, filters: JSON.stringify(options.filters || {}) } })).data
    },
  },
})
