<template>
  <BaseModal
    :model-value="open"
    kind="confirm"
    size="sm"
    title-id="recurring-actions-title"
    @close="emit('close')"
  >
    <div data-testid="recurring-actions-modal">
      <div class="border-b border-border-muted px-6 pb-4 pt-6">
        <h3 id="recurring-actions-title" class="text-base font-bold text-text-default">
          {{ record?.name || `Pago recurrente #${record?.id}` }}
        </h3>
        <p class="mt-1 text-sm text-text-muted">
          {{ money(record?.price, record?.currency) }} · {{ record?.frequency_label }}
          · {{ record?.is_archived ? 'Archivado' : record?.is_active ? 'Activo' : 'Inactivo' }}
        </p>
      </div>

      <ul class="py-2">
        <li v-for="action in actions" :key="action.id">
          <!-- design-tokens: allow-raw-button -->
          <button
            type="button"
            class="flex w-full items-center gap-3 px-6 py-3 text-left text-sm transition-colors"
            :class="action.danger
              ? 'text-danger-strong hover:bg-danger-soft'
              : 'text-text-default hover:bg-surface-raised'"
            :data-testid="`recurring-action-${action.id}-${record?.id}`"
            @click="run(action)"
          >
            <BaseActionIcon :action="action.action" class="h-5 w-5" />
            <span>{{ action.label }}</span>
          </button>
        </li>
      </ul>

      <div class="flex justify-end border-t border-border-muted px-6 py-4">
        <BaseButton variant="secondary" @click="emit('close')">Cerrar</BaseButton>
      </div>
    </div>
  </BaseModal>
</template>

<script setup>
import { computed } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import { HISTORY_ROW_ACTION, NOTE_ROW_ACTION, hasNote } from '~/utils/accountingRowActions';
import { formatMoney } from '~/utils/formatMoney';

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
});

const emit = defineEmits([
  'close', 'history', 'notes', 'edit', 'duplicate', 'toggle-state', 'toggle-mute',
  'archive', 'restore', 'delete',
]);

function money(value, currency) {
  return formatMoney(Number(value ?? 0), currency || 'COP');
}

const actions = computed(() => {
  const row = props.record;
  if (!row) return [];
  const list = [
    { ...HISTORY_ROW_ACTION, event: 'history' },
    ...(hasNote(row) ? [{ ...NOTE_ROW_ACTION, event: 'notes' }] : []),
    { id: 'edit', action: 'edit', label: 'Editar', event: 'edit' },
    { id: 'duplicate', action: 'duplicate', label: 'Duplicar', event: 'duplicate' },
  ];
  if (row.is_archived) {
    list.push(
      { id: 'restore', action: 'restore', label: 'Restaurar como inactivo', event: 'restore' },
      {
        id: 'delete', action: 'delete', label: 'Eliminar definitivamente',
        event: 'delete', danger: true,
      },
    );
    return list;
  }
  list.push({
    id: row.is_active ? 'deactivate' : 'activate',
    action: row.is_active ? 'deactivate' : 'activate',
    label: row.is_active ? 'Desactivar' : 'Activar',
    event: 'toggle-state',
  });
  list.push({
    id: row.reminders_effectively_muted ? 'unmute' : 'mute',
    action: row.reminders_effectively_muted ? 'unmute' : 'mute',
    label: row.reminders_effectively_muted ? 'Reactivar avisos' : 'Silenciar avisos',
    event: 'toggle-mute',
  });
  list.push({
    id: 'archive', action: 'archive', label: 'Archivar', event: 'archive', danger: true,
  });
  return list;
});

function run(action) {
  emit(action.event, props.record);
  emit('close');
}
</script>
