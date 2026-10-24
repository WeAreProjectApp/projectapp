<script setup>
import VideoResourceManager from '~/components/resources/VideoResourceManager.vue'
import { usePlatformVideoCopy } from '~/composables/usePlatformVideoCopy'

const { t } = usePlatformVideoCopy()
const emit = defineEmits(['updated'])
const topics = {
  general: 'platform-overview',
  chatbot: 'platform-chatbot',
  'voice-reporting': 'platform-voice-reporting',
}
</script>

<template>
  <section data-testid="platform-video-resources" class="space-y-4">
    <h2 class="text-xl font-semibold text-text-default">{{ t('platformVideos.adminTitle') }}</h2>
    <p class="text-sm text-text-muted">{{ t('platformVideos.adminDescription') }}</p>
    <p class="text-sm text-text-muted">{{ t('platformVideos.subtitleHint') }}</p>
    <section v-for="(module, topic) in topics" :key="module" :data-testid="`platform-video-resource-${topic}`">
      <h3 class="text-lg font-medium text-text-default">{{ t(`platformVideos.${topic}`) }}</h3>
      <VideoResourceManager :module="module" language="es" :languages="['es']" @updated="emit('updated', $event)" />
    </section>
  </section>
</template>
