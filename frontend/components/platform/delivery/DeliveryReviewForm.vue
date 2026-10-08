<script setup>
import { computed, reactive, ref, toRef } from 'vue'
import BaseAlert from '~/components/base/BaseAlert.vue'
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseFormField from '~/components/base/BaseFormField.vue'
import BaseInput from '~/components/base/BaseInput.vue'
import BaseSelect from '~/components/base/BaseSelect.vue'
import BaseTextarea from '~/components/base/BaseTextarea.vue'
import BaseCheckbox from '~/components/base/BaseCheckbox.vue'
import DeliveryDocumentPicker from './DeliveryDocumentPicker.vue'

const props = defineProps({
  stage: { type: Object, required: true }, documents: { type: Array, default: () => [] },
  historical: { type: Boolean, default: false }, loading: { type: Boolean, default: false }, error: { type: String, default: '' },
  evidenceMessages: { type: Array, default: () => [] },
  draft: { type: Object, default: null },
})
const emit = defineEmits(['submit', 'cancel', 'draft'])
const { t } = useI18n()
const draftState = reactive(props.draft || {
  decisions: Object.fromEntries(props.stage.requirements.map((requirement) => [requirement.id, { decision: '', message: '', environment: requirement.guide?.environment || '' }])),
  message: '', documentIds: [],
  evidence: { source_message_id: '', client_statement: false, original_reviewer: '', occurred_at: '', evidence_channel: 'email', external_reference: '' },
})
emit('draft', draftState)
const decisions = draftState.decisions
const message = toRef(draftState, 'message')
const documentIds = toRef(draftState, 'documentIds')
const validationError = ref('')
const fieldErrors = reactive({})
const evidence = draftState.evidence
const selectedEvidence = computed(() => props.evidenceMessages.find((item) => String(item.id) === String(evidence.source_message_id)))
const evidenceOptions = computed(() => [{ value: '', label: t('platformDelivery.otherEvidence') }, ...props.evidenceMessages.map((item) => ({ value: item.id, label: `${item.original_reviewer} · ${item.subject}` }))])
const decisionOptions = () => [
  { value: '', label: t('platformDelivery.undecided') },
  { value: 'approved', label: t('platformDelivery.approve') },
  ...(!props.historical ? [
    { value: 'objected', label: t('platformDelivery.object') },
    { value: 'rejected', label: t('platformDelivery.reject') },
  ] : []),
]
function submit() {
  validationError.value = ''
  Object.keys(fieldErrors).forEach((key) => delete fieldErrors[key])
  const selected = props.stage.requirements.filter((requirement) => requirement.review_status === 'in_review' && decisions[requirement.id].decision)
  if (!selected.length) { validationError.value = t('platformDelivery.chooseDecision'); return }
  selected.forEach((requirement) => {
    const result = decisions[requirement.id]
    if (result.decision !== 'approved' && !result.message.trim()) fieldErrors[requirement.id] = t('platformDelivery.reasonRequired')
  })
  if (Object.keys(fieldErrors).length) return
  if (props.historical) {
    if (!evidence.client_statement || !message.value.trim()) {
      validationError.value = t('platformDelivery.evidenceRequired'); return
    }
    if (!evidence.source_message_id && (!evidence.original_reviewer.trim() || !evidence.occurred_at || !evidence.external_reference.trim() || !documentIds.value.length)) {
      validationError.value = t('platformDelivery.externalEvidenceRequired'); return
    }
  }
  const payload = { decisions: selected.map((requirement) => ({ requirement_id: requirement.id, version: requirement.version, ...decisions[requirement.id] })) }
  if (props.historical) {
    payload.evidence_message = message.value.trim()
    payload.evidence_document_ids = documentIds.value
    payload.client_statement = true
    if (evidence.source_message_id) payload.source_message_id = Number(evidence.source_message_id)
    else Object.assign(payload, {
      original_reviewer: evidence.original_reviewer.trim(), occurred_at: new Date(evidence.occurred_at).toISOString(),
      evidence_channel: evidence.evidence_channel, external_reference: evidence.external_reference.trim(),
    })
  } else {
    payload.message = message.value.trim()
    payload.document_ids = documentIds.value
  }
  emit('submit', payload)
}
</script>

<template>
  <form class="space-y-5" @submit.prevent="submit" data-testid="delivery-review-form">
    <p class="text-sm text-text-muted">{{ t(historical ? 'platformDelivery.historicalHint' : 'platformDelivery.reviewHint') }}</p>
    <BaseAlert v-if="error || validationError" variant="danger" role="alert">{{ error || validationError }}</BaseAlert>
    <section v-for="requirement in stage.requirements" :key="requirement.id" class="space-y-3 rounded-xl border border-border-default p-4" :data-testid="`delivery-review-requirement-${requirement.id}`">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <h3 class="min-w-0 break-words text-sm font-semibold text-text-default">{{ requirement.title }}</h3>
        <BaseBadge v-if="requirement.review_status === 'approved'" variant="success">{{ t('platformDelivery.frozen') }}</BaseBadge>
      </div>
      <p v-if="['objected', 'rejected'].includes(requirement.review_status)" class="text-sm text-text-muted">{{ t('platformDelivery.awaitingRound') }}</p>
      <template v-if="requirement.review_status === 'in_review'">
        <BaseFormField :label="t('platformDelivery.decision')" :for="`review-decision-${requirement.id}`">
          <BaseSelect :id="`review-decision-${requirement.id}`" v-model="decisions[requirement.id].decision" :options="decisionOptions()" :data-testid="`delivery-review-decision-${requirement.id}`" />
        </BaseFormField>
        <template v-if="decisions[requirement.id].decision">
          <BaseFormField :label="t('platformDelivery.reviewEnvironment')" :for="`review-environment-${requirement.id}`">
            <BaseInput :id="`review-environment-${requirement.id}`" v-model="decisions[requirement.id].environment" />
          </BaseFormField>
          <BaseFormField :label="t('platformDelivery.reason')" :error="fieldErrors[requirement.id]" :required="decisions[requirement.id].decision !== 'approved'" :for="`review-message-${requirement.id}`">
            <BaseTextarea :id="`review-message-${requirement.id}`" v-model="decisions[requirement.id].message" :rows="3" :error="!!fieldErrors[requirement.id]" :data-testid="`delivery-review-message-${requirement.id}`" />
          </BaseFormField>
        </template>
      </template>
    </section>
    <section v-if="historical" class="space-y-4">
      <BaseFormField :label="t('platformDelivery.sourceEvidence')" for="delivery-historical-source">
        <BaseSelect id="delivery-historical-source" v-model="evidence.source_message_id" :options="evidenceOptions" data-testid="delivery-historical-source" />
      </BaseFormField>
      <pre v-if="selectedEvidence" class="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-surface-raised p-3 text-sm text-text-muted">{{ selectedEvidence.content }}</pre>
      <template v-else>
        <BaseFormRow :cols="2">
          <BaseFormField :label="t('platformDelivery.originalReviewer')" for="delivery-historical-reviewer" required><BaseInput id="delivery-historical-reviewer" v-model="evidence.original_reviewer" /></BaseFormField>
          <BaseFormField :label="t('platformDelivery.approvedAt')" for="delivery-historical-date" required><BaseInput id="delivery-historical-date" v-model="evidence.occurred_at" type="datetime-local" /></BaseFormField>
        </BaseFormRow>
        <BaseFormField :label="t('platformDelivery.evidenceChannel')" for="delivery-historical-channel"><BaseSelect id="delivery-historical-channel" v-model="evidence.evidence_channel" :options="[{ value: 'email', label: t('platformDelivery.emailChannel') }, { value: 'whatsapp', label: t('platformDelivery.whatsappChannel') }, { value: 'document', label: t('platformDelivery.documentChannel') }]" /></BaseFormField>
        <BaseFormField :label="t('platformDelivery.externalReference')" for="delivery-historical-reference" required><BaseInput id="delivery-historical-reference" v-model="evidence.external_reference" /></BaseFormField>
      </template>
      <BaseCheckbox v-model="evidence.client_statement" data-testid="delivery-historical-client-statement">{{ t('platformDelivery.clientStatement') }}</BaseCheckbox>
    </section>
    <BaseFormField :label="t(historical ? 'platformDelivery.evidenceMessage' : 'platformDelivery.reviewMessage')" :required="historical" for="delivery-review-report-message">
      <BaseTextarea id="delivery-review-report-message" v-model="message" :rows="4" data-testid="delivery-review-report-message" />
    </BaseFormField>
    <DeliveryDocumentPicker v-model="documentIds" :documents="documents" />
    <BaseModalActions>
      <BaseButton variant="ghost" @click="emit('cancel')">{{ t('platformDelivery.cancel') }}</BaseButton>
      <BaseButton type="submit" :loading="loading" data-testid="delivery-review-submit">{{ t('platformDelivery.submitReview') }}</BaseButton>
    </BaseModalActions>
  </form>
</template>
