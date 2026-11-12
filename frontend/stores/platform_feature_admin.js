import { defineStore } from 'pinia'
import { get_request, patch_request } from '~/stores/services/request_http'

const base = 'platform/features/admin/'

export const usePlatformFeatureAdminStore = defineStore('platform_feature_admin', {
  state: () => ({ settings: null, clients: { results: [], page: 1, count: 0 }, client: null, events: null }),
  actions: {
    async load() { this.settings = (await get_request(base)).data },
    async searchClients(search = '', page = 1) {
      this.clients = (await get_request(`${base}clients/?search=${encodeURIComponent(search)}&page=${page}`)).data
    },
    async selectClient(id) { this.client = (await get_request(`${base}clients/${id}/`)).data },
    async save(values, client = false) {
      const scope = client ? this.client : this.settings
      const { data } = await patch_request(client ? `${base}clients/${scope.user_id}/` : base,
        { expected_version: scope.version, values })
      if (client) this.client = data
      else { this.settings = data; if (this.client) await this.selectClient(this.client.user_id) }
      return data
    },
    async loadEvents(page = 1) { this.events = (await get_request(`${base}events/?page=${page}`)).data },
  },
})

