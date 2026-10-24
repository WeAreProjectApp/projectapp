// qa: draft-unvalidated (2026-10-24 — app not running)
/**
 * Platform help journeys.
 *
 * These catch a dismissed guide returning after reload, contextual onboarding
 * being skipped, or a help-service outage taking the client out of a project.
 */
import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setPlatformAuth, mockPlatformClient } from '../helpers/platform-auth.js'
import {
  PLATFORM_GUIDED_TOUR_GENERAL,
  PLATFORM_GUIDED_TOUR_PROJECT,
  PLATFORM_GUIDED_TOUR_VOICE,
} from '../helpers/flow-tags.js'

const project = {
  id: 71,
  name: 'Portal de soporte',
  description: 'Proyecto visible para el recorrido contextual.',
  status: 'active',
  status_label: 'Activo',
  progress: 62,
  client_id: mockPlatformClient.id,
  client_name: 'Client E2E',
  client_email: mockPlatformClient.email,
  client_company: mockPlatformClient.company_name,
  current_state: { id: 1, name: 'Activo', system_key: 'active', operational_effect: 'operating', color: 'emerald' },
}

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })

function tour({ id, slug, context, status = '', target, title, steps }) {
  return {
    id,
    slug,
    context,
    kind: 'onboarding',
    revision: 1,
    status,
    last_step: '',
    content: {
      title_es: title,
      title_en: title,
      steps: steps || [{
        target,
        title_es: title,
        title_en: title,
        description_es: `Explicación de ${title}.`,
        description_en: `Explanation for ${title}.`,
      }],
    },
  }
}

async function setupClient(page, { globalTours = [], projectTours = [], helpStatus = 200, progressStatus = 200 } = {}) {
  const progress = []
  const terminal = new Set(['completed', 'skipped'])
  const persisted = new Map(
    [...globalTours, ...projectTours]
      .filter((item) => item.status)
      .map((item) => [item.id, { status: item.status, last_step: item.last_step }]),
  )
  const catalog = (tours) => tours.map((item) => {
    const state = persisted.get(item.id)
    return state ? { ...item, ...state } : { ...item }
  })
  await setPlatformAuth(page, { user: mockPlatformClient })
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(mockPlatformClient)
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([project])
    if (apiPath === `accounts/projects/${project.id}/` && method === 'GET') return json(project)
    if (apiPath === `accounts/projects/${project.id}/phases/` && method === 'GET') return json([])
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') return json({ unread_count: 0 })
    if (apiPath === 'platform/help/' && method === 'GET') {
      if (helpStatus >= 400) return json({ detail: 'Ayuda no disponible.' }, helpStatus)
      const hasProject = new URL(route.request().url()).searchParams.has('project_id')
      return json({ tour_enabled: true, video_enabled: false, tours: catalog(hasProject ? projectTours : globalTours) })
    }
    const progressMatch = apiPath.match(/^platform\/help\/tours\/(\d+)\/progress\/$/)
    if (progressMatch && method === 'POST') {
      const id = Number(progressMatch[1])
      const body = JSON.parse(route.request().postData() || '{}')
      progress.push({ id, body })
      if (progressStatus >= 400) return json({ status: 'rejected' }, progressStatus)
      const current = persisted.get(id)
      if (!terminal.has(current?.status)) persisted.set(id, { status: body.status, last_step: body.last_step || '' })
      return json({ status: persisted.get(id)?.status || body.status })
    }
    return null
  })
  return progress
}

const latestProgress = (progress, id) => progress.filter((item) => item.id === id).at(-1)

async function openProjects(page) {
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Mis proyectos' })).toHaveText('Mis proyectos')
}

async function openOwnedProject(page) {
  await openProjects(page)
  await page.getByTestId(`project-row-${project.id}`).click()
  await expect(page).toHaveURL(new RegExp(`/platform/projects/${project.id}$`))
  await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveText(project.name)
}

test.describe('Platform guided tour', () => {
  test.setTimeout(60_000)

  test('skipping the general guide keeps it dismissed until Help replays it', {
    tag: [...PLATFORM_GUIDED_TOUR_GENERAL, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: a skipped tour returns after reload or cannot be manually replayed.
    const general = tour({ id: 401, slug: 'general', context: 'general', target: 'welcome', title: 'Conoce tu plataforma' })
    const progress = await setupClient(page, { globalTours: [general] })

    await openProjects(page)
    const popover = page.getByTestId('platform-tour-popover')
    await expect(popover).toContainText('Conoce tu plataforma')
    await page.getByTestId('platform-tour-skip').click()

    await expect.poll(() => latestProgress(progress, general.id)?.body.status).toBe('skipped')
    await expect(latestProgress(progress, general.id)?.body).toMatchObject({ revision: 1, manual: false, last_step: 'welcome' })

    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('platform-help-trigger')).toBeVisible()
    await expect(popover).toHaveCount(0)

    await page.getByTestId('platform-help-trigger').click()
    await page.getByTestId('platform-help-tour-general').click()
    await expect(popover).toContainText('Conoce tu plataforma')
  })

  test('a rejected skip keeps the general guide hidden after reload', {
    tag: [...PLATFORM_GUIDED_TOUR_GENERAL, '@role:platform-client', '@outcome:failure'],
  }, async ({ page }) => {
    // Bug caught: a transient progress failure reopens a guide the user already dismissed.
    const general = tour({ id: 402, slug: 'general', context: 'general', target: 'welcome', title: 'Inicio sin conexión' })
    const progress = await setupClient(page, { globalTours: [general], progressStatus: 500 })

    await openProjects(page)
    await page.getByTestId('platform-tour-skip').click()
    await expect.poll(() => latestProgress(progress, general.id)?.body.status).toBe('skipped')

    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('platform-help-trigger')).toBeVisible()
    await expect(page.getByTestId('platform-tour-popover')).toHaveCount(0)
  })

  test('completing the general guide stays hidden after reload', {
    tag: [...PLATFORM_GUIDED_TOUR_GENERAL, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the authenticated project list is the client entry point; the tour itself advances through visible controls)
    // Bug caught: a completed multi-step guide is saved as in-progress and restarts after the next sign-in.
    const general = tour({
      id: 408,
      slug: 'general',
      context: 'general',
      title: 'Bienvenida',
      steps: [
        { target: 'welcome', title_es: 'Bienvenida', title_en: 'Welcome', description_es: 'Conoce tu espacio.', description_en: 'Get to know your space.' },
        { target: 'projects', title_es: 'Proyectos', title_en: 'Projects', description_es: 'Aquí está tu trabajo.', description_en: 'Your work is here.' },
        { target: 'help', title_es: 'Ayuda', title_en: 'Help', description_es: 'Repite el recorrido aquí.', description_en: 'Replay the tour here.' },
      ],
    })
    const progress = await setupClient(page, { globalTours: [general] })

    await openProjects(page)
    const popover = page.getByTestId('platform-tour-popover')
    await expect(popover).toContainText('Bienvenida')
    await page.getByTestId('platform-tour-next').click()
    await expect(popover).toContainText('Proyectos')
    await page.getByTestId('platform-tour-next').click()
    await expect(popover).toContainText('Ayuda')
    await page.getByTestId('platform-tour-next').click()

    await expect.poll(() => latestProgress(progress, general.id)?.body.status).toBe('completed')
    await expect(latestProgress(progress, general.id)?.body).toMatchObject({ revision: 1, manual: false, last_step: 'help' })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('platform-help-trigger')).toBeVisible()
    await expect(popover).toHaveCount(0)
  })

  test('an unseen project guide starts after the completed general guide', {
    tag: [...PLATFORM_GUIDED_TOUR_PROJECT, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: entering an owned project omits its eligible contextual guide.
    const general = tour({ id: 403, slug: 'general', context: 'general', status: 'completed', target: 'welcome', title: 'General finalizado' })
    const contextual = tour({ id: 404, slug: 'project-overview', context: 'project', target: 'project-summary', title: 'Resumen del proyecto' })
    await setupClient(page, { globalTours: [general], projectTours: [contextual] })

    await openOwnedProject(page)
    await expect(page.getByTestId('platform-tour-popover')).toContainText('Resumen del proyecto')
  })

  test('a help catalog outage leaves the owned project usable', {
    tag: [...PLATFORM_GUIDED_TOUR_PROJECT, '@role:platform-client', '@outcome:failure'],
  }, async ({ page }) => {
    // Bug caught: an unavailable help catalog prevents a client from opening their project.
    await setupClient(page, { helpStatus: 503 })

    await openOwnedProject(page)
    await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveText(project.name)
    await expect(page.getByTestId('platform-tour-popover')).toHaveCount(0)
  })

  test('Help hides the voice guide while the project has no voice control', {
    tag: [...PLATFORM_GUIDED_TOUR_VOICE, '@role:platform-client', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the authenticated project list is the client entry point; this display flow reaches the owned project by clicking its row)
    // Bug caught: Help offers a voice walkthrough for a control the client cannot use.
    const general = tour({ id: 405, slug: 'general', context: 'general', status: 'completed', target: 'welcome', title: 'General completado' })
    const completedProject = tour({ id: 406, slug: 'project-overview', context: 'project', status: 'completed', target: 'project-summary', title: 'Resumen completado' })
    const voice = tour({ id: 407, slug: 'voice-report', context: 'voice', target: 'voice-report', title: 'Reporta por voz' })
    await setupClient(page, { globalTours: [general], projectTours: [completedProject, voice] })

    await openOwnedProject(page)
    await page.getByTestId('platform-help-trigger').click()

    await expect(page.getByTestId('platform-help-menu')).toContainText('Resumen completado')
    await expect(page.getByTestId('platform-help-tour-voice-report')).toHaveCount(0)
  })
})
