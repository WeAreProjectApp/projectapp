<script setup>
definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
const { t } = useI18n()
const localePath = useLocalePath()
const route = useRoute()
</script>

<template>
  <section class="space-y-4 rounded-xl border border-border-default bg-surface p-6" data-testid="platform-feature-unavailable">
    <h1 class="text-xl font-semibold text-text-default">{{ t('platformFeatures.unavailable') }}</h1>
    <p role="status" class="text-text-muted">{{ t(route.query.reason === 'load' ? 'platformFeatures.loadError' : 'platformFeatures.unavailableHint') }}</p>
    <NuxtLink :to="localePath('/platform/projects')" class="text-text-brand underline">{{ t('platformFeatures.back') }}</NuxtLink>
  </section>
</template>
