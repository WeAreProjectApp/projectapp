<script setup>
import BaseCheckbox from '~/components/base/BaseCheckbox.vue'
defineProps({ modelValue: { type: Array, default: () => [] }, documents: { type: Array, default: () => [] } })
defineEmits(['update:modelValue'])
const { t } = useI18n()
</script>

<template>
  <fieldset class="min-w-0 space-y-2">
    <legend class="mb-2 text-sm font-medium text-text-default">{{ t('platformDelivery.optionalDocuments') }}</legend>
    <p v-if="!documents.length" class="text-sm text-text-muted">{{ t('platformDelivery.noDocuments') }}</p>
    <BaseCheckbox v-for="document in documents" :key="document.id" class="flex" :model-value="modelValue" :value="document.id" @update:model-value="$emit('update:modelValue', $event)">
      <span class="break-words">{{ document.title }}</span>
    </BaseCheckbox>
  </fieldset>
</template>
