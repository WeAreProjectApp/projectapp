<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
defineProps({ documents: { type: Array, default: () => [] }, canEdit: { type: Boolean, default: false } })
defineEmits(['attach', 'download', 'unlink'])
const { t } = useI18n()
</script>

<template>
  <section class="min-w-0 space-y-2" data-testid="delivery-documents">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h6 class="text-xs font-semibold text-text-muted">{{ t('platformDelivery.documents') }}</h6>
      <BaseButton v-if="canEdit" variant="ghost" size="sm" @click="$emit('attach')">{{ t('platformDelivery.attach') }}</BaseButton>
    </div>
    <p v-if="!documents.length" class="text-xs text-text-subtle">{{ t('platformDelivery.noDocuments') }}</p>
    <ul v-else class="space-y-2">
      <li v-for="document in documents" :key="document.id" class="flex flex-col items-start justify-between gap-2 rounded-lg bg-surface-raised px-3 py-2 sm:flex-row sm:items-center">
        <span class="min-w-0 break-words text-sm text-text-default">{{ document.title }}</span>
        <div class="flex flex-wrap gap-2">
          <BaseButton variant="secondary" size="sm" :aria-label="`${t('platformDelivery.download')} · ${document.title}`" :data-testid="`delivery-document-download-${document.id}`" @click="$emit('download', document)">{{ t('platformDelivery.download') }}</BaseButton>
          <BaseButton v-if="canEdit" variant="danger-ghost" size="sm" :aria-label="`${t('platformDelivery.unlink')} · ${document.title}`" @click="$emit('unlink', document)">{{ t('platformDelivery.unlink') }}</BaseButton>
        </div>
      </li>
    </ul>
  </section>
</template>
