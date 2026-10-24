import { defineStore } from 'pinia'
import { get_request, patch_request, put_request, create_request, delete_request } from './services/request_http'

const base = 'platform/ai/admin/'
export const usePlatformAIAdminStore = defineStore('platform-ai-admin', {
  state: () => ({ settings: null, templates: [], clients: { results: [], count: 0, page: 1 }, usage: null }),
  actions: {
    async load() { this.settings = (await get_request(`${base}settings/`)).data },
    async saveSettings(data) { this.settings = (await patch_request(`${base}settings/`, data)).data },
    async loadClients(search = '', page = 1) { this.clients = (await get_request(`${base}clients/`, { params: { search, page } })).data },
    async saveClient(client, field, enabled) {
      const saved = (await patch_request(`${base}clients/${client.user_id}/`, { [field]: enabled, expected_version: client.version })).data
      this.clients.results = this.clients.results.map((row) => row.user_id === saved.user_id ? saved : row)
    },
    async saveClientQuota(client, limit, minutes) {
      const saved = (await patch_request(`${base}clients/${client.user_id}/`, { ai_request_limit: limit, ai_window_minutes: minutes, expected_version: client.version })).data
      this.clients.results = this.clients.results.map((row) => row.user_id === saved.user_id ? saved : row)
    },
    async saveKey(provider, apiKey) {
      await put_request(`${base}credentials/${provider}/`, { api_key: apiKey, expected_version: this.settings.credentials[provider].version })
      await this.load()
    },
    async deleteKey(provider) { await delete_request(`${base}credentials/${provider}/`, { expected_version: this.settings.credentials[provider].version }); await this.load() },
    async testKey(provider) { await create_request(`${base}credentials/${provider}/test/`, {}); await this.load() },
    async loadTemplates() { this.templates = (await get_request(`${base}templates/`)).data },
    async saveTemplate(item, content) { await patch_request(`${base}templates/${item.id}/`, { content, expected_version: item.version }); await this.loadTemplates() },
    async previewTemplate(item, content) { return (await create_request(`${base}templates/${item.id}/preview/`, { content, expected_version: item.version })).data.preview },
    async versions(item) { return (await get_request(`${base}templates/${item.id}/versions/`)).data },
    async restoreTemplate(item, version) { await create_request(`${base}templates/${item.id}/restore/`, { version, expected_version: item.version }); await this.loadTemplates() },
    async loadUsage() { this.usage = (await get_request(`${base}usage/`)).data },
    async invalidate(functionName) { await create_request(`${base}cache/invalidate/`, { function: functionName }); await this.load() },
  },
})
