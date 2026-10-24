import { computed, ref } from 'vue'
import { usePlatformGuidedTour } from '~/composables/usePlatformGuidedTour'
import { usePlatformHelpSurface } from '~/composables/usePlatformHelpSurface'

/** Layout-owned public integration: video session registers its own opener. */
export function usePlatformHelp() {
  const route = useRoute()
  const tour = usePlatformGuidedTour()
  const surface = usePlatformHelpSurface()
  const voiceVisible = ref(false)
  const videoAvailable = ref(false)
  let videoOpener = null
  const projectId = computed(() => route.path.match(/\/platform\/projects\/(\d+)(?:\/|$)/)?.[1] || null)
  return { tour, voiceVisible, videoAvailable, ...surface,
    start: (id) => tour.start(id, { projectId: projectId.value, manual: true }),
    openVideo: () => videoOpener?.(),
    registerVideo(opener, available) { videoOpener = opener; videoAvailable.value = available },
  }
}
