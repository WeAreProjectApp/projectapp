/**
 * Procurement panel E2E coverage.
 *
 * These checks catch regressions where the visible SECOP workflow succeeds in
 * the browser but sends a different request, hides a rejected operation, or
 * navigates staff to a page that does not render the received opportunity.
 */
import { test, expect } from '../helpers/test.js'
import {
  ADMIN_PROCUREMENT_ALERTS,
  ADMIN_PROCUREMENT_CLASSIFICATION,
  ADMIN_PROCUREMENT_DELIVERIES,
  ADMIN_PROCUREMENT_FILTERS_EXPORT,
  ADMIN_PROCUREMENT_OPPORTUNITY_LIST,
  ADMIN_PROCUREMENT_SAVED_SEARCHES,
  ADMIN_PROCUREMENT_SETTINGS_SYNC,
} from '../helpers/flow-tags.js'
import {
  delivery,
  json,
  openProcurementFromSidebar,
  opportunity,
  setProcurementAdmin,
  setupProcurementApi,
} from '../helpers/procurement.js'

test.describe('Admin procurement', () => {
  test.setTimeout(60_000)

  test.beforeEach(async ({ page }) => {
    await setProcurementAdmin(page)
  })

  test('opens the SECOP list from the sidebar with its received opportunity', {
    tag: [...ADMIN_PROCUREMENT_OPPORTUNITY_LIST, '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    // Catches a sidebar entry that reaches a route without rendering SECOP data.
    // quality: allow-deep-link (the authenticated proposals page is setup; the tested SECOP route is reached through its sidebar link)
    await setupProcurementApi(page)
    await openProcurementFromSidebar(page)

    const card = page.getByTestId(`procurement-opportunity-${opportunity.id}`)
    await expect(card).toContainText('Mantenimiento de espacios públicos')
    await expect(card).toContainText('Alcaldía de Bogotá')
  })

  test('refresh recovers the opportunity list after a service failure', {
    tag: [...ADMIN_PROCUREMENT_OPPORTUNITY_LIST, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches a failed list load that cannot be recovered from the real refresh control.
    let listReads = 0
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => {
        if (apiPath === 'procurement/opportunities/' && method === 'GET') {
          listReads += 1
          return listReads === 1 ? json({ detail: 'SECOP no disponible' }, 503) : json({ results: [opportunity], count: 1 })
        }
        return null
      },
    })
    await openProcurementFromSidebar(page)
    await expect(page.getByRole('alert')).toHaveText('SECOP no disponible')

    await page.getByRole('button', { name: 'Actualizar', exact: true }).click()
    await expect(page.getByTestId(`procurement-opportunity-${opportunity.id}`)).toContainText(opportunity.reference)
  })

  test('exports the active keyword filter representation', {
    tag: [...ADMIN_PROCUREMENT_FILTERS_EXPORT, '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    // Catches Excel downloads that ignore the filters visible in the panel.
    // quality: allow-deep-link (the authenticated proposals page is setup; the tested SECOP route is reached through its sidebar link)
    const state = await setupProcurementApi(page)
    await openProcurementFromSidebar(page)
    await page.getByTestId('filter-keywords').fill('aseo | vigilancia')
    await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click()
    await expect.poll(() => state.calls.list.length).toBeGreaterThan(1)

    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Exportar Excel', exact: true }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe('oportunidades-secop.xlsx')
    expect(JSON.parse(state.calls.export.at(-1))).toEqual(JSON.parse(state.calls.list.at(-1)))
  })

  test('shows the API validation message for an invalid process range', {
    tag: [...ADMIN_PROCUREMENT_FILTERS_EXPORT, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches a filter rejection that looks like a successful empty result.
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method, route }) => {
        if (apiPath === 'procurement/opportunities/' && method === 'GET' && new URL(route.request().url()).searchParams.get('filters').includes('max_budget')) {
          return json({ max_budget: ['El presupuesto máximo debe superar el mínimo.'] }, 400)
        }
        return null
      },
    })
    await openProcurementFromSidebar(page)
    await page.getByText('Más filtros', { exact: true }).click()
    await page.getByTestId('filter-min_budget').fill('900000')
    await page.getByTestId('filter-max_budget').fill('100')
    await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click()
    await expect(page.getByRole('alert')).toHaveText('El presupuesto máximo debe superar el mínimo.')
  })

  test('keeps the process filter error visible when export fails', {
    tag: [...ADMIN_PROCUREMENT_FILTERS_EXPORT, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches a failed export that provides no visible feedback to staff.
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => apiPath === 'procurement/export/' && method === 'GET'
        ? json({ detail: 'La exportación SECOP falló.' }, 503) : null,
    })
    await openProcurementFromSidebar(page)
    await page.getByRole('button', { name: 'Exportar Excel', exact: true }).click()
    await expect(page.getByRole('alert')).toHaveText('La exportación SECOP falló.')
  })

  test('records a discard rationale from the opportunity detail', {
    tag: [...ADMIN_PROCUREMENT_CLASSIFICATION, '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    // Catches a detail page that saves a classification without the selected rationale.
    // quality: allow-deep-link (the authenticated proposals page is setup; both SECOP routes are reached through visible links)
    const payloads = []
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method, route }) => {
        if (apiPath === `procurement/opportunities/${opportunity.id}/classification/` && method === 'POST') {
          payloads.push(route.request().postDataJSON())
        }
        return null
      },
    })
    await openProcurementFromSidebar(page)
    await page.getByTestId(`procurement-opportunity-${opportunity.id}`).getByRole('link', { name: opportunity.title }).click()
    await expect(page.getByTestId('procurement-detail')).toContainText('Servicio de mantenimiento para espacios públicos.')
    await page.getByLabel('Estado').selectOption('discarded')
    await page.getByLabel('Análisis y motivo').fill('No acredita la experiencia requerida.')
    await page.getByTestId('procurement-save-classification').click()
    await expect(page.getByRole('status')).toHaveText('Cambios guardados.')
    expect(payloads).toEqual([{ state: 'discarded', notes: 'No acredita la experiencia requerida.' }])
  })

  test('rejects a discard without its required rationale', {
    tag: [...ADMIN_PROCUREMENT_CLASSIFICATION, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches the client accepting an irreversible discard with no audit reason.
    let classificationPosts = 0
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => {
        if (apiPath === `procurement/opportunities/${opportunity.id}/classification/` && method === 'POST') classificationPosts += 1
        return null
      },
    })
    await page.goto(`/es-co/panel/procurement/${opportunity.id}`, { waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('procurement-detail')).toContainText(opportunity.reference)
    await page.getByLabel('Estado').selectOption('discarded')
    await page.getByTestId('procurement-save-classification').click()
    await expect(page.getByRole('alert')).toHaveText('Indica el motivo del descarte.')
    expect(classificationPosts).toBe(0)
  })

  test('shows a save failure for a classification request', {
    tag: [...ADMIN_PROCUREMENT_CLASSIFICATION, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches an unavailable classification service that appears to save the analysis.
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => apiPath === `procurement/opportunities/${opportunity.id}/classification/` && method === 'POST'
        ? json({ detail: 'Servicio de análisis no disponible.' }, 503) : null,
    })
    await page.goto(`/es-co/panel/procurement/${opportunity.id}`, { waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('procurement-detail')).toContainText(opportunity.title)
    await page.getByLabel('Análisis y motivo').fill('La experiencia es suficiente.')
    await page.getByTestId('procurement-save-classification').click()
    await expect(page.getByRole('alert')).toHaveText('No se pudo guardar el cambio.')
  })

  test('applies the saved search filters after creation', {
    tag: [...ADMIN_PROCUREMENT_SAVED_SEARCHES, '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    // Catches saved searches that store one filter set but apply another to SECOP.
    // quality: allow-deep-link (the authenticated proposals page is setup; the tested SECOP route is reached through its sidebar link)
    const payloads = []
    const state = await setupProcurementApi(page, {
      onRequest: ({ apiPath, method, route }) => {
        if (apiPath === 'procurement/searches/' && method === 'POST') payloads.push(route.request().postDataJSON())
        return null
      },
    })
    await openProcurementFromSidebar(page)
    await page.getByTestId('filter-keywords').fill('interventoría')
    await page.getByTestId('procurement-new-search').click()
    const form = page.getByTestId('procurement-record-form')
    await form.getByLabel('Nombre').fill('Interventoría')
    await form.getByTestId('procurement-save').click()
    await page.getByTestId('procurement-tab-searches').click()
    await expect(page.getByText('Interventoría', { exact: true })).toHaveCount(1)
    await page.getByRole('button', { name: 'Aplicar', exact: true }).click()
    await expect(page.getByTestId('procurement-tab-processes')).toHaveAttribute('aria-pressed', 'true')
    expect(payloads).toEqual([{ name: 'Interventoría', filters: { keywords: ['interventoría'] }, is_favorite: false }])
    expect(JSON.parse(state.calls.list.at(-1))).toEqual({ keywords: ['interventoría'] })
  })

  test('keeps the saved search form open after a validation rejection', {
    tag: [...ADMIN_PROCUREMENT_SAVED_SEARCHES, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches a duplicate search name that closes the form as though it was created.
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => apiPath === 'procurement/searches/' && method === 'POST'
        ? json({ name: ['Ya existe una búsqueda con este nombre.'] }, 400) : null,
    })
    await page.goto('/es-co/panel/procurement', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('procurement-new-search').click()
    const form = page.getByTestId('procurement-record-form')
    await form.getByLabel('Nombre').fill('Repetida')
    await form.getByTestId('procurement-save').click()
    await expect(form.getByRole('alert')).toHaveText('Ya existe una búsqueda con este nombre.')
    await expect(form.getByLabel('Nombre')).toHaveValue('Repetida')
  })

  test('keeps the saved search form open after a service failure', {
    tag: [...ADMIN_PROCUREMENT_SAVED_SEARCHES, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches a 5xx from saved-search persistence that silently discards user input.
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => apiPath === 'procurement/searches/' && method === 'POST'
        ? json({ detail: 'Servicio de búsquedas no disponible.' }, 503) : null,
    })
    await page.goto('/es-co/panel/procurement', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('procurement-new-search').click()
    const form = page.getByTestId('procurement-record-form')
    await form.getByLabel('Nombre').fill('Obra civil')
    await form.getByTestId('procurement-save').click()
    await expect(form.getByRole('alert')).toHaveText('Servicio de búsquedas no disponible.')
    await expect(form.getByLabel('Nombre')).toHaveValue('Obra civil')
  })

  test('creates an active alert with normalized recipients', {
    tag: [...ADMIN_PROCUREMENT_ALERTS, '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    // Catches alert recipients posted as a single comma-delimited string.
    // quality: allow-deep-link (the authenticated proposals page is setup; the tested SECOP route is reached through its sidebar link)
    const payloads = []
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method, route }) => {
        if (apiPath === 'procurement/alerts/' && method === 'POST') payloads.push(route.request().postDataJSON())
        return null
      },
    })
    await openProcurementFromSidebar(page)
    await page.getByTestId('procurement-new-alert').click()
    const form = page.getByTestId('procurement-record-form')
    await form.getByLabel('Nombre').fill('Obras urgentes')
    await form.getByLabel('Destinatarios (separados por comas)').fill('carlos@example.test, equipo@example.test')
    await form.getByLabel('Frecuencia').selectOption('weekly')
    await form.getByLabel('Alerta activa').check()
    await form.getByTestId('procurement-save').click()
    await expect(form).toBeHidden()
    expect(payloads).toEqual([{ name: 'Obras urgentes', filters: {}, recipients: ['carlos@example.test', 'equipo@example.test'], frequency: 'weekly', is_active: true }])
  })

  test('keeps the alert form open for duplicate recipients', {
    tag: [...ADMIN_PROCUREMENT_ALERTS, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches duplicate recipient validation that falsely reports a created alert.
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => apiPath === 'procurement/alerts/' && method === 'POST'
        ? json({ recipients: ['Cada destinatario debe ser único.'] }, 400) : null,
    })
    await page.goto('/es-co/panel/procurement', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('procurement-new-alert').click()
    const form = page.getByTestId('procurement-record-form')
    await form.getByLabel('Nombre').fill('Duplicados')
    await form.getByLabel('Destinatarios (separados por comas)').fill('carlos@example.test, carlos@example.test')
    await form.getByTestId('procurement-save').click()
    await expect(form.getByRole('alert')).toHaveText('Cada destinatario debe ser único.')
    await expect(form.getByLabel('Nombre')).toHaveValue('Duplicados')
  })

  test('keeps the alert form open after an alert service failure', {
    tag: [...ADMIN_PROCUREMENT_ALERTS, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches a failed alert save that closes the dialog without preserving input.
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => apiPath === 'procurement/alerts/' && method === 'POST'
        ? json({ detail: 'Servicio de alertas no disponible.' }, 503) : null,
    })
    await page.goto('/es-co/panel/procurement', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('procurement-new-alert').click()
    const form = page.getByTestId('procurement-record-form')
    await form.getByLabel('Nombre').fill('Alerta pendiente')
    await form.getByLabel('Destinatarios (separados por comas)').fill('carlos@example.test')
    await form.getByTestId('procurement-save').click()
    await expect(form.getByRole('alert')).toHaveText('Servicio de alertas no disponible.')
    await expect(form.getByLabel('Nombre')).toHaveValue('Alerta pendiente')
  })

  test('persists settings before requesting a synchronization', {
    tag: [...ADMIN_PROCUREMENT_SETTINGS_SYNC, '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    // Catches a visible email switch or sync button that does not issue its request.
    // quality: allow-deep-link (the authenticated proposals page is setup; the tested SECOP route is reached through its sidebar link)
    const patches = []
    const state = await setupProcurementApi(page, {
      onRequest: ({ apiPath, method, route }) => {
        if (apiPath === 'procurement/settings/' && method === 'PATCH') patches.push(route.request().postDataJSON())
        return null
      },
    })
    await openProcurementFromSidebar(page)
    await page.getByTestId('procurement-tab-settings').click()
    await page.getByLabel('Permitir envíos de correo').check()
    await page.getByTestId('procurement-save').click()
    await expect(page.getByRole('status')).toHaveText('Cambios guardados.')
    await page.getByTestId('procurement-sync').click()
    await expect(page.getByRole('status')).toHaveText('Actualización solicitada.')
    expect(patches).toHaveLength(1)
    expect(patches[0].email_enabled).toBe(true)
    expect(state.calls.sync).toBe(1)
  })

  test('shows a settings validation message without losing the form', {
    tag: [...ADMIN_PROCUREMENT_SETTINGS_SYNC, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches invalid synchronization settings that appear accepted after submission.
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => apiPath === 'procurement/settings/' && method === 'PATCH'
        ? json({ lookback_days: ['El periodo supera el límite operativo configurado.'] }, 400) : null,
    })
    await page.goto('/es-co/panel/procurement', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('procurement-tab-settings').click()
    await page.getByLabel('Días de consulta inicial').fill('31')
    await page.getByTestId('procurement-save').click()
    await expect(page.getByRole('alert')).toHaveText('El periodo supera el límite operativo configurado.')
    await expect(page.getByLabel('Días de consulta inicial')).toHaveValue('31')
  })

  test('shows a synchronization service failure', {
    tag: [...ADMIN_PROCUREMENT_SETTINGS_SYNC, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches a rejected SECOP synchronization request that shows success.
    await setupProcurementApi(page, {
      onRequest: ({ apiPath, method }) => apiPath === 'procurement/sync/' && method === 'POST'
        ? json({ detail: 'SECOP no responde.' }, 503) : null,
    })
    await page.goto('/es-co/panel/procurement', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('procurement-sync').click()
    await expect(page.getByRole('alert')).toHaveText('SECOP no responde.')
  })

  test('confirms a retry for an uncertain delivery', {
    tag: [...ADMIN_PROCUREMENT_DELIVERIES, '@role:admin', '@outcome:display', '@outcome:success'],
  }, async ({ page }) => {
    // Catches a retry that bypasses the uncertainty warning or targets another delivery.
    // quality: allow-deep-link (the authenticated proposals page is setup; the tested SECOP route is reached through its sidebar link)
    const state = await setupProcurementApi(page, { deliveries: [{ ...delivery }] })
    await openProcurementFromSidebar(page)
    await page.getByTestId('procurement-tab-deliveries').click()
    await expect(page.getByText('Resultado incierto', { exact: true })).toHaveCount(1)
    await page.getByRole('button', { name: 'Reintentar', exact: true }).click()
    await expect(page.getByText('Comprueba el buzón antes de reintentar: este correo podría haberse enviado.')).toHaveCount(1)
    await page.getByTestId('procurement-confirm').click()
    await expect(page.getByRole('status')).toHaveText('Reintento solicitado.')
    expect(state.calls.retry).toEqual([delivery.id])
  })

  test('keeps retry confirmation open for a rejected delivery retry', {
    tag: [...ADMIN_PROCUREMENT_DELIVERIES, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    // Catches a retry validation rejection that dismisses the delivery confirmation.
    await setupProcurementApi(page, {
      deliveries: [{ ...delivery }],
      onRequest: ({ apiPath, method }) => apiPath === `procurement/deliveries/${delivery.id}/retry/` && method === 'POST'
        ? json({ detail: 'La entrega ya está en curso.' }, 400) : null,
    })
    await page.goto('/es-co/panel/procurement', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('procurement-tab-deliveries').click()
    await page.getByRole('button', { name: 'Reintentar', exact: true }).click()
    await page.getByTestId('procurement-confirm').click()
    await expect(page.getByRole('alert')).toHaveText('La entrega ya está en curso.')
    await expect(page.getByTestId('procurement-confirm')).toBeVisible()
  })

  test('keeps retry confirmation open after a delivery service failure', {
    tag: [...ADMIN_PROCUREMENT_DELIVERIES, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    // Catches an unavailable mail delivery service that silently closes retry confirmation.
    await setupProcurementApi(page, {
      deliveries: [{ ...delivery }],
      onRequest: ({ apiPath, method }) => apiPath === `procurement/deliveries/${delivery.id}/retry/` && method === 'POST'
        ? json({ detail: 'Pasarela de correo no disponible.' }, 503) : null,
    })
    await page.goto('/es-co/panel/procurement', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('procurement-tab-deliveries').click()
    await page.getByRole('button', { name: 'Reintentar', exact: true }).click()
    await page.getByTestId('procurement-confirm').click()
    await expect(page.getByRole('alert')).toHaveText('Pasarela de correo no disponible.')
    await expect(page.getByTestId('procurement-confirm')).toBeVisible()
  })
})
