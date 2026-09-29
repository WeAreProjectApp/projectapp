<template>
  <BaseBadge :variant="variant" size="sm" :data-testid="`secure-link-status-${state}`">{{ label }}</BaseBadge>
</template>

<script setup>
import { computed } from 'vue';
import BaseBadge from '~/components/base/BaseBadge.vue';

const VARIANTS = { ready: 'success', sent: 'info', opened: 'info', expired: 'warning', revoked: 'danger' };

const props = defineProps({
  status: { type: String, required: true },
  teamOnly: { type: Boolean, default: false },
});

const { t } = useI18n();
const state = computed(() => ({ active: 'ready', consumed: 'opened' })[props.status] || props.status);
const variant = computed(() => VARIANTS[state.value] || 'neutral');
const label = computed(() => VARIANTS[state.value]
  ? t(`secureLinks.states.${props.teamOnly && state.value === 'ready' ? 'receivedReady' : state.value}`)
  : props.status);
</script>
