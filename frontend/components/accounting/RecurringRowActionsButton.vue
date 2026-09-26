<script setup>
defineProps({
  row: { type: Object, required: true },
  busy: { type: Boolean, default: false },
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
      :label="`Acciones de ${row.name || `pago recurrente ${row.id}`}`"
      :status-label="busy ? 'Preparando duplicado' : ''"
      :loading="busy"
      :disabled="busy"
      :data-testid="`recurring-actions-${row.id}`"
      @click.stop="emit('open', row)"
    />
  </div>
</template>
