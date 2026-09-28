import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import {
  PUBLIC_ADDITIONAL_MODULES_CATALOG,
  PUBLIC_ADDITIONAL_MODULES_DETAIL,
  PUBLIC_ADDITIONAL_MODULES_EXPLAINER,
  PUBLIC_ADDITIONAL_MODULES_GUIDE,
  PUBLIC_ADDITIONAL_MODULES_PDF,
  PUBLIC_ADDITIONAL_MODULES_SHARE,
  PUBLIC_ADDITIONAL_MODULES_THEME,
} from '../helpers/flow-tags.js'

const shareUuid = '11111111-1111-4111-8111-111111111111'
const invoicing = {
  slug: 'electronic-invoicing', icon: '🧾', name: 'Facturación electrónica',
  summary: 'Emite documentos fiscales desde la plataforma.',
  what_is: 'Una integración con un proveedor autorizado.',
  purpose: 'Automatizar la emisión fiscal.',
  problems_solved: ['Evita la digitación doble'], integrations: ['Proveedor autorizado'],
  implementation_requirements: ['Credenciales fiscales'],
}
const landing = {
  slug: 'landing-page', icon: '◫', name: 'Landing page',
  summary: 'Crea un punto de llegada medible.', what_is: 'Una página pública enfocada.',
  purpose: 'Convertir visitas.', problems_solved: ['Falta de punto de entrada'],
  integrations: ['Analítica'], implementation_requirements: ['Contenido de marca'],
}
const fullCatalog = {
  language: 'es', total_modules: 2, is_shared: false,
  canonical_path: '/es-co/additional-modules',
  categories: [
    { slug: 'commerce', name: 'Comercio', modules: [invoicing] },
    { slug: 'marketing', name: 'Marketing', modules: [landing] },
  ],
}
const selectedCatalog = {
  ...fullCatalog,
  total_modules: 1,
  is_shared: true,
  share_uuid: shareUuid,
  categories: [{ slug: 'commerce', name: 'Comercio', modules: [invoicing] }],
}

function localizedCatalog(source, language) {
  if (language !== 'en') return source
  const moduleCopy = {
    'electronic-invoicing': {
      name: 'Electronic invoicing',
      summary: 'Issue tax documents from the platform.',
      what_is: 'An integration with an authorized provider.',
      purpose: 'Automate tax document issuance.',
      problems_solved: ['Avoids duplicate data entry'],
      integrations: ['Authorized provider'],
      implementation_requirements: ['Tax credentials'],
    },
    'landing-page': {
      name: 'Landing page',
      summary: 'Create a measurable destination.',
      what_is: 'A focused public page.',
      purpose: 'Convert visits.',
      problems_solved: ['Missing entry point'],
      integrations: ['Analytics'],
      implementation_requirements: ['Brand content'],
    },
  }
  return {
    ...source,
    language: 'en',
    canonical_path: '/en-us/additional-modules',
    categories: source.categories.map((category) => ({
      ...category,
      name: category.slug === 'commerce' ? 'Commerce' : 'Marketing',
      modules: category.modules.map((module) => ({
        ...module,
        ...moduleCopy[module.slug],
      })),
    })),
  }
}

function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

async function setupPublicApi(page, scenario = {}) {
  let catalogCalls = 0
  await page.addInitScript((showGuide) => {
    if (showGuide) {
      window.localStorage.removeItem('projectapp-additional-modules-guide-seen')
      return
    }
    window.localStorage.setItem('projectapp-additional-modules-guide-seen', 'true')
  }, Boolean(scenario.showGuide))
  await mockApi(page, async ({ apiPath, method, route }) => {
    const requestUrl = new URL(route.request().url())
    const requestedLanguage = requestUrl.searchParams.get('lang') || 'es'
    if (apiPath === 'additional-modules/public/' && method === 'GET') {
      catalogCalls += 1
      if (scenario.catalogUnavailable || catalogCalls <= (scenario.catalogFailures || 0)) {
        return json(503, { detail: 'Unavailable' })
      }
      return json(200, {
        ...localizedCatalog(fullCatalog, requestedLanguage),
        show_explainer_video: !scenario.videoHidden,
      })
    }
    if (apiPath === `additional-modules/public/shares/${shareUuid}/pdf/`) {
      scenario.pdfLanguage = requestedLanguage
      if (scenario.pdfFailure) return json(410, { detail: 'Este enlace fue retirado.' })
      const filename = requestedLanguage === 'en' ? 'selected-modules.pdf' : 'catalogo-seleccion.pdf'
      return { status: 200, contentType: 'application/pdf', headers: { 'Content-Disposition': `attachment; filename="${filename}"` }, body: '%PDF-1.4 selected' }
    }
    if (apiPath === 'additional-modules/public/pdf/') {
      scenario.pdfLanguage = requestedLanguage
      if (scenario.pdfFailure) return json(503, { detail: 'Unavailable' })
      const filename = requestedLanguage === 'en' ? 'additional-modules-catalog.pdf' : 'catalogo-modulos-adicionales.pdf'
      return { status: 200, contentType: 'application/pdf', headers: { 'Content-Disposition': `attachment; filename="${filename}"` }, body: '%PDF-1.4 full' }
    }
    if (apiPath === `additional-modules/public/shares/${shareUuid}/track/` && method === 'POST') {
      scenario.trackPayload = route.request().postDataJSON()
      return json(200, { status: 'recorded' })
    }
    if (apiPath === `additional-modules/public/shares/${shareUuid}/` && method === 'GET') {
      return scenario.shareGone
        ? json(410, { detail: 'Este enlace fue retirado.' })
        : json(200, {
          ...localizedCatalog(selectedCatalog, requestedLanguage),
          show_explainer_video: !scenario.videoHidden,
        })
    }
    return null
  })
}

async function openFromFooter(page) {
  await page.goto('/es-co', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('button', { name: 'Switch to English' })).toBeEnabled()
  const catalogLink = page.getByRole('link', { name: 'Módulos adicionales', exact: true })
  await catalogLink.scrollIntoViewIfNeeded()
  await catalogLink.click()
  await expect(page).toHaveURL(/\/es-co\/additional-modules$/)
  await expect(page.getByTestId('additional-module-card-electronic-invoicing')).toBeVisible()
}

test.describe('Public additional modules catalog', () => {
  test.setTimeout(60_000)

  test('reaches the indexed catalog from the footer and shows live data', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_CATALOG, '@role:guest', '@outcome:display', '@responsive:public'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)
    const heading = page.getByRole('heading', { name: 'Módulos adicionales' })
    await expect(heading).toBeVisible()
    const headingBox = await heading.boundingBox()
    expect(headingBox.y).toBeLessThan(150)
    await expect(page.getByTestId('additional-module-card-electronic-invoicing')).toContainText('Facturación electrónica')
    await expect(page.getByTestId('additional-module-card-landing-page')).toContainText('Landing page')
    await expect(page.locator('main')).not.toContainText(/COP|USD|\$/)
    await expect(page.locator('nav[aria-label="Main navigation"]')).toHaveCount(0)
    await expect(page.locator('nav[aria-label="Mobile navigation"]')).toHaveCount(0)
    await expect(page.getByTestId('additional-modules-share-floating')).toBeVisible()
    await expect(page.getByTestId('additional-modules-download-pdf-floating')).toBeVisible()
    await expect(page.getByTestId('additional-modules-guide-restart')).toBeVisible()
    await expect(page.getByTestId('additional-modules-theme-toggle')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Contact our web design team via WhatsApp' })).toBeVisible()
  })

  test('switches the public catalog to English', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_CATALOG, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)

    await page.getByTestId('additional-language-en').click()

    await expect(page).toHaveURL(/\/en-us\/additional-modules$/)
    await expect(page.getByRole('heading', { name: 'Additional modules' })).toBeVisible()
    await expect(page.getByTestId('additional-module-card-electronic-invoicing'))
      .toContainText('Electronic invoicing')
  })

  test('shows the compact module list', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_CATALOG, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)

    await page.getByTestId('additional-view-list').click()

    await expect(page.getByTestId('additional-module-list-electronic-invoicing')).toBeVisible()
    await expect(page.getByTestId('additional-module-card-electronic-invoicing')).toHaveCount(0)
  })

  test('restores the accordion preference after reload', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_CATALOG, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)
    await page.getByTestId('additional-view-accordion').click()

    await page.reload({ waitUntil: 'domcontentloaded' })

    await expect(page.getByTestId('additional-module-accordion-electronic-invoicing')).toBeVisible()
    await page.getByTestId('additional-module-accordion-trigger-electronic-invoicing').click()
    await expect(page.getByText('Credenciales fiscales')).toBeVisible()
  })

  test('keeps a retry path when the live catalog is unavailable', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_CATALOG, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-deep-link (isolates the canonical route's live-refresh failure state)
    const scenario = { catalogUnavailable: true }
    await setupPublicApi(page, scenario)
    await page.goto('/es-co/additional-modules', { waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('heading', { name: 'No pudimos cargar el catálogo.' })).toBeVisible()
    scenario.catalogUnavailable = false
    await page.getByRole('button', { name: 'Reintentar' }).click()
    await expect(page.getByTestId('additional-module-card-electronic-invoicing')).toBeVisible()
  })

  test('opens all detail blocks and restores focus to the card', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_DETAIL, '@role:guest', '@outcome:success', '@responsive:public'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)
    const card = page.getByTestId('additional-module-card-electronic-invoicing')
    await card.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toContainText('Qué es')
    await expect(dialog).toContainText('Para qué sirve')
    await expect(dialog).toContainText('Evita la digitación doble')
    await expect(dialog).toContainText('Proveedor autorizado')
    await expect(dialog).toContainText('Credenciales fiscales')
    await dialog.getByRole('button', { name: 'Cerrar' }).click()
    await expect(card).toBeFocused()
  })

  test('shows only the prepared selection and records one browser session', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_SHARE, '@role:guest', '@outcome:display', '@responsive:public'],
  }, async ({ page }) => {
    // quality: allow-deep-link (a prospect enters from the received message URL)
    // quality: allow-no-interaction (opening the received URL is the display outcome)
    const scenario = {}
    await setupPublicApi(page, scenario)
    await page.goto(`/es-co/additional-modules/share/${shareUuid}`, { waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('additional-module-card-electronic-invoicing')).toBeVisible()
    await expect(page.getByTestId('additional-module-card-landing-page')).toHaveCount(0)
    await expect(page.getByText('Esta selección fue preparada para esta conversación.')).toBeVisible()
    await expect.poll(() => scenario.trackPayload?.session_id).toMatch(/^[a-z0-9]{32}$/)
    await expect(page.locator('main')).not.toContainText('Acme')
    await expect(page.locator('main')).not.toContainText('aperturas')
    await expect(page.locator('nav[aria-label="Main navigation"]')).toHaveCount(0)
    await expect(page.locator('nav[aria-label="Mobile navigation"]')).toHaveCount(0)
  })

  test('allows a shared recipient to switch languages', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_SHARE, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await page.goto(`/es-co/additional-modules/share/${shareUuid}`, { waitUntil: 'domcontentloaded' })

    await page.getByTestId('additional-language-en').click()

    await expect(page).toHaveURL(new RegExp(`/en-us/additional-modules/share/${shareUuid}$`))
    await expect(page.getByTestId('additional-module-card-electronic-invoicing'))
      .toContainText('Electronic invoicing')
  })

  test('shows a final unavailable state for a revoked selection', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_SHARE, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-deep-link (a revoked received link is the failure being exercised)
    // quality: allow-no-interaction (opening the revoked URL is the failure outcome)
    await setupPublicApi(page, { shareGone: true })
    await page.goto(`/es-co/additional-modules/share/${shareUuid}`, { waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('heading', { name: 'No hay módulos disponibles' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Reintentar' })).toHaveCount(0)
  })

  test('copies the current shared-selection URL without creating another token', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_SHARE, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await page.addInitScript(() => {
      window.__copiedAdditionalModulesUrl = ''
      Object.defineProperty(window.navigator, 'clipboard', {
        configurable: true,
        value: {
          writeText: async (value) => {
            window.__copiedAdditionalModulesUrl = value
          },
        },
      })
    })
    await setupPublicApi(page)
    await page.goto(`/es-co/additional-modules/share/${shareUuid}`, { waitUntil: 'domcontentloaded' })

    await page.getByTestId('additional-modules-share-floating').click()
    await expect(page.getByTestId('additional-modules-share-dialog')).toBeVisible()
    await page.getByTestId('additional-modules-copy-link').click()

    await expect(page.getByTestId('additional-modules-share-feedback')).toHaveText('Enlace copiado')
    const copiedUrl = await page.evaluate(() => window.__copiedAdditionalModulesUrl)
    expect(new URL(copiedUrl).pathname).toBe(`/es-co/additional-modules/share/${shareUuid}`)
  })

  test('starts in light mode with the public theme control available', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_THEME, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)

    await expect(page.getByTestId('additional-modules-catalog')).toHaveAttribute('data-theme', 'light')
    await expect(page.getByTestId('additional-modules-theme-toggle')).toBeVisible()
  })

  test('remembers dark mode after reloading the public catalog', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_THEME, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)

    await page.getByTestId('additional-modules-theme-toggle').click()
    await expect(page.getByTestId('additional-modules-catalog')).toHaveAttribute('data-theme', 'dark')
    await page.reload({ waitUntil: 'domcontentloaded' })

    await expect(page.getByTestId('additional-modules-catalog')).toHaveAttribute('data-theme', 'dark')
  })

  test('introduces the catalog controls on the first visit', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_GUIDE, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupPublicApi(page, { showGuide: true })
    await openFromFooter(page)

    await expect(page.getByTestId('additional-modules-guide')).toBeVisible()
    await expect(page.getByTestId('additional-modules-guide')).toContainText('Empieza por el video')
    await expect(page.getByTestId('additional-modules-guide-progress')).toHaveText('1/8')
  })

  test('reopens the catalog guide from its floating control', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_GUIDE, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)
    await expect(page.getByTestId('additional-modules-guide')).toHaveCount(0)

    await page.getByTestId('additional-modules-guide-restart').click()
    await expect(page.getByTestId('additional-modules-guide')).toBeVisible()
    await page.getByRole('button', { name: 'Omitir' }).click()
    await expect(page.getByTestId('additional-modules-guide')).toHaveCount(0)

    await page.getByTestId('additional-modules-guide-restart').click()
    await expect(page.getByTestId('additional-modules-guide')).toBeVisible()
  })

  test('downloads the public catalog PDF', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_PDF, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupPublicApi(page, scenario)
    await openFromFooter(page)
    await page.getByTestId('additional-language-en').click()
    await expect(page).toHaveURL(/\/en-us\/additional-modules$/)
    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('additional-modules-download-pdf-floating').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe('additional-modules-catalog.pdf')
    expect(scenario.pdfLanguage).toBe('en')
  })

  test('keeps the shared catalog open when its PDF becomes unavailable', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_PDF, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-deep-link (a prospect enters from the received message URL)
    await setupPublicApi(page, { pdfFailure: true })
    await page.goto(`/es-co/additional-modules/share/${shareUuid}`, { waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('additional-module-card-electronic-invoicing')).toBeVisible()
    await page.getByTestId('additional-modules-download-pdf-floating').click()
    await expect(page.getByText('No pudimos generar el PDF. Vuelve a intentarlo.')).toBeVisible()
    await expect(page).toHaveURL(new RegExp(`/additional-modules/share/${shareUuid}$`))
  })
  test('shows the explainer video as the first block under the catalog title', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_EXPLAINER, '@role:guest', '@outcome:display', '@responsive:public'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)

    const card = page.getByTestId('additional-modules-explainer-card')
    await expect(card).toBeVisible()
    await expect(card).toContainText('Descubre lo que tu plataforma puede hacer')
    const headingBox = await page.getByRole('heading', { name: 'Módulos adicionales' }).boundingBox()
    const cardBox = await card.boundingBox()
    const firstModuleBox = await page.getByTestId('additional-module-card-electronic-invoicing').boundingBox()
    expect(cardBox.y).toBeGreaterThan(headingBox.y)
    expect(cardBox.y).toBeLessThan(firstModuleBox.y)
    await expect(page.getByTestId('additional-modules-explainer-player')).toHaveCount(0)
  })

  test('plays the explainer inline with native controls', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_EXPLAINER, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)

    await page.getByTestId('additional-modules-explainer-play').click()

    const player = page.getByTestId('additional-modules-explainer-player')
    await expect(player).toBeVisible()
    await expect(player).toHaveAttribute('controls', '')
    await expect(player).toHaveAttribute('src', /additional-modules-brag-v2-es[^/]*\.mp4/)
    await expect(page.getByTestId('additional-modules-explainer-play')).toHaveCount(0)
  })

  test('keeps the explainer paused after returning to its window', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_EXPLAINER, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await openFromFooter(page)
    await page.getByTestId('additional-modules-explainer-play').click()
    const player = page.getByTestId('additional-modules-explainer-player')
    await expect.poll(() => player.evaluate(element => element.currentTime)).toBeGreaterThan(0)

    // The OS focus event is the browser boundary; media playback itself is real.
    await page.evaluate(() => window.dispatchEvent(new Event('blur')))
    await expect(player).toHaveJSProperty('paused', true)
    const pausedAt = await player.evaluate(element => element.currentTime)
    await page.evaluate(() => window.dispatchEvent(new Event('focus')))

    await expect(player).toHaveJSProperty('paused', true)
    await expect(player).toHaveJSProperty('autoplay', false)
    await player.press('Space')
    await expect.poll(() => player.evaluate(element => element.currentTime)).toBeGreaterThan(pausedAt)
  })

  test('offers the video file when the browser cannot load the explainer', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_EXPLAINER, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupPublicApi(page)
    await page.route(/additional-modules-brag-v2-es[^/?]*\.mp4$/, (route) => route.abort())
    await openFromFooter(page)

    await page.getByTestId('additional-modules-explainer-play').click()

    await expect(page.getByTestId('additional-modules-explainer-error')).toContainText('No pudimos reproducir el video')
    await expect(page.getByTestId('additional-modules-explainer-open')).toHaveAttribute('href', /additional-modules-brag-v2-es[^/]*\.mp4/)
    await expect(page.getByTestId('additional-module-card-electronic-invoicing')).toBeVisible()
  })

  test('plays the explainer on a shared selection', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_EXPLAINER, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-deep-link (a prospect enters from the received message URL)
    await setupPublicApi(page)
    await page.goto(`/es-co/additional-modules/share/${shareUuid}`, { waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('additional-module-card-electronic-invoicing')).toBeVisible()

    await page.getByTestId('additional-modules-explainer-play').click()

    await expect(page.getByTestId('additional-modules-explainer-player')).toBeVisible()
    await expect(page).toHaveURL(new RegExp(`/additional-modules/share/${shareUuid}$`))
  })

  test('hides the explainer under the catalog title when the panel switch is off', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_EXPLAINER, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupPublicApi(page, { videoHidden: true })
    await openFromFooter(page)

    await expect(page.getByRole('heading', { name: 'Módulos adicionales' })).toBeVisible()
    await expect(page.getByTestId('additional-modules-explainer-card')).toHaveCount(0)
    await expect(page.getByTestId('additional-module-card-landing-page')).toBeVisible()
  })

  test('hides the explainer on a shared selection whose link turned it off', {
    tag: [...PUBLIC_ADDITIONAL_MODULES_EXPLAINER, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (a prospect enters from the received message URL)
    await setupPublicApi(page, { videoHidden: true })
    await page.goto(`/es-co/additional-modules/share/${shareUuid}`, { waitUntil: 'domcontentloaded' })
    const card = page.getByTestId('additional-module-card-electronic-invoicing')
    await expect(card).toBeVisible()
    await expect(page.getByTestId('additional-modules-explainer-card')).toHaveCount(0)

    await card.click()

    await expect(page.getByRole('dialog')).toContainText('Credenciales fiscales')
    await expect(page.getByTestId('additional-modules-explainer-card')).toHaveCount(0)
    await expect(page.getByTestId('additional-module-card-landing-page')).toHaveCount(0)
  })
})
