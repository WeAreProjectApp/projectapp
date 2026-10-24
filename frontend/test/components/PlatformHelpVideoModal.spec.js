import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive, ref } from 'vue'
import PlatformHelpVideoModal from '../../components/platform/PlatformHelpVideoModal.vue'
import { usePlatformHelpVideosStore } from '../../stores/platform-help-videos'
import { usePlatformApi } from '../../composables/usePlatformApi'

const mockRoute = reactive({ fullPath: '/es-co/platform/projects' })
const mockStates = {}
let mockNuxtApp
jest.mock('#imports', () => ({
  useRoute: () => mockRoute,
  useI18n: () => ({ t: (key) => {
    const es = jest.requireActual('../../locales/platformVideos/es').default
    return es[key.replace('platformVideos.', '')] || key
  } }),
}))
jest.mock('../../composables/usePlatformApi', () => ({ usePlatformApi: jest.fn() }))
jest.mock('../../composables/useExplainerVideos', () => ({
  explainerVideoFor: (module) => ({ src: `/${module}.mp4`, durationSeconds: 90 }),
  formatExplainerDuration: () => '1:30',
}))
global.useState = (key, init) => mockStates[key] ||= ref(init())
global.useNuxtApp = () => mockNuxtApp

const catalog = { data: { enabled: true, videos: [
  { topic: 'general', module: 'platform-overview', language: 'es', resource: { mode: 'default' } },
  { topic: 'chatbot', module: 'platform-chatbot', language: 'es', resource: { mode: 'default' } },
] } }
const stubs = {
  BaseModal: { props: ['modelValue'], template: '<div v-if="modelValue" role="dialog"><slot /></div>' },
  BaseButton: { template: '<button v-bind="$attrs"><slot /></button>' },
  BaseAlert: { template: '<p role="alert"><slot /></p>' },
}

describe('platform video modal', () => {
  let wrapper
  let store
  let pause
  let play
  let registerVideo
  let closeChat
  beforeEach(async () => {
    setActivePinia(createPinia())
    Object.keys(mockStates).forEach((key) => delete mockStates[key])
    mockNuxtApp = {}
    mockRoute.fullPath = '/es-co/platform/projects'
    pause = jest.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
    play = jest.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
    usePlatformApi.mockReturnValue({ get: jest.fn().mockResolvedValue(catalog) })
    store = usePlatformHelpVideosStore()
    registerVideo = jest.fn()
    wrapper = mount(PlatformHelpVideoModal, { global: { stubs, provide: { platformHelp: { registerVideo } } } })
    await flushPromises()
    closeChat = jest.fn()
    mockNuxtApp._platformHelpHandlers.set('chat', closeChat)
    mockStates['platform-help-surface'].value = 'chat'
    await store.openVideo()
    await flushPromises()
  })
  afterEach(() => { wrapper.unmount(); jest.restoreAllMocks() })

  it('waits for explicit playback after opening help', () => {
    const video = wrapper.get('video')
    expect(video.attributes('autoplay')).toBeUndefined()
    expect(video.attributes('preload')).toBe('none')
    expect(play).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Video en español')
  })

  it('stops the player when the user closes the modal', async () => {
    await wrapper.get('[data-testid="platform-video-close"]').trigger('click')
    expect(pause).toHaveBeenCalled()
    expect(wrapper.find('video').exists()).toBe(false)
  })

  it('changes to the clip selected by the user', async () => {
    await wrapper.get('[data-testid="platform-video-topic-chatbot"]').trigger('click')
    expect(wrapper.get('video').attributes('src')).toBe('/platform-chatbot.mp4')
    expect(pause).toHaveBeenCalled()
    expect(play).not.toHaveBeenCalled()
  })

  it('offers a retry after media failure', async () => {
    await wrapper.get('video').trigger('error')
    expect(wrapper.get('[role="alert"]').text()).toContain('No pudimos reproducir')
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('recovers after the requested catalog cannot be loaded', async () => {
    await wrapper.get('[data-testid="platform-video-close"]').trigger('click')
    usePlatformApi.mockReturnValue({ get: jest.fn().mockRejectedValue(new Error('Network unavailable')) })
    await registerVideo.mock.calls.at(-1)[0]()
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('No pudimos cargar los videos')
    usePlatformApi.mockReturnValue({ get: jest.fn().mockResolvedValue(catalog) })
    await wrapper.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(wrapper.find('video').exists()).toBe(true)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('stops playback when navigating to another view', async () => {
    mockRoute.fullPath = '/es-co/platform/notifications'
    await flushPromises()
    expect(pause).toHaveBeenCalled()
    expect(wrapper.find('video').exists()).toBe(false)
  })

  it('closes the previous help surface before showing video', () => {
    expect(closeChat).toHaveBeenCalledTimes(1)
    expect(mockStates['platform-help-surface'].value).toBe('video')
    expect(registerVideo).toHaveBeenCalledWith(expect.any(Function), true)
  })
})
