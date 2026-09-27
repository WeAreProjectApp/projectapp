<template>
  <BaseModal
    :model-value="open"
    kind="detail"
    title-id="stats-modal-title"
    @close="emit('close')"
  >
    <div data-testid="stats-modal">
      <div class="px-4 pb-3 pt-5 panel-portrait:px-6 panel-portrait:pt-6">
        <h3 id="stats-modal-title" class="text-lg font-bold text-text-default">
          {{ title }}
        </h3>
        <p v-if="subtitle" class="text-sm text-text-muted mt-1">{{ subtitle }}</p>
      </div>

      <div class="border-b border-border-muted px-4 panel-portrait:px-6">
        <BaseTabs
          :model-value="modelValue"
          :tabs="tabs"
          @update:model-value="emit('update:modelValue', $event)"
        />
      </div>

      <div class="min-h-[340px] px-4 py-5 panel-portrait:px-6">
        <div v-if="loading" class="space-y-3" data-testid="stats-modal-loading">
          <div class="h-16 rounded-xl bg-surface-raised motion-safe:animate-pulse" />
          <div class="h-64 rounded-xl bg-surface-raised motion-safe:animate-pulse" />
        </div>
        <slot v-else :active-tab="modelValue" />
      </div>

    </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="secondary" @click="emit('close')">
          Cerrar
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseButton from '~/components/base/BaseButton.vue';
import BaseTabs from '~/components/base/BaseTabs.vue';

/**
 * Shared shell for the analytics modals: BaseModal + BaseTabs + a slot
 * that receives the active tab. Consumers must render tab panels with
 * v-if (not v-show) so ApexCharts never mounts inside a hidden panel
 * at width 0.
 */
defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  /** BaseTabs shape: [{ id, label, badge?, disabled? }]. */
  tabs: { type: Array, required: true },
  /** Active tab id. */
  modelValue: { type: String, required: true },
  size: { type: String, default: '5xl' },
  loading: { type: Boolean, default: false },
});

const emit = defineEmits(['close', 'update:modelValue']);
</script>
