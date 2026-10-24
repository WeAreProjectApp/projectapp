import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { usePlatformAuthStore } from '~/stores/platform-auth'

const base = '/api/platform/help/'
const terminal = new Set(['completed', 'skipped'])
const pendingKey = (id) => `platform-help-pending:${id}`

function pending(id) {
  try { return JSON.parse(localStorage.getItem(pendingKey(id)) || '{}') } catch { return {} }
}

function savePending(id, values) {
  try { localStorage.setItem(pendingKey(id), JSON.stringify(values)) } catch { /* Storage may be disabled. */ }
}

export const usePlatformHelpStore = defineStore('platform-help', {
  state: () => ({ tours: [], tourEnabled: false, videoEnabled: false, loaded: false, request: 0, userId: null }),
  actions: {
    reset() {
      this.request += 1
      this.tours = []
      this.tourEnabled = false
      this.videoEnabled = false
      this.loaded = false
      this.userId = null
    },
    async fetchHelp(projectId) {
      const auth = usePlatformAuthStore()
      if (!auth.isClient || !auth.user?.id) { this.reset(); return false }
      const request = ++this.request
      const userId = auth.user.id
      try {
        const response = await usePlatformApi().get(base, { baseURL: '', params: projectId ? { project_id: projectId } : {} })
        if (request !== this.request || userId !== auth.user?.id) return false
        this.userId = userId
        this.tourEnabled = response.data.tour_enabled
        this.videoEnabled = response.data.video_enabled
        const queued = pending(userId)
        this.tours = response.data.tours.map((tour) => ({ ...tour, status: terminal.has(queued[tour.id]?.status) ? queued[tour.id].status : tour.status }))
        this.loaded = true
        await this.flushPending(userId)
        return true
      } catch {
        if (request === this.request) { this.tourEnabled = false; this.loaded = false }
        return false
      }
    },
    async flushPending(userId) {
      const queued = pending(userId)
      for (const [id, value] of Object.entries(queued)) {
        if (usePlatformAuthStore().user?.id !== userId) return
        try {
          await usePlatformApi().post(`${base}tours/${id}/progress/`, value, { baseURL: '' })
          // Merge with the current queue so a newer acknowledgement isn't lost.
          const current = pending(userId)
          if (JSON.stringify(current[id]) === JSON.stringify(value)) delete current[id]
          savePending(userId, current)
        } catch { /* Retry on the next successful refresh. */ }
      }
    },
    async acknowledge(tour, status, lastStep, projectId, manual = false) {
      const userId = this.userId
      if (!userId || usePlatformAuthStore().user?.id !== userId) return
      const value = { status, revision: tour.revision, last_step: lastStep || '', manual,
        ...(tour.context !== 'general' && projectId ? { project_id: Number(projectId) } : {}) }
      if (!terminal.has(tour.status)) tour.status = status
      tour.last_step = lastStep
      const queued = pending(userId)
      // Terminal acknowledgements survive navigation, offline dismissal and reload.
      if (!terminal.has(queued[tour.id]?.status)) queued[tour.id] = value
      savePending(userId, queued)
      await this.flushPending(userId)
    },
  },
})
