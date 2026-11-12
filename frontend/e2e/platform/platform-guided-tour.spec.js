/**
 * Platform help journeys.
 *
 * These catch a dismissed guide returning after reload, contextual onboarding
 * being skipped, or a help-service outage taking the client out of a project.
 */
import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setPlatformAuth, mockPlatformClient } from '../helpers/platform-auth.js'
import { waitForNuxtApp } from '../helpers/navigation.js'
import { textContrast } from '../helpers/text-contrast.js'
import { viewportUse, VIEWPORTS } from '../helpers/viewports.js'
import {
  PLATFORM_GUIDED_TOUR_GENERAL,
  PLATFORM_GUIDED_TOUR_PROJECT,
  PLATFORM_GUIDED_TOUR_VOICE,
} from '../helpers/flow-tags.js'

// UserProfileSerializer exposes user_id; an invented id alias hides PA-219.
const platformClient = { ...mockPlatformClient }
delete platformClient.id

const project = {
  id: 71,
  name: 'Portal de soporte',
  description: 'Proyecto visible para el recorrido contextual.',
  status: 'active',
  status_label: 'Activo',
  progress: 62,
  client_id: platformClient.user_id,
  client_name: 'Client E2E',
  client_email: mockPlatformClient.email,
  client_company: mockPlatformClient.company_name,
  current_state: { id: 1, name: 'Activo', system_key: 'active', operational_effect: 'operating', color: 'emerald' },
}

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })

function tour({ id, slug, context, status = '', lastStep = '', kind = 'onboarding', target, title, steps }) {
  return {
    id,
    slug,
    context,
    kind,
    revision: 1,
    status,
    last_step: lastStep,
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

async function setupClient(page, {
  globalTours = [], projectTours = [], helpStatus = 200, progressStatus = 200, prohibitedRequests = [], voiceAvailable = true,
} = {}) {
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
  await setPlatformAuth(page, { user: platformClient })
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(platformClient)
    if (apiPath === 'accounts/documents/' && method === 'GET') return json({ documents: [], email: platformClient.email, email_verified: true })
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([project])
    if (apiPath === `accounts/projects/${project.id}/` && method === 'GET') return json(project)
    if (apiPath === `accounts/projects/${project.id}/phases/` && method === 'GET') return json([])
    if (apiPath === `accounts/projects/${project.id}/bug-reports/` && method === 'GET') return json([])
    if (apiPath === `accounts/projects/${project.id}/issue-reports/context-options/` && method === 'GET') return json({ requirements: [] })
    if (apiPath === 'accounts/notifications/unread-count/' && method === 'GET') return json({ unread_count: 0 })
    if (apiPath === 'platform/ai/capabilities/' && method === 'GET') {
      return json({
        chatbot: { enabled: false, available: false, voice_available: false },
        voice_reporting: { enabled: voiceAvailable, available: voiceAvailable },
        quota: { limit: 20, used: 0, remaining: 20, window_minutes: 300, next_available_at: null },
      })
    }
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
    if (method === 'POST' && [
      'platform/ai/transcriptions/',
      `platform/ai/projects/${project.id}/report-drafts/`,
      `accounts/projects/${project.id}/bug-reports/`,
    ].includes(apiPath)) prohibitedRequests.push(apiPath)
    return null
  })
  return progress
}

const latestProgress = (progress, id) => progress.filter((item) => item.id === id).at(-1)

async function openProjects(page) {
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  await expect(page.getByRole('heading', { name: 'Mis proyectos' })).toHaveText('Mis proyectos')
}

async function openOwnedProject(page) {
  await openProjects(page)
  await page.getByTestId(`project-row-${project.id}`)
    .or(page.getByTestId(`project-card-${project.id}`)).filter({ visible: true }).click()
  await expect(page).toHaveURL(new RegExp(`/platform/projects/${project.id}$`))
  await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveText(project.name)
}

async function openBugFormFromProject(page) {
  await openOwnedProject(page)
  await page.getByRole('link', { name: 'Bugs', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Reporte de bugs', exact: true })).toHaveText('Reporte de bugs')
  await page.getByRole('button', { name: 'Reportar bug', exact: true }).click()
}

async function openMobileNavigation(page) {
  const navigation = page.getByRole('button', { name: 'Abrir navegación', exact: true })
  if (await navigation.isVisible()) await navigation.click()
}

async function openHelp(page) {
  await openMobileNavigation(page)
  await page.getByTestId('platform-help-trigger').filter({ visible: true }).click()
}

async function openProjectsFromDocuments(page) {
  await page.goto('/es-co/platform/documents', { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  await expect(page.getByRole('heading', { name: 'Mis documentos', exact: true })).toHaveText('Mis documentos')
  await openMobileNavigation(page)
  await page.getByRole('link', { name: 'Proyectos', exact: true }).filter({ visible: true }).click()
  await expect(page.getByRole('heading', { name: 'Mis proyectos', exact: true })).toHaveText('Mis proyectos')
}

async function openOwnedProjectFromDocuments(page) {
  await openProjectsFromDocuments(page)
  await page.getByTestId(`project-row-${project.id}`)
    .or(page.getByTestId(`project-card-${project.id}`)).filter({ visible: true }).click()
  await expect(page).toHaveURL(new RegExp(`/platform/projects/${project.id}$`))
  await expect(page.getByRole('heading', { name: project.name, exact: true })).toHaveText(project.name)
}

async function waitForTourLayout(page) {
  await page.evaluate(async () => {
    const nextFrame = () => new Promise((resolve) => window.requestAnimationFrame(resolve))
    // Let responsive styles, Vue and the tour's resize handler reach the browser.
    await nextFrame()
    await nextFrame()
    const animations = document.getAnimations().filter((animation) => {
      const target = animation.effect?.target
      return target instanceof Element && target.closest('main, aside, [data-testid="platform-tour-popover"]')
        && animation.playState === 'running'
        && Number.isFinite(animation.effect.getComputedTiming().endTime)
    })
    // Await layout and card animations before inspecting or advancing the tour.
    await Promise.allSettled(animations.map((animation) => animation.finished))
    await nextFrame()
    await nextFrame()
  })
}

async function expectHighlightedTarget(page, key) {
  await waitForTourLayout(page)
  const target = page.locator(`[data-tour="${key}"]`).filter({ visible: true })
  await expect(target).toBeInViewport()
  // Check the rendered cutout, not Driver's cached element or its CSS marker.
  await expect.poll(() => target.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    const svg = document.querySelector('svg.driver-overlay')
    const path = svg?.querySelector('path')
    const popover = document.querySelector('[data-testid="platform-tour-popover"]')
    if (!path || !popover || !svg.getScreenCTM()) return null
    const center = new DOMPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
    const point = center.matrixTransform(svg.getScreenCTM().inverse())
    const card = popover.getBoundingClientRect()
    const horizontalGap = Math.max(0, rect.left - card.right, card.left - rect.right)
    const verticalGap = Math.max(0, rect.top - card.bottom, card.top - rect.bottom)
    return {
      targetHasArea: rect.width > 0 && rect.height > 0,
      cutoutContainsTargetCenter: !path.isPointInFill(point),
      cardIsAdjacentToTarget: horizontalGap <= 32 && verticalGap <= 32,
    }
  })).toEqual({ targetHasArea: true, cutoutContainsTargetCenter: true, cardIsAdjacentToTarget: true })
}

function completedProjectGuide() {
  return tour({ id: 418, slug: 'project-overview', context: 'project', status: 'completed', target: 'project-summary', title: 'Resumen del proyecto' })
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

  test('Help resumes a paused guide at its saved step', {
    tag: [...PLATFORM_GUIDED_TOUR_GENERAL, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: a saved pause restarts at the beginning or loses the manual acknowledgement.
    const general = tour({
      id: 412, slug: 'general', context: 'general', status: 'paused', lastStep: 'help', title: 'Guía pausada',
      steps: [
        { target: 'welcome', title_es: 'Bienvenida', title_en: 'Welcome', description_es: 'Inicio de la guía.', description_en: 'Start of the guide.' },
        { target: 'help', title_es: 'Continúa aquí', title_en: 'Continue here', description_es: 'Este es tu último paso.', description_en: 'This is your saved step.' },
      ],
    })
    const progress = await setupClient(page, { globalTours: [general] })

    await openProjects(page)
    await page.getByTestId('platform-help-trigger').click()
    await page.getByTestId('platform-help-tour-general').click()

    await expect(page.getByTestId('platform-tour-popover')).toContainText('Este es tu último paso.')
    await page.getByTestId('platform-tour-next').click()
    await expect.poll(() => latestProgress(progress, general.id)?.body.status).toBe('completed')
    expect(latestProgress(progress, general.id)?.body).toMatchObject({ manual: true, last_step: 'help' })
  })

  test('an independent novelty keeps completed onboarding dismissed', {
    tag: [...PLATFORM_GUIDED_TOUR_GENERAL, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: a new published identity is suppressed by the general guide's terminal progress.
    const general = tour({ id: 413, slug: 'general', context: 'general', status: 'completed', target: 'welcome', title: 'Guía general completada' })
    const novelty = tour({ id: 414, slug: 'new-client-dashboard', kind: 'novelty', context: 'general', target: 'help', title: 'Novedad independiente' })
    const progress = await setupClient(page, { globalTours: [general, novelty] })

    await openProjects(page)
    await expect(page.getByTestId('platform-tour-popover')).toContainText('Novedad independiente')
    await page.getByTestId('platform-tour-next').click()
    await expect.poll(() => latestProgress(progress, novelty.id)?.body.status).toBe('completed')
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.getByTestId('platform-help-trigger').click()

    await expect(page.getByTestId('platform-help-tour-general')).toHaveText('Guía general completada')
    await expect(page.getByTestId('platform-help-tour-new-client-dashboard')).toHaveText('Novedad independiente')
    await expect(page.getByTestId('platform-tour-popover')).toHaveCount(0)
    expect(progress.filter((item) => item.id === general.id)).toEqual([])
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

  test('the voice guide explains the real bug-report control without starting a report', {
    tag: [...PLATFORM_GUIDED_TOUR_VOICE, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: voice onboarding is omitted from the real bug form, or it starts recording and sends AI requests by itself.
    const general = tour({ id: 409, slug: 'general', context: 'general', status: 'completed', target: 'welcome', title: 'General completado' })
    const voice = tour({
      id: 410,
      slug: 'voice-report',
      context: 'voice',
      target: 'voice-report',
      title: 'Describe un bug por voz',
      steps: [{
        target: 'voice-report',
        title_es: 'Describe un bug por voz',
        title_en: 'Describe a bug by voice',
        description_es: 'Graba una nota y revísala antes de usarla en el formulario.',
        description_en: 'Record a note and review it before using it in the form.',
      }],
    })
    const prohibitedRequests = []
    await setupClient(page, { globalTours: [general], projectTours: [voice], prohibitedRequests })

    await openBugFormFromProject(page)

    const voiceInput = page.getByTestId('voice-report-input')
    await expect(voiceInput.getByRole('button', { name: 'Describir con una nota de voz', exact: true })).toHaveText('Describir con una nota de voz')
    await expect(page.getByTestId('platform-tour-popover')).toContainText('Graba una nota y revísala antes de usarla en el formulario.')
    await expect(voiceInput.getByRole('button', { name: 'Grabar o volver a grabar', exact: true })).toHaveCount(0)
    await expect(voiceInput.getByLabel('Escuchar grabación', { exact: true })).toHaveCount(0)
    expect(prohibitedRequests).toEqual([])
  })

  test('unavailable AI controls are omitted from client guidance', {
    tag: [...PLATFORM_GUIDED_TOUR_GENERAL, ...PLATFORM_GUIDED_TOUR_VOICE, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: a general card highlights disabled Appi or voice guidance opens without its form control.
    const general = tour({
      id: 415, slug: 'general', context: 'general', title: 'Guía sin IA',
      steps: [
        { target: 'welcome', title_es: 'Inicio sin IA', title_en: 'Start without AI', description_es: 'Conoce tu plataforma.', description_en: 'Discover your platform.' },
        { target: 'platform-appi-launcher', title_es: 'Appi no disponible', title_en: 'Unavailable Appi', description_es: 'Este paso se omite.', description_en: 'This step is omitted.' },
        { target: 'help', title_es: 'Ayuda sin IA', title_en: 'Help without AI', description_es: 'Repite la guía aquí.', description_en: 'Repeat the guide here.' },
      ],
    })
    const voice = tour({ id: 416, slug: 'voice-report', context: 'voice', target: 'voice-report', title: 'Voz no disponible' })
    await setupClient(page, { globalTours: [general], projectTours: [general, voice], voiceAvailable: false })

    await openProjects(page)
    await expect(page.getByTestId('platform-tour-popover')).toContainText('Inicio sin IA')
    await page.getByTestId('platform-tour-next').click()
    await expect(page.getByTestId('platform-tour-popover')).toContainText('Ayuda sin IA')
    await page.getByTestId('platform-tour-next').click()
    await openBugFormFromProject(page)
    await expect(page.getByRole('heading', { name: 'Reportar bug', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Describir con una nota de voz', exact: true })).toHaveCount(0)
    await expect(page.getByTestId('platform-tour-popover')).toHaveCount(0)
    await page.getByRole('button', { name: 'Cancelar', exact: true }).click()
    await page.getByTestId('platform-help-trigger').click()

    await expect(page.getByTestId('platform-help-tour-voice-report')).toHaveCount(0)
    await expect(page.getByTestId('appi-launcher')).toHaveCount(0)
  })
})

test.describe('Platform guided tour on compact screens', () => {
  test.use(viewportUse('compact'))
  test.setTimeout(60_000)

  test('restores the compact navigation drawer after the guided tour', {
    tag: [...PLATFORM_GUIDED_TOUR_GENERAL, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: a compact guided tour leaves navigation closed while it highlights links, or leaves the drawer covering the platform after completion.
    const general = tour({
      id: 411,
      slug: 'general',
      context: 'general',
      title: 'Guía móvil',
      steps: [
        { target: 'welcome', title_es: 'Guía móvil', title_en: 'Mobile guide', description_es: 'Empieza aquí.', description_en: 'Start here.' },
        { target: 'projects', title_es: 'Proyectos', title_en: 'Projects', description_es: 'Tus proyectos están en la navegación.', description_en: 'Your projects are in navigation.' },
        { target: 'help', title_es: 'Ayuda', title_en: 'Help', description_es: 'Repite la guía desde Ayuda.', description_en: 'Replay the guide from Help.' },
      ],
    })
    const progress = await setupClient(page, { globalTours: [general] })

    await openProjects(page)
    await expect(page.getByTestId('platform-tour-popover')).toContainText('Guía móvil')
    await expect(page.getByRole('button', { name: 'Cerrar navegación', exact: true })).toHaveCount(0)

    await page.getByTestId('platform-tour-next').click()
    const drawerClose = page.getByRole('button', { name: 'Cerrar navegación', exact: true })
    await expect(drawerClose).toHaveAttribute('aria-label', 'Cerrar navegación')
    await expect(page.getByRole('link', { name: 'Proyectos', exact: true })).toHaveText('Proyectos')

    await page.getByTestId('platform-tour-next').click()
    await page.getByTestId('platform-tour-next').click()

    await expect.poll(() => latestProgress(progress, general.id)?.body.status).toBe('completed')
    await expect(latestProgress(progress, general.id)?.body).toMatchObject({ last_step: 'help', manual: false })
    await expect(drawerClose).toHaveCount(0)
  })

  test('Help replays a completed guide on compact screens', {
    tag: [...PLATFORM_GUIDED_TOUR_GENERAL, '@role:platform-client', '@outcome:success'],
  }, async ({ page }) => {
    // Bug caught: the mobile Help entry disappears after a completed guide or cannot start a manual replay.
    const general = tour({ id: 417, slug: 'general', context: 'general', status: 'completed', target: 'welcome', title: 'Repetir guía móvil' })
    const progress = await setupClient(page, { globalTours: [general] })

    await openProjects(page)
    await page.getByRole('button', { name: 'Abrir navegación', exact: true }).click()
    await page.getByTestId('platform-help-trigger').filter({ visible: true }).click()
    await page.getByTestId('platform-help-tour-general').click()
    await expect(page.getByTestId('platform-tour-popover')).toContainText('Repetir guía móvil')
    await page.getByTestId('platform-tour-skip').click()

    await expect.poll(() => latestProgress(progress, general.id)?.body.manual).toBe(true)
    await expect(page.getByRole('button', { name: 'Cerrar navegación', exact: true })).toBeVisible()
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('heading', { name: 'Mis proyectos', exact: true })).toBeVisible()
    await expect(page.getByTestId('platform-tour-popover')).toHaveCount(0)
  })

})

test.describe('Platform guided tour responsive anchors', () => {
  test.setTimeout(60_000)

  test.describe('project guide opened from the compact drawer', () => {
    test.use(viewportUse('compact'))

    test('Help exposes the highlighted project control outside the drawer', {
      tag: [...PLATFORM_GUIDED_TOUR_PROJECT, '@role:platform-client', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (Documentos is the authenticated client landing; Projects, the project, Bugs, drawer and Help are reached through UI clicks)
      // Bug caught: the project cutout illuminates Hosting in the drawer over the real Summary.
      await setupClient(page, { projectTours: [completedProjectGuide()] })
      await openOwnedProjectFromDocuments(page)
      await page.getByRole('link', { name: 'Bugs', exact: true }).click()
      await expect(page).toHaveURL(new RegExp(`/platform/projects/${project.id}/bugs$`))

      await openHelp(page)
      await page.getByTestId('platform-help-tour-project-overview').filter({ visible: true }).click()

      await expect(page.getByTestId('platform-tour-popover')).toContainText('Resumen del proyecto')
      await expect(page.getByRole('button', { name: 'Cerrar navegación', exact: true })).toHaveCount(0)
      await expectHighlightedTarget(page, 'project-summary')
      await page.reload({ waitUntil: 'domcontentloaded' })
      await expect(page.getByRole('heading', { name: 'Reporte de bugs', exact: true })).toBeVisible()
      await expect(page.getByTestId('platform-tour-popover')).toHaveCount(0)
    })
  })

  for (const { from, to } of [
    { from: 'desktop', to: 'compact' },
    { from: 'wide', to: 'compact' },
    { from: 'compact', to: 'portrait' },
    { from: 'compact', to: 'landscape' },
    { from: 'compact', to: 'wide' },
  ]) {
    test.describe(`project guide resize ${from} to ${to}`, () => {
      test.use(viewportUse(from))

      test('the open project highlight follows its control across the breakpoint', {
        tag: [...PLATFORM_GUIDED_TOUR_PROJECT, '@role:platform-client', '@outcome:display'],
      }, async ({ page }) => {
        // quality: allow-deep-link (Documentos is the authenticated client landing; Projects, project, Bugs and Help navigation are exercised before resizing)
        // Bug caught: a breakpoint moves Summary while the cutout stays at its old coordinates.
        await setupClient(page, { projectTours: [completedProjectGuide()] })
        await openOwnedProjectFromDocuments(page)
        await page.getByRole('link', { name: 'Bugs', exact: true }).click()
        await expect(page).toHaveURL(new RegExp(`/platform/projects/${project.id}/bugs$`))
        await openHelp(page)
        await page.getByTestId('platform-help-tour-project-overview').filter({ visible: true }).click()
        await expectHighlightedTarget(page, 'project-summary')

        await page.setViewportSize(VIEWPORTS[to])

        await expect(page.getByTestId('platform-tour-popover')).toContainText('Resumen del proyecto')
        await expect(page.getByRole('button', { name: 'Cerrar navegación', exact: true })).toHaveCount(0)
        await expectHighlightedTarget(page, 'project-summary')
        await page.reload({ waitUntil: 'domcontentloaded' })
        await expect(page.getByRole('heading', { name: 'Reporte de bugs', exact: true })).toBeVisible()
        await expect(page.getByTestId('platform-tour-popover')).toHaveCount(0)
      })
    })
  }

  test.describe('general guide across the mobile breakpoint', () => {
    test.use(viewportUse('desktop'))

    test('the open navigation highlight moves to the visible menu', {
      tag: [...PLATFORM_GUIDED_TOUR_GENERAL, '@role:platform-client', '@outcome:display'],
    }, async ({ page }) => {
      // quality: allow-deep-link (Documentos is the authenticated setup landing; Projects, Help, guide selection and Next are reached through UI clicks)
      // Bug caught: resizing keeps Driver attached to a hidden zero-size desktop navigation link.
      const general = tour({ id: 419, slug: 'general', context: 'general', status: 'completed', title: 'Guía general adaptable', steps: [
        { target: 'welcome', title_es: 'Bienvenida', title_en: 'Welcome', description_es: 'Inicio.', description_en: 'Start.' },
        { target: 'projects', title_es: 'Tus proyectos', title_en: 'Your projects', description_es: 'Consulta tus proyectos.', description_en: 'Check your projects.' },
        { target: 'documents', title_es: 'Tus documentos', title_en: 'Your documents', description_es: 'Consulta tus documentos.', description_en: 'Check your documents.' },
      ] })
      await setupClient(page, { globalTours: [general] })
      await openProjectsFromDocuments(page)
      await openHelp(page)
      await page.getByTestId('platform-help-tour-general').click()
      await page.getByTestId('platform-tour-next').click()
      await expectHighlightedTarget(page, 'projects')

      await page.setViewportSize(VIEWPORTS.compact)

      await expect(page.getByRole('button', { name: 'Cerrar navegación', exact: true })).toBeVisible()
      await expectHighlightedTarget(page, 'projects')
      await page.getByTestId('platform-tour-next').click()
      await expect(page.getByTestId('platform-tour-popover')).toContainText('Tus documentos')
      await expectHighlightedTarget(page, 'documents')
      await page.setViewportSize(VIEWPORTS.portrait)
      await expect(page.getByRole('button', { name: 'Cerrar navegación', exact: true })).toHaveCount(0)
      await expectHighlightedTarget(page, 'documents')
    })
  })
})


for (const viewport of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
  for (const theme of ['dark', 'light']) {
    test.describe(`Skip contrast ${viewport} ${theme} (PA-250)`, () => {
      test.use({ ...viewportUse(viewport), colorScheme: theme })

      test.beforeEach(async ({ page }) => {
        await page.addInitScript((value) => localStorage.setItem('platform_theme', value), theme)
      })

      for (const [context, enter, pageTitle] of [
        ['general', openProjects, 'Mis proyectos'],
        ['project', openOwnedProject, project.name],
      ]) {
        test(`keeps the initial ${context} skip readable before a manual replay`, {
          tag: [...(context === 'general' ? PLATFORM_GUIDED_TOUR_GENERAL : PLATFORM_GUIDED_TOUR_PROJECT), '@role:platform-client', '@outcome:display'],
        }, async ({ page }) => {
          const general = tour({ id: 450, slug: 'general', context: 'general', status: context === 'project' ? 'completed' : '', target: 'welcome', title: 'Bienvenido a tu plataforma' })
          const contextual = tour({ id: 451, slug: 'project-overview', context: 'project', target: 'project-summary', title: 'Resumen' })
          const progress = await setupClient(page, { globalTours: [general], projectTours: [contextual] })
          const current = context === 'general' ? general : contextual
          await enter(page)
          const popover = page.getByTestId('platform-tour-popover')
          const skip = page.getByTestId('platform-tour-skip')
          await expect(popover).toHaveAttribute('data-theme', theme)
          await expect(skip).toBeFocused()
          expect(await textContrast(skip)).toBeGreaterThanOrEqual(4.5)

          await popover.getByText(current.content.title_es, { exact: true }).click()
          expect(await textContrast(skip)).toBeGreaterThanOrEqual(4.5)
          await skip.hover()
          expect(await textContrast(skip)).toBeGreaterThanOrEqual(4.5)
          await page.mouse.down()
          expect(await textContrast(skip)).toBeGreaterThanOrEqual(4.5)
          await page.mouse.up()

          await expect(popover).toHaveCount(0)
          await expect.poll(() => latestProgress(progress, current.id)?.body.status).toBe('skipped')
          await page.reload({ waitUntil: 'domcontentloaded' })
          await waitForNuxtApp(page)
          await expect(page.getByRole('heading', { name: pageTitle, exact: true })).toBeVisible()
          await expect(popover).toHaveCount(0)
          await openHelp(page)
          await page.getByTestId(`platform-help-tour-${current.slug}`).click()
          await expect(popover).toContainText(current.content.title_es)
          expect(await textContrast(skip)).toBeGreaterThanOrEqual(4.5)
          await skip.click()
          await expect.poll(() => latestProgress(progress, current.id)?.body.manual).toBe(true)
        })
      }
    })
  }
}
