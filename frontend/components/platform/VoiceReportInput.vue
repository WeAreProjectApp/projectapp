<script setup>
import { computed, onMounted, onBeforeUnmount, ref, useId, watch } from 'vue'
import { usePlatformAIStore } from '~/stores/platform-ai'
import { useVoiceRecorder } from '~/composables/useVoiceRecorder'
import PlatformAIQuotaMeter from './PlatformAIQuotaMeter.vue'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
  scenario: { type: String, required: true },
  requirementId: { type: [Number, String], default: null },
  stageId: { type: [Number, String], default: null },
})
const emit = defineEmits(['apply'])
const { t, locale } = useI18n()
const inputId = useId()
const store = usePlatformAIStore()
const { recording, seconds, audio, audioUrl, start, stop, clear } = useVoiceRecorder()
const open = ref(false), busy = ref(false), error = ref(''), transcript = ref(''), proposal = ref(null)
const transcriptionId = ref(''), draftId = ref(''), recoverable = ref([])
let disposed = false, timer, quotaTimer, controller, finishDelay, epoch = 0
let transcriptionRequestId = '', draftRequestId = '', draftRequestBody = ''
const contextKey = computed(() => [props.projectId, props.scenario, props.requirementId, props.stageId].join(':'))
const context = () => ({
  ...(props.requirementId ? { source_requirement_id: Number(props.requirementId) } : {}),
  ...(props.stageId ? { stage_id: Number(props.stageId) } : {}),
})
const current = (token) => !disposed && token === epoch
const editableFields = computed(() => props.scenario === 'bug' ? ['title', 'description', 'expected_behavior', 'actual_behavior'] : props.scenario === 'change' ? ['title', 'description', 'module_or_screen'] : ['message'])
onMounted(() => store.refreshCapabilities())
watch(() => store.capabilities?.quota?.next_available_at, (next) => {
  clearTimeout(quotaTimer)
  if (next) quotaTimer = setTimeout(() => store.refreshCapabilities(), Math.max(1000, new Date(next).getTime() - Date.now() + 200))
})
function cancelPolling() { clearTimeout(timer); finishDelay?.(); controller?.abort() }
function resetPreparation() {
  proposal.value = null; transcript.value = ''; draftId.value = ''; transcriptionId.value = ''; clear()
  transcriptionRequestId = ''; draftRequestId = ''; draftRequestBody = ''
}
watch(contextKey, () => {
  epoch++; cancelPolling(); stop(); resetPreparation()
  open.value = false; busy.value = false; error.value = ''; recoverable.value = []
})
watch(audio, () => { transcriptionRequestId = '' })
onBeforeUnmount(() => { disposed = true; clearTimeout(quotaTimer); cancelPolling() })

async function run(action) {
  const token = epoch
  error.value = ''; busy.value = true
  try { await action(token) }
  catch { if (current(token)) { error.value = t('platformAI.processingError'); await store.refreshCapabilities() } }
  finally { if (current(token)) busy.value = false }
}
async function show() {
  const token = epoch
  open.value = true
  try {
    await store.refreshCapabilities()
    if (!current(token)) return
    const rows = await store.recent(props.projectId, props.scenario, context())
    if (current(token)) recoverable.value = rows
  } catch { if (current(token)) recoverable.value = [] }
}
async function record() {
  error.value = ''
  try { await start() } catch { error.value = t('platformAI.microphoneError') }
}
async function waitForJob(job, token) {
  controller = new AbortController()
  const began = Date.now()
  while (current(token) && ['pending', 'processing'].includes(job.status)) {
    if (Date.now() - began > 120000) throw new Error('timeout')
    await new Promise((resolve) => { finishDelay = resolve; timer = setTimeout(resolve, 1500) })
    if (!current(token)) return null
    job = await store.job(job.id, controller.signal)
  }
  if (!current(token)) return null
  if (!job || job.status !== 'ready') throw new Error('failed')
  return job
}
function convert() {
  return run(async (token) => {
    transcriptionRequestId ||= crypto.randomUUID()
    const item = await store.transcribe(audio.value, { purpose: 'voice_report', projectId: props.projectId, requestId: transcriptionRequestId })
    if (!current(token)) return
    transcriptionId.value = item.id
    if (item.status === 'failed') transcriptionRequestId = ''
    const result = await waitForJob(item, token)
    if (result) { transcript.value = result.transcript; proposal.value = null; clear() }
    await store.refreshCapabilities()
  })
}
function generate() {
  return run(async (token) => {
    const body = {
      transcription_id: transcriptionId.value, transcript: transcript.value,
      scenario: props.scenario, language: locale.value.startsWith('en') ? 'en' : 'es',
      ...context(),
    }
    if (JSON.stringify(body) !== draftRequestBody) { draftRequestBody = JSON.stringify(body); draftRequestId = crypto.randomUUID() }
    const item = await store.generateReport(props.projectId, { ...body, request_id: draftRequestId })
    if (!current(token)) return
    draftId.value = item.id
    if (item.status === 'failed') draftRequestBody = ''
    const result = await waitForJob(item, token)
    if (result) proposal.value = result.proposal
  })
}
async function discard() {
  await run(async (token) => {
    for (const id of [draftId.value, transcriptionId.value].filter(Boolean)) await store.discard(id)
    if (current(token)) { resetPreparation(); recoverable.value = [] }
  })
}
async function restore(item) {
  await run(async (token) => {
    const result = await store.job(item.id)
    if (!current(token)) return
    if (result.operation === 'draft') { draftId.value = result.id; proposal.value = result.proposal }
    else { transcriptionId.value = result.id; transcript.value = result.transcript }
  })
}
async function apply() {
  await run(async (token) => {
    await store.refreshCapabilities()
    if (!store.voiceAvailable) throw new Error('disabled')
    // Read again so disabled permissions and changed context cannot apply a stale result.
    await store.job(draftId.value)
    if (!current(token)) return
    emit('apply', { ...proposal.value })
    for (const id of [draftId.value, transcriptionId.value].filter(Boolean)) await store.discard(id)
    if (current(token)) { resetPreparation(); open.value = false; recoverable.value = [] }
  })
}
</script>

<template>
  <section v-if="store.voiceAvailable || open" class="space-y-3 rounded-xl border border-border-muted p-3" data-testid="voice-report-input">
    <BaseButton v-if="!open && store.voiceAvailable" type="button" variant="secondary" data-tour="voice-report" @click="show">{{ t('platformAI.reportByVoice') }}</BaseButton>
    <PlatformAIQuotaMeter :quota="store.capabilities?.quota" />
    <template v-if="open">
      <p class="text-sm text-text-muted">{{ t('platformAI.voiceHint') }}</p>
      <BaseAlert v-if="!store.voiceAvailable" variant="warning">{{ t('platformAI.disabled') }}</BaseAlert>
      <BaseAlert v-if="error" variant="danger" role="alert">{{ error }}</BaseAlert>
      <div v-if="store.voiceAvailable" class="flex flex-wrap items-center gap-2">
        <BaseButton v-if="!recording" type="button" variant="secondary" :disabled="busy || store.capabilities?.quota?.remaining === 0" :disabled-reason="t(busy ? 'platformAI.processing' : 'platformAI.quotaEmpty')" @click="record">{{ t('platformAI.record') }}</BaseButton>
        <BaseButton v-else type="button" variant="danger" @click="stop">{{ t('platformAI.stop') }} · {{ seconds }} / 60</BaseButton>
        <BaseButton v-if="audio && !recording" type="button" :disabled="busy || store.capabilities?.quota?.remaining === 0" :disabled-reason="t(busy ? 'platformAI.processing' : 'platformAI.quotaEmpty')" @click="convert">{{ t('platformAI.transcribe') }}</BaseButton>
        <span v-if="busy" class="text-sm text-text-muted" role="status">{{ t('platformAI.processing') }}</span>
      </div>
      <audio v-if="audioUrl" :src="audioUrl" controls class="w-full" :aria-label="t('platformAI.recording')" />
      <div v-if="recoverable.length && !transcript && !proposal" class="flex flex-wrap gap-2">
        <BaseButton v-for="item in recoverable" :key="item.id" type="button" variant="ghost" @click="restore(item)">{{ t('platformAI.recover') }} · {{ new Date(item.created_at).toLocaleString() }}</BaseButton>
      </div>
      <template v-if="transcript">
        <BaseFormField :label="t('platformAI.transcript')" :for="`${inputId}-transcript`"><BaseTextarea :id="`${inputId}-transcript`" v-model="transcript" :rows="4" maxlength="6000" data-testid="voice-transcript" /></BaseFormField>
        <BaseButton type="button" :disabled="busy || !transcript.trim() || !store.voiceAvailable" :disabled-reason="t('platformAI.reviewFirst')" @click="generate">{{ t('platformAI.generate') }}</BaseButton>
      </template>
      <div v-if="proposal" class="space-y-3" data-testid="voice-proposal">
        <p class="text-sm text-text-muted">{{ t('platformAI.reviewHint') }}</p>
        <BaseFormField v-for="field in editableFields" :key="field" :label="t(`platformAI.fields.${field}`)" :for="`${inputId}-${field}`"><BaseTextarea :id="`${inputId}-${field}`" v-model="proposal[field]" :rows="3" :maxlength="field === 'title' ? 300 : field === 'module_or_screen' ? 200 : 6000" :data-testid="`voice-proposal-${field}`" /></BaseFormField>
        <BaseFormField v-if="scenario === 'bug'" :label="t('platformAI.fields.steps_to_reproduce')" :for="`${inputId}-steps`">
          <BaseTextarea :id="`${inputId}-steps`" :model-value="proposal.steps_to_reproduce.join('\n')" :rows="3" @update:model-value="proposal.steps_to_reproduce = $event.split('\n').filter(Boolean)" />
        </BaseFormField>
        <p v-if="proposal.missing_details.length" class="text-sm text-text-muted">{{ t('platformAI.missing') }}: {{ proposal.missing_details.join(' · ') }}</p>
        <BaseButton type="button" :disabled="busy || !store.voiceAvailable" :disabled-reason="t('platformAI.reviewFirst')" @click="apply">{{ t('platformAI.useText') }}</BaseButton>
      </div>
      <BaseButton type="button" variant="ghost" :disabled="busy || recording" :disabled-reason="t('platformAI.processing')" @click="discard">{{ t('platformAI.discard') }}</BaseButton>
    </template>
  </section>
</template>
