import { createPinia, setActivePinia } from 'pinia'
import { usePlatformFeaturesStore } from '../../stores/platform-features'
import { usePlatformAuthStore } from '../../stores/platform-auth'
import { usePlatformApi } from '../../composables/usePlatformApi'
import { platformFeatureCatalog } from '../../utils/platformFeatures'

jest.mock('../../composables/usePlatformApi', () => ({
  usePlatformApi: jest.fn(), readPlatformSession: jest.fn(), writePlatformSession: jest.fn(), clearPlatformSession: jest.fn(),
}))

const evaluation = (values = {}) => ({ data: { user_id: 41,
  features: { ...Object.fromEntries(platformFeatureCatalog.features.map(item => [item.key, item.default_enabled])), ...values },
} })

describe('Platform availability per identity', () => {
  let api, auth, store
  beforeEach(() => {
    setActivePinia(createPinia())
    api = { get: jest.fn() }
    usePlatformApi.mockReturnValue(api)
    auth = usePlatformAuthStore()
    Object.assign(auth, { user: { user_id: 41 }, role: 'client', isAuthenticated: true })
    store = usePlatformFeaturesStore()
  })
  afterEach(() => jest.clearAllMocks())

  it('blocks protected routes until evaluation succeeds', () => {
    expect(store.routeAllowed('/es-co/platform/documents')).toBe(false)
    expect(store.routeAllowed('/es-co/platform/projects')).toBe(true)
  })

  it('uses the effective value returned for the current account', async () => {
    api.get.mockResolvedValue(evaluation({ 'platform.bugs': false, 'platform.documents': true }))

    await store.refresh()

    expect(store.routeAllowed('/platform/projects/5/bugs')).toBe(false)
    expect(store.routeAllowed('/platform/documents')).toBe(true)
  })

  it('blocks packages independently from change requests', async () => {
    api.get.mockResolvedValue(evaluation({ 'platform.requirement_packages': false }))

    await store.refresh()

    expect(store.routeAllowed('/es-co/platform/projects/5/packages')).toBe(false)
    expect(store.routeAllowed('/platform/projects/5/changes')).toBe(true)
  })

  it('retains packages when change requests are disabled', async () => {
    api.get.mockResolvedValue(evaluation({ 'platform.change_requests': false }))

    await store.refresh()

    expect(store.routeAllowed('/platform/projects/5/packages')).toBe(true)
  })

  it('discards a response from the previous client', async () => {
    let finish
    api.get.mockReturnValue(new Promise(resolve => { finish = resolve }))
    const first = store.refresh()
    auth.user = { user_id: 42 }
    store.reset()

    finish(evaluation({ 'platform.documents': true }))
    await first

    expect(store.routeAllowed('/platform/documents')).toBe(false)
    expect(store.loaded).toBe(false)
  })

  it('clears earlier values after a failed refresh', async () => {
    api.get.mockResolvedValueOnce(evaluation({ 'platform.documents': true }))
    await store.refresh()
    api.get.mockRejectedValue(new Error('offline'))

    await store.refresh()

    expect(store.routeAllowed('/platform/documents')).toBe(false)
    expect(store.error).toBe(true)
  })

  it('hides a route after a server availability denial', async () => {
    api.get.mockResolvedValue(evaluation({ 'platform.documents': true }))
    await store.refresh()

    store.markDisabled('platform.documents')

    expect(store.routeAllowed('/platform/documents')).toBe(false)
  })

  it('retains the administrator support experience', () => {
    auth.role = 'admin'

    expect(store.routeAllowed('/platform/documents')).toBe(true)
  })

  it('rejects an incomplete availability response', async () => {
    api.get.mockResolvedValue({ data: { user_id: 41, features: null } })

    await store.refresh()

    expect(store.routeAllowed('/platform/documents')).toBe(false)
    expect(store.error).toBe(true)
  })
})
