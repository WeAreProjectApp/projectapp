import { defineStore } from 'pinia';
import { get_request, create_request, patch_request, delete_request } from './services/request_http';
import { normalizeApiError } from './services/normalize_api_error';
import { folderPath } from '~/utils/folderHierarchy';
import { buildFolderRollup } from '~/utils/folderRollup';

/** Adapter to the shared Document Manager navigation contract. No secrets. */
export const useSecureLinkFoldersStore = defineStore('secureLinkFolders', {
  state: () => ({ folders: [], navigation: { projects: [], clients: [] }, request: 0, isLoading: false, isUpdating: false, error: '' }),
  getters: {
    folderById: state => id => state.folders.find(f => f.id === Number(id)) || null,
    ancestorsOf: state => id => folderPath(state.folders.find(f => f.id === Number(id)), state.folders),
    childrenOf: state => (id, scope = 'active') => state.folders.filter(f => f.parent === id && (scope === 'all' || f.is_archived === (scope === 'archived'))),
    descendantIdsOf: state => id => new Set(state.folders.filter(f => f.id !== Number(id) && folderPath(f, state.folders).some(p => p.id === Number(id))).map(f => f.id)),
    activeRollup: state => buildFolderRollup(state.folders, { countingScope: 'active', membershipScope: 'all' }),
    archivedRollup: state => buildFolderRollup(state.folders, { countingScope: 'archived', membershipScope: 'all' }),
    mixedRollup: state => buildFolderRollup(state.folders, { countingScope: 'all', membershipScope: 'all' }),
    rollupOf() { return (folder, scope = 'active') => (scope === 'all' ? this.mixedRollup : scope === 'archived' ? this.archivedRollup : this.activeRollup).get(folder.id) || { docs: 0, subs: 0 }; },
    recursiveDocumentCount() { return (folder, scope) => this.rollupOf(folder, scope).docs; },
    archivedContentCount() { return folder => { const counts = this.rollupOf(folder, 'archived'); return counts.docs + counts.subs; }; },
    totalContentCount() { return folder => this.rollupOf(folder, 'all').docs + this.folders.filter(f => f.parent === folder.id).length; },
    navigationFacets: state => state.navigation,
  },
  actions: {
    async fetchFolders() {
      const request = ++this.request;
      this.isLoading = true;
      this.error = '';
      try {
        const response = await get_request('secure-links/folders/');
        if (request !== this.request) return { success: false, stale: true };
        const rows = response.data.folders || [];
        this.folders = rows.map(f => ({ ...f, active_document_count: f.link_count || 0, archived_document_count: f.archived_link_count || 0,
          active_children_count: rows.filter(c => c.parent === f.id && !c.is_archived).length,
          archived_children_count: rows.filter(c => c.parent === f.id && c.is_archived).length }));
        this.navigation = response.data.navigation || { projects: [], clients: [] };
        return { success: true };
      } catch (error) {
        if (request !== this.request) return { success: false, stale: true };
        this.error = normalizeApiError(error).message;
        return { success: false, error: normalizeApiError(error) };
      } finally { if (request === this.request) this.isLoading = false; }
    },
    async write(call) {
      if (this.isUpdating) return { success: false };
      this.isUpdating = true;
      try {
        const response = await call();
        await this.fetchFolders();
        return { success: true, data: response.data };
      } catch (error) { return { success: false, error: normalizeApiError(error) }; }
      finally { this.isUpdating = false; }
    },
    saveFolder(id, data) { return this.write(() => id ? patch_request(`secure-links/folders/${id}/`, data) : create_request('secure-links/folders/', data)); },
    deleteFolder(folder) { return this.write(() => delete_request(`secure-links/folders/${folder.id}/`, { expected_updated_at: folder.updated_at })); },
    archiveFolder(folder, restore = false) { return this.write(() => create_request(`secure-links/folders/${folder.id}/${restore ? 'restore' : 'archive'}/`, { expected_updated_at: folder.updated_at })); },
    reorderFolders(ids, parent = null) { return this.write(() => create_request('secure-links/folders/reorder/', { ids, parent })); },
  },
});
