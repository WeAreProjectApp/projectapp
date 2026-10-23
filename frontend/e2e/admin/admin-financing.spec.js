import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import { financingProgramFixture } from '../helpers/financing-fixture.js'
import { financingSettingsFixture } from '../helpers/financing-agreement-fixture.js'
import {
  ADMIN_FINANCING_DISTRIBUTION,
  ADMIN_FINANCING_EXPLAINER,
  ADMIN_FINANCING_EXPLAINER_VISIBILITY,
} from '../helpers/flow-tags.js'
import { PANEL_BREAKPOINTS } from '../../config/responsive.js'


function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

async function setupApi(page, scenario = {}) {
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return scenario.unauthorized
      ? json(401, { detail: 'Authentication required' })
      : json(200, { user: { username: 'admin', is_staff: true } })
    if (apiPath === 'proposals/' && method === 'GET') return json(200, [])
    if (apiPath === 'proposals/dashboard/') return json(200, { total: 0, by_status: {} })
    if (apiPath === 'proposals/alerts/') return json(200, [])
    if (apiPath === 'financing/settings/' && method === 'GET') {
      return json(200, financingSettingsFixture())
    }
    if (apiPath === 'explainer-videos/admin/settings/' && method === 'GET') {
      return json(200, { show_additional_modules_video: true, show_financing_video: true })
    }
    if (apiPath === 'explainer-videos/admin/settings/update/' && method === 'PATCH') {
      scenario.videoPatch = route.request().postDataJSON()
      if (scenario.videoSaveFails) return json(500, { detail: 'Unavailable' })
      return json(200, { show_additional_modules_video: true, ...scenario.videoPatch })
    }
    if (apiPath === 'financing/agreements/' && method === 'GET') {
      return json(200, {
        count: 0,
        limit: 25,
        offset: 0,
        results: [],
        stats: { total_active_records: 0, archived: 0, by_status: {} },
      })
    }
    if (apiPath === 'financing/public/pdf/' && method === 'GET') {
      scenario.pdfLanguage = new URL(route.request().url()).searchParams.get('lang') || 'es'
      return {
        status: 200,
        contentType: 'application/pdf',
        headers: { 'Content-Disposition': 'attachment; filename="programa-de-alianza.pdf"' },
        body: '%PDF-1.4 financing',
      }
    }
    if (apiPath === 'financing/public/' && method === 'GET') {
      if (scenario.programUnavailable) return json(503, { detail: 'Unavailable' })
      const language = new URL(route.request().url()).searchParams.get('lang') || 'es'
      return json(200, financingProgramFixture(language, {
        catalogSynced: scenario.catalogSynced,
      }))
    }
    return null
  })
}

async function openFinancing(page) {
  await page.goto('/es-co/panel/partnership-program', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('financing-public-url')).toBeVisible({ timeout: 30_000 })
}

test.describe('Admin financing distribution', () => {
  test.setTimeout(60_000)

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin',
      userAuth: { id: 1, role: 'admin', is_staff: true },
    })
  })

  test('navigates from Comercial to the financing preview', {
    tag: [...ADMIN_FINANCING_DISTRIBUTION, '@role:admin', '@outcome:display', '@responsive:commercial'],
  }, async ({ page }) => {
    await setupApi(page)
    // quality: allow-deep-link (the authenticated proposals list is the Comercial entry point; this test then reaches financing through the visible sidebar)
    await page.goto('/es-co/panel/proposals', { waitUntil: 'domcontentloaded' })
    if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
      await page.getByRole('button', { name: 'Abrir menú' }).click()
    }
    const link = page.getByRole('link', { name: 'Programa de Alianza', exact: true })

    await link.click()

    await expect(page).toHaveURL(/\/es-co\/panel\/partnership-program$/)
    await expect(page.getByRole('heading', { name: 'Programa de Alianza', exact: true })).toBeVisible()
    await expect(page.getByTestId('financing-public-url'))
      .toHaveValue('https://projectapp.co/es-co/partnership-program')
    await expect(page.getByTestId('financing-option-five-year')).toContainText('Alianza a 5 años')
  })

  test('preserves tab selection when following a legacy panel link', {
    tag: ['@flow:admin-partnership-legacy-redirects', '@outcome:success', '@role:admin'],
  }, async ({ page }) => {
    await setupApi(page)
    // quality: allow-deep-link (the behavior under test starts with a saved legacy link)
    // quality: allow-no-interaction (navigation invokes this compatibility behavior)
    await page.goto('/es-co/panel/financing?tab=agreements#history', { waitUntil: 'domcontentloaded' })

    await expect(page).toHaveURL(/\/es-co\/panel\/partnership-program\?tab=agreements#history$/)
    await expect(page.getByTestId('financing-new-agreement')).toBeVisible()
  })

  test('requires staff authentication at the redirected panel destination', {
    tag: ['@flow:admin-partnership-legacy-redirects', '@outcome:error', '@role:guest'],
  }, async ({ page }) => {
    await setupApi(page, { unauthorized: true })
    await page.route('**/admin/login/**', (route) => route.fulfill({ contentType: 'text/html', body: '<main>Admin login</main>' }))
    // quality: allow-deep-link (an unauthenticated visitor follows a legacy bookmark)
    // quality: allow-no-interaction (the route guard itself is the behavior under test)
    await page.goto('/en-us/panel/financing/new', { waitUntil: 'domcontentloaded' })

    await expect(page).toHaveURL(/\/admin\/login\/\?next=/)
    expect(new URL(page.url()).searchParams.get('next')).toBe('/en-us/panel/partnership-program/new')
  })

  test('copies the canonical public financing URL', {
    tag: [...ADMIN_FINANCING_DISTRIBUTION, '@role:admin', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await setupApi(page)
    // quality: allow-deep-link (sidebar navigation is covered separately; this isolates clipboard distribution)
    await openFinancing(page)

    await page.getByTestId('financing-copy-public-url').click()

    expect(await page.evaluate(() => navigator.clipboard.readText()))
      .toBe('https://projectapp.co/es-co/partnership-program')
    await expect(page.getByRole('alert')).toContainText('URL pública copiada')
  })

  test('downloads the public booklet from the distribution card', {
    tag: [...ADMIN_FINANCING_DISTRIBUTION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    // quality: allow-deep-link (sidebar navigation is covered separately; this isolates the PDF shortcut)
    await openFinancing(page)
    await expect(page.getByTestId('financing-public-url'))
      .toHaveValue('https://projectapp.co/es-co/partnership-program')

    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('financing-panel-download-pdf').click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toBe('programa-de-alianza.pdf')
    expect(scenario.pdfLanguage).toBe('es')
  })

  test('keeps requirement allowances after changing language', {
    tag: [...ADMIN_FINANCING_DISTRIBUTION, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Bug caught: changing locale replaces the fixed monthly requirement allowance.
    // quality: allow-deep-link (sidebar navigation is covered separately; this isolates the localized allowance display)
    await setupApi(page)
    await openFinancing(page)

    await expect(page.getByRole('heading', { name: '4 XS · 2 S · 1 M' })).toBeVisible()

    await page.getByTestId('financing-language-en').click()

    await expect(page).toHaveURL(/\/en-us\/panel\/partnership-program$/)
    await expect(page.getByRole('heading', { name: '4 XS · 2 S · 1 M' })).toBeVisible()
    await expect(page.getByTestId('financing-package-facts')).toContainText('Requirements do not roll over')
  })

  test('retries after the financing program request fails', {
    tag: [...ADMIN_FINANCING_DISTRIBUTION, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-deep-link (isolates the panel's API failure and retry states)
    const scenario = { programUnavailable: true }
    await setupApi(page, scenario)
    await page.goto('/es-co/panel/partnership-program', { waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('alert')).toContainText('No pudimos cargar el Programa de Alianza')
    scenario.programUnavailable = false

    await page.getByRole('button', { name: 'Reintentar' }).click()

    await expect(page.getByTestId('financing-public-url')).toBeVisible()
  })
  test('previews the financing explainer once from the Programa tab', {
    tag: [...ADMIN_FINANCING_EXPLAINER, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page)
    await openFinancing(page)
    await expect(page.getByTestId('financing-program')).toBeVisible()
    const card = page.getByTestId('financing-explainer-card')
    await expect(card).toContainText('Video explicativo del programa')
    await expect(page.getByTestId('financing-program').getByTestId('financing-explainer-card')).toHaveCount(0)

    await page.getByTestId('financing-explainer-play').click()

    await expect(page.getByTestId('financing-explainer-player')).toBeVisible()
  })

  test('hides the Partnership Program video for clients from the panel switch', {
    tag: [...ADMIN_FINANCING_EXPLAINER_VISIBILITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    // quality: allow-deep-link (sidebar navigation is covered in beforeEach; this isolates the video switch)
    await openFinancing(page)
    const toggle = page.getByTestId('financing-explainer-visibility-toggle')
    await expect(toggle).toHaveAttribute('aria-checked', 'true')

    await toggle.click()

    await expect(toggle).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByRole('alert')).toContainText('El video quedó oculto en la vista pública del Programa de Alianza.')
    expect(scenario.videoPatch).toEqual({ show_financing_video: false })
  })

  test('reverts the video switch when the save fails', {
    tag: [...ADMIN_FINANCING_EXPLAINER_VISIBILITY, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const scenario = { videoSaveFails: true }
    await setupApi(page, scenario)
    // quality: allow-deep-link (sidebar navigation is covered in beforeEach; this isolates the failed save)
    await openFinancing(page)
    const toggle = page.getByTestId('financing-explainer-visibility-toggle')
    await expect(toggle).toHaveAttribute('aria-checked', 'true')

    await toggle.click()

    await expect(page.getByRole('alert')).toContainText('No pudimos guardar la visibilidad del video.')
    await expect(toggle).toHaveAttribute('aria-checked', 'true')
  })
})
