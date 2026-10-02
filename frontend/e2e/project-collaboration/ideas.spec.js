import { test, expect } from '../helpers/test.js'
import { authenticate, authenticatePanel, fixture, frontendUrl, openIdeas } from './helpers.js'
import { waitForNuxtApp } from '../helpers/navigation.js'

test.setTimeout(60_000)

test('owner reads the preserved suggestion through project navigation', { tag: ['@flow:platform-project-ideas', '@outcome:display'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openIdeas(page, data)
  await expect(page.getByTestId(`project-idea-${data.idea.id}`)).toContainText('Cliente')
  await expect(page.getByTestId('idea-collection-title')).toHaveCount(0)
})

test('owner saves a suggestion that survives reloading', { tag: ['@flow:platform-project-ideas', '@outcome:success'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openIdeas(page, data)
  await page.getByTestId('project-idea-text').fill('Evaluar etiquetas de inventario para un contrato futuro')
  await page.getByTestId('project-idea-save').click()
  await expect(page.getByTestId('idea-text').filter({ hasText: 'Evaluar etiquetas de inventario' })).toHaveText('Evaluar etiquetas de inventario para un contrato futuro')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('idea-text').filter({ hasText: 'Evaluar etiquetas de inventario' })).toHaveText('Evaluar etiquetas de inventario para un contrato futuro')
})

test('another owner receives an error without the project suggestion', { tag: ['@flow:platform-project-ideas', '@outcome:error'] }, async ({ page, request }, testInfo) => {
  // quality: allow-no-interaction (no visible navigation may link to another owner's project; a direct URL verifies the authorization boundary)
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'other')
  // quality: allow-deep-link (direct unauthorized project URL proves the object permission boundary)
  await page.goto(`${frontendUrl}/es-co/platform/projects/${data.project.id}/ideas`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('project-ideas-workspace').getByRole('alert')).toContainText('Proyecto no encontrado')
  await expect(page.getByTestId('idea-text')).toHaveCount(0)
})

test('failed submission preserves the client draft for retry', { tag: ['@flow:platform-project-ideas', '@outcome:failure'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openIdeas(page, data)
  await page.route(`**/api/accounts/projects/${data.project.id}/ideas/`, async (route) => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Guardado temporalmente no disponible' }) })
  })
  await page.getByTestId('project-idea-text').fill('Mi borrador debe conservarse')
  await page.getByTestId('project-idea-save').click()
  await expect(page.getByTestId('project-ideas-workspace').getByRole('alert')).toContainText('Guardado temporalmente no disponible')
  await expect(page.getByTestId('project-idea-text')).toHaveValue('Mi borrador debe conservarse')
})

test('owner correction preserves the original text in versions', { tag: ['@flow:platform-project-ideas', '@outcome:success'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openIdeas(page, data)
  const suggestion = page.getByTestId(`project-idea-${data.idea.id}`)
  await suggestion.getByRole('button', { name: 'Corregir', exact: true }).click()
  await page.getByTestId('project-idea-text').fill('Corregir el tablero sin incorporarlo al contrato')
  await page.getByTestId('project-idea-save').click()
  await expect(suggestion.getByTestId('idea-text')).toHaveText('Corregir el tablero sin incorporarlo al contrato')
  await suggestion.getByRole('button', { name: 'Ver versiones', exact: true }).click()
  await expect(page.getByTestId('project-idea-history')).toContainText(data.idea.text)
})

async function panelIdeas(page, data) {
  await authenticatePanel(page, data)
  // quality: allow-deep-link (authenticated panel project list is the entry; the Ideas link performs navigation)
  await page.goto(`${frontendUrl}/es-co/panel/projects`, { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  await page.getByTestId('projects-search-input').fill(data.project.name)
  await page.getByTestId(`project-actions-${data.project.id}`).click()
  await page.getByTestId('project-actions-ideas').click()
  await expect(page.getByTestId(`project-idea-${data.idea.id}`)).toContainText(data.idea.text)
}

test('panel collects the exact selected suggestion for future evaluation', { tag: ['@flow:admin-project-idea-collection', '@outcome:success'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await panelIdeas(page, data)
  await page.getByTestId(`project-idea-${data.idea.id}`).getByRole('checkbox').check()
  await page.getByTestId('idea-collection-title').fill('Opciones para el siguiente contrato')
  await page.getByTestId('idea-collection-save').click()
  await expect(page.getByTestId('idea-collection')).toContainText(data.idea.text)
  await expect(page.getByTestId('idea-collection')).toContainText('Opciones para el siguiente contrato')
})

test('panel displays the original client author before collecting', { tag: ['@flow:admin-project-idea-collection', '@outcome:display'] }, async ({ page, request }, testInfo) => {
  // quality: allow-deep-link (panelIdeas enters the authenticated project list, filters the project and follows its visible Ideas link)
  const data = await fixture(request, testInfo)
  await panelIdeas(page, data)
  await expect(page.getByTestId(`project-idea-${data.idea.id}`)).toContainText('Cliente')
  await expect(page.getByTestId(`project-idea-${data.idea.id}`).getByRole('button', { name: 'Corregir', exact: true })).toHaveCount(0)
})

test('panel restores an archived suggestion without losing its text', { tag: ['@flow:admin-project-idea-collection', '@outcome:success'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await panelIdeas(page, data)
  const suggestion = page.getByTestId(`project-idea-${data.idea.id}`)
  await suggestion.getByRole('button', { name: 'Archivar', exact: true }).click()
  await expect(suggestion).toContainText('Archivada')
  await suggestion.getByRole('button', { name: 'Restaurar', exact: true }).click()
  await expect(suggestion.getByRole('button', { name: 'Archivar', exact: true })).toBeVisible()
  await expect(suggestion.getByTestId('idea-text')).toHaveText(data.idea.text)
})

test('stale collection selection retains the administrator selection', { tag: ['@flow:admin-project-idea-collection', '@outcome:error'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await panelIdeas(page, data)
  await page.getByTestId(`project-idea-${data.idea.id}`).getByRole('checkbox').check()
  await page.getByTestId('idea-collection-title').fill('Selección pendiente')
  const login = await request.post(`${frontendUrl}/api/accounts/login/`, { data: data.client })
  const session = await login.json()
  const changed = await request.patch(`${frontendUrl}/api/accounts/projects/${data.project.id}/ideas/${data.idea.id}/`, {
    headers: { Authorization: `Bearer ${session.tokens.access}` }, data: { text: 'Versión más reciente', expected_version: 1 } })
  expect(changed.status()).toBe(200)
  await page.getByTestId('idea-collection-save').click()
  await expect(page.getByTestId('project-ideas-workspace').getByRole('alert')).toContainText('cambiaron')
  await expect(page.getByTestId(`project-idea-${data.idea.id}`).getByRole('checkbox')).toBeChecked()
  await expect(page.getByTestId('idea-collection')).toHaveCount(0)
})

test('collection load failure has a recoverable message', { tag: ['@flow:admin-project-idea-collection', '@outcome:failure'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await page.route(`**/api/projects/${data.project.id}/idea-collections/**`, async (route) => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Recopilaciones temporalmente no disponibles' }) })
  })
  await panelIdeas(page, data)
  await expect(page.getByTestId('project-ideas-workspace').getByRole('alert')).toContainText('Recopilaciones temporalmente no disponibles')
})
