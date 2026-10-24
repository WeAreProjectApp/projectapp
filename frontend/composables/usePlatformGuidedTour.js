import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { usePlatformHelpStore } from '~/stores/platform-help'
import { usePlatformSidebar } from '~/composables/usePlatformSidebar'
import { usePlatformHelpSurface } from '~/composables/usePlatformHelpSurface'
import { usePlatformTheme } from '~/composables/usePlatformTheme'

export function visibleTourTarget(key) {
  return [...document.querySelectorAll(`[data-tour="${CSS.escape(key)}"]`)]
    .find((element) => element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden')
}

/** Driver is client-only and loaded on demand. Copy always enters through textContent. */
export function usePlatformGuidedTour() {
  const store = usePlatformHelpStore()
  const sidebar = usePlatformSidebar()
  const surface = usePlatformHelpSurface()
  const { isDark } = usePlatformTheme()
  const { t, locale } = useI18n()
  const activeTour = ref(null)
  const completedTour = ref(null)
  const currentStep = ref('')
  let driver = null
  let snapshot = null
  let ending = false
  let manualRun = false
  let runProject = null
  let runToken = 0
  let unregister = null

  const language = computed(() => locale.value.startsWith('en') ? 'en' : 'es')

  function restore() {
    if (!snapshot) return
    sidebar.isMobileOpen.value = snapshot.mobile
    sidebar.isCollapsed.value = snapshot.collapsed
    window.scrollTo(snapshot.scrollX, snapshot.scrollY)
    snapshot.focus?.focus?.({ preventScroll: true })
    snapshot = null
  }

  async function finish(status) {
    if (ending || !activeTour.value) return
    ending = true
    runToken += 1
    const tour = activeTour.value
    const step = currentStep.value
    if (status === 'completed') completedTour.value = tour
    activeTour.value = null
    driver?.destroy()
    driver = null
    surface.releaseSurface('tour')
    unregister?.()
    unregister = null
    restore()
    ending = false
    await store.acknowledge(tour, status, step, runProject, manualRun)
  }

  function pause() {
    runToken += 1
    if (!activeTour.value) restore()
    return finish('paused')
  }

  async function prepareTarget(key) {
    const globalNav = ['projects', 'documents', 'collection-accounts', 'hosting', 'notifications', 'profile', 'help'].includes(key)
    if (globalNav) {
      if (window.matchMedia('(max-width: 767px)').matches) sidebar.isMobileOpen.value = true
      else sidebar.isCollapsed.value = false
    } else if (snapshot) sidebar.isMobileOpen.value = snapshot.mobile
    await nextTick()
    const target = visibleTourTarget(key)
    target?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'instant' })
    return target
  }

  async function start(tourId, { projectId = null, manual = true } = {}) {
    completedTour.value = null
    await pause()
    const token = ++runToken
    if (!await store.fetchHelp(projectId) || !store.tourEnabled || token !== runToken) return false
    const tour = store.tours.find((item) => item.id === tourId)
    if (!tour || (!manual && ['completed', 'skipped', 'paused'].includes(tour.status))) return false
    const { driver: createDriver } = await import('driver.js')
    await import('driver.js/dist/driver.css')
    if (token !== runToken) return false
    snapshot = { mobile: sidebar.isMobileOpen.value, collapsed: sidebar.isCollapsed.value,
      focus: document.activeElement, scrollX: window.scrollX, scrollY: window.scrollY }
    manualRun = manual
    runProject = projectId
    // Global navigation is opened before measuring, while project tabs already exist.
    const steps = []
    for (const step of tour.content.steps) {
      const element = step.target === 'welcome' ? null : await prepareTarget(step.target)
      if (token !== runToken) return false
      if (!element && step.target !== 'welcome') continue
      const title = document.createElement('span')
      title.textContent = step[`title_${language.value}`]
      const description = document.createElement('p')
      description.textContent = step[`description_${language.value}`]
      steps.push({ element: element || undefined, targetKey: step.target,
        disableActiveInteraction: step.target !== 'platform-appi-launcher',
        popover: { title: title.outerHTML, description: description.outerHTML } })
    }
    if (!steps.length) { restore(); return false }
    activeTour.value = tour
    surface.requestSurface('tour')
    unregister = surface.registerSurface('tour', () => { void pause() })

    async function advance(direction) {
      const currentId = activeTour.value?.id
      if (!currentId) return
      const loaded = await store.fetchHelp(projectId)
      if (token !== runToken || !driver) return
      if (!loaded || !store.tourEnabled || !store.tours.some((item) => item.id === currentId)) { await pause(); return }
      const available = new Set(store.tours.find((item) => item.id === currentId).content.steps.map((step) => step.target))
      let index = driver.getActiveIndex() + direction
      while (index >= 0 && index < steps.length) {
        const key = steps[index].targetKey
        const element = await prepareTarget(key)
        if (token !== runToken || !driver) return
        if (available.has(key) && (key === 'welcome' || element)) {
          steps[index].element = element || undefined
          driver.drive(index)
          return
        }
        index += direction
      }
      if (direction > 0) await finish('completed')
    }

    driver = createDriver({
      animate: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      showProgress: true, allowClose: true, overlayClickBehavior: 'none',
      disableActiveInteraction: true, popoverClass: 'platform-guided-tour',
      nextBtnText: t('platformHelp.next'), prevBtnText: t('platformHelp.previous'),
      doneBtnText: t('platformHelp.done'), progressText: t('platformHelp.progress', { current: '{{current}}', total: '{{total}}' }),
      steps, onDoneClick: () => { void finish('completed') }, onNextClick: () => { void advance(1) }, onPrevClick: () => { void advance(-1) },
      onCloseClick: () => { void finish('skipped') },
      onDestroyStarted: () => { if (!ending) void finish('skipped') },
      onHighlighted: (_element, step) => {
        currentStep.value = step.targetKey
        void store.acknowledge(tour, 'in_progress', step.targetKey, projectId, manual)
      },
      onPopoverRender: ({ wrapper, closeButton, nextButton, previousButton }) => {
        wrapper.setAttribute('data-testid', 'platform-tour-popover')
        wrapper.setAttribute('role', 'dialog')
        wrapper.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
        wrapper.setAttribute('aria-label', tour.content[`title_${language.value}`])
        nextButton.setAttribute('data-testid', 'platform-tour-next')
        previousButton.setAttribute('data-testid', 'platform-tour-previous')
        closeButton.setAttribute('data-testid', 'platform-tour-skip')
        closeButton.textContent = t('platformHelp.skip')
        closeButton.setAttribute('aria-label', t('platformHelp.skip'))
      },
    })
    const resumeIndex = ['paused', 'in_progress'].includes(tour.status) ? steps.findIndex((step) => step.targetKey === tour.last_step) : 0
    await prepareTarget(steps[Math.max(0, resumeIndex)].targetKey)
    if (token !== runToken || !driver) return false
    driver.drive(Math.max(0, resumeIndex))
    return true
  }

  function cancel() { return finish('skipped') }
  onBeforeUnmount(() => { void pause(); runToken += 1 })
  return { start, pause, cancel, activeTour, completedTour, isTourActive: surface.isTourActive }
}
