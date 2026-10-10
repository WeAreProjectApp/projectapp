import { defineStore } from 'pinia';
import { get_request, create_request, patch_request, delete_request } from './services/request_http';
import { normalizeApiError } from './services/normalize_api_error';
import { useAccountingStore } from './accounting';
import { useDocumentStore } from './documents';

/**
 * The accounting pickers memoize projects per client forever; any module
 * mutation must drop that cache or a rename/archive would keep serving the
 * stale entry in every form. Total invalidation on purpose: mutations here
 * are rare and the picker lists are tiny.
 */
function invalidatePickerCache() {
  useAccountingStore().invalidateProjectsCache();
}

/** Keep already-mounted relation columns coherent after a project rename. */
function syncLoadedProjectName(project) {
  if (!project?.id || typeof project.name !== 'string') return;

  const accounting = useAccountingStore();
  const replaceName = (record, relationKey) => (
    record[relationKey] === project.id
      ? { ...record, project_name: project.name }
      : record
  );
  if (accounting.hostings.length) {
    accounting.hostings = accounting.hostings.map(
      (record) => replaceName(record, 'project'),
    );
  }
  if (accounting.incomes.length) {
    accounting.incomes = accounting.incomes.map(
      (record) => replaceName(record, 'project'),
    );
  }
  if (accounting.collectionAccounts.length) {
    accounting.collectionAccounts = accounting.collectionAccounts.map(
      (record) => replaceName(record, 'project_id'),
    );
  }

  const documentStore = useDocumentStore();
  if (documentStore.documents.length) {
    documentStore.documents = documentStore.documents.map(
      (record) => replaceName(record, 'project'),
    );
  }
}

/**
 * Panel-side store for the Projects module (Plataforma space).
 *
 * Session/CSRF client like every content store — the platform keeps its own
 * JWT store (platform-projects.js) for /platform views. `createRecord` and
 * `updateRecord` keep the `(entity, ...)` signature so the page can drive
 * them through useAccountingCrudPage.
 */
export const usePanelProjectsStore = defineStore('panel_projects', {
  state: () => ({
    records: [],
    meta: {
      total: 0,
      by_state: [],
      review_required: 0,
      clients_without_projects: 0,
      records_without_project: 0,
    },
    isLoading: false,
    isUpdating: false,
    error: null,
    clientsWithoutProjects: [],
    isLoadingClientsWithoutProjects: false,
  }),

  actions: {
    async previewDeletion(id, { force = false, deleteKeys } = {}) {
      try {
        const response = force && deleteKeys !== undefined
          ? await create_request(`projects/${id}/delete-preview/`, { delete_keys: deleteKeys })
          : await get_request(`projects/${id}/delete-preview/${force ? '?force=true' : ''}`);
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, ...normalizeApiError(error, 'No se pudieron comprobar las dependencias del proyecto.') };
      }
    },

    async deleteProject(id, options) {
      this.isUpdating = true;
      try {
        if (options) await delete_request(`projects/${id}/delete/`, options);
        else await delete_request(`projects/${id}/delete/`);
        // A successful DELETE is final even if the subsequent refresh fails.
        // Remove the row locally first so retrying cannot submit it again.
        this.records = this.records.filter((record) => record.id !== id);
        invalidatePickerCache();
        const refresh = await this.fetchProjects();
        return { success: true, refreshFailed: !refresh.success };
      } catch (error) {
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudo eliminar el proyecto.'),
          preview: ['project_delete_blocked', 'project_force_delete_blocked', 'stale_project_delete_preview'].includes(error?.response?.data?.code)
            ? error.response.data : null,
        };
      } finally {
        this.isUpdating = false;
      }
    },

    async fetchProjects() {
      this.isLoading = true;
      this.error = null;
      try {
        // One load with scope=all: the module filters client-side, same
        // approach as the accounting tabs (the volume is tiny).
        const response = await get_request('projects/?scope=all');
        this.records = response.data.results;
        this.meta = response.data.meta;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_failed';
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudieron cargar los proyectos.'),
        };
      } finally {
        this.isLoading = false;
      }
    },

    async refreshAfterExternalMutation() {
      const result = await this.fetchProjects();
      if (result.success) invalidatePickerCache();
      return result;
    },

    /** `(entity, payload)` — signature shared with useAccountingCrudPage. */
    async createRecord(entity, payload) {
      this.isUpdating = true;
      try {
        const response = await create_request('projects/create/', payload);
        await this.fetchProjects();
        invalidatePickerCache();
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudo crear el proyecto.'),
        };
      } finally {
        this.isUpdating = false;
      }
    },

    async updateRecord(entity, id, payload) {
      this.isUpdating = true;
      try {
        const response = await patch_request(`projects/${id}/update/`, payload);
        await this.fetchProjects();
        syncLoadedProjectName(response.data);
        invalidatePickerCache();
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudo actualizar el proyecto.'),
        };
      } finally {
        this.isUpdating = false;
      }
    },

    /** Preview of the assign flow: the client's records without a project. */
    async fetchUnlinkedRecords(id) {
      try {
        const response = await get_request(`projects/${id}/unlinked-records/`);
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudieron cargar los registros sin proyecto.'),
        };
      }
    },

    /** Assign the project to the confirmed ids; refetch so counts move. */
    async assignUnlinkedRecords(id, payload) {
      this.isUpdating = true;
      try {
        const response = await create_request(`projects/${id}/assign-unlinked/`, payload);
        // The response carries the updated accounting rows (cascaded liquid
        // children included). An accounting tab open in the SPA rebuilds
        // from them — reloading is a symptom, not a fix.
        const accounting = useAccountingStore();
        const hostings = new Map(
          (response.data.hostings ?? []).map((row) => [row.id, row]),
        );
        if (hostings.size && accounting.hostings.length) {
          accounting.hostings = accounting.hostings.map(
            (record) => hostings.get(record.id) ?? record,
          );
        }
        const incomes = new Map(
          (response.data.incomes ?? []).map((row) => [row.id, row]),
        );
        if (incomes.size && accounting.incomes.length) {
          accounting.incomes = accounting.incomes.map(
            (record) => incomes.get(record.id) ?? record,
          );
        }
        // Documents follow the same rule (F7).
        const documents = new Map(
          (response.data.documents ?? []).map((row) => [row.id, row]),
        );
        const documentStore = useDocumentStore();
        if (documents.size && documentStore.documents.length) {
          documentStore.documents = documentStore.documents.map(
            (record) => documents.get(record.id) ?? record,
          );
        }
        // Cuentas are Documents too, but their accounting serializer names
        // the live relation `project_id` while DocumentListSerializer returns
        // `project`. Merge only the live relation fields so the open monitor
        // updates immediately without losing its billing/status metadata.
        if (documents.size && accounting.collectionAccounts.length) {
          accounting.collectionAccounts = accounting.collectionAccounts.map(
            (record) => {
              const document = documents.get(record.id);
              if (!document) return record;
              return {
                ...record,
                project_id: document.project,
                project_name: document.project_name,
              };
            },
          );
        }
        await this.fetchProjects();
        invalidatePickerCache();
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudieron asignar los registros.'),
        };
      } finally {
        this.isUpdating = false;
      }
    },

    /** Impact preview of moving the project to another client. No state. */
    async previewChangeClient(id, clientProfileId) {
      try {
        const response = await get_request(
          `projects/${id}/change-client/preview/?client_profile_id=${clientProfileId}`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudo calcular el impacto.'),
        };
      }
    },

    /**
     * Apply the change-client cascade. The response carries counts plus the
     * annotated project row, never the touched records (the set is
     * unbounded and multi-module), so the accounting lists that are already
     * loaded refetch instead of map-replacing.
     */
    async changeClient(id, payload, preview = null) {
      this.isUpdating = true;
      try {
        const requestPayload = { ...payload };
        if (preview?.impact_hash) {
          requestPayload.expected_impact_hash = preview.impact_hash;
        }
        const response = await create_request(
          `projects/${id}/change-client/`, requestPayload,
        );
        const accounting = useAccountingStore();
        const documentStore = useDocumentStore();
        const refreshes = [];
        if (accounting.hostings.length) {
          refreshes.push(accounting.fetchRecords('hostings'));
        }
        if (accounting.incomes.length) {
          refreshes.push(accounting.fetchRecords('incomes'));
        }
        const changedDraftAccounts = (
          (response.data.moved?.draft_accounts ?? 0)
          + (response.data.detached?.draft_accounts ?? 0)
        );
        if (changedDraftAccounts && accounting.collectionAccounts.length) {
          refreshes.push(accounting.fetchCollectionAccounts());
        }
        if (changedDraftAccounts && documentStore.documents.length) {
          refreshes.push(documentStore.fetchDocuments());
        }
        await Promise.all(refreshes);
        await this.fetchProjects();
        invalidatePickerCache();
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          ...normalizeApiError(
            error, 'No se pudo cambiar el cliente del proyecto.',
          ),
        };
      } finally {
        this.isUpdating = false;
      }
    },

    async fetchClientsWithoutProjects() {
      this.isLoadingClientsWithoutProjects = true;
      try {
        const response = await get_request(
          'proposals/client-profiles/?without_projects=true&limit=500',
        );
        this.clientsWithoutProjects = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          ...normalizeApiError(error, 'No se pudieron cargar los clientes sin proyecto.'),
        };
      } finally {
        this.isLoadingClientsWithoutProjects = false;
      }
    },
  },
});
