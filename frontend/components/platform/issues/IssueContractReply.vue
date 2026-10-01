<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseCheckbox from '~/components/base/BaseCheckbox.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import BaseTextarea from '~/components/base/BaseTextarea.vue'
import DeliveryPromptSources from '~/components/platform/delivery/DeliveryPromptSources.vue'
import { useClipboardFeedback } from '~/composables/useClipboardFeedback'
import { usePlatformIssueReportsStore } from '~/stores/platform-issue-reports'

const props = defineProps({
  modelValue: { type: Object, default: null },
  projectId: { type: [String, Number], required: true },
  kind: { type: String, required: true }, ticket: { type: Object, required: true },
  contractId: { type: Number, default: null }, message: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'draft'])
const { t } = useI18n()
const store = usePlatformIssueReportsStore()
const clipboard = useClipboardFeedback()
const options = ref(null)
const context = ref(null)
const preview = ref(null)
const outputJson = ref('')
const previewedJson = ref('')
const humanReviewed = ref(false)
const busy = ref(false)
const loading = ref(true)
const error = ref('')
const feedback = ref('')
const selection = reactive({ amendment_ids: [], sources: [], missing_sources: '', uncertainties: '', instructions: '' })
let preparationRetry = null
let generation = 0
let revision = 0
const contract = computed(() => options.value?.contracts?.find((item) => item.id === props.contractId))
const amendments = computed(() => (options.value?.amendments || []).filter((item) => item.contract_id === props.contractId))
const candidates = computed(() => [
  ...(options.value?.documents || []).map((item) => ({ ...item, key: `document-${item.id}`, document_id: item.id })),
  ...(options.value?.proposal_documents || []).map((item) => ({ ...item, key: `proposal-${item.id}`, proposal_document_id: item.id })),
])
const currentPreview = computed(() => preview.value?.valid && previewedJson.value === outputJson.value)
const sourceRoles = computed(() => [
  { value: 'reference', label: t('platformIssues.reply.reference') },
  { value: 'contractual_annex', label: t('platformIssues.reply.annex') },
])
const lines = (text) => text.split('\n').map((line) => line.trim()).filter(Boolean)
const selectedSource = (candidate) => selection.sources.find((source) =>
  candidate.document_id ? source.document_id === candidate.document_id : source.proposal_document_id === candidate.proposal_document_id)
function toggleSource(candidate, checked) {
  const found = selectedSource(candidate)
  if (found) selection.sources.splice(selection.sources.indexOf(found), 1)
  if (checked) selection.sources.push({
    ...(candidate.document_id ? { document_id: candidate.document_id } : { proposal_document_id: candidate.proposal_document_id }),
    role: 'reference', applicability_note: '',
  })
}
function clearPreparation() {
  revision += 1
  const hadDraft = !!context.value
  context.value = null
  preview.value = null
  humanReviewed.value = false
  emit('update:modelValue', null)
  if (hadDraft) emit('draft', '')
}
function emitReview() {
  if (!preview.value || !context.value) return
  emit('update:modelValue', {
    context_id: context.value.id, expected_version: context.value.captured_version,
    expected_ticket_version: context.value.destination.ticket_version,
    classifications: preview.value.classifications, source_references: preview.value.source_references,
    human_reviewed: !!humanReviewed.value && !!currentPreview.value,
  })
}
async function load() {
  const current = ++generation
  loading.value = true
  const result = await store.replyOptions(props.projectId, props.kind, props.ticket.id)
  if (current !== generation) return
  loading.value = false
  if (result.success) options.value = result.data
  else error.value = result.message
}
async function prepare() {
  if (busy.value || !options.value) return
  error.value = ''
  if (selection.sources.some((source) => !source.applicability_note.trim())) {
    error.value = t('platformIssues.reply.sourceReasonRequired'); return
  }
  const payload = {
    expected_version: options.value.version, expected_ticket_version: props.ticket.version,
    contract_id: props.contractId, amendment_ids: selection.amendment_ids.map(Number),
    sources: selection.sources, missing_sources: lines(selection.missing_sources),
    uncertainties: lines(selection.uncertainties), instructions: selection.instructions.trim(),
  }
  const fingerprint = JSON.stringify(payload)
  if (preparationRetry?.fingerprint !== fingerprint) preparationRetry = { fingerprint, requestId: crypto.randomUUID() }
  busy.value = true
  const current = revision
  const result = await store.prepareReply(props.projectId, props.kind, props.ticket.id, { ...payload, request_id: preparationRetry.requestId })
  busy.value = false
  if (current !== revision) return
  if (!result.success) { error.value = result.message; return }
  clearPreparation()
  context.value = result.data
  outputJson.value = JSON.stringify(result.data.template, null, 2)
}
async function validateOutput() {
  if (busy.value || !context.value) return
  error.value = ''
  let payload
  try { payload = JSON.parse(outputJson.value) } catch { error.value = t('platformIssues.reply.invalidJson'); return }
  if (payload.context_id !== context.value.id) { error.value = t('platformIssues.reply.contextMismatch'); return }
  busy.value = true
  const current = revision
  const json = outputJson.value
  const result = await store.previewReply(props.projectId, props.kind, props.ticket.id, {
    expected_version: context.value.captured_version,
    expected_ticket_version: context.value.destination.ticket_version, payload,
  })
  busy.value = false
  if (current !== revision || json !== outputJson.value) return
  if (!result.success) { preview.value = null; error.value = result.message; return }
  preview.value = result.data
  previewedJson.value = outputJson.value
  humanReviewed.value = false
  emit('draft', result.data.response_text)
  emitReview()
}
async function copyPrompt() {
  const success = await clipboard.copyText({
    key: 'issue-contract-prompt', text: context.value.prompt,
    successLabel: t('platformIssues.reply.copied'), errorLabel: t('platformIssues.reply.copyError'),
  })
  feedback.value = t(success ? 'platformIssues.reply.copied' : 'platformIssues.reply.copyError')
}
async function downloadSource(source) {
  const result = await store.downloadReplySource(props.projectId, props.kind, props.ticket.id, context.value.id, source.source_key)
  if (!result.success) { error.value = result.message; return }
  const url = URL.createObjectURL(result.data)
  try {
    const link = document.createElement('a')
    link.href = url
    link.download = source.filename || 'captured-source.bin'
    document.body.appendChild(link)
    link.click()
    link.remove()
  } finally { URL.revokeObjectURL(url) }
}
watch(() => [props.projectId, props.kind, props.ticket.id], () => { clearPreparation(); load() })
watch(() => [props.ticket.version, props.contractId], () => {
  clearPreparation()
  selection.amendment_ids = props.contractId && props.ticket.origin_context?.amendment_id ? [props.ticket.origin_context.amendment_id] : []
  selection.sources = []
}, { immediate: true })
watch(selection, clearPreparation, { deep: true })
watch(outputJson, () => { humanReviewed.value = false; emitReview() })
watch(() => props.message, () => { humanReviewed.value = false; emitReview() })
watch(humanReviewed, emitReview)
onMounted(load)
</script>

<template>
  <details class="space-y-3 rounded-xl border border-border-default p-3" data-testid="issue-contract-reply">
    <summary class="cursor-pointer text-sm font-semibold text-text-default">{{ t('platformIssues.reply.title') }}</summary>
    <p class="text-xs text-text-muted">{{ t('platformIssues.reply.hint') }}</p>
    <p class="text-xs text-text-default">{{ t('platformIssues.contract') }}: {{ contract?.title || t('platformIssues.noContract') }}</p>
    <BaseAlert v-if="!contractId" variant="warning">{{ t('platformIssues.reply.noContract') }}</BaseAlert>
    <p v-if="loading" class="text-xs text-text-muted">{{ t('platformIssues.loading') }}</p>
    <fieldset v-if="contractId" class="space-y-2">
      <legend class="text-xs font-medium text-text-default">{{ t('platformIssues.reply.amendments') }}</legend>
      <BaseCheckbox v-for="item in amendments" :key="item.id" v-model="selection.amendment_ids" :value="item.id">{{ item.title }}</BaseCheckbox>
    </fieldset>
    <fieldset v-if="contractId && candidates.length" class="space-y-3">
      <legend class="text-xs font-medium text-text-default">{{ t('platformIssues.reply.sources') }}</legend>
      <section v-for="candidate in candidates" :key="candidate.key" class="space-y-2">
        <BaseCheckbox :model-value="!!selectedSource(candidate)" @update:model-value="toggleSource(candidate, $event)">{{ candidate.title }}</BaseCheckbox>
        <template v-if="selectedSource(candidate)">
          <label :for="`issue-source-role-${candidate.key}`" class="block text-xs text-text-muted">{{ t('platformIssues.reply.sourceRole') }}</label>
          <BaseSelect :id="`issue-source-role-${candidate.key}`" v-model="selectedSource(candidate).role" :options="sourceRoles" />
          <label :for="`issue-source-reason-${candidate.key}`" class="block text-xs text-text-muted">{{ t('platformIssues.reply.sourceReason') }}</label>
          <BaseTextarea :id="`issue-source-reason-${candidate.key}`" v-model="selectedSource(candidate).applicability_note" :rows="2" />
        </template>
      </section>
    </fieldset>
    <label for="issue-reply-missing" class="block text-xs text-text-muted">{{ t('platformIssues.reply.missing') }}</label>
    <BaseTextarea id="issue-reply-missing" v-model="selection.missing_sources" :rows="2" />
    <label for="issue-reply-uncertainties" class="block text-xs text-text-muted">{{ t('platformIssues.reply.uncertainties') }}</label>
    <BaseTextarea id="issue-reply-uncertainties" v-model="selection.uncertainties" :rows="2" />
    <label for="issue-reply-instructions" class="block text-xs text-text-muted">{{ t('platformIssues.reply.instructions') }}</label>
    <BaseTextarea id="issue-reply-instructions" v-model="selection.instructions" :rows="2" />
    <BaseButton variant="secondary" :loading="busy" :disabled="loading || !options" :disabled-reason="t('platformIssues.loading')" @click="prepare">{{ t('platformIssues.reply.prepare') }}</BaseButton>
    <template v-if="context">
      <DeliveryPromptSources :context="context" @download="downloadSource" />
      <BaseButton variant="secondary" @click="copyPrompt">{{ t('platformIssues.reply.copyPrompt') }}</BaseButton>
      <p v-if="feedback" role="status" class="text-xs text-text-muted">{{ feedback }}</p>
      <label for="issue-reply-json" class="block text-xs text-text-muted">{{ t('platformIssues.reply.json') }}</label>
      <BaseTextarea id="issue-reply-json" v-model="outputJson" :rows="10" data-testid="issue-reply-json" />
      <BaseButton variant="secondary" :loading="busy" @click="validateOutput">{{ t('platformIssues.reply.preview') }}</BaseButton>
      <template v-if="currentPreview">
        <p class="text-xs text-text-muted">{{ t('platformIssues.reply.finalText') }}</p>
        <ul class="space-y-1 text-xs text-text-default">
          <li v-for="(item, index) in preview.classifications" :key="index">{{ item.request }}: {{ t(`platformIssues.scope.${item.classification === 'inside_scope' ? 'within_scope' : item.classification}`) }}</li>
        </ul>
        <BaseCheckbox v-model="humanReviewed" data-testid="issue-reply-human-reviewed">{{ t('platformIssues.reply.humanReview') }}</BaseCheckbox>
      </template>
      <BaseButton variant="ghost" @click="clearPreparation">{{ t('platformIssues.reply.discard') }}</BaseButton>
    </template>
    <p v-if="error" role="alert" class="text-xs text-danger-strong">{{ error }}</p>
    <BaseButton v-if="error" variant="secondary" @click="clearPreparation(); load()">{{ t('platformIssues.reply.reload') }}</BaseButton>
  </details>
</template>
