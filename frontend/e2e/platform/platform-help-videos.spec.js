import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { mockPlatformClient, setPlatformAuth } from '../helpers/platform-auth.js'
import { PLATFORM_HELP_VIDEOS } from '../helpers/flow-tags.js'
import { PANEL_VIEWPORTS } from '../helpers/viewports.js'

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })
const general = { topic: 'general', module: 'platform-overview', language: 'es', resource: { mode: 'default', video: null } }
const chatbot = { topic: 'chatbot', module: 'platform-chatbot', language: 'es', resource: { mode: 'default', video: null } }

async function setup(page, scenario = {}) {
  await setPlatformAuth(page, { user: mockPlatformClient })
  await mockApi(page, ({ apiPath }) => {
    if (apiPath === 'accounts/me/') return json(mockPlatformClient)
    if (apiPath === 'accounts/projects/') return json([])
    if (apiPath === 'platform/help/') return json({ tour_enabled: false, video_enabled: true, tours: [] })
    if (apiPath === 'platform/help/videos/') return json({ enabled: true, videos: scenario.videos || [general, chatbot] })
    return null
  })
}

async function openHelpVideo(page) {
  if (page.viewportSize().width < 768) await page.getByRole('button', { name: 'Abrir navegación' }).click()
  await page.getByTestId('platform-help-trigger').filter({ visible: true }).click()
  await page.getByTestId('platform-help-menu').getByRole('button', { name: /Ver video|Watch video/ }).click()
  await expect(page.getByTestId('platform-help-video-player')).toBeVisible()
}

test.describe('Platform help videos', () => {
  test.setTimeout(60_000)
  test('opens an available topic from Help', { tag: [...PLATFORM_HELP_VIDEOS, '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (the localized project list is the authenticated landing; Help -> Watch video -> topic is navigated through visible controls)
    await setup(page)
    await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
    await openHelpVideo(page)
    await expect(page.getByTestId('platform-video-topic-chatbot')).toContainText('Appi')
    await page.getByTestId('platform-video-topic-chatbot').click()
    await expect(page.getByTestId('platform-help-video-player')).toHaveAttribute('aria-label', 'Consultar y orientarte con Appi')
    await expect(page.getByText('Video en español · con subtítulos')).toBeVisible()
  })

  test('keeps playback paused until the user requests it', { tag: [...PLATFORM_HELP_VIDEOS, '@outcome:success'] }, async ({ page }) => {
    await setup(page, { videos: [general] })
    await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
    await openHelpVideo(page)
    const player = page.getByTestId('platform-help-video-player')
    await expect.poll(() => player.evaluate((element) => element.paused)).toBe(true)
    await player.focus()
    await player.press('Space')
    await expect.poll(() => player.evaluate((element) => element.paused)).toBe(false)
    await page.getByTestId('platform-video-close').click()
    await expect(player).toHaveCount(0)
    await expect(page.getByTestId('platform-help-trigger').filter({ visible: true })).toBeFocused()
  })

  test('offers recovery after a media request fails', { tag: [...PLATFORM_HELP_VIDEOS, '@outcome:failure'] }, async ({ page }) => {
    await setup(page, { videos: [{ ...general, resource: { mode: 'uploaded', video: { src: '/tutorial-unavailable.mp4', durationSeconds: 90 } } }] })
    await page.route('**/tutorial-unavailable.mp4', (route) => route.fulfill({ status: 404, body: '' }))
    await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
    await openHelpVideo(page)
    await page.getByTestId('platform-help-video-player').focus()
    await page.getByTestId('platform-help-video-player').press('Space')
    await expect(page.getByRole('alert')).toContainText('No pudimos reproducir')
    await page.getByRole('button', { name: 'Volver a intentar' }).click()
    await expect(page.getByRole('alert')).toHaveCount(0)
  })

  test('identifies Spanish content in the English interface', { tag: [...PLATFORM_HELP_VIDEOS, '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (the localized project list is the authenticated landing; the English Help menu opens the video through its visible action)
    await setup(page, { videos: [general] })
    await page.goto('/en-us/platform/projects', { waitUntil: 'domcontentloaded' })
    await openHelpVideo(page)
    await expect(page.getByText('Video in Spanish · with Spanish captions')).toBeVisible()
  })
})

for (const [profile, viewport] of Object.entries(PANEL_VIEWPORTS)) {
  test.describe(`Tutorial modal ${profile}`, () => {
    test.use({ viewport })
    test('keeps the player within the dialog', { tag: [...PLATFORM_HELP_VIDEOS, '@outcome:success'] }, async ({ page }) => {
      await setup(page, { videos: [general] })
      await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
      await openHelpVideo(page)
      const box = await page.getByTestId('platform-help-video-player').boundingBox()
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(viewport.width)
      await page.getByTestId('platform-video-close').click()
      await expect(page.getByTestId('platform-help-video-player')).toHaveCount(0)
    })
  })
}
