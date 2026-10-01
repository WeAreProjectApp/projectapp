import { expect } from '../helpers/test.js'
import { setPlatformAuth } from '../helpers/platform-auth.js'
import { waitForNuxtApp } from '../helpers/navigation.js'

export const backendUrl = 'http://127.0.0.1:3202'
export const frontendUrl = 'http://127.0.0.1:3203'

export async function fixture(request, testInfo) {
  const response = await request.post(`${backendUrl}/__delivery_fixture__`, {
    data: { key: testInfo.title.replace(/[^a-z0-9]/gi, '-').slice(0, 100) },
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

export async function authenticate(page, request, data, role = 'client') {
  const response = await request.post(`${backendUrl}/api/accounts/login/`, { data: data[role] })
  expect(response.ok()).toBeTruthy()
  const session = await response.json()
  expect(session.tokens.access).toBeTruthy()
  await setPlatformAuth(page, {
    user: session.user, accessToken: session.tokens.access, refreshToken: session.tokens.refresh,
  })
  return session
}

export async function openWorkspace(page, data) {
  await page.goto(`${frontendUrl}/es-co/platform/projects`, { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  const project = page.getByTestId(`project-row-${data.project.id}`).or(page.getByTestId(`project-card-${data.project.id}`))
  await expect(project).toContainText(data.project.name)
  await project.click()
  await page.getByRole('link', { name: 'Entregas', exact: true }).click()
  await expect(page.getByTestId(`delivery-stage-${data.stage_id}`)).toBeVisible()
  await expect(page.getByTestId('delivery-workspace').getByText('Cargando entregas…')).toHaveCount(0)
}

export async function openReview(page, data) {
  await page.getByTestId(`delivery-review-open-${data.stage_id}`).click()
  await expect(page.getByTestId('delivery-review-form')).toBeVisible()
}

export async function submitDecision(page, data, index, decision, message = '') {
  await openReview(page, data)
  await page.getByTestId(`delivery-review-decision-${data.requirement_ids[index]}`).selectOption(decision)
  await page.getByTestId(`delivery-review-message-${data.requirement_ids[index]}`).fill(message)
  await page.getByTestId('delivery-review-submit').click()
  await expect(page.getByTestId('delivery-review-form')).toHaveCount(0)
}

export async function publish(page, stageId) {
  await page.getByTestId(`delivery-publish-${stageId}`).click()
  await page.getByTestId('delivery-confirm-action').click()
  await expect(page.getByTestId('delivery-confirm-action')).toHaveCount(0)
}

export async function addRequirement(page, data, title) {
  await page.getByTestId(`delivery-add-requirement-${data.hidden_stage_id}`).click()
  await page.getByTestId('delivery-author-key').fill('prepared-case')
  await page.getByTestId('delivery-author-title').fill(title)
  await page.locator('#delivery-author-role').fill('Cliente')
  await page.locator('#delivery-author-environment').fill('Staging')
  await page.locator('#delivery-author-steps').fill('Abrir el caso preparado.\nConfirmar el resultado.')
  await page.locator('#delivery-author-expected_result').fill('Aparece el resultado esperado.')
  await page.locator('#delivery-author-failure_signals').fill('Aparece un error.')
  await page.getByTestId('delivery-authoring-save').click()
  await expect(page.getByTestId('delivery-authoring-form')).toHaveCount(0)
}
