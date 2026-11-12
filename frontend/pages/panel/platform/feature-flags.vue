<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePlatformFeatureAdminStore } from '~/stores/platform_feature_admin'

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] })
const { t, locale } = useI18n()
const localePath = useLocalePath()
const store = usePlatformFeatureAdminStore()
const scope = ref('global')
const search = ref('')
const busy = ref(false)
const error = ref('')
const saved = ref(false)
const selected = computed(() => scope.value === 'global' ? store.settings : store.client)
const label = item => item[locale.value.startsWith('en') ? 'label_en' : 'label_es']

async function run(action) {
  if (busy.value) return
  busy.value = true; error.value = ''; saved.value = false
  try { await action() }
  catch (cause) { error.value = t(cause.response?.status === 409 ? 'platformFeatures.conflict' : 'platformFeatures.error') }
  finally { busy.value = false }
}
async function save(key, value) {
  await run(async () => { await store.save({ [key]: value }, scope.value === 'client'); saved.value = true })
}
const options = item => [
  ...(scope.value === 'client' ? [{ label: t('platformFeatures.inherit'), onClick: () => save(item.key, null) }] : []),
  { label: t('platformFeatures.enabled'), onClick: () => save(item.key, true) },
  { label: t('platformFeatures.disabled'), onClick: () => save(item.key, false) },
]
const choice = item => scope.value === 'client' && item.override === null ? t('platformFeatures.inherit')
  : t((scope.value === 'client' ? item.override : item.global_value) ? 'platformFeatures.enabled' : 'platformFeatures.disabled')
let searchTimer
watch(search, () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => store.searchClients(search.value).catch(() => { error.value = t('platformFeatures.error') }), 300) })
onBeforeUnmount(() => clearTimeout(searchTimer))
onMounted(() => run(() => Promise.all([store.load(), store.searchClients(), store.loadEvents()])))
</script>

<template>
  <div class="mx-auto max-w-screen-xl space-y-6" data-testid="platform-feature-admin">
    <h1 class="text-2xl font-semibold text-text-default">{{ t('platformFeatures.title') }}</h1>
    <p class="text-sm text-text-muted">{{ t('platformFeatures.precedence') }}</p>
    <BaseAlert v-if="error" variant="danger" role="alert">{{ error }}</BaseAlert>
    <BaseAlert v-if="saved" variant="success" role="status">{{ t('platformFeatures.saved') }}</BaseAlert>
    <div class="flex flex-wrap gap-3">
      <BaseButton :variant="scope === 'global' ? 'primary' : 'secondary'" @click="scope = 'global'">{{ t('platformFeatures.global') }}</BaseButton>
      <BaseButton :variant="scope === 'client' ? 'primary' : 'secondary'" @click="scope = 'client'">{{ t('platformFeatures.byClient') }}</BaseButton>
      <BaseButton variant="ghost" :loading="busy" @click="run(async () => { await store.load(); if (store.client) await store.selectClient(store.client.user_id) })">{{ t('platformFeatures.reload') }}</BaseButton>
    </div>
    <section v-if="scope === 'client'" class="space-y-3 rounded-xl border border-border-default bg-surface p-4">
      <BaseFormField :label="t('platformFeatures.search')" for="feature-client-search">
        <BaseInput id="feature-client-search" v-model="search" :placeholder="t('platformFeatures.search')" />
      </BaseFormField>
      <BaseDropdown align="left" :items="store.clients.results.map(client => ({ label: client.name, onClick: () => run(() => store.selectClient(client.user_id)) }))">
        <template #trigger><BaseButton variant="secondary" :loading="busy" data-testid="feature-client-picker">{{ store.client?.name || t('platformFeatures.chooseClient') }}</BaseButton></template>
      </BaseDropdown>
      <p v-if="!store.clients.results.length" class="text-sm text-text-muted">{{ t('platformFeatures.empty') }}</p>
      <div class="flex flex-wrap items-center gap-3">
        <BaseButton v-if="store.clients.page > 1" variant="ghost" @click="run(() => store.searchClients(search, store.clients.page - 1))">{{ t('platformFeatures.previous') }}</BaseButton>
        <span class="text-sm text-text-muted">{{ store.clients.page }} · {{ store.clients.count }}</span>
        <BaseButton v-if="store.clients.page * 20 < store.clients.count" variant="ghost" @click="run(() => store.searchClients(search, store.clients.page + 1))">{{ t('platformFeatures.next') }}</BaseButton>
      </div>
    </section>
    <p v-if="!selected && !error" class="text-sm text-text-muted" role="status">{{ t(scope === 'client' ? 'platformFeatures.chooseClient' : 'platformFeatures.loading') }}</p>
    <section v-else class="grid gap-4 panel-portrait:grid-cols-2">
      <article v-for="item in selected.features" :key="item.key" class="min-w-0 space-y-3 rounded-xl border border-border-default bg-surface p-4" :data-testid="`feature-${item.key}`">
        <h2 class="font-semibold text-text-default">{{ label(item) }}</h2>
        <p class="break-all font-mono text-xs text-text-muted">{{ item.key }}</p>
        <BaseDropdown align="left" :items="options(item)">
          <template #trigger><BaseButton variant="secondary" :loading="busy" :aria-label="`${label(item)}: ${choice(item)}`">{{ choice(item) }}</BaseButton></template>
        </BaseDropdown>
        <p class="text-sm text-text-default" data-testid="feature-effective">{{ t('platformFeatures.effective') }}: {{ t(item.effective ? 'platformFeatures.enabled' : 'platformFeatures.disabled') }}</p>
        <p class="text-sm text-text-muted">{{ t('platformFeatures.source') }}: {{ t(item.source === 'client' ? 'platformFeatures.exception' : 'platformFeatures.global') }}</p>
        <p v-if="scope === 'client'" class="text-xs text-text-muted">{{ t('platformFeatures.global') }}: {{ t(item.global_value ? 'platformFeatures.enabled' : 'platformFeatures.disabled') }}</p>
      </article>
    </section>
    <section class="space-y-3 rounded-xl border border-border-default p-4">
      <h2 class="font-semibold">{{ t('platformFeatures.audit') }}</h2>
      <BaseButton variant="ghost" @click="run(() => store.loadEvents())">{{ t('platformFeatures.reload') }}</BaseButton>
      <p v-for="event in store.events?.results || []" :key="event.id" class="break-words text-sm text-text-muted">{{ event.created_at }} · {{ event.scope }} · {{ event.client_id || t('platformFeatures.global') }} · {{ Object.keys(event.changes).join(', ') }}</p>
      <div class="flex gap-3">
        <BaseButton v-if="store.events?.page > 1" variant="ghost" @click="run(() => store.loadEvents(store.events.page - 1))">{{ t('platformFeatures.previous') }}</BaseButton>
        <BaseButton v-if="store.events && store.events.page * 20 < store.events.count" variant="ghost" @click="run(() => store.loadEvents(store.events.page + 1))">{{ t('platformFeatures.next') }}</BaseButton>
      </div>
    </section>
    <NuxtLink :to="localePath('/panel/views')" class="text-text-brand underline">{{ t('platformFeatures.viewMap') }}</NuxtLink>
  </div>
</template>

