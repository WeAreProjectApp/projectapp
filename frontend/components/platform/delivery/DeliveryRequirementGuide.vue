<script setup>
import { computed } from 'vue'
import BaseBadge from '~/components/base/BaseBadge.vue'

const props = defineProps({ requirement: { type: Object, required: true } })
const { t } = useI18n()
const prose = (value) => (Array.isArray(value) ? value.filter((item) => String(item || '').trim()).join('\n') : String(value || '')).trim()
const fields = computed(() => [
  ['role', 'role'], ['environment', 'environment'], ['preparation', 'preparation'],
  ['access', 'access'], ['data', 'data'], ['allowed_actions', 'allowedActions'],
  ['expected_result', 'expected'], ['failure_signals', 'failures'],
  ['blocked_actions', 'blockedActions'], ['blocked_result', 'blockedResult'], ['dependencies', 'dependencies'],
].filter(([key]) => prose(props.requirement.guide?.[key])))
const stepLists = computed(() => [['steps', 'steps'], ['blocked_steps', 'blockedSteps']].map(([key, label]) => ({
  key, label, steps: (props.requirement.guide?.[key] || []).filter((step) => prose(step)),
})).filter(({ steps }) => steps.length))
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
    <dl v-if="fields.length" class="grid gap-4 sm:grid-cols-2">
      <div v-for="[key, label] in fields" :key="key" class="min-w-0" :data-testid="`delivery-guide-field-${key}`">
        <dt class="text-xs font-semibold text-text-muted">{{ t(`platformDelivery.${label}`) }}</dt>
        <dd class="mt-1 whitespace-pre-line break-words text-sm text-text-default">{{ prose(requirement.guide[key]) }}</dd>
      </div>
    </dl>
    <div v-for="{ key, label, steps } in stepLists" :key="key" :data-testid="`delivery-guide-${key}`">
      <h6 class="text-xs font-semibold text-text-muted">{{ t(`platformDelivery.${label}`) }}</h6>
      <ol class="mt-2 list-decimal space-y-2 pl-5 text-sm text-text-default">
        <li v-for="(step, index) in steps" :key="index" class="whitespace-pre-line break-words">{{ step }}</li>
      </ol>
    </div>
    <slot />
  </article>
</template>
