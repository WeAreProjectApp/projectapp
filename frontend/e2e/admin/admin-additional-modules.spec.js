import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import { PANEL_BREAKPOINTS } from '../../config/responsive.js'
import {
  ADMIN_ADDITIONAL_MODULES_CATALOG,
  ADMIN_ADDITIONAL_MODULES_EXPLAINER,
  ADMIN_ADDITIONAL_MODULES_EXPLAINER_VISIBILITY,
  ADMIN_ADDITIONAL_MODULES_MANAGE,
  ADMIN_ADDITIONAL_MODULES_PDF,
  ADMIN_ADDITIONAL_MODULES_QUICK_ACCESS,
  ADMIN_ADDITIONAL_MODULES_REORDER,
  ADMIN_ADDITIONAL_MODULES_SHARE,
  ADMIN_ADDITIONAL_MODULES_SHARE_VIDEO,
} from '../helpers/flow-tags.js'

const categories = [
  { id: 1, slug: 'commerce', name_es: 'Comercio', name_en: 'Commerce', order: 0, is_active: true, module_count: 2, active_module_count: 2 },
  { id: 2, slug: 'marketing', name_es: 'Marketing', name_en: 'Marketing', order: 1, is_active: true, module_count: 1, active_module_count: 1 },
]

function moduleItem(id, category, slug, name) {
  return {
    id, category, slug, icon: '＋', order: id, is_active: true,
    name_es: name, name_en: `${name} EN`,
    summary_es: `Resumen ${name}`, summary_en: `Summary ${name}`,
    what_is_es: 'Una capacidad integrada.', what_is_en: 'An integrated capability.',
    purpose_es: 'Automatizar el proceso.', purpose_en: 'Automate the process.',
    problems_solved_es: ['Trabajo manual'], problems_solved_en: ['Manual work'],
    integrations_es: ['API externa'], integrations_en: ['External API'],
    implementation_requirements_es: ['Credenciales'], implementation_requirements_en: ['Credentials'],
  }
}

const modules = [
  moduleItem(10, 1, 'electronic-invoicing', 'Facturación electrónica'),
  moduleItem(11, 1, 'regional-payments', 'Pagos regionales'),
  moduleItem(12, 2, 'landing-page', 'Landing page'),
]
const catalog = { revision: 'revision-1', categories, modules }
const trackedLink = {
  id: 1, uuid: '11111111-1111-4111-8111-111111111111',
  recipient_label: 'Acme — pagos', client: null, client_name: '', language: 'es',
  selected_modules: modules.slice(0, 2),
  public_path: '/es-co/additional-modules/share/11111111-1111-4111-8111-111111111111',
  is_active: true, revoked_at: null, view_count: 2,
  first_viewed_at: '2026-08-20T10:00:00Z', last_viewed_at: '2026-08-21T10:00:00Z',
  created_at: '2026-08-19T10:00:00Z',
}

function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

async function setupApi(page, scenario = {}) {
  let catalogCalls = 0
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json(200, { user: { username: 'admin', is_staff: true } })
    if (apiPath === 'proposals/' && method === 'GET') return json(200, [])
    if (apiPath === 'proposals/dashboard/') return json(200, { total: 0, by_status: {} })
    if (apiPath === 'proposals/alerts/') return json(200, [])
    if (apiPath === 'proposals/client-profiles/') return json(200, scenario.clients || [])
    if (apiPath === 'additional-modules/admin/' && method === 'GET') {
      catalogCalls += 1
      if (scenario.catalogUnavailable || catalogCalls <= (scenario.catalogFailures || 0)) {
        return json(503, { detail: 'Servicio no disponible' })
      }
      return json(200, catalog)
    }
    if (apiPath === 'additional-modules/admin/shares/' && method === 'GET') return json(200, scenario.shareLinks || [])
    if (apiPath === 'explainer-videos/admin/settings/' && method === 'GET') {
      return json(200, { show_additional_modules_video: !scenario.catalogVideoHidden, show_financing_video: true })
    }
    if (apiPath === 'explainer-videos/admin/settings/update/' && method === 'PATCH') {
      scenario.videoPatch = route.request().postDataJSON()
      if (scenario.videoSaveFails) return json(500, { detail: 'Servicio no disponible' })
      return json(200, { show_financing_video: true, ...scenario.videoPatch })
    }
    if (apiPath === `additional-modules/admin/shares/${trackedLink.uuid}/` && method === 'PATCH') {
      scenario.shareVideoPatch = route.request().postDataJSON()
      return json(200, { ...trackedLink, ...scenario.shareVideoPatch })
    }
    if (apiPath === 'additional-modules/admin/modules/' && method === 'POST') {
      scenario.modulePayload = route.request().postDataJSON()
      return scenario.moduleFailure ? json(500, { detail: 'No se pudo guardar el módulo.' }) : json(201, modules[0])
    }
    if (apiPath === 'additional-modules/admin/modules/10/' && method === 'PATCH') {
      scenario.updatePayload = route.request().postDataJSON()
      return scenario.moduleFailure ? json(500, { detail: 'No se pudo guardar el módulo.' }) : json(200, modules[0])
    }
    if (apiPath === 'additional-modules/admin/reorder/' && method === 'POST') {
      scenario.orderPayload = route.request().postDataJSON()
      return scenario.staleOrder
        ? json(409, { detail: 'El catálogo cambió.', code: 'stale_catalog_revision' })
        : json(200, { revision: 'revision-2' })
    }
    if (apiPath === 'additional-modules/admin/shares/' && method === 'POST') {
      scenario.sharePayload = route.request().postDataJSON()
      return scenario.shareFailure
        ? json(500, { detail: 'No se pudo generar el enlace.' })
        : json(201, trackedLink)
    }
    if (apiPath.endsWith('/revoke/') && method === 'POST') return json(200, { ...trackedLink, is_active: false })
    if (apiPath === 'additional-modules/admin/pdf/' && method === 'POST') {
      scenario.pdfPayload = route.request().postDataJSON()
      if (scenario.pdfFailure) return json(500, { detail: 'No se pudo generar el PDF.' })
      return { status: 200, contentType: 'application/pdf', headers: { 'Content-Disposition': 'attachment; filename="catalogo.pdf"' }, body: '%PDF-1.4 demo' }
    }
    if (apiPath === 'additional-modules/public/pdf/' && method === 'GET') {
      scenario.fullPdfLanguage = new URL(route.request().url()).searchParams.get('lang')
      return {
        status: 200,
        contentType: 'application/pdf',
        headers: { 'Content-Disposition': 'attachment; filename="catalogo-completo.pdf"' },
        body: '%PDF-1.4 complete',
      }
    }
    return null
  })
}

async function openCatalog(page) {
  await page.goto('/es-co/panel/additional-modules', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('additional-admin-module-10')).toBeVisible({ timeout: 30_000 })
}

async function openSelection(page, mode = 'share') {
  await page.getByRole('button', { name: mode === 'share' ? 'Preparar selección' : 'Personalizar PDF' }).click()
  await expect(page.getByRole('heading', { name: mode === 'share' ? 'Preparar enlace compartible' : 'Preparar PDF' })).toBeVisible()
}

async function fillCreateForm(page) {
  await page.getByTestId('additional-module-new').click()
  const form = page.getByTestId('additional-module-form')
  await form.getByTestId('additional-module-category').selectOption('1')
  await form.getByTestId('additional-module-slug').fill('customer-portal')
  for (const [id, value] of Object.entries({
    'additional-module-name-es': 'Portal de clientes', 'additional-module-summary-es': 'Centraliza las solicitudes.',
    'additional-module-what-es': 'Un portal seguro.', 'additional-module-purpose-es': 'Dar autoservicio.',
    'additional-module-problems-es': 'Solicitudes dispersas', 'additional-module-integrations-es': 'CRM',
    'additional-module-requirements-es': 'Accesos del cliente',
  })) await form.locator(`#${id}`).fill(value)
  await form.getByRole('tab', { name: 'English' }).click()
  for (const [id, value] of Object.entries({
    'additional-module-name-en': 'Customer portal', 'additional-module-summary-en': 'Centralizes requests.',
    'additional-module-what-en': 'A secure portal.', 'additional-module-purpose-en': 'Enable self-service.',
    'additional-module-problems-en': 'Scattered requests', 'additional-module-integrations-en': 'CRM',
    'additional-module-requirements-en': 'Customer access',
  })) await form.locator(`#${id}`).fill(value)
  return form
}

test.describe('Additional modules admin catalog', () => {
  test.setTimeout(60_000)

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-admin', userAuth: { id: 1, role: 'admin', is_staff: true } })
  })

  test('navigates from Comercial and displays grouped catalog data', {
    tag: [...ADMIN_ADDITIONAL_MODULES_CATALOG, '@role:admin', '@outcome:display', '@responsive:commercial'],
  }, async ({ page }) => {
    await setupApi(page)
    // quality: allow-deep-link (the authenticated proposals page is setup; this test exercises the Comercial sidebar navigation to the catalog)
    await page.goto('/es-co/panel/proposals', { waitUntil: 'domcontentloaded' })
    if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
      await page.getByRole('button', { name: 'Abrir menú' }).click()
    }
    const catalogLink = page.getByRole('link', { name: 'Módulos adicionales', exact: true })
    await expect(catalogLink).toBeVisible()
    await catalogLink.click()
    await expect(page.getByRole('heading', { name: 'Catálogo de módulos adicionales' })).toBeVisible()
    await expect(page.getByTestId('additional-admin-module-10')).toContainText('Facturación electrónica')
    await expect(page.getByTestId('additional-admin-module-12')).toContainText('Landing page')

    const detailOpener = page.getByTestId('additional-admin-module-10').getByRole('button', { name: 'Ver detalle' })
    await detailOpener.click()
    const detail = page.getByRole('dialog')
    await expect(detail.getByRole('heading', { name: 'Facturación electrónica' })).toHaveText('Facturación electrónica')
    for (const section of ['Qué es', 'Para qué sirve', 'Qué resuelve', 'Qué se integra', 'Qué hace falta para implementarlo']) {
      await expect(detail.getByRole('heading', { name: section })).toHaveCount(1)
    }
    await detail.getByRole('button', { name: 'Cerrar' }).click()
    await expect(detail).not.toBeVisible()
    await expect(detailOpener).toBeFocused()
  })

  test('switches the panel catalog to English', {
    tag: [...ADMIN_ADDITIONAL_MODULES_CATALOG, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page)
    await openCatalog(page)

    await page.getByTestId('additional-language-en').click()

    await expect(page).toHaveURL(/\/en-us\/panel\/additional-modules$/)
    await expect(page.getByRole('heading', { name: 'Additional modules catalog' })).toBeVisible()
    await expect(page.getByTestId('additional-admin-module-10')).toContainText('Facturación electrónica EN')
  })

  test('exposes a canonical public URL that can be copied directly', {
    tag: [...ADMIN_ADDITIONAL_MODULES_QUICK_ACCESS, '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page, context }) => {
    await setupApi(page)
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    // quality: allow-deep-link (catalog entry is covered separately; this isolates the canonical sharing controls)
    await openCatalog(page)
    const expectedUrl = `${new URL(page.url()).origin}/es-co/additional-modules`

    await expect(page.getByTestId('additional-modules-public-url')).toHaveValue(expectedUrl)
    await page.getByTestId('additional-modules-copy-public-url').click()

    await expect(page.getByRole('alert')).toContainText('URL pública copiada')
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(expectedUrl)
    await expect(page.getByTestId('additional-modules-open-public'))
      .toHaveAttribute('href', '/es-co/additional-modules')
  })

  test('downloads the complete active catalog without opening the selection modal', {
    tag: [...ADMIN_ADDITIONAL_MODULES_QUICK_ACCESS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    // quality: allow-deep-link (catalog entry is covered separately; this isolates the complete PDF download)
    await openCatalog(page)

    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('additional-modules-download-full-pdf').click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toBe('catalogo-completo.pdf')
    expect(scenario.fullPdfLanguage).toBe('es')
    await expect(page.getByRole('heading', { name: 'Preparar PDF' })).toHaveCount(0)
  })

  test('shows compact rows in list mode', {
    tag: [...ADMIN_ADDITIONAL_MODULES_CATALOG, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (sidebar navigation is covered by the catalog entry test; this case isolates list presentation)
    await setupApi(page)
    await openCatalog(page)

    await page.getByTestId('additional-view-list').click()

    await expect(page.getByTestId('additional-admin-list-commerce')).toBeVisible()
    await expect(page.getByTestId('additional-admin-module-10')).toContainText('Facturación electrónica')
  })

  test('reveals complete details in accordion mode', {
    tag: [...ADMIN_ADDITIONAL_MODULES_CATALOG, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (sidebar navigation is covered by the catalog entry test; this case isolates accordion disclosure)
    await setupApi(page)
    await openCatalog(page)
    await page.getByTestId('additional-view-accordion').click()

    const trigger = page.getByTestId('additional-admin-accordion-trigger-10')
    await trigger.click()

    await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    await expect(page.getByTestId('additional-admin-module-10')).toContainText('Credenciales')
  })

  test('retries after the catalog request fails', {
    tag: [...ADMIN_ADDITIONAL_MODULES_CATALOG, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { catalogFailures: 1 })
    const initialFailure = page.waitForResponse((response) => (
      response.url().endsWith('/api/additional-modules/admin/') && response.status() === 503
    ))
    await page.goto('/es-co/panel/additional-modules', { waitUntil: 'domcontentloaded' })
    await initialFailure
    await expect(page.getByRole('alert')).toContainText('No pudimos cargar el catálogo')
    await page.getByRole('button', { name: 'Reintentar' }).click()
    await expect(page.getByTestId('additional-admin-module-10')).toBeVisible()
  })

  test('associates the English name error with its field', {
    tag: [...ADMIN_ADDITIONAL_MODULES_MANAGE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupApi(page)
    await openCatalog(page)
    await page.getByTestId('additional-module-new').click()
    await page.getByTestId('additional-module-save').click()

    // Catches a regression that disconnects the English field from its local validation message.
    const form = page.getByTestId('additional-module-form')
    await expect(form.getByRole('tab', { name: 'English' })).toHaveAttribute('aria-selected', 'true')
    const englishName = form.getByTestId('additional-module-name-en')
    await expect(englishName).toHaveAttribute('aria-invalid', 'true')
    const errorId = await englishName.getAttribute('aria-describedby')
    expect(errorId).toBeTruthy()
    await expect(form.locator(`[id="${errorId}"]`)).toHaveText('Escribe el nombre en inglés.')
    await expect(form.getByRole('alert')).toHaveCount(8)
    await expect(form.getByText('Completa los campos obligatorios', { exact: true })).toHaveCount(0)
  })

  test('creates a complete bilingual module', {
    tag: [...ADMIN_ADDITIONAL_MODULES_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    await openCatalog(page)
    const form = await fillCreateForm(page)
    const dialog = page.getByRole('dialog').filter({ has: form })
    await dialog.getByTestId('additional-module-save').click()
    await expect(form).not.toBeVisible()
    expect(scenario.modulePayload.name_es).toBe('Portal de clientes')
    expect(scenario.modulePayload.name_en).toBe('Customer portal')
    expect(scenario.modulePayload.problems_solved_es).toEqual(['Solicitudes dispersas'])
  })

  test('keeps the edit form open when the server rejects the save', {
    tag: [...ADMIN_ADDITIONAL_MODULES_MANAGE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { moduleFailure: true })
    await openCatalog(page)
    await page.getByTestId('additional-admin-module-10').getByRole('button', { name: 'Editar' }).click()
    await page.getByTestId('additional-module-save').click()
    await expect(page.getByTestId('additional-module-form')).toContainText('No se pudo guardar el módulo')
  })

  test('persists bilingual module edits with PATCH and closes the form', {
    tag: [...ADMIN_ADDITIONAL_MODULES_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    await openCatalog(page)
    await page.getByTestId('additional-admin-module-10').getByRole('button', { name: 'Editar' }).click()
    const form = page.getByTestId('additional-module-form')
    await form.getByTestId('additional-module-name-es').fill('Facturación electrónica automatizada')
    const dialog = page.getByRole('dialog').filter({ has: form })
    await dialog.getByTestId('additional-module-save').click()
    await expect(form).not.toBeVisible()
    expect(scenario.updatePayload.name_es).toBe('Facturación electrónica automatizada')
    expect(scenario.updatePayload.name_en).toBe('Facturación electrónica EN')
  })

  test('saves the new module order', {
    tag: [...ADMIN_ADDITIONAL_MODULES_REORDER, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    await openCatalog(page)
    await page.getByRole('button', { name: 'Reordenar' }).click()
    await page.getByRole('button', { name: 'Bajar: Facturación electrónica' }).click()
    await page.getByTestId('additional-catalog-order-save').click()
    await expect(page.getByRole('heading', { name: 'Orden del catálogo' })).not.toBeVisible()
    expect(scenario.orderPayload.module_groups[0].module_ids).toEqual([11, 10])
  })

  test('shows the recoverable stale-order message', {
    tag: [...ADMIN_ADDITIONAL_MODULES_REORDER, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { staleOrder: true })
    await openCatalog(page)
    await page.getByRole('button', { name: 'Reordenar' }).click()
    await page.getByTestId('additional-catalog-order-save').click()
    await expect(page.getByText('El catálogo cambió en otra sesión. Se recargó el orden más reciente.')).toBeVisible()
  })

  test('requires a selected module before creating a link', {
    tag: [...ADMIN_ADDITIONAL_MODULES_SHARE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupApi(page)
    await openCatalog(page)
    await openSelection(page)
    await page.getByTestId('additional-selection-submit').click()
    await expect(page.getByText('Selecciona al menos un módulo.')).toBeVisible()
  })

  test('generates a fixed-selection public link', {
    tag: [...ADMIN_ADDITIONAL_MODULES_SHARE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    await openCatalog(page)
    await openSelection(page)
    await page.getByTestId('additional-select-module-10').click()
    await page.getByTestId('additional-share-recipient').fill('Acme — pagos')
    await page.getByTestId('additional-selection-submit').click()
    await expect(page.getByText('Enlace listo para compartir')).toBeVisible()
    expect(scenario.sharePayload.selected_module_ids).toEqual([10])
    expect(scenario.sharePayload.recipient_label).toBe('Acme — pagos')
    expect(scenario.sharePayload.language).toBe('es')
  })

  test('shows link-generation server failures inside the selection modal', {
    tag: [...ADMIN_ADDITIONAL_MODULES_SHARE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { shareFailure: true })
    await openCatalog(page)
    await openSelection(page)
    await page.getByTestId('additional-select-module-10').click()
    await page.getByTestId('additional-share-recipient').fill('Acme')
    await page.getByTestId('additional-selection-submit').click()
    await expect(page.getByText('No se pudo generar el enlace.')).toBeVisible()
  })

  test('displays tracked openings and revokes a shared link', {
    tag: [...ADMIN_ADDITIONAL_MODULES_SHARE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupApi(page, { shareLinks: [trackedLink] })
    // quality: allow-deep-link (the commercial catalog navigation is covered above; this isolates the Seguimiento display and revoke behavior)
    await openCatalog(page)
    await page.getByTestId('additional-modules-tracking').click()
    const history = page.getByTestId('additional-share-history')
    await expect(history).toContainText('Acme — pagos')
    await expect(history).toContainText('2 aperturas')
    await history.getByRole('button', { name: 'Revocar' }).click()
    await expect(history).toContainText('Retirado')
  })

  test('downloads the selected PDF', {
    tag: [...ADMIN_ADDITIONAL_MODULES_PDF, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    await openCatalog(page)
    await openSelection(page, 'pdf')
    await page.getByTestId('additional-select-module-11').click()
    await page.getByTestId('additional-share-recipient').fill('Acme Colombia')
    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('additional-selection-submit').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe('catalogo-modulos-adicionales.pdf')
    expect(scenario.pdfPayload.module_ids).toEqual([10, 12])
    expect(scenario.pdfPayload.language).toBe('es')
    expect(scenario.pdfPayload.recipient_label).toBe('Acme Colombia')
  })

  test('shows PDF generation failures without closing the selection', {
    tag: [...ADMIN_ADDITIONAL_MODULES_PDF, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { pdfFailure: true })
    await openCatalog(page)
    await openSelection(page, 'pdf')
    await page.getByTestId('additional-selection-submit').click()
    await expect(page.getByText('No se pudo generar el PDF.')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Preparar PDF' })).toBeVisible()
  })
  test('previews the catalog explainer video from the panel', {
    tag: [...ADMIN_ADDITIONAL_MODULES_EXPLAINER, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page)
    await openCatalog(page)
    const card = page.getByTestId('additional-modules-explainer-card')
    await expect(card).toContainText('Video explicativo del catálogo')
    await expect(card).toHaveAttribute('data-variant', 'compact')

    await page.getByTestId('additional-modules-explainer-play').click()

    await expect(page.getByTestId('additional-modules-explainer-player')).toBeVisible()
  })

  test('hides the catalog video for clients from the panel switch', {
    tag: [...ADMIN_ADDITIONAL_MODULES_EXPLAINER_VISIBILITY, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    await openCatalog(page)
    const toggle = page.getByTestId('additional-modules-explainer-visibility-toggle')
    await expect(toggle).toHaveAttribute('aria-checked', 'true')

    await toggle.click()

    await expect(toggle).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByRole('alert')).toContainText('El video quedó oculto en la vista pública del catálogo.')
    expect(scenario.videoPatch).toEqual({ show_additional_modules_video: false })
  })

  test('reverts the catalog video switch when the save fails', {
    tag: [...ADMIN_ADDITIONAL_MODULES_EXPLAINER_VISIBILITY, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { videoSaveFails: true })
    await openCatalog(page)
    const toggle = page.getByTestId('additional-modules-explainer-visibility-toggle')
    await expect(toggle).toHaveAttribute('aria-checked', 'true')

    await toggle.click()

    await expect(page.getByRole('alert')).toContainText('No pudimos guardar la visibilidad del video.')
    await expect(toggle).toHaveAttribute('aria-checked', 'true')
  })

  test('creates a short share link without the explainer video', {
    tag: [...ADMIN_ADDITIONAL_MODULES_SHARE_VIDEO, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = {}
    await setupApi(page, scenario)
    await openCatalog(page)
    await openSelection(page)
    await page.getByTestId('additional-select-module-10').click()
    await page.getByTestId('additional-share-recipient').fill('Acme — pagos')

    await page.getByTestId('additional-share-video-toggle').click()
    await page.getByTestId('additional-selection-submit').click()

    await expect(page.getByText('Enlace listo para compartir')).toBeVisible()
    expect(scenario.sharePayload.show_explainer_video).toBe(false)
    expect(scenario.sharePayload.selected_module_ids).toEqual([10])
  })

  test('turns the video back on for one shared link from the history', {
    tag: [...ADMIN_ADDITIONAL_MODULES_SHARE_VIDEO, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { shareLinks: [{ ...trackedLink, show_explainer_video: false }] }
    await setupApi(page, scenario)
    await openCatalog(page)
    await page.getByTestId('additional-modules-tracking').click()
    const toggle = page.getByTestId(`additional-share-history-video-toggle-${trackedLink.uuid}`)
    await expect(toggle).toHaveAttribute('aria-checked', 'false')

    await toggle.click()

    await expect(toggle).toHaveAttribute('aria-checked', 'true')
    await expect(page.getByRole('alert')).toContainText('El enlace de Acme — pagos vuelve a mostrar el video.')
    expect(scenario.shareVideoPatch).toEqual({ show_explainer_video: true })
  })

  test('explains in the history that no link shows the video while the catalog hides it', {
    tag: [...ADMIN_ADDITIONAL_MODULES_SHARE_VIDEO, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupApi(page, { catalogVideoHidden: true, shareLinks: [trackedLink] })
    // quality: allow-deep-link (the commercial catalog navigation is covered above; this isolates the history notice)
    await openCatalog(page)
    await expect(page.getByTestId('additional-modules-explainer-visibility-toggle')).toHaveAttribute('aria-checked', 'false')

    await page.getByTestId('additional-modules-tracking').click()

    await expect(page.getByTestId('additional-share-history-video-catalog-off'))
      .toHaveText('El video está oculto para todo el catálogo, así que ningún enlace lo muestra hasta volver a encenderlo.')
    await expect(page.getByTestId('additional-share-history')).toContainText('Acme — pagos')
  })
})
