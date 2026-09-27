import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { financingProgramFixture } from '../helpers/financing-fixture.js'
import {
  PUBLIC_FINANCING_EXPLAINER,
  PUBLIC_FINANCING_GUIDE,
  PUBLIC_FINANCING_LANGUAGE,
  PUBLIC_FINANCING_LOAD,
  PUBLIC_FINANCING_OVERVIEW,
  PUBLIC_FINANCING_PDF,
  PUBLIC_FINANCING_SHARE,
  PUBLIC_FINANCING_TERMS,
} from '../helpers/flow-tags.js'


function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

async function setupApi(page, scenario = {}) {
  await page.addInitScript((showGuide) => {
    if (showGuide) {
      window.localStorage.removeItem('projectapp-financing-guide-seen')
      return
    }
    window.localStorage.setItem('projectapp-financing-guide-seen', 'true')
  }, Boolean(scenario.showGuide))
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'financing/public/pdf/' && method === 'GET') {
      const language = new URL(route.request().url()).searchParams.get('lang') || 'es'
      if (scenario.pdfUnavailable) return json(503, { detail: 'Unavailable' })
      scenario.pdfLanguage = language
      return {
        status: 200,
        contentType: 'application/pdf',
        headers: {
          'Content-Disposition': `attachment; filename="${language === 'en' ? 'partnership-program.pdf' : 'programa-de-alianza.pdf'}"`,
        },
        body: '%PDF-1.4 financing',
      }
    }
    if (apiPath === 'financing/public/' && method === 'GET') {
      if (scenario.programUnavailable) return json(503, { detail: 'Unavailable' })
      const language = new URL(route.request().url()).searchParams.get('lang') || 'es'
      return json(200, financingProgramFixture(language, { showExplainerVideo: !scenario.videoHidden }))
    }
    return null
  })
}

async function openFromFooter(page) {
  await page.goto('/es-co', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('button', { name: 'Switch to English' })).toBeEnabled()
  const link = page.getByRole('link', { name: 'Programa de Alianza', exact: true }).first()
  await link.scrollIntoViewIfNeeded()
  await link.click()
  await expect(page).toHaveURL(/\/es-co\/partnership-program$/)
  await expect(page.getByRole('heading', { name: 'Construimos hoy. Crecemos contigo.' })).toBeVisible()
}

test.describe('Public financing program', () => {
  test.setTimeout(60_000)

  test('shows the financing program after footer navigation', {
    tag: [...PUBLIC_FINANCING_OVERVIEW, '@role:guest', '@outcome:display', '@responsive:public'],
  }, async ({ page }) => {
    await setupApi(page)
    await openFromFooter(page)

    await expect(page.getByTestId('financing-option-five-year')).toContainText('Alianza a 5 años')
    await expect(page.getByTestId('financing-option-three-year')).toContainText('Alianza a 3 años')
    await expect(page.getByTestId('financing-condition-calculator')).toContainText('Calculadora de requerimientos')
    await expect(page.getByTestId('financing-condition-payment-discipline')).toContainText('aumenta en 2% el costo vigente del Hosting')
    await expect(page.getByTestId('financing-condition-project-value-range')).toContainText('Un rango claro para aplicar')
    await expect(page.getByTestId('financing-condition-risk-and-initial-payment')).toContainText('aporte desde el 20%')
    await expect(page.getByTestId('financing-option-five-year')).toContainText('dos ciclos')
    await expect(page.getByTestId('financing-option-five-year')).toContainText('Exclusividad conceptual a cargo de Project App.')
    await expect(page.getByTestId('financing-option-three-year')).toContainText('Sin el compromiso adicional de exclusividad conceptual')
    await expect(page.getByTestId('financing-condition-conceptual-exclusivity')).toContainText('proyectos competidores del mismo sector y nicho')
    await expect(page.getByTestId('financing-calculator-input-output')).toContainText('Qué se obtiene')
    await expect(page.getByTestId('financing-package-facts')).toContainText('No acumula horas')
    await expect(page.getByTestId('financing-whatsapp-cta')).toHaveAttribute('href', /wa\.me\/573238122373/)
    await expect(page.locator('nav[aria-label="Main navigation"]')).toHaveCount(0)
  })

  test('switches the financing program to English', {
    tag: [...PUBLIC_FINANCING_LANGUAGE, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page)
    await openFromFooter(page)

    await page.getByTestId('financing-language-en').click()

    await expect(page).toHaveURL(/\/en-us\/partnership-program$/)
    await expect(page.getByRole('heading', { name: 'We build today. We grow with you.' })).toBeVisible()
    await expect(page.getByTestId('financing-option-five-year')).toContainText('5-year partnership')
    await expect(page.getByTestId('financing-condition-conceptual-exclusivity')).toContainText('Conceptual exclusivity — five-year option only')
  })

  test('expands the five-year conceptual exclusivity scope', {
    tag: [...PUBLIC_FINANCING_TERMS, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page)
    await openFromFooter(page)
    const trigger = page.getByTestId('financing-term-trigger-conceptual-exclusivity-scope')

    await trigger.click()

    await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const term = page.getByTestId('financing-term-conceptual-exclusivity-scope')
    await expect(term.getByText('Aplica únicamente al elegir la modalidad de cinco años', { exact: false })).toBeVisible()
    await expect(term).toContainText('un segundo ciclo no reinicia ni extiende este plazo')
    await expect(term).toContainText('delimitan por escrito el sector, el nicho, el producto')
  })

  test('expands the code custody rule', {
    tag: [...PUBLIC_FINANCING_TERMS, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page)
    await openFromFooter(page)
    const trigger = page.getByTestId('financing-term-trigger-code-custody')

    await trigger.click()

    await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    await expect(page.getByTestId('financing-term-code-custody'))
      .toContainText('La custodia no transfiere la propiedad intelectual.')
  })

  test('copies the localized financing URL', {
    tag: [...PUBLIC_FINANCING_SHARE, '@role:guest', '@outcome:success'],
  }, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'share', { configurable: true, value: undefined })
    })
    await setupApi(page)
    await openFromFooter(page)

    await page.getByTestId('financing-share').click()
    await page.getByTestId('financing-copy-link').click()

    expect(await page.evaluate(() => navigator.clipboard.readText()))
      .toMatch(/\/es-co\/partnership-program$/)
  })

  test('downloads the Spanish financing booklet', {
    tag: [...PUBLIC_FINANCING_PDF, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    await openFromFooter(page)

    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('financing-download-pdf').click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toBe('programa-de-alianza.pdf')
    expect(scenario.pdfLanguage).toBe('es')
  })

  test('shows a PDF failure without leaving the program', {
    tag: [...PUBLIC_FINANCING_PDF, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { pdfUnavailable: true })
    await openFromFooter(page)

    await page.getByTestId('financing-download-pdf').click()

    await expect(page.getByRole('alert')).toContainText('No pudimos generar el PDF')
    await expect(page.getByRole('heading', { name: 'Construimos hoy. Crecemos contigo.' })).toBeVisible()
  })

  test('recovers after the program request fails', {
    tag: [...PUBLIC_FINANCING_LOAD, '@role:guest', '@outcome:failure', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { programUnavailable: true }
    await setupApi(page, scenario)
    await page.goto('/es-co/partnership-program', { waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('heading', { name: 'No pudimos cargar el Programa de Alianza.' })).toBeVisible()
    scenario.programUnavailable = false

    await page.getByRole('button', { name: 'Reintentar' }).click()

    await expect(page.getByRole('heading', { name: 'Construimos hoy. Crecemos contigo.' })).toBeVisible()
  })
  test('plays the financing explainer from the hero', {
    tag: [...PUBLIC_FINANCING_EXPLAINER, '@role:guest', '@outcome:success', '@responsive:public'],
  }, async ({ page }) => {
    await setupApi(page)
    await openFromFooter(page)
    await expect(page.getByTestId('financing-explainer-card')).toContainText('Conoce el Programa de Alianza')

    await page.getByTestId('financing-explainer-play').click()

    const player = page.getByTestId('financing-explainer-player')
    await expect(player).toBeVisible()
    await expect(player).toHaveAttribute('controls', '')
    await expect(player).toHaveAttribute('src', /financing-brag-v2-es[^/]*\.mp4/)
  })

  test('shows a fallback link when the financing video cannot load', {
    tag: [...PUBLIC_FINANCING_EXPLAINER, '@role:guest', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page)
    await page.route(/financing-brag-v2-es[^/?]*\.mp4$/, (route) => route.abort())
    await openFromFooter(page)

    await page.getByTestId('financing-explainer-play').click()

    await expect(page.getByTestId('financing-explainer-error')).toContainText('No pudimos reproducir el video')
    await expect(page.getByTestId('financing-explainer-open')).toHaveAttribute('href', /financing-brag-v2-es[^/]*\.mp4/)
    await expect(page.getByTestId('financing-whatsapp-hero')).toBeVisible()
  })

  test('hides the explainer in the English program until that render exists', {
    tag: [...PUBLIC_FINANCING_EXPLAINER, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupApi(page)
    await openFromFooter(page)
    await expect(page.getByTestId('financing-explainer-card')).toBeVisible()

    await page.getByTestId('financing-language-en').click()

    await expect(page).toHaveURL(/\/en-us\/partnership-program$/)
    await expect(page.getByRole('heading', { name: 'We build today. We grow with you.' })).toBeVisible()
    await expect(page.getByTestId('financing-explainer-card')).toHaveCount(0)
  })

  test('hides the explainer and starts the guide at the options when the panel switch is off', {
    tag: [...PUBLIC_FINANCING_EXPLAINER, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupApi(page, { videoHidden: true, showGuide: true })
    await openFromFooter(page)

    await expect(page.getByTestId('financing-guide')).toContainText('Dos formas de alianza')
    await expect(page.getByTestId('financing-guide-progress')).toHaveText('1/7')
    await expect(page.getByTestId('financing-explainer-card')).toHaveCount(0)
    await expect(page.getByTestId('financing-whatsapp-hero')).toBeVisible()
  })

  test('introduces the financing program on the first visit', {
    tag: [...PUBLIC_FINANCING_GUIDE, '@role:guest', '@outcome:display'],
  }, async ({ page }) => {
    await setupApi(page, { showGuide: true })
    await openFromFooter(page)

    await expect(page.getByTestId('financing-guide')).toBeVisible()
    await expect(page.getByTestId('financing-guide')).toContainText('Empieza por el video')
    await expect(page.getByTestId('financing-guide-progress')).toHaveText('1/8')
  })

  test('reopens the financing guide from its floating control', {
    tag: [...PUBLIC_FINANCING_GUIDE, '@role:guest', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page)
    await openFromFooter(page)
    await expect(page.getByTestId('financing-guide')).toHaveCount(0)

    await page.getByTestId('financing-guide-restart').click()
    await expect(page.getByTestId('financing-guide')).toBeVisible()
    await page.getByRole('button', { name: 'Omitir' }).click()
    await expect(page.getByTestId('financing-guide')).toHaveCount(0)

    await page.getByTestId('financing-guide-restart').click()
    await expect(page.getByTestId('financing-guide')).toBeVisible()
  })
})
