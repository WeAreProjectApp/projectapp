<script setup>
import { onBeforeUnmount, ref } from 'vue'
const props = defineProps({ video: { type: Object, required: true }, language: { type: String, default: 'es' } })
const player = ref(null)
onBeforeUnmount(() => player.value?.pause())
</script>

<template>
  <section class="flex min-h-screen w-full items-center bg-surface px-5 py-16" data-testid="proposal-personalized-video">
    <div class="mx-auto w-full max-w-5xl space-y-6">
      <h2 class="text-2xl font-medium text-text-default">{{ props.language === 'en' ? 'Your proposal on video' : 'Tu propuesta en video' }}</h2>
      <video ref="player" :key="video.src" :src="video.src" :poster="video.poster" controls playsinline preload="metadata" class="aspect-video w-full rounded-2xl bg-surface-muted" :aria-label="language === 'en' ? 'Personalized proposal video' : 'Video personalizado de la propuesta'" />
    </div>
  </section>
</template>
