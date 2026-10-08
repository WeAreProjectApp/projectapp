// qa: draft-unvalidated (2026-10-07 — combined runtime pending)
import { test, expect } from '../helpers/test.js'
import { authenticate, backendUrl, fixture, openReview, openWorkspace, publish, submitDecision } from './helpers.js'
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

// Fails if retained Django administration flags override the client's current
// Platform role and turn its own JWT review into an administrative operation.
test('a client with retained Django flags records its own review', {
  tag: ['@flow:platform-delivery-review', '@role:platform-client', '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo, 'client-retained-django-flags')
  const session = await authenticate(page, request, data)
  expect(session.user).toMatchObject({ role: 'client', user_id: expect.any(Number) })
  await openWorkspace(page, data)
  const message = 'Conformidad registrada con mi rol actual de cliente.'
  await submitDecision(page, data, 0, 'approved', message)
  await page.reload({ waitUntil: 'domcontentloaded' })
  const requirement = page.getByTestId(`delivery-requirement-${data.requirement_ids[0]}`)
  await expect(requirement).toContainText('Aprobado')
  await expect(requirement).toContainText(message)
  const response = await request.get(`${backendUrl}/api/accounts/projects/${data.project.id}/delivery/`, {
    headers: { Authorization: `Bearer ${session.tokens.access}` },
  })
  expect(response.status()).toBe(200)
  const workspace = await response.json()
  const persisted = workspace.scopes.flatMap((scope) => scope.phases)
    .flatMap((phase) => phase.stages).flatMap((stage) => stage.requirements)
    .find((item) => item.id === data.requirement_ids[0])
  expect(persisted.reviews).toEqual([expect.objectContaining({
    id: expect.any(Number), actor_id: session.user.user_id, decision: 'approved',
    is_external: false, message,
  })])
})

for (const [decision, label] of [['objected', 'objection'], ['rejected', 'rejection']]) {
test(`a client ${label} requires its motive`, {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-client', '@outcome:error'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await openReview(page, data)
  await page.getByTestId(`delivery-review-decision-${data.requirement_ids[1]}`).selectOption(decision)
  await page.getByTestId('delivery-review-submit').click()
  await expect(page.getByTestId('delivery-review-form')).toContainText('Describe el motivo de la objeción o rechazo.')
  await expect(page.getByTestId(`delivery-review-message-${data.requirement_ids[1]}`)).toHaveAttribute('aria-invalid', 'true')
})
}

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
  // Partial review is a real client API precondition. This case drives the
  // administrative reopen through the UI, then reads its result as the client.
  const data = await fixture(request, testInfo, 'review-partial')
  const context = await browser.newContext()
  const adminPage = await context.newPage()
  try {
    await authenticate(adminPage, request, data, 'admin')
    await openWorkspace(adminPage, data)
    await adminPage.getByTestId(`delivery-report-open-${data.stage_id}`).click()
    await adminPage.getByTestId('delivery-report-message').fill('Atendimos el correo observado. Por favor compruébalo en la nueva ronda.')
    await adminPage.getByTestId('delivery-report-submit').click()
    await expect(adminPage.getByTestId('delivery-report-message')).toHaveCount(0)
    await expect(adminPage.getByTestId(`delivery-publish-${data.stage_id}`)).toHaveText('Abrir nueva ronda')

    await publish(adminPage, data.stage_id)

    await authenticate(page, request, data)
    await openWorkspace(page, data)
    const approved = page.getByTestId(`delivery-requirement-${data.requirement_ids[0]}`)
    await expect(approved.locator('header').first()).toContainText('Aprobado')
    await expect(approved).toContainText('El traslado quedó conforme.')
    await expect(page.getByTestId(`delivery-requirement-${data.requirement_ids[1]}`).locator('header').first()).toContainText('En revisión')
  } finally {
    await context.close()
  }
})

// Detecta que una revisión desactualizada borre el motivo o registre conformidad sobre otro contenido.
test('a stale review preserves the unsent client observation', {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-client', '@outcome:failure'],
}, async ({ page, request, browser }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await openReview(page, data)
  await page.getByTestId(`delivery-review-decision-${data.requirement_ids[1]}`).selectOption('objected')
  await page.getByTestId(`delivery-review-message-${data.requirement_ids[1]}`).fill('El correo sigue pendiente de mi comprobación.')
  const context = await browser.newContext()
  const adminPage = await context.newPage()
  await authenticate(adminPage, request, data, 'admin')
  await openWorkspace(adminPage, data)
  await adminPage.getByTestId(`delivery-edit-requirement-${data.requirement_ids[1]}`).click()
  await adminPage.getByLabel('Qué debe pasar', { exact: true }).fill('Resultado corregido para la siguiente publicación.')
  await adminPage.getByTestId('delivery-authoring-save').click()
  await expect(adminPage.getByTestId('delivery-authoring-form')).toHaveCount(0)

  await page.getByTestId('delivery-review-submit').click()

  await expect(page.getByTestId('delivery-review-form')).toContainText('El contenido cambió mientras lo revisabas.')
  await expect(page.getByTestId(`delivery-review-message-${data.requirement_ids[1]}`)).toHaveValue('El correo sigue pendiente de mi comprobación.')
  await context.close()
})

// Detecta que un rechazo con motivo no se conserve en el historial de la versión probada.
test('client retrieves a rejected result after returning', {
  tag: [...PLATFORM_DELIVERY_REVIEW, '@role:platform-client', '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await submitDecision(page, data, 1, 'rejected', 'Las cantidades recibidas no corresponden al registro preparado.')

  await page.reload({ waitUntil: 'domcontentloaded' })

  const requirement = page.getByTestId(`delivery-requirement-${data.requirement_ids[1]}`)
  await expect(requirement.getByText('Rechazado', { exact: true })).toHaveCount(2)
  await expect(requirement.getByTestId('delivery-review-history')).toContainText('Las cantidades recibidas no corresponden al registro preparado.')
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

// Detecta que una respuesta desactualizada desaparezca del formulario o sobrescriba una conversación nueva.
test('a stale response preserves the unsent message', {
  tag: ['@flow:platform-delivery-responses', '@module:platform', '@priority:P1', '@role:platform-client', '@outcome:failure'],
}, async ({ page, request, browser }, testInfo) => {
  const data = await fixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await page.getByTestId(`delivery-report-open-${data.stage_id}`).click()
  await page.getByTestId('delivery-report-message').fill('Observación pendiente de envío.')
  const context = await browser.newContext()
  const adminPage = await context.newPage()
  await authenticate(adminPage, request, data, 'admin')
  await openWorkspace(adminPage, data)
  await adminPage.getByTestId(`delivery-report-open-${data.stage_id}`).click()
  await adminPage.getByTestId('delivery-report-message').fill('Actualización pública más reciente.')
  await adminPage.getByTestId('delivery-report-submit').click()
  await expect(adminPage.getByTestId('delivery-report-message')).toHaveCount(0)

  await page.getByTestId('delivery-report-submit').click()

  await expect(page.getByRole('dialog')).toContainText('El contenido cambió mientras lo revisabas.')
  await expect(page.getByTestId('delivery-report-message')).toHaveValue('Observación pendiente de envío.')
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId(`delivery-stage-${data.stage_id}`)).toContainText('Actualización pública más reciente.')
  await expect(page.getByTestId(`delivery-stage-${data.stage_id}`)).not.toContainText('Observación pendiente de envío.')
  await context.close()
})
