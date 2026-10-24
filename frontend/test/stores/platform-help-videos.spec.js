import { createPinia, setActivePinia } from 'pinia'
import { usePlatformHelpVideosStore } from '../../stores/platform-help-videos'
import { usePlatformApi } from '../../composables/usePlatformApi'

jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
jest.mock('../../composables/useExplainerVideos', () => ({
  explainerVideoFor: (module) => ({ src: `/${module}.mp4`, poster: '/poster.webp', durationSeconds: 90 }),
}))

const general = { topic: 'general', module: 'platform-overview', language: 'es', resource: { mode: 'default', video: null } }
const response = (videos = [general], enabled = true) => ({ data: { enabled, videos } })

describe('platform help videos', () => {
  let get
  let store
  beforeEach(() => {
    setActivePinia(createPinia())
    get = jest.fn().mockResolvedValue(response())
    usePlatformApi.mockReturnValue({ get })
    store = usePlatformHelpVideosStore()
  })
  afterEach(() => jest.restoreAllMocks())

  it('fetches metadata without opening the player', async () => {
    await store.fetchVideos()
    expect(store.videoAvailable).toBe(true)
    expect(store.isOpen).toBe(false)
    expect(get).toHaveBeenCalledWith('/api/platform/help/videos/', { baseURL: '' })
  })

  it('opens the requested available topic after refresh', async () => {
    const opened = await store.openVideo()
    expect(opened).toBe(true)
    expect(store.selectedVideo.src).toBe('/platform-overview.mp4')
    expect(store.isOpen).toBe(true)
  })

  it('refuses a topic omitted by the server', async () => {
    expect(await store.openVideo('chatbot')).toBe(false)
    expect(store.isOpen).toBe(false)
  })

  it('offers another available piece when general was retired', async () => {
    get.mockResolvedValue(response([{ ...general, topic: 'chatbot', module: 'platform-chatbot' }]))
    await store.openVideo()
    expect(store.selectedTopic).toBe('chatbot')
    expect(store.isOpen).toBe(true)
  })

  it('uses the uploaded replacement descriptor', async () => {
    get.mockResolvedValue(response([{ ...general, resource: { mode: 'uploaded', video: { src: '/revision-2.mp4', durationSeconds: 32 } } }]))
    await store.openVideo()
    expect(store.selectedVideo.src).toBe('/revision-2.mp4')
  })

  it('closes a video whose visibility was revoked', async () => {
    await store.openVideo()
    get.mockResolvedValue(response([], false))
    await store.fetchVideos()
    expect(store.isOpen).toBe(false)
    expect(store.videoAvailable).toBe(false)
  })

  it('clears the catalog after a rejected request', async () => {
    await store.openVideo()
    get.mockRejectedValue(new Error('Network unavailable'))
    await store.fetchVideos()
    expect(store.isOpen).toBe(false)
    expect(store.videoAvailable).toBe(false)
    expect(store.error).toBe(true)
  })

  it('ignores a late response after closing help', async () => {
    let resolve
    get.mockReturnValue(new Promise((done) => { resolve = done }))
    const pending = store.openVideo()
    store.closeVideo()
    resolve(response())
    expect(await pending).toBe(false)
    expect(store.isOpen).toBe(false)
  })

  it('clears client video metadata on logout', async () => {
    await store.openVideo()
    store.reset()
    expect(store.resources).toEqual([])
    expect(store.isOpen).toBe(false)
  })
})
