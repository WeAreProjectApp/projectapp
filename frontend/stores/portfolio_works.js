import { defineStore } from 'pinia';
import { get_request, create_request, patch_request, delete_request } from './services/request_http';

export const usePortfolioWorksStore = defineStore('portfolio_works', {
  /**
   * State of the PortfolioWorks store.
   *
   * Properties:
   * - works (Array): List of portfolio works.
   * - currentWork (Object|null): Currently viewed/edited work.
   * - isLoading (Boolean): Whether a fetch operation is in progress.
   * - isUpdating (Boolean): Whether a mutation operation is in progress.
   * - error (String|null): Last error message.
   */
  state: () => ({
    works: [],
    currentWork: null,
    publicWorkRequestId: 0,
    isLoading: false,
    isUpdating: false,
    error: null,
  }),

  getters: {
    /**
     * getWorkById: Find a work in the list by its ID.
     */
    getWorkById: (state) => (id) =>
      state.works.find((w) => w.id === id),
  },

  actions: {
    // -----------------------------------------------------------------
    // Public
    // -----------------------------------------------------------------

    /**
     * fetchWorks: List all published portfolio works.
     * @param {string} lang - Language code ('es' or 'en').
     */
    async fetchWorks(lang = 'es') {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(`portfolio/?lang=${lang}`);
        this.works = response.data || [];
        return { success: true };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error('Error fetching portfolio works:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchWork: Retrieve a single published portfolio work by slug.
     * @param {string} slug - Work slug.
     * @param {string} lang - Language code ('es' or 'en').
     */
    async fetchWork(slug, lang = 'es') {
      const requestId = ++this.publicWorkRequestId;
      this.isLoading = true;
      this.error = null;
      this.currentWork = null;
      try {
        const response = await get_request(`portfolio/${slug}/?lang=${lang}`);
        if (requestId === this.publicWorkRequestId) this.currentWork = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        const status = error.response?.status;
        const code = status === 404 ? 'not_found' : 'unknown';
        if (requestId === this.publicWorkRequestId) this.error = code;
        return { success: false, error: code, status };
      } finally {
        if (requestId === this.publicWorkRequestId) this.isLoading = false;
      }
    },

    // -----------------------------------------------------------------
    // Admin
    // -----------------------------------------------------------------

    /**
     * fetchAdminWorks: List all portfolio works (including drafts) for admin.
     */
    async fetchAdminWorks() {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request('portfolio/admin/');
        this.works = response.data;
        return { success: true };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error('Error fetching admin portfolio works:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchAdminWork: Retrieve full work detail for admin editing.
     * @param {number} id - Work ID.
     */
    async fetchAdminWork(id) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(`portfolio/admin/${id}/detail/`);
        this.currentWork = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error('Error fetching portfolio work:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * createWork: Create a new portfolio work.
     * @param {object} payload - Work data.
     */
    async createWork(payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request('portfolio/admin/create/', payload);
        this.currentWork = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'create_failed';
        console.error('Error creating portfolio work:', error);
        return { success: false, errors: error.response?.data };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * updateWork: Update a portfolio work's fields.
     * @param {number} id - Work ID.
     * @param {object} payload - Fields to update.
     */
    async updateWork(id, payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(`portfolio/admin/${id}/update/`, payload);
        this.currentWork = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'update_failed';
        console.error('Error updating portfolio work:', error);
        return { success: false, errors: error.response?.data };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * deleteWork: Delete a portfolio work.
     * @param {number} id - Work ID.
     */
    async deleteWork(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        await delete_request(`portfolio/admin/${id}/delete/`);
        this.works = this.works.filter((w) => w.id !== id);
        if (this.currentWork?.id === id) {
          this.currentWork = null;
        }
        return { success: true };
      } catch (error) {
        this.error = 'delete_failed';
        console.error('Error deleting portfolio work:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * createWorkFromJSON: Create a portfolio work from a full JSON payload.
     * @param {object} payload - Full portfolio JSON.
     */
    async createWorkFromJSON(payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request('portfolio/admin/create-from-json/', payload);
        this.currentWork = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'create_failed';
        console.error('Error creating portfolio work from JSON:', error);
        return { success: false, errors: error.response?.data };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * uploadCoverImage: Upload a cover image file for a portfolio work.
     * @param {number} id - Work ID.
     * @param {File} file - Image file to upload.
     */
    async uploadCoverImage(id, file) {
      this.isUpdating = true;
      this.error = null;
      try {
        const formData = new FormData();
        formData.append('cover_image', file);
        const csrfToken = document.cookie
          .split('; ')
          .find((c) => c.startsWith('csrftoken='))
          ?.split('=')[1] || '';
        const response = await fetch(`/api/portfolio/admin/${id}/upload-cover/`, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrfToken },
          body: formData,
        });
        if (!response.ok) throw new Error('Upload failed');
        const data = await response.json();
        this.currentWork = data;
        return { success: true, data };
      } catch (error) {
        this.error = 'upload_failed';
        console.error('Error uploading cover image:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * duplicateWork: Create a deep copy of a portfolio work as a new draft.
     * @param {number} id - Work ID to duplicate.
     */
    async duplicateWork(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(`portfolio/admin/${id}/duplicate/`, {});
        this.works.unshift(response.data);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'duplicate_failed';
        console.error('Error duplicating portfolio work:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * downloadJSONTemplate: Fetch the portfolio JSON template from the API.
     */
    async downloadJSONTemplate() {
      try {
        const response = await get_request('portfolio/admin/json-template/');
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error downloading portfolio JSON template:', error);
        return { success: false };
      }
    },
  },
});
