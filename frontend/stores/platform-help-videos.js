import { defineStore } from 'pinia'
import { usePlatformApi } from '~/composables/usePlatformApi'
import { explainerVideoFor } from '~/composables/useExplainerVideos'

export const usePlatformHelpVideosStore = defineStore('platformHelpVideos', {
  state: () => ({
    resources: [], enabled: false, isLoading: false, isOpen: false,
    selectedTopic: 'general', error: false, requestVersion: 0,
  }),
  getters: {
    videos: (state) => state.enabled ? state.resources.flatMap((item) => {
      const video = item.resource?.mode === 'uploaded'
        ? item.resource.video
        : item.resource?.mode === 'default' ? explainerVideoFor(item.module, item.language) : null
      return video?.src ? [{ ...video, topic: item.topic, language: item.language }] : []
    }) : [],
    videoAvailable() { return this.videos.length > 0 },
    selectedVideo() { return this.videos.find((item) => item.topic === this.selectedTopic) || null },
  },
  actions: {
    async fetchVideos() {
      const version = ++this.requestVersion
      this.isLoading = true
      this.error = false
      try {
        const { get } = usePlatformApi()
        const { data } = await get('/api/platform/help/videos/', { baseURL: '' })
        if (version !== this.requestVersion) return false
        this.enabled = data.enabled === true
        this.resources = data.videos || []
        if (this.isOpen && !this.selectedVideo) this.isOpen = false
        return true
      } catch {
        if (version !== this.requestVersion) return false
        this.enabled = false
        this.resources = []
        this.isOpen = false
        this.error = true
        return false
      } finally {
        if (version === this.requestVersion) this.isLoading = false
      }
    },
    async openVideo(topic = 'general') {
      if (!await this.fetchVideos()) return false
      const video = this.videos.find((item) => item.topic === topic)
        || (topic === 'general' ? this.videos[0] : null)
      if (!video) return false
      this.selectedTopic = video.topic
      this.isOpen = true
      return true
    },
    selectVideo(topic) {
      if (this.videos.some((item) => item.topic === topic)) this.selectedTopic = topic
    },
    closeVideo() {
      this.requestVersion += 1
      this.isLoading = false
      this.isOpen = false
    },
    reset() {
      const version = this.requestVersion + 1
      this.$reset()
      this.requestVersion = version
    },
  },
})
