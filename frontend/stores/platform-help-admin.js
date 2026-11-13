import { defineStore } from 'pinia'
import { get_request, create_request, patch_request } from '~/stores/services/request_http'
const request_http = (method, url, data, config) => method === 'GET' ? get_request(url, config) : method === 'POST' ? create_request(url, data) : patch_request(url, data)
const base = 'platform/help/'
export const usePlatformHelpAdminStore = defineStore('platform-help-admin', {
  state: () => ({
    settings: null, tours: [], targets: {},
    clients: { results: [], page: 1, count: 0 },
    clientsLoading: false, clientsError: false, clientsSearch: '', clientsGeneration: 0,
    progress: { results: [], page: 1, count: 0 },
  }),
  actions: {
    async load() {
      const [settings, catalog] = await Promise.all([request_http('GET', `${base}settings/`), request_http('GET', `${base}admin/tours/`)])
      this.settings = settings.data; this.tours = catalog.data.results; this.targets = catalog.data.targets
    },
    invalidateClients(search = '') {
      // Invalidate immediately, including the debounce window before the next GET.
      this.clientsGeneration += 1;
      this.clientsSearch = search;
      this.clients = { results: [], page: 1, count: 0 };
      this.clientsLoading = true;
      this.clientsError = false;
    },
    cancelClients() {
      this.clientsGeneration += 1;
      this.clientsLoading = false;
    },
    async loadClients(page = 1, search = '') {
      const generation = ++this.clientsGeneration;
      this.clientsSearch = search;
      this.clientsLoading = true;
      this.clientsError = false;
      this.clients = { results: [], page, count: 0 };
      try {
        const response = await request_http('GET', `${base}clients/`, null, { params: { page, search } });
        if (generation === this.clientsGeneration) this.clients = response.data;
      } catch {
        if (generation === this.clientsGeneration) this.clientsError = true;
      } finally {
        if (generation === this.clientsGeneration) this.clientsLoading = false;
      }
    },
    async loadProgress(page = 1) { this.progress = (await request_http('GET', `${base}admin/progress/`, null, { params: { page } })).data },
    async saveFlags(flags, userId) { return (await request_http('PATCH', `${base}${userId ? `clients/${userId}/` : 'settings/'}`, { expected_version: flags.version, tour_enabled: flags.tour_enabled, video_enabled: flags.video_enabled })).data },
    async saveTour(tour) {
      const payload = { slug: tour.slug, context: tour.context, kind: tour.kind || 'novelty', priority: Number(tour.priority), is_active: tour.is_active, content: tour.content, ...(tour.id ? { expected_version: tour.version } : {}) }
      return (await request_http(tour.id ? 'PATCH' : 'POST', `${base}admin/tours/${tour.id ? `${tour.id}/` : ''}`, payload)).data
    },
    async publish(tour) { return (await request_http('POST', `${base}admin/tours/${tour.id}/publish/`, { expected_version: tour.version })).data },
    async preview(id) { return (await request_http('GET', `${base}admin/tours/${id}/preview/`)).data },
    async revisions(id) { return (await request_http('GET', `${base}admin/tours/${id}/revisions/`)).data.results },
  },
})
