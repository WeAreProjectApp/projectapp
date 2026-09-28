import { defineStore } from 'pinia'
import { create_request, get_request } from './services/request_http'

export const useVideoResourcesStore = defineStore('video_resources', {
  state: () => ({ resources: {} }),
  actions: {
    async fetchResource(path, config = {}) {
      const { data } = await get_request(path, config)
      this.resources[data.key] = data
      return data
    },
    async updateResource(path, payload, config = {}) {
      const { data } = await create_request(path, payload, config)
      this.resources[data.key] = data
      return data
    },
  },
})
