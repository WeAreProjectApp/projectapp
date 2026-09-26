<script setup>
import { computed } from 'vue'
import BaseButton from '~/components/base/BaseButton.vue'
import BaseModal from '~/components/base/BaseModal.vue'
import { HISTORY_ROW_ACTION } from '~/utils/accountingRowActions'
import { formatMoney } from '~/utils/formatMoney'

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
  busy: { type: Boolean, default: false },
})

const emit = defineEmits([
  'close', 'detail', 'notes', 'download', 'emails', 'resend',
  'mark-paid', 'cancel', 'delete',
])

const actions = computed(() => {
  const row = props.record
  if (!row) return []

  // The collection detail modal carries the record history too, hence the
  // shared label; the id stays `view-detail` because it opens that modal.
  const list = [
    { ...HISTORY_ROW_ACTION, id: 'view-detail', event: 'detail' },
  ]

  if (row.notes) {
    list.push({
      id: 'notes', action: 'notes', label: 'Ver notas internas',
      event: 'notes',
    })
  }

  list.push(
    {
      id: 'download-pdf', action: 'download', label: 'Descargar PDF',
      event: 'download',
    },
    {
      id: 'emails', action: 'email-history', label: 'Ver correos enviados',
      event: 'emails',
    },
  )

  if (['issued', 'paid'].includes(row.commercial_status)) {
    list.push({
      id: 'resend', action: 'resend', label: 'Reenviar al cliente',
      event: 'resend',
    })
  }

  if (row.commercial_status === 'issued') {
    list.push({
      id: 'mark-paid',
      action: 'complete',
      label: row.income_kind === 'expected' ? 'Registrar pago (liquidar)' : 'Marcar pagada',
      event: 'mark-paid',
    })
  }

  if (['draft', 'issued'].includes(row.commercial_status)) {
    list.push({
      id: 'cancel', action: 'void', label: 'Anular', event: 'cancel', danger: true,
    })
  }

  if (row.can_delete) {
    list.push({
      id: 'delete', action: 'delete', label: 'Eliminar', event: 'delete', danger: true,
    })
  }

  return list
})

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP')
}

function run(action) {
  if (props.busy || !props.record) return
  emit(action.event, props.record)
  emit('close')
}
</script>

<template>
  <BaseModal
    :model-value="open"
    kind="confirm"
    title-id="collection-actions-title"
    @close="emit('close')"
  >
    <div data-testid="collection-actions-modal">
      <header class="border-b border-border-muted px-6 pb-4 pt-6">
        <h3 id="collection-actions-title" class="text-base font-bold text-text-default">
          {{ record?.public_number || `Cuenta #${record?.id}` }}
        </h3>
        <p class="mt-1 text-sm text-text-muted">
          {{ record?.client_display_name || record?.customer_name || 'Sin cliente' }}
          · <span class="tabular-nums">{{ money(record?.total) }}</span>
        </p>
      </header>

      <ul class="py-2">
        <li v-for="action in actions" :key="action.id">
          <!-- design-tokens: allow-raw-button -- menu row, not a standalone CTA -->
          <button
            type="button"
            class="flex min-h-11 w-full items-center gap-3 px-6 py-3 text-left text-sm transition-colors"
            :class="action.danger
              ? 'text-danger-strong hover:bg-danger-soft'
              : 'text-text-default hover:bg-surface-raised'"
            :disabled="busy"
            :data-testid="`collection-${action.id}-${record?.id}`"
            @click="run(action)"
          >
            <BaseActionIcon :action="action.action" class="h-5 w-5" />
            <span>{{ action.label }}</span>
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
