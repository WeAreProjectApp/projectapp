import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { normalizeBlobApiError } from '~/stores/services/normalize_api_error'

let fallbackRequestSequence = 0
const requestId = () => globalThis.crypto?.randomUUID?.() || `delivery-${Date.now()}-${++fallbackRequestSequence}`
const apiFailure = (error) => ({
  success: false,
  message: typeof error.response?.data?.detail === 'string' ? error.response.data.detail : '',
  status: error.response?.status,
  code: error.response?.data?.code || '',
  fields: error.response?.data || {},
})

export const usePlatformDeliveryStore = defineStore('platformDelivery', {
  state: () => ({
    projectId: null,
    workspace: null,
    documentOptions: [],
    proposalDocumentOptions: [],
    approvalFileOptions: [],
    evidenceMessages: [],
    isLoading: false,
    isUpdating: false,
    error: '',
    hasConflict: false,
    pendingRequests: {},
  }),
  getters: {
    version: (state) => state.workspace?.version ?? 0,
    contracts: (state) => state.workspace?.contracts || [],
    scopes: (state) => state.workspace?.scopes || [],
    stages: (state) => (state.workspace?.scopes || []).flatMap((scope) =>
      (scope.phases || []).flatMap((phase) => phase.stages || [])),
  },
  actions: {
    base(path = '') { return `projects/${this.projectId}/delivery/${path}` },
    async fetchDelivery(projectId) {
      this.isLoading = true
      this.error = ''
      if (String(this.projectId) !== String(projectId)) {
        this.workspace = null
        this.documentOptions = []
        this.proposalDocumentOptions = []
        this.approvalFileOptions = []
        this.evidenceMessages = []
        this.pendingRequests = {}
      }
      this.projectId = projectId
      try {
        const response = await usePlatformApi().get(this.base())
        this.workspace = response.data
        this.hasConflict = false
        return { success: true, data: response.data }
      } catch (error) {
        const failure = apiFailure(error)
        this.error = failure.message
        return failure
      } finally { this.isLoading = false }
    },
    async fetchDocumentOptions() {
      try {
        const response = await usePlatformApi().get(this.base('documents/options/'))
        this.documentOptions = response.data.documents || []
        this.proposalDocumentOptions = response.data.proposal_documents || []
        this.approvalFileOptions = response.data.approval_files || []
        return { success: true }
      } catch (error) { return apiFailure(error) }
    },
    async fetchPromptOptions() {
      try {
        const response = await usePlatformApi().get(this.base('prompt/options/'))
        return { success: true, data: response.data }
      } catch (error) { return apiFailure(error) }
    },
    async fetchPromptContext(id) {
      try {
        const response = await usePlatformApi().get(this.base(`prompt/${id}/`))
        return { success: true, data: response.data }
      } catch (error) { return apiFailure(error) }
    },
    async fetchPromptContexts() {
      try {
        const response = await usePlatformApi().get(this.base('prompt/contexts/'))
        return { success: true, data: response.data }
      } catch (error) { return apiFailure(error) }
    },
    async fetchEvidenceOptions() {
      try {
        const response = await usePlatformApi().get(this.base('evidence-options/'))
        this.evidenceMessages = response.data.messages || []
        return { success: true }
      } catch (error) { return apiFailure(error) }
    },
    retainClosureEmailVersion(data) {
      if (this.workspace && Number.isInteger(data?.version) && data.version >= this.version) this.workspace.version = data.version
    },
    async fetchClosureEmailHistory(stageId) {
      try {
        const response = await usePlatformApi().get(this.base(`stages/${stageId}/closure-email/history/`))
        this.retainClosureEmailVersion(response.data)
        return { success: true, data: response.data }
      } catch (error) { return apiFailure(error) }
    },
    async fetchClosureEmail(id) {
      try {
        const response = await usePlatformApi().get(this.base(`closure-emails/${id}/`))
        this.retainClosureEmailVersion(response.data)
        return { success: true, data: response.data }
      } catch (error) { return apiFailure(error) }
    },
    async mutateClosureEmail(path, payload = {}) {
      const result = await this.mutate(path, payload, 'POST', { refresh: false })
      if (result.success) this.retainClosureEmailVersion(result.data)
      return result
    },
    prepareClosureEmail(stageId, payload) { return this.mutateClosureEmail(`stages/${stageId}/closure-email/prepare/`, payload) },
    sendClosureEmail(id, payload) { return this.mutateClosureEmail(`closure-emails/${id}/send/`, payload) },
    prepareClosureEmailResend(id) { return this.mutateClosureEmail(`closure-emails/${id}/resend/prepare/`) },
    downloadClosureEmailAttachment(attachment) { return this.downloadPromptSource(attachment) },
    async mutate(path, payload = {}, method = 'POST', { refresh = true } = {}) {
      this.isUpdating = true
      this.error = ''
      const content = payload instanceof FormData ? [...payload.entries()].filter(([key]) => !['expected_version', 'request_id'].includes(key)).map(([key, value]) => [key, value instanceof File ? [value.name, value.size, value.lastModified] : value]) : payload
      const signature = `${method}:${path}:${this.version}:${JSON.stringify(content)}`
      const actionId = this.pendingRequests[signature] ||= requestId()
      const data = payload instanceof FormData ? payload : { ...payload, expected_version: this.version, request_id: actionId }
      if (data instanceof FormData) {
        data.set('expected_version', String(this.version))
        data.set('request_id', actionId)
      }
      try {
        const response = await usePlatformApi().request({
          url: this.base(path), method, data,
          ...(data instanceof FormData ? { headers: { 'Content-Type': 'multipart/form-data' } } : {}),
        })
        delete this.pendingRequests[signature]
        if (refresh) this.workspace = response.data
        this.hasConflict = false
        return { success: true, data: response.data }
      } catch (error) {
        const failure = apiFailure(error)
        this.error = failure.message
        this.hasConflict = failure.status === 409
        return failure
      } finally { this.isUpdating = false }
    },
    createEntity(type, payload) { return this.mutate(`${type}/`, payload) },
    updateEntity(type, id, payload) { return this.mutate(`${type}/${id}/`, payload, 'PATCH') },
    deleteEntity(type, id) { return this.mutate(`${type}/${id}/`, {}, 'DELETE') },
    previewImport(payload) { return this.mutate('import/preview/', { payload }, 'POST', { refresh: false }) },
    applyImport(payload) { return this.mutate('import/apply/', { payload }) },
    preparePrompt(selection) { return this.mutate('prompt/', selection, 'POST', { refresh: false }) },
    previewReply(payload) { return this.mutate('reply/preview/', { payload }, 'POST', { refresh: false }) },
    publishStage(id) { return this.mutate(`stages/${id}/publish/`) },
    reviewStage(id, payload) { return this.mutate(`stages/${id}/review/`, payload) },
    recordHistoricalApprovals(id, payload) { return this.mutate(`stages/${id}/historical-approvals/`, payload) },
    sendMessage(payload) { return this.mutate('messages/', payload) },
    recordExternalSignature(type, id, payload) { return this.mutate(`${type}/${id}/signature-external/`, payload) },
    linkDocument(payload) { return this.mutate('documents/', payload) },
    unlinkDocument(id) { return this.mutate(`documents/${id}/`, {}, 'DELETE') },
    async downloadPromptSource(source) {
      try {
        const response = await usePlatformApi().get(source.file_url || source.download_url, { responseType: 'blob', baseURL: '' })
        const mimeType = response.headers?.['content-type'] || source.content_type || 'application/octet-stream'
        const objectUrl = URL.createObjectURL(new Blob([response.data], { type: mimeType }))
        const link = window.document.createElement('a')
        link.href = objectUrl
        const headerFilename = response.headers?.['content-disposition']?.match(/filename="([^"]+)"/)?.[1]
        link.download = (source.filename || headerFilename || source.title || 'source').replace(/[\\/]/g, '-')
        window.document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(objectUrl)
        return { success: true }
      } catch (error) {
        const failure = await normalizeBlobApiError(error, '')
        return { success: false, message: failure.message }
      }
    },
    downloadContractSource(source) {
      return this.downloadPromptSource({
        download_url: source.source_download_url, filename: source.source_filename,
        content_type: source.source_content_type, title: source.title,
      })
    },
    async downloadDocument(document) {
      try {
        const response = await usePlatformApi().get(document.pdf_url, {
          responseType: 'blob', ...(document.pdf_url.startsWith('/') ? { baseURL: '' } : {}),
        })
        const objectUrl = URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
        const link = window.document.createElement('a')
        link.href = objectUrl
        link.download = `${(document.title || 'document').replace(/[\\/]/g, '-')}.pdf`
        window.document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(objectUrl)
        return { success: true }
      } catch (error) {
        const failure = await normalizeBlobApiError(error, '')
        return { success: false, message: failure.message }
      }
    },
  },
})
