/**
 * Internal platform-help administration.
 *
 * These catch inaccessible administration, lost flag writes, stale-version
 * errors being hidden, and an editor that stops exposing draft evidence.
 */
import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import {
  ADMIN_PLATFORM_GUIDED_TOUR_AUTHORING,
  ADMIN_PLATFORM_HELP_SETTINGS,
} from '../helpers/flow-tags.js'

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })

const targets = {
  projects: { context: 'general', route: '/platform/projects' },
  welcome: { context: 'general' },
  'project-summary': { context: 'project', route: '/platform/projects/{project_id}' },
}

const authoredTour = {
  id: 811,
  slug: 'platform-basics',
  context: 'general',
  kind: 'onboarding',
  priority: 10,
  is_active: true,
  version: 7,
  published_revision: 2,
  content: {
    title_es: 'Conoce tu espacio',
    title_en: 'Know your space',
    steps: [{ target: 'projects', title_es: 'Tus proyectos', title_en: 'Your projects', description_es: 'Aquí ves el avance.', description_en: 'Track progress here.' }],
  },
}

function helpFixture({ settings = { tour_enabled: true, video_enabled: true, version: 3 }, tours = [authoredTour], clients = [], progress = [] } = {}) {
  return { settings: { ...settings }, tours: tours.map((tour) => structuredClone(tour)), clients, progress }
}

async function setupAdmin(page, { fixture = helpFixture(), settingsStatus = 200, tourStatus = 200 } = {}) {
  const writes = []
  await setAuthLocalStorage(page, { token: 'platform-help-admin', userAuth: { id: 51, role: 'admin', is_staff: true, is_superuser: true } })
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'help-admin', is_staff: true, is_superuser: true } })
    if (apiPath === 'platform/help/settings/' && method === 'GET') return json(fixture.settings)
    if (apiPath === 'platform/help/admin/tours/' && method === 'GET') return json({ results: fixture.tours, targets })
    if (apiPath === 'platform/help/clients/' && method === 'GET') return json({ results: fixture.clients, page: 1, count: fixture.clients.length })
    if (apiPath === 'platform/help/admin/progress/' && method === 'GET') return json({ results: fixture.progress, page: 1, count: fixture.progress.length })
    if (apiPath === 'platform/help/settings/' && method === 'PATCH') {
      const body = JSON.parse(route.request().postData() || '{}')
      writes.push({ type: 'settings', body })
      if (settingsStatus >= 400) return json({ detail: 'La configuración fue modificada por otra persona.' }, settingsStatus)
      fixture.settings = { ...fixture.settings, ...body, version: fixture.settings.version + 1 }
      return json(fixture.settings)
    }
    if (apiPath === `platform/help/admin/tours/${authoredTour.id}/` && method === 'PATCH') {
      const body = JSON.parse(route.request().postData() || '{}')
      writes.push({ type: 'tour', body })
      if (tourStatus >= 400) return json({ detail: 'El borrador ya no coincide.' }, tourStatus)
      fixture.tours = fixture.tours.map((tour) => tour.id === authoredTour.id ? { ...tour, ...body, version: tour.version + 1 } : tour)
      return json(fixture.tours.find((tour) => tour.id === authoredTour.id))
    }
    if (apiPath === `platform/help/admin/tours/${authoredTour.id}/preview/` && method === 'GET') return json({ ...authoredTour, preview: true })
    if (apiPath === `platform/help/admin/tours/${authoredTour.id}/revisions/` && method === 'GET') {
      return json({ results: [{ number: 2, content: authoredTour.content }] })
    }
    return null
  })
  return writes
}

async function openPlatformHelp(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' })
  const link = page.getByRole('link', { name: 'Ayuda de la plataforma', exact: true })
  await expect(link).toHaveText('Ayuda de la plataforma')
  await link.click()
  await expect(page).toHaveURL(/\/panel\/platform\/help$/)
  await expect(page.getByTestId('platform-help-admin').getByRole('heading', { name: 'Ayuda de la plataforma' })).toHaveText('Ayuda de la plataforma')
}

test.describe('Platform help administration', () => {
  test.setTimeout(60_000)

  test('panel navigation displays configured help data', {
    tag: [...ADMIN_PLATFORM_HELP_SETTINGS, ...ADMIN_PLATFORM_GUIDED_TOUR_AUTHORING, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the authenticated panel home is the entry point; this test clicks its visible Plataforma navigation)
    // Bug caught: the panel link no longer reaches the help editor or loses returned tour data.
    await setupAdmin(page, { fixture: helpFixture({ progress: [{ user_id: 9002, user: 'client@e2e-test.com', tour: 'platform-basics', status: 'completed' }] }) })

    await openPlatformHelp(page)
    await expect(page.getByLabel('Seleccionar recorrido')).toHaveValue(String(authoredTour.id))
    await expect(page.getByTestId('platform-help-admin')).toContainText('client@e2e-test.com')
  })

  test('saving global availability sends the current version', {
    tag: [...ADMIN_PLATFORM_HELP_SETTINGS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: turning off tours does not persist the global setting with its version.
    const writes = await setupAdmin(page)

    await openPlatformHelp(page)
    const toggle = page.getByRole('switch', { name: 'Recorridos habilitados', exact: true })
    await expect(toggle).toHaveAttribute('aria-checked', 'true')
    await toggle.click()
    await page.getByRole('heading', { name: 'Disponibilidad global', exact: true })
      .locator('xpath=..').getByRole('button', { name: 'Guardar', exact: true }).click()

    await expect(page.getByRole('status')).toHaveText('Cambios guardados.')
    await expect.poll(() => writes.find((item) => item.type === 'settings')?.body).toMatchObject({ expected_version: 3, tour_enabled: false, video_enabled: true })
  })

  test('a stale global availability write reports the save failure', {
    tag: [...ADMIN_PLATFORM_HELP_SETTINGS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Bug caught: a version conflict is acknowledged as saved even though the setting was rejected.
    await setupAdmin(page, { settingsStatus: 409 })

    await openPlatformHelp(page)
    await page.getByRole('switch', { name: 'Recorridos habilitados', exact: true }).click()
    await page.getByRole('heading', { name: 'Disponibilidad global', exact: true })
      .locator('xpath=..').getByRole('button', { name: 'Guardar', exact: true }).click()

    await expect(page.getByRole('alert')).toHaveText('No se pudo guardar. Actualiza los datos e inténtalo de nuevo.')
  })

  test('previewing a tour shows the saved draft in the active locale', {
    tag: [...ADMIN_PLATFORM_GUIDED_TOUR_AUTHORING, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: preview stops rendering the draft that an administrator is about to publish.
    await setupAdmin(page)

    await openPlatformHelp(page)
    await page.getByRole('button', { name: 'Vista previa', exact: true }).click()
    const preview = page.getByTestId('tour-admin-preview')
    await expect(preview).toContainText('Tus proyectos')
    await expect(preview).toContainText('Aquí ves el avance.')
  })

  test('a rejected tour draft save keeps the error visible', {
    tag: [...ADMIN_PLATFORM_GUIDED_TOUR_AUTHORING, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Bug caught: an invalid or stale tour draft fails without informing its editor.
    await setupAdmin(page, { tourStatus: 400 })

    await openPlatformHelp(page)
    const priority = page.getByLabel('Prioridad', { exact: true })
    await priority.fill('25')
    await priority.locator('xpath=ancestor::form').getByRole('button', { name: 'Guardar', exact: true }).click()

    await expect(page.getByRole('alert')).toHaveText('No se pudo guardar. Actualiza los datos e inténtalo de nuevo.')
  })
})
