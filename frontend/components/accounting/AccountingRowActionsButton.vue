<script setup>
/**
 * The three-dot button of an accounting row.
 *
 * It sits alone in the table's leading 56px track (`menu-start`) and only
 * opens the row's actions menu: every action, detail and history included,
 * belongs to that menu. 44px square keeps the coarse-pointer target.
 */
defineProps({
  /** Names the row it acts on: "Acciones de <record>". */
  label: { type: String, required: true },
  testId: { type: String, required: true },
  /** An action chosen from the menu is still working on this row. */
  busy: { type: Boolean, default: false },
  busyLabel: { type: String, default: 'Procesando' },
});

const emit = defineEmits(['open']);
</script>

<template>
  <div class="flex items-center justify-center">
    <BaseActionButton
      action="more"
      variant="ghost"
      size="sm"
      class="h-11 w-11 shrink-0"
      :label="label"
      :status-label="busy ? busyLabel : ''"
      :loading="busy"
      :disabled="busy"
      :data-testid="testId"
      @click.stop="emit('open')"
    />
  </div>
</template>
