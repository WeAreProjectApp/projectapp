<template>
  <BaseModal
    :model-value="open"
    kind="confirm"
    size="sm"
    title-id="income-actions-title"
    @close="emit('close')"
  >
    <div data-testid="income-actions-modal">
      <!-- Which income you are acting on. A kebab in a dense table loses
           that context otherwise. -->
      <div class="px-6 pt-6 pb-4 border-b border-border-muted">
        <h3 id="income-actions-title" class="text-base font-bold text-text-default">
          {{ record?.concept || `Ingreso #${record?.id}` }}
        </h3>
        <p class="text-sm text-text-muted mt-1">
          {{ record?.client_name || 'Sin cliente' }}
          <span v-if="record?.project_name"> · {{ record.project_name }}</span>
          · <span class="tabular-nums">{{ money(record?.total_amount) }}</span>
          · {{ record?.kind_label }}
        </p>
      </div>

      <ul class="py-2">
        <li v-for="action in actions" :key="action.id">
          <!-- Menu rows, not standalone actions: a BaseButton variant per
               row would paint eight competing buttons inside one list. -->
          <!-- design-tokens: allow-raw-button -->
          <button
            type="button"
            class="flex w-full items-center gap-3 px-6 py-3 text-sm text-left transition-colors"
            :class="action.danger
              ? 'text-danger-strong hover:bg-danger-soft'
              : 'text-text-default hover:bg-surface-raised'"
            :data-testid="`income-action-${action.id}-${record?.id}`"
            @click="run(action)"
          >
            <BaseActionIcon :action="action.action" class="h-5 w-5" />
            <span>{{ action.label }}</span>
          </button>
        </li>
      </ul>

      <div class="px-6 py-4 border-t border-border-muted flex justify-end">
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

/**
 * Every action available on one income, in one list.
 *
 * A modal rather than a dropdown on purpose: both accounting tables wrap in
 * `overflow-x-auto`, which clips an absolutely-positioned menu — the last
 * rows and narrow viewports would cut it off.
 *
 * One component for both the grouped and the classic view, which had already
 * drifted apart: the classic table had silently lost the mute action.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
});

const emit = defineEmits([
  'close', 'detail', 'notes', 'edit', 'duplicate', 'liquidate', 'generate-collection',
  'view-collection', 'view-emails', 'toggle-mute', 'write-off', 'delete',
]);

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

const actions = computed(() => {
  const row = props.record;
  if (!row) return [];
  const list = [
    // The income detail modal carries the record history too, hence the shared
    // label; the id stays `detail` because it opens that richer modal.
    { ...HISTORY_ROW_ACTION, id: 'detail', event: 'detail' },
    ...(hasNote(row) ? [{ ...NOTE_ROW_ACTION, event: 'notes' }] : []),
    { id: 'edit', action: 'edit', label: 'Editar', event: 'edit' },
    // Offered whatever the state is: the frequent case is duplicating an
    // already collected income to open its next period.
    {
      id: 'duplicate', action: 'duplicate', label: 'Duplicar',
      event: 'duplicate',
    },
  ];
  if (row.kind === 'expected') {
    list.push({
      id: 'liquidate', action: 'settle', label: 'Liquidar', event: 'liquidate',
    });
  }
  if (row.kind !== 'lost') {
    list.push(row.has_collection_account
      ? {
        id: 'view-collection',
        action: 'open-external',
        label: `Ver cuenta de cobro ${row.collection_account_number || ''}`.trim(),
        event: 'view-collection',
      }
      : {
        id: 'generate-collection',
        action: 'generate',
        label: 'Generar cuenta de cobro',
        event: 'generate-collection',
      });
  }
  if (row.kind === 'expected' && row.payment_status !== 'paid') {
    list.push({
      id: 'toggle-mute',
      action: row.reminders_muted ? 'unmute' : 'mute',
      label: row.reminders_muted ? 'Reactivar avisos' : 'Silenciar avisos',
      event: 'toggle-mute',
    });
  }
  if (row.kind === 'expected' && row.payment_status === 'pending') {
    list.push({
      id: 'write-off', action: 'write-off', label: 'Marcar como perdido',
      event: 'write-off',
    });
  }
  list.push({
    id: 'view-emails', label: 'Ver correos de este ingreso',
    action: 'email-history', event: 'view-emails',
  });
  list.push({
    id: 'delete', action: 'delete', label: 'Eliminar', event: 'delete',
    danger: true,
  });
  return list;
});

function run(action) {
  emit(action.event, props.record);
  emit('close');
}
</script>
