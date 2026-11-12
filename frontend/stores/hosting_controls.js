import { defineStore } from 'pinia'
import { get_request, patch_request } from './services/request_http'
import { normalizeApiError } from './services/normalize_api_error'

export const useHostingControlsStore = defineStore('hosting_controls', {
  state: () => ({ records: [], selected: null, events: [], page: 1, pages: 1, loading: false, saving: false, searchSerial: 0, selectionSerial: 0, error: '', conflict: false }),
  actions: {
    async search(search = '', page = 1, projectId = '') {
      this.loading = true
      const serial = ++this.searchSerial
      try {
        const query = new URLSearchParams({ search, page: String(page) })
        if (projectId) query.set('project_id', String(projectId))
        const { data } = await get_request(`hosting-controls/?${query}`)
        if (serial !== this.searchSerial) return
        this.records = data.results
        this.page = data.page
        this.pages = data.pages
        this.error = ''
      } catch {
        this.error = 'No se pudo consultar el inventario de producción.'
      } finally { if (serial === this.searchSerial) this.loading = false }
    },
    async select(id) {
      if (this.saving) return this.selected
      const serial = ++this.selectionSerial
      const { data } = await get_request(`hosting-controls/${id}/`)
      if (serial !== this.selectionSerial) return data
      this.selected = data
      await this.history()
      return data
    },
    async refresh() {
      if (!this.selected) return
      const id = this.selected.id
      const { data } = await get_request(`hosting-controls/${id}/`)
      if (this.selected?.id === id && data.version >= this.selected.version) this.selected = data
    },
    async history() {
      if (!this.selected) return
      const id = this.selected.id
      const { data } = await get_request(`hosting-controls/${id}/events/`)
      if (this.selected?.id === id) this.events = data.results
    },
    async save(kind, payload) {
      if (this.saving || !this.selected) return false
      this.saving = true
      this.error = ''
      this.conflict = false
      try {
        const { data } = await patch_request(`hosting-controls/${this.selected.id}/${kind}/`, payload)
        this.selected = data
        try { await this.history() } catch { this.error = 'Cambio guardado; no se pudo actualizar el historial.' }
        return true
      } catch (error) {
        this.conflict = error.response?.status === 409
        this.error = this.conflict ? 'Otra edición cambió la configuración. Recarga para revisar; tu borrador se conserva.' : normalizeApiError(error, 'No se pudo guardar el cambio.').message
        return false
      } finally { this.saving = false }
    },
  },
})
