<script setup>
import { ref } from 'vue';

const props = defineProps({
  rows: { type: Array, required: true },
  busy: Boolean,
});
const emit = defineEmits(['inspect', 'accept']);
const { t } = useI18n();
const notes = ref({});
</script>

<template>
  <section class="space-y-3" data-testid="calculator-cost-coverage">
    <h2 class="text-lg font-semibold text-text-default">{{ t('requirementCalculator.packageCoverage') }}</h2>
    <div class="grid gap-3 md:grid-cols-3">
      <article v-for="row in props.rows" :key="row.corpus_digest" class="min-w-0 space-y-3 rounded-xl border border-border-default p-4" :data-testid="'calculator-cost-' + row.size">
        <h3 class="font-semibold text-text-default">{{ row.size }} · {{ t('requirementCalculator.costStatus.' + row.economic_status) }}</h3>
        <p class="text-sm text-text-muted">{{ t('requirementCalculator.verifiedSamples', { verified: row.verified_cost_samples, total: row.samples }) }}</p>
        <p v-if="row.median_verified_cost_cop !== null" class="text-sm text-text-default">{{ t('requirementCalculator.verifiedMedian', { cost: row.median_verified_cost_cop, value: row.standard_value_cop ?? '—' }) }}</p>
        <p v-if="row.covers_verified_median_cost === false" class="text-sm text-danger-strong">{{ t('requirementCalculator.verifiedUnderCost') }}</p>
        <p v-if="row.last_review" class="break-words text-sm text-text-muted">{{ t('requirementCalculator.lastDecision', { date: row.last_review.created_at.slice(0, 10), note: row.last_review.note }) }}</p>
        <BaseButton variant="link" :disabled="busy" @click="emit('inspect', row)">{{ t('requirementCalculator.inspectSamples') }}</BaseButton>
        <form v-if="row.economic_status === 'provisional' && row.covers_verified_median_cost !== null" class="space-y-2" @submit.prevent="emit('accept', row, notes[row.corpus_digest]?.trim())">
          <label class="block text-sm">{{ t('requirementCalculator.costDecisionNote') }}
            <textarea v-model="notes[row.corpus_digest]" required maxlength="2000" class="mt-1 w-full rounded-lg border border-input-border bg-input-bg p-2 text-input-text" />
          </label>
          <BaseButton type="submit" :disabled="busy || !notes[row.corpus_digest]?.trim()" :disabled-reason="t('requirementCalculator.costDecisionNote')">{{ t('requirementCalculator.acceptCostReview') }}</BaseButton>
        </form>
      </article>
    </div>
  </section>
</template>
