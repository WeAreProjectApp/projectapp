<script setup>
import { computed, ref } from 'vue'
import BaseBadge from '~/components/base/BaseBadge.vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseTextarea from '~/components/base/BaseTextarea.vue'
import { listOf } from '~/utils/buildingWithUs'
import { estimateRequest, estimateWhatsappMessage, tierWhatsappUrl } from '~/utils/buildingOnDemand'

const props = defineProps({
  program: { type: Object, required: true },
  language: { type: String, default: 'es' },
})
const { t } = useI18n()
const label = (key, params = {}) => t(`buildingOnDemand.${key}`, params, {
  locale: props.language === 'en' ? 'en-us' : 'es-co',
})
const selection = ref({})
const description = ref('')
const boundedDescription = computed({
  get: () => description.value,
  set: (value) => { description.value = String(value).slice(0, 1000) },
})
const tiers = computed(() => listOf(props.program.tiers?.items))
const sizes = computed(() => listOf(props.program.estimator?.sizes))
const tasks = computed(() => listOf(props.program.estimator?.tasks).filter((task) => (
  sizes.value.some((size) => size.id === task.size)
  && tiers.value.some((tier) => tier.id === task.min_tier)
)))
const estimate = computed(() => estimateRequest({
  tiers: tiers.value,
  sizes: sizes.value,
  tasks: tasks.value,
  selection: selection.value,
}))
const suggestedResult = computed(() => estimate.value.tierResults.find(({ tier }) => tier.id === estimate.value.suggestedTier?.id))
const suggestionReason = computed(() => {
  const keys = { roles: 'estimateReasonRoles', hours: 'estimateReasonHours', months: 'estimateReasonMonths' }
  const key = keys[estimate.value.suggestionReason]
  return key ? label(key, { months: suggestedResult.value?.monthsNeeded }) : ''
})
const whatsappUrl = computed(() => tierWhatsappUrl(props.program.contact?.whatsapp_base_url, estimateWhatsappMessage({
  program: props.program,
  selection: selection.value,
  description: description.value,
  language: props.language,
})))
const quantityFor = (taskId) => selection.value[taskId] || 0
const sizeFor = (task) => sizes.value.find((size) => size.id === task.size)
const statusLabel = (status) => label({ fits: 'estimateFits', 'may-fit': 'estimateMayFit', exceeds: 'estimateExceeds' }[status])
const statusVariant = (status) => ({ fits: 'success', 'may-fit': 'warning', exceeds: 'danger' }[status])

function changeQuantity(taskId, amount) {
  selection.value = {
    ...selection.value,
    [taskId]: Math.max(0, Math.min(10, quantityFor(taskId) + amount)),
  }
}
</script>

<template>
  <section id="estimator" data-document-enter class="building-on-demand-estimator min-w-0 scroll-mt-6 space-y-6 [overflow-wrap:anywhere]" data-testid="building-on-demand-estimator">
    <div>
      <h2 class="text-3xl font-light text-text-brand sm:text-4xl">{{ program.estimator?.title }}</h2>
      <p class="mt-4 max-w-3xl text-base leading-7 text-text-muted">{{ program.estimator?.summary }}</p>
    </div>

    <div class="grid min-w-0 grid-cols-1 items-start gap-6 lg:grid-cols-2">
      <div class="min-w-0 space-y-5">
        <div class="space-y-2">
          <label for="building-on-demand-description" class="block text-base font-medium text-text-default">
            {{ program.estimator?.description_label }}
          </label>
          <BaseTextarea
            id="building-on-demand-description"
            v-model="boundedDescription"
            :placeholder="program.estimator?.description_placeholder"
            :maxlength="1000"
            :rows="4"
            aria-describedby="building-on-demand-description-count"
            class="w-full text-base"
            data-testid="building-on-demand-estimator-description"
          />
          <p id="building-on-demand-description-count" class="text-right text-sm text-text-muted">
            {{ label('descriptionCounter', { count: description.length, max: 1000 }) }}
          </p>
        </div>

        <ul class="space-y-3">
          <li
            v-for="task in tasks"
            :key="task.id"
            class="flex min-w-0 flex-col gap-4 rounded-xl border border-border-default bg-surface p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div class="min-w-0 space-y-2">
              <p class="text-base font-semibold text-text-default">{{ task.label }}</p>
              <p class="text-sm text-text-muted">{{ task.hint }}</p>
              <BaseBadge variant="neutral" v-bind="{ textPolicy: 'wrap' }">
                {{ label('taskSize', { size: task.size.toUpperCase(), min: sizeFor(task).hours_min, max: sizeFor(task).hours_max }) }}
              </BaseBadge>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <BaseButton
                variant="secondary"
                icon-only
                class="min-h-11 min-w-11"
                :aria-label="label('quantityDecrease', { task: task.label })"
                :disabled="quantityFor(task.id) === 0"
                :disabled-reason="label('quantityMinimum')"
                :data-testid="`building-on-demand-task-${task.id}-decrease`"
                @click="changeQuantity(task.id, -1)"
              >
                <span aria-hidden="true" class="text-xl">−</span>
              </BaseButton>
              <output
                class="min-w-6 text-center text-base font-semibold tabular-nums text-text-default"
                aria-live="polite"
                aria-atomic="true"
                :aria-label="label('taskQuantity', { task: task.label, count: quantityFor(task.id) })"
                :data-testid="`building-on-demand-task-${task.id}-quantity`"
              >
                {{ quantityFor(task.id) }}
              </output>
              <BaseButton
                variant="secondary"
                icon-only
                class="min-h-11 min-w-11"
                :aria-label="label('quantityIncrease', { task: task.label })"
                :disabled="quantityFor(task.id) === 10"
                :disabled-reason="label('quantityMaximum')"
                :data-testid="`building-on-demand-task-${task.id}-increase`"
                @click="changeQuantity(task.id, 1)"
              >
                <span aria-hidden="true" class="text-xl">+</span>
              </BaseButton>
            </div>
          </li>
        </ul>
      </div>

      <div class="min-w-0 space-y-5 rounded-2xl border border-border-default bg-surface-raised p-5 sm:p-6 lg:sticky lg:top-6 lg:self-start">
        <template v-if="estimate.hasSelection">
          <p class="text-xl font-semibold text-text-default" aria-live="polite" data-testid="building-on-demand-estimate-range">
            {{ label('estimateRange', { min: estimate.hoursMin, max: estimate.hoursMax }) }}
          </p>
          <ul class="space-y-3">
            <li
              v-for="result in estimate.tierResults"
              :key="result.tier.id"
              class="min-w-0 space-y-2 rounded-xl border bg-surface p-4"
              :class="result.tier.id === estimate.suggestedTier?.id ? 'border-primary ring-1 ring-primary/20' : 'border-border-default'"
              :data-testid="`building-on-demand-estimate-tier-${result.tier.id}`"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-base font-semibold text-text-default">{{ result.tier.name }}</p>
                <BaseBadge :variant="statusVariant(result.status)" v-bind="{ textPolicy: 'wrap' }">{{ statusLabel(result.status) }}</BaseBadge>
              </div>
              <p class="text-sm text-text-muted">{{ label('bagHours', { hours: result.tier.bag_hours }) }}</p>
              <p v-if="result.status === 'exceeds'" class="text-sm font-semibold text-text-default">{{ label('estimateMonths', { months: result.monthsNeeded }) }}</p>
              <p v-if="!result.eligible" class="text-sm text-text-muted">{{ label('estimateRoleRequirement', { tier: estimate.requiredTier?.name }) }}</p>
            </li>
          </ul>
          <div v-if="estimate.suggestedTier" class="space-y-2 rounded-xl bg-primary-soft p-4" data-testid="building-on-demand-estimate-suggested">
            <p class="text-sm font-semibold text-text-brand">{{ label('suggestedTierLabel') }}</p>
            <p class="text-xl font-semibold text-text-default">{{ estimate.suggestedTier.name }}</p>
            <p class="text-sm text-text-muted">{{ suggestionReason }}</p>
          </div>
          <BaseButton
            as="a"
            :to="whatsappUrl"
            variant="primary"
            v-bind="{ textPolicy: 'wrap' }"
            target="_blank"
            rel="noopener noreferrer"
            class="min-h-11 w-full"
            data-testid="building-on-demand-estimate-whatsapp"
          >
            {{ label('estimateWhatsapp') }}
          </BaseButton>
        </template>
        <p v-else class="text-base text-text-muted">{{ label('estimatorEmpty') }}</p>
      </div>
    </div>

    <p class="max-w-prose text-sm text-text-muted">{{ program.estimator?.disclaimer }}</p>
  </section>
</template>

<style scoped>
.building-on-demand-estimator :deep(textarea) {
  font-size: 1rem;
}
</style>
