<template>
  <nav class="flex min-w-0 items-start gap-2 text-sm text-green-light">
    <NuxtLink :to="localePath('/platform/projects')" class="shrink-0 hover:text-text-brand">Proyectos</NuxtLink>
    <span class="shrink-0 text-green-light/40">/</span>
    <span class="min-w-0 whitespace-normal text-text-default [overflow-wrap:anywhere]" aria-current="page" data-testid="project-breadcrumb-name">{{ projectName || '…' }}</span>
  </nav>
</template>

<script setup>
defineProps({ projectName: { type: String, default: '' } })
const localePath = useLocalePath()
</script>
