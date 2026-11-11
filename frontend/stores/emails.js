import { defineStore } from 'pinia';
import {
  get_request,
  create_request,
  put_request,
  patch_request,
  delete_request,
} from './services/request_http';
import { recipientEmails } from '~/utils/emailRecipients';

export const useEmailStore = defineStore('emails', {
  state: () => ({
    history: [],
    historyPagination: { total: 0, page: 1, has_next: false },
    historyFilters: {},
    attachmentTypeOptions: [],
    defaults: { greeting: '', footer: '' },
    copyRecipients: [],
    copyFamilies: [],
    copyMode: 'bcc',
    isSending: false,
    isLoadingHistory: false,
    isLoadingDefaults: false,
    isSavingDefaults: false,
    isLoadingPreview: false,
    isLoadingCopyRecipients: false,
    isSavingCopyRecipient: false,
    isResending: false,
    error: null,
  }),

  actions: {
    async retryEmail(logId) {
      try {
        const response = await create_request(`emails/history/${logId}/retry/`, {});
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          data: error.response?.data,
          message: error.response?.data?.detail || 'No se pudo reintentar el correo.',
        };
      }
    },
    async fetchDefaults() {
      this.isLoadingDefaults = true;
      this.error = null;
      try {
        const response = await get_request('emails/defaults/');
        this.defaults = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_defaults_failed';
        console.error('Error fetching email defaults:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoadingDefaults = false;
      }
    },

    async saveDefaults(payload) {
      this.isSavingDefaults = true;
      this.error = null;
      try {
        const response = await put_request('emails/defaults/', payload);
        this.defaults = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = error.response?.data?.error || 'save_defaults_failed';
        console.error('Error saving email defaults:', error);
        return { success: false, error: error.response?.data?.error };
      /* c8 ignore next 3 */
      } finally {
        this.isSavingDefaults = false;
      }
    },

    async fetchHistory(page = 1, filters = null) {
      this.isLoadingHistory = true;
      this.error = null;
      try {
        if (filters !== null) this.historyFilters = { ...filters };
        const params = new URLSearchParams({ scope: 'all', page: String(page) });
        for (const [key, value] of Object.entries(this.historyFilters)) {
          if (value) params.set(key, value);
        }
        const response = await get_request(`emails/history/?${params.toString()}`);
        if (page === 1) {
          this.history = response.data.results;
        } else {
          this.history.push(...response.data.results);
        }
        this.historyPagination = {
          total: response.data.total,
          page: response.data.page,
          has_next: response.data.has_next,
        };
        this.attachmentTypeOptions = response.data.attachment_type_options || [];
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_history_failed';
        console.error('Error fetching email history:', error);
        return { success: false, data: { results: [], total: 0, page: 1, has_next: false } };
      /* c8 ignore next 3 */
      } finally {
        this.isLoadingHistory = false;
      }
    },

    async fetchEmailBody(logId) {
      try {
        const response = await get_request(`emails/history/${logId}/body/`);
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          message: error.response?.data?.error || 'No se pudo cargar el correo.',
        };
      }
    },

    async resendEmail(logId, recipients, ccRecipients = []) {
      this.isResending = true;
      try {
        const payload = typeof recipients === 'string'
          ? { recipient: recipients }
          : {
            recipient_emails: recipientEmails(recipients),
            cc_emails: recipientEmails(ccRecipients),
          };
        const response = await create_request(
          `emails/history/${logId}/resend/`,
          payload,
        );
        return { success: true, data: response.data };
      } catch (error) {
        return {
          success: false,
          error: error.response?.data,
          message: error.response?.data?.detail || 'No se pudo reenviar el correo.',
        };
      /* c8 ignore next 3 */
      } finally {
        this.isResending = false;
      }
    },

    async previewEmail(payload) {
      this.isLoadingPreview = true;
      this.error = null;
      try {
        const response = await create_request('emails/preview/', payload);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = error.response?.data?.error || 'preview_failed';
        console.error('Error fetching email preview:', error);
        return { success: false, error: error.response?.data?.error };
      /* c8 ignore next 3 */
      } finally {
        this.isLoadingPreview = false;
      }
    },

    async sendEmail(formData) {
      this.isSending = true;
      this.error = null;
      try {
        const response = await create_request('emails/send/', formData);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = error.response?.data?.error || 'send_failed';
        console.error('Error sending email:', error);
        return { success: false, error: error.response?.data?.error };
      /* c8 ignore next 3 */
      } finally {
        this.isSending = false;
      }
    },

    async fetchCopyRecipients() {
      this.isLoadingCopyRecipients = true;
      this.error = null;
      try {
        const response = await get_request('emails/copy-recipients/');
        this.copyRecipients = response.data.results || [];
        this.copyFamilies = response.data.families || [];
        this.copyMode = response.data.copy_mode || 'bcc';
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_copy_recipients_failed';
        console.error('Error fetching client email copy recipients:', error);
        return { success: false, error: error.response?.data };
      /* c8 ignore next 3 */
      } finally {
        this.isLoadingCopyRecipients = false;
      }
    },

    async createCopyRecipient(payload) {
      this.isSavingCopyRecipient = true;
      try {
        const response = await create_request('emails/copy-recipients/', payload);
        this.copyRecipients.push(response.data);
        this.copyRecipients.sort((a, b) => a.email.localeCompare(b.email));
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, error: error.response?.data };
      /* c8 ignore next 3 */
      } finally {
        this.isSavingCopyRecipient = false;
      }
    },

    async updateCopyRecipient(id, payload) {
      this.isSavingCopyRecipient = true;
      try {
        const response = await patch_request(`emails/copy-recipients/${id}/`, payload);
        const index = this.copyRecipients.findIndex(item => item.id === id);
        if (index !== -1) this.copyRecipients[index] = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, error: error.response?.data };
      /* c8 ignore next 3 */
      } finally {
        this.isSavingCopyRecipient = false;
      }
    },

    async deleteCopyRecipient(id) {
      this.isSavingCopyRecipient = true;
      try {
        await delete_request(`emails/copy-recipients/${id}/`);
        this.copyRecipients = this.copyRecipients.filter(item => item.id !== id);
        return { success: true };
      } catch (error) {
        return { success: false, error: error.response?.data };
      /* c8 ignore next 3 */
      } finally {
        this.isSavingCopyRecipient = false;
      }
    },
  },
});
