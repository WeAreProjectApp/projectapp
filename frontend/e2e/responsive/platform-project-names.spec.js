/** PA-229: RESP-R090 must retain project columns; RESP-R094 must identify the closed source selector. */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setPlatformAuth, mockPlatformClient, mockPlatformAdmin } from '../helpers/platform-auth.js'
import { waitForNuxtApp } from '../helpers/navigation.js'
import { viewportUse } from '../helpers/viewports.js'
import { RESPONSIVE_PROFILES } from './catalog-scenarios.js'

test.setTimeout(60_000)

const names = {
  unbroken: 'Proyecto'.repeat(25),
  spaced: 'Proyecto con un nombre largo '.repeat(7).slice(0, 175),
}
// DevQA confirmed these lengths without changing the active DEVQA-000 dataset.
const reportedNames = {
  unbroken: 'QA_RESPONSIVE_SIN_ESPACIOS_'.padEnd(177, 'X'),
  spaced: 'QA RESPONSIVE — Proyecto ficticio con nombre largo '.repeat(4).slice(0, 165),
}
const project = {
  id: 77, name: 'Proyecto de validación', status: 'active', status_label: 'Activo',
  current_state: { color: 'emerald', operational_effect: 'operating' },
  progress: 65, bugs_open_count: 3, phases_total_amount: '1200000.00',
  last_activity_at: '2026-10-01T12:00:00Z', client_id: mockPlatformClient.id,
  client_name: 'Cliente de prueba', client_email: 'cliente@example.test',
  changes_pending_count: 2,
}
const requirements = [
  { id: 41, title: 'RequerimientoExtremoSinEspacios'.padEnd(300, 'X'), contract_title: 'Alcance vigente', stage_title: 'Etapa 1: revisión del cliente', source_publication_id: 11, source_requirement_version: 1 },
  { id: 42, title: `${names.spaced}OrigenDos`, contract_title: 'Alcance vigente', stage_title: 'Etapa 1: revisión del cliente', source_publication_id: 11, source_requirement_version: 1 },
]
const recordKinds = { compact: 'card', portrait: 'card', landscape: 'row', desktop: 'row', wide: 'row' }
const entry = (page, profile, id) => page.getByTestId(`project-${recordKinds[profile]}-${id}`)
const responsiveTags = (profile) => [
  '@responsive:clients', '@responsive-special:clients',
  '@responsive-batch:clients-special-3', `@viewport:${profile}`,
]
const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

async function setup(page, { name = project.name, user = mockPlatformClient } = {}) {
  const projects = [
    { ...project, name },
    { ...project, id: 78, name: 'Proyecto corto' },
    { ...project, id: 79, name: reportedNames.unbroken },
    { ...project, id: 80, name: reportedNames.spaced },
  ]
  await setPlatformAuth(page, { user })
  await page.addInitScript(() => localStorage.setItem('platform_theme', 'light'))
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/') return json(user)
    if (apiPath === 'accounts/projects/' && method === 'GET') return json(projects)
    if (apiPath === 'accounts/projects/77/' && method === 'GET') return json(projects[0])
    if (apiPath === 'accounts/projects/77/issue-reports/context-options/') return json({ requirements, contracts: [], documents: [] })
    if (/accounts\/projects\/77\/(bug-reports|change-requests|phases|requirements)\/$/.test(apiPath)) return json([])
    if (apiPath === 'accounts/notifications/unread-count/') return json({ unread_count: 0 })
    return null
  })
}

async function openProjects(page) {
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
}

async function assertCompleteText(locator, value) {
  await expect(locator).toHaveText(value)
  const geometry = await locator.evaluate((element) => ({
    scrollWidth: element.scrollWidth, width: element.clientWidth,
    scrollHeight: element.scrollHeight, height: element.clientHeight,
  }))
  expect(geometry.scrollWidth, 'El nombre completo queda recortado horizontalmente').toBeLessThanOrEqual(geometry.width + 1)
  expect(geometry.scrollHeight, 'El nombre completo queda recortado verticalmente').toBeLessThanOrEqual(geometry.height + 1)
}

async function assertRecordFits(record, page) {
  const bounds = await record.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds.x).toBeGreaterThanOrEqual(0)
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(page.viewportSize().width + 1)
  const horizontalOverflow = await record.evaluate((element) => element.scrollWidth - element.clientWidth)
  expect(horizontalOverflow, 'Una columna o el acceso al detalle quedó fuera de la fila').toBeLessThanOrEqual(1)
}

const verifyTableByProfile = {
  compact: async () => {},
  portrait: async () => {},
  landscape: verifyTable,
  desktop: verifyTable,
  wide: verifyTable,
}

async function verifyTable(page) {
  const container = page.getByTestId('projects-table-container')
  const geometry = await container.evaluate((element) => ({
    width: element.clientWidth, scrollWidth: element.scrollWidth, scrollLeft: element.scrollLeft,
  }))
  expect(geometry.scrollLeft).toBe(0)
  expect(geometry.scrollWidth, 'Las columnas deben caber desde la posición inicial').toBeLessThanOrEqual(geometry.width + 1)
  await expect(page.getByRole('columnheader', { name: 'Progreso', exact: true })).toBeInViewport()
  await expect(page.getByRole('columnheader', { name: 'Bugs abiertos', exact: true })).toBeInViewport()
  await expect(page.getByRole('columnheader', { name: 'Valor total', exact: true })).toBeInViewport()
  await expect(page.getByRole('columnheader', { name: 'Última actividad', exact: true })).toBeInViewport()
  const detailCell = entry(page, 'desktop', project.id).getByRole('cell').last()
  await expect(detailCell).toBeInViewport()
}

async function openSource(page, profile, tab, button) {
  await openProjects(page)
  await entry(page, profile, project.id).click()
  await page.getByRole('link', { name: tab, exact: true }).click()
  await page.getByRole('button', { name: button, exact: true }).first().click()
  await expect(page.getByTestId('issue-source').getByRole('option')).toHaveCount(requirements.length + 1)
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`PA-229 · ${profile}`, () => {
    test.use(viewportUse(profile))

    for (const [variant, name] of Object.entries(names)) {
      test(`client opens a project with a ${variant} name from the complete list`, {
        tag: ['@flow:platform-project-list', '@outcome:display', ...responsiveTags(profile)],
      }, async ({ page }, testInfo) => {
        // quality: allow-deep-link (the authenticated project list is the shell entry; the project detail is reached by clicking its visible record)
        await setup(page, { name })
        await openProjects(page)
        await expect(page.getByTestId(new RegExp(`^project-${recordKinds[profile]}-`))).toHaveCount(4)
        await assertCompleteText(page.getByTestId(`project-name-${project.id}`), name)
        await assertCompleteText(page.getByTestId('project-name-78'), 'Proyecto corto')
        await assertCompleteText(page.getByTestId('project-name-79'), reportedNames.unbroken)
        await assertCompleteText(page.getByTestId('project-name-80'), reportedNames.spaced)
        const record = entry(page, profile, project.id)
        await expect(record).toContainText('65%')
        await expect(record).toContainText('1.200.000')
        await expect(record).toContainText('3')
        await assertRecordFits(record, page)
        await assertRecordFits(entry(page, profile, 78), page)
        await assertRecordFits(entry(page, profile, 79), page)
        await assertRecordFits(entry(page, profile, 80), page)
        await verifyTableByProfile[profile](page)
        await assertResponsiveScenario(page, testInfo, null, { profile })

        await record.click()
        await expect(page).toHaveURL(/\/platform\/projects\/77$/)
        await expect(page.getByRole('link', { name: 'Bugs', exact: true })).toBeVisible()
      })
    }

    test('client identifies the selected bug requirement before submitting', {
      tag: ['@flow:platform-bug-reports', '@outcome:display', ...responsiveTags(profile)],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (openSource starts at the authenticated project list, then opens the project, Bugs tab and report form through UI controls)
      await setup(page)
      await openSource(page, profile, 'Bugs', 'Reportar bug')
      const picker = page.getByTestId('issue-source')
      await picker.selectOption(String(requirements[0].id))
      await picker.blur()
      await assertCompleteText(page.getByTestId('issue-source-title'), requirements[0].title)
      await expect(page.getByTestId('issue-source-selection')).toContainText(requirements[0].stage_title)
      await picker.selectOption(String(requirements[1].id))
      await picker.blur()
      await assertCompleteText(page.getByTestId('issue-source-title'), requirements[1].title)
      await expect(picker).toHaveValue(String(requirements[1].id))
      await assertResponsiveScenario(page, testInfo, null, { profile })
      await picker.selectOption('')
      await expect(page.getByTestId('issue-source-selection')).toHaveCount(0)
    })
  })
}

for (const profile of ['compact', 'desktop']) {
  test.describe(`PA-229 shared consumers · ${profile}`, () => {
    test.use(viewportUse(profile))

    test('client identifies the required source of a change request', {
      tag: ['@flow:platform-change-requests', '@outcome:display', ...responsiveTags(profile)],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (openSource starts at the authenticated project list, then opens the project, Solicitudes tab and request form through UI controls)
      await setup(page)
      await openSource(page, profile, 'Solicitudes', 'Nueva solicitud')
      const picker = page.getByTestId('issue-source')
      await picker.selectOption(String(requirements[0].id))
      await picker.blur()
      await assertCompleteText(page.getByTestId('issue-source-title'), requirements[0].title)
      await expect(picker).toHaveValue(String(requirements[0].id))
      await assertResponsiveScenario(page, testInfo, null, { profile })
    })

    test('admin opens the long project without losing client data', {
      tag: ['@flow:platform-project-list', '@outcome:display', ...responsiveTags(profile)],
    }, async ({ page }, testInfo) => {
      // quality: allow-deep-link (the authenticated project list is the shell entry; the administrator reaches the detail by clicking its visible record)
      await setup(page, { name: names.unbroken, user: mockPlatformAdmin })
      await openProjects(page)
      const record = entry(page, profile, project.id)
      await assertCompleteText(page.getByTestId(`project-name-${project.id}`), names.unbroken)
      await expect(record).toContainText(project.client_name)
      await expect(record).toContainText(project.client_email)
      await assertRecordFits(record, page)
      await verifyTableByProfile[profile](page)
      await assertResponsiveScenario(page, testInfo, null, { profile })
      await record.click()
      await expect(page).toHaveURL(/\/platform\/projects\/77$/)
    })
  })
}
