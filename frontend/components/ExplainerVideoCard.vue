<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'

import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import { formatExplainerDuration } from '~/composables/useExplainerVideos'

const props = defineProps({
  /** Descriptor from useExplainerVideo(): { id, language, src, poster, durationSeconds, width, height }. */
  video: { type: Object, required: true },
  /** Locale namespace that holds the explainer* keys. */
  i18nNamespace: {
    type: String,
    required: true,
    validator: (value) => ['additionalModules', 'financing', 'proposalExplainer'].includes(value),
  },
  /** hero = protagonist card on a public view; compact = panel media object. */
  variant: { type: String, default: 'hero', validator: (value) => ['hero', 'compact'].includes(value) },
  testId: { type: String, default: 'explainer-video' },
  /** Public documents may choose a language independently of the browser locale. */
  contentLocale: { type: String, default: undefined },
  contentMessages: { type: Object, default: undefined },
})

const emit = defineEmits(['play', 'error'])
const { t } = useI18n(props.contentMessages ? {
  useScope: 'local',
  locale: props.contentLocale,
  inheritLocale: false,
  messages: props.contentMessages,
} : {})
function translate(key, params = {}) {
  return props.contentLocale ? t(key, params, { locale: props.contentLocale }) : t(key, params)
}

const state = ref('idle')
const videoRef = ref(null)

function pause() { videoRef.value?.pause() }
onBeforeUnmount(pause)
defineExpose({ pause })

const ns = computed(() => props.i18nNamespace)
const isCompact = computed(() => props.variant === 'compact')
const titleId = computed(() => `${props.testId}-title`)
const title = computed(() => translate(`${ns.value}.${isCompact.value ? 'explainerPanelTitle' : 'explainerTitle'}`))
const description = computed(() => translate(`${ns.value}.${isCompact.value ? 'explainerPanelDescription' : 'explainerDescription'}`))
const durationLabel = computed(() => translate(`${ns.value}.explainerDuration`, { time: formatExplainerDuration(props.video.durationSeconds) }))

async function start() {
  state.value = 'playing'
  emit('play')
  await nextTick()
  const element = videoRef.value
  if (!element) return
  element.muted = false
  element.volume = 1
  if (typeof element.play === 'function') {
    try {
      await element.play()
    } catch {
      // Native controls stay available if the browser refuses the automatic start.
    }
  }
  element.focus?.()
}

function onError() {
  state.value = 'error'
  emit('error')
}

function onEnded() {
  state.value = 'idle'
}
</script>

<template>
  <section
    :data-testid="`${testId}-card`"
    :data-state="state"
    :data-variant="variant"
    :aria-labelledby="titleId"
    class="overflow-hidden rounded-3xl border border-border-default bg-surface text-left shadow-card"
    :class="isCompact ? 'flex flex-col gap-4 p-4 panel-portrait:flex-row panel-portrait:items-center' : 'flex flex-col'"
  >
    <div :class="isCompact ? 'w-full shrink-0 panel-portrait:w-72' : 'w-full'">
      <BaseButton
        v-if="state === 'idle'"
        unstyled
        icon-only
        type="button"
        :aria-label="translate(`${ns}.explainerPlayAria`, { title })"
        :data-testid="`${testId}-play`"
        class="group relative aspect-video w-full overflow-hidden bg-primary-strong"
        :class="isCompact ? 'rounded-2xl' : ''"
        @click="start"
      >
        <img
          :src="video.poster"
          :width="video.width"
          :height="video.height"
          alt=""
          loading="eager"
          decoding="async"
          class="absolute inset-0 h-full w-full object-cover"
        />
        <span aria-hidden="true" class="absolute inset-0 bg-gradient-to-t from-primary-strong/70 via-transparent to-transparent" />
        <span aria-hidden="true" class="absolute inset-0 flex items-center justify-center">
          <span
            class="flex items-center justify-center rounded-full bg-accent text-primary-strong shadow-raised transition-transform group-hover:scale-105"
            :class="isCompact ? 'h-14 w-14' : 'h-16 w-16 sm:h-20 sm:w-20'"
          >
            <svg class="ml-1 h-1/2 w-1/2" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M8 5v14l11-7z" />
            </svg>
          </span>
        </span>
        <span
          aria-hidden="true"
          class="absolute right-3 top-3 rounded-full bg-primary-strong/80 px-3 py-1 text-xs font-medium text-on-primary"
        >
          {{ translate(`${ns}.explainerPlay`) }} · {{ durationLabel }}
        </span>
      </BaseButton>
      <template v-else>
        <video
          ref="videoRef"
          :data-testid="`${testId}-player`"
          :src="video.src"
          :poster="video.poster"
          :aria-label="title"
          controls
          autoplay
          playsinline
          preload="auto"
          class="aspect-video w-full bg-primary-strong"
          :class="isCompact ? 'rounded-2xl' : ''"
          @error="onError"
          @ended="onEnded"
        />
        <BaseAlert v-if="state === 'error'" variant="warning" class="mt-3" :data-testid="`${testId}-error`">
          {{ translate(`${ns}.explainerError`) }}
          <a
            :href="video.src"
            target="_blank"
            rel="noopener"
            :data-testid="`${testId}-open`"
            class="ml-1 font-medium underline"
          >{{ translate(`${ns}.explainerOpenFile`) }}</a>
        </BaseAlert>
      </template>
    </div>

    <div :class="isCompact ? 'min-w-0 flex-1' : 'p-5 sm:p-6'">
      <h2 :id="titleId" class="text-lg font-medium text-text-brand sm:text-xl">{{ title }}</h2>
      <p class="mt-1 text-sm leading-6 text-text-muted">{{ description }}</p>
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <BaseBadge variant="neutral" size="sm">{{ durationLabel }}</BaseBadge>
        <span class="text-xs text-text-subtle">{{ translate(`${ns}.explainerNoAudioNote`) }}</span>
      </div>
    </div>
  </section>
</template>
