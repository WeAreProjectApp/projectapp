<template>
  <div v-if="tour.completedTour.value && store.videoEnabled && videoAvailable" class="fixed bottom-5 left-4 z-50 max-w-sm rounded-2xl border border-border-default bg-surface p-4 shadow-xl dark:bg-primary" role="status">
    <p class="mb-3 text-sm text-text-default">{{ t('platformHelp.videoInvitation') }}</p>
    <div class="flex gap-2">
      <BaseButton variant="accent" @click="openVideo">{{ t('platformHelp.video') }}</BaseButton>
      <BaseButton variant="ghost" @click="tour.completedTour.value = null">{{ t('platformHelp.dismiss') }}</BaseButton>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, watch } from 'vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformHelpStore } from '~/stores/platform-help'
import { usePlatformGuidedTour, visibleTourTarget } from '~/composables/usePlatformGuidedTour'
const route = useRoute()
const auth = usePlatformAuthStore()
const store = usePlatformHelpStore()
const help = inject('platformHelp')
const tour = help.tour
const { t } = useI18n()
const projectId = computed(() => route.path.match(/\/platform\/projects\/(\d+)(?:\/|$)/)?.[1] || null)
const videoAvailable = computed(() => help.videoAvailable.value)
let observer = null
let timer = null
let lastAutoContext = ''
let busy = false

async function considerAuto() {
  if (busy || !auth.isClient || !auth.hasValidatedSession || auth.needsProfileCompletion || tour.isTourActive.value || help.activeSurface.value) return
  const voice = Boolean(visibleTourTarget('voice-report'))
  help.voiceVisible.value = voice
  const contextKey = `${route.path}:${voice}`
  if (lastAutoContext === contextKey) return
  busy = true
  try {
    if (!await store.fetchHelp(projectId.value)) return
    const eligible = store.tours.filter((item) => !['completed', 'skipped', 'paused'].includes(item.status))
    const selected = eligible.find((item) => voice && item.context === 'voice')
      || eligible.find((item) => item.context === 'general')
      || eligible.find((item) => projectId.value && item.context === 'project')
    if (selected) {
      lastAutoContext = contextKey
      await tour.start(selected.id, { projectId: projectId.value, manual: false })
    }
  } finally { busy = false }
}

async function refresh() {
  if (!auth.isClient) { await tour.pause(); store.reset(); return }
  const loaded = await store.fetchHelp(projectId.value)
  if (!loaded || !store.tourEnabled) await tour.pause()
  await considerAuto()
}

function openVideo() { tour.completedTour.value = null; help.openVideo() }
watch(() => route.path, async () => { await tour.pause(); tour.completedTour.value = null; await refresh() })
watch(() => auth.user?.id, async () => { await tour.pause(); store.reset(); lastAutoContext = ''; await refresh() })
onMounted(() => {
  void refresh()
  observer = new MutationObserver(() => { if (Boolean(visibleTourTarget('voice-report')) !== help.voiceVisible.value) void considerAuto() })
  observer.observe(document.body, { childList: true, subtree: true })
  window.addEventListener('focus', refresh)
  timer = window.setInterval(() => { if (tour.isTourActive.value) void refresh() }, 30000)
})
onBeforeUnmount(() => { observer?.disconnect(); window.clearInterval(timer); window.removeEventListener('focus', refresh) })
</script>
