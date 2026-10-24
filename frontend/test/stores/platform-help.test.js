import { createPinia, setActivePinia } from 'pinia'
import { usePlatformHelpStore } from '../../stores/platform-help'
import { usePlatformAuthStore } from '../../stores/platform-auth'
import { usePlatformApi } from '../../composables/usePlatformApi'
jest.mock('../../composables/usePlatformApi', () => ({
  usePlatformApi: jest.fn(), readPlatformSession: jest.fn(), writePlatformSession: jest.fn(), clearPlatformSession: jest.fn(),
}))

const fixture = () => ({ id: 23, revision: 1, context: 'general', status: '', content: { steps: [] } })
describe('platform help account progress', () => {
  let api, store, auth
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    api = { get: jest.fn(), post: jest.fn().mockResolvedValue({ data: {} }) }
    usePlatformApi.mockReturnValue(api)
    auth = usePlatformAuthStore(); auth.user = { id: 41 }; auth.role = 'client'
    store = usePlatformHelpStore()
    api.get.mockResolvedValue({ data: { tour_enabled: true, video_enabled: true, tours: [fixture()] } })
  })
  afterEach(() => { jest.clearAllMocks(); localStorage.clear() })

  it('retains offline dismissal after refreshing the catalog', async () => {
    await store.fetchHelp()
    api.post.mockRejectedValue(new Error('offline'))
    await store.acknowledge(store.tours[0], 'skipped', 'projects')
    await store.fetchHelp()
    expect(store.tours[0].status).toBe('skipped')
  })

  it('retries queued completion after connectivity returns', async () => {
    await store.fetchHelp()
    api.post.mockRejectedValueOnce(new Error('offline'))
    await store.acknowledge(store.tours[0], 'completed', 'help')
    await store.fetchHelp()
    expect(JSON.parse(localStorage.getItem('platform-help-pending:41'))).toEqual({})
    expect(api.post).toHaveBeenLastCalledWith('/api/platform/help/tours/23/progress/', expect.objectContaining({ status: 'completed' }), { baseURL: '' })
  })

  it('keeps another account unseen on a shared browser', async () => {
    await store.fetchHelp()
    api.post.mockRejectedValue(new Error('offline'))
    await store.acknowledge(store.tours[0], 'skipped', 'projects')
    auth.user = { id: 42 }
    await store.fetchHelp()
    expect(store.tours[0].status).toBe('')
  })

  it('ignores a response belonging to the previous account', async () => {
    let resolve
    api.get.mockReturnValue(new Promise((done) => { resolve = done }))
    const request = store.fetchHelp()
    auth.user = { id: 42 }
    store.reset()
    resolve({ data: { tour_enabled: true, tours: [fixture()] } })
    await request
    expect(store.loaded).toBe(false)
    expect(store.tours).toEqual([])
  })

  it('disables automatic tours when configuration cannot be loaded', async () => {
    await store.fetchHelp()
    api.get.mockRejectedValue(new Error('offline'))
    await store.fetchHelp()
    expect(store.tourEnabled).toBe(false)
  })

  it('preserves a terminal state during manual replay', async () => {
    api.get.mockResolvedValue({ data: { tour_enabled: true, tours: [{ ...fixture(), status: 'completed' }] } })
    await store.fetchHelp()
    await store.acknowledge(store.tours[0], 'in_progress', 'welcome', null, true)
    expect(store.tours[0].status).toBe('completed')
  })
})
