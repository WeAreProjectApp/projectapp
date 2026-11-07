import { ref } from 'vue'
import { useFolderPanelWidth } from '../../composables/useFolderPanelWidth'

const STORAGE_KEY = 'projectapp-documents-folder-width'
const SECURE_LINKS_STORAGE_KEY = 'projectapp-secure-links-folder-width'

// El contenedor es el div del grid: su borde izquierdo coincide con el del
// panel, así que un clientX de 500 con left=100 pide un ancho de 400px.
function makeContainer() {
  return ref({ getBoundingClientRect: () => ({ left: 100, width: 1000 }) })
}

function pointerEvent(overrides = {}) {
  return {
    pointerId: 7,
    clientX: 0,
    currentTarget: {
      setPointerCapture: jest.fn(),
      releasePointerCapture: jest.fn(),
    },
    ...overrides,
  }
}

function keyEvent(key) {
  return { key, preventDefault: jest.fn() }
}

describe('useFolderPanelWidth', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('defaults to 384px on a clean profile and exposes it as the CSS variable', () => {
    const { width, gridStyle } = useFolderPanelWidth(makeContainer())
    expect(width.value).toBe(384)
    expect(gridStyle.value).toEqual({ '--folders-panel-w': '384px' })
  })

  it('restores a persisted width', () => {
    window.localStorage.setItem(STORAGE_KEY, '400')
    const { width } = useFolderPanelWidth(makeContainer())
    expect(width.value).toBe(400)
  })

  it('clamps an out-of-range stored width on hydration', () => {
    window.localStorage.setItem(STORAGE_KEY, '900')
    const { width, gridStyle } = useFolderPanelWidth(makeContainer())
    expect(width.value).toBe(480)
    expect(gridStyle.value).toEqual({ '--folders-panel-w': '480px' })
  })

  it('falls back to the default when the stored value is not a number', () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify('wide'))
    const { width } = useFolderPanelWidth(makeContainer())
    expect(width.value).toBe(384)
  })

  it('drags the width from the container left edge and persists only on release', () => {
    // quality: allow-too-many-assertions (down→move→up es un solo gesto: cada paso se verifica sobre el estado que dejó el anterior y partirlo duplicaría el setup sin aislar nada)
    const { width, dragging, onHandleDown, onHandleMove, onHandleUp } =
      useFolderPanelWidth(makeContainer())

    // Un move sin pointerdown previo no debe mover nada.
    onHandleMove(pointerEvent({ clientX: 500 }))
    expect(width.value).toBe(384)

    const down = pointerEvent()
    onHandleDown(down)
    expect(dragging.value).toBe(true)

    onHandleMove(pointerEvent({ clientX: 500 }))
    expect(width.value).toBe(400)
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()

    const up = pointerEvent()
    onHandleUp(up)
    expect(dragging.value).toBe(false)
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('400')
  })

  it('clamps the drag at both bounds', () => {
    const { width, onHandleDown, onHandleMove } = useFolderPanelWidth(makeContainer())
    onHandleDown(pointerEvent())
    onHandleMove(pointerEvent({ clientX: 1200 }))
    expect(width.value).toBe(480)
    onHandleMove(pointerEvent({ clientX: 0 }))
    expect(width.value).toBe(240)
  })

  it('resizes with the keyboard, persisting each step, and ignores other keys', () => {
    // quality: allow-too-many-assertions (el contrato de teclado es una tabla ←/→/Home/End/otras sobre el mismo estado encadenado; una aserción por tecla)
    const { width, onHandleKey } = useFolderPanelWidth(makeContainer())

    const right = keyEvent('ArrowRight')
    onHandleKey(right)
    expect(width.value).toBe(400)
    expect(right.preventDefault).toHaveBeenCalled()
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('400')

    onHandleKey(keyEvent('ArrowLeft'))
    expect(width.value).toBe(384)
    onHandleKey(keyEvent('Home'))
    expect(width.value).toBe(240)
    onHandleKey(keyEvent('End'))
    expect(width.value).toBe(480)
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('480')

    const other = keyEvent('Enter')
    onHandleKey(other)
    expect(width.value).toBe(480)
    expect(other.preventDefault).not.toHaveBeenCalled()
  })

  it('reset returns to the default and clears the stored width', () => {
    const { width, onHandleDown, onHandleMove, onHandleUp, resetWidth } =
      useFolderPanelWidth(makeContainer())
    onHandleDown(pointerEvent())
    onHandleMove(pointerEvent({ clientX: 550 }))
    onHandleUp(pointerEvent())
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('450')

    resetWidth()
    expect(width.value).toBe(384)
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('uses the secure-links default independently from the documents panel', () => {
    // Fails if secure links inherits Documents' 384px preference instead of its compact 256px default.
    const { width, gridStyle } = useFolderPanelWidth(makeContainer(), {
      storageKey: SECURE_LINKS_STORAGE_KEY,
      defaultWidth: 256,
    })

    expect(width.value).toBe(256)
    expect(gridStyle.value).toEqual({ '--folders-panel-w': '256px' })
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('resets only the secure-links preference without removing the documents width', () => {
    // Fails if resetting secure links clears the persisted documents navigation width.
    window.localStorage.setItem(STORAGE_KEY, '400')
    window.localStorage.setItem(SECURE_LINKS_STORAGE_KEY, '336')
    const secureLinks = useFolderPanelWidth(makeContainer(), {
      storageKey: SECURE_LINKS_STORAGE_KEY,
      defaultWidth: 256,
    })

    secureLinks.resetWidth()

    expect(secureLinks.width.value).toBe(256)
    expect(window.localStorage.getItem(SECURE_LINKS_STORAGE_KEY)).toBeNull()
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('400')
  })
})
