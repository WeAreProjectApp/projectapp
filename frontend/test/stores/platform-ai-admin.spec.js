import { createPinia, setActivePinia } from 'pinia'
import { usePlatformAIAdminStore } from '../../stores/platform_ai_admin'

jest.mock('../../stores/services/request_http', () => ({
  get_request: jest.fn(), patch_request: jest.fn(), put_request: jest.fn(), create_request: jest.fn(), delete_request: jest.fn(),
}))
const { get_request, patch_request, put_request } = require('../../stores/services/request_http')

describe('usePlatformAIAdminStore', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = usePlatformAIAdminStore()
    store.settings = { credentials: { anthropic: { configured: true, version: 4 } } }
  })

  afterEach(() => { jest.clearAllMocks() })

  it('saves a provider key as a write-only versioned payload', async () => {
    // Falla si una clave se manda sin la versión de concurrencia o queda almacenada en el estado del panel.
    get_request.mockResolvedValueOnce({ data: { credentials: { anthropic: { configured: true, version: 5 } } } })

    await store.saveKey('anthropic', 'sk-live-private-key')

    expect(put_request).toHaveBeenCalledWith('platform/ai/admin/credentials/anthropic/', { api_key: 'sk-live-private-key', expected_version: 4 })
    expect(JSON.stringify(store.$state)).not.toContain('sk-live-private-key')
  })

  it('updates one client feature without replacing other client rows', async () => {
    // Falla si cambiar voz para un cliente borra o sobrescribe los controles de los demás.
    store.clients = { page: 1, count: 2, results: [
      { user_id: 7, name: 'Ada', chatbot_enabled: false, voice_reporting_enabled: false, version: 2 },
      { user_id: 8, name: 'Luis', chatbot_enabled: true, voice_reporting_enabled: false, version: 1 },
    ] }
    patch_request.mockResolvedValueOnce({ data: { user_id: 7, name: 'Ada', chatbot_enabled: false, voice_reporting_enabled: true, version: 3 } })

    await store.saveClient(store.clients.results[0], 'voice_reporting_enabled', true)

    expect(store.clients.results).toEqual([
      { user_id: 7, name: 'Ada', chatbot_enabled: false, voice_reporting_enabled: true, version: 3 },
      { user_id: 8, name: 'Luis', chatbot_enabled: true, voice_reporting_enabled: false, version: 1 },
    ])
    expect(patch_request).toHaveBeenCalledWith('platform/ai/admin/clients/7/', { voice_reporting_enabled: true, expected_version: 2 })
  })

  it.each([
    {
      label: 'stores a client allowance', limit: 7, minutes: 45,
      saved: { user_id: 7, name: 'Ada', ai_request_limit: 7, ai_window_minutes: 45, version: 3 },
    },
    {
      label: 'returns a client to the global allowance', limit: null, minutes: null,
      saved: { user_id: 7, name: 'Ada', ai_request_limit: null, ai_window_minutes: null, version: 3 },
    },
  ])('$label', async ({ limit, minutes, saved }) => {
    // Falla si el administrador no puede distinguir un cupo propio de la herencia global.
    const client = { user_id: 7, name: 'Ada', ai_request_limit: 4, ai_window_minutes: 30, version: 2 }
    store.clients = { page: 1, count: 1, results: [client] }
    patch_request.mockResolvedValueOnce({ data: saved })

    await store.saveClientQuota(client, limit, minutes)

    expect(patch_request).toHaveBeenCalledWith('platform/ai/admin/clients/7/', {
      ai_request_limit: limit, ai_window_minutes: minutes, expected_version: 2,
    })
    expect(store.clients.results).toEqual([saved])
  })
})
