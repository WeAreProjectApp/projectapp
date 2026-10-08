<script setup>
import { ref, watch } from 'vue'
import { usePlatformApi } from '~/composables/usePlatformApi'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseButton from '~/components/base/BaseButton.vue'

const props = defineProps({ projectId: { type: Number, required: true }, workspaceVersion: { type: Number, default: 0 } })
const { t } = useI18n()
const events = ref([])
const page = ref(1)
const count = ref(0)
const busy = ref(false)
const error = ref('')
const preview = ref(null)
let requestId = ''
let sequence = 0
const base = () => `projects/${props.projectId}/delivery/notices/`
const failure = (cause) => typeof cause.response?.data?.detail === 'string' ? cause.response.data.detail : t('platformDelivery.notices.error')

async function load() {
  const current = ++sequence
  busy.value = true
  error.value = ''
  try {
    const response = await usePlatformApi().get(base(), { params: { page: page.value } })
    if (current !== sequence) return
    events.value = response.data.results
    count.value = response.data.count
  } catch (cause) {
    if (current === sequence) error.value = failure(cause)
  } finally {
    if (current === sequence) busy.value = false
  }
}

async function prepare(event) {
  const current = ++sequence
  preview.value = null
  requestId = ''
  error.value = ''
  busy.value = true
  try {
    const response = await usePlatformApi().get(`${base()}${event.id}/retry-preview/`, { params: { expected_version: event.version } })
    if (current !== sequence) return
    preview.value = response.data
    requestId = globalThis.crypto?.randomUUID?.() || `notice-${Date.now()}-${current}`
  } catch (cause) { if (current === sequence) error.value = failure(cause) }
  finally { if (current === sequence) busy.value = false }
}

async function retry() {
  if (!preview.value || busy.value) return
  const current = ++sequence
  busy.value = true
  error.value = ''
  try {
    await usePlatformApi().post(`${base()}${preview.value.id}/retry/`, {
      expected_version: preview.value.version, request_id: requestId, preview_sha256: preview.value.preview_sha256,
    })
    if (current !== sequence) return
    preview.value = null
    await load()
  } catch (cause) { if (current === sequence) error.value = failure(cause) }
  finally { if (current === sequence) busy.value = false }
}

watch(() => [props.projectId, props.workspaceVersion, page.value], ([projectId], previous = []) => {
  if (projectId !== previous[0]) { events.value = []; count.value = 0; page.value = 1 }
  preview.value = null
  load()
}, { immediate: true })
</script>

<template>
  <section class="min-w-0 space-y-3 rounded-xl border border-border-default p-4" data-testid="delivery-notice-history">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 class="font-semibold text-text-default">{{ t('platformDelivery.notices.title') }}</h3>
      <BaseButton variant="ghost" size="sm" :loading="busy" @click="load">{{ t('platformDelivery.refresh') }}</BaseButton>
    </div>
    <p class="text-sm text-text-muted">{{ t('platformDelivery.notices.hint') }}</p>
    <BaseAlert v-if="error" variant="danger" role="alert">{{ error }}</BaseAlert>
    <p v-if="!events.length" class="text-sm text-text-muted">{{ t('platformDelivery.notices.empty') }}</p>
    <article v-for="event in events" :key="event.id" class="min-w-0 space-y-2 rounded-lg bg-surface-raised p-3">
      <p class="break-words font-medium text-text-default">{{ event.subject }}</p>
      <p class="text-sm text-text-muted">{{ t(`platformDelivery.notices.status.${event.status}`) }}</p>
      <p class="break-all text-sm text-text-muted">{{ event.recipients.join(', ') }}</p>
      <p v-if="event.status === 'unknown' || event.status === 'sending'" class="text-sm text-text-muted">{{ t('platformDelivery.notices.uncertain') }}</p>
      <BaseButton v-if="event.status === 'failed'" variant="secondary" size="sm" :loading="busy" @click="prepare(event)">{{ t('platformDelivery.notices.preview') }}</BaseButton>
    </article>
    <section v-if="preview" class="min-w-0 space-y-3 rounded-lg border border-border-default p-3" data-testid="delivery-notice-retry-preview">
      <p class="break-words font-semibold text-text-default">{{ preview.subject }}</p>
      <p class="break-all text-sm text-text-muted">{{ preview.recipients.join(', ') }}</p>
      <pre class="whitespace-pre-wrap break-words text-sm text-text-default">{{ preview.text_body }}</pre>
      <div class="flex flex-wrap gap-2"><BaseButton :loading="busy" @click="retry">{{ t('platformDelivery.notices.confirm') }}</BaseButton><BaseButton variant="ghost" @click="preview = null">{{ t('platformDelivery.cancel') }}</BaseButton></div>
    </section>
    <div v-if="count > 20" class="flex flex-wrap gap-2">
      <BaseButton variant="ghost" :disabled="page === 1 || busy" @click="page--">{{ t('platformDelivery.notices.previous') }}</BaseButton>
      <BaseButton variant="ghost" :disabled="page * 20 >= count || busy" @click="page++">{{ t('platformDelivery.notices.next') }}</BaseButton>
    </div>
  </section>
</template>
