<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { usePlatformDeliveryStore } from '~/stores/platform-delivery'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseCheckbox from '~/components/base/BaseCheckbox.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseModalActions from '~/components/base/BaseModalActions.vue'
import BaseTextarea from '~/components/base/BaseTextarea.vue'

const props = defineProps({ stage: { type: Object, required: true }, isAdmin: { type: Boolean, default: false } })
const emit = defineEmits(['cancel'])
const { t, locale } = useI18n()
const store = usePlatformDeliveryStore()
const history = ref(null)
const action = ref('')
const error = ref('')
const historyError = ref('')
const message = ref('')
const includeRecordPdf = ref(false)
const documentSnapshotIds = ref([])
const preview = ref(null)
const savedPreview = ref(false)
const previewStale = ref(false)
const humanReviewed = ref(false)
const outcomeUnknown = ref(false)
const available = computed(() => props.isAdmin && props.stage.status === 'approved' && !!props.stage.publication_id && props.stage.requirements?.length > 0 && props.stage.requirements.every((item) => item.review_status === 'approved'))
const busy = computed(() => !!action.value || store.isUpdating)
const canPrepare = computed(() => available.value && !!history.value && !busy.value)
const canSend = computed(() => available.value && preview.value?.status === 'prepared' && !!preview.value.manifest_sha256 && !previewStale.value && humanReviewed.value && !busy.value && !outcomeUnknown.value)
const selectionKey = computed(() => JSON.stringify({ message: message.value, include_record_pdf: includeRecordPdf.value, document_snapshot_ids: [...documentSnapshotIds.value].sort() }))
const emailStatus = (email) => ['prepared', 'sending', 'sent', 'failed', 'unknown'].includes(email?.status) ? email.status : 'unknown'
const statusVariant = (email) => ({ prepared: 'info', sending: 'warning', sent: 'success', failed: 'danger', unknown: 'warning' }[emailStatus(email)])
const resendAvailable = (email) => ['sent', 'failed', 'unknown'].includes(email.status)
const formattedDate = (value) => value ? new Intl.DateTimeFormat(locale?.value || 'es', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : ''
const failureMessage = (result) => result.status === 409 ? t('platformDelivery.conflict') : result.message || t('platformDelivery.closureEmail.actionError')
function remember(email) {
  if (!history.value) return
  const emails = history.value.emails || []
  const index = emails.findIndex((item) => item.id === email.id)
  if (index < 0) history.value.emails = [email, ...emails]
  else emails.splice(index, 1, email)
}
function showPreview(email, { saved = false, stale = false } = {}) {
  preview.value = email
  savedPreview.value = saved
  previewStale.value = stale
  humanReviewed.value = false
  outcomeUnknown.value = false
  remember(email)
}
async function loadHistory() {
  if (!available.value || busy.value) return
  action.value = 'history'
  historyError.value = ''
  try {
    const result = await store.fetchClosureEmailHistory(props.stage.id)
    if (!result.success) { historyError.value = failureMessage(result); return }
    history.value = result.data
    const current = result.data.emails?.find((email) => email.id === preview.value?.id)
    if (current) {
      preview.value = current
      outcomeUnknown.value = false
    }
  } finally { action.value = '' }
}
async function preparePreview() {
  if (!canPrepare.value) return
  action.value = 'prepare'
  error.value = ''
  humanReviewed.value = false
  const preparedSelection = selectionKey.value
  try {
    const result = await store.prepareClosureEmail(props.stage.id, {
      message: message.value, include_record_pdf: includeRecordPdf.value,
      document_snapshot_ids: [...documentSnapshotIds.value],
    })
    if (!result.success) { error.value = failureMessage(result); return }
    showPreview(result.data, { stale: preparedSelection !== selectionKey.value })
  } finally { action.value = '' }
}
async function inspectEmail(email) {
  if (!available.value || busy.value) return
  action.value = 'detail'
  error.value = ''
  humanReviewed.value = false
  try {
    const result = await store.fetchClosureEmail(email.id)
    if (!result.success) { error.value = failureMessage(result); return }
    showPreview(result.data, { saved: true })
  } finally { action.value = '' }
}
async function sendPreview() {
  if (!canSend.value) return
  action.value = 'send'
  error.value = ''
  try {
    const result = await store.sendClosureEmail(preview.value.id, { preview_sha256: preview.value.manifest_sha256, human_reviewed: true })
    humanReviewed.value = false
    if (result.success) { showPreview(result.data, { saved: savedPreview.value }); return }
    error.value = failureMessage(result)
    const recovered = await store.fetchClosureEmail(preview.value.id)
    if (recovered.success) showPreview(recovered.data, { saved: savedPreview.value })
    else outcomeUnknown.value = true
  } finally { action.value = '' }
}
async function prepareResend(email) {
  if (!available.value || busy.value || !resendAvailable(email)) return
  action.value = 'resend'
  error.value = ''
  humanReviewed.value = false
  try {
    const result = await store.prepareClosureEmailResend(email.id)
    if (!result.success) { error.value = failureMessage(result); return }
    showPreview(result.data, { saved: true })
  } finally { action.value = '' }
}
async function downloadAttachment(attachment) {
  if (busy.value) return
  action.value = 'download'
  error.value = ''
  try {
    const result = await store.downloadClosureEmailAttachment(attachment)
    if (!result.success) error.value = result.message || t('platformDelivery.downloadError')
  } finally { action.value = '' }
}
function startNew() {
  if (busy.value) return
  preview.value = null
  savedPreview.value = false
  previewStale.value = false
  humanReviewed.value = false
  outcomeUnknown.value = false
  error.value = ''
  message.value = ''
  includeRecordPdf.value = false
  documentSnapshotIds.value = []
}
watch(selectionKey, () => {
  humanReviewed.value = false
  if (preview.value) previewStale.value = true
}, { flush: 'sync' })
watch(() => [preview.value?.id, preview.value?.manifest_sha256], () => { humanReviewed.value = false }, { flush: 'sync' })
watch(available, (allowed) => { if (!allowed) humanReviewed.value = false })
onMounted(loadHistory)
</script>

<template>
  <section class="min-w-0 space-y-5" data-testid="delivery-closure-email">
    <BaseAlert v-if="!available" variant="warning" data-testid="delivery-closure-unavailable">{{ t('platformDelivery.closureEmail.unavailable') }}</BaseAlert>
    <template v-else>
      <p class="text-sm text-text-muted">{{ t('platformDelivery.closureEmail.hint') }}</p>
      <BaseAlert v-if="error" variant="danger" role="alert" data-testid="delivery-closure-error">{{ error }}</BaseAlert>
      <BaseAlert v-if="historyError" variant="danger" role="alert" data-testid="delivery-closure-history-error">{{ historyError }}</BaseAlert>
      <p v-if="action === 'history'" class="text-sm text-text-muted" role="status">{{ t('platformDelivery.loading') }}</p>
      <BaseButton v-if="historyError" variant="secondary" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" data-testid="delivery-closure-history-retry" @click="loadHistory">{{ t('platformDelivery.retry') }}</BaseButton>
      <template v-if="history">
        <template v-if="!savedPreview">
          <BaseFormField :label="t('platformDelivery.closureEmail.message')" :hint="t('platformDelivery.closureEmail.messageHint')" for="delivery-closure-message" label-policy="wrap">
            <BaseTextarea id="delivery-closure-message" v-model="message" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" :rows="4" maxlength="20000" data-testid="delivery-closure-message" />
          </BaseFormField>
          <BaseCheckbox v-model="includeRecordPdf" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" data-testid="delivery-closure-include-record">{{ t('platformDelivery.closureEmail.includeRecord') }}</BaseCheckbox>
          <fieldset class="space-y-3">
            <legend class="mb-2 text-sm font-semibold text-text-default">{{ t('platformDelivery.closureEmail.documents') }}</legend>
            <p class="text-sm text-text-muted">{{ t('platformDelivery.closureEmail.documentsHint') }}</p>
            <p v-if="!history.available_documents?.length" class="text-sm text-text-muted">{{ t('platformDelivery.closureEmail.noDocuments') }}</p>
            <div v-for="document in history.available_documents" :key="document.id" class="min-w-0 space-y-1">
              <BaseCheckbox v-model="documentSnapshotIds" :value="document.id" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" :data-testid="`delivery-closure-document-${document.id}`">{{ document.title }}</BaseCheckbox>
              <p class="break-words text-xs text-text-muted">{{ document.filename }} · {{ t('platformDelivery.closureEmail.documentVersion', { version: document.version, round: document.round }) }}</p>
            </div>
          </fieldset>
          <BaseButton :disabled="!canPrepare" :disabled-reason="t('platformDelivery.closureEmail.busy')" :loading="action === 'prepare'" data-testid="delivery-closure-prepare" @click="preparePreview">{{ t('platformDelivery.closureEmail.prepare') }}</BaseButton>
        </template>
        <template v-if="preview">
          <BaseAlert v-if="previewStale" variant="warning" data-testid="delivery-closure-stale">{{ t('platformDelivery.closureEmail.previewChanged') }}</BaseAlert>
          <BaseAlert v-if="outcomeUnknown" variant="warning" data-testid="delivery-closure-unknown">{{ t('platformDelivery.closureEmail.unknownResult') }}</BaseAlert>
          <article class="min-w-0 space-y-4 rounded-xl border border-border-default bg-surface-raised p-4" data-testid="delivery-closure-preview">
            <header class="flex flex-wrap items-center justify-between gap-2">
              <h3 class="text-sm font-semibold text-text-default">{{ t('platformDelivery.closureEmail.preview') }}</h3>
              <BaseBadge :variant="action === 'send' || outcomeUnknown ? 'warning' : statusVariant(preview)" role="status" data-testid="delivery-closure-status">{{ t(`platformDelivery.closureEmail.status.${action === 'send' ? 'sending' : outcomeUnknown ? 'unknown' : emailStatus(preview)}`) }}</BaseBadge>
            </header>
            <dl class="space-y-3">
              <div><dt class="text-xs font-semibold text-text-muted">{{ t('platformDelivery.closureEmail.to') }}</dt><dd class="break-words text-sm text-text-default" data-testid="delivery-closure-to">{{ preview.to?.join(', ') }}</dd></div>
              <div><dt class="text-xs font-semibold text-text-muted">{{ t('platformDelivery.closureEmail.subject') }}</dt><dd class="whitespace-pre-line break-words text-sm text-text-default" data-testid="delivery-closure-subject">{{ preview.subject }}</dd></div>
            </dl>
            <pre class="whitespace-pre-wrap break-words text-sm text-text-default" data-testid="delivery-closure-body">{{ preview.text_body }}</pre>
            <p v-if="preview.status === 'prepared' && !outcomeUnknown" class="text-sm text-text-muted" data-testid="delivery-closure-not-sent">{{ t('platformDelivery.closureEmail.notSent') }}</p>
            <p v-if="preview.error_message" class="whitespace-pre-line break-words text-sm text-danger-strong" role="alert">{{ preview.error_message }}</p>
            <ol v-if="preview.attempts?.length" class="space-y-2" data-testid="delivery-closure-attempts">
              <li v-for="attempt in preview.attempts" :key="attempt.id" class="space-y-1 text-xs text-text-muted">
                <span>{{ t(`platformDelivery.closureEmail.status.${emailStatus(attempt)}`) }}</span>
                <time v-if="attempt.finished_at || attempt.claimed_at || attempt.created_at" :datetime="attempt.finished_at || attempt.claimed_at || attempt.created_at"> · {{ formattedDate(attempt.finished_at || attempt.claimed_at || attempt.created_at) }}</time>
              </li>
            </ol>
            <section class="space-y-2">
              <h4 class="text-sm font-semibold text-text-default">{{ t('platformDelivery.closureEmail.attachments') }}</h4>
              <p v-if="!preview.attachments?.length" class="text-sm text-text-muted" data-testid="delivery-closure-no-attachments">{{ t('platformDelivery.closureEmail.noAttachments') }}</p>
              <article v-for="attachment in preview.attachments" :key="attachment.id" class="min-w-0 space-y-1 rounded-lg border border-border-default p-3">
                <p class="break-words text-sm font-medium text-text-default">{{ attachment.title }}</p>
                <p class="break-words text-xs text-text-muted">{{ attachment.filename }}<span v-if="attachment.version != null"> · {{ t('platformDelivery.version', { version: attachment.version }) }}</span></p>
                <BaseButton variant="secondary" size="sm" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" :data-testid="`delivery-closure-download-${attachment.id}`" @click="downloadAttachment(attachment)">{{ t('platformDelivery.download') }}</BaseButton>
              </article>
            </section>
          </article>
          <p v-if="savedPreview" class="text-sm text-text-muted">{{ t('platformDelivery.closureEmail.retainedPreview') }}</p>
          <BaseCheckbox v-if="preview.status === 'prepared'" v-model="humanReviewed" :disabled="busy || previewStale || outcomeUnknown" :disabled-reason="t(busy ? 'platformDelivery.closureEmail.busy' : outcomeUnknown ? 'platformDelivery.closureEmail.unknownResult' : 'platformDelivery.closureEmail.previewChanged')" data-testid="delivery-closure-reviewed">{{ t('platformDelivery.closureEmail.humanReviewed') }}</BaseCheckbox>
          <div class="flex flex-wrap gap-2">
            <BaseButton v-if="preview.status === 'prepared'" :disabled="!canSend" :disabled-reason="t(busy ? 'platformDelivery.closureEmail.busy' : outcomeUnknown ? 'platformDelivery.closureEmail.unknownResult' : previewStale ? 'platformDelivery.closureEmail.previewChanged' : 'platformDelivery.closureEmail.reviewRequired')" :loading="action === 'send'" data-testid="delivery-closure-send" @click="sendPreview">{{ t('platformDelivery.closureEmail.send') }}</BaseButton>
            <BaseButton v-if="resendAvailable(preview)" variant="secondary" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" data-testid="delivery-closure-resend-current" @click="prepareResend(preview)">{{ t('platformDelivery.closureEmail.prepareResend') }}</BaseButton>
            <BaseButton v-if="outcomeUnknown" variant="secondary" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" data-testid="delivery-closure-check-result" @click="inspectEmail(preview)">{{ t('platformDelivery.closureEmail.checkResult') }}</BaseButton>
            <BaseButton v-if="savedPreview" variant="ghost" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" data-testid="delivery-closure-new" @click="startNew">{{ t('platformDelivery.closureEmail.newEmail') }}</BaseButton>
          </div>
        </template>
        <section class="space-y-3 border-t border-border-muted pt-4" data-testid="delivery-closure-history">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h3 class="text-sm font-semibold text-text-default">{{ t('platformDelivery.closureEmail.history') }}</h3>
            <BaseButton variant="ghost" size="sm" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" data-testid="delivery-closure-history-refresh" @click="loadHistory">{{ t('platformDelivery.refresh') }}</BaseButton>
          </div>
          <p v-if="!history.emails?.length" class="text-sm text-text-muted">{{ t('platformDelivery.closureEmail.emptyHistory') }}</p>
          <article v-for="email in history.emails" :key="email.id" class="min-w-0 space-y-2 rounded-xl border border-border-default p-3" :data-testid="`delivery-closure-history-${email.id}`">
            <div class="flex flex-wrap items-start justify-between gap-2"><p class="min-w-0 break-words text-sm font-medium text-text-default">{{ email.subject }}</p><BaseBadge :variant="statusVariant(email)">{{ t(`platformDelivery.closureEmail.status.${emailStatus(email)}`) }}</BaseBadge></div>
            <p class="break-words text-xs text-text-muted">{{ email.to?.join(', ') }}</p>
            <time v-if="email.created_at" :datetime="email.created_at" class="text-xs text-text-muted">{{ formattedDate(email.created_at) }}</time>
            <p v-if="email.error_message" class="whitespace-pre-line break-words text-sm text-danger-strong">{{ email.error_message }}</p>
            <div class="flex flex-wrap gap-2">
              <BaseButton variant="secondary" size="sm" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" :data-testid="`delivery-closure-inspect-${email.id}`" @click="inspectEmail(email)">{{ t('platformDelivery.closureEmail.view') }}</BaseButton>
              <BaseButton v-if="resendAvailable(email)" variant="secondary" size="sm" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" :data-testid="`delivery-closure-resend-${email.id}`" @click="prepareResend(email)">{{ t('platformDelivery.closureEmail.prepareResend') }}</BaseButton>
            </div>
          </article>
        </section>
      </template>
    </template>
    <BaseModalActions><BaseButton variant="ghost" :disabled="busy" :disabled-reason="t('platformDelivery.closureEmail.busy')" @click="emit('cancel')">{{ t('platformDelivery.close') }}</BaseButton></BaseModalActions>
  </section>
</template>
