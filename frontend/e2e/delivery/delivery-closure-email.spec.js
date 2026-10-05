import { test, expect } from '../helpers/test.js'
import { backendUrl, authenticate, openWorkspace, submitDecision } from './helpers.js'
import { PANEL_VIEWPORTS } from '../../config/responsive.js'
import { batchForScenario } from '../responsive/catalog-scenarios.js'
import { waitForNuxtApp } from '../helpers/navigation.js'

const responsiveScenario = 'frontend/pages/platform/projects/[id]/delivery.vue'

test.setTimeout(60_000)

function fixtureKey(testInfo) {
  return `closure-${testInfo.title.replace(/[^a-z0-9]/gi, '-').slice(0, 90)}`
}

async function closureFixture(request, testInfo, mode) {
  const key = fixtureKey(testInfo)
  const response = await request.post(`${backendUrl}/__delivery_fixture__`, {
    data: { key, ...(mode ? { mode } : {}) },
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function closureProbe(request, testInfo) {
  const response = await request.post(`${backendUrl}/__delivery_fixture_probe__`, {
    data: { key: fixtureKey(testInfo) },
  })
  expect(response.ok()).toBeTruthy()
  return response.json()
}

async function openClosureEmail(page, data) {
  await page.getByTestId(`delivery-closure-email-open-${data.stage_id}`).click()
  await expect(page.getByTestId('delivery-closure-email')).toContainText('Prepara el correo y revisa su contenido exacto.')
}

async function enterPortalAndOpenWorkspace(page, request, data) {
  await authenticate(page, request, data, 'admin')
  await page.goto('/es-co', { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  const landingNav = page.getByLabel(page.viewportSize()?.width < 1024 ? 'Mobile navigation' : 'Main navigation')
  const entryLink = landingNav.getByRole('link', { name: 'Iniciar Sesión' })
  await expect(entryLink).toHaveAttribute('href', '/es-co/platform')
  await entryLink.click()
  await waitForNuxtApp(page)
  if (page.viewportSize()?.width < 768) await page.getByRole('button', { name: 'Abrir navegación' }).click()
  await page.getByRole('link', { name: 'Proyectos', exact: true }).click()
  await expect(page).toHaveURL(/\/platform\/projects\/?$/)
  const project = page.getByTestId(`project-row-${data.project.id}`).or(page.getByTestId(`project-card-${data.project.id}`))
  await expect(project).toContainText(data.project.name)
  await project.click()
  await page.getByRole('link', { name: 'Entregas', exact: true }).click()
  await expect(page.getByTestId(`delivery-stage-${data.stage_id}`)).toBeVisible()
}

async function prepareReviewedEmail(page, data, message) {
  await openClosureEmail(page, data)
  await page.getByTestId('delivery-closure-message').fill(message)
  await page.getByTestId('delivery-closure-prepare').click()
  await expect(page.getByTestId('delivery-closure-preview')).toContainText(message)
  await expect(page.getByTestId('delivery-closure-not-sent')).toHaveText('El correo está preparado. Todavía no se ha enviado.')
  await page.getByTestId('delivery-closure-reviewed').getByRole('checkbox').check()
}

for (const [viewport, dimensions] of Object.entries(PANEL_VIEWPORTS)) {
  test(`admin opens the closure preview at ${viewport} width through the approved stage`, {
    tag: ['@flow:platform-delivery-closure-email', '@module:platform', '@priority:P1', '@role:platform-admin', '@outcome:display', '@responsive:clients', `@responsive-scenario:${responsiveScenario}`, `@responsive-batch:${batchForScenario(responsiveScenario)}`, `@viewport:${viewport}`],
  }, async ({ page, request }, testInfo) => {
    // Catches a regression where the approved-stage email modal clips its preview, recipient, or action at this viewport.
    const data = await closureFixture(request, testInfo, 'closure-approved')
    await page.setViewportSize(dimensions)
    await enterPortalAndOpenWorkspace(page, request, data)
    await openClosureEmail(page, data)
    await page.getByTestId('delivery-closure-message').fill('Vista previa legible en el portal.')
    await page.getByTestId('delivery-closure-prepare').click()

    await expect(page.getByTestId(`delivery-stage-${data.stage_id}`)).toContainText('Aprobado')
    await expect(page.getByTestId('delivery-closure-to')).toHaveText(data.client.email)
    await expect(page.getByTestId('delivery-closure-send')).toHaveText('Enviar correo')
    await expect(page.getByTestId('delivery-closure-not-sent')).toHaveText('El correo está preparado. Todavía no se ha enviado.')
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(1)
    const probe = await closureProbe(request, testInfo)
    expect(probe.outbox_count).toBe(0)
    expect(probe.emails).toHaveLength(1)
  })
}

test('admin sends exactly one reviewed closure email', {
  tag: ['@flow:platform-delivery-closure-email', '@module:platform', '@priority:P1', '@role:platform-admin', '@outcome:success'],
}, async ({ page, request }, testInfo) => {
  // Catches a regression where a preview sends early, a double click duplicates delivery, or a resend skips a new reviewed preview.
  const data = await closureFixture(request, testInfo, 'closure-approved')
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await prepareReviewedEmail(page, data, 'Gracias por validar la etapa con los datos acordados.')

  let probe = await closureProbe(request, testInfo)
  expect(probe.outbox_count).toBe(0)
  expect(probe.emails).toHaveLength(1)
  expect(probe.emails[0].status).toBe('prepared')

  await page.getByTestId('delivery-closure-send').dblclick()
  await expect(page.getByTestId('delivery-closure-status')).toHaveText('Enviado')
  await expect(page.getByTestId('delivery-closure-attempts')).toContainText('Enviado')

  probe = await closureProbe(request, testInfo)
  expect(probe.outbox_count).toBe(1)
  expect(probe.emails).toHaveLength(1)
  expect(probe.emails[0]).toMatchObject({ status: 'sent', attempt_count: 1, to: [data.client.email] })

  await page.getByTestId('delivery-closure-resend-current').click()
  await expect(page.getByTestId('delivery-closure-status')).toHaveText('Preparado, sin enviar')
  await expect(page.getByTestId('delivery-closure-not-sent')).toHaveText('El correo está preparado. Todavía no se ha enviado.')

  probe = await closureProbe(request, testInfo)
  expect(probe.outbox_count).toBe(1)
  expect(probe.emails).toHaveLength(2)
  expect(probe.emails[0]).toMatchObject({ status: 'prepared' })
  expect(probe.emails[0].resend_of_id).toBe(probe.emails[1].id)
})

test('closure email action stays restricted to fully approved administrator stages', {
  tag: ['@flow:platform-delivery-closure-email', '@module:platform', '@priority:P1', '@role:platform-admin', '@outcome:error'],
}, async ({ page, request, browser }, testInfo) => {
  // Catches a regression where a client or a partially approved stage can start a contractual closure email.
  const data = await closureFixture(request, testInfo)
  await authenticate(page, request, data)
  await openWorkspace(page, data)
  await expect(page.getByTestId(`delivery-closure-email-open-${data.stage_id}`)).toHaveCount(0)
  await submitDecision(page, data, 0, 'approved', 'El traslado quedó conforme.')

  const adminContext = await browser.newContext()
  const adminPage = await adminContext.newPage()
  await authenticate(adminPage, request, data, 'admin')
  await openWorkspace(adminPage, data)
  await expect(adminPage.getByTestId(`delivery-stage-${data.stage_id}`)).toContainText('En revisión')
  await expect(adminPage.getByTestId(`delivery-closure-email-open-${data.stage_id}`)).toHaveCount(0)
  await adminContext.close()
})

test('admin sees a retained closure delivery failure', {
  tag: ['@flow:platform-delivery-closure-email', '@module:platform', '@priority:P1', '@role:platform-admin', '@outcome:failure'],
}, async ({ page, request }, testInfo) => {
  // Catches a regression where a failed SMTP send is presented as delivered or silently sends a duplicate on retry.
  const data = await closureFixture(request, testInfo, 'closure-smtp-failure')
  await authenticate(page, request, data, 'admin')
  await openWorkspace(page, data)
  await prepareReviewedEmail(page, data, 'Esta constancia debe quedar registrada como intento fallido.')
  await page.getByTestId('delivery-closure-send').click()

  await expect(page.getByTestId('delivery-closure-status')).toHaveText('Envío fallido')
  await expect(page.getByTestId('delivery-closure-preview').getByRole('alert')).toContainText('No se pudo completar el envío de correo.')
  const probe = await closureProbe(request, testInfo)
  expect(probe.outbox_count).toBe(0)
  expect(probe.emails).toHaveLength(1)
  expect(probe.emails[0]).toMatchObject({ status: 'failed', attempt_count: 1, error_message: 'No se pudo completar el envío de correo.' })
})
