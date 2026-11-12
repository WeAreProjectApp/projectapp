import { expect } from './test.js'
import { mockApi } from './api.js'
import { setAuthLocalStorage } from './auth.js'

export const opportunity = {
  id: 71,
  reference: 'SECOP-II-2026-071',
  title: 'Mantenimiento de espacios públicos',
  entity_name: 'Alcaldía de Bogotá',
  department: 'Bogotá D.C.',
  city: 'Bogotá',
  budget: 125000000,
  closing_at: '2026-12-20T17:00:00Z',
  days_remaining: 5,
  source_status: 'Publicado',
  method: 'Licitación pública',
  unspsc_code: '72101500',
  description: 'Servicio de mantenimiento para espacios públicos.',
  source_url: 'https://www.colombiacompra.gov.co/secop-ii',
  my_classification: null,
}

export const settings = {
  id: 9,
  sync_enabled: true,
  email_enabled: false,
  sync_time: '02:00',
  daily_time: '07:00',
  weekly_time: '07:00',
  weekly_day: 0,
  lookback_days: 30,
  updated_at: '2026-11-05T12:00:00Z',
}

export const delivery = {
  id: 41,
  recipient: 'carlos@example.test',
  status: 'uncertain',
  frequency: 'daily',
  attempts: 1,
  error: 'La pasarela no confirmó la entrega.',
  created_at: '2026-11-05T12:00:00Z',
  opportunity_count: 1,
  snapshot: { opportunities: [{ ...opportunity, matched_alerts: [] }] },
}

export const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

export async function setProcurementAdmin(page) {
  await setAuthLocalStorage(page, {
    token: 'procurement-e2e-admin',
    userAuth: { id: 1, role: 'admin', is_staff: true },
  })
}

export async function setupProcurementApi(page, scenario = {}) {
  const state = {
    records: scenario.records || [{ ...opportunity }],
    searches: scenario.searches || [],
    alerts: scenario.alerts || [],
    deliveries: scenario.deliveries || [],
    settings: { ...settings, ...(scenario.settings || {}) },
    sync: scenario.sync || { open_count: 1, recent: [{ status: 'success', message: 'SECOP actualizado' }] },
    detail: scenario.detail || { ...opportunity, classifications: [], activities: [] },
    calls: { list: [], export: [], sync: 0, retry: [] },
  }

  await mockApi(page, async ({ route, apiPath, method }) => {
    const override = await scenario.onRequest?.({ route, apiPath, method, state })
    if (override) return override

    if (apiPath === 'auth/check/') return json({ user: { id: 1, username: 'admin', is_staff: true } })
    if (apiPath === 'proposals/' || apiPath === 'proposals/alerts/' || apiPath === 'proposals/client-profiles/') return json([])
    if (apiPath === 'proposals/dashboard/') return json({ total: 0, by_status: {} })
    if (apiPath === 'procurement/searches/' && method === 'GET') return json(state.searches)
    if (apiPath === 'procurement/settings/' && method === 'GET') return json(state.settings)
    if (apiPath === 'procurement/sync/' && method === 'GET') return json(state.sync)
    if (apiPath === 'procurement/alerts/' && method === 'GET') return json(state.alerts)
    if (apiPath === 'procurement/deliveries/' && method === 'GET') return json({ results: state.deliveries, count: state.deliveries.length })
    if (apiPath === 'procurement/opportunities/' && method === 'GET') {
      state.calls.list.push(new URL(route.request().url()).searchParams.get('filters'))
      return json({ results: state.records, count: state.records.length })
    }
    if (apiPath === `procurement/opportunities/${opportunity.id}/` && method === 'GET') return json(state.detail)
    if (apiPath === 'procurement/export/' && method === 'GET') {
      state.calls.export.push(new URL(route.request().url()).searchParams.get('filters'))
      return { status: 200, contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', body: 'fixture workbook' }
    }
    if (apiPath === 'procurement/searches/' && method === 'POST') {
      const search = { id: 8, ...route.request().postDataJSON() }
      state.searches = [...state.searches, search]
      return json(search, 201)
    }
    if (apiPath === 'procurement/alerts/' && method === 'POST') {
      const alert = { id: 17, ...route.request().postDataJSON() }
      state.alerts = [...state.alerts, alert]
      return json(alert, 201)
    }
    if (apiPath === 'procurement/settings/' && method === 'PATCH') {
      state.settings = { ...state.settings, ...route.request().postDataJSON() }
      return json(state.settings)
    }
    if (apiPath === 'procurement/sync/' && method === 'POST') {
      state.calls.sync += 1
      state.sync = { ...state.sync, recent: [{ status: 'queued', message: 'Actualización solicitada' }] }
      return json(state.sync, 202)
    }
    if (apiPath === `procurement/opportunities/${opportunity.id}/classification/` && method === 'POST') {
      const classification = { id: 6, owner: 1, owner_name: 'admin', ...route.request().postDataJSON() }
      state.detail = { ...state.detail, classifications: [classification], activities: [{ id: 3, actor: 'admin', created_at: '2026-11-05T12:01:00Z', snapshot: classification }] }
      return json(classification, 201)
    }
    if (apiPath === `procurement/opportunities/${opportunity.id}/restore/` && method === 'POST') {
      state.detail = { ...state.detail, classifications: [{ id: 6, owner: 1, owner_name: 'admin', state: 'interesting', notes: 'Cumple perfil' }] }
      return json(state.detail.classifications[0])
    }
    if (apiPath === `procurement/deliveries/${delivery.id}/retry/` && method === 'POST') {
      state.calls.retry.push(delivery.id)
      return json({ id: delivery.id, status: 'queued' }, 202)
    }
    return null
  })
  return state
}

export async function openProcurementFromSidebar(page) {
  await page.goto('/es-co/panel/proposals', { waitUntil: 'domcontentloaded' })
  const procurementLink = page.getByRole('link', { name: 'Oportunidades SECOP', exact: true })
  await expect(procurementLink).toHaveCount(1)
  await procurementLink.click()
  await expect(page).toHaveURL(/\/panel\/procurement$/)
  await expect(page.getByTestId('procurement-page')).toHaveCount(1)
}
