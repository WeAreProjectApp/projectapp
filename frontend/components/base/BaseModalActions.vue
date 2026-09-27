<template>
  <div
    class="flex shrink-0 flex-col-reverse gap-2 border-t border-border-muted bg-surface px-4 py-4 panel-portrait:flex-row panel-portrait:flex-wrap panel-portrait:justify-end panel-portrait:px-6"
    data-testid="base-modal-actions"
  >
    <slot />
  </div>
</template>

<style scoped>
@media (max-width: 639px) {
  :deep(.base-button:not(.base-button--link)) {
    width: 100%;
  }
}
</style>
