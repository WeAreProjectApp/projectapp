import { defineStore } from 'pinia'
import { normalizeApiError } from '~/stores/services/normalize_api_error'

function limitedEnvironments(environments) {
  return environments.filter((entry) => ['production', 'staging'].includes(entry.environment)).map((entry) => {
    const item = { environment: entry.environment }
    for (const field of ['site_url', 'admin_url']) if (typeof entry[field] === 'string') item[field] = entry[field]
    if (Array.isArray(entry.credential_actions)) item.credential_actions = entry.credential_actions.filter((field) => ['admin_username', 'admin_password'].includes(field))
    return item
  })
}

export const usePlatformClientAccessStore = defineStore('platformClientAccess', {
  state: () => ({ projectId: null, environments: [], loading: false, error: '', generation: 0 }),
  actions: {
    clear() { this.generation += 1; this.environments = []; this.projectId = null; this.error = ''; this.loading = false },
    async load(projectId, api) {
      this.projectId = projectId
      this.environments = []
      this.loading = true
      this.error = ''
      const generation = ++this.generation
      try {
        const result = await api.client()
        if (generation !== this.generation || String(result.project_id) !== String(projectId)) return false
        this.environments = limitedEnvironments(result.environments)
        return true
      } catch (error) {
        if (generation === this.generation) this.error = normalizeApiError(error).message
        return false
      } finally { if (generation === this.generation) this.loading = false }
    },
  },
})
