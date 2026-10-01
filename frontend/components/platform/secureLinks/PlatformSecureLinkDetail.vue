<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import BaseModal from '~/components/base/BaseModal.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseInput from '~/components/base/BaseInput.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import { usePlatformSecureLinksStore } from '~/stores/platform-secure-links'

const props = defineProps({ link: { type: Object, required: true } })
const emit = defineEmits(['close', 'updated', 'replace'])
const store = usePlatformSecureLinksStore()
const { t } = useI18n()
const current = ref({ ...props.link })
const title = ref(props.link.title)
const events = ref([])
const eventPage = ref(1)
const eventCount = ref(0)
const url = ref('')
const copied = ref(false)
const busy = ref(false)
const error = ref('')
const confirmation = ref('')
const validityDays = ref(7)
let generation = 0
onBeforeUnmount(() => { generation += 1; url.value = ''; events.value = [] })

async function loadEvents(page = 1) {
  const attempt = generation
  const result = await store.events(current.value.id, page)
  if (attempt !== generation) return
  if (result.success) { events.value = result.data.results; eventPage.value = result.data.page; eventCount.value = result.data.count }
  else error.value = result.code || 'failed'
}
onMounted(() => loadEvents())
async function act(action) {
  if (busy.value) return
  const attempt = generation
  busy.value = true
  error.value = ''
  url.value = ''
  copied.value = false
  let result
  if (action === 'copy') result = await store.copyURL(current.value.id)
  else if (action === 'rename') result = await store.rename(current.value, title.value)
  else if (action === 'reactivate') result = await store.reactivate(current.value, validityDays.value)
  else result = await store.revoke(current.value.id)
  if (attempt !== generation) return
  busy.value = false
  confirmation.value = ''
  if (!result.success) { error.value = result.code || 'failed'; emit('updated'); return }
  if (action === 'copy') url.value = result.data.url
  else {
    current.value = result.data.link || result.data
    url.value = result.data.url || ''
    emit('updated')
  }
  if (action === 'replace') { emit('replace', current.value); return }
  await loadEvents()
}
async function copy() {
  try { await navigator.clipboard.writeText(url.value); copied.value = true } catch { error.value = 'clipboard' }
}
</script>

<template>
  <BaseModal :model-value="true" kind="detail" padding="md" @update:model-value="emit('close')">
    <h2 class="text-lg font-semibold text-text-default">{{ current.title }}</h2>
    <p class="mt-2 text-sm text-text-muted">{{ t('platformSecureLinks.teamOnly') }} {{ t('platformSecureLinks.noSecretRead') }}</p>
    <p class="mt-3 text-sm text-text-default" data-testid="platform-secure-detail-status">{{ t(`platformSecureLinks.status.${current.status}`) }}</p>
    <form class="mt-4 space-y-3" @submit.prevent="act('rename')">
      <BaseFormField :label="t('platformSecureLinks.label')" for="platform-secure-rename" required>
        <BaseInput id="platform-secure-rename" v-model="title" required maxlength="160" data-testid="platform-secure-rename" />
      </BaseFormField>
      <BaseButton type="submit" variant="secondary" :loading="busy" data-testid="platform-secure-save-title">{{ t('platformSecureLinks.saveTitle') }}</BaseButton>
    </form>
    <div class="mt-4 flex flex-wrap gap-2">
      <BaseButton v-if="current.capabilities.copy_url" variant="secondary" :loading="busy" data-testid="platform-secure-request-url" @click="act('copy')">{{ t('platformSecureLinks.showUrl') }}</BaseButton>
      <BaseButton v-if="current.capabilities.revoke" variant="danger-ghost" data-testid="platform-secure-revoke" @click="confirmation = 'revoke'">{{ t('platformSecureLinks.revoke') }}</BaseButton>
      <BaseButton v-if="current.capabilities.reactivate" variant="secondary" data-testid="platform-secure-reactivate" @click="confirmation = 'reactivate'">{{ t('platformSecureLinks.reactivate') }}</BaseButton>
      <BaseButton v-if="!current.replaced_by" variant="secondary" data-testid="platform-secure-replace" @click="confirmation = 'replace'">{{ t('platformSecureLinks.replace') }}</BaseButton>
    </div>
    <div v-if="url" class="mt-4 space-y-2">
      <BaseInput :model-value="url" readonly :aria-label="t('platformSecureLinks.url')" data-testid="platform-secure-url" />
      <BaseButton data-testid="platform-secure-copy" @click="copy">{{ t(copied ? 'platformSecureLinks.copied' : 'platformSecureLinks.copy') }}</BaseButton>
    </div>
    <p v-if="current.replaces" class="mt-3 text-sm text-text-muted">{{ t('platformSecureLinks.replacesId', { id: current.replaces }) }}</p>
    <p v-if="current.replaced_by" class="mt-3 text-sm text-text-muted">{{ t('platformSecureLinks.replacedById', { id: current.replaced_by }) }}</p>
    <BaseAlert v-if="error" variant="danger" class="mt-4" data-testid="platform-secure-detail-error">{{ t(`platformSecureLinks.errors.${error}`) }}</BaseAlert>
    <h3 class="mt-5 font-semibold text-text-default">{{ t('platformSecureLinks.history') }}</h3>
    <ul class="mt-3 space-y-2 text-sm text-text-muted" data-testid="platform-secure-history">
      <li v-for="event in events" :key="event.id">{{ t(`platformSecureLinks.events.${event.kind}`) }} · {{ event.created_at }} · {{ t(`platformSecureLinks.actors.${event.actor_kind}`) }}</li>
    </ul>
    <div class="mt-3 flex flex-wrap gap-2">
      <BaseButton v-if="eventPage > 1" variant="ghost" @click="loadEvents(eventPage - 1)">{{ t('platformSecureLinks.previous') }}</BaseButton>
      <BaseButton v-if="eventPage * 25 < eventCount" variant="ghost" @click="loadEvents(eventPage + 1)">{{ t('platformSecureLinks.next') }}</BaseButton>
    </div>
    <BaseButton variant="ghost" class="mt-4" data-testid="platform-secure-close" @click="emit('close')">{{ t('platformSecureLinks.close') }}</BaseButton>
    <BaseModal :model-value="Boolean(confirmation)" kind="confirm" padding="md" @update:model-value="confirmation = ''">
      <h3 class="font-semibold text-text-default">{{ t('platformSecureLinks.confirmTitle') }}</h3>
      <p class="mt-3 text-sm text-text-muted">{{ t(`platformSecureLinks.confirm.${confirmation || 'revoke'}`) }}</p>
      <BaseFormField v-if="confirmation === 'reactivate'" class="mt-3" :label="t('platformSecureLinks.validity')" for="platform-secure-reactivate-validity">
        <BaseSelect id="platform-secure-reactivate-validity" v-model="validityDays" :options="[1, 3, 7].map(value => ({ value, label: t('platformSecureLinks.days', { count: value }) }))" />
      </BaseFormField>
      <div class="mt-4 flex flex-wrap gap-2">
        <BaseButton variant="danger" :loading="busy" data-testid="platform-secure-confirm" @click="act(confirmation)">{{ t('platformSecureLinks.confirmAction') }}</BaseButton>
        <BaseButton variant="ghost" @click="confirmation = ''">{{ t('platformSecureLinks.cancel') }}</BaseButton>
      </div>
    </BaseModal>
  </BaseModal>
</template>
