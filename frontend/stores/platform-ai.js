import { defineStore } from 'pinia'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformApi } from '~/composables/usePlatformApi'

const base = '/api/platform/ai/'
const pendingCapabilities = new WeakMap()

export const usePlatformAIStore = defineStore('platform-ai', {
  state: () => ({ capabilities: null, generation: 0 }),
  getters: {
    voiceAvailable: (state) => !!state.capabilities?.voice_reporting?.available,
  },
  actions: {
    reset() { this.generation += 1; this.capabilities = null; pendingCapabilities.delete(this) },
    async refreshCapabilities() {
      const generation = this.generation, actorId = usePlatformAuthStore().user?.user_id
      if (pendingCapabilities.has(this)) return pendingCapabilities.get(this)
      const request = (async () => {
        try {
          const { data } = await usePlatformApi().get(`${base}capabilities/`, { baseURL: '' })
          if (generation === this.generation && actorId === usePlatformAuthStore().user?.user_id) this.capabilities = data
        }
        catch { if (generation === this.generation) this.capabilities = null }
        finally { if (generation === this.generation) pendingCapabilities.delete(this) }
      })()
      pendingCapabilities.set(this, request)
      return request
    },
    async transcribe(audio, { purpose, projectId, requestId }) {
      const form = new FormData()
      const extension = audio.type.includes('mp4') ? 'mp4' : 'webm'
      form.append('audio', audio, `note.${extension}`)
      form.append('purpose', purpose)
      if (projectId) form.append('project_id', String(projectId))
      form.append('request_id', requestId)
      return (await usePlatformApi().post(`${base}transcriptions/`, form, { baseURL: '', headers: { 'Content-Type': undefined } })).data
    },
    async generateReport(projectId, payload) {
      return (await usePlatformApi().post(`${base}projects/${projectId}/report-drafts/`, payload, { baseURL: '' })).data
    },
    async job(id, signal) {
      return (await usePlatformApi().get(`${base}transcriptions/${id}/`, { baseURL: '', signal })).data
    },
    async discard(id) { await usePlatformApi().delete(`${base}transcriptions/${id}/`, { baseURL: '' }) },
    async recent(projectId, scenario, context = {}) {
      return (await usePlatformApi().get(`${base}transcriptions/`, { baseURL: '', params: {
        purpose: 'voice_report', project_id: projectId, scenario, ...context,
      } })).data
    },
  },
})
