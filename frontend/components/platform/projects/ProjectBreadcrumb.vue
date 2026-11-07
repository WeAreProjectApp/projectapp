<template>
  <nav class="flex items-center gap-2 text-sm text-text-muted">
    <NuxtLink :to="localePath('/platform/projects')" class="hover:text-text-brand">Proyectos</NuxtLink>
    <span class="text-text-muted">/</span>
    <span class="text-text-default">{{ projectName || '…' }}</span>
  </nav>
</template>

<script setup>
defineProps({ projectName: { type: String, default: '' } })
const localePath = useLocalePath()
</script>
