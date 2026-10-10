<script setup>
import BaseActionMenu from './BaseActionMenu.vue'
import BaseButton from './BaseButton.vue'

defineProps({
  selectedCount: { type: Number, required: true },
  outsideCount: { type: Number, default: 0 },
  filteredCount: { type: Number, default: 0 },
  allFilteredSelected: { type: Boolean, default: false },
  actions: { type: Array, required: true },
  busy: { type: Boolean, default: false },
  testidPrefix: { type: String, default: 'records' },
  testid: { type: String, default: '' },
})

defineEmits(['clear', 'select-all'])
</script>

<template>
  <div
    v-if="selectedCount > 0"
    class="sticky bottom-4 z-20 mt-4 flex flex-col gap-3 rounded-xl border border-border-default bg-surface-raised p-3 pr-20 shadow-lg panel-portrait:flex-row panel-portrait:items-center"
    :data-testid="testid || `${testidPrefix}-bulk-bar`"
  >
    <span class="text-sm text-text-default">
      <span class="whitespace-nowrap">
        <span class="font-semibold tabular-nums">{{ selectedCount }}</span>
        seleccionado{{ selectedCount === 1 ? '' : 's' }}
      </span>
      <span
        v-if="outsideCount > 0"
        class="whitespace-nowrap text-xs text-text-muted"
        title="Se marcaron con otro filtro activo. La acción los incluye igual; la confirmación los lista uno por uno."
        :data-testid="`${testidPrefix}-bulk-outside`"
      >
        · {{ outsideCount }} fuera del filtro actual
      </span>
    </span>

    <slot name="selection-summary" />

    <BaseButton
      v-if="!allFilteredSelected && filteredCount > 0"
      variant="ghost"
      size="sm"
      :data-testid="`${testidPrefix}-select-all-filtered`"
      @click="$emit('select-all')"
    >
      Seleccionar los {{ filteredCount }} filtrados
    </BaseButton>

    <div class="flex flex-wrap items-center gap-2 panel-portrait:ml-auto">
      <BaseButton variant="secondary" size="sm" @click="$emit('clear')">
        Cancelar
      </BaseButton>
      <BaseActionMenu
        :items="actions"
        label="Acciones"
        placement="top"
        align="right"
        width="w-64"
        variant="primary"
        :disabled="busy"
        :testid="`${testidPrefix}-bulk-actions`"
      />
    </div>
  </div>
</template>
