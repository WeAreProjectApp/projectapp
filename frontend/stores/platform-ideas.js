import { defineStore } from 'pinia'
import { normalizeApiError } from '~/stores/services/normalize_api_error'
import { newRequestId } from '~/services/projectCollaborationRequests'

export const usePlatformIdeasStore = defineStore('platformIdeas', {
  state: () => ({ projectId: null, items: [], count: 0, page: 1, collections: [], collectionCount: 0, collectionPage: 1,
    loading: false, busy: false, error: '', generation: 0, collectionGeneration: 0, pendingRequests: {} }),
  actions: {
    reset(projectId = null) {
      this.generation += 1
      this.collectionGeneration += 1
      this.projectId = projectId
      this.items = []
      this.collections = []
      this.count = 0
      this.collectionCount = 0
      this.page = 1
      this.collectionPage = 1
      this.pendingRequests = {}
      this.error = ''
      this.busy = false
      this.loading = false
    },
    async load(projectId, api, page = 1) {
      if (String(this.projectId) !== String(projectId)) this.reset(projectId)
      const generation = ++this.generation
      this.loading = true
      this.error = ''
      try {
        const result = await api.list(page)
        if (generation !== this.generation) return false
        this.items = result.results
        this.count = result.count
        this.page = result.page
        return true
      } catch (error) {
        if (generation === this.generation) this.error = normalizeApiError(error).message
        return false
      } finally { if (generation === this.generation) this.loading = false }
    },
    async loadCollections(api, page = 1) {
      const projectId = this.projectId
      const generation = ++this.collectionGeneration
      const result = await api.collections(page)
      if (projectId === this.projectId && generation === this.collectionGeneration) {
        this.collections = result.results
        this.collectionCount = result.count
        this.collectionPage = result.page
      }
    },
    async mutate(api, operation, { text, idea, selected, title } = {}) {
      const projectId = this.projectId
      this.busy = true
      this.error = ''
      try {
        let result
        if (operation === 'create' || operation === 'collect') {
          const body = operation === 'create' ? { text } : { title, items: selected.map((item) => ({ idea_id: item.id, expected_version: item.version })) }
          const signature = `${projectId}:${operation}:${JSON.stringify(body)}`
          const requestId = this.pendingRequests[signature] ||= newRequestId()
          result = await api[operation]({ ...body, request_id: requestId })
          if (projectId !== this.projectId) return null
          delete this.pendingRequests[signature]
        } else {
          result = await api[operation](idea.id, { expected_version: idea.version, ...(operation === 'edit' ? { text } : {}) })
        }
        if (projectId !== this.projectId) return null
        await this.load(projectId, api, this.page)
        return result
      } catch (error) {
        if (projectId === this.projectId) this.error = normalizeApiError(error).message
        return null
      } finally { if (projectId === this.projectId) this.busy = false }
    },
  },
})
