import { randomUUID } from 'node:crypto'
import { backendUrl, frontendUrl } from './ports.js'
import { expect } from '../helpers/test.js'
import { setPlatformAuth } from '../helpers/platform-auth.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import { waitForNuxtApp } from '../helpers/navigation.js'
export { backendUrl, frontendUrl }
export async function fixture(request, testInfo, grants = []) {
  const response = await request.post(`${backendUrl}/__p4_fixture__`, {
    data: { key: `${testInfo.title.replace(/[^a-z0-9]/gi, '-').slice(0, 90)}-${randomUUID()}`, grants } })
  expect(response.ok()).toBeTruthy()
  return response.json()
}
export async function authenticate(page, request, data, role = 'client') {
  const response = await request.post(`${backendUrl}/api/accounts/login/`, { data: data[role] })
  expect(response.ok()).toBeTruthy()
  const result = await response.json()
  await setPlatformAuth(page, { user: result.user, accessToken: result.tokens.access, refreshToken: result.tokens.refresh })
  return result
}
export async function authenticatePanel(page, data) {
  await page.context().addCookies([
    { name: 'sessionid', value: data.panel_session, url: frontendUrl, httpOnly: true },
    { name: 'csrftoken', value: data.csrf_token, url: frontendUrl },
  ])
  await setAuthLocalStorage(page, { token: 'panel-test-session', userAuth: { id: 1, role: 'admin', is_staff: true, is_superuser: false } })
}
export async function openProject(page, data) {
  await page.goto(`${frontendUrl}/es-co/platform/projects`, { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  const row = page.getByTestId(`project-row-${data.project.id}`).or(page.getByTestId(`project-card-${data.project.id}`))
  await expect(row).toContainText(data.project.name)
  await row.click()
  await expect(page.getByRole('heading', { name: data.project.name, exact: true })).toBeVisible()
}
export async function openIdeas(page, data) {
  await openProject(page, data)
  await page.getByRole('link', { name: 'Ideas', exact: true }).click()
  await expect(page.getByTestId(`project-idea-${data.idea.id}`)).toContainText(data.idea.text)
}
export async function openAccess(page, data) {
  await openProject(page, data)
  await page.getByRole('link', { name: 'Accesos', exact: true }).click()
}
