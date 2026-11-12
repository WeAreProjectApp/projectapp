import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { usePlatformGuidedTour } from '../../composables/usePlatformGuidedTour'
import { usePlatformHelpStore } from '../../stores/platform-help'
import { usePlatformSidebar } from '../../composables/usePlatformSidebar'
import { usePlatformHelpSurface } from '../../composables/usePlatformHelpSurface'
import { usePlatformTheme } from '../../composables/usePlatformTheme'

jest.mock('vue', () => {
  const actual = jest.requireActual('vue')
  return { ...actual, nextTick: (...args) => globalThis.__platformTourNextTick(...args) }
})
jest.mock('../../stores/platform-help', () => ({ usePlatformHelpStore: jest.fn() }))
jest.mock('../../composables/usePlatformSidebar', () => ({ usePlatformSidebar: jest.fn() }))
jest.mock('../../composables/usePlatformHelpSurface', () => ({ usePlatformHelpSurface: jest.fn() }))
jest.mock('../../composables/usePlatformTheme', () => ({ usePlatformTheme: jest.fn() }))
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

function restoreGlobal(name, value) {
  if (value === undefined) delete globalThis[name]
  else globalThis[name] = value
}

function restoreWindowProperty(name, descriptor) {
  if (descriptor === undefined) delete window[name]
  else Object.defineProperty(window, name, descriptor)
}

describe('usePlatformGuidedTour', () => {
  let mounted = []
  let tour
  let store
  let sidebar
  let surface
  let driver
  let originalCSS
  let originalUseI18n
  let originalDriverFactory
  let originalNextTick
  let originalMatchMedia
  let originalScrollTo
  let originalScrollX
  let originalScrollY
  let originalResizeObserver
  let originalRequestAnimationFrame
  let originalCancelAnimationFrame

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
    originalCSS = globalThis.CSS
    originalUseI18n = globalThis.useI18n
    originalDriverFactory = globalThis.__platformDriverFactory
    originalNextTick = globalThis.__platformTourNextTick
    originalMatchMedia = Object.getOwnPropertyDescriptor(window, 'matchMedia')
    originalScrollTo = Object.getOwnPropertyDescriptor(window, 'scrollTo')
    originalScrollX = Object.getOwnPropertyDescriptor(window, 'scrollX')
    originalScrollY = Object.getOwnPropertyDescriptor(window, 'scrollY')
    originalResizeObserver = globalThis.ResizeObserver
    originalRequestAnimationFrame = Object.getOwnPropertyDescriptor(window, 'requestAnimationFrame')
    originalCancelAnimationFrame = Object.getOwnPropertyDescriptor(window, 'cancelAnimationFrame')
    global.CSS = { escape: (value) => value }
    globalThis.__platformTourNextTick = jest.fn().mockResolvedValue(undefined)
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
    usePlatformTheme.mockReturnValue({ isDark: ref(false) })
    globalThis.__platformDriverFactory = jest.fn().mockReturnValue(driver)
  })

  afterEach(() => {
    mounted.forEach((wrapper) => wrapper.unmount())
    document.body.innerHTML = ''
    restoreGlobal('CSS', originalCSS)
    restoreGlobal('useI18n', originalUseI18n)
    restoreGlobal('__platformDriverFactory', originalDriverFactory)
    restoreGlobal('__platformTourNextTick', originalNextTick)
    restoreWindowProperty('matchMedia', originalMatchMedia)
    restoreWindowProperty('scrollTo', originalScrollTo)
    restoreWindowProperty('scrollX', originalScrollX)
    restoreWindowProperty('scrollY', originalScrollY)
    restoreGlobal('ResizeObserver', originalResizeObserver)
    restoreWindowProperty('requestAnimationFrame', originalRequestAnimationFrame)
    restoreWindowProperty('cancelAnimationFrame', originalCancelAnimationFrame)
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
    expect(store.acknowledge).toHaveBeenLastCalledWith(expect.objectContaining({ id: 17 }), 'skipped', 'projects', null, true)
  })

  it('exposes a project destination behind the mobile Help drawer', async () => {
    // Fails if opening a project guide leaves the global drawer covering Summary.
    addTarget('project-summary')
    window.matchMedia = jest.fn().mockImplementation((query) => ({ matches: query === '(max-width: 767px)' }))
    sidebar.isMobileOpen.value = true
    store.tours = [{ ...tourFixture([step('project-summary')]), context: 'project' }]
    mountHarness()

    await tour.start(17, { projectId: 71 })

    expect(sidebar.isMobileOpen.value).toBe(false)
    expect(tour.activeTour.value.id).toBe(17)
  })

  it('keeps the visible menu destination across repeated breakpoint measurements', async () => {
    // Driver returns a resolved active-step copy but re-reads configured steps on drive().
    const desktopTarget = addTarget('projects')
    const mobileTarget = addTarget('projects')
    mobileTarget.getClientRects = () => []
    const frames = []
    window.requestAnimationFrame = jest.fn((callback) => { frames.push(callback); return frames.length })
    window.cancelAnimationFrame = jest.fn()
    driver.refresh = jest.fn()
    driver.getActiveElement = jest.fn().mockReturnValue(desktopTarget)
    store.tours = [tourFixture([step('projects')])]
    mountHarness()
    await tour.start(17)
    const config = globalThis.__platformDriverFactory.mock.calls[0][0]
    driver.getConfig = jest.fn().mockReturnValue(config)
    driver.getActiveStep = jest.fn().mockReturnValue({ ...config.steps[0] })
    desktopTarget.getClientRects = () => []
    mobileTarget.getClientRects = () => [{ width: 24, height: 24 }]
    window.matchMedia = jest.fn().mockImplementation((query) => ({ matches: query === '(max-width: 767px)' }))

    window.dispatchEvent(new Event('resize'))
    await frames.shift()()
    window.dispatchEvent(new Event('resize'))
    await frames.shift()()

    expect(config.steps[0].element).toBe(mobileTarget)
    expect(driver.drive).toHaveBeenCalledTimes(2)
    expect(driver.refresh).toHaveBeenCalledTimes(1)
  })

  it('releases pending layout work when the guide closes', async () => {
    // Fails if a closed guide keeps a DOM observer or queued measurement alive.
    const observed = new Set()
    const frames = new Map()
    globalThis.ResizeObserver = jest.fn(() => ({
      observe: (element) => observed.add(element),
      unobserve: (element) => observed.delete(element),
      disconnect: () => observed.clear(),
    }))
    window.requestAnimationFrame = jest.fn((callback) => { frames.set(1, callback); return 1 })
    window.cancelAnimationFrame = jest.fn((frame) => frames.delete(frame))
    const target = addTarget('projects')
    store.tours = [tourFixture([step('projects')])]
    mountHarness()
    await tour.start(17)
    expect(observed.has(target)).toBe(true)
    window.dispatchEvent(new Event('resize'))
    expect(frames.size).toBe(1)

    await tour.cancel()

    expect(observed.size).toBe(0)
    expect(frames.size).toBe(0)
  })

  it('cancels a run paused while a navigation target is being prepared', async () => {
    // Fails if a route change during target preparation opens Driver after the user has already left the tour.
    let releaseTargetPreparation
    let targetPreparationReached
    const targetPreparation = new Promise((resolve) => { releaseTargetPreparation = resolve })
    const targetPreparationReachedPromise = new Promise((resolve) => { targetPreparationReached = resolve })
    globalThis.__platformTourNextTick.mockImplementationOnce(() => {
      targetPreparationReached()
      return targetPreparation
    })
    window.matchMedia = jest.fn().mockImplementation((query) => ({ matches: query === '(max-width: 767px)' }))
    store.tours = [tourFixture([step('projects')])]
    mountHarness()

    const starting = tour.start(17)
    await targetPreparationReachedPromise
    await tour.pause()
    releaseTargetPreparation()

    await expect(starting).resolves.toBe(false)
    expect(globalThis.__platformDriverFactory).toHaveBeenCalledTimes(0)
    expect(sidebar.isMobileOpen.value).toBe(false)
  })

  it('does not open Driver when a start is paused in the same turn', async () => {
    // Fails if start captures its cancellation token after a same-turn pause and opens a stale guide.
    mountHarness()

    const starting = tour.start(17)
    await tour.pause()

    await expect(starting).resolves.toBe(false)
    expect(globalThis.__platformDriverFactory).toHaveBeenCalledTimes(0)
    expect(store.fetchHelp).toHaveBeenCalledTimes(0)
  })

  it('does not drive a next step after the active tour is paused', async () => {
    // Fails if a delayed catalog refresh advances a Driver instance after its tour was paused.
    let releaseRefresh
    let refreshRequested
    const refresh = new Promise((resolve) => { releaseRefresh = resolve })
    const refreshRequestedPromise = new Promise((resolve) => { refreshRequested = resolve })
    addTarget('projects')
    store.tours = [tourFixture([step('welcome'), step('projects')])]
    mountHarness()
    await tour.start(17)
    store.fetchHelp.mockImplementationOnce(() => {
      refreshRequested()
      return refresh
    })

    globalThis.__platformDriverFactory.mock.calls[0][0].onNextClick()
    await refreshRequestedPromise
    await tour.pause()
    releaseRefresh(true)
    await flushPromises()

    expect(driver.drive).toHaveBeenCalledTimes(1)
    expect(store.acknowledge).toHaveBeenLastCalledWith(expect.objectContaining({ id: 17 }), 'paused', 'welcome', null, true)
  })

  it('acknowledges welcome when cancellation precedes Driver highlighting', async () => {
    mountHarness()

    await tour.start(17)
    await tour.cancel()

    expect(store.acknowledge).toHaveBeenLastCalledWith(expect.objectContaining({ id: 17 }), 'skipped', 'welcome', null, true)
  })

  it('acknowledges the final destination when completion precedes Driver highlighting', async () => {
    addTarget('projects')
    store.tours = [tourFixture([step('welcome'), step('projects')])]
    mountHarness()

    await tour.start(17)
    const options = globalThis.__platformDriverFactory.mock.calls[0][0]
    options.onNextClick()
    await flushPromises()
    options.onDoneClick()
    await flushPromises()

    expect(driver.drive).toHaveBeenLastCalledWith(1)
    expect(store.acknowledge).toHaveBeenLastCalledWith(expect.objectContaining({ id: 17 }), 'completed', 'projects', null, true)
  })
})
