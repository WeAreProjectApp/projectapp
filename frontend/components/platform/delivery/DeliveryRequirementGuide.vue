<script setup>
import { computed } from 'vue'
import BaseBadge from '~/components/base/BaseBadge.vue'

const props = defineProps({ requirement: { type: Object, required: true } })
const { t } = useI18n()
const fields = computed(() => [
  ['role', 'role'], ['environment', 'environment'], ['preparation', 'preparation'],
  ['data', 'data'], ['expected_result', 'expected'], ['failure_signals', 'failures'],
].filter(([key]) => props.requirement.guide?.[key]))
const prose = (value) => Array.isArray(value) ? value.join('\n') : String(value || '')
</script>

<template>
  <article :id="`requirement-${requirement.id}`" class="min-w-0 space-y-4 rounded-xl border border-border-default bg-surface p-4 sm:p-5" :data-testid="`delivery-requirement-${requirement.id}`">
    <header class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0 flex-1">
        <p class="text-xs text-text-muted">{{ requirement.key }}</p>
        <h5 class="break-words text-base font-semibold text-text-default">{{ requirement.title }}</h5>
      </div>
      <BaseBadge :variant="requirement.review_status === 'approved' ? 'success' : requirement.review_status === 'rejected' ? 'danger' : requirement.review_status === 'objected' ? 'warning' : 'info'">
        {{ t(`platformDelivery.status.${requirement.review_status || 'pending'}`) }}
      </BaseBadge>
    </header>
    <p v-if="requirement.description" class="whitespace-pre-line break-words text-sm text-text-muted">{{ requirement.description }}</p>
    <p v-if="requirement.review_status === 'approved'" class="text-sm text-success-strong">{{ t('platformDelivery.frozenHint') }}</p>
    <dl class="grid gap-4 sm:grid-cols-2">
      <div v-for="[key, label] in fields" :key="key" class="min-w-0">
        <dt class="text-xs font-semibold text-text-muted">{{ t(`platformDelivery.${label}`) }}</dt>
        <dd class="mt-1 whitespace-pre-line break-words text-sm text-text-default">{{ prose(requirement.guide[key]) }}</dd>
      </div>
    </dl>
    <div v-if="requirement.guide?.steps?.length">
      <h6 class="text-xs font-semibold text-text-muted">{{ t('platformDelivery.steps') }}</h6>
      <ol class="mt-2 list-decimal space-y-2 pl-5 text-sm text-text-default">
        <li v-for="(step, index) in requirement.guide.steps" :key="index" class="whitespace-pre-line break-words">{{ step }}</li>
      </ol>
    </div>
    <slot />
  </article>
</template>
