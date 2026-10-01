import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { issueError } from '~/utils/issue-reports'

export const usePlatformIssueReportsStore = defineStore('platformIssueReports', {
  state: () => ({ error: '' }),
  actions: {
    async replyRequest(projectId, kind, ticketId, path, payload, { blob = false } = {}) {
      this.error = ''
      try {
        const { get, post } = usePlatformApi()
        const url = `projects/${projectId}/issue-reports/${kind}/${ticketId}/reply/${path}`
        const response = payload === undefined ? await get(url, blob ? { responseType: 'blob' } : {}) : await post(url, payload)
        return { success: true, data: response.data }
      } catch (error) {
        this.error = issueError(error, 'No pudimos preparar la respuesta del ticket.')
        return { success: false, message: this.error, status: error.response?.status }
      }
    },
    replyOptions(projectId, kind, ticketId) {
      return this.replyRequest(projectId, kind, ticketId, 'options/')
    },
    prepareReply(projectId, kind, ticketId, payload) {
      return this.replyRequest(projectId, kind, ticketId, 'contexts/', payload)
    },
    previewReply(projectId, kind, ticketId, payload) {
      return this.replyRequest(projectId, kind, ticketId, 'preview/', payload)
    },
    replyContext(projectId, kind, ticketId, contextId) {
      return this.replyRequest(projectId, kind, ticketId, `contexts/${contextId}/`)
    },
    downloadReplySource(projectId, kind, ticketId, contextId, sourceKey) {
      return this.replyRequest(projectId, kind, ticketId, `contexts/${contextId}/sources/${encodeURIComponent(sourceKey)}/`, undefined, { blob: true })
    },
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
