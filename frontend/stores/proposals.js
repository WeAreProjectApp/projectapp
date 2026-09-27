import { defineStore } from 'pinia';
import { get_request, create_request, put_request, patch_request, delete_request } from './services/request_http';
import { normalizeApiError } from './services/normalize_api_error';
import { isUuid } from '~/utils/slugify';

export const useProposalStore = defineStore('proposals', {
  /**
   * State of the Proposal store.
   *
   * Properties:
   * - proposals (Array): List of proposals (admin).
   * - currentProposal (Object|null): Currently viewed/edited proposal.
   * - isLoading (Boolean): Whether a fetch operation is in progress.
   * - isUpdating (Boolean): Whether a mutation operation is in progress.
   * - error (String|null): Last error message.
   */
  state: () => ({
    proposals: [],
    currentProposal: null,
    adminUser: null,
    isLoading: false,
    isUpdating: false,
    error: null,
  }),

  getters: {
    /**
     * getProposalById: Find a proposal in the list by its ID.
     */
    getProposalById: (state) => (id) =>
      state.proposals.find((p) => p.id === id),

    /**
     * enabledSections: Return only enabled sections, sorted by order.
     */
    enabledSections: (state) =>
      state.currentProposal?.sections
        ?.filter((s) => s.is_enabled)
        ?.sort((a, b) => a.order - b.order) || [],

    /**
     * totalSections: Count of enabled sections.
     */
    totalSections: (state) =>
      state.currentProposal?.sections?.filter((s) => s.is_enabled)?.length || 0,

    /**
     * isSuperuser: Whether the checked panel session belongs to a superuser
     * (set by checkAdminAuth; gates superuser-only modules like accounting).
     */
    isSuperuser: (state) => !!state.adminUser?.is_superuser,
  },

  actions: {
    // -----------------------------------------------------------------
    // Public
    // -----------------------------------------------------------------

    /**
     * fetchPublicProposal: Retrieve a proposal by UUID or slug for client viewing.
     * @param {string} identifier - Proposal UUID or slug.
     */
    async fetchPublicProposal(identifier) {
      this.isLoading = true;
      this.error = null;
      const uuid = identifier;
      const path = isUuid(identifier)
        ? `proposals/${identifier}/`
        : `proposals/by-slug/${identifier}/`;
      try {
        const response = await get_request(path);
        this.currentProposal = response.data;
        // Expired proposals now return 200 with full data + expired_meta
        if (response.data?.expired_meta) {
          return { success: true, data: response.data, expired: true };
        }
        return { success: true, data: response.data };
      } catch (error) {
        const status = error.response?.status;
        if (status === 410) {
          this.error = 'expired';
          // Legacy fallback: store partial data from 410 response
          const partial = error.response?.data;
          if (partial) {
            this.currentProposal = {
              client_name: partial.client_name || '',
              title: partial.title || '',
              uuid: partial.uuid || uuid,
              expired_at: partial.expired_at || null,
              seller_name: partial.seller_name || '',
              whatsapp_url: partial.whatsapp_url || '',
              total_investment: partial.total_investment || '',
              currency: partial.currency || '',
            };
          }
        } else if (status === 404) {
          this.error = 'not_found';
        } else {
          this.error = 'unknown';
        }
        return { success: false, error: this.error, status };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchContractTerms: Retrieve the current masked global contract for a proposal.
     * @param {string} uuid - Public proposal UUID.
     */
    async fetchContractTerms(uuid) {
      try {
        const response = await get_request(`proposals/${uuid}/contract-terms/`);
        return { success: true, data: response.data };
      } catch (error) {
        const status = error.response?.status;
        return {
          success: false,
          status,
          error: error.response?.data?.error || 'contract_terms_unavailable',
        };
      }
    },

    // -----------------------------------------------------------------
    // Admin
    // -----------------------------------------------------------------

    /**
     * fetchProposals: List all proposals (admin).
     * @param {string} [statusFilter] - Optional status filter.
     */
    async fetchProposals(statusFilter) {
      this.isLoading = true;
      this.error = null;
      try {
        const url = statusFilter
          ? `proposals/?status=${statusFilter}`
          : 'proposals/';
        const response = await get_request(url);
        this.proposals = response.data;
        return { success: true };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error('Error fetching proposals:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchProposal: Retrieve full proposal detail for admin editing.
     * @param {number} id - Proposal ID.
     */
    async fetchProposal(id) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(`proposals/${id}/detail/`);
        this.currentProposal = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_failed';
        console.error('Error fetching proposal:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * createProposal: Create a new proposal.
     * @param {object} payload - Proposal data.
     */
    async createProposal(payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request('proposals/create/', payload);
        this.currentProposal = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'create_failed';
        console.error('Error creating proposal:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * createProposalFromJSON: Create a proposal from a complete JSON payload.
     * @param {object} jsonData - Full payload with metadata + sections.
     */
    async createProposalFromJSON(jsonData) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request('proposals/create-from-json/', jsonData);
        this.currentProposal = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'create_from_json_failed';
        console.error('Error creating proposal from JSON:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * exportProposalJSON: Export a proposal as importable JSON.
     * @param {number} id - Proposal ID.
     */
    async exportProposalJSON(id) {
      try {
        const response = await get_request(`proposals/${id}/export-json/`);
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error exporting proposal JSON:', error);
        return { success: false };
      }
    },

    /**
     * updateProposalFromJSON: Update an existing proposal from a complete JSON payload.
     * @param {number} id - Proposal ID.
     * @param {object} jsonData - Full payload with metadata + sections.
     */
    async updateProposalFromJSON(id, jsonData) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await put_request(`proposals/${id}/update-from-json/`, jsonData);
        this.currentProposal = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'update_from_json_failed';
        console.error('Error updating proposal from JSON:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * updateProposal: Update proposal metadata.
     * @param {number} id - Proposal ID.
     * @param {object} payload - Fields to update.
     */
    async updateProposal(id, payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(`proposals/${id}/update/`, payload);
        this.currentProposal = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'update_failed';
        console.error('Error updating proposal:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * previewProposalEmail: Render an email template against this proposal.
     * @param {number} id - Proposal ID.
     * @param {object} payload - { template_key, email_intro?, email_features?, email_method_phases?, email_signed_by? }
     * @returns {Promise<{success: boolean, html?: string, error?: string}>}
     */
    async previewProposalEmail(id, payload) {
      try {
        const response = await create_request(
          `proposals/${id}/email-preview/`,
          payload,
        );
        return { success: true, html: response.data };
      } catch (error) {
        console.error('Error previewing proposal email:', error);
        return { success: false, error: error.response?.data?.error || 'Error generando preview' };
      }
    },

    /**
     * deleteProposal: Delete a proposal.
     * @param {number} id - Proposal ID.
     */
    async deleteProposal(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        await delete_request(`proposals/${id}/delete/`);
        this.proposals = this.proposals.filter((p) => p.id !== id);
        if (this.currentProposal?.id === id) {
          this.currentProposal = null;
        }
        return { success: true };
      } catch (error) {
        this.error = 'delete_failed';
        console.error('Error deleting proposal:', error);
        return {
          success: false,
          error:
            error.response?.data?.error ||
            error.response?.data?.detail ||
            null,
        };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * duplicateProposal: Create a deep copy of a proposal as a new draft.
     * @param {number} id - Proposal ID to duplicate.
     */
    async duplicateProposal(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(`proposals/${id}/duplicate/`, {});
        this.proposals.unshift(response.data);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'duplicate_failed';
        console.error('Error duplicating proposal:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * sendProposal: Mark proposal as SENT and schedule reminder.
     * @param {number} id - Proposal ID.
     */
    async sendProposal(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(`proposals/${id}/send/`, {});
        this.currentProposal = response.data;
        return {
          success: true,
          data: response.data,
          email_delivery: response.data?.email_delivery ?? null,
        };
      } catch (error) {
        this.error = 'send_failed';
        console.error('Error sending proposal:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * fetchProposalsByClient: List proposals for a specific client.
     * @param {number} clientId - UserProfile id of the client.
     */
    async fetchProposalsByClient(clientId) {
      try {
        const response = await get_request(`proposals/?client_id=${clientId}`);
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching client proposals:', error);
        return { success: false, data: [] };
      }
    },

    /**
     * sendMultiProposal: Send a single email referencing several proposals.
     * @param {number} primaryId - Proposal ID in path (the one being edited).
     * @param {number[]} proposalIds - All proposal IDs to include.
     */
    async sendMultiProposal(primaryId, proposalIds) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `proposals/${primaryId}/send-multi/`,
          { proposal_ids: proposalIds },
        );
        this.currentProposal = response.data;
        return {
          success: true,
          data: response.data,
          email_delivery: response.data?.email_delivery ?? null,
        };
      } catch (error) {
        this.error = 'send_multi_failed';
        console.error('Error sending multi proposal:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * resendProposal: Re-send a proposal keeping existing expires_at.
     * @param {number} id - Proposal ID.
     * @param {string|undefined} emailIntro - Edited message; omitted keeps the saved value.
     */
    async resendProposal(id, emailIntro = undefined) {
      this.isUpdating = true;
      this.error = null;
      try {
        const payload = emailIntro === undefined ? {} : { email_intro: emailIntro };
        const response = await create_request(`proposals/${id}/resend/`, payload);
        this.currentProposal = response.data;
        return {
          success: true,
          data: response.data,
          email_delivery: response.data?.email_delivery ?? null,
        };
      } catch (error) {
        this.error = 'resend_failed';
        console.error('Error resending proposal:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * toggleProposalActive: Toggle a proposal's is_active flag.
     * @param {number} id - Proposal ID.
     */
    async toggleProposalActive(id) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(`proposals/${id}/toggle-active/`, {});
        if (this.currentProposal?.id === id) {
          this.currentProposal = response.data;
        }
        const idx = this.proposals.findIndex((p) => p.id === id);
        if (idx !== -1) {
          this.proposals[idx].is_active = response.data.is_active;
        }
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'toggle_active_failed';
        console.error('Error toggling proposal active:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * updateProposalStatus: Inline status change from the proposals table.
     * @param {number} id - Proposal ID.
     * @param {string} newStatus - New status value.
     */
    async updateProposalStatus(id, newStatus) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(`proposals/${id}/update-status/`, { status: newStatus });
        if (this.currentProposal?.id === id) {
          this.currentProposal = response.data;
        }
        const idx = this.proposals.findIndex((p) => p.id === id);
        if (idx !== -1) {
          this.proposals[idx].status = response.data.status;
          this.proposals[idx].available_transitions = response.data.available_transitions || [];
          this.proposals[idx].sent_at = response.data.sent_at ?? this.proposals[idx].sent_at;
        }
        return {
          success: true,
          data: response.data,
          email_delivery: response.data?.email_delivery ?? null,
        };
      } catch (error) {
        this.error = 'update_status_failed';
        console.error('Error updating proposal status:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * launchToPlatform: Trigger platform onboarding for an accepted proposal.
     * @param {number} id - Proposal ID.
     * @param {boolean} force - If true, re-onboard even if already completed.
     */
    async launchToPlatform(id, force = false) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(`proposals/${id}/launch-to-platform/`, { force });
        if (this.currentProposal?.id === id) {
          this.currentProposal = response.data;
        }
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'launch_to_platform_failed';
        console.error('Error launching to platform:', error);
        return { success: false, errors: error.response?.data, status: error.response?.status };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * pollOnboardingStatus: Poll proposal detail until onboarding completes or fails.
     * @param {number} id - Proposal ID.
     * @param {Function} onUpdate - Callback with updated proposal data.
     * @param {number} interval - Polling interval in ms (default 3000).
     * @param {number} maxAttempts - Max polls before giving up (default 60).
     * @returns {Function} cancel - Call to stop polling.
     */
    pollOnboardingStatus(id, onUpdate, interval = 3000, maxAttempts = 60) {
      let attempts = 0;
      let stopped = false;

      const poll = async () => {
        if (stopped) return;
        attempts++;
        try {
          const response = await get_request(`proposals/${id}/detail/`);
          const data = response.data;
          const status = data.platform_onboarding_status;
          if (status !== 'pending' || attempts >= maxAttempts) {
            stopped = true;
            if (this.currentProposal?.id === id) {
              this.currentProposal = data;
            }
            onUpdate(data);
            return;
          }
        } catch (error) {
          console.error('Error polling onboarding status:', error);
        }
        if (!stopped) {
          setTimeout(poll, interval);
        }
      };

      setTimeout(poll, interval);
      return () => { stopped = true; };
    },

    /**
     * fetchScorecard: Get pre-send scorecard for a proposal.
     * @param {number} id - Proposal ID.
     */
    async fetchScorecard(id) {
      try {
        const response = await get_request(`proposals/${id}/scorecard/`);
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching scorecard:', error);
        return { success: false };
      }
    },

    /**
     * updateSection: Update a proposal section's content.
     * @param {number} sectionId - Section ID.
     * @param {object} payload - Fields to update (content_json, title, etc.).
     */
    async updateSection(sectionId, payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await patch_request(
          `proposals/sections/${sectionId}/update/`,
          payload,
        );
        const { section, proposal_totals, investment_section } = response.data || {};
        if (this.currentProposal) {
          const replaceSection = (s) => {
            const i = this.currentProposal.sections?.findIndex((x) => x.id === s.id);
            if (i != null && i !== -1) this.currentProposal.sections[i] = s;
          };
          if (section) replaceSection(section);
          if (investment_section) replaceSection(investment_section);
          if (proposal_totals) {
            this.currentProposal.total_investment = proposal_totals.total_investment;
            this.currentProposal.effective_total_investment =
              proposal_totals.effective_total_investment;
          }
        }
        return { success: true, data: section };
      } catch (error) {
        this.error = 'update_section_failed';
        console.error('Error updating section:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * previewSync: Compute a read-only diff between the submitted content_json
     * and the current project state. Does not save anything.
     * @param {number} sectionId - Section ID.
     * @param {object} contentJson - The new content_json to preview.
     */
    async previewSync(sectionId, contentJson) {
      try {
        const response = await create_request(
          `proposals/sections/${sectionId}/sync-preview/`,
          { content_json: contentJson },
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error previewing sync:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      }
    },

    /**
     * applySync: Save content_json and sync project requirements (with deletions).
     * @param {number} sectionId - Section ID.
     * @param {object} contentJson - The new content_json to save and sync.
     */
    async applySync(sectionId, contentJson) {
      this.isUpdating = true;
      try {
        const response = await create_request(
          `proposals/sections/${sectionId}/apply-sync/`,
          { content_json: contentJson },
        );
        if (this.currentProposal?.sections && response.data.section) {
          const idx = this.currentProposal.sections.findIndex(
            (s) => s.id === sectionId,
          );
          if (idx !== -1) {
            this.currentProposal.sections[idx] = response.data.section;
          }
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error applying sync:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * reorderSections: Bulk reorder sections.
     * @param {number} proposalId - Proposal ID.
     * @param {Array} sections - Array of { id, order }.
     */
    async reorderSections(proposalId, sections) {
      this.isUpdating = true;
      try {
        await create_request(
          `proposals/${proposalId}/reorder-sections/`,
          { sections },
        );
        // Update local order
        if (this.currentProposal?.sections) {
          const orderMap = Object.fromEntries(
            sections.map((s) => [s.id, s.order]),
          );
          this.currentProposal.sections.forEach((s) => {
            if (orderMap[s.id] !== undefined) {
              s.order = orderMap[s.id];
            }
          });
        }
        return { success: true };
      } catch (error) {
        console.error('Error reordering sections:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * createSection: add a section of a given type, seeded server-side from
     * the language defaults. Pushes the returned section into currentProposal.
     */
    async createSection(proposalId, sectionType) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `proposals/${proposalId}/sections/create/`,
          { section_type: sectionType },
        );
        const { section, proposal_totals } = response.data || {};
        if (this.currentProposal && section) {
          this.currentProposal.sections = [
            ...(this.currentProposal.sections || []),
            section,
          ];
          if (proposal_totals) {
            this.currentProposal.total_investment = proposal_totals.total_investment;
            this.currentProposal.effective_total_investment =
              proposal_totals.effective_total_investment;
          }
        }
        return { success: true, data: section };
      } catch (error) {
        this.error = 'create_section_failed';
        console.error('Error creating section:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * deleteSection: remove a section from the proposal (guarded server-side
     * for functional_requirements with a confirmed calculator selection).
     */
    async deleteSection(sectionId) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await delete_request(`proposals/sections/${sectionId}/delete/`);
        const proposal_totals = response.data?.proposal_totals;
        if (this.currentProposal?.sections) {
          this.currentProposal.sections = this.currentProposal.sections.filter(
            (s) => s.id !== sectionId,
          );
          if (proposal_totals) {
            this.currentProposal.total_investment = proposal_totals.total_investment;
            this.currentProposal.effective_total_investment =
              proposal_totals.effective_total_investment;
          }
        }
        return { success: true };
      } catch (error) {
        this.error = 'delete_section_failed';
        console.error('Error deleting section:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    // -----------------------------------------------------------------
    // Auth
    // -----------------------------------------------------------------

    /**
     * respondToProposal: Client accepts or rejects a proposal.
     * @param {string} uuid - Proposal UUID.
     * @param {string} action - 'accepted' or 'rejected'.
     * @param {object} extra - Optional { reason, comment } for rejections.
     */
    async respondToProposal(uuid, action, extra = {}) {
      try {
        const response = await create_request(`proposals/${uuid}/respond/`, { action, ...extra });
        if (this.currentProposal && this.currentProposal.uuid === uuid) {
          this.currentProposal.status = action;
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error responding to proposal:', error);
        return { success: false };
      }
    },

    /**
     * commentOnProposal: Client submits a negotiation comment before deciding.
     * @param {string} uuid - Proposal UUID.
     * @param {string} comment - Client's comment text.
     */
    async commentOnProposal(uuid, comment) {
      try {
        const response = await create_request(`proposals/${uuid}/comment/`, { comment });
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error submitting proposal comment:', error);
        return { success: false };
      }
    },

    /**
     * trackSectionViews: Send section engagement data for a proposal.
     * @param {string} uuid - Proposal UUID.
     * @param {object} payload - { session_id, sections }.
     */
    async trackSectionViews(uuid, payload) {
      try {
        await create_request(`proposals/${uuid}/track/`, payload);
        return { success: true };
      } catch (error) {
        console.error('Error tracking section views:', error);
        return { success: false };
      }
    },

    /**
     * fetchProposalAnalytics: Retrieve engagement analytics for a proposal.
     * @param {number} id - Proposal ID.
     */
    async fetchProposalAnalytics(id) {
      try {
        const response = await get_request(`proposals/${id}/analytics/`);
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching proposal analytics:', error);
        return { success: false };
      }
    },

    /** Retry a failed first-view notification delivery. */
    async retryFirstViewNotification(id) {
      try {
        const response = await create_request(
          `proposals/${id}/notifications/first-view/retry/`,
          {},
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error retrying first-view notification:', error);
        return { success: false };
      }
    },

    /**
     * fetchProposalDashboard: Retrieve global KPI metrics for all proposals.
     */
    async fetchProposalDashboard() {
      try {
        const response = await get_request('proposals/dashboard/');
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching proposal dashboard:', error);
        return { success: false };
      }
    },

    /**
     * scheduleFollowup: Schedule a follow-up reminder for a rejected proposal.
     * @param {string} uuid - Proposal UUID.
     * @param {number} months - Number of months until follow-up.
     */
    async scheduleFollowup(uuid, months = 3) {
      try {
        const response = await create_request(`proposals/${uuid}/schedule-followup/`, { months });
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error scheduling followup:', error);
        return { success: false };
      }
    },

    /**
     * shareProposal: Create a tracked share link for a proposal.
     * @param {string} uuid - Proposal UUID.
     * @param {object} payload - { name, email }.
     */
    async shareProposal(uuid, payload) {
      try {
        const response = await create_request(`proposals/${uuid}/share/`, payload);
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error sharing proposal:', error);
        return { success: false };
      }
    },

    /**
     * fetchSharedProposal: Retrieve a proposal via a share link UUID.
     * @param {string} shareUuid - Share link UUID.
     * @param {object} params - Optional { name, email } query params.
     */
    async fetchSharedProposal(shareUuid, params = {}) {
      this.isLoading = true;
      this.error = null;
      try {
        const query = new URLSearchParams(params).toString();
        const url = query ? `proposals/shared/${shareUuid}/?${query}` : `proposals/shared/${shareUuid}/`;
        const response = await get_request(url);
        this.currentProposal = response.data;
        return { success: true, data: response.data };
      } catch (error) {
        const status = error.response?.status;
        if (status === 410) {
          this.error = 'expired';
        } else if (status === 404) {
          this.error = 'not_found';
        } else {
          this.error = 'unknown';
        }
        return { success: false, error: this.error, status };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchClients: List all unique clients with their proposal history.
     */
    async fetchClients() {
      try {
        const response = await get_request('proposals/clients/');
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching clients:', error);
        return { success: false };
      }
    },

    /**
     * logActivity: Manually log a seller activity on a proposal.
     */
    async logActivity(proposalId, payload) {
      try {
        const response = await create_request(`proposals/${proposalId}/log-activity/`, payload);
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error logging activity:', error);
        return { success: false };
      }
    },

    /**
     * fetchAlerts: Get proposals that need attention (not viewed, not responded, expiring).
     */
    async fetchAlerts() {
      try {
        const response = await get_request('proposals/alerts/');
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching alerts:', error);
        return { success: false, data: [] };
      }
    },

    /**
     * createAlert: Create a manual alert/reminder for a proposal.
     * @param {object} payload - { proposal, alert_type, message, alert_date }
     */
    async createAlert(payload) {
      try {
        const response = await create_request('proposals/alerts/create/', payload);
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error creating alert:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      }
    },

    /**
     * dismissAlert: Dismiss a manual or computed alert.
     * @param {number} alertId - Manual alert ID, or proposal ID for computed alerts.
     * @param {object} payload - Optional payload for computed alerts.
     */
    async dismissAlert(alertId, payload = {}) {
      try {
        await patch_request(`proposals/alerts/${alertId}/dismiss/`, payload);
        return { success: true };
      } catch (error) {
        console.error('Error dismissing alert:', error);
        return { success: false };
      }
    },

    /**
     * bulkAction: Perform a batch action on multiple proposals.
     * @param {Array} ids - Proposal IDs.
     * @param {string} action - 'delete' | 'expire' | 'resend'.
     */
    async bulkAction(ids, action) {
      try {
        const response = await create_request('proposals/bulk-action/', { ids, action });
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error performing bulk action:', error);
        return { success: false };
      }
    },

    /**
     * checkAdminAuth: Verify if the current session is an authenticated staff user.
     */
    async checkAdminAuth() {
      try {
        const response = await get_request('auth/check/');
        this.adminUser = response.data.user;
        return { success: true, user: response.data.user };
      } catch (error) {
        this.adminUser = null;
        return { success: false, status: error?.response?.status ?? null };
      }
    },

    // -----------------------------------------------------------------
    // Proposal Default Config
    // -----------------------------------------------------------------

    /**
     * fetchProposalDefaults: Retrieve default section config for a language.
     * @param {string} lang - 'es' or 'en'.
     */
    async fetchProposalDefaults(lang = 'es') {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(`proposals/defaults/?lang=${lang}`);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_defaults_failed';
        console.error('Error fetching proposal defaults:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * saveProposalDefaults: Save (create or update) default section config.
     * @param {string} lang - 'es' or 'en'.
     * @param {Array|null} sectionsJson - Full array of section dicts.
     * @param {Object|null} generalConfig - Optional general defaults payload.
     * @param {string|null} baseUpdatedAt - updated_at of the version being
     *   edited. Sent with a wholesale sections_json write so the backend
     *   answers 409 ('stale_defaults') instead of overwriting a newer version.
     */
    async saveProposalDefaults(lang, sectionsJson, generalConfig = null, baseUpdatedAt = null) {
      this.isUpdating = true;
      this.error = null;
      try {
        const payload = {
          language: lang,
        };
        if (Array.isArray(sectionsJson)) {
          payload.sections_json = sectionsJson;
          if (baseUpdatedAt) {
            payload.base_updated_at = baseUpdatedAt;
          }
        }
        if (generalConfig && typeof generalConfig === 'object') {
          const fieldMap = {
            currency: 'default_currency',
            total_investment: 'default_total_investment',
            hosting_percent: 'hosting_percent',
            hosting_discount_nine_month: 'hosting_discount_nine_month',
            hosting_discount_semiannual: 'hosting_discount_semiannual',
            hosting_discount_quarterly: 'hosting_discount_quarterly',
            expiration_days: 'expiration_days',
            reminder_days: 'reminder_days',
            urgency_reminder_days: 'urgency_reminder_days',
            discount_percent: 'default_discount_percent',
            default_slug_pattern: 'default_slug_pattern',
          };
          for (const [formKey, backendKey] of Object.entries(fieldMap)) {
            const value = generalConfig[formKey];
            if (value !== undefined && value !== null) {
              payload[backendKey] = value;
            }
          }
        }
        const response = await put_request('proposals/defaults/', {
          ...payload,
        });
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'save_defaults_failed';
        console.error('Error saving proposal defaults:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * resetProposalDefaults: Reset defaults to hardcoded values for a language.
     * @param {string} lang - 'es' or 'en'.
     */
    async resetProposalDefaults(lang = 'es') {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request('proposals/defaults/reset/', { language: lang });
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'reset_defaults_failed';
        console.error('Error resetting proposal defaults:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    // -----------------------------------------------------------------
    // Email Templates
    // -----------------------------------------------------------------

    /**
     * fetchEmailTemplates: Retrieve the list of all email templates.
     */
    async fetchEmailTemplates() {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request('email-templates/');
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_email_templates_failed';
        console.error('Error fetching email templates:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * fetchEmailTemplateDetail: Retrieve a single template's editable fields.
     * @param {string} templateKey - The template_key identifier.
     */
    async fetchEmailTemplateDetail(templateKey) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(`email-templates/${templateKey}/`);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_email_template_detail_failed';
        console.error('Error fetching email template detail:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * saveEmailTemplate: Save content overrides for a template.
     * @param {string} templateKey - The template_key identifier.
     * @param {Object} payload - { content_overrides: {}, is_active: bool }
     */
    async saveEmailTemplate(templateKey, payload) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await put_request(`email-templates/${templateKey}/`, payload);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'save_email_template_failed';
        console.error('Error saving email template:', error);
        return { success: false, errors: error.response?.data, ...normalizeApiError(error) };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * previewEmailTemplate: Get HTML preview of a template with sample data.
     * @param {string} templateKey - The template_key identifier.
     */
    async previewEmailTemplate(templateKey) {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request(`email-templates/${templateKey}/preview/`);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'preview_email_template_failed';
        console.error('Error previewing email template:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * resetEmailTemplate: Reset a template to default values.
     * @param {string} templateKey - The template_key identifier.
     */
    async resetEmailTemplate(templateKey) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(`email-templates/${templateKey}/reset/`);
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'reset_email_template_failed';
        console.error('Error resetting email template:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * fetchEmailDeliverability: Retrieve email deliverability dashboard stats.
     */
    async fetchEmailDeliverability() {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await get_request('email-deliverability/');
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'fetch_email_deliverability_failed';
        console.error('Error fetching email deliverability:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isLoading = false;
      }
    },

    /**
     * requestMagicLink: Request proposal link(s) to be sent to a client email.
     * @param {string} email - Client email address.
     */
    async requestMagicLink(email) {
      try {
        await create_request('proposals/request-link/', { email });
        return { success: true };
      } catch (error) {
        console.error('Error requesting magic link:', error);
        return { success: false };
      }
    },

    /**
     * fetchCompanySettings: Get seller company defaults for contract modal.
     */
    async fetchCompanySettings() {
      try {
        const response = await get_request('proposals/company-settings/');
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching company settings:', error);
        return { success: false };
      }
    },

    /** Save the complete global service-term configuration. */
    async saveServiceContractSettings(settings) {
      try {
        const response = await patch_request('proposals/company-settings/', { service_contract_settings: settings });
        return { success: true, data: response.data };
      } catch (error) {
        return { success: false, errors: error.response?.data?.service_contract_settings || {} };
      }
    },

    /** Get the default contract template markdown. */
    async fetchDefaultContractTemplate() {
      try {
        const response = await get_request('proposals/contract-template/default/');
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error fetching default contract template:', error);
        return { success: false };
      }
    },

    /**
     * saveContractAndNegotiate: Save contract params, generate PDF, move to negotiating.
     * @param {number} proposalId
     * @param {Object} contractParams
     */
    async saveContractAndNegotiate(proposalId, contractParams) {
      this.isUpdating = true;
      this.error = null;
      try {
        const response = await create_request(
          `proposals/${proposalId}/contract/save-and-negotiate/`,
          { contract_params: contractParams },
        );
        if (this.currentProposal?.id === proposalId) {
          this.currentProposal = response.data;
        }
        const idx = this.proposals.findIndex((p) => p.id === proposalId);
        if (idx !== -1) {
          this.proposals[idx] = { ...this.proposals[idx], ...response.data };
        }
        return { success: true, data: response.data };
      } catch (error) {
        this.error = 'contract_save_failed';
        console.error('Error saving contract and negotiating:', error);
        return { success: false };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * updateContractParams: Update contract params and regenerate the
     * contracts of the proposal's closing modality.
     * @param {number} proposalId
     * @param {Object} contractParams - Only the keys being edited; the backend
     *   merges them over the saved parameters.
     * @param {string} [variant] - Document being generated or edited
     *   ('combined', 'product' or 'service').
     */
    async updateContractParams(proposalId, contractParams, variant) {
      this.isUpdating = true;
      try {
        const payload = { contract_params: contractParams };
        if (variant) payload.variant = variant;
        const response = await patch_request(
          `proposals/${proposalId}/contract/update/`,
          payload,
        );
        if (this.currentProposal?.id === proposalId) {
          this.currentProposal = response.data;
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error updating contract params:', error);
        return { success: false, ...normalizeApiError(error, 'No se pudo guardar el contrato.') };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * updateContractModality: Choose whether a negotiated deal closes with one
     * contract ('single') or with product and service contracts ('split').
     * @param {number} proposalId
     * @param {string} modality
     */
    async updateContractModality(proposalId, modality) {
      this.isUpdating = true;
      try {
        const response = await patch_request(
          `proposals/${proposalId}/contract/modality/`,
          { contract_modality: modality },
        );
        if (this.currentProposal?.id === proposalId) {
          this.currentProposal = response.data;
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error updating contract modality:', error);
        return { success: false, ...normalizeApiError(error, 'No se pudo cambiar la modalidad de cierre.') };
      /* c8 ignore next 3 */
      } finally {
        this.isUpdating = false;
      }
    },

    /**
     * uploadProposalDocument: Upload a document to a proposal.
     * @param {number} proposalId
     * @param {FormData} formData - Must include 'file', optionally 'title' and 'document_type'
     */
    async uploadProposalDocument(proposalId, formData) {
      try {
        const response = await create_request(
          `proposals/${proposalId}/documents/upload/`,
          formData,
        );
        if (this.currentProposal?.id === proposalId) {
          await this.fetchProposal(proposalId);
        }
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error uploading proposal document:', error);
        return { success: false };
      }
    },

    /**
     * sendDocumentsToClient: Send selected documents to the client via email.
     * @param {number} proposalId
     * @param {Object} payload - { documents, additional_doc_ids, subject, greeting, body, footer, document_descriptions }
     */
    async sendDocumentsToClient(proposalId, payload) {
      try {
        const response = await create_request(
          `proposals/${proposalId}/documents/send/`,
          payload,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error sending documents to client:', error);
        return { success: false };
      }
    },

    async sendDiscountOffer(proposalId) {
      try {
        const response = await create_request(
          `proposals/${proposalId}/discount-offer/send/`,
          {},
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error sending discount offer:', error);
        return { success: false, message: error.response?.data?.error };
      }
    },

    /**
     * deleteProposalDocument: Delete a user-uploaded proposal document.
     * @param {number} proposalId
     * @param {number} docId
     */
    async deleteProposalDocument(proposalId, docId) {
      try {
        await delete_request(`proposals/${proposalId}/documents/${docId}/delete/`);
        if (this.currentProposal?.id === proposalId) {
          await this.fetchProposal(proposalId);
        }
        return { success: true };
      } catch (error) {
        console.error('Error deleting proposal document:', error);
        return { success: false };
      }
    },

    /**
     * Send a user-composed email for a proposal.
     * @param {number} proposalId
     * @param {FormData} formData
     * @param {string} basePath - 'branded-email' or 'proposal-email'
     */
    async sendComposedEmail(proposalId, formData, basePath = 'branded-email') {
      try {
        const response = await create_request(
          `proposals/${proposalId}/${basePath}/send/`,
          formData,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error sending ${basePath}:`, error);
        return { success: false };
      }
    },

    /**
     * Get admin-configurable defaults for an email composer.
     * @param {number} proposalId
     * @param {string} basePath - 'branded-email' or 'proposal-email'
     */
    async fetchEmailDefaults(proposalId, basePath = 'branded-email') {
      try {
        const response = await get_request(
          `proposals/${proposalId}/${basePath}/defaults/`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error fetching ${basePath} defaults:`, error);
        return { success: false, data: {} };
      }
    },

    /**
     * Fetch paginated email history for a proposal.
     * @param {number} proposalId
     * @param {number} page
     * @param {string} basePath - 'branded-email' or 'proposal-email'
     */
    async fetchEmailHistory(proposalId, page = 1, basePath = 'branded-email') {
      try {
        const response = await get_request(
          `proposals/${proposalId}/${basePath}/history/?page=${page}`,
        );
        return { success: true, data: response.data };
      } catch (error) {
        console.error(`Error fetching ${basePath} history:`, error);
        return { success: false, data: { results: [], total: 0, page: 1, has_next: false } };
      }
    },

    // -----------------------------------------------------------------
    // Project schedule (Cronograma)
    // -----------------------------------------------------------------

    /**
     * updateProjectStage: PUT start_date / end_date for a stage.
     * On success, replaces the matching stage in
     * `currentProposal.project_stages` so the UI reflects the new dates.
     * @param {number} proposalId
     * @param {string} stageKey - 'design' | 'development'
     * @param {{ start_date?: string, end_date?: string }} dates
     * @returns {Promise<{ success: boolean, data?: object, error?: object }>}
     */
    async updateProjectStage(proposalId, stageKey, dates) {
      try {
        const response = await put_request(
          `proposals/${proposalId}/stages/${stageKey}/`,
          dates,
        );
        this._mergeProjectStage(proposalId, response.data);
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error updating project stage:', error);
        return { success: false, error: error?.response?.data || null };
      }
    },

    /**
     * completeProjectStage: POST to mark a stage as completed.
     * @param {number} proposalId
     * @param {string} stageKey - 'design' | 'development'
     * @returns {Promise<{ success: boolean, data?: object }>}
     */
    async completeProjectStage(proposalId, stageKey) {
      try {
        const response = await create_request(
          `proposals/${proposalId}/stages/${stageKey}/complete/`,
          {},
        );
        this._mergeProjectStage(proposalId, response.data);
        return { success: true, data: response.data };
      } catch (error) {
        console.error('Error completing project stage:', error);
        return { success: false };
      }
    },

    /**
     * Replace (or insert) a stage in `currentProposal.project_stages`,
     * mutating the array in place. Matches the existing pattern used by
     * updateSection / applySync / reorderSections in this same store.
     *
     * @param {number} proposalId
     * @param {object} stage
     */
    _mergeProjectStage(proposalId, stage) {
      if (!this.currentProposal || this.currentProposal.id !== proposalId) return;
      if (!Array.isArray(this.currentProposal.project_stages)) {
        this.currentProposal.project_stages = [];
      }
      const idx = this.currentProposal.project_stages.findIndex(
        (s) => s.stage_key === stage.stage_key,
      );
      if (idx !== -1) {
        this.currentProposal.project_stages[idx] = stage;
      } else {
        this.currentProposal.project_stages.push(stage);
      }
    },
  },
});
