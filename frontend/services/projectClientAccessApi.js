/** Credentials stay outside list/store payloads and are never persisted. */
export function createProjectClientAccessApi(transport, projectId) {
  const base = `projects/${projectId}/`
  const data = async (request) => (await request).data
  return {
    policy: () => data(transport.get(`${base}access/client-policy/`)),
    updatePolicy: (payload) => data(transport.patch(`${base}access/client-policy/`, payload)),
    preview: () => data(transport.get(`${base}access/client-policy/preview/`)),
    events: (page = 1) => data(transport.get(`${base}access/client-policy/events/?page=${page}`)),
    client: () => data(transport.get(`${base}client-access/`)),
    reveal: (environment, field) => data(transport.post(`${base}client-access/environments/${environment}/credentials/${field}/reveal/`, {})),
  }
}
