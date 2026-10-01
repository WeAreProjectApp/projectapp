import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import { openProjectAction } from '../helpers/projects.js'

import { ADMIN_PROJECT_BRAND } from '../helpers/flow-tags.js'
test.setTimeout(60_000)

async function setup(page, { uploadError = false, loadError = false } = {}) {
  await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 9001, role: 'admin', is_staff: true } })
  const tree = { id: 'd5d5d5d5-1111-4111-8111-111111111111', name: 'Company links', handle: 'company', project: null }
  let assets = []
  const json = (data, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(data) })
  await mockApi(page, ({ route, apiPath, method }) => {
    if (apiPath === 'projects/1/brand/' && method === 'GET') return loadError ? json({ detail: 'Unavailable' }, 503) : json({ assets, linktrees: tree.project ? [tree] : [] })
    if (apiPath === 'projects/1/brand/' && method === 'POST') {
      if (uploadError) return json({ file: ['Formato rechazado.'] }, 400)
      assets = [{ id: 7, title: 'Brand manual', category: 'manual', filename: 'manual.pdf', size: 20 }]
      return json(assets[0], 201)
    }
    if (apiPath === 'projects/1/brand/7/' && method === 'DELETE') { assets = []; return { status: 204, body: '' } }
    if (apiPath === 'projects/1/brand/7/' && method === 'GET') return { status: 200, contentType: 'application/octet-stream', headers: { 'Content-Disposition': 'attachment; filename="manual.pdf"' }, body: '%PDF-1.4 manual' }
    if (apiPath === `linktrees/admin/${tree.id}/update/`) { tree.project = route.request().postDataJSON().project; return json(tree) }
    if (apiPath === 'linktrees/admin/') return json([tree])
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/') return json([])
    if (apiPath === 'projects/') return json({ results: [{ id: 1, name: 'Brand project', client: { profile_id: 1, name: 'Client' }, status_label: 'Activo', hostings_count: 0, incomes_count: 0 }], meta: { total: 1, by_state: [], clients_without_projects: 0, records_without_project: 0 } })
    return null
  })
  // quality: allow-deep-link (the flow under test is the brand modal, reached by clicking the project action)
  await page.goto('/en-us/panel/projects', { waitUntil: 'domcontentloaded' })
  await openLibrary(page)
  return page.getByTestId('project-brand-modal')
}

async function openLibrary(page) {
  await openProjectAction(page, 1, 'brand')
}

async function fillUpload(modal) {
  await modal.getByLabel('Resource name').fill('Brand manual')
  await modal.getByLabel('Category', { exact: true }).selectOption('manual')
  await modal.getByLabel('File', { exact: true }).setInputFiles({ name: 'manual.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 manual') })
}

test('links and unlinks an existing Linktree from a project', { tag: [...ADMIN_PROJECT_BRAND, '@role:admin', '@outcome:success'] }, async ({ page }) => {
  const modal = await setup(page)
  await modal.getByRole('combobox', { name: 'Select an unassigned Linktree' }).selectOption({ label: 'Company links (@company)' })
  await modal.getByRole('button', { name: 'Link', exact: true }).click()
  await expect(modal.getByRole('link', { name: 'Company links (@company)' })).toBeVisible()
  await modal.getByRole('button', { name: 'Close', exact: true }).click()
  await openLibrary(page)
  await expect(modal.getByRole('link', { name: 'Company links (@company)' })).toBeVisible()
  await modal.getByRole('button', { name: 'Unlink', exact: true }).click()
  await expect(modal.getByText('This project has no Linktrees yet.')).toBeVisible()
})

test('uploads downloads and confirms removal of a brand manual', { tag: [...ADMIN_PROJECT_BRAND, '@role:admin', '@outcome:success'] }, async ({ page }) => {
  const modal = await setup(page)
  await fillUpload(modal)
  await modal.getByRole('button', { name: 'Upload file' }).click()
  await expect(modal.getByRole('listitem').getByText('Brand manual', { exact: true })).toBeVisible()
  const download = page.waitForEvent('download')
  await modal.getByRole('link', { name: 'Download' }).click()
  expect((await download).suggestedFilename()).toBe('manual.pdf')
  await modal.getByRole('button', { name: 'Delete', exact: true }).click()
  await modal.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(modal.getByRole('link', { name: 'Download' })).toBeVisible()
  await modal.getByRole('button', { name: 'Delete', exact: true }).click()
  await modal.getByRole('button', { name: 'Confirm deletion' }).click()
  await expect(modal.getByText('No brand resources yet.')).toBeVisible()
})

test('keeps upload fields when the server rejects the file', { tag: [...ADMIN_PROJECT_BRAND, '@role:admin', '@outcome:error'] }, async ({ page }) => {
  const modal = await setup(page, { uploadError: true })
  await fillUpload(modal)
  await modal.getByRole('button', { name: 'Upload file' }).click()
  await expect(modal.getByRole('alert')).toHaveText('Formato rechazado.')
  await expect(modal.getByLabel('Resource name')).toHaveValue('Brand manual')
  await expect(modal.getByText('No brand resources yet.')).toBeVisible()
})

test('shows retry after a library loading failure', { tag: [...ADMIN_PROJECT_BRAND, '@role:admin', '@outcome:failure'] }, async ({ page }) => {
  const modal = await setup(page, { loadError: true })
  await expect(modal.getByRole('alert')).toHaveText('Could not load project resources.')
  await modal.getByRole('button', { name: 'Reload' }).click()
  await expect(modal.getByRole('alert')).toHaveText('Could not load project resources.')
  await expect(modal.getByRole('button', { name: 'Upload file' })).toHaveCount(0)
})

for (const width of [412, 835, 1195, 1440, 2560]) {
test(`opens the project brand library at ${width}px`, { tag: [...ADMIN_PROJECT_BRAND, '@role:admin', '@outcome:display'] }, async ({ page }) => {
  // quality: allow-deep-link (the project listing is the entry; this flow opens the brand modal through its visible action)
  await page.setViewportSize({ width, height: 915 })
  const modal = await setup(page)
  await expect(modal.getByText('No brand resources yet.')).toBeVisible()
  await expect(modal.getByRole('heading', { name: 'Brand and resources' })).toBeVisible()
  expect(await modal.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
})

}
