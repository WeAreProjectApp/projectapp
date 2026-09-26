<template>
  <BaseBadge :variant="meta.variant" size="sm" :data-testid="`secure-link-status-${status}`">{{ meta.label }}</BaseBadge>
</template>

<script setup>
import { computed } from 'vue';
import BaseBadge from '~/components/base/BaseBadge.vue';

const STATUS = {
  active: { label: 'Activo', variant: 'success' },
  consumed: { label: 'Usado', variant: 'info' },
  expired: { label: 'Vencido', variant: 'warning' },
  revoked: { label: 'Revocado', variant: 'danger' },
};

const props = defineProps({
  status: { type: String, required: true },
});

const meta = computed(() => STATUS[props.status] || { label: props.status, variant: 'neutral' });
</script>
