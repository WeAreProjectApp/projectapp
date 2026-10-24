import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import { ADMIN_PLATFORM_HELP_VIDEOS } from '../helpers/flow-tags.js'

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })
async function setup(page, scenario = {}) {
  await setAuthLocalStorage(page, { token: 'test-token', userAuth: { is_staff: true, is_superuser: true } })
  await mockApi(page, ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { is_staff: true, is_superuser: true } })
    if (apiPath === 'platform/help/settings/') return json({ version: 1, tour_enabled: true, video_enabled: true })
    if (apiPath === 'platform/help/admin/tours/') return json({ results: [], targets: {} })
    if (apiPath === 'platform/help/clients/' || apiPath === 'platform/help/admin/progress/') return json({ results: [], page: 1, count: 0 })
    const match = apiPath.match(/^video-resources\/admin\/modules\/(platform-[^/]+)\/es\/$/)
    if (!match) return null
    if (method === 'POST') return scenario.reject ? json({ detail: 'No se pudo validar el video.' }, 400) : json({ key: `${match[1]}:es`, module: match[1], language: 'es', revision: 1, mode: 'uploaded', filename: 'tutorial.mp4', video: { src: '/tutorial-replaced.mp4', durationSeconds: 45 } })
    return json({ key: `${match[1]}:es`, module: match[1], language: 'es', revision: 0, mode: 'default', video: null })
  })
  await page.goto('/es-co/panel/platform/help', { waitUntil: 'domcontentloaded' })
  return page.getByTestId('platform-video-resource-general')
}

test.describe('Platform tutorial administration', () => {
  test.setTimeout(60_000)
  test('lists the three managed tutorial pieces', { tag: [...ADMIN_PLATFORM_HELP_VIDEOS, '@outcome:display'] }, async ({ page }) => {
    const general = await setup(page)
    await expect(general.getByRole('heading', { name: 'Lo principal de tu plataforma' })).toBeVisible()
    await expect(page.getByTestId('platform-video-resource-chatbot')).toContainText('Appi')
    await general.getByRole('button', { name: 'Consultar recurso' }).click()
    await expect(general.getByRole('combobox')).toHaveValue('es')
  })

  test('replaces a tutorial from the shared panel', { tag: [...ADMIN_PLATFORM_HELP_VIDEOS, '@outcome:success'] }, async ({ page }) => {
    const general = await setup(page)
    await general.locator('input[type="file"]').setInputFiles({ name: 'tutorial.mp4', mimeType: 'video/mp4', buffer: Buffer.from('mock-upload') })
    await general.getByRole('button', { name: 'Sustituir video' }).click()
    await expect(general.locator('video')).toHaveAttribute('src', '/tutorial-replaced.mp4')
  })

  test('rejects an incompatible file before upload', { tag: [...ADMIN_PLATFORM_HELP_VIDEOS, '@outcome:error'] }, async ({ page }) => {
    const general = await setup(page)
    await general.locator('input[type="file"]').setInputFiles({ name: 'tutorial.txt', mimeType: 'text/plain', buffer: Buffer.from('invalid') })
    await general.getByRole('button', { name: 'Sustituir video' }).click()
    await expect(general.getByText('Selecciona un archivo MP4.', { exact: true })).toBeVisible()
  })

  test('preserves the current preview after a rejected replacement', { tag: [...ADMIN_PLATFORM_HELP_VIDEOS, '@outcome:failure'] }, async ({ page }) => {
    const general = await setup(page, { reject: true })
    const original = await general.locator('video').getAttribute('src')
    await general.locator('input[type="file"]').setInputFiles({ name: 'tutorial.mp4', mimeType: 'video/mp4', buffer: Buffer.from('mock-upload') })
    await general.getByRole('button', { name: 'Sustituir video' }).click()
    await expect(general.getByText('No se pudo validar el video.', { exact: true })).toBeVisible()
    await expect(general.locator('video')).toHaveAttribute('src', original)
  })
})
