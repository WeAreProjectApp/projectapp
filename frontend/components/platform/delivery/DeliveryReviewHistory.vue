<script setup>
import BaseBadge from '~/components/base/BaseBadge.vue'
import DeliveryDocuments from './DeliveryDocuments.vue'

defineProps({ reviews: { type: Array, default: () => [] } })
defineEmits(['download'])
const { t, locale } = useI18n()
const date = (value) => value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : ''
const tone = (decision) => decision === 'approved' ? 'success' : decision === 'rejected' ? 'danger' : 'warning'
const evidenceDocuments = (review) => (review.evidence_documents || []).filter((document) =>
  review.evidence_document_ids?.includes(document.document_id))
const downloadableEvidence = (review) => evidenceDocuments(review).filter((document) => document.pdf_url)
const evidenceTitles = (review) => evidenceDocuments(review).filter((document) => !document.pdf_url && document.title)
</script>

<template>
  <section v-if="reviews.length" class="space-y-3 border-t border-border-muted pt-4" data-testid="delivery-review-history">
    <h6 class="text-sm font-semibold text-text-default">{{ t('platformDelivery.reviewEvidence') }}</h6>
    <article v-for="review in reviews" :key="review.id" class="space-y-3 rounded-xl bg-surface-raised p-3" :data-testid="`delivery-review-evidence-${review.id}`">
      <header class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex flex-wrap gap-2"><BaseBadge :variant="tone(review.decision)">{{ t(`platformDelivery.status.${review.decision}`) }}</BaseBadge><BaseBadge v-if="review.is_external" variant="neutral">{{ t('platformDelivery.externalApproval') }}</BaseBadge></div>
        <span class="text-xs text-text-muted">{{ t('platformDelivery.version', { version: review.version }) }}</span>
      </header>
      <dl class="grid gap-3 text-sm sm:grid-cols-2">
        <div><dt class="text-xs text-text-muted">{{ t('platformDelivery.originalReviewer') }}</dt><dd class="break-words text-text-default">{{ review.original_reviewer || review.actor_name }}</dd></div>
        <div><dt class="text-xs text-text-muted">{{ t('platformDelivery.reviewedAt') }}</dt><dd class="text-text-default"><time :datetime="review.reviewed_at">{{ date(review.reviewed_at) }}</time></dd></div>
        <div v-if="review.environment"><dt class="text-xs text-text-muted">{{ t('platformDelivery.reviewEnvironment') }}</dt><dd class="break-words text-text-default">{{ review.environment }}</dd></div>
        <div v-if="review.evidence_channel"><dt class="text-xs text-text-muted">{{ t('platformDelivery.evidenceChannel') }}</dt><dd class="text-text-default">{{ t(`platformDelivery.${review.evidence_channel}Channel`) }}</dd></div>
        <template v-if="review.is_external"><div><dt class="text-xs text-text-muted">{{ t('platformDelivery.recordedBy') }}</dt><dd class="break-words text-text-default">{{ review.actor_name }}</dd></div><div><dt class="text-xs text-text-muted">{{ t('platformDelivery.recordedAt') }}</dt><dd class="text-text-default"><time :datetime="review.recorded_at">{{ date(review.recorded_at) }}</time></dd></div></template>
      </dl>
      <p v-if="review.message" class="whitespace-pre-line break-words text-sm text-text-default">{{ review.message }}</p>
      <section v-if="review.client_statement" class="space-y-1">
        <h6 class="text-xs font-medium text-text-muted">{{ t('platformDelivery.evidenceMessage') }}</h6>
        <p class="whitespace-pre-line break-words text-sm text-text-default">{{ review.client_statement }}</p>
      </section>
      <DeliveryDocuments v-if="downloadableEvidence(review).length" :documents="downloadableEvidence(review)" @download="$emit('download', $event)" />
      <ul v-if="evidenceTitles(review).length" class="space-y-2 text-sm text-text-muted" :aria-label="t('platformDelivery.documents')">
        <li v-for="document in evidenceTitles(review)" :key="document.document_id" class="break-words">{{ document.title }}</li>
      </ul>
    </article>
  </section>
</template>
