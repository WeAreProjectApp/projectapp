import { test, expect } from '../helpers/test.js'
import { apiPost, backendUrl, fixture, login, open, openFromDelivery } from './helpers.js'
import { selectChoiceOption } from '../helpers/choice-select.js'

async function mailboxCount(request) {
  const response = await request.get(`${backendUrl}/__issues_mailbox__`)
  expect(response.ok()).toBeTruthy()
  const mailbox = await response.json()
  expect(mailbox.backend).toBe('locmem')
  expect(mailbox.aliases.length).toBeGreaterThan(0)
  return mailbox.count
}

async function prepareReviewedGeneralReply(page) {
  const reply = page.getByTestId('issue-contract-reply')
  await reply.getByText('Preparar respuesta con fuentes', { exact: true }).click()
  await expect(reply).toContainText('Sin contrato seleccionado')
  await reply.getByRole('button', { name: 'Preparar contexto y prompt', exact: true }).click()
  await expect(reply.getByTestId('issue-reply-json')).toHaveValue(/"context_id"/)
  await reply.getByRole('button', { name: 'Verificar borrador y citas', exact: true }).click()
  await expect(reply).toContainText('Alcance indeterminado')
  await reply.getByTestId('issue-reply-human-reviewed').getByRole('checkbox').check()
  return reply
}

async function chooseIssueSource(page, title) {
  await page.getByTestId('issue-source').click()
  await page.getByRole('option', { name: new RegExp(`^${title} ·`) }).click()
}

test.describe('Tickets reales de proyecto', () => {
  test.setTimeout(60_000)

  test('cliente reporta bug general sin guías', { tag: ['@flow:platform-bug-reports', '@outcome:success'] }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    await open(page, request, data, data.general_project.id)
    await page.getByRole('button', { name: 'Reportar bug', exact: true }).click()
    await expect(page.getByTestId('issue-source-selection')).toHaveCount(0)
    await page.getByPlaceholder('¿Qué está fallando?').fill('La pantalla general no responde')
    const submitted = page.waitForResponse((response) => response.url().endsWith('/bug-reports/') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Reportar bug', exact: true }).last().click()
    const response = await submitted
    expect(response.status()).toBe(201)
    expect((await response.json()).origin_context.origin_kind).toBe('general')
    await expect(page.getByText('La pantalla general no responde', { exact: true })).toBeVisible()
  })

  test('entrega autocompleta la guía original', { tag: ['@flow:platform-bug-reports', '@outcome:success'] }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    await openFromDelivery(page, request, data, data.project.id, `?from_req=${data.requirement_ids[0]}&from_pub=${data.publication_id}`)
    await expect(page.getByTestId('issue-source')).toContainText('Traslado entre sucursales')
    await expect(page.getByTestId('issue-source-title')).toHaveText('Traslado entre sucursales')
    await expect(page.getByPlaceholder('Paso 1')).toHaveValue('Abrir el registro preparado.')
    await page.getByPlaceholder('¿Qué está fallando?').fill('Falla el traslado')
    const submitted = page.waitForResponse((response) => response.url().endsWith('/bug-reports/') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Reportar bug', exact: true }).last().click()
    const ticket = await (await submitted).json()
    expect(ticket.origin_context.publication_id).toBe(data.publication_id)
    expect(ticket.origin_context.contract_id).toBe(data.contract_id)
    expect(ticket.origin_context.requirement_id).toBe(data.requirement_ids[0])
    await page.getByText('Falla el traslado', { exact: true }).click()
    await expect(page.getByTestId('issue-history')).toContainText('Ronda 1')
  })

  test('cliente reabre conservando la respuesta del equipo', { tag: ['@flow:platform-bug-reports', '@outcome:success'] }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const admin = await login(request, data.admin)
    const ticket = await apiPost(request, admin, `projects/${data.general_project.id}/bug-reports/`, { title: 'Falla persistente' })
    await apiPost(request, admin, `projects/${data.general_project.id}/bug-reports/${ticket.id}/evaluate/`, { status: 'resolved', admin_response: 'Corregimos el botón.' })
    await open(page, request, data, data.general_project.id)
    await page.getByText('Falla persistente', { exact: true }).click()
    await page.getByLabel('Qué sigue fallando').fill('Sigue fallando en Safari.')
    await page.getByRole('button', { name: 'Responder y reabrir', exact: true }).click()
    await expect(page.getByTestId('issue-reopen')).toHaveCount(0)
    await expect(page.getByTestId('issue-history')).toContainText('Corregimos el botón.')
    await expect(page.getByTestId('issue-history')).toContainText('El cliente indica que sigue fallando')
    await expect(page.getByText('Sigue fallando en Safari.', { exact: true })).toBeVisible()
  })

  test('reapertura exige explicación', { tag: ['@flow:platform-bug-reports', '@outcome:error'] }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const admin = await login(request, data.admin)
    const ticket = await apiPost(request, admin, `projects/${data.general_project.id}/bug-reports/`, { title: 'Falla para explicar' })
    await apiPost(request, admin, `projects/${data.general_project.id}/bug-reports/${ticket.id}/evaluate/`, { status: 'resolved' })
    await open(page, request, data, data.general_project.id)
    await page.getByText('Falla para explicar', { exact: true }).click()
    await expect(page.getByRole('button', { name: 'Responder y reabrir' })).toBeDisabled()
    await page.getByLabel('Qué sigue fallando').fill('   ')
    await expect(page.getByRole('button', { name: 'Responder y reabrir' })).toBeDisabled()
  })

  // Catches the regression that exposed an internal team response in the client's ticket history.
  test('cliente no ve la respuesta interna del equipo', { tag: ['@flow:platform-bug-reports', '@outcome:display'] }, async ({ page, request }, testInfo) => {
    // quality: allow-deep-link (the authenticated project list is the documented entry; project, Bugs and ticket are opened through UI)
    const data = await fixture(request, testInfo)
    const admin = await login(request, data.admin)
    const secret = 'Nota interna: revisar el registro privado antes de responder.'
    const ticket = await apiPost(request, admin, `projects/${data.general_project.id}/bug-reports/`, { title: 'Error con nota interna' })
    await apiPost(request, admin, `projects/${data.general_project.id}/bug-reports/${ticket.id}/evaluate/`, {
      status: 'resolved', admin_response: secret, is_internal: true,
    })

    await open(page, request, data, data.general_project.id)
    await page.getByRole('button', { name: 'Error con nota interna', exact: true }).press('Enter')
    await expect(page.getByTestId('issue-history')).toContainText('Resuelto por equipo')
    await expect(page.getByTestId('issue-history')).not.toContainText(secret)
  })

  // Catches the regression that hid an evaluation failure and removed the team's retry form.
  test('error del servidor al evaluar un bug conserva el formulario', { tag: ['@flow:platform-bug-reports', '@outcome:failure'] }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const admin = await login(request, data.admin)
    const ticket = await apiPost(request, admin, `projects/${data.general_project.id}/bug-reports/`, { title: 'Bug con evaluación temporalmente caída' })

    await open(page, request, data, data.general_project.id, 'bugs', '', 'admin')
    await page.getByText(ticket.title, { exact: true }).click()
    await page.getByRole('button', { name: 'Evaluar', exact: true }).click()
    await page.route(`**/api/accounts/projects/${data.general_project.id}/bug-reports/${ticket.id}/evaluate/`, (route) => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Servicio temporalmente no disponible.' }),
    }))
    await page.getByRole('button', { name: 'Guardar', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('Servicio temporalmente no disponible.')
    await expect(page.getByRole('button', { name: 'Guardar', exact: true })).toBeVisible()
  })

  // Catches the regression that preserved a request's origin only in its create response, not its detail UI.
  test('solicitud conserva el contexto de la entrega', { tag: ['@flow:platform-change-requests', '@outcome:success', '@outcome:display'] }, async ({ page, request }, testInfo) => {
    // quality: allow-deep-link (the authenticated project list is the documented entry; project, Solicitudes and ticket are opened through UI)
    const data = await fixture(request, testInfo)
    await open(page, request, data, data.project.id, 'changes')
    await page.getByRole('button', { name: 'Nueva solicitud', exact: true }).click()
    await chooseIssueSource(page, 'Traslado entre sucursales')
    await page.getByPlaceholder('¿Qué cambio necesitas?').fill('Ampliar el traslado')
    const priority = page.getByRole('combobox', { name: 'Prioridad sugerida' })
    await expect(priority).toHaveText('Media')
    await selectChoiceOption(page, priority, 'Alta')
    const posts = []
    page.on('request', (sent) => {
      if (sent.method() === 'POST' && sent.url().endsWith('/change-requests/')) posts.push(sent)
    })
    const submitted = page.waitForResponse((response) => response.url().endsWith('/change-requests/') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Crear solicitud', exact: true }).click()
    const response = await submitted
    expect(response.status()).toBe(201)
    const ticket = await response.json()
    expect(ticket.origin_context.publication_id).toBe(data.publication_id)
    expect(ticket.origin_context.requirement_id).toBe(data.requirement_ids[0])
    expect(ticket.suggested_priority).toBe('high')
    await page.reload({ waitUntil: 'domcontentloaded' })
    const row = page.getByRole('row').filter({ hasText: 'Ampliar el traslado' })
    await expect(row.getByText('Alta', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Ampliar el traslado', exact: true }).press('Enter')
    await expect(page.getByTestId('issue-history')).toContainText('Ronda 1')
    await expect(page.getByText('Alta', { exact: true }).last()).toBeVisible()
    expect(posts).toHaveLength(1)
  })

  for (const scenario of [
    {
      name: 'título sin entrega',
      arrange: page => page.getByPlaceholder('¿Qué cambio necesitas?').fill('Ampliar el traslado'),
      error: 'Selecciona la entrega de origen.',
    },
    {
      name: 'entrega sin título',
      arrange: page => chooseIssueSource(page, 'Traslado entre sucursales'),
      error: 'Escribe el título de la solicitud.',
    },
  ]) {
    test(`solicitud con ${scenario.name} señala el dato faltante antes del POST`, {
      tag: ['@flow:platform-change-requests', '@outcome:error'],
    }, async ({ page, request }, testInfo) => {
      const data = await fixture(request, testInfo)
      await open(page, request, data, data.project.id, 'changes')
      await page.getByRole('button', { name: 'Nueva solicitud', exact: true }).click()
      await scenario.arrange(page)
      const posts = []
      page.on('request', (sent) => {
        if (sent.method() === 'POST' && sent.url().endsWith('/change-requests/')) posts.push(sent)
      })

      await page.getByRole('button', { name: 'Crear solicitud', exact: true }).click()

      await expect(page.getByRole('alert', { name: '' }).filter({ hasText: scenario.error })).toBeVisible()
      expect(posts).toHaveLength(0)
    })
  }

  test('equipo aplica el estado rápido desde la fila de solicitud', {
    tag: ['@flow:platform-change-requests', '@outcome:success'],
  }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const client = await login(request, data.client)
    const ticket = await apiPost(request, client, `projects/${data.project.id}/change-requests/`, {
      title: 'Cambio rápido de estado', source_requirement_id: data.requirement_ids[0],
    })
    await open(page, request, data, data.project.id, 'changes', '', 'admin')
    const row = page.getByRole('row').filter({ hasText: ticket.title })
    const status = row.getByRole('combobox', { name: 'Estado rápido' })

    await selectChoiceOption(page, status, 'En evaluación')

    await expect(status).toHaveText('En evaluación')
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(status).toHaveText('En evaluación')
  })

  test('equipo guarda la evaluación con el contrato elegido', {
    tag: ['@flow:platform-change-requests', '@outcome:success'],
  }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const client = await login(request, data.client)
    const ticket = await apiPost(request, client, `projects/${data.project.id}/change-requests/`, {
      title: 'Evaluación con contrato', source_requirement_id: data.requirement_ids[0],
    })
    await open(page, request, data, data.project.id, 'changes', '', 'admin')
    await page.getByText(ticket.title, { exact: true }).click()
    await page.getByRole('button', { name: 'Evaluar', exact: true }).click()
    const contract = page.getByRole('combobox', { name: 'Contrato aplicable' })
    await selectChoiceOption(page, contract, 'Sin contrato seleccionado')
    await selectChoiceOption(page, contract, `Contrato ${data.fixture_key}`)
    await selectChoiceOption(page, page.getByRole('combobox', { name: 'Estado', exact: true }), 'En evaluación')
    const saved = page.waitForResponse(response => response.url().endsWith(`/change-requests/${ticket.id}/evaluate/`) && response.request().method() === 'POST')

    await page.getByRole('button', { name: 'Guardar evaluación', exact: true }).click()

    const response = await saved
    expect(response.status()).toBe(200)
    expect(response.request().postDataJSON()).toMatchObject({ contract_id: data.contract_id, status: 'evaluating' })
    await expect(contract).toHaveCount(0)
  })

  test('equipo convierte la solicitud en el borrador elegido', {
    tag: ['@flow:platform-change-requests', '@outcome:success'],
  }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const client = await login(request, data.client)
    const admin = await login(request, data.admin)
    const ticket = await apiPost(request, client, `projects/${data.project.id}/change-requests/`, {
      title: 'Solicitud para convertir', source_requirement_id: data.requirement_ids[0],
    })
    await apiPost(request, admin, `projects/${data.project.id}/change-requests/${ticket.id}/evaluate/`, {
      status: 'approved', expected_version: ticket.version,
    })
    await open(page, request, data, data.project.id, 'changes', '', 'admin')
    await page.getByText(ticket.title, { exact: true }).click()
    const convert = page.getByRole('button', { name: 'Preparar como requerimiento', exact: true })
    await convert.click()
    const dialog = page.getByRole('dialog')
    await selectChoiceOption(page, dialog.getByRole('combobox', { name: /etapa de destino en borrador/i }), 'Borrador privado del equipo')
    const saved = page.waitForResponse(response => response.url().endsWith(`/change-requests/${ticket.id}/convert/`) && response.request().method() === 'POST')

    await dialog.getByRole('button', { name: 'Preparar como requerimiento', exact: true }).click()

    const response = await saved
    const converted = await response.json()
    expect(response.status()).toBe(201)
    expect(response.request().postDataJSON().stage_id).toBe(data.hidden_stage_id)
    await expect(page.getByText(`Convertida en requerimiento #${converted.linked_requirement_id}`)).toBeVisible()
  })

  // Catches the regression that made a stale evaluation look as if the team's response had been applied.
  test('evaluación desactualizada de solicitud muestra el conflicto', { tag: ['@flow:platform-change-requests', '@outcome:error'] }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const client = await login(request, data.client)
    const ticket = await apiPost(request, client, `projects/${data.project.id}/change-requests/`, {
      title: 'Solicitud que cambia mientras se evalúa',
      source_requirement_id: data.requirement_ids[0],
    })
    const admin = await login(request, data.admin)

    await open(page, request, data, data.project.id, 'changes', '', 'admin')
    await page.getByText(ticket.title, { exact: true }).click()
    await page.getByRole('button', { name: 'Evaluar', exact: true }).click()
    await apiPost(request, admin, `projects/${data.project.id}/change-requests/${ticket.id}/evaluate/`, {
      status: 'evaluating', expected_version: ticket.version,
    })
    await page.getByRole('button', { name: 'Guardar evaluación', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('El ticket cambió. Actualiza antes de responder.')
  })

  // Catches the regression that hid a failed change-request evaluation and removed the retry form.
  test('error del servidor al evaluar una solicitud conserva el formulario', { tag: ['@flow:platform-change-requests', '@outcome:failure'] }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const client = await login(request, data.client)
    const ticket = await apiPost(request, client, `projects/${data.project.id}/change-requests/`, {
      title: 'Solicitud con evaluación temporalmente caída',
      source_requirement_id: data.requirement_ids[0],
    })

    await open(page, request, data, data.project.id, 'changes', '', 'admin')
    await page.getByText(ticket.title, { exact: true }).click()
    await page.getByRole('button', { name: 'Evaluar', exact: true }).click()
    await page.route(`**/api/accounts/projects/${data.project.id}/change-requests/${ticket.id}/evaluate/`, (route) => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Servicio temporalmente no disponible.' }),
    }))
    await page.getByRole('button', { name: 'Guardar evaluación', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('Servicio temporalmente no disponible.')
    await expect(page.getByRole('button', { name: 'Guardar evaluación', exact: true })).toBeVisible()
  })

  // Catches the regression that treated a general bug as contractual or exposed private review provenance to the client.
  test('revisión humana de bug general publica sólo alcance indeterminado', { tag: ['@flow:platform-bug-reports', '@outcome:success'] }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const admin = await login(request, data.admin)
    const ticket = await apiPost(request, admin, `projects/${data.general_project.id}/bug-reports/`, {
      title: 'Bug general revisado con fuentes',
    })
    const initialMailboxCount = await mailboxCount(request)

    await open(page, request, data, data.general_project.id, 'bugs', '', 'admin')
    await page.getByRole('button', { name: ticket.title, exact: true }).press('Enter')
    await page.getByRole('button', { name: 'Evaluar', exact: true }).click()
    await prepareReviewedGeneralReply(page)
    await page.getByRole('button', { name: 'Guardar', exact: true }).click()

    await open(page, request, data, data.general_project.id)
    await page.getByRole('button', { name: ticket.title, exact: true }).press('Enter')
    const evidence = page.getByTestId('issue-review-evidence')
    await expect(evidence).toContainText('Alcance indeterminado')
    await expect(evidence).not.toContainText('context_id')
    await expect(evidence).not.toContainText('source_references')
    await expect(evidence).not.toContainText('prompt')
    await expect(evidence).not.toContainText('private')
    expect(await mailboxCount(request)).toBe(initialMailboxCount)
  })

  // Catches the regression that accepted a reviewed reply after another admin had changed the ticket.
  test('publicación contractual rechaza la revisión cuando cambió el ticket', { tag: ['@flow:platform-bug-reports', '@outcome:error'] }, async ({ page, request }, testInfo) => {
    const data = await fixture(request, testInfo)
    const admin = await login(request, data.admin)
    const ticket = await apiPost(request, admin, `projects/${data.general_project.id}/bug-reports/`, {
      title: 'Bug general con versión vencida',
    })
    const initialMailboxCount = await mailboxCount(request)

    await open(page, request, data, data.general_project.id, 'bugs', '', 'admin')
    await page.getByRole('button', { name: ticket.title, exact: true }).press('Enter')
    await page.getByRole('button', { name: 'Evaluar', exact: true }).click()
    await prepareReviewedGeneralReply(page)

    const concurrentAdmin = await login(request, data.admin)
    await apiPost(request, concurrentAdmin, `projects/${data.general_project.id}/bug-reports/${ticket.id}/evaluate/`, {
      status: 'confirmed', expected_version: ticket.version,
    })
    const rejected = page.waitForResponse((response) => (
      response.url().endsWith(`/bug-reports/${ticket.id}/evaluate/`) && response.request().method() === 'POST'
    ))
    await page.getByRole('button', { name: 'Guardar', exact: true }).click()
    expect((await rejected).status()).toBe(409)
    await expect(page.getByText('El ticket cambió. Actualiza antes de responder.', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Guardar', exact: true })).toBeVisible()

    const detail = await request.get(`${backendUrl}/api/accounts/projects/${data.general_project.id}/bug-reports/${ticket.id}/`, {
      headers: { Authorization: `Bearer ${concurrentAdmin.tokens.access}` },
    })
    expect(detail.ok()).toBeTruthy()
    expect((await detail.json()).responses).toHaveLength(0)
    expect(await mailboxCount(request)).toBe(initialMailboxCount)
  })
})
