<template>
  <div class="relative inline-flex items-center">
    <BaseChoiceSelect
      :model-value="proposal.status"
      :options="statusOptions"
      :disabled="updating"
      disabled-reason="Guardando el estado de la propuesta."
      size="sm"
      :trigger-class="statusClass(proposal.status)"
      aria-label="Cambiar estado de la propuesta"
      @update:model-value="onChange"
      @click.stop
    />
    <span v-if="updating" class="absolute right-1.5 flex items-center pointer-events-none">
      <svg class="animate-spin h-3 w-3 text-text-muted" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import BaseChoiceSelect from '~/components/base/BaseChoiceSelect.vue';
import {
  PROPOSAL_STATUSES,
  proposalTransitionStatusLabel,
  statusClass,
} from '~/utils/proposalStatuses';

/**
 * Badge-styled status select (admin mode). Pure intent-picker: the visible
 * value only moves when `proposal.status` updates after a successful PATCH;
 * on change the select snaps back and the chosen status is emitted for the
 * page to confirm/PATCH (useProposalStatusChange).
 */
const props = defineProps({
  proposal: { type: Object, required: true },
  updating: { type: Boolean, default: false },
});

const emit = defineEmits(['change']);

const naturalTargets = computed(() => props.proposal.available_transitions || []);
const forcedTargets = computed(() => PROPOSAL_STATUSES
  .map((s) => s.value)
  .filter((value) => value !== props.proposal.status && !naturalTargets.value.includes(value)));

const statusOptions = computed(() => [
  { value: props.proposal.status, label: proposalTransitionStatusLabel(props.proposal.status), disabled: true },
  ...naturalTargets.value.map(value => ({ value, label: proposalTransitionStatusLabel(value), group: 'Flujo normal' })),
  ...forcedTargets.value.map(value => ({ value, label: proposalTransitionStatusLabel(value), group: 'Forzar estado' })),
]);

function onChange(value) {
  // Only the confirmed server response changes the displayed value.
  if (value && value !== props.proposal.status) emit('change', value);
}
</script>
