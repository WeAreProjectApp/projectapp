/**
 * Catches a regression where administrators could change the displayed global
 * voice switch but the saved configuration was never persisted by the panel.
 */
import { test, expect } from './helpers/test.js'
import { mockApi } from './helpers/api.js'
import { setAuthLocalStorage } from './helpers/auth.js'
import { waitForNuxtApp } from './helpers/navigation.js'

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })

function makeSettings(overrides = {}) {
  return {
    version: 4,
    chatbot_enabled: false,
    voice_reporting_enabled: true,
    chatbot_model: 'claude-haiku-5-5',
    voice_report_model: 'claude-haiku-5-5',
    monthly_audio_limit: 1000,
    daily_user_audio_limit: 20,
    ai_request_limit: 20,
    ai_window_minutes: 300,
    max_output_tokens: 1000,
    report_cache_enabled: true,
    chatbot_cache_enabled: true,
    report_cache_hours: 24,
    chatbot_cache_hours: 24,
    credentials: {
      anthropic: { configured: true, version: 2, last_test_status: 'ok' },
      openai: { configured: true, version: 2, last_test_status: 'ok' },
      jev: { configured: true, version: 2, last_test_status: 'ok' },
    },
    ...overrides,
  }
}

function reportTemplate() {
  return {
    id: 1,
    family: 'report',
    scenario: 'bug',
    language: 'es',
    version: 1,
    placeholders: ['transcript'],
    content: 'Estructura el reporte: {{ transcript }}',
  }
}

async function setup(page, { saveFails = false, previewFails = false, concurrentSettingsChange = false } = {}) {
  const scenario = { settings: makeSettings(), savedPayload: null }
  await setAuthLocalStorage(page, {
    token: 'e2e-ai-settings-admin',
    userAuth: { id: 901, role: 'admin', is_staff: true, is_superuser: true },
  })
  await mockApi(page, ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } })
    if (apiPath === 'platform/ai/admin/settings/' && method === 'GET') return json(scenario.settings)
    if (apiPath === 'platform/ai/admin/settings/' && method === 'PATCH') {
      scenario.savedPayload = route.request().postDataJSON()
      if (saveFails) return json({ detail: 'No disponible.' }, 503)
      if (scenario.savedPayload.expected_version !== scenario.settings.version) return json({ detail: 'Versión desactualizada.' }, 409)
      scenario.settings = { ...scenario.settings, ...scenario.savedPayload, version: 5 }
      return json(scenario.settings)
    }
    if (apiPath === 'platform/ai/admin/clients/' && method === 'GET') return json({ results: [], count: 0, page: 1 })
    if (apiPath === 'platform/ai/admin/credentials/anthropic/' && method === 'PUT') {
      if (concurrentSettingsChange) scenario.settings = { ...scenario.settings, voice_reporting_enabled: false, version: 5 }
      return json({ configured: true, version: 3, last_test_status: '' })
    }
    if (apiPath === 'platform/ai/admin/templates/' && method === 'GET') return json([reportTemplate()])
    if (apiPath === 'platform/ai/admin/templates/1/preview/' && method === 'POST') {
      if (previewFails) return json({ detail: 'La plantilla no se puede previsualizar.' }, 400)
      return json({ preview: 'Vista previa del reporte.' })
    }
    if (apiPath === 'platform/ai/admin/usage/' && method === 'GET') return json({ month: '2026-10', groups: [] })
    if (apiPath === 'proposals/' || apiPath === 'proposals/alerts/') return json([])
    if (apiPath === 'proposals/dashboard/') return json({ total: 0, by_status: {} })
    return null
  })
  return scenario
}

async function openSettingsFromPanel(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' })
  await waitForNuxtApp(page)
  await page.getByRole('link', { name: 'Configuración de IA', exact: true }).click()
  await expect(page).toHaveURL(/\/es-co\/panel\/platform\/ai$/)
  await expect(page.getByTestId('platform-ai-settings')).toContainText('Controles globales')
}

test.describe('Platform AI settings', () => {
  test.setTimeout(60_000)

  // Catches the regression where an apparently successful global switch did not change the server configuration.
  test('persists the global voice-report switch', {
    tag: ['@flow:panel-platform-ai-settings', '@outcome:success'],
  }, async ({ page }) => {
    const scenario = await setup(page)
    await openSettingsFromPanel(page)

    const voiceSwitch = page.getByTestId('ai-global-voice_reporting_enabled')
    await expect(voiceSwitch).toHaveAttribute('aria-checked', 'true')
    await voiceSwitch.click()
    await expect(voiceSwitch).toHaveAttribute('aria-checked', 'false')
    await page.getByTestId('ai-save-settings').click()

    await expect(page.getByRole('status')).toHaveText('Datos actualizados.')
    expect(scenario.savedPayload.voice_reporting_enabled).toBe(false)
  })

  // Catches the regression where a rejected save silently discarded an administrator's selected switch state.
  test('keeps the global voice-report switch after a failed save', {
    tag: ['@flow:panel-platform-ai-settings', '@outcome:failure'],
  }, async ({ page }) => {
    const scenario = await setup(page, { saveFails: true })
    await openSettingsFromPanel(page)

    const voiceSwitch = page.getByTestId('ai-global-voice_reporting_enabled')
    await voiceSwitch.click()
    await page.getByTestId('ai-save-settings').click()

    await expect(page.getByRole('alert')).toHaveText('No se pudo completar la operación. Actualiza los datos y revisa los valores antes de reintentar.')
    await expect(voiceSwitch).toHaveAttribute('aria-checked', 'false')
    expect(scenario.savedPayload.voice_reporting_enabled).toBe(false)
  })

  // Catches the regression where a rejected template preview left no visible recovery state for the administrator.
  test('shows a visible error when template preview is rejected', {
    tag: ['@flow:panel-platform-ai-settings', '@outcome:error'],
  }, async ({ page }) => {
    await setup(page, { previewFails: true })
    await openSettingsFromPanel(page)

    await page.getByRole('tab', { name: 'Plantillas', exact: true }).click()
    const templateSelect = page.getByRole('combobox').filter({ has: page.getByRole('option', { name: 'Reporte de bug · ES', exact: true }) })
    await templateSelect.selectOption('1')
    await page.getByTestId('ai-template-content').fill('Texto de vista previa rechazado')
    await page.getByRole('button', { name: 'Previsualizar sin IA', exact: true }).click()

    await expect(page.getByRole('alert')).toHaveText('No se pudo completar la operación. Actualiza los datos y revisa los valores antes de reintentar.')
    await expect(page.getByTestId('ai-template-content')).toHaveValue('Texto de vista previa rechazado')
  })

  // Catches a key refresh adopting another administrator's new settings version while retaining an older global form.
  test('keeps the global form version after saving a provider key', {
    tag: ['@flow:panel-platform-ai-settings', '@outcome:error'],
  }, async ({ page }) => {
    const scenario = await setup(page, { concurrentSettingsChange: true })
    await openSettingsFromPanel(page)
    await page.getByRole('tab', { name: 'Proveedores y claves', exact: true }).click()
    const provider = page.getByRole('article').filter({ has: page.getByRole('heading', { name: 'Anthropic', exact: true }) })
    await provider.getByTestId('ai-key-anthropic').fill('synthetic-provider-key')
    await provider.getByRole('button', { name: 'Guardar o reemplazar clave', exact: true }).click()
    await expect(page.getByRole('status')).toHaveText('Datos actualizados.')
    await expect(provider.getByTestId('ai-key-anthropic')).toHaveValue('')

    await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click()

    await expect(page.getByRole('alert')).toHaveText('No se pudo completar la operación. Actualiza los datos y revisa los valores antes de reintentar.')
    expect(scenario.savedPayload.expected_version).toBe(4)
    expect(scenario.settings.voice_reporting_enabled).toBe(false)
  })
})
