import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import catalog from '../../../contracts/platform-features.json'

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })
const flags = () => Object.fromEntries(catalog.features.map(item => [item.key, item.default_enabled]))

async function setup(page, { failure = 0 } = {}) {
  const state = { values: flags(), version: 0, overrides: {}, clientVersion: 0 }
  const payload = (client = false) => ({ version: client ? state.clientVersion : state.version,
    global_version: state.version, user_id: client ? 9002 : null, name: client ? 'Cliente QA' : null,
    features: catalog.features.map(item => ({ ...item, global_value: state.values[item.key],
      override: client ? state.overrides[item.key] ?? null : null,
      effective: client ? state.overrides[item.key] ?? state.values[item.key] : state.values[item.key],
      source: client && item.key in state.overrides ? 'client' : 'global' })) })
  await setAuthLocalStorage(page, { token: 'feature-admin', userAuth: { id: 51, role: 'admin', is_staff: true, is_superuser: true } })
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'feature-admin', is_staff: true, is_superuser: true } })
    if (apiPath === 'platform/features/admin/clients/') return json({ results: [{ user_id: 9002, name: 'Cliente QA' }], count: 1, page: 1 })
    if (apiPath === 'platform/features/admin/events/') return json({ results: [], page: 1, count: 0 })
    if (apiPath === 'platform/features/admin/' || apiPath === 'platform/features/admin/clients/9002/') {
      const client = apiPath.includes('/clients/')
      if (method === 'PATCH') {
        if (failure) return json({ detail: 'Cambio rechazado.' }, failure)
        const body = route.request().postDataJSON()
        Object.entries(body.values).forEach(([key, value]) => {
          const values = client ? state.overrides : state.values
          if (value === null) delete values[key]
          else values[key] = value
        })
        if (client) state.clientVersion += 1
        else state.version += 1
      }
      return json(payload(client))
    }
    return null
  })
  return state
}

async function open(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' })
  await page.getByRole('link', { name: 'Feature flags', exact: true }).click()
  await expect(page.getByTestId('platform-feature-admin')).toContainText('Feature flags de Plataforma')
}

async function choose(page, key, option) {
  const row = page.getByTestId(`feature-${key}`)
  await row.getByRole('button').click()
  await page.getByRole('menuitem', { name: option, exact: true }).click()
  return row
}

test.describe('PA-263 availability administration', () => {
  test.setTimeout(60_000)

  test('panel navigation exposes the initial availability', { tag: ['@flow:panel-platform-feature-flags', '@outcome:display'] }, async ({ page }) => {
    await setup(page)
    await open(page)

    await expect(page.getByTestId('feature-platform.documents').getByTestId('feature-effective')).toHaveText('Valor efectivo: Habilitada')
    await expect(page.getByTestId('feature-platform.ai_chatbot').getByTestId('feature-effective')).toHaveText('Valor efectivo: Deshabilitada')
  })

  test('global change survives reloading', { tag: ['@flow:panel-platform-feature-flags', '@outcome:success'] }, async ({ page }) => {
    await setup(page)
    await open(page)
    await choose(page, 'platform.documents', 'Deshabilitada')
    await expect(page.getByRole('status')).toHaveText('Configuración guardada.')

    await page.reload({ waitUntil: 'domcontentloaded' })

    await expect(page.getByTestId('feature-platform.documents').getByTestId('feature-effective')).toHaveText('Valor efectivo: Deshabilitada')
  })

  test('client exception can return to inheritance', { tag: ['@flow:panel-platform-feature-flags', '@outcome:success'] }, async ({ page }) => {
    await setup(page)
    await open(page)
    await choose(page, 'platform.documents', 'Deshabilitada')
    await expect(page.getByRole('status')).toHaveText('Configuración guardada.')
    await page.getByRole('button', { name: 'Por cliente', exact: true }).click()
    await page.getByTestId('feature-client-picker').click()
    await page.getByRole('menuitem', { name: 'Cliente QA', exact: true }).click()
    const row = await choose(page, 'platform.documents', 'Habilitada')
    await expect(row).toContainText('Procedencia: Excepción del cliente')

    await choose(page, 'platform.documents', 'Heredar global')

    await expect(row).toContainText('Procedencia: Global')
    await expect(row.getByTestId('feature-effective')).toHaveText('Valor efectivo: Deshabilitada')
  })

  test('conflict preserves the displayed value', { tag: ['@flow:panel-platform-feature-flags', '@outcome:error'] }, async ({ page }) => {
    await setup(page, { failure: 409 })
    await open(page)

    const row = await choose(page, 'platform.documents', 'Deshabilitada')

    await expect(page.getByRole('alert')).toContainText('Otro administrador cambió la configuración')
    await expect(row.getByTestId('feature-effective')).toHaveText('Valor efectivo: Habilitada')
  })

  test('server failure offers a retry', { tag: ['@flow:panel-platform-feature-flags', '@outcome:failure'] }, async ({ page }) => {
    await setup(page, { failure: 503 })
    await open(page)

    await choose(page, 'platform.documents', 'Deshabilitada')

    await expect(page.getByRole('alert')).toContainText('Vuelve a intentarlo')
    await expect(page.getByTestId('feature-platform.documents').getByRole('button')).toBeEnabled()
  })
})
