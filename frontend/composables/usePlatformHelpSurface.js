import { computed, readonly } from 'vue'

/** One coordinator per Nuxt app; never share client state across SSR requests. */
export function usePlatformHelpSurface() {
  const activeSurface = useState('platform-help-surface', () => null)
  const app = useNuxtApp()
  const handlers = app._platformHelpHandlers ||= new Map()

  function registerSurface(name, onClose) {
    handlers.set(name, onClose)
    return () => {
      if (handlers.get(name) === onClose) handlers.delete(name)
      if (activeSurface.value === name) activeSurface.value = null
    }
  }

  function requestSurface(name) {
    if (activeSurface.value === name) return
    const previous = activeSurface.value
    activeSurface.value = name
    if (previous) handlers.get(previous)?.()
  }

  function releaseSurface(name) {
    if (activeSurface.value === name) activeSurface.value = null
  }

  return {
    activeSurface: readonly(activeSurface),
    isTourActive: computed(() => activeSurface.value === 'tour'),
    registerSurface, requestSurface, releaseSurface,
  }
}
