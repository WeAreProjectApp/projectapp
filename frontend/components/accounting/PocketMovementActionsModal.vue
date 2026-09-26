<script setup>
import BaseButton from '~/components/base/BaseButton.vue'
import BaseModal from '~/components/base/BaseModal.vue'
import { hasNote } from '~/utils/accountingRowActions'
import { formatDate } from '~/utils/formatDate'
import { formatMoney } from '~/utils/formatMoney'

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
})

const emit = defineEmits(['close', 'history', 'notes', 'edit', 'delete'])

function signedAmount(row) {
  if (!row) return formatMoney(0)
  const prefix = row.direction === 'out' ? '-' : ''
  return `${prefix}${formatMoney(Number(row.amount ?? 0))}`
}

function run(event) {
  if (!props.record) return
  emit(event, props.record)
  emit('close')
}
</script>

<template>
  <BaseModal
    :model-value="open"
    kind="confirm"
    title-id="pocket-actions-title"
    @close="emit('close')"
  >
    <div data-testid="pocket-actions-modal">
      <header class="border-b border-border-muted px-6 pb-4 pt-6">
        <h3 id="pocket-actions-title" class="break-words text-base font-bold text-text-default">
          {{ record?.concept || `Movimiento #${record?.id}` }}
        </h3>
        <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-text-muted">
          <span>{{ formatDate(record?.movement_date) }}</span>
          <span aria-hidden="true">·</span>
          <span>{{ record?.direction_label }}</span>
          <span aria-hidden="true">·</span>
          <span class="tabular-nums">{{ signedAmount(record) }}</span>
        </p>
      </header>

      <ul class="py-2">
        <li>
          <!-- design-tokens: allow-raw-button -- menu row, not a standalone CTA -->
          <button
            type="button"
            class="flex min-h-11 w-full items-center gap-3 px-6 py-3 text-left text-sm text-text-default transition-colors hover:bg-surface-raised"
            :data-testid="`pocket-action-history-${record?.id}`"
            @click="run('history')"
          >
            <BaseActionIcon action="view" class="h-5 w-5" />
            <span>Detalle e historial</span>
          </button>
        </li>
        <li v-if="hasNote(record)">
          <!-- design-tokens: allow-raw-button -- menu row, not a standalone CTA -->
          <button
            type="button"
            class="flex min-h-11 w-full items-center gap-3 px-6 py-3 text-left text-sm text-text-default transition-colors hover:bg-surface-raised"
            :data-testid="`pocket-action-notes-${record?.id}`"
            @click="run('notes')"
          >
            <BaseActionIcon action="notes" class="h-5 w-5" />
            <span>Ver nota</span>
          </button>
        </li>
        <li>
          <!-- design-tokens: allow-raw-button -- menu row, not a standalone CTA -->
          <button
            type="button"
            class="flex min-h-11 w-full items-center gap-3 px-6 py-3 text-left text-sm text-text-default transition-colors hover:bg-surface-raised"
            :data-testid="`pocket-action-edit-${record?.id}`"
            @click="run('edit')"
          >
            <BaseActionIcon action="edit" class="h-5 w-5" />
            <span>Editar</span>
          </button>
        </li>
        <li>
          <!-- design-tokens: allow-raw-button -- menu row, not a standalone CTA -->
          <button
            type="button"
            class="flex min-h-11 w-full items-center gap-3 px-6 py-3 text-left text-sm text-danger-strong transition-colors hover:bg-danger-soft"
            :data-testid="`pocket-action-delete-${record?.id}`"
            @click="run('delete')"
          >
            <BaseActionIcon action="delete" class="h-5 w-5" />
            <span>Eliminar</span>
          </button>
        </li>
      </ul>

      <div class="border-t border-border-muted px-6 py-4">
        <BaseButton class="w-full" variant="secondary" @click="emit('close')">
          Cerrar
        </BaseButton>
      </div>
    </div>
  </BaseModal>
</template>
