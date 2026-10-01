import { createPinia, setActivePinia } from 'pinia'
import { usePlatformSecureLinksStore } from '../../stores/platform-secure-links'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))

const { usePlatformApi } = require('../../composables/usePlatformApi')

const deferred = () => {
  let resolve
  const promise = new Promise((done) => { resolve = done })
  return { promise, resolve }
}

describe('platform secure links store', () => {
  let api
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    api = { get: jest.fn(), post: jest.fn(), patch: jest.fn() }
    usePlatformApi.mockReturnValue(api)
    store = usePlatformSecureLinksStore()
  })

  afterEach(() => { jest.restoreAllMocks() })

  it('keeps list responses as metadata only', async () => {
    // Fails if a list response persists an access URL or secret content in Pinia.
    api.get.mockResolvedValue({ data: {
      results: [{ id: 7, project: 1, title: 'Database access', status: 'active', updated_at: '2026-10-01T12:00:00Z', url: 'https://example.test/#fake-token', fields: { password: 'fake-secret-for-test' } }],
      counts: { active: 1 }, count: 1, page: 1,
    } })

    await store.fetchLinks(1)

    expect(store.links).toEqual([{ id: 7, project: 1, title: 'Database access', status: 'active', updated_at: '2026-10-01T12:00:00Z' }])
    expect(JSON.stringify(store.$state)).not.toContain('fake-secret-for-test')
  })

  it.each([
    ['another project', (currentStore) => currentStore.enterProject(2), 2],
    ['a cleared workspace', (currentStore) => currentStore.clear(), null],
  ])('discards a late list response after %s', async (_label, leaveRequest, projectId) => {
    // Fails if a late response restores metadata after the selected project changed.
    const pending = deferred()
    api.get.mockReturnValue(pending.promise)

    const resultPromise = store.fetchLinks(1)
    leaveRequest(store)
    pending.resolve({ data: { results: [{ id: 7, title: 'Old project link', url: 'https://example.test/#fake-token' }], counts: { active: 1 }, count: 1, page: 1 } })
    const result = await resultPromise

    expect(result).toEqual({ success: false, stale: true })
    expect(store.links).toEqual([])
    expect(store.projectId).toBe(projectId)
    expect(store.error).toBe('')
  })

  it('returns an explicit URL without storing it after copy', async () => {
    // Fails if the explicit access URL becomes shared Pinia state after copying.
    store.enterProject(1)
    api.post.mockResolvedValue({ data: { url: 'https://example.test/#copy-fake-token', fields: { password: 'fake-secret-for-test' } } })

    const result = await store.copyURL(7)

    expect(result.data.url).toBe('https://example.test/#copy-fake-token')
    expect(api.post).toHaveBeenCalledWith('projects/1/secure-links/7/link/', {})
    expect(JSON.stringify(store.$state)).not.toContain('copy-fake-token')
  })

  it('returns a rotated URL without storing it after reactivation', async () => {
    // Fails if a reactivation URL or submitted secret content is retained by the store.
    store.enterProject(1)
    const link = { id: 7, updated_at: '2026-10-01T12:00:00Z' }
    api.post.mockResolvedValue({ data: { url: 'https://example.test/#rotate-fake-token', link: { id: 7, title: 'Database access' }, fields: { password: 'fake-secret-for-test' } } })

    const result = await store.reactivate(link, 3)

    expect(result.data.url).toBe('https://example.test/#rotate-fake-token')
    expect(api.post).toHaveBeenCalledWith('projects/1/secure-links/7/reactivate/', { validity_days: 3, expected_updated_at: '2026-10-01T12:00:00Z' })
    expect(JSON.stringify(store.$state)).not.toContain('rotate-fake-token')
  })
})
