/**
 * Commercial video resource administration.
 *
 * Catches regressions where a resource manager disappears from one of its
 * four panel entry points, accepts an invalid file, or replaces a preview
 * after a failed upload.
 */
import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import { ADMIN_COMMERCIAL_VIDEO_RESOURCES } from '../helpers/flow-tags.js'
import { financingProgramFixture } from '../helpers/financing-fixture.js'
import { financingSettingsFixture } from '../helpers/financing-agreement-fixture.js'

const PROPOSAL_ID = 740
const RESOURCE_UUID = '74000000-1111-4111-8111-111111111111'
const UPLOADED_SRC = `/api/video-resources/${RESOURCE_UUID}/1/video/`
const CLIP_FILE = { name: 'clip.mp4', mimeType: 'video/mp4', buffer: Buffer.from('e2e-mp4') }

const proposal = {
  id: PROPOSAL_ID,
  uuid: '74000000-1111-4111-8111-111111111111',
  title: 'Propuesta de video E2E',
  client_name: 'Cliente de video',
  client_email: 'video@example.com',
  language: 'es',
  status: 'draft',
  is_active: true,
  total_investment: '5000000',
  currency: 'COP',
  sections: [],
  requirement_groups: [],
}

function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

function resource({ module = 'financing', mode = 'none', revision = 1, video = null } = {}) {
  return {
    key: `${module}:es`, module, language: 'es', mode, revision,
    filename: video ? 'existing.mp4' : null,
    size: video ? 1024 : 0,
    video,
  }
}

function catalogFixture() {
  return {
    revision: 'catalog-r1',
    categories: [{ id: 1, slug: 'commerce', name_es: 'Comercio', name_en: 'Commerce', order: 0, is_active: true, module_count: 1, active_module_count: 1 }],
    modules: [{
      id: 1, category: 1, slug: 'video-module', icon: '▶', order: 0, is_active: true,
      name_es: 'Módulo de video', name_en: 'Video module', summary_es: 'Recurso de prueba', summary_en: 'Test resource',
      what_is_es: 'Prueba', what_is_en: 'Test', purpose_es: 'Prueba', purpose_en: 'Test',
      problems_solved_es: [], problems_solved_en: [], integrations_es: [], integrations_en: [],
      implementation_requirements_es: [], implementation_requirements_en: [],
    }],
  }
}

async function setupApi(page, scenario = {}) {
  scenario.resources ??= {
    financing: resource({ mode: 'default' }),
    'additional-modules': resource({ module: 'additional-modules', mode: 'default' }),
    proposal: resource({ module: 'proposal', mode: 'default' }),
    personalized: resource({ module: 'proposal:740', mode: 'uploaded', video: { src: UPLOADED_SRC, poster: null } }),
  }

  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json(200, { user: { username: 'e2e-admin', is_staff: true } })
    if (apiPath === 'proposals/' && method === 'GET') return json(200, [proposal])
    if (apiPath === `proposals/${PROPOSAL_ID}/detail/` && method === 'GET') return json(200, proposal)
    if (apiPath === 'proposals/dashboard/') return json(200, { total: 1, by_status: { draft: 1 } })
    if (apiPath === 'proposals/alerts/') return json(200, [])
    if (apiPath === 'proposals/client-profiles/') return json(200, [])
    if (apiPath === 'explainer-videos/admin/settings/' && method === 'GET') {
      return json(200, { show_financing_video: true, show_additional_modules_video: true, show_proposal_video: true })
    }
    if (apiPath === 'financing/public/' && method === 'GET') return json(200, financingProgramFixture('es'))
    if (apiPath === 'financing/settings/' && method === 'GET') return json(200, financingSettingsFixture())
    if (apiPath === 'financing/agreements/' && method === 'GET') return json(200, { count: 0, limit: 25, offset: 0, results: [], stats: { total_active_records: 0, archived: 0, by_status: {} } })
    if (apiPath === 'additional-modules/admin/' && method === 'GET') return json(200, catalogFixture())
    if (apiPath === 'additional-modules/admin/shares/' && method === 'GET') return json(200, [])

    const moduleMatch = apiPath.match(/^video-resources\/admin\/modules\/([^/]+)\/([^/]+)\/$/)
    const proposalMatch = apiPath.match(/^video-resources\/admin\/proposals\/(\d+)\/$/)
    const key = moduleMatch?.[1] || (proposalMatch ? 'personalized' : null)
    if (key && method === 'GET') return json(200, scenario.resources[key])
    if (key && method === 'POST') {
      scenario.lastUpload = route.request().postData() || ''
      scenario.lastContentType = await route.request().headerValue('content-type') || ''
      if (scenario.uploadFails) return json(500, { detail: 'El validador de video no está disponible.' })
      const action = scenario.lastUpload.includes('name="action"\r\n\r\nremove') ? 'remove'
        : scenario.lastUpload.includes('name="action"\r\n\r\nrestore-default') ? 'restore-default' : 'upload'
      const previous = scenario.resources[key]
      const updated = action === 'remove'
        ? resource({ module: previous.module, mode: 'none', revision: previous.revision + 1 })
        : action === 'restore-default'
          ? resource({ module: previous.module, mode: 'default', revision: previous.revision + 1 })
          : resource({ module: previous.module, mode: 'uploaded', revision: previous.revision + 1, video: { src: `/api/video-resources/${RESOURCE_UUID}/${previous.revision + 1}/video/`, poster: null } })
      scenario.resources[key] = updated
      return json(200, updated)
    }
    return null
  })
}

async function authenticate(page) {
  await setAuthLocalStorage(page, { token: 'e2e-admin', userAuth: { id: 740, role: 'admin', is_staff: true } })
}

async function openProposals(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' })
  await page.getByRole('link', { name: 'Propuestas', exact: true }).click()
  await expect(page).toHaveURL(/\/es-co\/panel\/proposals$/)
}

async function openFinancingResources(page) {
  await openProposals(page)
  await page.getByRole('link', { name: 'Programa de Alianza', exact: true }).click()
  await page.getByTestId('financing-tab-settings').click()
  await expect(page.getByTestId('video-resource-manager')).toBeVisible()
}

async function openAdditionalModuleResources(page) {
  await openProposals(page)
  await page.getByRole('link', { name: 'Módulos adicionales', exact: true }).click()
  await page.getByRole('tab', { name: 'Recursos', exact: true }).click()
  await expect(page.getByTestId('video-resource-manager')).toBeVisible()
}

async function openProposalGlobalResources(page) {
  await openProposals(page)
  await page.getByTestId('filter-tabs-config').click()
  await expect(page.getByTestId('video-resource-manager')).toBeVisible()
}

async function openProposalPersonalizedResources(page) {
  await openProposals(page)
  await page.getByTestId(`proposal-open-${PROPOSAL_ID}`).click()
  await page.getByRole('tab', { name: 'Recursos', exact: true }).click()
  await expect(page.getByTestId('video-resource-manager')).toBeVisible()
}

test.describe('Admin commercial video resources', () => {
  test.setTimeout(60_000)

  test.beforeEach(async ({ page }) => authenticate(page))

  test('Programa de Alianza settings displays its default video resource', {
    tag: [...ADMIN_COMMERCIAL_VIDEO_RESOURCES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (starts at the panel home and reaches this resource through visible navigation)
    await setupApi(page)
    await openFinancingResources(page)

    await expect(page.getByTestId('video-resource-manager')).toContainText('Recursos · Video general')
    await expect(page.getByLabel('Vista previa del video')).toHaveAttribute('src', /financing-brag-v2-es\.mp4/)
  })

  test('Additional Modules resources displays its default video resource', {
    tag: [...ADMIN_COMMERCIAL_VIDEO_RESOURCES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (starts at the panel home and reaches this resource through visible navigation)
    await setupApi(page)
    await openAdditionalModuleResources(page)

    await expect(page.getByTestId('video-resource-manager')).toContainText('Recursos · Video general')
    await expect(page.getByLabel('Vista previa del video')).toHaveAttribute('src', /additional-modules-brag-v2-es\.mp4/)
  })

  test('Propuestas Configuraciones displays the global video resource', {
    tag: [...ADMIN_COMMERCIAL_VIDEO_RESOURCES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (starts at the panel home and reaches this resource through visible navigation)
    await setupApi(page)
    await openProposalGlobalResources(page)

    await expect(page.getByTestId('video-resource-manager')).toContainText('Recursos · Video general')
    await expect(page.getByLabel('Vista previa del video')).toHaveAttribute('src', /proposal-brag-v2-es\.mp4/)
  })

  test('proposal Recursos displays its personalized video resource', {
    tag: [...ADMIN_COMMERCIAL_VIDEO_RESOURCES, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (starts at the panel home and reaches this resource through visible navigation)
    await setupApi(page)
    await openProposalPersonalizedResources(page)

    await expect(page.getByTestId('video-resource-manager')).toContainText('Video personalizado de esta propuesta')
    await expect(page.getByLabel('Vista previa del video')).toHaveAttribute('src', UPLOADED_SRC)
  })

  test('uploads a MP4 and replaces the financing preview with the returned resource', {
    tag: [...ADMIN_COMMERCIAL_VIDEO_RESOURCES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { resources: { financing: resource() } }
    await setupApi(page, scenario)
    await openFinancingResources(page)

    await page.getByLabel('Archivo de video').setInputFiles(CLIP_FILE)
    await page.getByRole('button', { name: 'Cargar video', exact: true }).click()

    await expect(page.getByRole('status')).toContainText('Recurso actualizado.')
    expect(scenario.lastContentType).toContain('multipart/form-data')
    expect(scenario.lastUpload).toContain('name="revision"')
    expect(scenario.lastUpload).toContain('name="file"; filename="clip.mp4"')
    await expect(page.getByLabel('Vista previa del video')).toHaveAttribute('src', /\/api\/video-resources\/74000000-1111-4111-8111-111111111111\/2\/video\/$/)
  })

  test('removes an uploaded video after confirmation and restores the default resource', {
    tag: [...ADMIN_COMMERCIAL_VIDEO_RESOURCES, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // quality: allow-flow-tag-mismatch (this success case exercises remove and restore; the adjacent success case exercises upload)
    const scenario = { resources: { financing: resource({ mode: 'uploaded', video: { src: UPLOADED_SRC, poster: null } }) } }
    await setupApi(page, scenario)
    await openFinancingResources(page)

    await page.getByRole('button', { name: 'Quitar video', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toContainText('El video dejará de aparecer.')
    await dialog.getByRole('button', { name: 'Quitar video', exact: true }).click()
    await expect(page.getByText('No hay video para este recurso.')).toBeVisible()

    await page.getByRole('button', { name: 'Restaurar predeterminado', exact: true }).click()
    await expect(page.getByLabel('Vista previa del video')).toHaveAttribute('src', /financing-brag-v2-es\.mp4/)
  })

  test('rejects a non-MP4 upload before a request is sent', {
    tag: [...ADMIN_COMMERCIAL_VIDEO_RESOURCES, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const scenario = { resources: { financing: resource() } }
    await setupApi(page, scenario)
    await openFinancingResources(page)

    await page.getByLabel('Archivo de video').setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('not a video') })
    await page.getByRole('button', { name: 'Cargar video', exact: true }).click()

    await expect(page.getByText('Selecciona un archivo MP4.')).toBeVisible()
    expect(scenario.lastUpload).toBeUndefined()
  })

  test('keeps the current preview when the video service rejects a replacement', {
    tag: [...ADMIN_COMMERCIAL_VIDEO_RESOURCES, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const scenario = { uploadFails: true, resources: { financing: resource({ mode: 'uploaded', video: { src: UPLOADED_SRC, poster: null } }) } }
    await setupApi(page, scenario)
    await openFinancingResources(page)

    await page.getByLabel('Archivo de video').setInputFiles(CLIP_FILE)
    await page.getByRole('button', { name: 'Sustituir video', exact: true }).click()

    await expect(page.getByText('El validador de video no está disponible.')).toBeVisible()
    await expect(page.getByLabel('Vista previa del video')).toHaveAttribute('src', UPLOADED_SRC)
  })
})
