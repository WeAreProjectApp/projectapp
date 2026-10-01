/** Domain transport: panel uses request_http, platform uses usePlatformApi. */
export function createProjectIdeasApi(transport, projectId) {
  const base = `projects/${projectId}/`
  const data = async (request) => (await request).data
  return {
    list: (page = 1) => data(transport.get(`${base}ideas/?page=${page}`)),
    create: (payload) => data(transport.post(`${base}ideas/`, payload)),
    edit: (id, payload) => data(transport.patch(`${base}ideas/${id}/`, payload)),
    revisions: (id, page = 1) => data(transport.get(`${base}ideas/${id}/revisions/?page=${page}`)),
    archive: (id, payload) => data(transport.post(`${base}ideas/${id}/archive/`, payload)),
    restore: (id, payload) => data(transport.post(`${base}ideas/${id}/restore/`, payload)),
    collections: (page = 1) => data(transport.get(`${base}idea-collections/?page=${page}`)),
    collect: (payload) => data(transport.post(`${base}idea-collections/`, payload)),
    collection: (id) => data(transport.get(`${base}idea-collections/${id}/`)),
  }
}
