import { expect } from './test.js'
import { mockApi } from './api.js'
import { financingProgramFixture } from './financing-fixture.js'
import { waitForNuxtApp } from './navigation.js'

export const commercialModule = {
  slug: 'landing-page', icon: '◫', name: 'Landing page',
  summary: 'Un punto de llegada para tus clientes.',
  what_is: 'Una página enfocada en una conversión.', purpose: 'Convertir visitas en oportunidades.',
  problems_solved: ['Falta de presencia digital'], integrations: ['Analítica'],
  implementation_requirements: ['Contenido de marca'],
}
export const commercialPages = [
  { name: 'catalog', path: '/es-co/additional-modules', prefix: 'additional-modules', root: 'additional-modules-catalog', share: 'additional-modules-share-floating', flow: 'public-additional-modules-theme' },
  { name: 'selection', path: '/es-co/additional-modules/share/11111111-1111-4111-8111-111111111111', prefix: 'additional-modules', root: 'additional-modules-catalog', share: 'additional-modules-share-floating', flow: 'public-additional-modules-theme' },
  { name: 'partnership', path: '/es-co/partnership-program', prefix: 'financing', root: 'financing-program', share: 'financing-share', flow: 'public-financing-theme' },
]

export async function setupCommercialPublic(page, { fail = false, video = false, categories } = {}) {
  await page.addInitScript(() => {
    localStorage.setItem('projectapp-additional-modules-guide-seen', 'true')
    localStorage.setItem('projectapp-financing-guide-seen', 'true')
  })
  await mockApi(page, ({ apiPath }) => {
    if (fail) return { status: 503, contentType: 'application/json', body: '{}' }
    const catalogCategories = categories || [{ slug: 'marketing', name: 'Marketing', modules: [commercialModule] }]
    const catalog = {
      language: 'es', total_modules: catalogCategories.reduce((total, category) => total + category.modules.length, 0),
      show_explainer_video: video, categories: catalogCategories,
    }
    const body = apiPath === 'financing/public/'
      ? financingProgramFixture('es', { showExplainerVideo: video })
      : catalog
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
  })
}

export async function openCommercial(page, entry) {
  // quality: allow-deep-link (these sales documents are entered through shared links)
  await page.goto(entry.path, { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  await expect(page.getByTestId(`${entry.prefix}-theme-toggle`)).toBeVisible()
}

export async function expectReadableHeading(page, entry) {
  const contrast = await page.getByTestId(entry.root).evaluate((root) => {
    const luminance = (color) => {
      const [r, g, b] = color.match(/[\d.]+/g).slice(0, 3).map((channel) => {
        const value = Number(channel) / 255
        return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
      })
      return r * 0.2126 + g * 0.7152 + b * 0.0722
    }
    const foreground = luminance(getComputedStyle(root.querySelector('h1')).color)
    const background = luminance(getComputedStyle(root).backgroundColor)
    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05)
  })
  expect(contrast).toBeGreaterThanOrEqual(3)
}

export async function expectLayeredCard(page, entry) {
  const cardId = entry.prefix === 'financing' ? 'financing-option-five-year' : 'additional-module-card-landing-page'
  const summary = entry.prefix === 'financing' ? financingProgramFixture().options[0].summary : commercialModule.summary
  const card = page.getByTestId(cardId)
  const pageBackground = await page.getByTestId(entry.root).evaluate((root) => getComputedStyle(root).backgroundColor)
  await expect(card).not.toHaveCSS('background-color', pageBackground)
  await expect.poll(() => card.getByText(summary, { exact: true }).evaluate((text, id) => {
    const luminance = (color) => color.match(/[\d.]+/g).slice(0, 3).map((channel) => {
      const value = Number(channel) / 255
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
    }).reduce((total, value, index) => total + value * [0.2126, 0.7152, 0.0722][index], 0)
    const foreground = luminance(getComputedStyle(text).color)
    const background = luminance(getComputedStyle(document.querySelector(`[data-testid="${id}"]`)).backgroundColor)
    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05)
  }, cardId)).toBeGreaterThanOrEqual(4.5)
}

export async function expectFloatingOrder(page, entry) {
  const theme = await page.getByTestId(`${entry.prefix}-theme-toggle`).boundingBox()
  const guide = await page.getByTestId(`${entry.prefix}-guide-restart`).boundingBox()
  const pdf = await page.getByTestId(`${entry.prefix}-download-pdf-floating`).boundingBox()
  const share = await page.getByTestId(entry.share).boundingBox()
  const whatsapp = await page.getByRole('link', { name: 'Contact our web design team via WhatsApp' }).boundingBox()
  expect(theme.width).toBe(44)
  expect(pdf.width).toBe(48)
  expect(guide.y + guide.height).toBeLessThan(theme.y)
  expect(share.y + share.height).toBeLessThan(pdf.y)
  expect(pdf.y + pdf.height).toBeLessThan(whatsapp.y)
  expect(share.x).toBe(pdf.x)
}
