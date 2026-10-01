<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { normalizeApiError } from '~/stores/services/normalize_api_error'
const props = defineProps({ api: { type: Object, required: true }, projectId: Number, environment: { type: String, required: true }, field: { type: String, required: true } })
const emit = defineEmits(['denied'])
const { t } = useI18n()
const secret = ref('')
const busy = ref(false)
const error = ref('')
const feedback = ref('')
let generation = 0
let timer
function clear() { generation += 1; secret.value = ''; feedback.value = ''; busy.value = false; clearTimeout(timer) }
async function reveal(copy = false) {
  const current = ++generation
  secret.value = ''
  busy.value = true
  error.value = ''
  try {
    const result = await props.api.reveal(props.environment, props.field)
    if (current !== generation) return
    if (copy) { await navigator.clipboard.writeText(result.secret); if (current !== generation) return; feedback.value = t('projectClientAccess.copied') }
    else secret.value = result.secret
    clearTimeout(timer)
    timer = setTimeout(clear, 30000)
  } catch (failure) {
    if (current !== generation) return
    clear()
    error.value = normalizeApiError(failure, t('projectClientAccess.copyError')).message
    if ([401, 403, 404].includes(failure.response?.status)) emit('denied')
  } finally { if (current === generation) busy.value = false }
}
function onVisibility() { if (document.hidden) clear() }
watch(() => `${props.projectId}:${props.environment}:${props.field}`, clear)
onMounted(() => document.addEventListener('visibilitychange', onVisibility))
onBeforeUnmount(() => { clear(); document.removeEventListener('visibilitychange', onVisibility) })
</script>

<template>
  <div class="space-y-2" :data-testid="`client-credential-${environment}-${field}`">
    <p class="text-sm font-medium">{{ t(`projectClientAccess.${field}`) }}</p>
    <p v-if="secret" class="break-all rounded-lg bg-surface-muted p-3" data-testid="client-credential-value">{{ secret }}</p>
    <div class="flex flex-wrap gap-2">
      <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" type="button" :disabled="busy" data-testid="client-credential-toggle" @click="secret ? clear() : reveal()">{{ t(secret ? 'projectClientAccess.hide' : 'projectClientAccess.show') }}</BaseButton>
      <BaseButton variant="secondary" size="md" textPolicy="wrap" class="min-h-11" type="button" :disabled="busy" data-testid="client-credential-copy" @click="reveal(true)">{{ t('projectClientAccess.copy') }}</BaseButton>
    </div>
    <p class="text-xs text-text-subtle">{{ t('projectClientAccess.secretNotice') }}</p>
    <p v-if="error" role="alert" class="text-sm">{{ error }}</p>
    <p v-if="feedback" role="status" class="text-sm">{{ feedback }}</p>
  </div>
</template>
