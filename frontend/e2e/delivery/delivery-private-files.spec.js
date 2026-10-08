// Catches missing legal categories, public/incorrect file downloads, hidden JWT
// permission errors, or duplicate downloads while the real response is pending.
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { test, expect } from '../helpers/test.js'
import { waitForNuxtApp } from '../helpers/navigation.js'
import { authenticate, backendUrl, fixture, frontendUrl } from './helpers.js'

const categories = [
  { value: 'contract', label: 'Contrato' },
  { value: 'amendment', label: 'Otrosí' },
  { value: 'legal_annex', label: 'Anexo legal' },
]

test.setTimeout(60_000)

async function openResources(page, data) {
  await page.goto(`${frontendUrl}/es-co/platform/projects`, { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  const project = page.getByTestId(`project-row-${data.project.id}`).or(page.getByTestId(`project-card-${data.project.id}`))
  await expect(project).toContainText(data.project.name)
  await project.click()
  await page.getByRole('link', { name: 'Recursos', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Recursos', exact: true })).toHaveText('Recursos', { timeout: 30_000 })
}

async function openResourceDetail(page, data, resource) {
  await openResources(page, data)
  const detailPromise = page.waitForResponse((response) =>
    response.url().endsWith(`/deliverables/${resource.id}/`) && response.request().method() === 'GET',
  )
  await page.getByRole('row').filter({ hasText: resource.title }).click()
  const response = await detailPromise
  expect(response.status()).toBe(200)
  await expect(page.getByRole('heading', { name: resource.title, exact: true })).toHaveText(resource.title)
  return response.json()
}

function escapeName(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function selectedFile(detail, kind) {
  return kind === 'current' ? detail : detail.versions.find((version) => version.version_number === 1)
}

function downloadButton(page, detail, kind) {
  const file = selectedFile(detail, kind)
  return kind === 'current'
    ? page.getByRole('button').filter({ hasText: file.file_name }).filter({ hasText: `Versión ${detail.current_version}` })
    : page.getByRole('button', { name: new RegExp(`^v1\\s+${escapeName(file.file_name)}`) })
}

function deferred() {
  let resolve
  const promise = new Promise((ready) => { resolve = ready })
  return { promise, resolve }
}

for (const category of categories) {
  test(`client filters real private resources in the ${category.value} category`, {
    tag: ['@flow:platform-deliverables', '@module:platform', '@priority:P2', '@role:platform-client', '@outcome:display'],
  }, async ({ page, request }, testInfo) => {
    // Catches an omitted legal category or a filter that mixes another category's resources.
    // quality: allow-deep-link (the authenticated projects index is setup; the project row and Recursos link are clicked before filtering the real resource list)
    const data = await fixture(request, testInfo, 'private-resources')
    await authenticate(page, request, data)
    const resource = data.resources.find((item) => item.category === category.value)
    await openResources(page, data)

    await page.getByRole('button', { name: category.label, exact: true }).click()

    const row = page.getByRole('row').filter({ hasText: resource.title })
    await expect(row.getByText(resource.title, { exact: true })).toHaveText(resource.title)
    await expect(row.getByText(category.label, { exact: true })).toHaveText(category.label)
    await expect(row.getByText(resource.file_name, { exact: true })).toHaveText(resource.file_name)
    await expect(page.getByRole('row')).toHaveCount(2)
  })
}

for (const kind of ['current', 'previous']) {
  test(`client downloads the exact ${kind} private resource file through its button`, {
    tag: ['@flow:platform-deliverables', '@module:platform', '@priority:P2', '@role:platform-client', '@outcome:success'],
  }, async ({ page, request }, testInfo) => {
    // Catches a raw media link, a wrong version, changed bytes, or loss of the backend filename.
    const data = await fixture(request, testInfo, 'private-resources')
    await authenticate(page, request, data)
    const resource = data.resources.find((item) => item.category === 'contract')
    const detail = await openResourceDetail(page, data, resource)
    const file = selectedFile(detail, kind)
    const expected = resource[`expected_${kind}`]
    const responsePromise = page.waitForResponse((response) => response.url() === new URL(file.file_url, frontendUrl).href)
    const downloadPromise = page.waitForEvent('download')

    await downloadButton(page, detail, kind).click()
    const response = await responsePromise
    const download = await downloadPromise
    const bytes = await readFile(await download.path())

    expect(response.status()).toBe(200)
    expect(response.headers()['content-type']).toBe('application/pdf')
    expect(response.headers()['cache-control']).toBe('no-store')
    expect(download.suggestedFilename()).toBe(expected.file_name)
    expect(bytes).toEqual(Buffer.from(expected.original_base64, 'base64'))
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(expected.sha256)
  })
}

test('a real foreign client permission denial keeps the resource modal open without a download', {
  tag: ['@flow:platform-deliverables', '@module:platform', '@priority:P2', '@role:platform-client', '@outcome:error'],
}, async ({ page, request }, testInfo) => {
  // Catches a JSON denial being saved as a file or swallowed while the modal closes.
  // Only the download transport receives another real client's JWT; production
  // authorization supplies the denial while the original authorized modal stays open.
  const data = await fixture(request, testInfo, 'private-resources')
  await authenticate(page, request, data)
  const resource = data.resources.find((item) => item.category === 'contract')
  const detail = await openResourceDetail(page, data, resource)
  const login = await request.post(`${backendUrl}/api/accounts/login/`, { data: data.foreign_client })
  expect(login.status()).toBe(200)
  const foreign = await login.json()
  const downloads = []
  page.on('download', (download) => downloads.push(download.suggestedFilename()))
  const url = new URL(detail.file_url, frontendUrl).href
  await page.route(url, (route) => route.continue({
    headers: { ...route.request().headers(), authorization: `Bearer ${foreign.tokens.access}` },
  }))
  const deniedPromise = page.waitForResponse((response) => response.url() === url)

  await downloadButton(page, detail, 'current').click()
  const denied = await deniedPromise

  expect(denied.status()).toBe(404)
  await expect(page.getByRole('alert')).toHaveText('Proyecto no encontrado.')
  await expect(page.getByRole('heading', { name: resource.title, exact: true })).toHaveText(resource.title)
  await expect(downloadButton(page, detail, 'current')).toBeEnabled()
  expect(downloads).toEqual([])
})

test('a double click keeps private resource download buttons disabled until the real response arrives', {
  tag: ['@flow:platform-deliverables', '@module:platform', '@priority:P2', '@role:platform-client', '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  // Catches a repeated click creating another request or artifact during an in-flight download.
  const data = await fixture(request, testInfo, 'private-resources')
  await authenticate(page, request, data)
  const resource = data.resources.find((item) => item.category === 'contract')
  const detail = await openResourceDetail(page, data, resource)
  const release = deferred()
  const received = deferred()
  const downloads = []
  let requests = 0
  page.on('download', (download) => downloads.push(download.suggestedFilename()))
  const url = new URL(detail.file_url, frontendUrl).href
  await page.route(url, async (route) => {
    requests += 1
    const response = await route.fetch()
    const body = await response.body()
    received.resolve(response.status())
    await release.promise
    await route.fulfill({ response, body })
  })
  const downloadedPromise = page.waitForEvent('download')
  try {
    await downloadButton(page, detail, 'current').dblclick()

    expect(await received.promise).toBe(200)
    await expect(downloadButton(page, detail, 'current')).toBeDisabled()
    await expect(downloadButton(page, detail, 'previous')).toBeDisabled()
    expect(requests).toBe(1)
    expect(downloads).toEqual([])
    release.resolve()
    const download = await downloadedPromise
    const bytes = await readFile(await download.path())
    expect(bytes).toEqual(Buffer.from(resource.expected_current.original_base64, 'base64'))
    expect(downloads).toEqual([resource.expected_current.file_name])
  } finally {
    release.resolve()
  }
})

test('a failed download connection preserves the resource modal for another attempt', {
  tag: ['@flow:platform-deliverables', '@module:platform', '@priority:P2', '@role:platform-client', '@outcome:failure'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo, 'private-resources')
  await authenticate(page, request, data)
  const resource = data.resources.find((item) => item.category === 'contract')
  const detail = await openResourceDetail(page, data, resource)
  const downloads = []
  page.on('download', (download) => downloads.push(download.suggestedFilename()))
  await page.route(new URL(detail.file_url, frontendUrl).href, (route) => route.abort('failed'))

  await downloadButton(page, detail, 'current').click()

  await expect(page.getByRole('alert')).toHaveText('No pudimos descargar el archivo. Inténtalo de nuevo.')
  await expect(page.getByRole('heading', { name: resource.title, exact: true })).toHaveText(resource.title)
  await expect(downloadButton(page, detail, 'current')).toBeEnabled()
  expect(downloads).toEqual([])
})
