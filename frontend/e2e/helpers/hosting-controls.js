import { expect } from './test.js'
import { mockApi } from './api.js'
import { setAuthLocalStorage } from './auth.js'

const initial = () => ({ id: 1, name: 'Sitio de prueba', client: 'Cliente ficticio', server: 'VPS de prueba', environment: 'production', version: 0, mode: 'normal', suspension_title: 'Servicio suspendido', suspension_text: 'Gestiona la reactivación con tu proveedor.', banner_title: 'Pago pendiente del servicio', banner_text: 'Contacta a tu proveedor.', targets: [{ key: 'fixture', origins: ['https://fixture.example'], state: 'unintegrated', lifecycle: 'active' }] })

export async function setupHostingControls(page, { failure = false, conflict = false, throughProjects = false } = {}) {
  const state = initial()
  await setAuthLocalStorage(page, { token: 'fixture', userAuth: { id: 1, is_staff: true, is_superuser: true, role: 'admin' } })
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true, is_superuser: true } }) }
    if (apiPath === 'projects/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [], meta: { total: 0, by_state: [], review_required: 0, clients_without_projects: 0, records_without_project: 0 } }) }
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/') return { status: 200, contentType: 'application/json', body: '[]' }
    if (apiPath === 'hosting-controls/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [state], page: 1, pages: 1 }) }
    if (apiPath.endsWith('/events/')) return { status: 200, contentType: 'application/json', body: '{"results":[]}' }
    if (apiPath === 'hosting-controls/1/') return { status: 200, contentType: 'application/json', body: JSON.stringify(state) }
    if (method === 'PATCH' && apiPath.startsWith('hosting-controls/1/')) {
      if (failure) return { status: 503, contentType: 'application/json', body: '{"detail":"Fallo de prueba"}' }
      if (conflict) return { status: 409, contentType: 'application/json', body: '{"detail":"Versión anterior"}' }
      const data = route.request().postDataJSON()
      if (data.mode) state.mode = data.mode
      else {
        const prefix = data.message_mode === 'suspended' ? 'suspension' : 'banner'
        state[`${prefix}_title`] = data.title
        state[`${prefix}_text`] = data.text
      }
      state.version += 1
      state.targets[0].state = 'pending'
      return { status: 200, contentType: 'application/json', body: JSON.stringify(state) }
    }
    return null
  })
  await page.goto(throughProjects ? '/panel/projects' : '/panel/projects/hosting', { waitUntil: 'domcontentloaded' })
  if (throughProjects) await page.getByTestId('projects-hosting-control').click()
  await expect(page.getByTestId('hosting-switch-banner')).toBeVisible()
  return state
}
