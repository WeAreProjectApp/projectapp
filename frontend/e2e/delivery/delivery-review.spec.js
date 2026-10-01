import { test, expect } from '../helpers/test.js'
import { authenticate, fixture, openReview, openWorkspace, publish, submitDecision } from './helpers.js'
import { PLATFORM_DELIVERY_REVIEW } from '../helpers/flow-tags.js'

test.setTimeout(60_000)

test('client reaches the published validation guide from the project', {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-client', '@outcome:display'],
}, async ({ page, request }, testInfo) => {
  // quality: allow-deep-link (the authenticated projects list is the entry point; delivery is reached through project navigation)
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  const requirement = page.getByTestId(`delivery-requirement-${data.requirement_ids[0]}`)
  await expect(requirement).toContainText('Sucursal Norte y un registro preparado.')
  await expect(requirement).toContainText('La sucursal de destino muestra el traslado.')
  await expect(page.getByText('Caso privado nunca publicado')).toHaveCount(0)
})

test('client records a partial conformity', {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-client', '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await submitDecision(page, data, 0, 'approved', 'El traslado quedó conforme.')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId(`delivery-requirement-${data.requirement_ids[0]}`)).toContainText('Aprobado')
  await expect(page.getByTestId(`delivery-requirement-${data.requirement_ids[1]}`)).toContainText('En revisión')
  await expect(page.getByTestId(`delivery-review-open-${data.stage_id}`)).toBeVisible()
})

test('an objection requires its motive', {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-client', '@outcome:error'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await openReview(page, data)
  await page.getByTestId(`delivery-review-decision-${data.requirement_ids[1]}`).selectOption('objected')
  await page.getByTestId('delivery-review-submit').click()
  await expect(page.getByTestId('delivery-review-form')).toContainText('Describe el motivo de la objeción o rechazo.')
  await expect(page.getByTestId(`delivery-review-message-${data.requirement_ids[1]}`)).toHaveAttribute('aria-invalid', 'true')
})

test('client sees the recorded objection after returning', {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-client', '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await submitDecision(page, data, 1, 'objected', 'No recibí el correo del día.')
  await page.reload({ waitUntil: 'domcontentloaded' })
  const requirement = page.getByTestId(`delivery-requirement-${data.requirement_ids[1]}`)
  await expect(requirement).toContainText('Con observaciones')
  await expect(requirement).toContainText('No recibí el correo del día.')
})

test('a reopened round preserves earlier conformity', {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-admin', '@outcome:success'],
}, async ({ page, request, browser }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await submitDecision(page, data, 0, 'approved')
  await submitDecision(page, data, 1, 'objected', 'El correo aún no llega.')
  const context = await browser.newContext()
  const adminPage = await context.newPage()
  await authenticate(adminPage, request, data, 'admin')
  await openWorkspace(adminPage, data)
  await expect(adminPage.getByTestId(`delivery-publish-${data.stage_id}`)).toHaveText('Abrir nueva ronda')
  await publish(adminPage, data.stage_id)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId(`delivery-requirement-${data.requirement_ids[0]}`).locator('header').first()).toContainText('Aprobado')
  await expect(page.getByTestId(`delivery-requirement-${data.requirement_ids[1]}`).locator('header').first()).toContainText('En revisión')
  await submitDecision(page, data, 1, 'approved', 'Ahora llegó el correo.')
  await expect(page.getByTestId(`delivery-stage-${data.stage_id}`).locator('header').first()).toContainText('Aprobado')
  await context.close()
})

test('approved requirements survive a pending guide correction', {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-admin', '@outcome:success'],
}, async ({ page, request, browser }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await submitDecision(page, data, 0, 'approved', 'Conforme en Staging.')
  const adminContext = await browser.newContext()
  const adminPage = await adminContext.newPage()
  await authenticate(adminPage, request, data, 'admin')
  await openWorkspace(adminPage, data)
  await adminPage.getByTestId(`delivery-edit-requirement-${data.requirement_ids[1]}`).click()
  await adminPage.getByLabel('Qué debe pasar', { exact: true }).fill('El correo incluye también la sucursal de destino.')
  await adminPage.getByTestId('delivery-authoring-save').click()
  await expect(adminPage.getByTestId('delivery-authoring-form')).toHaveCount(0)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId(`delivery-stage-${data.stage_id}`).locator('header').first()).toContainText('En revisión')
  await expect(page.getByTestId(`delivery-requirement-${data.requirement_ids[1]}`)).toContainText('El correo llega con las cantidades esperadas.')
  await publish(adminPage, data.stage_id)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId(`delivery-requirement-${data.requirement_ids[0]}`)).toContainText('Aprobado')
  await expect(page.getByTestId(`delivery-requirement-${data.requirement_ids[1]}`)).toContainText('El correo incluye también la sucursal de destino.')
  await expect(adminPage.getByTestId(`delivery-edit-requirement-${data.requirement_ids[0]}`)).toHaveCount(0)
  await adminContext.close()
})

test('a stage closes after every requirement is approved', {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-client', '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await openReview(page, data)
  await page.getByTestId(`delivery-review-decision-${data.requirement_ids[0]}`).selectOption('approved')
  await page.getByTestId(`delivery-review-decision-${data.requirement_ids[1]}`).selectOption('approved')
  await page.getByTestId('delivery-review-submit').click()
  await expect(page.getByTestId('delivery-review-form')).toHaveCount(0)
  await expect(page.getByTestId(`delivery-review-open-${data.stage_id}`)).toHaveCount(0)
  await expect(page.getByTestId(`delivery-stage-${data.stage_id}`).locator('header').first()).toContainText('Aprobado')
  await expect(page.getByTestId(`delivery-phase-${data.phase_id}`).locator('header').first()).toContainText('En revisión')
})

test('client persists a response without an attachment', {
  tag: ['@flow:platform-delivery-responses', '@module:platform', '@priority:P1', '@role:platform-client', '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await page.getByTestId(`delivery-report-open-${data.stage_id}`).click()
  await page.getByTestId('delivery-report-message').fill('Mañana pruebo el correo con los datos preparados.')
  await page.getByTestId('delivery-report-submit').click()
  await expect(page.getByTestId('delivery-report-message')).toHaveCount(0)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId(`delivery-stage-${data.stage_id}`)).toContainText('Mañana pruebo el correo con los datos preparados.')
})

test('a response requires a message', {
  tag: ['@flow:platform-delivery-responses', '@module:platform', '@priority:P1', '@role:platform-client', '@outcome:error'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await page.getByTestId(`delivery-report-open-${data.stage_id}`).click()
  await page.getByTestId('delivery-report-submit').click()
  await expect(page.getByRole('dialog')).toContainText('Escribe un mensaje.')
  await expect(page.getByTestId('delivery-report-message')).toHaveValue('')
})
