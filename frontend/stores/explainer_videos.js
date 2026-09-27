import { defineStore } from 'pinia'
import { get_request, patch_request } from './services/request_http'

/** Explainer id (see composables/useExplainerVideos.js) → settings field. */
export const EXPLAINER_VIDEO_SWITCHES = Object.freeze({
  'additional-modules': 'show_additional_modules_video',
  financing: 'show_financing_video',
  proposal: 'show_proposal_video',
})

export const useExplainerVideosStore = defineStore('explainer_videos', {
  /**
   * Panel switches that show or hide each explainer video in the client views.
   *
   * Properties:
   * - settings (Object|null): { show_additional_modules_video, show_financing_video, updated_at }.
   * - isLoading (Boolean): Whether the settings are being fetched.
   * - isUpdating (Boolean): Whether a switch change is being saved.
   */
  state: () => ({
    settings: null,
    isLoading: false,
    isUpdating: false,
  }),

  getters: {
    // A missing flag counts as visible, matching the backend default.
    isVisible: (state) => (module) => (
      state.settings?.[EXPLAINER_VIDEO_SWITCHES[module]] !== false
    ),
  },

  actions: {
    async fetchSettings() {
      this.isLoading = true
      try {
        const response = await get_request('explainer-videos/admin/settings/')
        this.settings = response.data
        return { success: true, data: response.data }
      } catch (error) {
        return { success: false, errors: error.response?.data }
      } finally {
        this.isLoading = false
      }
    },

    /**
     * Show or hide one module's video. The switch flips right away and goes
     * back to its previous state if the save fails.
     */
    async setVisibility(module, visible) {
      const field = EXPLAINER_VIDEO_SWITCHES[module]
      const previous = this.settings
      this.settings = { ...(previous || {}), [field]: visible }
      this.isUpdating = true
      try {
        const response = await patch_request(
          'explainer-videos/admin/settings/update/',
          { [field]: visible },
        )
        this.settings = response.data
        return { success: true, data: response.data }
      } catch (error) {
        this.settings = previous
        return { success: false, errors: error.response?.data }
      } finally {
        this.isUpdating = false
      }
    },
  },
})
