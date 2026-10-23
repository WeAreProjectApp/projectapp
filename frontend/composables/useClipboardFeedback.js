import { getCurrentScope, onScopeDispose, reactive } from 'vue'

const DEFAULT_SUCCESS_DURATION = 2_000
const DEFAULT_ERROR_DURATION = 3_000
const EMPTY_FEEDBACK = Object.freeze({ label: '', tone: 'info' })

/**
 * Confirm clipboard writes beside their originating control.
 *
 * Keys keep repeated/list controls independent. Consumer copy stays local so
 * public bilingual surfaces and panel notifications can use their own wording.
 */
export function useClipboardFeedback({
  successDuration = DEFAULT_SUCCESS_DURATION,
  errorDuration = DEFAULT_ERROR_DURATION,
} = {}) {
  const feedbackByKey = reactive({})
  const timers = new Map()

  function clearFeedback(key) {
    const timer = timers.get(key)
    if (timers.has(key)) clearTimeout(timer)
    timers.delete(key)
    delete feedbackByKey[key]
  }

  function clearAllFeedback() {
    timers.forEach(clearTimeout)
    timers.clear()
    Object.keys(feedbackByKey).forEach((key) => delete feedbackByKey[key])
  }

  function setFeedback(key, label, tone, duration) {
    clearFeedback(key)
    feedbackByKey[key] = { label, tone }
    timers.set(key, setTimeout(() => clearFeedback(key), duration))
  }

  async function copyText({
    key = 'default',
    text,
    successLabel = 'Copiado',
    errorLabel = 'No se pudo copiar',
    onError,
    write,
  }) {
    try {
      if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) {
        throw new Error('Clipboard API unavailable')
      }
      if (write) await write()
      else await navigator.clipboard.writeText(String(text ?? ''))
      setFeedback(key, successLabel, 'success', successDuration)
      return true
    } catch (error) {
      setFeedback(key, errorLabel, 'danger', errorDuration)
      onError?.(error)
      return false
    }
  }

  function feedbackFor(key = 'default') {
    return feedbackByKey[key] || EMPTY_FEEDBACK
  }

  if (getCurrentScope()) onScopeDispose(clearAllFeedback)

  return {
    clearAllFeedback,
    clearFeedback,
    copyText,
    feedbackFor,
  }
}

export default useClipboardFeedback
