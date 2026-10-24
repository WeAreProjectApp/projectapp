import { reactive, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import PlatformHelpHost from '../../components/platform/PlatformHelpHost.vue'
import { usePlatformAuthStore } from '../../stores/platform-auth'
import { usePlatformHelpStore } from '../../stores/platform-help'
import { usePlatformGuidedTour, visibleTourTarget } from '../../composables/usePlatformGuidedTour'

jest.mock('../../stores/platform-auth', () => ({ usePlatformAuthStore: jest.fn() }))
jest.mock('../../stores/platform-help', () => ({ usePlatformHelpStore: jest.fn() }))
jest.mock('../../composables/usePlatformGuidedTour', () => ({
  usePlatformGuidedTour: jest.fn(),
  visibleTourTarget: jest.fn(),
}))

const generalTour = { id: 11, context: 'general', status: '' }
const voiceTour = { id: 12, context: 'voice', status: '' }

describe('PlatformHelpHost', () => {
  let wrapper
  let auth
  let store
  let guidedTour
  let help
  let route

  function mountHost() {
    wrapper = mount(PlatformHelpHost, {
      global: {
        provide: { platformHelp: help },
        stubs: { BaseButton: { template: '<button><slot /></button>' } },
      },
    })
  }

  beforeEach(() => {
    route = reactive({ path: '/platform/projects/71/bugs' })
    global.useRoute = () => route
    global.useI18n = () => ({ t: (key) => key })
    auth = reactive({
      user: { id: 41 }, isClient: true, hasValidatedSession: true, needsProfileCompletion: false,
    })
    store = reactive({
      tours: [], tourEnabled: true, videoEnabled: false,
      fetchHelp: jest.fn().mockResolvedValue(true), reset: jest.fn(),
    })
    guidedTour = {
      activeTour: ref(null), completedTour: ref(null), isTourActive: ref(false),
      start: jest.fn().mockResolvedValue(true), pause: jest.fn().mockResolvedValue(undefined),
    }
    help = {
      tour: guidedTour, videoAvailable: ref(false), voiceVisible: ref(false),
      activeSurface: ref(null), openVideo: jest.fn(),
    }
    usePlatformAuthStore.mockReturnValue(auth)
    usePlatformHelpStore.mockReturnValue(store)
    usePlatformGuidedTour.mockReturnValue(guidedTour)
    visibleTourTarget.mockReturnValue(undefined)
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    delete global.useRoute
    delete global.useI18n
    jest.clearAllMocks()
  })

  it.each([
    ['the profile needs completion', { needsProfileCompletion: true }],
    ['the session has not been validated', { hasValidatedSession: false }],
  ])('does not start onboarding guidance while $reason', async (_reason, status) => {
    // Fails if a guidance overlay obscures the required client profile-completion or session-validation flow.
    Object.assign(auth, status)
    store.tours = [generalTour]
    mountHost()
    await flushPromises()

    expect(guidedTour.start).toHaveBeenCalledTimes(0)
    expect(store.fetchHelp).toHaveBeenCalledWith('71')
  })

  it('reinitializes help before refreshing after a session-user change', async () => {
    // Fails if a session replacement keeps the previous client’s active tour or catalog alive.
    mountHost()
    await flushPromises()
    guidedTour.pause.mockClear()
    store.reset.mockClear()
    store.fetchHelp.mockClear()
    guidedTour.start.mockClear()

    auth.user = { id: 42 }
    await flushPromises()

    expect(guidedTour.pause).toHaveBeenCalledTimes(1)
    expect(store.reset).toHaveBeenCalledTimes(1)
    expect(store.fetchHelp).toHaveBeenCalledWith('71')
    expect(guidedTour.pause.mock.invocationCallOrder[0]).toBeLessThan(store.reset.mock.invocationCallOrder[0])
    expect(store.reset.mock.invocationCallOrder[0]).toBeLessThan(store.fetchHelp.mock.invocationCallOrder[0])
    expect(guidedTour.start).toHaveBeenCalledTimes(0)
  })

  it.each([
    ['a visible voice recording control', true, 12],
    ['no voice recording control', false, 11],
  ])('selects the expected automatic guide with $visibility', async (_visibility, voiceVisible, expectedTourId) => {
    // Fails if voice help starts without its recording control or loses priority when the control is present.
    store.tours = [generalTour, voiceTour]
    visibleTourTarget.mockImplementation((key) => key === 'voice-report' && voiceVisible ? document.createElement('button') : undefined)
    mountHost()
    await flushPromises()

    expect(guidedTour.start).toHaveBeenCalledWith(expectedTourId, { projectId: '71', manual: false })
  })
})
