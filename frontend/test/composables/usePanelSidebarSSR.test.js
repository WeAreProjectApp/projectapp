/**
 * @jest-environment node
 *
 * Tests for usePanelSidebar SSR branches (window undefined).
 */

describe('usePanelSidebar (SSR — window undefined)', () => {
  let usePanelSidebar

  beforeEach(() => {
    jest.resetModules()
    // Mock vue to avoid ESM import issues in Node env
    jest.doMock('vue', () => ({
      ref: (v) => ({ value: v }),
      computed: (getter) => ({ get value() { return getter() } }),
      onMounted: jest.fn(),
      onUnmounted: jest.fn(),
    }))
    usePanelSidebar = require('../../composables/usePanelSidebar').usePanelSidebar
  })

  it('hydrate returns early when window is undefined', () => {
    const { hydrate, isCollapsed } = usePanelSidebar()
    isCollapsed.value = true
    hydrate()
    expect(isCollapsed.value).toBe(true)
  })

  it('setupResizeListener returns early when window is undefined', () => {
    const { setupResizeListener } = usePanelSidebar()
    expect(() => setupResizeListener()).not.toThrow()
  })

  it('cleanupResizeListener returns early when window is undefined', () => {
    const { cleanupResizeListener } = usePanelSidebar()
    expect(() => cleanupResizeListener()).not.toThrow()
  })
})
