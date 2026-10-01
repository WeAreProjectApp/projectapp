<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
import { onBeforeUnmount, ref, watch } from 'vue'
import { normalizeApiError } from '~/stores/services/normalize_api_error'
import { formatDateTime } from '~/utils/formatDate'
const props = defineProps({ api: { type: Object, required: true }, projectId: { type: Number, required: true } })
const { t } = useI18n()
const environments = ['production', 'staging']
const fields = ['site_url', 'admin_url', 'admin_username', 'admin_password']
const policy = ref(null)
const matrix = ref({})
const preview = ref(null)
const events = ref([])
const eventCount = ref(0)
const eventPage = ref(1)
const error = ref('')
const busy = ref(false)
let generation = 0
async function load() {
  const current = ++generation
  policy.value = null
  busy.value = false
  preview.value = null
  events.value = []
  error.value = ''
  try {
    const result = await props.api.policy()
    if (current !== generation) return
    policy.value = result
    matrix.value = JSON.parse(JSON.stringify(result.effective_permissions))
    await loadEvents()
  } catch (failure) { if (current === generation) error.value = normalizeApiError(failure).message }
}
async function loadEvents(page = 1) {
  const current = generation
  try {
    const result = await props.api.events(page)
    if (current !== generation) return
    events.value = result.results
    eventCount.value = result.count
    eventPage.value = result.page
  } catch (failure) { if (current === generation) error.value = normalizeApiError(failure).message }
}
async function save() {
  const current = generation
  busy.value = true
  error.value = ''
  try {
    const result = await props.api.updatePolicy({ expected_version: policy.value.version, source_token: policy.value.source_token, permissions: JSON.parse(JSON.stringify(matrix.value)) })
    if (current !== generation) return
    policy.value = result
    matrix.value = JSON.parse(JSON.stringify(result.effective_permissions))
    const currentPreview = await props.api.preview()
    if (current !== generation) return
    preview.value = currentPreview
    await loadEvents()
  } catch (failure) { if (current === generation) error.value = normalizeApiError(failure).message }
  finally { if (current === generation) busy.value = false }
}
watch(() => props.projectId, load, { immediate: true })
onBeforeUnmount(() => { generation += 1 })
</script>

<template>
  <section class="space-y-4 rounded-xl border border-border-default bg-surface p-4 text-text-default" data-testid="client-access-policy">
    <h2 class="text-lg font-semibold">{{ t('projectClientAccess.policyTitle') }}</h2>
    <p class="text-sm text-text-subtle">{{ t('projectClientAccess.notice') }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" type="button" @click="load">{{ t('projectClientAccess.retry') }}</BaseButton>
    <form v-if="policy" class="space-y-4" @submit.prevent="save">
      <div class="grid gap-4 lg:grid-cols-2">
        <fieldset v-for="environment in environments" :key="environment" class="space-y-3 rounded-xl border border-border-default p-4">
          <legend class="px-2 font-medium">{{ t(`projectClientAccess.${environment}`) }}</legend>
          <div v-for="field in fields" :key="field" class="space-y-1">
            <label class="flex min-h-11 items-center gap-3 text-sm">
              <input v-model="matrix[environment][field]" type="checkbox" :disabled="busy || !policy.available_fields[environment][field]" :data-testid="`client-access-enable-${environment}-${field}`" :aria-describedby="!policy.available_fields[environment][field] ? `access-unavailable-${environment}-${field}` : undefined" />
              {{ t(`projectClientAccess.${field}`) }}
            </label>
            <p v-if="!policy.available_fields[environment][field]" :id="`access-unavailable-${environment}-${field}`" class="text-xs text-text-subtle">{{ t('projectClientAccess.unavailable') }}</p>
            <p v-else-if="policy.permissions[environment][field] && !policy.effective_permissions[environment][field]" class="text-xs text-text-subtle">{{ t('projectClientAccess.stale') }}</p>
          </div>
        </fieldset>
      </div>
      <BaseButton variant="primary" size="md" textPolicy="wrap" class="min-h-11" type="submit" :disabled="busy" data-testid="client-access-policy-save">{{ t(busy ? 'projectClientAccess.saving' : 'projectClientAccess.save') }}</BaseButton>
    </form>
    <section v-if="preview" class="space-y-3" data-testid="client-access-preview">
      <h3 class="font-medium">{{ t('projectClientAccess.preview') }}</h3>
      <p v-if="!preview.environments.length">{{ t('projectClientAccess.empty') }}</p>
      <div v-for="environment in preview.environments" :key="environment.environment" class="space-y-2 rounded-xl bg-surface-muted p-3">
        <p class="font-medium">{{ t(`projectClientAccess.${environment.environment}`) }}</p>
        <p v-for="field in ['site_url', 'admin_url'].filter((name) => environment[name])" :key="field" class="break-all text-sm">{{ t(`projectClientAccess.${field}`) }}: {{ environment[field] }}</p>
        <p v-for="field in environment.credential_actions || []" :key="field" class="text-sm">{{ t(`projectClientAccess.${field}`) }} — {{ t('projectClientAccess.show') }}</p>
      </div>
    </section>
    <section class="space-y-2">
      <h3 class="font-medium">{{ t('projectClientAccess.events') }}</h3>
      <p v-for="event in events" :key="event.id" class="break-words text-sm text-text-subtle">{{ formatDateTime(event.created_at) }} · {{ t(`projectClientAccess.${event.action}`) }} · {{ event.fields.map((field) => field.split('.').map((part) => t(`projectClientAccess.${part}`)).join(' / ')).join(', ') }}</p>
      <div v-if="eventCount > 20" class="flex gap-3">
        <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="eventPage > 1" type="button" @click="loadEvents(eventPage - 1)">{{ t('projectClientAccess.previous') }}</BaseButton>
        <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" v-if="eventPage * 20 < eventCount" type="button" @click="loadEvents(eventPage + 1)">{{ t('projectClientAccess.next') }}</BaseButton>
      </div>
    </section>
  </section>
</template>
