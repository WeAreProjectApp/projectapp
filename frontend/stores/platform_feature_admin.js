import { defineStore } from 'pinia'
import { get_request, patch_request } from '~/stores/services/request_http'

const base = 'platform/features/admin/'

export const usePlatformFeatureAdminStore = defineStore('platform_feature_admin', {
  state: () => ({ settings: null, clients: { results: [], page: 1, count: 0 }, client: null, events: null, searchGeneration: 0, clientsLoading: false, clientsError: false }),
  actions: {
    async load() { this.settings = (await get_request(base)).data },
    invalidateClients() {
      this.searchGeneration += 1
      this.clients = { results: [], page: 1, count: 0 }
      this.clientsLoading = true
      this.clientsError = false
    },
    cancelClients() {
      this.searchGeneration += 1
      this.clientsLoading = false
    },
    async searchClients(search = '', page = 1) {
      const generation = ++this.searchGeneration
      this.clients = { results: [], page, count: 0 }
      this.clientsLoading = true
      this.clientsError = false
      try {
        const { data } = await get_request(`${base}clients/?search=${encodeURIComponent(search)}&page=${page}`)
        if (generation === this.searchGeneration) this.clients = data
      } catch {
        if (generation === this.searchGeneration) this.clientsError = true
      } finally {
        if (generation === this.searchGeneration) this.clientsLoading = false
      }
    },
    async selectClient(id) { this.client = (await get_request(`${base}clients/${id}/`)).data },
    async save(values, client = false) {
      const scope = client ? this.client : this.settings
      const { data } = await patch_request(client ? `${base}clients/${scope.user_id}/` : base,
        { expected_version: scope.version, values })
      if (client) this.client = data
      else {
        this.settings = data
        if (this.client) {
          const id = this.client.user_id
          this.client = null
          try { await this.selectClient(id) } catch { /* Keep the saved global value; reselect the client to retry. */ }
        }
      }
      return data
    },
    async loadEvents(page = 1) { this.events = (await get_request(`${base}events/?page=${page}`)).data },
  },
})

