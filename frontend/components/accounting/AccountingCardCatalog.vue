<script setup>
import EntityHistoryRecordModal from '~/components/history/EntityHistoryRecordModal.vue';
import { computed, onMounted, ref } from 'vue'
import ConfirmModal from '~/components/ConfirmModal.vue'
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue'
import AccountingRowActionsButton from '~/components/accounting/AccountingRowActionsButton.vue'
import AccountingRowActionsModal from '~/components/accounting/AccountingRowActionsModal.vue'
import { useConfirmModal } from '~/composables/useConfirmModal'
import { usePanelNotify } from '~/composables/usePanelNotify'
import { useAccountingStore } from '~/stores/accounting'
import { leadingRowActions } from '~/utils/accountingRowActions'
import { formatMoney } from '~/utils/formatMoney'

const store = useAccountingStore()
const notify = usePanelNotify()
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal()

// Editable copies of the catalog rows; `id: null` marks an unsaved card.
const rows = ref([])
const savingId = ref(null)
let draftKey = 0

function toRow(record) {
  return {
    id: record.id,
    key: `card-${record.id}`,
    name: record.name,
    credit_limit: record.credit_limit != null ? Number(record.credit_limit) : null,
    is_active: Boolean(record.is_active),
    statements_since: record.statements_since
      ? String(record.statements_since).slice(0, 7)
      : '',
  }
}

function syncRows() {
  rows.value = store.creditCards.map(toRow)
}

async function load() {
  const result = await store.fetchRecords('creditCards')
  if (result.success) syncRows()
}

onMounted(load)

function addRow() {
  rows.value.push({
    id: null,
    key: `draft-${++draftKey}`,
    name: '',
    credit_limit: null,
    is_active: true,
    statements_since: '',
  })
}

function removeDraft(row) {
  rows.value = rows.value.filter((item) => item.key !== row.key)
}

function buildPayload(row) {
  return {
    name: row.name.trim(),
    credit_limit: row.credit_limit,
    is_active: row.is_active,
    statements_since: row.statements_since || null,
  }
}

async function saveRow(row) {
  if (!row.name.trim() || !row.credit_limit || Number(row.credit_limit) <= 0) {
    notify.error('La tarjeta necesita nombre y un cupo mayor a cero.')
    return
  }
  savingId.value = row.key
  const payload = buildPayload(row)
  const result = row.id
    ? await store.updateRecord('creditCards', row.id, payload)
    : await store.createRecord('creditCards', payload)
  savingId.value = null
  if (result.success) {
    notify.success(row.id ? 'Tarjeta actualizada.' : 'Tarjeta agregada.')
    syncRows()
  } else {
    notify.error({
      title: 'No se pudo guardar la tarjeta',
      detail: result.message,
    })
  }
}

// ── Row menu ──
// The editable copy (toRow) drops notes and trims statements_since, so the
// menu, the history and the note are fed with the stored card instead: the
// history must show what was saved, not what is being typed.
const actionsRecord = ref(null)
const historyRecord = ref(null)
const noteRecord = ref(null)

function cardRecord(row) {
  return store.creditCards.find((card) => card.id === row.id) || null
}

const cardActions = computed(() => (actionsRecord.value
  ? [
    ...leadingRowActions(actionsRecord.value),
    { id: 'delete', action: 'delete', label: 'Eliminar', danger: true },
  ]
  : []))

const cardActionHandlers = {
  history: (card) => { historyRecord.value = card },
  notes: (card) => { noteRecord.value = card },
  delete: (card) => requestDelete(card),
}

function runCardAction(id, card) {
  cardActionHandlers[id]?.(card)
}

function requestDelete(row) {
  if (!row.id) {
    removeDraft(row)
    return
  }
  requestConfirm({
    title: 'Eliminar tarjeta',
    message: `¿Eliminar "${row.name}" del catálogo? Si tiene registros o extractos asociados, el sistema pedirá desactivarla en su lugar.`,
    variant: 'danger',
    confirmText: 'Eliminar',
    onConfirm: async () => {
      const result = await store.deleteRecord('creditCards', row.id)
      if (result.success) {
        notify.success('Tarjeta eliminada.')
        syncRows()
      } else {
        notify.error({
          title: 'No se pudo eliminar la tarjeta',
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

    <p v-if="rows.length === 0" class="text-sm text-text-subtle mb-3">
      No hay tarjetas en el catálogo.
    </p>
    <div v-else class="space-y-3 mb-3">
      <div
        v-for="row in rows"
        :key="row.key"
        class="rounded-lg border border-border-muted p-3 space-y-3"
        :data-testid="`card-catalog-row-${row.key}`"
      >
        <!-- A saved card leads with its kebab (history, note, Eliminar). An
             unsaved draft has no record yet: it only offers to discard. -->
        <div v-if="row.id" class="flex items-center gap-2">
          <AccountingRowActionsButton
            :label="`Acciones de ${cardRecord(row)?.name || row.name}`"
            :test-id="`card-catalog-actions-${row.key}`"
            @open="actionsRecord = cardRecord(row)"
          />
          <p class="min-w-0 truncate text-sm font-medium text-text-default">
            {{ cardRecord(row)?.name || row.name }}
          </p>
        </div>
        <BaseFormRow :cols="3" :gap="3">
          <BaseFormField label="Nombre" required>
            <BaseInput
              v-model="row.name"
              placeholder="T.C 0064"
              :data-testid="`card-catalog-name-${row.key}`"
            />
          </BaseFormField>
          <BaseFormField label="Cupo" required>
            <BaseCurrencyInput
              v-model="row.credit_limit"
              :data-testid="`card-catalog-limit-${row.key}`"
            />
          </BaseFormField>
          <BaseFormField label="Extractos desde">
            <BaseInput
              v-model="row.statements_since"
              type="month"
              :data-testid="`card-catalog-since-${row.key}`"
            />
          </BaseFormField>
        </BaseFormRow>
        <div class="flex items-center justify-between gap-3">
          <label class="flex items-center gap-2 text-sm text-text-default">
            <BaseToggle
              v-model="row.is_active"
              :aria-label="`Tarjeta ${row.name || 'nueva'} activa`"
            />
            Activa
          </label>
          <div class="flex flex-wrap items-center justify-end gap-2">
            <BaseActionButton
              v-if="!row.id"
              action="delete"
              variant="danger-ghost"
              size="sm"
              label="Descartar tarjeta nueva"
              :data-testid="`card-catalog-delete-${row.key}`"
              @click="removeDraft(row)"
            />
            <BaseButton
              variant="primary"
              size="sm"
              :disabled="savingId === row.key"
              :data-testid="`card-catalog-save-${row.key}`"
              @click="saveRow(row)"
            >
              {{ savingId === row.key ? 'Guardando...' : 'Guardar' }}
            </BaseButton>
          </div>
        </div>
      </div>
    </div>

    <BaseButton
      variant="secondary"
      size="sm"
      class="w-full panel-portrait:w-auto"
      data-testid="card-catalog-add"
      @click="addRow"
    >
      <BaseActionIcon action="create" />
      <span>Agregar tarjeta</span>
    </BaseButton>

    <AccountingRowActionsModal
      :open="actionsRecord !== null"
      :record="actionsRecord"
      :title="actionsRecord?.name || ''"
      :subtitle="actionsRecord ? `Cupo ${formatMoney(Number(actionsRecord.credit_limit ?? 0))}` : ''"
      :actions="cardActions"
      test-id-prefix="card-catalog"
      :test-id-suffix="actionsRecord ? `card-${actionsRecord.id}` : undefined"
      @close="actionsRecord = null"
      @select="runCardAction"
    />

    <EntityHistoryRecordModal
      :open="historyRecord !== null"
      entity-type="credit_card"
      :record="historyRecord"
      @close="historyRecord = null"
    />

    <AccountingNoteModal
      :open="noteRecord !== null"
      :subtitle="noteRecord?.name || ''"
      :notes="noteRecord?.notes ?? ''"
      @close="noteRecord = null"
    />
  </div>
</template>
