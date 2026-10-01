import { test, expect } from '../helpers/test.js'
import { authenticate, fixture, frontendUrl, openAccess, openProject } from './helpers.js'

test.setTimeout(60_000)

test('client sees only the authorized URL from project navigation', { tag: ['@flow:platform-project-client-access', '@outcome:display'] }, async ({ page, request }, testInfo) => {
  // quality: allow-deep-link (openAccess starts at the authenticated project list and follows visible project and Access links)
  const data = await fixture(request, testInfo, ['staging.site_url'])
  await authenticate(page, request, data)
  await openAccess(page, data)
  await expect(page.getByTestId('project-client-access').getByRole('link')).toHaveCount(1)
  await expect(page.getByTestId('project-client-access').getByRole('link')).toHaveText('https://qa.example.test/')
  await expect(page.getByTestId('project-access-editor')).toHaveCount(0)
})

test('client reveals a password only after an explicit action', { tag: ['@flow:platform-project-client-access', '@outcome:success'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo, ['production.admin_password'])
  await authenticate(page, request, data)
  await openAccess(page, data)
  const credential = page.getByTestId('client-credential-production-admin_password')
  await expect(credential.getByTestId('client-credential-value')).toHaveCount(0)
  await credential.getByRole('button', { name: 'Mostrar', exact: true }).click()
  await expect(credential.getByTestId('client-credential-value')).toHaveText('production-secret')
  await credential.getByRole('button', { name: 'Ocultar', exact: true }).click()
  await expect(credential.getByTestId('client-credential-value')).toHaveCount(0)
})

test('revocation denies a fresh credential request', { tag: ['@flow:platform-project-client-access', '@outcome:error'], timeout: 120_000 }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo, ['production.admin_password'])
  await authenticate(page, request, data)
  await openAccess(page, data)
  const adminLogin = await request.post(`${frontendUrl}/api/accounts/login/`, { data: data.admin })
  const admin = await adminLogin.json()
  const headers = { Authorization: `Bearer ${admin.tokens.access}` }
  const policyResponse = await request.get(`${frontendUrl}/api/accounts/projects/${data.project.id}/access/client-policy/`, { headers })
  const policy = await policyResponse.json()
  const revoked = await request.patch(`${frontendUrl}/api/accounts/projects/${data.project.id}/access/client-policy/`, {
    headers, data: { expected_version: policy.version, source_token: policy.source_token,
      permissions: { production: { site_url: false, admin_url: false, admin_username: false, admin_password: false }, staging: { site_url: false, admin_url: false, admin_username: false, admin_password: false } } } })
  expect(revoked.status()).toBe(200)
  await page.getByTestId('client-credential-production-admin_password').getByRole('button', { name: 'Mostrar', exact: true }).click()
  await expect(page.getByTestId('project-client-access')).toContainText('No hay accesos habilitados')
  await expect(page.getByTestId('client-credential-value')).toHaveCount(0)
})

test('access load failure leaves no previous URLs', { tag: ['@flow:platform-project-client-access', '@outcome:failure'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo, ['production.site_url'])
  await authenticate(page, request, data)
  await openAccess(page, data)
  await page.route(`**/api/accounts/projects/${data.project.id}/client-access/`, async (route) => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Accesos temporalmente no disponibles' }) })
  })
  await page.getByTestId('project-client-access').getByRole('button', { name: 'Actualizar', exact: true }).click()
  await expect(page.getByTestId('project-client-access').getByRole('alert')).toContainText('Accesos temporalmente no disponibles')
  await expect(page.getByTestId('project-client-access').getByRole('link')).toHaveCount(0)
})

test('hidden access defaults preserve the other project modules', { tag: ['@flow:platform-project-client-access', '@outcome:display'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openProject(page, data)
  await expect(page.getByRole('link', { name: 'Accesos', exact: true })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Bugs', exact: true })).toHaveCount(1)
  await expect(page.getByRole('link', { name: 'Hosting', exact: true })).toHaveCount(1)
  await expect(page.getByRole('link', { name: 'Entregas', exact: true })).toHaveCount(1)
  await expect(page.locator('aside').filter({ has: page.getByRole('link', { name: 'Entregas', exact: true }) })).toContainText('Cuentas de cobro')
  // quality: allow-deep-link (direct compatibility route stays available as an empty projection when no grant adds a navigation link)
  await page.goto(`${frontendUrl}/es-co/platform/projects/${data.project.id}/access`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('project-client-access')).toContainText('No hay accesos habilitados')
})

test('admin enables one URL through the policy editor', { tag: ['@flow:admin-project-client-access-policy', '@outcome:success'], timeout: 120_000 }, async ({ page, request, browser }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openAccess(page, data)
  await page.getByTestId('client-access-enable-production-site_url').check()
  await page.getByTestId('client-access-policy-save').click()
  await expect(page.getByTestId('client-access-preview')).toContainText('https://client.example.test/')
  const clientPage = await browser.newPage()
  try {
    await authenticate(clientPage, request, data)
    await openAccess(clientPage, data)
    await expect(clientPage.getByTestId('project-client-access').getByRole('link')).toHaveCount(1)
    await expect(clientPage.getByTestId('project-client-access').getByRole('link')).toHaveText('https://client.example.test/')
  } finally { await clientPage.close() }
})

test('admin sees disabled unavailable fields in the policy', { tag: ['@flow:admin-project-client-access-policy', '@outcome:display'] }, async ({ page, request }, testInfo) => {
  // quality: allow-deep-link (openAccess starts at the authenticated project list and follows visible project and Access links)
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await openAccess(page, data)
  await expect(page.getByTestId('client-access-enable-staging-admin_password')).toBeDisabled()
  await expect(page.getByTestId('client-access-enable-production-site_url')).not.toBeChecked()
})

test('a stale source requires reloading the policy editor', { tag: ['@flow:admin-project-client-access-policy', '@outcome:error'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  const admin = await authenticate(page, request, data, 'admin')
  await openAccess(page, data)
  await expect(page.getByTestId('client-access-enable-production-site_url')).toBeEnabled()
  const updated = await request.patch(`${frontendUrl}/api/accounts/projects/${data.project.id}/access/`, {
    headers: { Authorization: `Bearer ${admin.tokens.access}` }, data: { environment: 'production', site_url: 'https://changed.example.test/' } })
  expect(updated.status()).toBe(200)
  await page.getByTestId('client-access-enable-production-site_url').check()
  await page.getByTestId('client-access-policy-save').click()
  await expect(page.getByTestId('client-access-policy').getByRole('alert')).toContainText('cambiaron')
})

test('policy load failure offers refresh without sharing data', { tag: ['@flow:admin-project-client-access-policy', '@outcome:failure'] }, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data, 'admin')
  await page.route(`**/api/accounts/projects/${data.project.id}/access/client-policy/`, async (route) => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Política temporalmente no disponible' }) })
  })
  await openAccess(page, data)
  await expect(page.getByTestId('client-access-policy').getByRole('alert')).toContainText('Política temporalmente no disponible')
  await expect(page.getByTestId('client-access-policy-save')).toHaveCount(0)
})
