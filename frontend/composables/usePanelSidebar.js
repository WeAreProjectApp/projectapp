import { computed, ref } from 'vue'
import { PANEL_BREAKPOINTS } from '~/config/responsive'

const STORAGE_KEY = 'panel_sidebar_collapsed'
const MOBILE_BREAKPOINT = PANEL_BREAKPOINTS.landscape
const EXPANDED_BREAKPOINT = PANEL_BREAKPOINTS.desktop
export const PANEL_SIDEBAR_MIN = 200
export const PANEL_SIDEBAR_MAX = 400
export const PANEL_SIDEBAR_DEFAULT = 240
export const PANEL_SIDEBAR_WIDTH_KEY = 'projectapp-panel-sidebar-width'

const isCollapsed = ref(false)
const isMobileOpen = ref(false)
const expandedWidth = ref(PANEL_SIDEBAR_DEFAULT)
const isResizing = ref(false)

function clampWidth(value) {
  const width = Number(value)
  return Number.isFinite(width) && width > 0
    ? Math.min(PANEL_SIDEBAR_MAX, Math.max(PANEL_SIDEBAR_MIN, width))
    : PANEL_SIDEBAR_DEFAULT
}

function isClient() {
  return typeof window !== 'undefined'
}

/**
 * Collapsible sidebar + mobile drawer state for the internal admin panel (mirrors usePlatformSidebar API).
 */
export function usePanelSidebar() {
  function hydrate() {
    if (!isClient()) return
    let stored = null
    let storedWidth = null
    try {
      stored = localStorage.getItem(STORAGE_KEY)
      storedWidth = localStorage.getItem(PANEL_SIDEBAR_WIDTH_KEY)
    } catch (_error) { /* Navigation remains available when storage is blocked. */ }
    expandedWidth.value = clampWidth(storedWidth)
    if (stored === 'true') {
      isCollapsed.value = true
    } else if (stored === 'false') {
      isCollapsed.value = false
    } else {
      // Tablet landscape keeps the desktop navigation available but collapsed;
      // a laptop and larger starts expanded.
      isCollapsed.value = window.innerWidth < EXPANDED_BREAKPOINT
    }
  }

  const layoutStyle = computed(() => ({
    '--panel-sidebar-width': `${isCollapsed.value ? 64 : expandedWidth.value}px`,
  }))

  function persistWidth() {
    if (!isClient()) return
    try {
      localStorage.setItem(PANEL_SIDEBAR_WIDTH_KEY, String(expandedWidth.value))
    } catch (_error) { /* The current layout remains usable without storage. */ }
  }

  function startResize() {
    if (!isCollapsed.value) isResizing.value = true
  }

  function moveResize(event) {
    if (isResizing.value) expandedWidth.value = clampWidth(event.clientX)
  }

  function endResize() {
    if (!isResizing.value) return
    isResizing.value = false
    persistWidth()
  }

  function resizeWidth(value) {
    expandedWidth.value = clampWidth(value)
    persistWidth()
  }

  function resetWidth() {
    expandedWidth.value = PANEL_SIDEBAR_DEFAULT
    if (!isClient()) return
    try {
      localStorage.removeItem(PANEL_SIDEBAR_WIDTH_KEY)
    } catch (_error) { /* Storage is optional. */ }
  }

  function toggle() {
    endResize()
    isCollapsed.value = !isCollapsed.value
    if (isClient()) {
      localStorage.setItem(STORAGE_KEY, String(isCollapsed.value))
    }
  }

  function collapse() {
    endResize()
    isCollapsed.value = true
    if (isClient()) {
      localStorage.setItem(STORAGE_KEY, 'true')
    }
  }

  function expand() {
    endResize()
    isCollapsed.value = false
    if (isClient()) {
      localStorage.setItem(STORAGE_KEY, 'false')
    }
  }

  function openMobile() {
    isMobileOpen.value = true
  }

  function closeMobile() {
    isMobileOpen.value = false
  }

  function toggleMobile() {
    isMobileOpen.value = !isMobileOpen.value
  }

  function handleResize() {
    /* c8 ignore next */
    if (!isClient()) return
    if (window.innerWidth < MOBILE_BREAKPOINT) endResize()
    if (window.innerWidth >= MOBILE_BREAKPOINT) {
      isMobileOpen.value = false
    }
  }

  function setupResizeListener() {
    if (!isClient()) return
    window.addEventListener('resize', handleResize)
  }

  function cleanupResizeListener() {
    if (!isClient()) return
    endResize()
    window.removeEventListener('resize', handleResize)
  }

  return {
    isCollapsed,
    isMobileOpen,
    expandedWidth,
    isResizing,
    layoutStyle,
    startResize,
    moveResize,
    endResize,
    resizeWidth,
    resetWidth,
    hydrate,
    toggle,
    collapse,
    expand,
    openMobile,
    closeMobile,
    toggleMobile,
    setupResizeListener,
    cleanupResizeListener,
  }
}
