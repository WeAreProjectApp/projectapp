/**
 * R-platform-ai-01: AI limits must remain reachable with their concrete
 * shared-quota values at each supported panel width.
 */
import { test, expect, assertResponsiveScenario } from '../helpers/test.js'
import { mockApi } from '../helpers/api.js'
import { setAuthLocalStorage } from '../helpers/auth.js'
import { viewportUse } from '../helpers/viewports.js'
import { RESPONSIVE_PROFILES, batchForScenario, getResponsiveScenario } from './catalog-scenarios.js'

const scenario = getResponsiveScenario('frontend/pages/panel/platform/ai.vue')
const json = (body) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

test.setTimeout(60_000)

const settings = {
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
}

async function setup(page) {
  await setAuthLocalStorage(page, {
    token: 'responsive-platform-ai-admin',
    userAuth: { id: 901, role: 'admin', is_staff: true, is_superuser: true },
  })
  await mockApi(page, ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } })
    if (apiPath === 'platform/ai/admin/settings/' && method === 'GET') return json(settings)
    if (apiPath === 'platform/ai/admin/clients/' && method === 'GET') return json({ results: [], count: 0, page: 1 })
    if (apiPath === 'platform/ai/admin/templates/' && method === 'GET') return json([])
    if (apiPath === 'platform/ai/admin/usage/' && method === 'GET') return json({ month: '2026-10', groups: [] })
    if (apiPath === 'proposals/' || apiPath === 'proposals/alerts/') return json([])
    if (apiPath === 'proposals/dashboard/') return json({ total: 0, by_status: {} })
    return null
  })
}

const entryByProfile = Object.freeze({
  compact: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Configuración de IA', exact: true }).click() },
  portrait: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Configuración de IA', exact: true }).click() },
  landscape: (page) => page.getByRole('link', { name: 'Configuración de IA', exact: true }).click(),
  desktop: (page) => page.getByRole('link', { name: 'Configuración de IA', exact: true }).click(),
  wide: (page) => page.getByRole('link', { name: 'Configuración de IA', exact: true }).click(),
})

const usageByProfile = Object.freeze({
  compact: (page) => page.getByRole('combobox', { name: 'Configuración de IA', exact: true }).selectOption('usage'),
  portrait: (page) => page.getByRole('combobox', { name: 'Configuración de IA', exact: true }).selectOption('usage'),
  landscape: (page) => page.getByRole('tab', { name: 'Consumo y caché', exact: true }).click(),
  desktop: (page) => page.getByRole('tab', { name: 'Consumo y caché', exact: true }).click(),
  wide: (page) => page.getByRole('tab', { name: 'Consumo y caché', exact: true }).click(),
})

async function openUsage(page, profile) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' })
  await entryByProfile[profile](page)
  const panel = page.getByTestId('platform-ai-settings')
  await expect(panel).toContainText('Controles globales')
  await usageByProfile[profile](page)
  await expect(panel).toContainText('Límites y reutilización')
  await expect.poll(() => panel.getByRole('spinbutton').evaluateAll((inputs) => inputs.map((input) => input.value))).toEqual(expect.arrayContaining(['20', '300']))
  return panel
}

for (const profile of RESPONSIVE_PROFILES) {
  test.describe(`platform AI responsive · ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile))

    test('keeps the shared quota controls reachable', {
      tag: ['@flow:panel-platform-ai-settings', '@outcome:display', '@responsive:projects', `@responsive-scenario:${scenario.catalogKey}`, `@responsive-batch:${batchForScenario(scenario.catalogKey)}`, `@viewport:${profile}`],
    }, async ({ page }, testInfo) => {
      await setup(page)
      // quality: allow-deep-link (the authenticated panel shell is the entry point; responsive navigation reaches the AI settings link).
      const panel = await openUsage(page, profile)
      const limit = panel.getByRole('spinbutton', { name: 'Solicitudes compartidas por ventana', exact: true })
      await expect(limit).toHaveValue('20')
      await expect(panel.getByRole('spinbutton', { name: 'Ventana móvil (minutos)', exact: true })).toHaveValue('300')
      await limit.fill('19')
      await expect(limit).toHaveValue('19')
      await assertResponsiveScenario(page, testInfo, scenario, { profile, priorityLocator: panel })
    })
  })
}
