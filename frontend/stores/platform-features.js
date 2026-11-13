import { defineStore } from 'pinia'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { featureForRoute, featureForTarget, platformFeatureCatalog } from '~/utils/platformFeatures'

const pending = new WeakMap()

export const usePlatformFeaturesStore = defineStore('platform-features', {
  state: () => ({ features: {}, userId: null, loaded: false, error: false, generation: 0 }),
  actions: {
    reset() {
      this.generation += 1
      this.features = {}
      this.userId = null
      this.loaded = false
      this.error = false
      pending.delete(this)
    },
    enabled(key) {
      const auth = usePlatformAuthStore()
      return auth.isAdmin || (this.userId === auth.user?.user_id && this.loaded && this.features[key] === true)
    },
    routeAllowed(path) {
      const key = featureForRoute(path)
      return !key || this.enabled(key)
    },
    targetAllowed(target) {
      const key = featureForTarget(target)
      return !key || this.enabled(key)
    },
    markDisabled(key) {
      if (this.userId === usePlatformAuthStore().user?.user_id) this.features[key] = false
    },
    async refresh() {
      const auth = usePlatformAuthStore()
      const userId = auth.user?.user_id
      if (!auth.isAuthenticated || !userId) { this.reset(); return false }
      if (this.userId !== userId) { this.reset(); this.userId = userId }
      if (auth.isAdmin) { this.loaded = true; return true }
      if (pending.has(this)) return pending.get(this)
      const generation = this.generation
      const task = (async () => {
        try {
          const { data } = await usePlatformApi().get('/api/platform/features/', { baseURL: '' })
          if (generation !== this.generation || userId !== auth.user?.user_id) return false
          if (data?.user_id !== userId || !platformFeatureCatalog.features.every(item => typeof data.features?.[item.key] === 'boolean')) {
            throw new Error('Invalid availability response')
          }
          this.features = data.features
          this.loaded = true
          this.error = false
          return true
        } catch {
          if (generation === this.generation) { this.features = {}; this.loaded = false; this.error = true }
          return false
        } finally {
          if (generation === this.generation) pending.delete(this)
        }
      })()
      pending.set(this, task)
      return task
    },
  },
})
