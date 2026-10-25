<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from '#imports'
import { storeToRefs } from 'pinia'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseModal from '~/components/base/BaseModal.vue'
import { usePlatformHelpVideosStore } from '~/stores/platform-help-videos'
import { usePlatformHelpSurface } from '~/composables/usePlatformHelpSurface'
import { usePlatformVideoCopy } from '~/composables/usePlatformVideoCopy'
import { formatExplainerDuration } from '~/composables/useExplainerVideos'

const emit = defineEmits(['open', 'close'])
const store = usePlatformHelpVideosStore()
const { videos, selectedVideo } = storeToRefs(store)
const { t } = usePlatformVideoCopy()
const help = inject('platformHelp', null)
const surface = usePlatformHelpSurface()
const route = useRoute()
const unregister = surface.registerSurface('video', close)
const player = ref(null)
const failed = ref(false)
const catalogFailed = ref(false)
const visible = computed(() => store.isOpen || catalogFailed.value)
const canOpen = computed(() => store.videoAvailable || store.error)
const playbackRevision = ref(0)

function pause() { player.value?.pause() }
function close() { pause(); catalogFailed.value = false; store.closeVideo() }
async function open() {
  // The menu item disappears before the response arrives. Give BaseModal a
  // stable focus origin for keyboard users and for the tour's final CTA.
  const entry = [...document.querySelectorAll('[data-testid="platform-help-trigger"]')]
    .find((element) => element.getClientRects().length)
  entry?.focus({ preventScroll: true })
  await store.openVideo()
  catalogFailed.value = store.error
}
function onVisibility() { if (document.visibilityState === 'hidden') pause() }
async function onFocus() {
  const wasOpen = visible.value
  const version = store.requestVersion + 1
  await store.fetchVideos()
  if (wasOpen && version === store.requestVersion) {
    catalogFailed.value = store.error
    if (!store.error && store.selectedVideo) store.isOpen = true
  }
}
function retry() { failed.value = false; playbackRevision.value += 1 }
watch(() => selectedVideo.value?.src, () => { pause(); failed.value = false }, { flush: 'sync' })
watch(visible, (open) => {
  if (open) surface.requestSurface('video')
  else { pause(); surface.releaseSurface('video') }
  emit(open ? 'open' : 'close')
}, { flush: 'sync' })
watch(() => route.fullPath, close)
watch(canOpen, (available) => help?.registerVideo(open, available))
onMounted(() => {
  help?.registerVideo(open, canOpen.value)
  store.fetchVideos()
  if (store.isOpen) { surface.requestSurface('video'); emit('open') }
  window.addEventListener('blur', pause)
  window.addEventListener('pagehide', pause)
  window.addEventListener('focus', onFocus)
  document.addEventListener('visibilitychange', onVisibility)
})
onBeforeUnmount(() => {
  pause()
  unregister()
  help?.registerVideo(null, false)
  store.reset()
  window.removeEventListener('blur', pause)
  window.removeEventListener('pagehide', pause)
  window.removeEventListener('focus', onFocus)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<template>
  <BaseModal :model-value="visible" kind="detail" padding="md" data-testid="platform-help-video-modal" @update:model-value="close">
    <div class="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 class="text-xl font-semibold text-text-default">{{ t('platformVideos.title') }}</h2>
        <p class="mt-1 text-sm text-text-muted">{{ t('platformVideos.description') }}</p>
      </div>
      <BaseButton variant="ghost" icon-only :aria-label="t('platformVideos.close')" data-testid="platform-video-close" @click="close">×</BaseButton>
    </div>
    <div class="mb-4 flex flex-wrap gap-2" role="group" :aria-label="t('platformVideos.title')">
      <BaseButton v-for="video in videos" :key="video.topic" :variant="selectedVideo?.topic === video.topic ? 'primary' : 'secondary'" :aria-pressed="selectedVideo?.topic === video.topic" :data-testid="`platform-video-topic-${video.topic}`" @click="pause(); store.selectVideo(video.topic)">
        {{ t(`platformVideos.${video.topic}`) }} · {{ formatExplainerDuration(video.durationSeconds) }}
      </BaseButton>
    </div>
    <p class="mb-3 text-sm text-text-muted">{{ t('platformVideos.language') }}</p>
    <BaseAlert v-if="catalogFailed" variant="warning" role="alert">
      {{ t('platformVideos.loadError') }}
      <BaseButton variant="secondary" size="sm" class="mt-2" @click="open">{{ t('platformVideos.retry') }}</BaseButton>
    </BaseAlert>
    <video v-if="selectedVideo" :key="`${selectedVideo.src}-${playbackRevision}`" ref="player" :src="selectedVideo.src" :poster="selectedVideo.poster" :aria-label="t(`platformVideos.${selectedVideo.topic}`)" controls playsinline preload="none" class="aspect-video w-full rounded-xl bg-primary-strong" data-testid="platform-help-video-player" @error="failed = true" />
    <BaseAlert v-if="failed" variant="warning" class="mt-3" role="alert">
      {{ t('platformVideos.playbackError') }}
      <BaseButton variant="secondary" size="sm" class="mt-2" @click="retry">{{ t('platformVideos.retry') }}</BaseButton>
    </BaseAlert>
  </BaseModal>
</template>
