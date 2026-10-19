<script setup>
import { computed, ref, watch } from 'vue';
import { useHostingPeriod } from '~/composables/useHostingPeriod';
import { FREQUENCY_OPTIONS } from '~/utils/recurring';

const props = defineProps({ record: { type: Object, required: true } });
const emit = defineEmits(['change']);
const form = ref({ period_start: props.record.period_date ?? '', period_end: '', period_cadence: '' });
const { anchorStart, cycleOptions, isCycleActive, applyCycle, onPeriodEndEdited, periodEndError } = useHostingPeriod(form, {
  isHosting: computed(() => true), isEdit: computed(() => false),
  isDuplicate: computed(() => false), seed: computed(() => null),
});
anchorStart.value = props.record.period_date ?? '';
watch([form, periodEndError], () => {
  const touched = form.value.period_end || form.value.period_cadence || form.value.period_start !== (props.record.period_date ?? '');
  const complete = form.value.period_start && form.value.period_end && form.value.period_cadence && !periodEndError.value;
  emit('change', { period: touched && complete ? { ...form.value } : null, invalid: Boolean(touched && !complete) });
}, { deep: true, immediate: true });
const cycleLabel = (months) => ({ 1: '1 mes', 3: '3 meses', 6: '6 meses', 12: '1 año' })[months] ?? `${months} meses`;
</script>

<template>
  <section class="rounded-lg border border-border-muted p-4 space-y-3" data-testid="income-liquidate-period-block">
    <h4 class="text-sm font-medium text-text-default">Período que cubre {{ record.concept }}</h4>
    <p class="text-xs text-text-subtle">Opcional: si lo dejas vacío, la liquidación se registra igual.</p>
    <BaseFormRow :cols="3" :gap="3" help="Al elegir la periodicidad se calcula la fecha de fin del período.">
      <BaseFormField label="Periodicidad">
        <BaseSelect v-model="form.period_cadence" :options="FREQUENCY_OPTIONS" placeholder="Elegir periodicidad" data-testid="income-liquidate-period-cadence" />
      </BaseFormField>
      <BaseFormField label="Inicio del período">
        <BaseInput v-model="form.period_start" type="date" data-testid="income-liquidate-period-start" />
      </BaseFormField>
      <BaseFormField label="Fin del período" :error="periodEndError">
        <BaseInput v-model="form.period_end" type="date" :error="Boolean(periodEndError)" data-testid="income-liquidate-period-end" @update:model-value="onPeriodEndEdited" />
      </BaseFormField>
    </BaseFormRow>
    <div class="flex flex-wrap gap-2" data-testid="income-liquidate-cycles">
      <BaseButton v-for="option in cycleOptions" :key="option.months" type="button" size="sm" :variant="isCycleActive(option) ? 'primary' : 'secondary'" :aria-pressed="isCycleActive(option)" :data-testid="`income-liquidate-cycle-${option.months}`" @click="applyCycle(option)">
        {{ cycleLabel(option.months) }}
      </BaseButton>
    </div>
  </section>
</template>
