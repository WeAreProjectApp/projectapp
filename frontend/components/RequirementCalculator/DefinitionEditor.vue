<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  modelValue: { type: Object, required: true },
  parametersOnly: { type: Boolean, default: false },
});
const { t } = useI18n();
const search = ref('');
const page = ref(0);
const sizeOptions = ['XS', 'S', 'M', 'L', 'XL', 'PROJECT'];
const filteredSignals = computed(() => props.modelValue.signals.filter((row) => `${row.label} ${row.description} ${row.size}`.toLowerCase().includes(search.value.toLowerCase())));
const pageCount = computed(() => Math.max(1, Math.ceil(filteredSignals.value.length / 15)));
const signals = computed(() => filteredSignals.value.slice(page.value * 15, (page.value + 1) * 15));
watch(search, () => { page.value = 0; });
const fieldClass = 'w-full rounded-lg border border-input-border bg-input-bg px-3 py-2 text-sm text-input-text';
function addSignal() {
  props.modelValue.signals.push({ id: `signal-${crypto.randomUUID()}`, size: 'XS', label: '', description: '', surcharge_percent: '0' });
  search.value = '';
  page.value = Math.floor((props.modelValue.signals.length - 1) / 15);
}
function addModifier() {
  props.modelValue.modifiers.push({ id: `modifier-${crypto.randomUUID()}`, label: '', kind: 'percentage', minimum: '0', maximum: '0', applies_to: ['XS', 'S', 'M', 'L', 'XL'], exclusive_group: '' });
}
</script>

<template>
  <div class="space-y-6" data-testid="calculator-definition-editor">
    <p v-if="parametersOnly" class="rounded-xl bg-surface-muted p-4 text-sm text-text-muted">{{ t('requirementCalculator.parametersOnly') }}</p>
    <section v-if="!parametersOnly" class="space-y-4 rounded-xl border border-border-default p-4">
      <label class="block text-sm text-text-default">{{ t('requirementCalculator.name') }}<input v-model="modelValue.title" :class="fieldClass" data-testid="calculator-title"></label>
      <label class="block text-sm text-text-default">{{ t('requirementCalculator.methodology') }}<textarea v-model="modelValue.methodology" rows="7" :class="fieldClass" /></label>
      <label v-for="(_, index) in modelValue.project_rules" :key="index" class="block text-sm text-text-default">{{ t('requirementCalculator.projectRule') }} {{ index + 1 }}<textarea v-model="modelValue.project_rules[index]" rows="2" :class="fieldClass" /></label>
      <BaseButton variant="secondary" @click="modelValue.project_rules.push('')">{{ t('requirementCalculator.addProjectRule') }}</BaseButton>
    </section>
    <section class="space-y-4">
      <h2 class="text-lg font-semibold text-text-default">{{ t('requirementCalculator.sizes') }}</h2>
      <article v-for="size in modelValue.sizes" :key="size.id" class="space-y-3 rounded-xl border border-border-default p-4" :data-testid="`calculator-size-${size.id}`">
        <h3 class="font-semibold text-text-default">{{ size.id }} · {{ size.label }}</h3>
        <template v-if="!parametersOnly">
          <label class="block text-sm text-text-default">{{ t('requirementCalculator.name') }}<input v-model="size.label" :class="fieldClass"></label>
          <label class="block text-sm text-text-default">{{ t('requirementCalculator.definition') }}<textarea v-model="size.definition" :class="fieldClass" /></label>
          <label v-for="(_, index) in size.examples" :key="index" class="block text-sm text-text-default">{{ t('requirementCalculator.example') }} {{ index + 1 }}<input v-model="size.examples[index]" :class="fieldClass"></label>
          <BaseButton variant="ghost" size="sm" @click="size.examples.push('')">{{ t('requirementCalculator.addExample') }}</BaseButton>
        </template>
        <p v-else class="text-sm text-text-muted">{{ size.definition }}</p>
        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <label v-for="field in ['points', 'hours_min', 'hours_max', 'standard_value_cop']" :key="field" class="block text-sm text-text-default">{{ t(`requirementCalculator.${field}`) }}<input v-model="size[field]" type="number" min="0" step="0.001" :class="fieldClass" :data-testid="`calculator-${size.id}-${field}`"></label>
        </div>
      </article>
    </section>
    <details class="rounded-xl border border-border-default p-4">
      <summary class="cursor-pointer font-semibold text-text-default">{{ t('requirementCalculator.signals') }} ({{ modelValue.signals.length }})</summary>
      <div class="mt-4 space-y-4">
        <label class="block text-sm text-text-default">{{ t('requirementCalculator.search') }}<input v-model="search" :class="fieldClass"></label>
        <article v-for="signal in signals" :key="signal.id" class="space-y-3 rounded-lg bg-surface-muted p-3">
          <p class="text-sm font-medium text-text-default">{{ signal.label }}</p>
          <template v-if="!parametersOnly">
            <label class="block text-sm text-text-default">{{ t('requirementCalculator.name') }}<input v-model="signal.label" :class="fieldClass"></label>
            <label class="block text-sm text-text-default">{{ t('requirementCalculator.definition') }}<textarea v-model="signal.description" rows="3" :class="fieldClass" /></label>
          </template>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block text-sm text-text-default">{{ t('requirementCalculator.size') }}<select v-model="signal.size" :class="fieldClass"><option v-for="size in sizeOptions" :key="size" :value="size">{{ size }}</option></select></label>
            <label class="block text-sm text-text-default">{{ t('requirementCalculator.surcharge') }}<input v-model="signal.surcharge_percent" type="number" min="0" step="0.001" :class="fieldClass"></label>
          </div>
          <BaseButton v-if="!parametersOnly" variant="danger-ghost" size="sm" @click="modelValue.signals.splice(modelValue.signals.indexOf(signal), 1)">{{ t('requirementCalculator.remove') }}</BaseButton>
        </article>
        <div class="flex flex-wrap items-center gap-3">
          <BaseButton variant="secondary" :disabled="page === 0" :disabled-reason="t('requirementCalculator.firstPage')" @click="page--">{{ t('requirementCalculator.previous') }}</BaseButton>
          <span class="text-sm text-text-muted">{{ page + 1 }} / {{ pageCount }}</span>
          <BaseButton variant="secondary" :disabled="page + 1 >= pageCount" :disabled-reason="t('requirementCalculator.lastPage')" @click="page++">{{ t('requirementCalculator.next') }}</BaseButton>
          <BaseButton v-if="!parametersOnly" variant="secondary" @click="addSignal">{{ t('requirementCalculator.addSignal') }}</BaseButton>
        </div>
      </div>
    </details>
    <details class="rounded-xl border border-border-default p-4">
      <summary class="cursor-pointer font-semibold text-text-default">{{ t('requirementCalculator.modifiers') }}</summary>
      <div class="mt-4 space-y-4">
        <article v-for="modifier in modelValue.modifiers" :key="modifier.id" class="space-y-3 rounded-lg bg-surface-muted p-3">
          <p class="text-sm font-medium text-text-default">{{ modifier.label }}</p>
          <template v-if="!parametersOnly">
            <label class="block text-sm text-text-default">{{ t('requirementCalculator.name') }}<input v-model="modifier.label" :class="fieldClass"></label>
            <label class="block text-sm text-text-default">{{ t('requirementCalculator.kind') }}<select v-model="modifier.kind" :class="fieldClass"><option v-for="kind in ['percentage', 'factor', 'fixed_hours', 'separate']" :key="kind" :value="kind">{{ t(`requirementCalculator.${kind}`) }}</option></select></label>
            <label class="block text-sm text-text-default">{{ t('requirementCalculator.exclusiveGroup') }}<input v-model="modifier.exclusive_group" :class="fieldClass"></label>
            <fieldset><legend class="text-sm text-text-default">{{ t('requirementCalculator.appliesTo') }}</legend><label v-for="size in sizeOptions.slice(0, 5)" :key="size" class="mr-3 inline-flex items-center gap-1 text-sm text-text-default"><input v-model="modifier.applies_to" type="checkbox" :value="size">{{ size }}</label></fieldset>
          </template>
          <div class="grid gap-3 sm:grid-cols-2">
            <label v-for="field in ['minimum', 'maximum']" :key="field" class="block text-sm text-text-default">{{ t(`requirementCalculator.${field}`) }}<input v-model="modifier[field]" type="number" min="0" step="0.001" :class="fieldClass"></label>
          </div>
          <BaseButton v-if="!parametersOnly" variant="danger-ghost" size="sm" @click="modelValue.modifiers.splice(modelValue.modifiers.indexOf(modifier), 1)">{{ t('requirementCalculator.remove') }}</BaseButton>
        </article>
        <BaseButton v-if="!parametersOnly" variant="secondary" @click="addModifier">{{ t('requirementCalculator.addModifier') }}</BaseButton>
      </div>
    </details>
    <details v-if="!parametersOnly" class="rounded-xl border border-border-default p-4">
      <summary class="cursor-pointer font-semibold text-text-default">{{ t('requirementCalculator.families') }}</summary>
      <div class="mt-4 space-y-4">
        <article v-for="(family, index) in modelValue.families" :key="index" class="space-y-2 rounded-lg bg-surface-muted p-3">
          <label v-for="field in ['label', 'small', 'medium', 'large', 'extra_large']" :key="field" class="block text-sm text-text-default">{{ t(`requirementCalculator.${field}`) }}<input v-model="family[field]" :class="fieldClass"></label>
          <BaseButton variant="danger-ghost" size="sm" @click="modelValue.families.splice(index, 1)">{{ t('requirementCalculator.remove') }}</BaseButton>
        </article>
        <BaseButton variant="secondary" @click="modelValue.families.push({ label: '', small: '', medium: '', large: '', extra_large: '' })">{{ t('requirementCalculator.addFamily') }}</BaseButton>
      </div>
    </details>
    <section class="space-y-3 rounded-xl border border-border-default p-4">
      <h2 class="font-semibold text-text-default">{{ t('requirementCalculator.calibration') }}</h2>
      <div class="grid gap-3 sm:grid-cols-3">
        <label v-for="field in ['minimum_samples', 'deviation_percent', 'hourly_cost_cop']" :key="field" class="block text-sm text-text-default">{{ t(`requirementCalculator.${field}`) }}<input v-model="modelValue.calibration[field]" type="number" min="0" :step="field === 'minimum_samples' ? '1' : '0.001'" :class="fieldClass"></label>
      </div>
    </section>
  </div>
</template>
