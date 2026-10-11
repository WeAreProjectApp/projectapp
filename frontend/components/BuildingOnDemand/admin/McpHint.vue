<script setup>
import { computed } from 'vue';
import { useI18n } from '#imports';
import BaseBadge from '~/components/base/BaseBadge.vue';

const props = defineProps({ connector: { type: Object, default: null } });
const { t } = useI18n();
const connectorState = computed(() => {
  if (props.connector?.is_active === true) return { key: 'active', variant: 'success' };
  if (props.connector?.is_active === false) return { key: 'inactive', variant: 'warning' };
  return { key: 'unavailable', variant: 'neutral' };
});
</script>

<template>
  <section class="min-w-0 rounded-2xl border border-border-default bg-surface p-5 panel-portrait:p-6" aria-labelledby="building-on-demand-admin-mcp-title" data-testid="building-on-demand-admin-mcp-hint">
    <div class="flex flex-wrap items-center gap-2">
      <h2 id="building-on-demand-admin-mcp-title" class="text-lg font-medium text-text-brand">{{ t('buildingOnDemandAdmin.mcpHint.title') }}</h2>
      <BaseBadge :variant="connectorState.variant" :textPolicy="'wrap'" data-testid="building-on-demand-admin-mcp-status">{{ t(`buildingOnDemandAdmin.mcpHint.${connectorState.key}`) }}</BaseBadge>
    </div>
    <p class="mt-3 max-w-3xl text-sm leading-6 text-text-muted">{{ t('buildingOnDemandAdmin.mcpHint.description') }}</p>
    <code class="mt-3 block max-w-full text-sm text-text-default [overflow-wrap:anywhere]" data-testid="building-on-demand-admin-mcp-slug">{{ connector?.slug || 'building-on-demand' }}</code>
  </section>
</template>
