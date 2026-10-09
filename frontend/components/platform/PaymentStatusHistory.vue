<template>
  <div v-if="sortedHistory.length" class="mt-4 border-t border-input-border pt-4">
    <p class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-green-light/60">
      {{ title }}
    </p>
    <ul class="space-y-2.5">
      <li
        v-for="h in sortedHistory"
        :key="h.id"
        class="flex flex-col gap-0.5 border-l-2 border-input-border pl-3"
      >
        <span class="text-xs font-medium text-text-brand dark:text-white">
          {{ statusLabel(h.from_status) }} → {{ statusLabel(h.to_status) }}
        </span>
        <span class="text-[10px] text-green-light/70">{{ formatDateTime(h.created_at) }}</span>
        <span v-if="h.source" class="text-[10px] text-green-light/50">{{ sourceLabel(h.source) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatDateTime } from '~/utils/formatDate'

const props = defineProps({
  payment: {
    type: Object,
    required: true,
  },
  title: {
    type: String,
    default: 'Historial de estado del pago',
  },
})

const STATUS_LABELS = {
  pending: 'Pendiente',
  overdue: 'Vencido',
  paid: 'Pagado',
  processing: 'Procesando',
  failed: 'Fallido',
  voided: 'Anulado',
}

const SOURCE_LABELS = {
  api: 'Pago con tarjeta (API)',
  wompi_link: 'Link de pago Wompi',
  webhook: 'Confirmación automática (Wompi)',
  wompi_verify: 'Verificación de transacción',
  system: 'Sistema',
}

const sortedHistory = computed(() => {
  const raw = props.payment?.history
  if (!raw?.length) return []
  return [...raw].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
})

function statusLabel(s) {
  return STATUS_LABELS[s] || s
}

function sourceLabel(s) {
  if (!s) return ''
  return SOURCE_LABELS[s] || s
}
</script>
