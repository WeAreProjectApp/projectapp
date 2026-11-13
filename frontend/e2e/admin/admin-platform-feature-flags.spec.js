import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import catalog from '../../../contracts/platform-features.json' with { type: 'json' };

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })
const flags = () => Object.fromEntries(catalog.features.map(item => [item.key, item.default_enabled]))

async function setup(page, { failure = 0, loadFailure = 0, clientResponse = null } = {}) {
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
    if (apiPath === 'platform/features/admin/clients/' && clientResponse) return clientResponse({ route })
    if (apiPath === 'platform/features/admin/clients/') return json({ results: [{ user_id: 9002, name: 'Cliente QA' }], count: 1, page: 1 })
    if (apiPath === 'platform/features/admin/events/') return json({ results: [], page: 1, count: 0 })
    if (apiPath === 'platform/features/admin/' || apiPath === 'platform/features/admin/clients/9002/') {
      const client = apiPath.includes('/clients/')
      if (method === 'GET' && loadFailure) {
        const status = loadFailure
        loadFailure = 0
        return json({ detail: 'Configuración temporalmente inaccesible.' }, status)
      }
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

async function openClientSearch(page) {
  await open(page)
  await page.getByRole('button', { name: 'Por cliente', exact: true }).click()
}

async function expectClient(page, name) {
  await expect(page.getByTestId('feature-client-results')).toHaveAttribute('aria-busy', 'false')
  const picker = page.getByTestId('feature-client-picker')
  await picker.click()
  await expect(page.getByRole('menuitem', { name, exact: true })).toBeVisible()
  await picker.click()
  await expect(page.getByRole('menu')).toBeHidden()
}

test.describe('PA-263 availability administration', () => {
  test.setTimeout(60_000)

  test('panel navigation exposes the initial availability', { tag: ['@flow:panel-platform-feature-flags', '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (The authenticated Panel is the entry point; Feature flags is reached through its navigation.)
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

  test('initial configuration failure can be retried', { tag: ['@flow:panel-platform-feature-flags', '@outcome:failure'] }, async ({ page }) => {
    await setup(page, { loadFailure: 503 })
    await open(page)
    await expect(page.getByRole('alert')).toContainText('Vuelve a intentarlo')
    await expect(page.getByTestId('feature-platform.documents')).toHaveCount(0)

    await page.getByRole('button', { name: 'Recargar', exact: true }).first().click()

    await expect(page.getByTestId('feature-platform.documents').getByTestId('feature-effective')).toHaveText('Valor efectivo: Habilitada')
  })
  test('typing a client fragment loads results without submitting', {
    tag: ['@flow:panel-platform-feature-flags', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: typing in the client field could leave stale results until the search button was submitted.
    const requests = []
    await setup(page, {
      clientResponse: ({ route }) => {
        const url = new URL(route.request().url())
        const request = { page: Number(url.searchParams.get('page')), search: url.searchParams.get('search') }
        requests.push(request)
        return json(request.search === 'Diego'
          ? { results: [{ user_id: 82, name: 'Diego Duarte', tour_enabled: true, video_enabled: false }], page: 1, count: 1 }
          : { results: [], page: 1, count: 0 })
      },
    })

    await openClientSearch(page)
    const results = page.getByTestId('feature-client-results')
    await page.getByLabel('Buscar cliente por nombre, correo o empresa', { exact: true }).fill('Diego')

    await expect(results).toHaveAttribute('aria-busy', 'true')
    await expect.poll(() => requests.some((request) => request.search === 'Diego' && request.page === 1)).toBe(true)
    await expectClient(page, 'Diego Duarte')
  })

  test('latest client search response wins when requests resolve out of order', {
    tag: ['@flow:panel-platform-feature-flags', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: a slower prior fragment could overwrite the results for the latest client search.
    const pending = new Map()
    await setup(page, {
      clientResponse: ({ route }) => {
        const search = new URL(route.request().url()).searchParams.get('search')
        if (!search) return json({ results: [], page: 1, count: 0 })
        return new Promise((resolve) => pending.set(search, resolve))
      },
    })

    await openClientSearch(page)
    const search = page.getByLabel('Buscar cliente por nombre, correo o empresa', { exact: true })
    const results = page.getByTestId('feature-client-results')
    await search.fill('Die')
    await expect.poll(() => pending.has('Die')).toBe(true)
    await search.fill('Diego')
    await expect.poll(() => pending.has('Diego')).toBe(true)

    pending.get('Diego')(json({ results: [{ user_id: 83, name: 'Diego Duarte', tour_enabled: true, video_enabled: false }], page: 1, count: 1 }))
    await expectClient(page, 'Diego Duarte')
    pending.get('Die')(json({ results: [{ user_id: 84, name: 'Diego Serrano', tour_enabled: false, video_enabled: true }], page: 1, count: 1 }))

    await expectClient(page, 'Diego Duarte')
    await page.getByTestId('feature-client-picker').click()
    await expect(page.getByRole('menuitem', { name: 'Diego Serrano', exact: true })).toHaveCount(0)
    await page.keyboard.press('Escape')
  })

  test('clearing the client filter returns to the first page', {
    tag: ['@flow:panel-platform-feature-flags', '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: clearing a paged search could retain page two instead of restoring the first client results.
    const requests = []
    await setup(page, {
      clientResponse: ({ route }) => {
        const url = new URL(route.request().url())
        const pageNumber = Number(url.searchParams.get('page'))
        const search = url.searchParams.get('search')
        requests.push({ page: pageNumber, search })
        if (!search) return json({ results: [{ user_id: 85, name: 'Ana Inicio', tour_enabled: true, video_enabled: true }], page: 1, count: 1 })
        if (pageNumber === 2) return json({ results: [{ user_id: 87, name: 'Diego Página dos', tour_enabled: true, video_enabled: false }], page: 2, count: 22 })
        return json({ results: [{ user_id: 86, name: 'Diego Página uno', tour_enabled: true, video_enabled: false }], page: 1, count: 22 })
      },
    })

    await openClientSearch(page)
    const results = page.getByTestId('feature-client-results')
    const clientsSection = results
    const search = page.getByLabel('Buscar cliente por nombre, correo o empresa', { exact: true })
    await search.fill('Diego')
    await expectClient(page, 'Diego Página uno')
    await clientsSection.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expectClient(page, 'Diego Página dos')
    await search.fill('')

    await expectClient(page, 'Ana Inicio')
    await expect.poll(() => requests.at(-1)).toEqual({ page: 1, search: '' })
  })

  test('retrying a failed client search restores the current results', {
    tag: ['@flow:panel-platform-feature-flags', '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Bug caught: retrying a failed client lookup could drop the current fragment or leave the list unavailable.
    let unavailable = true
    const requests = []
    await setup(page, {
      clientResponse: ({ route }) => {
        const url = new URL(route.request().url())
        const request = { page: Number(url.searchParams.get('page')), search: url.searchParams.get('search') }
        requests.push(request)
        if (request.search === 'Diego' && unavailable) return json({ detail: 'Temporalmente no disponible.' }, 503)
        if (request.search === 'Diego') return json({ results: [{ user_id: 88, name: 'Diego Recuperado', tour_enabled: true, video_enabled: false }], page: 1, count: 1 })
        return json({ results: [], page: 1, count: 0 })
      },
    })

    await openClientSearch(page)
    const results = page.getByTestId('feature-client-results')
    await page.getByLabel('Buscar cliente por nombre, correo o empresa', { exact: true }).fill('Diego')
    await expect(results.getByRole('alert')).toHaveText('No se pudieron cargar los clientes. Reintentar')
    await expect.poll(() => requests.at(-1)).toEqual({ page: 1, search: 'Diego' })

    unavailable = false
    await results.getByRole('button', { name: 'Reintentar', exact: true }).click()

    await expectClient(page, 'Diego Recuperado')
    await expect.poll(() => requests.at(-1)).toEqual({ page: 1, search: 'Diego' })
  })

})
