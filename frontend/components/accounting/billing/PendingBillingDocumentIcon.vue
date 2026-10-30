<script setup>
import { ExclamationTriangleIcon } from '@heroicons/vue/24/solid'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseTooltip from '~/components/base/BaseTooltip.vue'
</script>
<template>
  <BaseTooltip text="Hace falta el documento vinculado" floating min-width="min-w-[220px]" width="max-w-xs" data-testid="pending-billing-document-icon">
    <template #trigger="{ tooltipId }">
      <BaseButton icon-only unstyled variant="ghost" size="sm" aria-label="Hace falta el documento vinculado" :aria-describedby="tooltipId" class="relative z-10 inline-flex min-h-8 min-w-8 items-center justify-center rounded-lg text-warning-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring">
        <ExclamationTriangleIcon class="h-5 w-5" aria-hidden="true" />
      </BaseButton>
    </template>
  </BaseTooltip>
</template>
