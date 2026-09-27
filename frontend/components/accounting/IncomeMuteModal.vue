<script setup>
import { useId, computed, ref, watch } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import { formatMoney } from '~/utils/formatMoney';
import { todayISO } from '~/utils/periodDates';

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  saving: { type: Boolean, default: false },
});
const emit = defineEmits(['close', 'submit']);

const MODE_OPTIONS = [
  { value: 'until', label: 'Hasta una fecha' },
  { value: 'indefinite', label: 'Indefinidamente' },
];

const mode = ref('until');
const resumeDate = ref('');

function tomorrowISO() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

function defaultResumeDate() {
  const date = new Date();
  date.setDate(date.getDate() + 30);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

// Opens on "hasta una fecha" with a month prefilled: an indefinite mute is the
// option that loses a receivable, so it should be a deliberate choice rather
// than the landing state.
// `immediate` so the defaults are seeded even when the modal is mounted
// already open, instead of only on the false -> true transition.
watch(() => props.open, (open) => {
  if (!open) return;
  mode.value = 'until';
  resumeDate.value = defaultResumeDate();
}, { immediate: true });

const dateError = computed(() => {
  if (mode.value !== 'until') return '';
  if (!resumeDate.value) return 'Elige la fecha en que se reanudan los avisos.';
  if (resumeDate.value <= todayISO()) return 'Elige una fecha posterior a hoy.';
  return '';
});

function onSubmit() {
  if (dateError.value) return;
  emit('submit', {
    muted: true,
    until: mode.value === 'until' ? resumeDate.value : null,
  });
}

const modalFormId = useId();
</script>

<template>
  <BaseModal :model-value="open" kind="confirm" title-id="income-mute-title" @close="emit('close')">
    <form :id="modalFormId" data-testid="income-mute-modal" @submit.prevent="onSubmit">
      <div class="px-6 pt-5">
        <h3 id="income-mute-title" class="text-lg font-bold text-text-default">
          Silenciar avisos
        </h3>
        <p v-if="record" class="text-sm text-text-muted mt-1">
          {{ record.concept }} — {{ formatMoney(Number(record.total_amount)) }}
        </p>
      </div>

      <div class="px-6 py-4 space-y-4">
        <BaseFormField label="Duración">
          <BaseSegmented
            v-model="mode"
            :options="MODE_OPTIONS"
            size="sm"
            data-testid="income-mute-mode"
          />
        </BaseFormField>

        <BaseFormField
          v-if="mode === 'until'"
          label="Reanudar avisos el"
          :error="dateError"
          hint="Ese día el ingreso vuelve al correo diario."
        >
          <BaseInput
            v-model="resumeDate"
            type="date"
            :min="tomorrowISO()"
            data-testid="income-mute-date"
          />
        </BaseFormField>
        <p v-else class="text-xs text-text-subtle">
          No se enviarán avisos de este ingreso hasta que los reactives a mano.
        </p>
      </div>

    </form>
    <template #footer>
      <BaseModalActions>
        <BaseButton
          type="button"
          variant="ghost"
          data-testid="income-mute-cancel"
          @click="emit('close')"
        >
          Cancelar
        </BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          :loading="saving"
          :disabled="!!dateError"
          :disabled-reason="dateError"
          data-testid="income-mute-submit"
        >
          {{ saving ? 'Guardando...' : 'Silenciar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
