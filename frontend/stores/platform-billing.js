import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'

export const usePlatformBillingStore = defineStore('platformBilling', {
  state: () => ({
    accounts: [], account: null, hosting: null, hostingProjects: [], options: null,
    loading: {}, errors: {}, requests: {},
  }),
  actions: {
    clear(slot, empty = null) {
      this.requests[slot] = (this.requests[slot] || 0) + 1
      this[slot] = empty
      this.loading[slot] = false
      this.errors[slot] = ''
    },
    async read(slot, url, params = {}, empty = null) {
      const request = (this.requests[slot] || 0) + 1
      this.requests[slot] = request
      this[slot] = empty
      this.errors[slot] = ''
      this.loading[slot] = true
      try {
        const response = await usePlatformApi().get(url, { params })
        if (this.requests[slot] !== request) return { success: false, stale: true }
        this[slot] = response.data
        return { success: true, data: response.data }
      } catch (error) {
        if (this.requests[slot] !== request) return { success: false, stale: true }
        const message = error.response?.data?.detail || error.message
        this.errors[slot] = typeof message === 'string' ? message : ''
        return { success: false, message }
      } finally {
        if (this.requests[slot] === request) this.loading[slot] = false
      }
    },
    fetchAccounts(params = {}) { return this.read('accounts', 'collection-accounts/', params, []) },
    fetchAccount(id) { return this.read('account', `collection-accounts/${id}/`) },
    fetchHosting(projectId) { return this.read('hosting', `projects/${projectId}/hosting-context/`) },
    fetchHostingProjects() { return this.read('hostingProjects', 'hosting/', {}, []) },
    fetchOptions(projectId) { return this.read('options', `projects/${projectId}/billing-options/`) },
  },
})
