import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'

// Authoring and decisions live in platform-delivery. This selector supplies
// published requirements to bug reports and change requests.
export const usePlatformRequirementsStore = defineStore('platformRequirements', {
  state: () => ({ requirements: [], isLoading: false, error: '' }),
  actions: {
    async fetchProjectRequirements(projectId) {
      this.isLoading = true
      this.error = ''
      try {
        const response = await usePlatformApi().get(`projects/${projectId}/requirements/`)
        this.requirements = response.data
        return { success: true, data: response.data }
      } catch (error) {
        this.error = error.response?.data?.detail || ''
        return { success: false, message: this.error }
      } finally {
        this.isLoading = false
      }
    },
  },
})
