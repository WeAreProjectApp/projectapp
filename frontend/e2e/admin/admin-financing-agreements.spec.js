import { test, expect } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import {
  financingAgreementFixture,
  financingAgreementTemplateFixture,
  financingClientContextFixture,
  financingClientFixture,
  financingSettingsFixture,
} from '../helpers/financing-agreement-fixture.js'
import { financingProgramFixture } from '../helpers/financing-fixture.js'
import {
  ADMIN_FINANCING_AGREEMENT_CREATE,
  ADMIN_FINANCING_AGREEMENT_LIFECYCLE,
  ADMIN_FINANCING_AGREEMENT_SECOND_CYCLE,
} from '../helpers/flow-tags.js'


function json(status, body) {
  return { status, contentType: 'application/json', body: JSON.stringify(body) }
}

function agreementEnvelope(rows) {
  return {
    count: rows.length,
    limit: 25,
    offset: 0,
    results: rows,
    stats: {
      total_active_records: rows.filter((row) => !row.is_archived).length,
      archived: rows.filter((row) => row.is_archived).length,
      by_status: rows.reduce((result, row) => ({
        ...result,
        [row.status]: (result[row.status] || 0) + 1,
      }), {}),
    },
  }
}

function transitionAgreement(scenario, status, overrides = {}) {
  const current = scenario.agreement
  scenario.agreement = financingAgreementFixture({
    id: current.id,
    uuid: current.uuid,
    client: current.client,
    client_full_name: current.client_full_name,
    client_company: current.client_company,
    client_id_type: current.client_id_type,
    client_id_number: current.client_id_number,
    client_email: current.client_email,
    client_phone: current.client_phone,
    project_name: current.project_name,
    financed_scope: current.financed_scope,
    modality: current.modality,
    modality_label: current.modality_label,
    cycle_number: current.cycle_number,
    previous_agreement: current.previous_agreement,
    previous_agreement_number: current.previous_agreement_number,
    partnership_start_date: current.partnership_start_date,
    partnership_end_date: current.partnership_end_date,
    ...overrides,
    status,
  })
  return scenario.agreement
}

function scheduleFromFirstInstallment(firstInstallmentDate, financedBalance, count = 12) {
  const firstDueDate = new Date(`${firstInstallmentDate}T12:00:00Z`)
  const monthlyAmount = Math.floor((financedBalance * 100) / count) / 100

  return Array.from({ length: count }, (_, index) => {
    const dueDate = new Date(firstDueDate)
    dueDate.setUTCMonth(dueDate.getUTCMonth() + index)
    const amount = index === count - 1
      ? financedBalance - (monthlyAmount * (count - 1))
      : monthlyAmount

    return {
      number: index + 1,
      due_date: dueDate.toISOString().slice(0, 10),
      amount: amount.toFixed(2),
    }
  })
}

function agreementFromCreatePayload(payload) {
  const totalValue = Number(payload.total_value)
  const initialPayment = Number(payload.initial_payment || 0)
  const financedBalance = totalValue - initialPayment
  const installmentSchedule = payload.installment_schedule || scheduleFromFirstInstallment(
    payload.first_installment_date,
    financedBalance,
  )

  return financingAgreementFixture({
    id: 501,
    status: 'draft',
    client: payload.client_id,
    client_full_name: payload.client_full_name,
    client_company: payload.client_company,
    client_id_type: payload.client_id_type,
    client_id_number: payload.client_id_number,
    client_email: payload.client_email,
    client_phone: payload.client_phone,
    source_proposal: payload.source_proposal_id,
    source_project: payload.source_project_id,
    original_contract_reference: payload.original_contract_reference,
    original_contract_date: payload.original_contract_date,
    project_name: payload.project_name,
    financed_scope: payload.financed_scope,
    modality: payload.modality,
    modality_label: payload.modality === 'three_year' ? 'Alianza a 3 años' : 'Alianza a 5 años',
    partnership_start_date: payload.partnership_start_date,
    currency: payload.currency,
    total_value: totalValue.toFixed(2),
    initial_payment: initialPayment.toFixed(2),
    financed_balance: financedBalance.toFixed(2),
    hosting_value: Number(payload.hosting_value).toFixed(2),
    hosting_period: payload.hosting_period,
    template: financingAgreementTemplateFixture,
    template_name: financingAgreementTemplateFixture.name,
    template_version: financingAgreementTemplateFixture.version,
    contract_markdown: payload.contract_markdown,
    installment_schedule: installmentSchedule,
  })
}

async function setupApi(page, scenario = {}) {
  scenario.agreement ??= financingAgreementFixture()
  scenario.createdPayload = null
  scenario.actionPayload = null
  scenario.settings ??= financingSettingsFixture()

  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json(200, { user: { username: 'admin', is_staff: true } })
    if (apiPath === 'proposals/' && method === 'GET') return json(200, [])
    if (apiPath === 'proposals/dashboard/') return json(200, { total: 0, by_status: {} })
    if (apiPath === 'proposals/alerts/') return json(200, [])
    if (apiPath === 'financing/public/' && method === 'GET') {
      return json(200, financingProgramFixture('es'))
    }
    if (apiPath === 'financing/settings/' && method === 'GET') {
      return json(200, scenario.settings)
    }
    if (apiPath === 'financing/agreements/templates/' && method === 'GET') {
      return json(200, {
        results: [financingAgreementTemplateFixture],
        known_placeholders: ['agreement_number', 'client_full_name'],
      })
    }
    if (apiPath === 'proposals/client-profiles/search/' && method === 'GET') {
      return json(200, scenario.clientSearchEmpty ? [] : [financingClientFixture])
    }
    if (apiPath === 'financing/agreements/client-context/' && method === 'GET') {
      return json(200, financingClientContextFixture())
    }
    if (apiPath === 'proposals/client-profiles/create/' && method === 'POST') {
      return json(201, financingClientFixture)
    }
    if (apiPath === 'financing/agreements/' && method === 'GET') {
      if (scenario.listUnavailable) return json(503, { detail: 'Servicio no disponible.' })
      const params = new URL(route.request().url()).searchParams
      const rows = scenario.filterRows?.(params) ?? scenario.rows ?? [scenario.agreement]
      return json(200, agreementEnvelope(rows))
    }
    if (apiPath === 'financing/agreements/' && method === 'POST') {
      scenario.createdPayload = route.request().postDataJSON()
      if (scenario.createError) {
        return json(400, {
          project_name: ['Indica el proyecto o producto.'],
          code: 'invalid_financing_agreement',
        })
      }
      scenario.agreement = agreementFromCreatePayload(scenario.createdPayload)
      return json(201, scenario.agreement)
    }

    const draftPdfMatch = apiPath.match(/^financing\/agreements\/(\d+)\/draft-pdf\/$/)
    if (draftPdfMatch && method === 'GET') {
      return {
        status: 200,
        contentType: 'application/pdf',
        headers: {
          'Content-Disposition': 'attachment; filename="Borrador_Otrosi_Financiacion_OFIN-2026-001_ana-semilla.pdf"',
        },
        body: '%PDF-1.4 populated financing draft',
      }
    }

    const actionMatch = apiPath.match(
      /^financing\/agreements\/(\d+)\/(mark-ready|reopen|upload-signed|complete|cancel|archive|restore|create-second-cycle|apply-current-policy)\/$/,
    )
    if (actionMatch && method === 'POST') {
      const action = actionMatch[2]
      if (scenario.actionFailure?.action === action) {
        return json(scenario.actionFailure.status, {
          detail: scenario.actionFailure.detail,
          code: scenario.actionFailure.code || 'operation_failed',
        })
      }
      if (!['upload-signed', 'mark-ready', 'reopen', 'archive', 'restore', 'create-second-cycle'].includes(action)) {
        scenario.actionPayload = route.request().postDataJSON()
      }
      if (action === 'mark-ready') {
        return json(200, transitionAgreement(scenario, 'ready', {
          number: 'OFIN-2026-042',
          resolved_contract_markdown: '# OTROSÍ OFIN-2026-042\n\nAna Semilla',
          resolved_contract_sha256: 'f'.repeat(64),
          template_name: 'Otrosí de financiación',
          template_version: 2,
        }))
      }
      if (action === 'reopen') return json(200, transitionAgreement(scenario, 'draft', { number: 'OFIN-2026-001' }))
      if (action === 'upload-signed') {
        scenario.uploadContentType = route.request().headers()['content-type']
        return json(200, transitionAgreement(scenario, 'active'))
      }
      if (action === 'complete') return json(200, transitionAgreement(scenario, 'completed'))
      if (action === 'cancel') return json(200, transitionAgreement(scenario, 'cancelled'))
      if (action === 'archive') {
        return json(200, transitionAgreement(scenario, scenario.agreement.status, {
          is_archived: true,
          archived_at: '2026-09-02T15:00:00Z',
        }))
      }
      if (action === 'restore') {
        return json(200, transitionAgreement(scenario, scenario.agreement.status, {
          is_archived: false,
          archived_at: null,
        }))
      }
      if (action === 'apply-current-policy') {
        scenario.agreement = financingAgreementFixture({
          ...scenario.agreement,
          policy_revision: scenario.settings.current.id,
          policy_version: scenario.settings.current.version,
          policy: scenario.settings.current,
          installment_schedule: scheduleFromFirstInstallment(
            scenario.agreement.installment_schedule[0].due_date,
            Number(scenario.agreement.financed_balance),
            scenario.settings.current.financing_months,
          ),
          allowed_actions: ['edit', 'download_draft', 'mark_ready', 'cancel'],
        })
        return json(200, scenario.agreement)
      }
      scenario.agreement = financingAgreementFixture({
        id: 502,
        uuid: 'e7ef10d9-3de8-40ff-906a-a0cf06d9142f',
        number: null,
        status: 'draft',
        cycle_number: 2,
        previous_agreement: 501,
        previous_agreement_number: 'OFIN-2026-001',
        financed_scope: '',
        total_value: '0.00',
        initial_payment: '0.00',
        financed_balance: '0.00',
        installment_schedule: [],
      })
      return json(201, scenario.agreement)
    }

    const detailMatch = apiPath.match(/^financing\/agreements\/(\d+)\/$/)
    if (detailMatch && method === 'GET') {
      if (scenario.detailUnavailable) return json(503, { detail: 'Servicio no disponible.' })
      return json(200, scenario.agreement)
    }
    return null
  })
}

async function openFinancingPanel(page) {
  await page.goto('/es-co/panel/proposals', { waitUntil: 'domcontentloaded' })
  await page.getByRole('link', { name: 'Programa de Alianza', exact: true }).click()
  await expect(page).toHaveURL(/\/es-co\/panel\/partnership-program$/)
}

async function openAgreementList(page) {
  await openFinancingPanel(page)
  await page.getByTestId('financing-tab-agreements').click()
  await expect(page).toHaveURL(/\/es-co\/panel\/partnership-program\?tab=agreements$/)
}

async function openAgreementDetail(page, id = 501) {
  await openAgreementList(page)
  await page.getByTestId(`financing-agreement-row-${id}`).click()
  await expect(page).toHaveURL(new RegExp(`/es-co/panel/partnership-program/${id}$`))
}

async function chooseFinancingClient(page) {
  await page.getByTestId('financing-agreement-client').fill('Semilla')
  await page.getByTestId(`client-autocomplete-option-${financingClientFixture.id}`).click()
  await expect(page.getByTestId('financing-client-legal-name')).toHaveValue(financingClientFixture.name)
}

async function fillRequiredAgreementFields(page) {
  await page.getByTestId('financing-original-contract').fill('Contrato de desarrollo PA-041')
  await page.getByTestId('financing-project-name').fill('Plataforma Semilla')
  await page.getByTestId('financing-scope').fill('Desarrollo e implementación de la fase comercial.')
  await page.getByTestId('financing-total-value').fill('25000000')
  await page.getByTestId('financing-initial-payment').fill('5000000')
  await page.getByTestId('financing-hosting-value').fill('500000')
}

async function runConfirmedAction(page, actionTestId) {
  await page.getByTestId(actionTestId).click()
  await expect(page.getByTestId('confirm-modal-confirm')).toBeVisible()
  await page.getByTestId('confirm-modal-confirm').click()
}

test.describe('Admin financing agreements', () => {
  test.setTimeout(60_000)

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-admin',
      userAuth: { id: 1, role: 'admin', is_staff: true },
    })
  })

  test('shows financing agreements in the management tab', {
    tag: [...ADMIN_FINANCING_AGREEMENT_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (authenticated panel setup has no public entry; the test then clicks the visible Financiación link and Otrosíes tab)
    const agreement = financingAgreementFixture({ status: 'active' })
    await setupApi(page, { agreement })
    await openAgreementList(page)

    await expect(page.getByTestId(`financing-agreement-row-${agreement.id}`)).toContainText('OFIN-2026-001')
    await expect(page.getByRole('table').getByText(agreement.client_full_name, { exact: true })).toBeVisible()
    await expect(page.getByTestId('financing-new-agreement')).toBeVisible()
  })

  test('applies named dropdown filters only when the form is submitted', {
    tag: [...ADMIN_FINANCING_AGREEMENT_CREATE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (the protected setup page leads to the visible Otrosíes tab)
    const draft = financingAgreementFixture({ id: 7, status: 'draft', project_name: 'Portal comercial 08-01' })
    const retired = financingAgreementFixture({ id: 6, status: 'cancelled', is_archived: true, project_name: 'Proyecto anterior' })
    const other = financingAgreementFixture({ id: 9, status: 'active', project_name: 'Portal de ventas' })
    const records = [draft, retired, other]
    await setupApi(page, {
      filterRows: (params) => records.filter((record) => (
        String(record.is_archived) === params.get('archived')
        && record.project_name.includes(params.get('q') || '')
      )),
    })
    await openAgreementList(page)

    const scope = page.getByRole('combobox', { name: 'Alcance', exact: true })
    await expect(page.getByRole('combobox', { name: 'Estado', exact: true })).toContainText('Todos los estados')
    await expect(page.getByRole('combobox', { name: 'Modalidad', exact: true })).toContainText('Todas las modalidades')
    await expect(scope).toContainText('Vigentes')

    const query = page.getByTestId('financing-agreement-search')
    const apply = page.getByRole('button', { name: 'Filtrar', exact: true })
    await query.fill(draft.project_name)
    await apply.click()
    await expect(page.getByTestId('financing-agreement-row-9')).toHaveCount(0)
    await expect(page.getByRole('row').filter({ hasText: draft.project_name })).toContainText('Borrador')

    await query.clear()
    await scope.click()
    await page.getByRole('option', { name: 'Archivados', exact: true }).click()
    await expect(page.getByTestId('financing-agreement-row-7')).toBeVisible()
    await apply.click()
    await expect(page.getByTestId('financing-agreement-row-7')).toHaveCount(0)
    await expect(page.getByRole('row').filter({ hasText: retired.project_name })).toContainText('Archivado')
    await expect(page.getByTestId('financing-agreement-row-6')).toBeVisible()
  })

  test('limits the conceptual exclusivity benefit to the five-year modality', {
    tag: [...ADMIN_FINANCING_AGREEMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page, { rows: [] })
    await openAgreementList(page)
    await page.getByTestId('financing-new-agreement').click()
    const benefits = page.getByTestId('financing-modality-benefits')

    await expect(benefits).toContainText('no reproduciremos para otros clientes conceptos, ideas o enfoques específicos')
    await expect(page.getByText('Para la exclusividad conceptual a cinco años', { exact: false })).toBeVisible()
    await page.getByTestId('financing-modality-three').click()

    await expect(benefits).toContainText('ni exclusividad conceptual a cargo de Project App.')
    await expect(benefits).not.toContainText('no reproduciremos')
    await expect(page.getByText('Para la exclusividad conceptual a cinco años', { exact: false })).toHaveCount(0)
    await page.getByTestId('financing-modality-five').click()
    await expect(benefits).toContainText('durante los cinco años no reproduciremos')
  })

  test('creates a populated draft from a selected client', {
    tag: [...ADMIN_FINANCING_AGREEMENT_CREATE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { rows: [] }
    await setupApi(page, scenario)
    await openAgreementList(page)
    await page.getByTestId('financing-new-agreement').click()
    await expect(page).toHaveURL(/\/es-co\/panel\/partnership-program\/new$/)
    await chooseFinancingClient(page)
    await fillRequiredAgreementFields(page)

    await page.getByTestId('financing-agreement-save').click()

    await expect(page).toHaveURL(/\/es-co\/panel\/partnership-program\/501$/)
    await expect(page.getByTestId('financing-installment-12')).toBeVisible()
    await expect(page.getByTestId('financing-late-payment-rule')).toContainText('aumenta 2%')
    expect(scenario.createdPayload.client_id).toBe(financingClientFixture.id)
    expect(scenario.createdPayload).toMatchObject({
      original_contract_reference: 'Contrato de desarrollo PA-041',
      project_name: 'Plataforma Semilla',
      financed_scope: 'Desarrollo e implementación de la fase comercial.',
      total_value: '25000000',
      initial_payment: '5000000',
      hosting_value: '500000',
    })
    expect(scenario.createdPayload.first_installment_date).toMatch(/-0?5$/)
    await expect(page.getByTestId('financing-installment-date-1'))
      .toHaveValue(scenario.createdPayload.first_installment_date)
    await expect(page.getByTestId('financing-installment-amount-12')).toHaveValue(/\d+\.\d{2}/)
  })

  test('keeps form values after validation rejection', {
    tag: [...ADMIN_FINANCING_AGREEMENT_CREATE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupApi(page, { createError: true })
    await page.goto('/es-co/panel/partnership-program/new', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('financing-original-contract').fill('Contrato que debe conservarse')

    await page.getByTestId('financing-agreement-save').click()

    await expect(page.getByRole('alert').first()).toContainText('No fue posible crear el borrador')
    await expect(page.getByTestId('financing-original-contract')).toHaveValue('Contrato que debe conservarse')
    await expect(page.getByText('Indica el proyecto o producto.')).toBeVisible()
  })

  test('shows a financing register failure', {
    tag: [...ADMIN_FINANCING_AGREEMENT_CREATE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // quality: allow-flow-tag-mismatch (this declared failure outcome is the register's initial-load failure; creation cannot start until the register resolves)
    await setupApi(page, { listUnavailable: true })
    await openAgreementList(page)

    await expect(page.getByRole('alert')).toContainText('No fue posible cargar los otrosíes')
    await expect(page.getByTestId('financing-agreements-empty')).toHaveCount(0)
  })

  test('shows the audit history for a locked agreement', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (authenticated panel setup has no public entry; the test reaches the record through the visible Financiación link, Otrosíes tab, and row)
    await setupApi(page, { agreement: financingAgreementFixture({ status: 'active' }) })
    await openAgreementDetail(page)

    await expect(page.getByRole('heading', { name: 'Historial auditable' })).toBeVisible()
    await expect(page.getByText('Admin Prueba')).toBeVisible()
    await expect(page.getByText('Calendario de 12 cuotas')).toBeVisible()
  })

  test('adopts the current policy in an older draft', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const settings = financingSettingsFixture({
      id: 3,
      version: 3,
      financing_months: 18,
    })
    const agreement = financingAgreementFixture({
      allowed_actions: [
        'edit', 'download_draft', 'mark_ready', 'cancel', 'apply_current_policy',
      ],
    })
    await setupApi(page, { agreement, settings })
    await openAgreementDetail(page)
    await expect(page.getByTestId('financing-agreement-policy')).toContainText(
      'la vigente es v3',
    )

    await runConfirmedAction(page, 'financing-apply-current-policy')

    await expect(page.getByTestId('financing-agreement-policy')).toContainText(
      'revisión v3',
    )
    await expect(page.getByTestId('financing-installment-18')).toBeVisible()
    await expect(page.getByTestId('financing-apply-current-policy')).toHaveCount(0)
  })

  test('marks a draft ready for signature', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page)
    await openAgreementDetail(page)

    await runConfirmedAction(page, 'financing-mark-ready')

    await expect(page.getByTestId('financing-agreement-status')).toContainText('Listo para firma')
    await expect(page.locator('h1')).toHaveText('OFIN-2026-042')
    await expect(page.getByText('Otrosí de financiación · v2')).toHaveText('Otrosí de financiación · v2')
    await expect(page.getByTestId('financing-open-upload')).toBeVisible()
    await expect(page.getByTestId('financing-agreement-save')).toHaveCount(0)
  })

  test('downloads the populated agreement draft', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page, { agreement: financingAgreementFixture({ status: 'ready' }) })
    await openAgreementDetail(page)
    await expect(page.locator('h1')).toHaveText('OFIN-2026-001')

    const downloadPromise = page.waitForEvent('download')
    await page.getByTestId('financing-download-draft').click()
    const download = await downloadPromise

    expect(download.suggestedFilename())
      .toBe('Borrador_Otrosi_Financiacion_OFIN-2026-001_ana-semilla.pdf')
  })

  test('activates a ready agreement from the signed PDF', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { agreement: financingAgreementFixture({ status: 'ready' }) }
    await setupApi(page, scenario)
    await openAgreementDetail(page)
    await page.getByTestId('financing-open-upload').click()
    await page.getByTestId('financing-signed-file').setInputFiles({
      name: 'otrosi-firmado.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4\n%%EOF'),
    })

    await page.getByTestId('financing-upload-signed').click()

    await expect(page.getByTestId('financing-agreement-status')).toContainText('Activo')
    expect(scenario.uploadContentType).toContain('multipart/form-data')
  })

  test('requires a PDF before signed registration', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupApi(page, { agreement: financingAgreementFixture({ status: 'ready' }) })
    await openAgreementDetail(page)
    await page.getByTestId('financing-open-upload').click()

    await page.getByTestId('financing-upload-signed').click()

    await expect(page.getByText('Selecciona el PDF firmado.').first()).toBeVisible()
    await expect(page.getByTestId('financing-agreement-status')).toContainText('Listo para firma')
  })

  test('certifies full payment with an audit note', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { agreement: financingAgreementFixture({ status: 'active' }) }
    await setupApi(page, scenario)
    await openAgreementDetail(page)
    await page.getByTestId('financing-open-complete').click()
    await page.getByTestId('financing-action-note').fill('Pago íntegro verificado contra soportes.')

    await page.getByTestId('financing-confirm-note-action').click()

    await expect(page.getByTestId('financing-agreement-status')).toContainText('Completado')
    expect(scenario.actionPayload).toEqual({ completion_note: 'Pago íntegro verificado contra soportes.' })
  })

  test('cancels an active agreement with a reason', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = { agreement: financingAgreementFixture({ status: 'active' }) }
    await setupApi(page, scenario)
    await openAgreementDetail(page)
    await page.getByTestId('financing-open-cancel').click()
    await page.getByTestId('financing-action-note').fill('Cierre acordado con el cliente.')

    await page.getByTestId('financing-confirm-note-action').click()

    await expect(page.getByTestId('financing-agreement-status')).toContainText('Cancelado')
    expect(scenario.actionPayload).toEqual({ cancellation_reason: 'Cierre acordado con el cliente.' })
  })

  test('archives a cancelled agreement', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page, { agreement: financingAgreementFixture({ status: 'cancelled' }) })
    await openAgreementDetail(page)

    await runConfirmedAction(page, 'financing-archive')

    await expect(page.getByTestId('financing-restore')).toBeVisible()
    await expect(page.getByTestId('financing-agreement-status')).toContainText('Archivado')
  })

  test('restores an archived agreement', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page, {
      agreement: financingAgreementFixture({ status: 'cancelled', is_archived: true }),
    })
    await openAgreementDetail(page)

    await runConfirmedAction(page, 'financing-restore')

    await expect(page.getByTestId('financing-archive')).toBeVisible()
    await expect(page.getByTestId('financing-agreement-status')).not.toContainText('Archivado')
  })

  test('shows an unavailable agreement detail', {
    tag: [...ADMIN_FINANCING_AGREEMENT_LIFECYCLE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, { detailUnavailable: true })
    await openAgreementDetail(page)

    await expect(page.getByRole('alert')).toContainText('No fue posible cargar el otrosí')
  })

  test('offers the second cycle after completed five-year financing', {
    tag: [...ADMIN_FINANCING_AGREEMENT_SECOND_CYCLE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (authenticated panel setup has no public entry; the test reaches the record through the visible Financiación link, Otrosíes tab, and row)
    await setupApi(page, { agreement: financingAgreementFixture({ status: 'completed' }) })
    await openAgreementDetail(page)

    await expect(page.getByTestId('financing-create-second-cycle')).toHaveText('Aprobar segundo ciclo')
  })

  test('hides the second cycle for three-year financing', {
    tag: [...ADMIN_FINANCING_AGREEMENT_SECOND_CYCLE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (authenticated panel setup has no public entry; the test reaches the record through the visible Financiación link, Otrosíes tab, and row)
    await setupApi(page, {
      agreement: financingAgreementFixture({
        status: 'completed',
        modality: 'three_year',
        modality_label: 'Alianza a 3 años',
        allowed_actions: ['download_signed', 'archive'],
      }),
    })
    await openAgreementDetail(page)

    await expect(page.locator('h1')).toHaveText('OFIN-2026-001')
    await expect(page.getByTestId('financing-create-second-cycle')).toHaveCount(0)
  })

  test('creates the second financing cycle', {
    tag: [...ADMIN_FINANCING_AGREEMENT_SECOND_CYCLE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupApi(page, { agreement: financingAgreementFixture({ status: 'completed' }) })
    await openAgreementDetail(page)

    await runConfirmedAction(page, 'financing-create-second-cycle')

    await expect(page).toHaveURL(/\/es-co\/panel\/partnership-program\/502$/)
    await expect(page.getByText('Este segundo ciclo conserva la modalidad')).toBeVisible()
    await expect(page.getByText('Ciclo 2')).toBeVisible()
    await expect(page.getByTestId('financing-modality-five')).toHaveCount(0)
  })

  test('shows a second-cycle eligibility rejection', {
    tag: [...ADMIN_FINANCING_AGREEMENT_SECOND_CYCLE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupApi(page, {
      agreement: financingAgreementFixture({ status: 'completed' }),
      actionFailure: {
        action: 'create-second-cycle',
        status: 409,
        detail: 'El primer ciclo todavía no acredita pago íntegro.',
        code: 'second_cycle_unavailable',
      },
    })
    await openAgreementDetail(page)

    await runConfirmedAction(page, 'financing-create-second-cycle')

    await expect(page.getByRole('alert').first()).toContainText('pago íntegro')
    await expect(page).toHaveURL(/\/es-co\/panel\/partnership-program\/501$/)
  })

  test('shows a second-cycle service failure', {
    tag: [...ADMIN_FINANCING_AGREEMENT_SECOND_CYCLE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupApi(page, {
      agreement: financingAgreementFixture({ status: 'completed' }),
      actionFailure: {
        action: 'create-second-cycle',
        status: 503,
        detail: 'No fue posible aprobar el segundo ciclo.',
      },
    })
    await openAgreementDetail(page)

    await runConfirmedAction(page, 'financing-create-second-cycle')

    await expect(page.getByRole('alert').first()).toContainText('No fue posible aprobar')
    await expect(page.getByTestId('financing-create-second-cycle')).toBeVisible()
  })
})
