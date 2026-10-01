import { expect } from '../helpers/test.js'
import { setPlatformAuth } from '../helpers/platform-auth.js'
import { waitForNuxtApp } from '../helpers/navigation.js'

export const backendUrl = 'http://127.0.0.1:4212'
export async function fixture(request, testInfo) {
  const response = await request.post(`${backendUrl}/__issues_fixture__`, { data: { key: testInfo.title.replace(/[^a-z0-9]/gi, '-').slice(0, 90) } })
  expect(response.ok()).toBeTruthy()
  return response.json()
}
export async function login(request, credentials) {
  const response = await request.post(`${backendUrl}/api/accounts/login/`, { data: credentials })
  expect(response.ok()).toBeTruthy()
  return response.json()
}
export async function open(page, request, data, projectId, kind = 'bugs', query = '', role = 'client') {
  const session = await login(request, data[role])
  await setPlatformAuth(page, { user: session.user, accessToken: session.tokens.access, refreshToken: session.tokens.refresh })
  await page.goto('/es-co/platform/projects', { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  await page.getByTestId(`project-row-${projectId}`).or(page.getByTestId(`project-card-${projectId}`)).click()
  await page.getByRole('link', { name: kind === 'bugs' ? 'Bugs' : 'Solicitudes', exact: true }).click()
  await expect(page.getByRole('heading', { name: kind === 'bugs' ? 'Reporte de bugs' : 'Solicitudes de cambio', exact: true })).toBeVisible({ timeout: 30_000 })
  return session
}
export async function openFromDelivery(page, request, data, projectId, query) {
  const session = await login(request, data.client)
  await setPlatformAuth(page, { user: session.user, accessToken: session.tokens.access, refreshToken: session.tokens.refresh })
  // The historical publication query is the ticket domain's entry contract.
  // P3 owns the delivery action that will supply this exact publication ID.
  await page.goto(`/es-co/platform/projects/${projectId}/bugs${query}`, { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  await expect(page.getByRole('heading', { name: 'Reporte de bugs', exact: true })).toBeVisible({ timeout: 30_000 })
  return session
}
export async function apiPost(request, session, path, data) {
  const response = await request.post(`${backendUrl}/api/accounts/${path}`, { data, headers: { Authorization: `Bearer ${session.tokens.access}` } })
  expect(response.ok()).toBeTruthy()
  return response.json()
}
