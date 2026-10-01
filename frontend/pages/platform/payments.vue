<script setup>
import BaseRowLink from '~/components/base/BaseRowLink.vue'
import { useRowNavigation } from '~/composables/useRowNavigation'
import { usePlatformBillingStore } from '~/stores/platform-billing'
const store = usePlatformBillingStore()
const { t } = useI18n()
const localePath = useLocalePath()
const { openRow } = useRowNavigation()
definePageMeta({ layout: 'platform', middleware: ['platform-auth'] })
store.fetchHostingProjects()
const href = project => localePath(`/platform/projects/${project.id}/payments`)
</script>
<template>
  <section class="mx-auto max-w-6xl space-y-5 p-4 sm:p-6" data-testid="billing-hosting-list">
    <h1 class="text-2xl font-semibold text-text-default">{{ t('platformBilling.hosting') }}</h1>
    <p v-if="store.loading.hostingProjects" role="status">{{ t('platformBilling.loading') }}</p>
    <div v-else-if="store.errors.hostingProjects" role="alert"><p>{{ store.errors.hostingProjects }}</p><button class="text-text-brand" @click="store.fetchHostingProjects">{{ t('platformBilling.retry') }}</button></div>
    <p v-else-if="!store.hostingProjects.length" class="text-text-muted">{{ t('platformBilling.noHostingProjects') }}</p>
    <ul v-else class="space-y-3">
      <li v-for="project in store.hostingProjects" :key="project.id" class="relative rounded-xl border border-border-default bg-surface p-4" @click="openRow(href(project), $event)" @auxclick.middle="openRow(href(project), $event)"><BaseRowLink :to="href(project)" stretch>{{ project.name }}</BaseRowLink></li>
    </ul>
  </section>
</template>
