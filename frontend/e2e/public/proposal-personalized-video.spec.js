/**
 * Public proposal personalized video.
 *
 * Catches regressions where a personalized video is not placed after the
 * greeting, a removed resource leaves an empty panel, or a playback failure
 * gives the visitor no retry path.
 */
import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { PUBLIC_PROPOSAL_PERSONALIZED_VIDEO } from '../helpers/flow-tags.js'
import { fileURLToPath } from 'node:url'

const UUID = '74111111-1111-4111-8111-111111111111'
const VIDEO_SRC = '/api/video-resources/74111111-1111-4111-8111-111111111111/1/video/'
const VIDEO_FIXTURE = fileURLToPath(new URL('../../assets/videos/customSoftware/infinityBlubs.mp4', import.meta.url))

function section(id, section_type, title, order, content_json = {}) {
  return { id, section_type, title, order, is_enabled: true, content_json }
}

function proposal(personalized_video) {
  return {
    id: 741, uuid: UUID, title: 'Propuesta con video', client_name: 'Cliente público', client_email: 'public@example.com',
    language: 'es', status: 'sent', total_investment: '10000000', currency: 'COP', view_count: 1, expires_at: null,
    personalized_video,
    sections: [
      section(1, 'greeting', '👋 Bienvenido', 0, { clientName: 'Cliente público', inspirationalQuote: 'Una prueba verificable.' }),
      section(2, 'executive_summary', '🧾 Resumen', 1, { index: '1', title: 'Resumen', paragraphs: ['Una propuesta concreta.'], highlightsTitle: 'Incluye', highlights: ['Video'] }),
      section(3, 'functional_requirements', '🧩 Requerimientos', 2, { index: '2', title: 'Requerimientos', intro: '', groups: [], additionalModules: [] }),
      section(4, 'investment', '💰 Inversión', 3, { index: '3', title: 'Inversión', introText: '', totalInvestment: '10000000', currency: 'COP', whatsIncluded: [], paymentOptions: [], paymentMethods: [], valueReasons: [], modules: [] }),
      section(5, 'proposal_closing', '🤝 Cierre', 4, { index: '4', title: 'Cierre' }),
    ],
    requirement_groups: [],
  }
}

function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

async function setupProposalApi(page, personalized_video) {
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === `proposals/${UUID}/` && method === 'GET') return json(200, proposal(personalized_video))
    if (apiPath === `proposals/${UUID}/record-view/` || apiPath.includes('/track/')) return json(200, {})
    return null
  })
}

async function openProposalGateway(page, personalized_video, configureMedia = null) {
  await page.addInitScript(() => localStorage.setItem('proposal_onboarding_seen', 'true'))
  await setupProposalApi(page, personalized_video)
  if (configureMedia) await configureMedia()
  await page.goto(`/proposal/${UUID}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('button', { name: /Vista Ejecutiva/ })).toContainText('Vista Ejecutiva')
}

async function chooseExecutive(page, personalized_video, configureMedia = null) {
  await openProposalGateway(page, personalized_video, configureMedia)
  await page.getByRole('button', { name: /Vista Ejecutiva/ }).click()
  await expect(page.getByTestId('section-counter')).toContainText('/')
}

test.describe('Public proposal personalized video', () => {
  test.setTimeout(60_000)

  test('keeps the personalized video after the greeting in executive and complete views', {
    tag: [...PUBLIC_PROPOSAL_PERSONALIZED_VIDEO, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the shared proposal URL is the documented guest entry point)
    await chooseExecutive(page, { src: VIDEO_SRC, poster: null })

    const greeting = page.locator('[data-section-type="greeting"]')
    const videoPanel = page.getByTestId('proposal-personalized-video')
    await expect(greeting).toContainText('Cliente público')
    await page.getByTestId('nav-next').click()
    await expect(videoPanel.getByLabel('Video personalizado de la propuesta')).toHaveAttribute('src', VIDEO_SRC)

    await page.getByTestId('index-toggle').click()
    await page.getByTestId('switch-to-detailed-btn').click()

    await expect(page.getByTestId('proposal-personalized-video').getByRole('heading', { name: 'Tu propuesta en video' })).toHaveText('Tu propuesta en video')
    await expect(page.getByTestId('proposal-personalized-video').getByLabel('Video personalizado de la propuesta')).toHaveAttribute('src', VIDEO_SRC)
  })

  test('omits the video panel after a resource has been removed', {
    tag: [...PUBLIC_PROPOSAL_PERSONALIZED_VIDEO, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await chooseExecutive(page, null)

    await page.getByTestId('index-toggle').click()
    await page.getByTestId('switch-to-detailed-btn').click()

    await expect(page.locator('[data-section-type="greeting"]')).toContainText('Cliente público')
    await expect(page.getByTestId('proposal-personalized-video')).toHaveCount(0)
  })

  test('offers and completes a playback retry after the browser reports a media error', {
    tag: [...PUBLIC_PROPOSAL_PERSONALIZED_VIDEO, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    let videoRequests = 0
    await chooseExecutive(page, { src: VIDEO_SRC, poster: null }, async () => {
      await page.route(`**${VIDEO_SRC}`, async (route) => {
        videoRequests += 1
        if (videoRequests === 1) return route.abort('failed')
        return route.fulfill({ path: VIDEO_FIXTURE, contentType: 'video/mp4' })
      })
    })

    await page.getByTestId('nav-next').click()
    const player = page.getByTestId('proposal-personalized-video').getByLabel('Video personalizado de la propuesta')
    await expect(page.getByRole('alert')).toContainText('No se pudo cargar el video.')
    const recovered = player.evaluate((element) => new Promise((resolve) => {
      element.addEventListener('loadedmetadata', () => resolve(true), { once: true })
    }))

    await page.getByRole('button', { name: 'Reintentar', exact: true }).click()
    await recovered
    expect(videoRequests).toBeGreaterThanOrEqual(2)
    await expect(page.getByRole('alert')).toHaveCount(0)
    await expect(player).toHaveAttribute('src', VIDEO_SRC)
  })
})
