import { ref } from 'vue'
import { usePlatformHelpSurface } from '../../composables/usePlatformHelpSurface'

describe('platform help surfaces', () => {
  beforeEach(() => {
    const state = ref(null), app = {}
    global.useState = () => state
    global.useNuxtApp = () => app
  })
  afterEach(() => { delete global.useState; delete global.useNuxtApp })

  it('pauses the previous surface when chat is opened', () => {
    const surface = usePlatformHelpSurface()
    const playingTour = ref(true)
    surface.registerSurface('tour', () => { playingTour.value = false })
    surface.requestSurface('tour')
    surface.requestSurface('chat')
    expect(playingTour.value).toBe(false)
    expect(surface.activeSurface.value).toBe('chat')
  })

  it('keeps the new surface active when the old one releases', () => {
    const surface = usePlatformHelpSurface()
    surface.registerSurface('tour', () => surface.releaseSurface('tour'))
    surface.requestSurface('tour')
    surface.requestSurface('video')
    expect(surface.activeSurface.value).toBe('video')
  })

  it('shares coordination inside a Nuxt app', () => {
    const tour = usePlatformHelpSurface(), chat = usePlatformHelpSurface()
    tour.requestSurface('tour')
    expect(chat.isTourActive.value).toBe(true)
    chat.releaseSurface('tour')
    expect(tour.isTourActive.value).toBe(false)
  })
})
