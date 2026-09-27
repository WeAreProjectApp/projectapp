<script setup>
import { useId, computed, ref, watch } from 'vue';
import { formatMoney } from '~/utils/formatMoney';
import { todayISO } from '~/utils/periodDates';

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  saving: { type: Boolean, default: false },
});
const emit = defineEmits(['close', 'submit']);

const mode = ref('until');
const resumeDate = ref('');
const modeOptions = [
  { value: 'until', label: 'Hasta una fecha' },
  { value: 'indefinite', label: 'Indefinidamente' },
];

function shiftedISO(days) {
  const value = new Date();
  value.setDate(value.getDate() + days);
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${value.getFullYear()}-${month}-${day}`;
}

watch(() => props.open, (open) => {
  if (!open) return;
  mode.value = 'until';
  resumeDate.value = shiftedISO(30);
}, { immediate: true });

const dateError = computed(() => {
  if (mode.value !== 'until') return '';
  if (!resumeDate.value) return 'Elige la fecha en que se reanudan los avisos.';
  if (resumeDate.value <= todayISO()) return 'Elige una fecha posterior a hoy.';
  return '';
});

function submit() {
  if (dateError.value) return;
  emit('submit', {
    muted: true,
    until: mode.value === 'until' ? resumeDate.value : null,
  });
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="confirm" size="sm" title-id="recurring-mute-title" @close="emit('close')">
    <form :id="modalFormId" data-testid="recurring-mute-modal" @submit.prevent="submit">
      <div class="px-6 pt-5">
        <h3 id="recurring-mute-title" class="text-lg font-bold text-text-default">Silenciar avisos</h3>
        <p v-if="record" class="mt-1 text-sm text-text-muted">
          {{ record.name }} — {{ formatMoney(Number(record.price), record.currency) }}
        </p>
      </div>
      <div class="space-y-4 px-6 py-4">
        <BaseFormField label="Duración">
          <BaseSegmented v-model="mode" :options="modeOptions" size="sm" data-testid="recurring-mute-mode" />
        </BaseFormField>
        <BaseFormField
          v-if="mode === 'until'"
          label="Reanudar avisos el"
          :error="dateError"
          hint="Ese día el pago vuelve al calendario de próximos cobros."
        >
          <BaseInput
            v-model="resumeDate"
            type="date"
            :min="shiftedISO(1)"
            data-testid="recurring-mute-date"
          />
        </BaseFormField>
        <p v-else class="text-xs text-text-subtle">
          No se enviarán avisos hasta que los reactives a mano.
        </p>
      </div>
    </form>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="ghost" @click="emit('close')">Cancelar</BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          :loading="saving"
          :disabled="!!dateError"
          :disabled-reason="dateError"
          data-testid="recurring-mute-submit"
          >Silenciar</BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
