<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import DeliveryNoticeHistory from '~/components/platform/delivery/DeliveryNoticeHistory.vue'
import { usePlatformAuthStore } from '~/stores/platform-auth'
import { usePlatformDeliveryStore } from '~/stores/platform-delivery'
import { usePlatformDocumentsStore } from '~/stores/platform-documents'
import { usePlatformProjectsStore } from '~/stores/platform-projects'
import { useClipboardFeedback } from '~/composables/useClipboardFeedback'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseCheckbox from '~/components/base/BaseCheckbox.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseInput from '~/components/base/BaseInput.vue'
import BaseModal from '~/components/base/BaseModal.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import BaseTextarea from '~/components/base/BaseTextarea.vue'
import DeliveryAuthoringForm from './DeliveryAuthoringForm.vue'
import DeliveryDocumentPicker from './DeliveryDocumentPicker.vue'
import DeliveryDocuments from './DeliveryDocuments.vue'
import DeliveryReviewForm from './DeliveryReviewForm.vue'
import DeliveryStage from './DeliveryStage.vue'
import DeliveryPromptWorkbench from './DeliveryPromptWorkbench.vue'
import DeliveryPromptSources from './DeliveryPromptSources.vue'

const props = defineProps({ projectId: { type: [String, Number], required: true } })
const { t } = useI18n()
const localePath = useLocalePath()
const route = useRoute()
const authStore = usePlatformAuthStore()
const store = usePlatformDeliveryStore()
const documentsStore = usePlatformDocumentsStore()
const projectsStore = usePlatformProjectsStore()
const clipboard = useClipboardFeedback()
const isAdmin = computed(() => authStore.isAdmin && store.workspace?.is_admin)
const loadFailed = ref(false)
const feedback = ref('')
const feedbackTone = ref('success')
const formError = ref('')
const optionsError = ref(false)
const commercialPhases = ref([])
const dialog = ref('')
const selected = ref(null)
const reviewDraft = ref(null)
const author = ref(null)
const confirm = ref(null)
const importJson = ref('')
const preview = ref(null)
const previewedJson = ref('')
const reportMessage = ref('')
const reportRequirementIds = ref([])
const reportDocumentIds = ref([])
const reportInternal = ref(false)
const reportPromptProof = ref(null)
const reportHumanReviewed = ref(false)
const retainedPromptContext = ref(null)
const loadingPromptContext = ref(false)
const promptContexts = ref([])
const loadingPromptHistory = ref(false)
const documentId = ref('')
const signature = reactive({ signer_name: '', signed_at: '', attestation: '', file: null, accept: false })
const signatureErrors = reactive({})
const entityNames = { contracts: 'contract', amendments: 'amendment', scopes: 'scope', phases: 'phase', stages: 'stage', requirements: 'requirement' }
const modalTitle = computed(() => {
  if (dialog.value === 'author') return t(author.value.node ? 'platformDelivery.editTitle' : 'platformDelivery.createTitle', { entity: t(`platformDelivery.${entityNames[author.value.entity]}`) })
  const keys = { import: 'importTitle', guidesPrompt: 'promptAuthoring.createGuides', replyPrompt: 'promptAuthoring.prepareReply', promptContext: 'promptSources.title', promptHistory: 'promptSources.history', review: 'reviewTitle', historical: 'historicalTitle', report: 'reportTitle', externalSignature: 'signatureTitle', sign: 'signTitle', attach: 'attachTitle' }
  return t(`platformDelivery.${keys[dialog.value] || 'close'}`, { title: selected.value?.node?.title || selected.value?.title || '', entity: selected.value?.node?.title || '' })
})
const chosenDocuments = computed(() => {
  if (isAdmin.value) return store.documentOptions
  const stage = selected.value?.node || selected.value
  const links = [...(stage?.documents || []), ...(stage?.requirements || []).flatMap((item) => item.documents || [])]
  return [...new Map(links.map((item) => [item.document_id, { id: item.document_id, title: item.title }])).values()]
})
const documentOptions = computed(() => store.documentOptions.map((item) => ({ value: item.id, label: item.title })))
const previewSummary = computed(() => typeof preview.value?.summary === 'string' ? preview.value.summary : JSON.stringify(preview.value?.summary || {}, null, 2))
const scopesFor = (contractId) => store.scopes.filter((scope) => scope.contract_id === contractId)
const amendmentTitle = (contract, scope) => contract.amendments?.find((item) => item.id === scope.amendment_id)?.title || ''
const statusTone = (status) => status === 'approved' ? 'success' : status === 'rejected' ? 'danger' : status === 'objected' ? 'warning' : 'info'
const signed = (contract) => ['portal', 'external'].includes(contract.signature_status)
function announce(message, tone = 'success') { feedback.value = message; feedbackTone.value = tone }
function failure(result) {
  const message = result.status === 409 ? t('platformDelivery.conflict') : result.message || t('platformDelivery.actionError')
  formError.value = message
  announce(message, 'danger')
}
function open(type, value = null) { dialog.value = type; selected.value = value; formError.value = '' }
function close() { dialog.value = ''; selected.value = null; formError.value = '' }
async function loadOptions() {
  const result = await store.fetchDocumentOptions()
  optionsError.value = !result.success
  const evidence = await store.fetchEvidenceOptions()
  optionsError.value ||= !evidence.success
}
async function load() {
  loadFailed.value = false
  const result = await store.fetchDelivery(props.projectId)
  loadFailed.value = !result.success
  if (result.success && isAdmin.value) {
    await loadOptions()
    commercialPhases.value = await projectsStore.loadPhases(props.projectId)
  }
  await nextTick()
  scrollToStage()
}
function scrollToStage() {
  if (route.query.stage) document.getElementById(`stage-${route.query.stage}`)?.scrollIntoView({ block: 'start' })
}
function openAuthor(value) { author.value = value; open('author') }
async function saveAuthor(payload) {
  const result = author.value.node
    ? await store.updateEntity(author.value.entity, author.value.node.id, payload)
    : await store.createEntity(author.value.entity, payload)
  if (!result.success) { failure(result); return }
  close(); announce(t('platformDelivery.saved'))
}
function requestRemove(value) {
  confirm.value = { ...value, kind: 'remove' }
  open('confirm')
}
function requestPublish(stage) { confirm.value = { kind: 'publish', node: stage }; open('confirm') }
function requestUnlink(document) { confirm.value = { kind: 'unlink', node: document }; open('confirm') }
async function confirmAction() {
  const action = confirm.value
  const result = action.kind === 'publish' ? await store.publishStage(action.node.id)
    : action.kind === 'unlink' ? await store.unlinkDocument(action.node.id)
    : await store.deleteEntity(action.entity, action.node.id)
  if (!result.success) { failure(result); return }
  close(); announce(t(action.kind === 'publish' ? 'platformDelivery.published' : 'platformDelivery.saved'))
}
function openReview(stage, historical = false) { reviewDraft.value = null; open(historical ? 'historical' : 'review', stage) }
async function submitReview(payload) {
  const result = dialog.value === 'historical'
    ? await store.recordHistoricalApprovals(selected.value.id, payload)
    : await store.reviewStage(selected.value.id, payload)
  if (!result.success) { failure(result); return }
  const key = dialog.value === 'historical' ? 'historicalSaved' : 'reviewed'
  close(); announce(t(`platformDelivery.${key}`))
}
function openReport(stage) {
  reportMessage.value = ''; reportRequirementIds.value = []; reportDocumentIds.value = []
  reportInternal.value = false
  reportPromptProof.value = null
  reportHumanReviewed.value = false
  open('report', stage)
}
function openReplyPrompt(stage) { open('replyPrompt', stage) }
function useReplyDraft(proof) {
  const stage = selected.value
  openReport(stage)
  reportPromptProof.value = proof
  reportMessage.value = proof.message
}
function finishPromptImport() { close(); announce(t('platformDelivery.imported')) }
async function openPromptContext(id) {
  retainedPromptContext.value = null
  open('promptContext', { context_id: id })
  loadingPromptContext.value = true
  const result = await store.fetchPromptContext(id)
  if (dialog.value !== 'promptContext' || selected.value?.context_id !== id) return
  if (result.success) retainedPromptContext.value = result.data
  else failure(result)
  loadingPromptContext.value = false
}
async function downloadPromptSource(source) {
  const result = await store.downloadPromptSource(source)
  if (!result.success) failure(result)
}
async function openPromptHistory() {
  promptContexts.value = []
  open('promptHistory')
  loadingPromptHistory.value = true
  const result = await store.fetchPromptContexts()
  if (dialog.value !== 'promptHistory') return
  if (result.success) promptContexts.value = result.data.contexts
  else failure(result)
  loadingPromptHistory.value = false
}
async function sendReport() {
  if (!reportMessage.value.trim()) { formError.value = t('platformDelivery.messageRequired'); return }
  if (reportPromptProof.value && !reportHumanReviewed.value) { formError.value = t('platformDelivery.promptAuthoring.reviewRequired'); return }
  const result = await store.sendMessage({
    level: 'stage', target_id: selected.value.id, message: reportMessage.value.trim(),
    requirement_ids: reportRequirementIds.value, document_ids: reportDocumentIds.value,
    is_internal: isAdmin.value && reportInternal.value,
    ...(reportPromptProof.value ? {
      context_id: reportPromptProof.value.context_id,
      source_references: reportPromptProof.value.source_references,
      classifications: reportPromptProof.value.classifications, human_reviewed: true,
    } : {}),
  })
  if (!result.success) { failure(result); return }
  close(); announce(t('platformDelivery.sent'))
}
function openAttach(value) { documentId.value = ''; open('attach', value) }
async function attachDocument() {
  if (!documentId.value) { formError.value = t('platformDelivery.fieldRequired'); return }
  const result = await store.linkDocument({ level: selected.value.level, target_id: selected.value.node.id, document_id: Number(documentId.value) })
  if (!result.success) { failure(result); return }
  close(); announce(t('platformDelivery.saved'))
}
async function downloadDocument(document) {
  const result = await store.downloadDocument(document)
  if (!result.success) announce(result.message || t('platformDelivery.downloadError'), 'danger')
}
async function copyStage(stage) {
  const path = localePath({ path: `/platform/projects/${props.projectId}/delivery`, query: { stage: stage.id } })
  const success = await clipboard.copyText({ key: `stage-${stage.id}`, text: new URL(path, window.location.origin).href, successLabel: t('platformDelivery.copied'), errorLabel: t('platformDelivery.copyError') })
  announce(t(success ? 'platformDelivery.copied' : 'platformDelivery.copyError'), success ? 'success' : 'danger')
}
function openImport() { preview.value = null; previewedJson.value = ''; open('import') }
async function previewImport() {
  formError.value = ''; preview.value = null
  let payload
  try { payload = JSON.parse(importJson.value) } catch { formError.value = t('platformDelivery.invalidJson'); return }
  const result = await store.previewImport(payload)
  if (!result.success) { failure(result); return }
  preview.value = result.data
  previewedJson.value = importJson.value
}
async function applyImport() {
  if (previewedJson.value !== importJson.value || !preview.value?.valid) { formError.value = t('platformDelivery.previewChanged'); return }
  const result = await store.applyImport(preview.value.payload || JSON.parse(importJson.value))
  if (!result.success) { failure(result); return }
  close(); announce(t('platformDelivery.imported'))
}
function openSignature(value, type) {
  Object.assign(signature, { signer_name: '', signed_at: '', attestation: '', file: null, accept: false })
  Object.keys(signatureErrors).forEach((key) => delete signatureErrors[key])
  open(type, value)
}
async function recordSignature() {
  Object.keys(signatureErrors).forEach((key) => delete signatureErrors[key])
  for (const key of ['signer_name', 'attestation']) if (!signature[key].trim()) signatureErrors[key] = t('platformDelivery.fieldRequired')
  if (!signature.signed_at) signatureErrors.signed_at = t('platformDelivery.signatureDate')
  if (!signature.file || !signature.file.name.toLowerCase().endsWith('.pdf')) signatureErrors.file = t('platformDelivery.pdfRequired')
  if (Object.keys(signatureErrors).length) return
  const payload = new FormData()
  payload.set('file', signature.file)
  payload.set('signer_name', signature.signer_name.trim())
  payload.set('signed_at', new Date(signature.signed_at).toISOString())
  payload.set('attestation', signature.attestation.trim())
  const result = await store.recordExternalSignature(selected.value.entity, selected.value.node.id, payload)
  if (!result.success) { failure(result); return }
  close(); announce(t('platformDelivery.signatureSaved'))
}
async function signPortal() {
  if (!signature.accept || !signature.signer_name.trim()) { formError.value = t('platformDelivery.fieldRequired'); return }
  const result = await documentsStore.signDocument(selected.value.node.document_uuid, signature.signer_name.trim())
  if (!result.success) { failure(result); return }
  close(); announce(t('platformDelivery.signSuccess')); await load()
}
async function refreshVersion() { close(); await load() }
onMounted(load)
watch(() => props.projectId, load)
watch(() => route.query.stage, () => nextTick(scrollToStage))
watch(reportMessage, () => { reportHumanReviewed.value = false })
</script>

<template>
  <div class="min-w-0 space-y-6" data-testid="delivery-workspace">
    <header class="space-y-3">
      <nav class="flex flex-wrap items-center gap-2 text-sm text-text-muted" :aria-label="t('platformDelivery.project')">
        <NuxtLink :to="localePath(`/platform/projects/${projectId}`)" class="text-text-brand underline">{{ store.workspace?.project?.name || t('platformDelivery.project') }}</NuxtLink>
        <span aria-hidden="true">/</span><span>{{ t('platformDelivery.navigation') }}</span>
      </nav>
      <h2 class="text-xl font-semibold text-text-default">{{ t('platformDelivery.title') }}</h2>
      <p class="text-sm text-text-muted">{{ t('platformDelivery.subtitle') }}</p>
    </header>
    <BaseAlert v-if="feedback" :variant="feedbackTone" role="status">{{ feedback }}</BaseAlert>
    <BaseAlert v-if="store.hasConflict" variant="warning" role="alert">
      <p>{{ t('platformDelivery.conflict') }}</p>
      <BaseButton variant="secondary" size="sm" class="mt-3" @click="refreshVersion">{{ t('platformDelivery.refresh') }}</BaseButton>
    </BaseAlert>
    <p v-if="store.isLoading" class="py-8 text-center text-sm text-text-muted" role="status">{{ t('platformDelivery.loading') }}</p>
    <BaseAlert v-else-if="loadFailed" variant="danger" role="alert">
      <p>{{ store.error || t('platformDelivery.loadError') }}</p>
      <BaseButton variant="secondary" size="sm" class="mt-3" @click="load">{{ t('platformDelivery.retry') }}</BaseButton>
    </BaseAlert>
    <template v-else-if="store.workspace">
      <div v-if="isAdmin" class="flex flex-wrap gap-2">
        <BaseButton data-testid="delivery-add-contract" @click="openAuthor({ entity: 'contracts' })">{{ t('platformDelivery.addContract') }}</BaseButton>
        <BaseButton variant="secondary" data-testid="delivery-add-scope" @click="openAuthor({ entity: 'scopes' })">{{ t('platformDelivery.addScope') }}</BaseButton>
        <BaseButton variant="secondary" data-testid="delivery-import" @click="openImport">{{ t('platformDelivery.import') }}</BaseButton>
        <BaseButton variant="secondary" data-testid="delivery-create-guides" @click="open('guidesPrompt')">{{ t('platformDelivery.promptAuthoring.createGuides') }}</BaseButton>
        <BaseButton variant="ghost" data-testid="delivery-prompt-history" @click="openPromptHistory">{{ t('platformDelivery.promptSources.history') }}</BaseButton>
      </div>
      <BaseAlert v-if="isAdmin && optionsError" variant="warning">
        <p>{{ t('platformDelivery.documentOptionsError') }}</p>
        <BaseButton variant="secondary" size="sm" class="mt-2" @click="loadOptions">{{ t('platformDelivery.retry') }}</BaseButton>
      </BaseAlert>
      <DeliveryDocuments :documents="store.workspace.project?.documents" :can-edit="isAdmin" @attach="openAttach({ level: 'project', node: store.workspace.project })" @download="downloadDocument" @unlink="requestUnlink" />
      <DeliveryNoticeHistory v-if="isAdmin" :project-id="projectId" :workspace-version="store.version" />
      <div v-if="!store.contracts.length" class="rounded-xl bg-surface-raised p-6 text-center">
        <h3 class="text-base font-semibold text-text-default">{{ t('platformDelivery.empty') }}</h3>
        <p class="mt-2 text-sm text-text-muted">{{ t(isAdmin ? 'platformDelivery.emptyAdmin' : 'platformDelivery.emptyClient') }}</p>
      </div>
      <section v-for="contract in store.contracts" :key="contract.id" class="min-w-0 space-y-5 rounded-xl border border-border-default p-4 sm:p-5" :data-testid="`delivery-contract-${contract.id}`">
        <header class="space-y-3">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1"><p class="text-xs text-text-muted">{{ t('platformDelivery.contract') }} · {{ contract.key }}</p><h3 class="break-words text-lg font-semibold text-text-default">{{ contract.title }}</h3></div>
            <BaseBadge :variant="signed(contract) ? 'success' : 'warning'">{{ t(`platformDelivery.status.${contract.signature_status || 'unsigned'}`) }}</BaseBadge>
          </div>
          <p v-if="contract.description" class="whitespace-pre-line break-words text-sm text-text-muted">{{ contract.description }}</p>
          <p v-if="contract.signer_name" class="text-sm text-text-muted">{{ t('platformDelivery.signer') }}: {{ contract.signer_name }}</p>
          <div class="flex flex-wrap gap-2">
            <BaseButton v-if="contract.pdf_url" variant="secondary" size="sm" @click="downloadDocument(contract)">{{ t('platformDelivery.download') }}</BaseButton>
            <template v-if="isAdmin">
              <BaseButton v-if="!signed(contract)" variant="secondary" size="sm" @click="openAuthor({ entity: 'contracts', node: contract })">{{ t('platformDelivery.edit') }}</BaseButton>
              <BaseButton v-if="!signed(contract)" variant="secondary" size="sm" :data-testid="`delivery-signature-contract-${contract.id}`" @click="openSignature({ entity: 'contracts', node: contract }, 'externalSignature')">{{ t('platformDelivery.signature') }}</BaseButton>
              <BaseButton variant="secondary" size="sm" :data-testid="`delivery-add-amendment-${contract.id}`" @click="openAuthor({ entity: 'amendments', initial: { contract_id: contract.id } })">{{ t('platformDelivery.addAmendment') }}</BaseButton>
              <BaseButton variant="secondary" size="sm" @click="openAuthor({ entity: 'scopes', initial: { contract_id: contract.id } })">{{ t('platformDelivery.addScope') }}</BaseButton>
              <BaseButton v-if="!signed(contract)" variant="danger-ghost" size="sm" @click="requestRemove({ entity: 'contracts', node: contract })">{{ t('platformDelivery.remove') }}</BaseButton>
            </template>
            <BaseButton v-else-if="contract.document_uuid && !signed(contract)" size="sm" :data-testid="`delivery-sign-contract-${contract.id}`" @click="openSignature({ entity: 'contracts', node: contract }, 'sign')">{{ t('platformDelivery.sign') }}</BaseButton>
          </div>
        </header>
        <DeliveryDocuments :documents="contract.documents" :can-edit="isAdmin && !signed(contract)" @attach="openAttach({ level: 'contract', node: contract })" @download="downloadDocument" @unlink="requestUnlink" />
        <section v-if="contract.amendments?.length" class="space-y-3">
          <h4 class="text-sm font-semibold text-text-muted">{{ t('platformDelivery.amendments') }}</h4>
          <article v-for="amendment in contract.amendments" :key="amendment.id" class="space-y-3 rounded-xl border border-border-muted bg-surface-raised p-4" :data-testid="`delivery-amendment-${amendment.id}`">
            <div class="flex flex-wrap items-start justify-between gap-2"><h5 class="min-w-0 break-words text-base font-semibold text-text-default">{{ amendment.title }}</h5><BaseBadge :variant="signed(amendment) ? 'success' : 'warning'">{{ t(`platformDelivery.status.${amendment.signature_status || 'unsigned'}`) }}</BaseBadge></div>
            <p v-if="amendment.description" class="whitespace-pre-line break-words text-sm text-text-muted">{{ amendment.description }}</p>
            <div class="flex flex-wrap gap-2">
              <BaseButton v-if="amendment.pdf_url" variant="secondary" size="sm" @click="downloadDocument(amendment)">{{ t('platformDelivery.download') }}</BaseButton>
              <template v-if="isAdmin && !signed(amendment)">
                <BaseButton variant="secondary" size="sm" @click="openAuthor({ entity: 'amendments', node: amendment })">{{ t('platformDelivery.edit') }}</BaseButton>
                <BaseButton variant="secondary" size="sm" @click="openSignature({ entity: 'amendments', node: amendment }, 'externalSignature')">{{ t('platformDelivery.signature') }}</BaseButton>
                <BaseButton variant="danger-ghost" size="sm" @click="requestRemove({ entity: 'amendments', node: amendment })">{{ t('platformDelivery.remove') }}</BaseButton>
              </template>
              <BaseButton v-if="!isAdmin && amendment.document_uuid && !signed(amendment)" size="sm" @click="openSignature({ entity: 'amendments', node: amendment }, 'sign')">{{ t('platformDelivery.sign') }}</BaseButton>
            </div>
            <DeliveryDocuments :documents="amendment.documents" :can-edit="isAdmin && !signed(amendment)" @attach="openAttach({ level: 'amendment', node: amendment })" @download="downloadDocument" @unlink="requestUnlink" />
          </article>
        </section>
        <section v-for="scope in scopesFor(contract.id)" :key="scope.id" class="min-w-0 space-y-5 border-t border-border-muted pt-5" :data-testid="`delivery-scope-${scope.id}`">
          <header class="space-y-3">
            <nav class="flex flex-wrap gap-2 text-xs text-text-muted" :aria-label="t('platformDelivery.scope')"><span>{{ contract.title }}</span><template v-if="scope.amendment_id"><span aria-hidden="true">/</span><span>{{ amendmentTitle(contract, scope) }}</span></template><span aria-hidden="true">/</span><span>{{ scope.title }}</span></nav>
            <div class="flex flex-wrap items-start justify-between gap-2"><div class="min-w-0"><p class="text-xs text-text-muted">{{ t('platformDelivery.scope') }} · {{ scope.key }}</p><h3 class="break-words text-lg font-semibold text-text-default">{{ scope.title }}</h3></div><BaseBadge :variant="scope.is_current ? 'primary' : 'neutral'">{{ t(scope.is_current ? 'platformDelivery.currentScope' : 'platformDelivery.previousScope') }}</BaseBadge></div>
            <p v-if="scope.description" class="whitespace-pre-line break-words text-sm text-text-muted">{{ scope.description }}</p>
            <div v-if="isAdmin" class="flex flex-wrap gap-2">
              <BaseButton variant="secondary" size="sm" @click="openAuthor({ entity: 'scopes', node: scope })">{{ t('platformDelivery.edit') }}</BaseButton>
              <BaseButton variant="secondary" size="sm" :data-testid="`delivery-add-phase-${scope.id}`" @click="openAuthor({ entity: 'phases', initial: { scope_id: scope.id } })">{{ t('platformDelivery.addPhase') }}</BaseButton>
              <BaseButton variant="danger-ghost" size="sm" @click="requestRemove({ entity: 'scopes', node: scope })">{{ t('platformDelivery.remove') }}</BaseButton>
            </div>
          </header>
          <DeliveryDocuments :documents="scope.documents" :can-edit="isAdmin" @attach="openAttach({ level: 'scope', node: scope })" @download="downloadDocument" @unlink="requestUnlink" />
          <p v-if="!scope.phases.length" class="text-sm text-text-muted">{{ t('platformDelivery.emptyScope') }}</p>
          <section v-for="phase in scope.phases" :key="phase.id" class="min-w-0 space-y-4 rounded-xl border border-border-muted p-3 sm:p-4" :data-testid="`delivery-phase-${phase.id}`">
            <header class="space-y-3">
              <nav class="flex flex-wrap gap-2 text-xs text-text-muted" :aria-label="t('platformDelivery.phase')"><span>{{ scope.title }}</span><span aria-hidden="true">/</span><span>{{ phase.title }}</span></nav>
              <div class="flex flex-wrap items-start justify-between gap-2"><div class="min-w-0"><p class="text-xs text-text-muted">{{ t('platformDelivery.phase') }} · {{ phase.key }}</p><h4 class="break-words text-lg font-semibold text-text-default">{{ phase.title }}</h4></div><BaseBadge :variant="statusTone(phase.status)">{{ t(`platformDelivery.status.${phase.status || 'pending'}`) }}</BaseBadge></div>
              <p v-if="phase.description" class="whitespace-pre-line break-words text-sm text-text-muted">{{ phase.description }}</p>
              <p v-if="phase.commercial_phase_id" class="text-xs text-text-muted">{{ t('platformDelivery.commercialPhase') }}: {{ commercialPhases.find((item) => item.id === phase.commercial_phase_id)?.proposal?.title || phase.commercial_phase_id }}. {{ t('platformDelivery.commercialHint') }}</p>
              <div v-if="isAdmin && phase.status !== 'approved'" class="flex flex-wrap gap-2">
                <BaseButton variant="secondary" size="sm" @click="openAuthor({ entity: 'phases', node: { ...phase, scope_id: scope.id } })">{{ t('platformDelivery.edit') }}</BaseButton>
                <BaseButton variant="secondary" size="sm" :data-testid="`delivery-add-stage-${phase.id}`" @click="openAuthor({ entity: 'stages', initial: { phase_id: phase.id } })">{{ t('platformDelivery.addStage') }}</BaseButton>
                <BaseButton variant="danger-ghost" size="sm" @click="requestRemove({ entity: 'phases', node: phase })">{{ t('platformDelivery.remove') }}</BaseButton>
              </div>
            </header>
            <DeliveryDocuments :documents="phase.documents" :can-edit="isAdmin && phase.status !== 'approved'" @attach="openAttach({ level: 'phase', node: phase })" @download="downloadDocument" @unlink="requestUnlink" />
            <p v-if="!phase.stages.length" class="text-sm text-text-muted">{{ t('platformDelivery.emptyPhase') }}</p>
            <DeliveryStage v-for="stage in phase.stages" :key="stage.id" :stage="stage" :project-id="projectId" :is-admin="!!isAdmin" :busy="store.isUpdating" @author="openAuthor" @remove="requestRemove" @publish="requestPublish" @review="openReview($event)" @historical="openReview($event, true)" @report="openReport" @prepare-reply="openReplyPrompt" @prompt-context="openPromptContext" @attach="openAttach" @download="downloadDocument" @unlink="requestUnlink" @copy="copyStage" />
          </section>
        </section>
      </section>
    </template>

    <BaseModal :model-value="!!dialog" :kind="dialog === 'confirm' ? 'confirm' : ['review', 'historical', 'author', 'import', 'guidesPrompt', 'replyPrompt', 'promptContext', 'promptHistory'].includes(dialog) ? 'form-wide' : 'form'" :close-on-backdrop="!store.isUpdating" :close-on-esc="!store.isUpdating" @update:model-value="!$event && close()">
      <div class="space-y-5 p-4 sm:p-6">
        <template v-if="dialog === 'confirm'">
          <h2 class="text-lg font-semibold text-text-default">{{ t(confirm.kind === 'publish' ? 'platformDelivery.publishTitle' : 'platformDelivery.confirmRemove', { title: confirm.node.title }) }}</h2>
          <p class="text-sm text-text-muted">{{ t(confirm.kind === 'publish' ? 'platformDelivery.publishHint' : 'platformDelivery.removeHint') }}</p>
          <BaseAlert v-if="confirm.kind === 'publish'" variant="info">{{ t('platformDelivery.publishBlocked') }}</BaseAlert>
          <BaseAlert v-if="formError" variant="danger" role="alert">{{ formError }}</BaseAlert>
          <BaseModalActions><BaseButton variant="ghost" @click="close">{{ t('platformDelivery.cancel') }}</BaseButton><BaseButton :variant="confirm.kind === 'publish' ? 'primary' : 'danger'" :loading="store.isUpdating" data-testid="delivery-confirm-action" @click="confirmAction">{{ t(confirm.kind === 'publish' ? 'platformDelivery.publish' : 'platformDelivery.remove') }}</BaseButton></BaseModalActions>
        </template>
        <template v-else>
          <h2 class="text-lg font-semibold text-text-default">{{ modalTitle }}</h2>
          <DeliveryPromptWorkbench v-if="dialog === 'guidesPrompt' || dialog === 'replyPrompt'" :key="dialog + '-' + (selected?.id || 'initial')" :mode="dialog === 'replyPrompt' ? 'reply' : 'guides'" :stage="selected" @cancel="close" @imported="finishPromptImport" @reply="useReplyDraft" />
          <section v-else-if="dialog === 'promptContext'" class="space-y-4">
            <p v-if="loadingPromptContext" class="text-sm text-text-muted" role="status">{{ t('platformDelivery.loading') }}</p>
            <BaseAlert v-if="formError" variant="danger" role="alert">{{ formError }}</BaseAlert>
            <DeliveryPromptSources v-if="retainedPromptContext" :context="retainedPromptContext" @download="downloadPromptSource" />
            <BaseModalActions><BaseButton variant="ghost" @click="close">{{ t('platformDelivery.close') }}</BaseButton></BaseModalActions>
          </section>
          <section v-else-if="dialog === 'promptHistory'" class="space-y-4" data-testid="delivery-prompt-history-list">
            <p v-if="loadingPromptHistory" class="text-sm text-text-muted" role="status">{{ t('platformDelivery.loading') }}</p>
            <BaseAlert v-if="formError" variant="danger" role="alert">{{ formError }}</BaseAlert>
            <p v-if="!loadingPromptHistory && !formError && !promptContexts.length" class="text-sm text-text-muted">{{ t('platformDelivery.promptSources.noHistory') }}</p>
            <p v-if="promptContexts.length" class="text-sm text-text-muted">{{ t('platformDelivery.promptSources.historyHint') }}</p>
            <article v-for="item in promptContexts" :key="item.id" class="min-w-0 space-y-2 rounded-xl border border-border-default p-4" :data-testid="`delivery-prompt-history-${item.id}`">
              <h3 class="break-words text-sm font-semibold text-text-default">{{ store.contracts.find((contract) => contract.id === item.contract_id)?.title || t('platformDelivery.contract') }}</h3>
              <p class="break-words text-sm text-text-muted">{{ t(item.mode === 'guides' ? 'platformDelivery.promptAuthoring.createGuides' : 'platformDelivery.promptAuthoring.prepareReply') }} · {{ item.created_at }}</p>
              <p class="break-all text-xs text-text-muted">{{ item.id }}</p>
              <BaseBadge :variant="item.complete ? 'success' : 'warning'">{{ t(item.complete ? 'platformDelivery.promptSources.status.included' : 'platformDelivery.promptSources.status.partial') }}</BaseBadge>
              <div><BaseButton variant="secondary" size="sm" @click="openPromptContext(item.id)">{{ t('platformDelivery.promptSources.openSources') }}</BaseButton></div>
            </article>
            <BaseModalActions><BaseButton variant="ghost" @click="close">{{ t('platformDelivery.close') }}</BaseButton></BaseModalActions>
          </section>
          <DeliveryAuthoringForm v-else-if="dialog === 'author'" :key="`${author.entity}-${author.node?.id || 'new'}`" :entity="author.entity" :initial="author.node || author.initial || {}" :contracts="store.contracts" :documents="store.documentOptions" :proposal-documents="store.proposalDocumentOptions" :commercial-phases="commercialPhases" :loading="store.isUpdating" :error="formError" @submit="saveAuthor" @cancel="close" />
          <DeliveryReviewForm v-else-if="dialog === 'review' || dialog === 'historical'" :key="`${dialog}-${selected.id}`" :stage="selected" :draft="reviewDraft" :historical="dialog === 'historical'" :documents="chosenDocuments" :evidence-messages="store.evidenceMessages" :loading="store.isUpdating" :error="formError" @draft="reviewDraft = $event" @submit="submitReview" @cancel="close" />
          <template v-else>
            <BaseAlert v-if="formError" variant="danger" role="alert">{{ formError }}</BaseAlert>
            <form v-if="dialog === 'report'" class="space-y-5" @submit.prevent="sendReport">
              <p class="text-sm text-text-muted">{{ t('platformDelivery.reportHint') }}</p>
              <BaseFormField :label="t('platformDelivery.message')" for="delivery-report-message" required><BaseTextarea id="delivery-report-message" v-model="reportMessage" :rows="5" data-testid="delivery-report-message" /></BaseFormField>
              <fieldset class="space-y-2"><legend class="mb-2 text-sm font-medium text-text-default">{{ t('platformDelivery.relatedRequirements') }}</legend><BaseCheckbox v-for="requirement in selected.requirements" :key="requirement.id" v-model="reportRequirementIds" :value="requirement.id" class="flex">{{ requirement.title }}</BaseCheckbox></fieldset>
              <DeliveryDocumentPicker v-model="reportDocumentIds" :documents="chosenDocuments" />
              <template v-if="reportPromptProof">
                <BaseAlert variant="info">{{ t('platformDelivery.promptAuthoring.manualReply') }}</BaseAlert>
                <BaseCheckbox v-model="reportHumanReviewed" data-testid="delivery-reply-human-reviewed">{{ t('platformDelivery.promptAuthoring.humanReviewed') }}</BaseCheckbox>
              </template>
              <BaseCheckbox v-if="isAdmin" v-model="reportInternal">{{ t('platformDelivery.internalMessage') }}</BaseCheckbox>
              <BaseModalActions><BaseButton variant="ghost" @click="close">{{ t('platformDelivery.cancel') }}</BaseButton><BaseButton type="submit" :loading="store.isUpdating" data-testid="delivery-report-submit">{{ t('platformDelivery.send') }}</BaseButton></BaseModalActions>
            </form>
            <form v-else-if="dialog === 'attach'" class="space-y-5" @submit.prevent="attachDocument">
              <p class="text-sm text-text-muted">{{ t('platformDelivery.documentHint') }}</p>
              <BaseFormField :label="t('platformDelivery.selectDocument')" for="delivery-attach-document" required><BaseSelect id="delivery-attach-document" v-model="documentId" :options="documentOptions" :placeholder="t('platformDelivery.select')" /></BaseFormField>
              <BaseModalActions><BaseButton variant="ghost" @click="close">{{ t('platformDelivery.cancel') }}</BaseButton><BaseButton type="submit" :loading="store.isUpdating" data-testid="delivery-document-attach-submit">{{ t('platformDelivery.attach') }}</BaseButton></BaseModalActions>
            </form>
            <section v-else-if="dialog === 'import'" class="space-y-5">
              <p class="text-sm text-text-muted">{{ t('platformDelivery.importHint') }}</p>
              <BaseAlert variant="info">{{ t('platformDelivery.manualJsonProvenance') }}</BaseAlert>
              <BaseFormField :label="t('platformDelivery.json')" for="delivery-import-json"><BaseTextarea id="delivery-import-json" v-model="importJson" :rows="12" class="font-mono" data-testid="delivery-import-json" /></BaseFormField>
              <BaseAlert v-if="preview?.valid && previewedJson === importJson" variant="success">{{ t('platformDelivery.previewReady') }}</BaseAlert>
              <section v-if="preview" class="space-y-2"><h3 class="text-sm font-medium text-text-default">{{ t('platformDelivery.previewSummary') }}</h3><pre class="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-surface-raised p-4 text-xs text-text-default">{{ previewSummary }}</pre></section>
              <BaseModalActions><BaseButton variant="ghost" @click="close">{{ t('platformDelivery.cancel') }}</BaseButton><BaseButton variant="secondary" :loading="store.isUpdating" data-testid="delivery-import-preview" @click="previewImport">{{ t('platformDelivery.preview') }}</BaseButton><BaseButton :loading="store.isUpdating" :disabled="!preview?.valid || previewedJson !== importJson" :disabled-reason="t('platformDelivery.previewChanged')" data-testid="delivery-import-apply" @click="applyImport">{{ t('platformDelivery.apply') }}</BaseButton></BaseModalActions>
            </section>
            <form v-else-if="dialog === 'externalSignature'" class="space-y-5" @submit.prevent="recordSignature">
              <p class="text-sm text-text-muted">{{ t('platformDelivery.signatureHint') }}</p>
              <BaseFormField :label="t('platformDelivery.signedFile')" :error="signatureErrors.file" for="delivery-signature-file" required><input id="delivery-signature-file" type="file" accept="application/pdf,.pdf" class="block w-full min-w-0 text-sm text-text-default" data-testid="delivery-signature-file" @change="signature.file = $event.target.files?.[0] || null" /></BaseFormField>
              <BaseFormRow :cols="2"><BaseFormField :label="t('platformDelivery.signer')" :error="signatureErrors.signer_name" for="delivery-signature-name" required><BaseInput id="delivery-signature-name" v-model="signature.signer_name" /></BaseFormField><BaseFormField :label="t('platformDelivery.signedAt')" :error="signatureErrors.signed_at" for="delivery-signature-date" required><BaseInput id="delivery-signature-date" v-model="signature.signed_at" type="datetime-local" /></BaseFormField></BaseFormRow>
              <BaseFormField :label="t('platformDelivery.attestation')" :error="signatureErrors.attestation" for="delivery-signature-attestation" required><BaseTextarea id="delivery-signature-attestation" v-model="signature.attestation" :rows="4" /></BaseFormField>
              <BaseModalActions><BaseButton variant="ghost" @click="close">{{ t('platformDelivery.cancel') }}</BaseButton><BaseButton type="submit" :loading="store.isUpdating" data-testid="delivery-signature-submit">{{ t('platformDelivery.signature') }}</BaseButton></BaseModalActions>
            </form>
            <form v-else-if="dialog === 'sign'" class="space-y-5" @submit.prevent="signPortal">
              <p class="text-sm text-text-muted">{{ t('platformDelivery.signHint') }}</p>
              <BaseButton v-if="selected.node.pdf_url" variant="secondary" @click="downloadDocument(selected.node)">{{ t('platformDelivery.download') }}</BaseButton>
              <BaseFormField :label="t('platformDelivery.signer')" for="delivery-portal-signer" required><BaseInput id="delivery-portal-signer" v-model="signature.signer_name" /></BaseFormField>
              <BaseCheckbox v-model="signature.accept">{{ t('platformDelivery.acceptTerms') }}</BaseCheckbox>
              <p class="text-sm text-text-muted">{{ t('platformDelivery.verifyEmail') }} <NuxtLink :to="localePath('/platform/documents')" class="text-text-brand underline">{{ t('platformDelivery.myDocuments') }}</NuxtLink></p>
              <BaseModalActions><BaseButton variant="ghost" @click="close">{{ t('platformDelivery.cancel') }}</BaseButton><BaseButton type="submit" :loading="documentsStore.isSigning" data-testid="delivery-portal-sign-submit">{{ t('platformDelivery.signSubmit') }}</BaseButton></BaseModalActions>
            </form>
          </template>
        </template>
      </div>
    </BaseModal>
  </div>
</template>
