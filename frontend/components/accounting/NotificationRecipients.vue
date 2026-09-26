<script setup>
import EntityHistoryRecordModal from '~/components/history/EntityHistoryRecordModal.vue';
import { computed, onMounted, ref } from 'vue'
import ConfirmModal from '~/components/ConfirmModal.vue'
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue'
import AccountingRowActionsButton from '~/components/accounting/AccountingRowActionsButton.vue'
import AccountingRowActionsModal from '~/components/accounting/AccountingRowActionsModal.vue'
import { leadingRowActions } from '~/utils/accountingRowActions'
import { useConfirmModal } from '~/composables/useConfirmModal'
import { usePanelNotify } from '~/composables/usePanelNotify'
import { useAccountingStore } from '~/stores/accounting'
import { formatDate } from '~/utils/formatDate'

const props = defineProps({
  /**
   * Master switch state (AccountingSettings.notifications_enabled). Owned by
   * the parent page; this component only reads it to warn that the list is
   * moot while everything is paused.
   */
  notificationsEnabled: { type: Boolean, default: true },
})

const store = useAccountingStore()
const notify = usePanelNotify()
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal()

// Draft address being added; `newEmailError` shows serializer feedback
// (bad format, duplicate) inline instead of as a toast that scrolls away.
const newEmail = ref('')
const newEmailError = ref('')
const isAdding = ref(false)
const togglingId = ref(null)

const recipients = computed(() => store.notificationRecipients)
const activeCount = computed(
  () => recipients.value.filter((row) => row.is_active).length,
)

onMounted(() => store.fetchRecords('notificationRecipients'))

async function addRecipient() {
  const email = newEmail.value.trim()
  if (!email) {
    newEmailError.value = 'Escribe un correo.'
    return
  }
  isAdding.value = true
  newEmailError.value = ''
  const result = await store.createRecord('notificationRecipients', { email })
  isAdding.value = false
  if (result.success) {
    newEmail.value = ''
    notify.success('Destinatario agregado.')
    return
  }
  newEmailError.value = result.fieldErrors?.email || result.message
}

async function toggleRecipient(row) {
  togglingId.value = row.id
  const result = await store.updateRecord('notificationRecipients', row.id, {
    is_active: !row.is_active,
  })
  togglingId.value = null
  if (result.success) {
    notify.success(
      result.data.is_active
        ? `${row.email} vuelve a recibir los avisos.`
        : `${row.email} queda pausado: no recibirá avisos.`,
    )
  } else {
    notify.error({
      title: 'No se pudo cambiar el estado',
      detail: result.message,
    })
  }
}

// ── Row menu ──
const actionsRow = ref(null)
const historyRow = ref(null)
const noteRow = ref(null)

const recipientActions = computed(() => (actionsRow.value
  ? [
    ...leadingRowActions(actionsRow.value),
    { id: 'remove', action: 'remove', label: 'Quitar', danger: true },
  ]
  : []))

const recipientActionHandlers = {
  history: (row) => { historyRow.value = row },
  notes: (row) => { noteRow.value = row },
  remove: (row) => requestDelete(row),
}

function runRecipientAction(id, row) {
  recipientActionHandlers[id]?.(row)
}

function requestDelete(row) {
  requestConfirm({
    title: 'Quitar destinatario',
    message:
      `¿Quitar ${row.email} de la lista? Dejará de recibir los avisos de ` +
      'cambios contables, la deuda de tarjetas, los extractos, el calendario ' +
      'de cobros y pagos y los pagos de hosting. ' +
      'Si es una pausa temporal, usa el interruptor en vez de quitarlo.',
    variant: 'danger',
    confirmText: 'Quitar',
    onConfirm: async () => {
      const result = await store.deleteRecord('notificationRecipients', row.id)
      if (result.success) {
        notify.success('Destinatario eliminado.')
      } else {
        notify.error({
          title: 'No se pudo eliminar el destinatario',
          detail: result.message,
        })
      }
    },
  })
}
</script>

<template>
  <div>
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />

    <p class="text-xs font-semibold text-text-subtle uppercase tracking-wider mb-2">
      Destinatarios
    </p>

    <!-- The two ways the automation ends up reaching nobody, told apart so
         the fix is obvious: turn the master switch back on, or activate
         someone. -->
    <BaseAlert
      v-if="!props.notificationsEnabled"
      variant="warning"
      class="mb-3"
      data-testid="recipients-master-off-warning"
    >
      Las notificaciones están desactivadas: no sale ningún correo del módulo,
      sin importar quién esté activo en esta lista.
    </BaseAlert>
    <BaseAlert
      v-else-if="activeCount === 0"
      variant="warning"
      class="mb-3"
      data-testid="recipients-none-active-warning"
    >
      Ningún destinatario activo: la automatización está apagada de hecho y
      nadie se entera de nada. Activa al menos un correo.
    </BaseAlert>

    <p
      v-if="recipients.length === 0"
      class="text-sm text-text-subtle mb-3"
      data-testid="recipients-empty"
    >
      Sin destinatarios registrados.
    </p>
    <ul v-else class="space-y-2 mb-4">
      <!-- Kebab first, like every accounting row: history, the note and
           Quitar live in its menu. The switch stays in the row because it is
           the recipient's state, read at a glance, not an action on it. -->
      <li
        v-for="row in recipients"
        :key="row.id"
        class="flex items-center gap-3 rounded-lg border border-border-muted px-3 py-2"
        :data-testid="`recipients-row-${row.id}`"
      >
        <AccountingRowActionsButton
          :label="`Acciones de ${row.email}`"
          :test-id="`recipients-actions-${row.id}`"
          @open="actionsRow = row"
        />
        <div class="min-w-0 flex-1">
          <p
            class="text-sm text-text-default truncate"
            :class="{ 'opacity-60': !row.is_active }"
            :data-testid="`recipients-email-${row.id}`"
          >
            {{ row.email }}
          </p>
          <p class="text-xs text-text-subtle">
            <span :data-testid="`recipients-state-${row.id}`">
              {{ row.is_active ? 'Activo' : 'Pausado' }}
            </span>
            · Alta {{ formatDate(row.created_at) }}
          </p>
        </div>
        <BaseToggle
          class="shrink-0"
          :model-value="row.is_active"
          :disabled="togglingId === row.id"
          :aria-label="`Enviar avisos a ${row.email}`"
          :data-testid="`recipients-toggle-${row.id}`"
          @update:model-value="toggleRecipient(row)"
        />
      </li>
    </ul>

    <AccountingRowActionsModal
      :open="actionsRow !== null"
      :record="actionsRow"
      :title="actionsRow?.email || ''"
      :subtitle="actionsRow ? (actionsRow.is_active ? 'Activo' : 'Pausado') : ''"
      :actions="recipientActions"
      test-id-prefix="recipients"
      @close="actionsRow = null"
      @select="runRecipientAction"
    />

    <EntityHistoryRecordModal
      :open="historyRow !== null"
      entity-type="notification_recipient"
      :record="historyRow"
      @close="historyRow = null"
    />

    <AccountingNoteModal
      :open="noteRow !== null"
      :subtitle="noteRow?.email || ''"
      :notes="noteRow?.notes ?? ''"
      @close="noteRow = null"
    />

    <BaseFormField label="Agregar correo" :error="newEmailError">
      <div class="flex flex-col items-stretch gap-2 panel-portrait:flex-row panel-portrait:items-start">
        <BaseInput
          v-model="newEmail"
          type="email"
          placeholder="correo@dominio.com"
          class="flex-1"
          :error="Boolean(newEmailError)"
          data-testid="recipients-new-email"
          @keyup.enter="addRecipient"
        />
        <BaseButton
          variant="secondary"
          size="md"
          class="w-full panel-portrait:w-auto"
          :disabled="isAdding"
          data-testid="recipients-add"
          @click="addRecipient"
        >
          <BaseActionIcon action="create" />
          <span>{{ isAdding ? 'Agregando...' : 'Agregar' }}</span>
        </BaseButton>
      </div>
    </BaseFormField>
  </div>
</template>
