import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { usePlatformGuidedTour } from '../../composables/usePlatformGuidedTour'
import { usePlatformHelpStore } from '../../stores/platform-help'
import { usePlatformSidebar } from '../../composables/usePlatformSidebar'
import { usePlatformHelpSurface } from '../../composables/usePlatformHelpSurface'

jest.mock('../../stores/platform-help', () => ({ usePlatformHelpStore: jest.fn() }))
jest.mock('../../composables/usePlatformSidebar', () => ({ usePlatformSidebar: jest.fn() }))
jest.mock('../../composables/usePlatformHelpSurface', () => ({ usePlatformHelpSurface: jest.fn() }))
jest.mock('driver.js', () => ({ driver: (...args) => globalThis.__platformDriverFactory(...args) }))
const tourFixture = (steps) => ({
  id: 17,
  revision: 3,
  status: '',
  context: 'general',
  last_step: '',
  content: { title_es: 'Conoce la plataforma', steps },
})
const step = (target) => ({
  target,
  title_es: target === 'welcome' ? 'Bienvenida' : 'Proyectos',
  description_es: target === 'welcome' ? 'Te mostramos la plataforma.' : 'Encuentra tus proyectos aquí.',
})

describe('usePlatformGuidedTour', () => {
  let mounted = []
  let tour
  let store
  let sidebar
  let surface
  let driver

  function mountHarness() {
    const wrapper = mount(defineComponent({
      setup() {
        tour = usePlatformGuidedTour()
        return () => h('div')
      },
    }))
    mounted.push(wrapper)
  }

  function addTarget(key) {
    const target = document.createElement('button')
    target.setAttribute('data-tour', key)
    target.getClientRects = () => [{ width: 24, height: 24 }]
    target.scrollIntoView = jest.fn()
    document.body.appendChild(target)
    return target
  }

  beforeEach(() => {
    mounted = []
    document.body.innerHTML = ''
    global.CSS = { escape: (value) => value }
    global.useI18n = () => ({ t: (key) => key, locale: ref('es-CO') })
    window.matchMedia = jest.fn().mockReturnValue({ matches: false })
    window.scrollTo = jest.fn()
    Object.defineProperties(window, {
      scrollX: { configurable: true, value: 31 },
      scrollY: { configurable: true, value: 47 },
    })
    store = {
      fetchHelp: jest.fn().mockResolvedValue(true),
      acknowledge: jest.fn().mockResolvedValue(undefined),
      tourEnabled: true,
      tours: [tourFixture([step('welcome')])],
    }
    sidebar = { isMobileOpen: ref(false), isCollapsed: ref(true) }
    surface = {
      requestSurface: jest.fn(),
      releaseSurface: jest.fn(),
      registerSurface: jest.fn().mockReturnValue(jest.fn()),
      isTourActive: ref(false),
    }
    driver = { drive: jest.fn(), destroy: jest.fn(), getActiveIndex: jest.fn().mockReturnValue(0) }
    usePlatformHelpStore.mockReturnValue(store)
    usePlatformSidebar.mockReturnValue(sidebar)
    usePlatformHelpSurface.mockReturnValue(surface)
    globalThis.__platformDriverFactory = jest.fn().mockReturnValue(driver)
  })

  afterEach(() => {
    mounted.forEach((wrapper) => wrapper.unmount())
    document.body.innerHTML = ''
    delete global.useI18n
    delete globalThis.__platformDriverFactory
    jest.clearAllMocks()
  })

  it('starts a welcome-only tour after excluding a missing navigation target', async () => {
    // Fails if an unavailable navigation control is handed to Driver as a broken highlight.
    store.tours = [tourFixture([step('welcome'), step('documents')])]
    mountHarness()

    await expect(tour.start(17)).resolves.toBe(true)

    expect(globalThis.__platformDriverFactory).toHaveBeenCalledTimes(1)
    expect(globalThis.__platformDriverFactory.mock.calls[0][0].steps).toEqual([
      expect.objectContaining({ targetKey: 'welcome', element: undefined }),
    ])
    expect(driver.drive).toHaveBeenCalledWith(0)
  })

  it('restores the pre-tour mobile screen snapshot after closing', async () => {
    // Fails if closing a mobile navigation tour leaves the drawer, viewport, or keyboard focus displaced.
    const returnFocus = document.createElement('button')
    returnFocus.setAttribute('aria-label', 'Volver a la página')
    document.body.appendChild(returnFocus)
    returnFocus.focus()
    addTarget('projects')
    window.matchMedia = jest.fn().mockImplementation((query) => ({ matches: query === '(max-width: 767px)' }))
    store.tours = [tourFixture([step('projects')])]
    mountHarness()

    await tour.start(17)
    globalThis.__platformDriverFactory.mock.calls[0][0].onCloseClick()
    await flushPromises()

    expect(sidebar.isMobileOpen.value).toBe(false)
    expect(sidebar.isCollapsed.value).toBe(true)
    expect(window.scrollTo).toHaveBeenLastCalledWith(31, 47)
    expect(document.activeElement.getAttribute('aria-label')).toBe('Volver a la página')
    expect(store.acknowledge).toHaveBeenLastCalledWith(expect.objectContaining({ id: 17 }), 'skipped', '', null, true)
  })
})
