import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { issueError } from '~/utils/issue-reports'

export const usePlatformIssueReportsStore = defineStore('platformIssueReports', {
  state: () => ({ error: '' }),
  actions: {
    async contextOptions(projectId, params = {}) {
      this.error = ''
      try {
        const { get } = usePlatformApi()
        const response = await get(`projects/${projectId}/issue-reports/context-options/`, { params })
        return { success: true, data: response.data }
      } catch (error) {
        this.error = issueError(error, 'No pudimos cargar el contexto del ticket.')
        return { success: false, message: this.error }
      }
    },
  },
})
