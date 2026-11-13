import { test, expect } from './helpers/test.js'
import { mockApi } from './helpers/api.js'
import { setPlatformAuth, mockPlatformClient } from './helpers/platform-auth.js'
import catalog from '../../contracts/platform-features.json' with { type: 'json' };

const json = (data, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(data) })

async function setup(page, { failure = false, disabled = 'platform.documents' } = {}) {
  await setPlatformAuth(page, { user: mockPlatformClient })
  await mockApi(page, ({ apiPath }) => {
    if (apiPath === 'accounts/me/') return json(mockPlatformClient)
    if (apiPath === 'platform/features/') return json({ user_id: mockPlatformClient.user_id,
      features: { ...Object.fromEntries(catalog.features.map(item => [item.key, item.default_enabled])), [disabled]: false } }, failure ? 503 : 200)
    if (apiPath === 'accounts/projects/') return json([])
    if (apiPath === 'platform/help/') return json({ tours: [], tour_enabled: true, video_enabled: true })
    if (apiPath === 'platform/ai/capabilities/') return json({ chatbot: { enabled: false, available: false }, voice_reporting: { enabled: false, available: false } })
    if (apiPath === 'accounts/notifications/unread-count/') return json({ count: 0 })
    return null
  })
}

test.describe('Client feature availability', () => {
  test.setTimeout(60_000)

  test('navigation omits the disabled document portal', { tag: ['@flow:platform-feature-availability', '@outcome:display'] }, async ({ page }) => {
    // quality: allow-deep-link (Projects is the client entry point; the test uses the navigation to reach profile.)
    await setup(page)
    await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })

    await expect(page.getByRole('link', { name: 'Documentos', exact: true })).toHaveCount(0)
    await page.getByRole('link', { name: 'Configuración', exact: true }).first().click()
    await expect(page).toHaveURL(/\/platform\/profile$/)
  })

  for (const { key, path, label } of [
    { key: 'platform.documents', path: '/es-co/platform/documents', label: 'documents' },
    { key: 'platform.requirement_packages', path: '/es-co/platform/projects/1/packages', label: 'packages' },
  ]) {
    test(`direct entry cannot open disabled ${label}`, { tag: ['@flow:platform-feature-availability', '@outcome:error'] }, async ({ page }) => {
      await setup(page, { disabled: key })
      await page.goto(path, { waitUntil: 'domcontentloaded' })

      await expect(page.getByTestId('platform-feature-unavailable')).toContainText('Esta funcionalidad está deshabilitada')
      await expect(page).toHaveURL(/\/platform\/unavailable$/)
      await page.getByRole('link', { name: 'Volver a Proyectos', exact: true }).click()
      await expect(page).toHaveURL(/\/platform\/projects$/)
    })
  }

  test('blocked client returns to the project structure', { tag: ['@flow:platform-feature-availability', '@outcome:success'] }, async ({ page }) => {
    await setup(page)
    await page.goto('/es-co/platform/documents', { waitUntil: 'domcontentloaded' })

    await page.getByRole('link', { name: 'Volver a Proyectos', exact: true }).click()

    await expect(page).toHaveURL(/\/platform\/projects$/)
    await expect(page.getByTestId('platform-feature-unavailable')).toHaveCount(0)
  })

  test('evaluation failure does not enable the requested feature', { tag: ['@flow:platform-feature-availability', '@outcome:failure'] }, async ({ page }) => {
    await setup(page, { failure: true })
    await page.goto('/es-co/platform/documents', { waitUntil: 'domcontentloaded' })

    await expect(page.getByTestId('platform-feature-unavailable')).toContainText('No se pudo comprobar la disponibilidad')
    await page.getByRole('link', { name: 'Volver a Proyectos', exact: true }).click()
    await expect(page).toHaveURL(/\/platform\/projects$/)
  })
})
