import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'

const keys = ['id', 'project', 'title', 'secret_type', 'type_label', 'language', 'audience', 'status', 'validity_days', 'expires_at', 'consumed_at', 'revoked_at', 'activation_count', 'created_at', 'updated_at', 'replaces', 'replaced_by', 'capabilities']
const metadata = (link) => Object.fromEntries(keys.filter(key => key in (link || {})).map(key => [key, link[key]]))
const knownErrors = new Set(['request_id_conflict', 'version_conflict', 'invalid_replacement', 'invalid_reactivation', 'secure_links_unavailable', 'invalid_content', 'invalid', 'not_found'])
const failure = (error) => ({ success: false, status: error.response?.status || 0, code: knownErrors.has(error.response?.data?.code) ? error.response.data.code : 'failed' })

export const usePlatformSecureLinksStore = defineStore('platformSecureLinks', {
  state: () => ({ projectId: null, links: [], types: [], counts: {}, count: 0, page: 1, loading: false, error: '', epoch: 0, listRequest: 0 }),
  actions: {
    clear() {
      this.epoch += 1
      this.projectId = null
      this.links = []
      this.types = []
      this.counts = {}
      this.count = 0
      this.page = 1
      this.loading = false
      this.error = ''
    },
    enterProject(projectId) {
      if (String(this.projectId) !== String(projectId)) {
        this.clear()
        this.projectId = projectId
      }
    },
    base(path = '') { return `projects/${this.projectId}/secure-links/${path}` },
    async fetchLinks(projectId, params = {}) {
      this.enterProject(projectId)
      const epoch = this.epoch
      const request = ++this.listRequest
      const url = this.base()
      this.loading = true
      this.error = ''
      try {
        const response = await usePlatformApi().get(url, { params })
        if (epoch !== this.epoch || request !== this.listRequest) return { success: false, stale: true }
        this.links = (response.data.results || []).map(metadata)
        this.counts = response.data.counts || {}
        this.count = response.data.count || 0
        this.page = response.data.page || 1
        return { success: true }
      } catch (error) {
        if (epoch !== this.epoch || request !== this.listRequest) return { success: false, stale: true }
        const result = failure(error)
        this.error = result.code
        return result
      } finally { if (epoch === this.epoch && request === this.listRequest) this.loading = false }
    },
    async fetchTypes() {
      const epoch = this.epoch
      try {
        const response = await usePlatformApi().get(this.base('types/'))
        if (epoch !== this.epoch) return { success: false, stale: true }
        this.types = response.data.types || []
        return { success: true }
      } catch (error) { return failure(error) }
    },
    async events(linkId, page = 1) {
      const epoch = this.epoch
      try {
        const response = await usePlatformApi().get(this.base(`${linkId}/events/`), { params: { page } })
        return epoch === this.epoch ? { success: true, data: response.data } : { success: false, stale: true }
      } catch (error) { return failure(error) }
    },
    async mutate(path, data = {}, method = 'post') {
      const epoch = this.epoch
      const url = this.base(path)
      try {
        const response = await usePlatformApi()[method](url, data)
        // URL and secret inputs stay in the caller's component, never Pinia.
        return epoch === this.epoch ? { success: true, data: response.data } : { success: false, stale: true }
      } catch (error) { return failure(error) }
    },
    create(data) { return this.mutate('', data) },
    rename(link, title) { return this.mutate(`${link.id}/`, { title, expected_updated_at: link.updated_at }, 'patch') },
    revoke(linkId) { return this.mutate(`${linkId}/revoke/`) },
    copyURL(linkId) { return this.mutate(`${linkId}/link/`) },
    reactivate(link, validityDays) { return this.mutate(`${link.id}/reactivate/`, { validity_days: Number(validityDays), expected_updated_at: link.updated_at }) },
  },
})
