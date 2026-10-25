import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'

const base = '/api/platform/chatbot/'
const config = { baseURL: '' }
const pending = new WeakMap()
const epochs = new WeakMap()
const capabilityReads = new WeakMap()
const epoch = (store) => epochs.get(store) || 0
const bump = (store) => { const value = epoch(store) + 1; epochs.set(store, value); return value }

export const usePlatformChatbotStore = defineStore('platform-chatbot', {
  state: () => ({
    capabilities: null, quota: null, projects: [], conversations: [], messages: [], conversation: null,
    selectedProjectId: null, draft: '', nextBefore: null, isLoading: false, isSubmitting: false, error: false,
    hintSeen: false, lastRequest: null, actorId: null,
  }),
  getters: {
    enabled: (state) => state.capabilities?.chatbot?.enabled === true,
    available: (state) => state.capabilities?.chatbot?.available === true,
    voiceAvailable: (state) => state.capabilities?.chatbot?.voice_available === true,
    waiting: (state) => state.messages.some((row) => ['pending', 'processing'].includes(row.status)),
  },
  actions: {
    stopPolling() { pending.get(this)?.abort(); pending.delete(this) },
    resetSession() { this.stopPolling(); bump(this); this.$reset() },
    bindActor(id) { const key = id == null ? null : String(id); if (this.actorId !== key) { this.resetSession(); this.actorId = key } },
    async refreshCapabilities() {
      const token = epoch(this), read = (capabilityReads.get(this) || 0) + 1
      capabilityReads.set(this, read)
      try {
        const response = await usePlatformApi().get('/api/platform/ai/capabilities/', config)
        if (token !== epoch(this) || read !== capabilityReads.get(this)) return null
        this.capabilities = response.data
        this.quota = this.capabilities.quota
      } catch { if (token === epoch(this) && read === capabilityReads.get(this)) this.capabilities = null }
      return this.capabilities
    },
    async initialize() {
      const token = epoch(this)
      this.isLoading = true; this.error = false
      try {
        await this.refreshCapabilities()
        if (token !== epoch(this) || !this.available) return
        const [projects, conversations] = await Promise.all([
          usePlatformApi().get('projects/'), usePlatformApi().get(`${base}conversations/`, config),
        ])
        if (token !== epoch(this)) return
        this.projects = projects.data
        this.conversations = conversations.data.results
      } catch { if (token === epoch(this)) this.error = true }
      finally { if (token === epoch(this)) this.isLoading = false }
    },
    async openConversation(id) {
      const token = bump(this)
      this.stopPolling(); this.error = false
      try {
        const { data } = await usePlatformApi().get(`${base}conversations/${id}/`, config)
        if (token !== epoch(this)) return
        this.conversation = data.conversation; this.messages = data.messages; this.quota = data.quota; this.nextBefore = data.next_before
        this.selectedProjectId = data.conversation.project_id
        const active = data.messages.find((row) => ['pending', 'processing'].includes(row.status))
        if (active) this.poll(active.id)
      } catch { if (token === epoch(this)) { this.error = true; await this.refreshCapabilities() } }
    },
    newConversation(projectId = this.selectedProjectId) {
      bump(this)
      this.stopPolling(); this.conversation = null; this.messages = []; this.nextBefore = null; this.lastRequest = null
      this.selectedProjectId = projectId ? Number(projectId) : null
    },
    async ensureConversation(language) {
      const token = epoch(this)
      if (this.conversation && this.conversation.language === language) return this.conversation
      const { data } = await usePlatformApi().post(`${base}conversations/`, { project_id: this.selectedProjectId, language }, config)
      if (token !== epoch(this)) return null
      this.conversation = data; this.messages = []; this.conversations.unshift(data)
      return data
    },
    upsert(message) {
      const index = this.messages.findIndex((row) => row.id === message.id)
      if (index >= 0) this.messages.splice(index, 1, message)
      else this.messages.push(message)
      if (message.quota) this.quota = message.quota
    },
    async send(question, language, transcriptionId = null) {
      const token = epoch(this)
      this.error = false; this.isSubmitting = true
      try {
        const conversation = await this.ensureConversation(language)
        if (!conversation || token !== epoch(this)) return false
        const signature = JSON.stringify([conversation.id, question, transcriptionId])
        if (this.lastRequest?.signature !== signature) this.lastRequest = { signature, id: crypto.randomUUID(), transcriptionId }
        const body = { request_id: this.lastRequest.id, question, ...(transcriptionId ? { transcription_id: transcriptionId } : {}) }
        const { data } = await usePlatformApi().post(`${base}conversations/${conversation.id}/messages/`, body, config)
        if (token !== epoch(this)) return false
        this.upsert(data)
        if (data.status !== 'failed') this.draft = ''
        if (['pending', 'processing'].includes(data.status)) this.poll(data.id)
        else if (data.status !== 'failed') this.lastRequest = null
        return true
      } catch {
        if (token === epoch(this)) { this.error = true; await this.refreshCapabilities() }
        return false
      } finally { if (token === epoch(this)) this.isSubmitting = false }
    },
    async poll(id) {
      this.stopPolling()
      const controller = new AbortController(); pending.set(this, controller)
      const conversationId = this.conversation?.id
      const began = Date.now()
      try {
        while (!controller.signal.aborted && Date.now() - began < 150000) {
          await new Promise((resolve) => {
            const done = () => { clearTimeout(handle); controller.signal.removeEventListener('abort', done); resolve() }
            const handle = setTimeout(done, 1500)
            controller.signal.addEventListener('abort', done, { once: true })
          })
          if (controller.signal.aborted) return
          const { data } = await usePlatformApi().get(`${base}conversations/${conversationId}/messages/${id}/`, { ...config, signal: controller.signal })
          if (controller.signal.aborted || this.conversation?.id !== conversationId) return
          this.upsert(data)
          if (!['pending', 'processing'].includes(data.status)) { if (data.status !== 'failed') this.lastRequest = null; return }
        }
        if (!controller.signal.aborted) this.error = true
      } catch { if (!controller.signal.aborted) { this.error = true; await this.refreshCapabilities() } }
      finally { if (pending.get(this) === controller) pending.delete(this) }
    },
    async loadOlder() {
      if (!this.conversation || !this.nextBefore || this.isLoading) return
      this.isLoading = true
      const token = epoch(this)
      try {
        const { data } = await usePlatformApi().get(`${base}conversations/${this.conversation.id}/`, { ...config, params: { before: this.nextBefore } })
        if (token !== epoch(this)) return
        this.messages.unshift(...data.messages.filter((item) => !this.messages.some((existing) => existing.id === item.id)))
        this.nextBefore = data.next_before
      } catch { if (token === epoch(this)) this.error = true }
      finally { if (token === epoch(this)) this.isLoading = false }
    },
    async removeConversation() {
      if (!this.conversation) return
      const id = this.conversation.id
      const token = epoch(this)
      try {
        await usePlatformApi().delete(`${base}conversations/${id}/`, config)
        if (token !== epoch(this)) return
        this.conversations = this.conversations.filter((row) => row.id !== id)
        this.newConversation()
      } catch { if (token === epoch(this)) this.error = true }
    },
  },
})
