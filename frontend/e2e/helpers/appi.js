import { mockApi } from './api.js'
import { mockPlatformClient, setPlatformAuth } from './platform-auth.js'

export const project = {
  id: 7, name: 'Portal de soporte', description: 'Proyecto visible de Appi.',
  status: 'active', status_label: 'Activo', progress: 62, client_id: mockPlatformClient.id,
  client_name: 'Client E2E', client_email: mockPlatformClient.email, client_company: mockPlatformClient.company_name,
  current_state: { id: 1, name: 'Activo', system_key: 'active', operational_effect: 'operating', color: 'emerald' },
  bugs_open_count: 0, changes_pending_count: 0, phases_total_amount: 0, last_activity_at: '2026-10-24T12:00:00Z',
}

export const quota = (overrides = {}) => ({
  used: 1, limit: 5, remaining: 4, window_minutes: 60, next_available_at: '2026-10-24T13:00:00Z', ...overrides,
})

export const capabilities = (overrides = {}) => ({
  chatbot: { enabled: true, available: true, voice_available: false }, quota: quota(), ...overrides,
})

export const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })

export const readyMessage = (overrides = {}) => ({
  id: 90, status: 'ready', question: '¿Cómo va mi proyecto?', freshness: 'current',
  answer: { text: 'El proyecto avanza según lo previsto.', verified_at: '2026-10-24T12:00:00Z', sources: [], actions: [] },
  ...overrides,
})

export const conversation = (overrides = {}) => ({ id: 42, title: 'Estado del portal', language: 'es', project_id: 7, ...overrides })
export const detail = (messages, overrides = {}) => ({ conversation: conversation(), messages, quota: quota(), next_before: null, ...overrides })

/** Mock only the client-facing Appi HTTP boundary; Appi business rules remain backend-owned. */
export async function setupAppi(page, { user = mockPlatformClient, appiCapabilities = capabilities(), conversations = [], details = {}, request } = {}) {
  await setPlatformAuth(page, { user })
  return mockApi(page, async (context) => {
    const { apiPath, method, route } = context
    const custom = request && await request(context)
    if (custom) return custom
    if (apiPath === 'accounts/me/' && method === 'GET') return json(user)
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([project])
    if (apiPath === `accounts/projects/${project.id}/` && method === 'GET') return json(project)
    if (apiPath === `accounts/projects/${project.id}/phases/` && method === 'GET') return json([])
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') return json({ unread_count: 0 })
    if (apiPath === 'platform/help/' && method === 'GET') return json({ tour_enabled: false, video_enabled: false, tours: [] })
    if (apiPath === 'platform/ai/capabilities/' && method === 'GET') return json(appiCapabilities)
    if (apiPath === 'projects/' && method === 'GET') return json([project])
    if (apiPath === 'platform/chatbot/conversations/' && method === 'GET') return json({ results: conversations })
    const detail = apiPath.match(/^platform\/chatbot\/conversations\/(\d+)\/$/)
    if (detail && method === 'GET') return json(details[detail[1]] || { conversation: conversation({ id: Number(detail[1]) }), messages: [], quota: appiCapabilities.quota, next_before: null })
    if (apiPath === 'platform/chatbot/conversations/' && method === 'POST') {
      const body = JSON.parse(route.request().postData() || '{}')
      return json(conversation({ project_id: body.project_id ?? null, language: body.language || 'es' }))
    }
    return null
  })
}

export async function visitClientProject(page) {
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
  await page.getByTestId(`project-row-${project.id}`).or(page.getByTestId(`project-card-${project.id}`)).click()
  await page.waitForURL(/\/platform\/projects\/7$/)
}

export async function openAppi(page) {
  await page.getByTestId('appi-launcher').click()
  return page.getByTestId('appi-panel')
}
