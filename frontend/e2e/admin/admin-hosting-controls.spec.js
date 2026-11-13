import { ADMIN_HOSTING_CONTROLS } from '../helpers/flow-tags.js'
import { test, expect, assertResponsiveScenario } from '../helpers/test.js'
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from '../responsive/catalog-scenarios.js'
import { viewportUse } from '../helpers/viewports.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'

test.setTimeout(60_000)
const initial = () => ({ id: 1, name: 'Sitio de prueba', client: 'Cliente ficticio', server: 'VPS de prueba', environment: 'production', version: 0, mode: 'normal', suspension_title: 'Servicio suspendido', suspension_text: 'Gestiona la reactivación con tu proveedor.', banner_title: 'Pago pendiente del servicio', banner_text: 'Contacta a tu proveedor.', targets: [{ key: 'fixture', origins: ['https://fixture.example'], state: 'unintegrated', lifecycle: 'active' }] })

async function setup(page, { failure = false, conflict = false, throughProjects = false } = {}) {
  const state = initial()
  await setAuthLocalStorage(page, { token: 'fixture', userAuth: { id: 1, is_staff: true, is_superuser: true, role: 'admin' } })
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true, is_superuser: true } }) }
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

test('switching mode replaces the previous selection', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:success'] }, async ({ page }) => {
  await setup(page)
  await page.getByTestId('hosting-switch-suspended').click()
  await expect(page.getByTestId('hosting-switch-suspended')).toHaveAttribute('aria-checked', 'true')
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-switch-suspended')).toHaveAttribute('aria-checked', 'false')
  await expect(page.getByTestId('hosting-switch-banner')).toHaveAttribute('aria-checked', 'true')
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-configured-mode')).toContainText('Funcionamiento normal')
})

test('editing the banner leaves suspension text intact', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:success'] }, async ({ page }) => {
  const state = await setup(page)
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-configured-mode')).toContainText('Banner de aviso')
  await page.getByTestId('hosting-title-banner').fill('Aviso actualizado de prueba')
  await page.getByTestId('hosting-save-banner').click()
  await expect.poll(() => state.banner_title).toBe('Aviso actualizado de prueba')
  expect(state.suspension_text).toBe('Gestiona la reactivación con tu proveedor.')
  expect(state.mode).toBe('banner')
})

test('a stale message keeps the operator draft', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:error'] }, async ({ page }) => {
  await setup(page, { conflict: true })
  await page.getByTestId('hosting-title-banner').fill('Borrador que conservar')
  await page.getByTestId('hosting-save-banner').click()
  await expect(page.getByTestId('hosting-error')).toContainText('Otra edición')
  await expect(page.getByTestId('hosting-title-banner')).toHaveValue('Borrador que conservar')
})

test('a failed mode change retains its configured state', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:failure'] }, async ({ page }) => {
  await setup(page, { failure: true })
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-error')).toContainText('Fallo de prueba')
  await expect(page.getByTestId('hosting-switch-banner')).toHaveAttribute('aria-checked', 'false')
})

test('production receipt is shown separately from configured mode', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:display'] }, async ({ page }) => {
  await setup(page, { throughProjects: true })
  await page.getByTestId('hosting-switch-banner').click()
  await expect(page.getByTestId('hosting-status-fixture')).toContainText('Pendiente de aplicación')
  await expect(page.getByText('https://fixture.example', { exact: true })).toBeVisible()
})

test('phone layout retains both message editors', { tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:success'] }, async ({ page }) => {
  await page.setViewportSize({ width: 412, height: 915 })
  await setup(page)
  await page.getByTestId('hosting-text-banner').fill('Mensaje móvil de prueba.')
  await page.getByTestId('hosting-save-banner').click()
  await expect(page.getByTestId('hosting-text-banner')).toHaveValue('Mensaje móvil de prueba.')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

const scenario = getResponsiveScenario('frontend/pages/panel/projects/hosting.vue')
for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`hosting control ${profile}`, () => {
    test.use(viewportUse(profile))
    test('message editing remains usable at this width', {
      tag: [...ADMIN_HOSTING_CONTROLS, '@outcome:success', '@responsive:projects', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setup(page)
      await page.getByTestId('hosting-title-banner').fill('Aviso de prueba responsivo')
      await page.getByTestId('hosting-save-banner').click()
      await expect(page.getByTestId('hosting-title-banner')).toHaveValue('Aviso de prueba responsivo')
      await assertResponsiveScenario(page, testInfo, scenario, { profile })
    })
  })
}
