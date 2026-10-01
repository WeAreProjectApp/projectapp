<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { usePlatformDeliveryStore } from '~/stores/platform-delivery'
import { useClipboardFeedback } from '~/composables/useClipboardFeedback'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseCheckbox from '~/components/base/BaseCheckbox.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseModalActions from '~/components/base/BaseModalActions.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import BaseTextarea from '~/components/base/BaseTextarea.vue'
import DeliveryPromptSources from './DeliveryPromptSources.vue'

const props = defineProps({
  mode: { type: String, required: true },
  stage: { type: Object, default: null },
})
const emit = defineEmits(['cancel', 'imported', 'reply'])
const { t } = useI18n()
const store = usePlatformDeliveryStore()
const clipboard = useClipboardFeedback()
const options = ref(null)
const loading = ref(true)
const error = ref('')
const feedback = ref('')
const context = ref(null)
const outputJson = ref('')
const preview = ref(null)
const previewedJson = ref('')
const draftText = ref('')
const fieldErrors = reactive({})
const selection = reactive({
  contract_id: '', amendment_ids: [], scope_id: '', sources: [],
  missing_sources: '', uncertainties: '', instructions: '',
})
const isReply = computed(() => props.mode === 'reply')
const stageScope = computed(() => store.scopes.find((scope) =>
  scope.phases?.some((phase) => phase.stages?.some((stage) => stage.id === props.stage?.id))))
const contracts = computed(() => options.value?.contracts || store.contracts)
const selectedContract = computed(() => {
  const contract = contracts.value.find((item) => String(item.id) === String(selection.contract_id))
  return contract ? { ...contract, amendments: contract.amendments || (options.value?.amendments || []).filter((item) => item.contract_id === contract.id) } : null
})
const contractOptions = computed(() => contracts.value.map((item) => ({ value: item.id, label: item.title })))
const scopeOptions = computed(() => [
  { value: '', label: t('platformDelivery.promptAuthoring.newScope') },
  ...store.scopes.filter((item) => String(item.contract_id) === String(selection.contract_id)).map((item) => ({ value: item.id, label: item.title })),
])
const selectedScope = computed(() => store.scopes.find((item) => String(item.id) === String(selection.scope_id)))
const candidates = computed(() => [
  ...(options.value?.documents || store.documentOptions).map((item) => ({ ...item, selectionKey: 'document-' + item.id, document_id: item.id })),
  ...(options.value?.proposal_documents || store.proposalDocumentOptions).map((item) => ({ ...item, selectionKey: 'proposal-' + item.id, proposal_document_id: item.id })),
])
const sourceRoles = computed(() => [
  { value: 'contractual_annex', label: t('platformDelivery.promptSources.roles.contractual_annex') },
  { value: 'reference', label: t('platformDelivery.promptSources.roles.reference') },
])
const hasCurrentPreview = computed(() => !!preview.value?.valid && previewedJson.value === outputJson.value)
const splitLines = (value) => value.split('\n').map((line) => line.trim()).filter(Boolean)
const sourceSelection = (candidate) => selection.sources.find((item) =>
  candidate.document_id ? item.document_id === candidate.document_id : item.proposal_document_id === candidate.proposal_document_id)
function toggleSource(candidate, checked) {
  const current = sourceSelection(candidate)
  if (current) selection.sources.splice(selection.sources.indexOf(current), 1)
  if (checked) selection.sources.push({
    ...(candidate.document_id ? { document_id: candidate.document_id } : { proposal_document_id: candidate.proposal_document_id }),
    role: 'reference', applicability_note: '',
  })
}
function invalidate() {
  context.value = null
  preview.value = null
  previewedJson.value = ''
  feedback.value = ''
}
function fail(result) {
  error.value = result.status === 409 ? t('platformDelivery.conflict') : result.message || t('platformDelivery.actionError')
}
async function loadOptions() {
  loading.value = true
  const result = await store.fetchPromptOptions()
  if (result.success) {
    options.value = result.data
    error.value = ''
    if (isReply.value && stageScope.value) {
      selection.contract_id = stageScope.value.contract_id
      selection.scope_id = stageScope.value.id
      selection.amendment_ids = stageScope.value.amendment_id ? [stageScope.value.amendment_id] : []
    }
  } else fail(result)
  loading.value = false
}
async function prepare() {
  error.value = ''
  Object.keys(fieldErrors).forEach((key) => delete fieldErrors[key])
  if (!selection.contract_id) fieldErrors.contract = t('platformDelivery.fieldRequired')
  selection.sources.forEach((source, index) => {
    if (!source.applicability_note.trim()) fieldErrors['source-' + index] = t('platformDelivery.fieldRequired')
  })
  if (Object.keys(fieldErrors).length) return
  const result = await store.preparePrompt({
    mode: props.mode, contract_id: Number(selection.contract_id),
    amendment_ids: selection.amendment_ids.map(Number),
    ...(selection.scope_id ? { scope_id: Number(selection.scope_id) } : {}),
    ...(isReply.value ? { stage_id: props.stage.id } : {}),
    sources: selection.sources.map((item) => ({ ...item, applicability_note: item.applicability_note.trim() })),
    missing_sources: splitLines(selection.missing_sources),
    uncertainties: splitLines(selection.uncertainties), instructions: selection.instructions.trim(),
  })
  if (!result.success) { fail(result); return }
  context.value = result.data
  preview.value = null
  previewedJson.value = ''
  outputJson.value = JSON.stringify(result.data.template, null, 2)
}
async function copyPrompt() {
  const success = await clipboard.copyText({
    key: 'delivery-selected-prompt', text: context.value.prompt,
    successLabel: t('platformDelivery.copied'), errorLabel: t('platformDelivery.copyError'),
  })
  feedback.value = t(success ? 'platformDelivery.copied' : 'platformDelivery.copyError')
}
async function downloadSource(source) {
  const result = await store.downloadPromptSource(source)
  if (!result.success) fail(result)
}
async function validateOutput() {
  error.value = ''
  preview.value = null
  let payload
  try { payload = JSON.parse(outputJson.value) } catch { error.value = t('platformDelivery.invalidJson'); return }
  if (payload?.context_id !== context.value?.id) { error.value = t('platformDelivery.promptAuthoring.contextMismatch'); return }
  const result = isReply.value ? await store.previewReply(payload) : await store.previewImport(payload)
  if (!result.success) { fail(result); return }
  preview.value = result.data
  previewedJson.value = outputJson.value
  if (isReply.value) draftText.value = result.data.response_text || result.data.payload?.response_text || payload.response_text
}
async function applyGuides() {
  if (!hasCurrentPreview.value) return
  const result = await store.applyImport(preview.value.payload || JSON.parse(outputJson.value))
  if (!result.success) { fail(result); return }
  emit('imported')
}
function useReplyDraft() {
  if (!hasCurrentPreview.value || !draftText.value.trim()) return
  const payload = preview.value.payload || JSON.parse(outputJson.value)
  const classifications = preview.value.classifications || payload.classifications
  const references = preview.value.source_references || classifications.flatMap((item) => item.citations || [])
  emit('reply', {
    message: draftText.value.trim(), context_id: context.value.id,
    source_references: references, classifications,
  })
}
watch(() => selection.contract_id, () => {
  if (isReply.value) return
  selection.amendment_ids = []
  selection.scope_id = ''
  selection.sources = []
})
watch(() => selection.scope_id, (scopeId) => {
  const scope = store.scopes.find((item) => String(item.id) === String(scopeId))
  selection.amendment_ids = scope?.amendment_id ? [scope.amendment_id] : []
})
watch(selection, invalidate, { deep: true })
onMounted(loadOptions)
</script>

<template>
  <section class="min-w-0 space-y-5" data-testid="delivery-prompt-workbench">
    <p class="text-sm text-text-muted">{{ t(isReply ? 'platformDelivery.promptAuthoring.replyHint' : 'platformDelivery.promptAuthoring.guidesHint') }}</p>
    <BaseAlert variant="info">{{ t('platformDelivery.promptAuthoring.scopeRule') }}</BaseAlert>
    <BaseAlert v-if="error" variant="danger" role="alert" data-testid="delivery-prompt-error">{{ error }}</BaseAlert>
    <p v-if="loading" class="text-sm text-text-muted" role="status">{{ t('platformDelivery.loading') }}</p>
    <BaseButton v-else-if="!options" variant="secondary" @click="loadOptions">{{ t('platformDelivery.retry') }}</BaseButton>
    <template v-else>
      <BaseFormField :label="t('platformDelivery.contract')" for="delivery-prompt-contract" :error="fieldErrors.contract" required>
        <BaseSelect id="delivery-prompt-contract" v-model="selection.contract_id" :options="contractOptions" :placeholder="t('platformDelivery.select')" :disabled="isReply" :error="!!fieldErrors.contract" data-testid="delivery-prompt-contract" />
      </BaseFormField>
      <BaseFormField :label="t('platformDelivery.scope')" for="delivery-prompt-scope">
        <BaseSelect id="delivery-prompt-scope" v-model="selection.scope_id" :options="scopeOptions" :disabled="isReply" data-testid="delivery-prompt-scope" />
      </BaseFormField>
      <fieldset v-if="selectedContract?.amendments?.length" class="space-y-2">
        <legend class="mb-2 text-sm font-medium text-text-default">{{ t('platformDelivery.promptAuthoring.applicableAmendments') }}</legend>
        <BaseCheckbox v-for="amendment in selectedContract.amendments" :key="amendment.id" v-model="selection.amendment_ids" :value="amendment.id" :disabled="selectedScope?.amendment_id === amendment.id" :disabled-reason="t('platformDelivery.promptAuthoring.scopeAmendment')" class="flex" :data-testid="'delivery-prompt-amendment-' + amendment.id">{{ amendment.title }}</BaseCheckbox>
      </fieldset>
      <p class="text-sm text-text-muted">{{ t('platformDelivery.promptAuthoring.amendmentHint') }}</p>
      <details class="min-w-0 space-y-3 rounded-xl border border-border-default p-4">
        <summary class="cursor-pointer text-sm font-semibold text-text-default">{{ t('platformDelivery.promptAuthoring.selectSources') }}</summary>
        <p class="mt-3 text-sm text-text-muted">{{ t('platformDelivery.promptAuthoring.sourceHint') }}</p>
        <p v-if="!candidates.length" class="text-sm text-text-muted">{{ t('platformDelivery.noDocuments') }}</p>
        <article v-for="candidate in candidates" :key="candidate.selectionKey" class="min-w-0 space-y-3 rounded-xl bg-surface-raised p-3">
          <BaseCheckbox :model-value="!!sourceSelection(candidate)" :data-testid="'delivery-prompt-select-' + candidate.selectionKey" @update:model-value="toggleSource(candidate, $event)">{{ candidate.title }}</BaseCheckbox>
          <p v-if="candidate.source_version || candidate.document_type" class="text-xs text-text-muted">{{ candidate.document_type }} · {{ candidate.source_version }}</p>
          <template v-if="sourceSelection(candidate)">
            <BaseFormField :label="t('platformDelivery.promptAuthoring.sourceRole')" :for="'delivery-source-role-' + candidate.selectionKey">
              <BaseSelect :id="'delivery-source-role-' + candidate.selectionKey" v-model="sourceSelection(candidate).role" :options="sourceRoles" />
            </BaseFormField>
            <BaseFormField :label="t('platformDelivery.promptAuthoring.applicabilityNote')" :for="'delivery-source-note-' + candidate.selectionKey" :error="fieldErrors['source-' + selection.sources.indexOf(sourceSelection(candidate))]" required>
              <BaseTextarea :id="'delivery-source-note-' + candidate.selectionKey" v-model="sourceSelection(candidate).applicability_note" :rows="3" />
            </BaseFormField>
          </template>
        </article>
      </details>
      <BaseFormField :label="t('platformDelivery.promptAuthoring.missingSources')" for="delivery-prompt-missing" :hint="t('platformDelivery.stepsHint')">
        <BaseTextarea id="delivery-prompt-missing" v-model="selection.missing_sources" :rows="2" data-testid="delivery-prompt-missing" />
      </BaseFormField>
      <BaseFormField :label="t('platformDelivery.promptAuthoring.uncertainties')" for="delivery-prompt-uncertainties">
        <BaseTextarea id="delivery-prompt-uncertainties" v-model="selection.uncertainties" :rows="2" />
      </BaseFormField>
      <BaseFormField :label="t(isReply ? 'platformDelivery.promptAuthoring.requests' : 'platformDelivery.promptAuthoring.instructions')" for="delivery-prompt-instructions">
        <BaseTextarea id="delivery-prompt-instructions" v-model="selection.instructions" :rows="4" data-testid="delivery-prompt-instructions" />
      </BaseFormField>
      <BaseButton :loading="store.isUpdating" data-testid="delivery-prompt-prepare" @click="prepare">{{ t('platformDelivery.promptAuthoring.prepare') }}</BaseButton>
      <template v-if="context">
        <DeliveryPromptSources :context="context" @download="downloadSource" />
        <BaseButton variant="secondary" data-testid="delivery-prompt-copy" @click="copyPrompt">{{ t('platformDelivery.copyPrompt') }}</BaseButton>
        <p v-if="feedback" class="text-sm text-text-muted" role="status">{{ feedback }}</p>
        <details class="rounded-xl bg-surface-raised p-3"><summary class="cursor-pointer text-sm font-medium text-text-default">{{ t('platformDelivery.promptAuthoring.showPrompt') }}</summary><pre class="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs text-text-default" data-testid="delivery-prompt-text">{{ context.prompt }}</pre></details>
        <BaseFormField :label="t(isReply ? 'platformDelivery.promptAuthoring.replyJson' : 'platformDelivery.json')" for="delivery-prompt-json">
          <BaseTextarea id="delivery-prompt-json" v-model="outputJson" :rows="10" class="font-mono" data-testid="delivery-prompt-json" />
        </BaseFormField>
        <BaseAlert v-if="hasCurrentPreview" variant="success">{{ t('platformDelivery.previewReady') }}</BaseAlert>
        <BaseButton variant="secondary" :loading="store.isUpdating" data-testid="delivery-prompt-preview" @click="validateOutput">{{ t('platformDelivery.preview') }}</BaseButton>
        <section v-if="hasCurrentPreview && !isReply" class="space-y-2">
          <h3 class="text-sm font-semibold text-text-default">{{ t('platformDelivery.previewSummary') }}</h3>
          <pre class="max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs text-text-default">{{ JSON.stringify(preview.summary, null, 2) }}</pre>
        </section>
        <section v-if="hasCurrentPreview && isReply" class="space-y-3">
          <article v-for="(item, index) in preview.classifications || preview.payload?.classifications" :key="index" class="space-y-2 rounded-xl border border-border-default p-3">
            <h3 class="break-words text-sm font-semibold text-text-default">{{ item.request }}</h3>
            <p class="text-sm font-medium text-text-default">{{ t('platformDelivery.promptAuthoring.classifications.' + item.classification) }}</p>
            <p class="whitespace-pre-line break-words text-sm text-text-muted">{{ item.rationale }}</p>
            <p v-for="(citation, citationIndex) in item.citations" :key="citationIndex" class="break-words text-xs text-text-muted">{{ citation.source_key }} · {{ citation.locator }} — {{ citation.quote }}</p>
          </article>
          <BaseFormField :label="t('platformDelivery.promptAuthoring.replyDraft')" for="delivery-prompt-reply-draft">
            <BaseTextarea id="delivery-prompt-reply-draft" v-model="draftText" :rows="6" data-testid="delivery-prompt-reply-draft" />
          </BaseFormField>
          <p class="text-sm text-text-muted">{{ t('platformDelivery.promptAuthoring.manualReply') }}</p>
        </section>
      </template>
      <BaseModalActions>
        <BaseButton variant="ghost" @click="emit('cancel')">{{ t('platformDelivery.cancel') }}</BaseButton>
        <BaseButton v-if="!isReply && context" :disabled="!hasCurrentPreview" :disabled-reason="t('platformDelivery.previewChanged')" :loading="store.isUpdating" data-testid="delivery-prompt-apply" @click="applyGuides">{{ t('platformDelivery.apply') }}</BaseButton>
        <BaseButton v-if="isReply && context" :disabled="!hasCurrentPreview || !draftText.trim()" :disabled-reason="t('platformDelivery.previewChanged')" data-testid="delivery-prompt-use-reply" @click="useReplyDraft">{{ t('platformDelivery.promptAuthoring.useDraft') }}</BaseButton>
      </BaseModalActions>
    </template>
  </section>
</template>
