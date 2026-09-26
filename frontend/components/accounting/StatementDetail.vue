<template>
  <section class="bg-surface rounded-xl border border-border-muted shadow-sm" data-testid="statement-detail">
    <EntityHistorySection entity-type="statement" :object-id="statement.id" class="mx-5" />
    <header class="flex flex-col gap-3 border-b border-border-muted px-5 py-4 panel-portrait:flex-row panel-portrait:items-center panel-portrait:justify-between">
      <div>
        <h2 class="text-base font-medium text-text-default">
          {{ statement.card_name }} · <span class="capitalize">{{ statement.period_label }}</span>
        </h2>
        <p class="text-xs text-text-subtle mt-0.5">
          {{ statement.transactions.length }} transacciones · registrado {{ formatDate(statement.created_at) }}
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span
          class="text-xs px-2.5 py-1 rounded-full font-medium"
          :class="isProcessed ? 'bg-success-soft text-success-strong' : 'bg-warning-soft text-warning-strong'"
        >
          {{ statement.status_label }}
        </span>
        <BaseActionMenu
          v-if="isNarrowActions"
          :items="statementActions"
          :disabled="isUpdating"
          label="Acciones"
          testid="statement-actions"
        />
        <template v-else>
        <BaseButton
          v-if="!isProcessed"
          variant="secondary"
          size="sm"
          :disabled="isUpdating"
          data-testid="statement-edit-header"
          @click="$emit('edit-header')"
        >
          Editar encabezado
        </BaseButton>
        <BaseButton
          v-if="!isProcessed"
          variant="secondary"
          size="sm"
          :disabled="isUpdating"
          data-testid="statement-add-tx"
          @click="$emit('add-tx')"
        >
          Agregar transacción
        </BaseButton>
        <BaseButton
          v-if="!isProcessed"
          variant="primary"
          size="sm"
          :disabled="isUpdating"
          data-testid="statement-finalize"
          @click="$emit('finalize')"
        >
          Finalizar
        </BaseButton>
        <BaseButton
          v-else
          variant="secondary"
          size="sm"
          :disabled="isUpdating"
          data-testid="statement-reopen"
          @click="$emit('reopen')"
        >
          Reabrir
        </BaseButton>
        <BaseButton
          variant="danger"
          size="sm"
          :disabled="isUpdating"
          data-testid="statement-delete"
          @click="$emit('delete')"
        >
          Eliminar
        </BaseButton>
        </template>
      </div>
    </header>

    <div class="p-5">
      <AccountingIndicatorGroup :columns="4" :secondary-count="1">
        <template #primary>
          <AccountingStatCard
            label="Saldo de cierre"
            :value="money(statement.closing_balance)"
            :sub="statement.due_date ? `Pago mínimo ${money(statement.minimum_payment)} · vence ${statement.due_date}` : ''"
          />
          <AccountingStatCard label="Intereses y comisiones" :value="money(statement.interest_and_fees)" tone="warning" />
          <AccountingStatCard label="Pagos y abonos" :value="money(statement.payments_total)" tone="success" />
        </template>
        <template #secondary>
          <AccountingStatCard label="Compras" :value="money(statement.purchases_total)" tone="brand" />
        </template>
      </AccountingIndicatorGroup>
    </div>

    <!-- Bank PDF kept as documentation -->
    <div class="px-5 pb-4">
      <div class="flex flex-col sm:flex-row sm:items-center gap-2 rounded-lg border border-border-muted bg-surface-raised px-4 py-3">
        <div class="flex-1">
          <p class="text-xs font-medium text-text-muted uppercase tracking-wider">Documento del extracto</p>
          <p class="text-xs text-text-subtle mt-0.5">
            {{ statement.pdf_file_url
              ? 'PDF del banco adjunto como documentación.'
              : 'Adjunta el PDF del banco para dejarlo como documentación.' }}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <a
            v-if="statement.pdf_file_url"
            :href="statement.pdf_file_url"
            target="_blank"
            rel="noopener"
            class="text-sm font-medium text-text-brand hover:underline"
            data-testid="statement-pdf-view"
          >
            Ver PDF
          </a>
          <BaseButton
            variant="secondary"
            size="sm"
            :disabled="isUpdating"
            data-testid="statement-pdf-upload"
            @click="pdfInput?.click()"
          >
            {{ statement.pdf_file_url ? 'Reemplazar' : 'Subir PDF' }}
          </BaseButton>
          <BaseButton
            v-if="statement.pdf_file_url"
            variant="danger"
            size="sm"
            :disabled="isUpdating"
            data-testid="statement-pdf-delete"
            @click="$emit('delete-pdf')"
          >
            Eliminar
          </BaseButton>
          <input
            ref="pdfInput"
            type="file"
            accept=".pdf"
            class="hidden"
            data-testid="statement-pdf-input"
            @change="onPdfChosen"
          >
        </div>
      </div>
    </div>

    <div v-if="statement.category_totals.length" class="px-5 pb-4">
      <h3 class="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Por categoría</h3>
      <div class="space-y-1.5">
        <div
          v-for="row in statement.category_totals"
          :key="row.category"
          class="flex items-center gap-3"
        >
          <span class="text-xs text-text-muted w-44 truncate">{{ row.label }}</span>
          <div class="flex-1 h-2 rounded-full bg-surface-raised overflow-hidden">
            <div
              class="h-full rounded-full bg-primary/70"
              :style="{ width: `${categoryPercent(row)}%` }"
            />
          </div>
          <span class="text-xs font-medium text-text-default w-28 text-right">{{ money(row.total) }}</span>
        </div>
      </div>
    </div>

    <p class="px-5 pt-4 pb-2 text-xs text-text-subtle border-t border-border-muted" data-testid="statement-inline-hint">
      Haz clic en cualquier celda para editarla.
      <span v-if="isProcessed">Este extracto está finalizado: al guardar se te pedirá reabrirlo.</span>
    </p>

    <div class="overflow-x-auto">
      <table class="statement-transactions-table w-full">
        <thead>
          <tr class="border-b border-border-muted text-left">
            <th
              class="px-1.5 py-2 panel-landscape:w-14"
              aria-label="Acciones"
              data-testid="statement-tx-actions-header"
            />
            <th class="px-2.5 py-2 first:pl-4 last:pr-4 text-xs font-medium text-text-muted uppercase tracking-wider">Fecha</th>
            <th class="px-2.5 py-2 first:pl-4 last:pr-4 text-xs font-medium text-text-muted uppercase tracking-wider">Descripción</th>
            <th class="px-2.5 py-2 first:pl-4 last:pr-4 text-xs font-medium text-text-muted uppercase tracking-wider">Comercio</th>
            <th class="px-2.5 py-2 first:pl-4 last:pr-4 text-xs font-medium text-text-muted uppercase tracking-wider">Categoría</th>
            <th class="px-2.5 py-2 first:pl-4 last:pr-4 text-xs font-medium text-text-muted uppercase tracking-wider">Cuota</th>
            <th class="px-2.5 py-2 first:pl-4 last:pr-4 text-xs font-medium text-text-muted uppercase tracking-wider text-right">Valor</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-border-muted">
          <tr
            v-for="tx in statement.transactions"
            :key="tx.id"
            class="statement-transaction-row h-9 transition-colors hover:bg-surface-raised"
            :data-testid="`statement-tx-${tx.id}`"
          >
            <!-- The kebab is the row's only control besides the click-to-edit
                 cells: detail/history, the note, Editar and Eliminar live in
                 its menu. -->
            <td
              data-field="actions"
              class="px-1.5 py-1.5 text-center panel-landscape:w-14"
              @click.stop
            >
              <AccountingRowActionsButton
                :label="`Acciones de ${txLabel(tx)}`"
                :test-id="`statement-tx-actions-${tx.id}`"
                @open="actionsTx = tx"
              />
            </td>
            <td
              data-field="transaction_date"
              class="px-2.5 py-1.5 first:pl-4 last:pr-4 text-sm text-text-muted whitespace-nowrap"
              :data-testid="`tx-cell-transaction_date-${tx.id}`"
            >
              <span class="statement-mobile-label panel-landscape:hidden">Fecha</span>
              <AccountingInlineCell
                type="date"
                :value="tx.transaction_date"
                :saving="inlineSavingKey === `${tx.id}:transaction_date`"
                @save="$emit('inline-save', tx, 'transaction_date', $event)"
              >
                {{ tx.transaction_date }}
              </AccountingInlineCell>
            </td>
            <td
              data-field="raw_description"
              class="px-2.5 py-1.5 first:pl-4 last:pr-4 text-xs text-text-subtle max-w-[220px]"
              :title="tx.raw_description"
              :data-testid="`tx-cell-raw_description-${tx.id}`"
            >
              <span class="statement-mobile-label panel-landscape:hidden">Descripción</span>
              <AccountingInlineCell
                :value="tx.raw_description"
                :saving="inlineSavingKey === `${tx.id}:raw_description`"
                @save="$emit('inline-save', tx, 'raw_description', $event)"
              >
                <span class="block truncate">{{ tx.raw_description }}</span>
              </AccountingInlineCell>
            </td>
            <td
              data-field="merchant_name"
              class="px-2.5 py-1.5 first:pl-4 last:pr-4 text-sm"
              :data-testid="`tx-cell-merchant_name-${tx.id}`"
            >
              <span class="statement-mobile-label panel-landscape:hidden">Comercio</span>
              <AccountingInlineCell
                type="merchant"
                :value="tx.merchant_name || ''"
                :options="merchantOptions"
                :saving="inlineSavingKey === `${tx.id}:merchant_name`"
                @save="(value, meta) => $emit('inline-save', tx, 'merchant_name', value, meta)"
              >
                <span v-if="tx.merchant_name" class="text-text-default">{{ tx.merchant_name }}</span>
                <span
                  v-else
                  class="text-xs px-2 py-0.5 rounded-full font-medium bg-warning-soft text-warning-strong"
                >
                  Sin identificar
                </span>
              </AccountingInlineCell>
            </td>
            <td
              data-field="category"
              class="px-2.5 py-1.5 first:pl-4 last:pr-4 text-sm text-text-muted"
              :data-testid="`tx-cell-category-${tx.id}`"
            >
              <span class="statement-mobile-label panel-landscape:hidden">Categoría</span>
              <AccountingInlineCell
                type="select"
                :value="tx.category"
                :options="categoryOptions"
                :saving="inlineSavingKey === `${tx.id}:category`"
                @save="$emit('inline-save', tx, 'category', $event)"
              >
                {{ tx.category_label }}
              </AccountingInlineCell>
            </td>
            <td
              data-field="installment_label"
              class="px-2.5 py-1.5 first:pl-4 last:pr-4 text-sm text-text-muted"
              :data-testid="`tx-cell-installment_label-${tx.id}`"
            >
              <span class="statement-mobile-label panel-landscape:hidden">Cuota</span>
              <AccountingInlineCell
                type="installments"
                :value="tx.installment_label || ''"
                :saving="inlineSavingKey === `${tx.id}:installment_label`"
                @save="$emit('inline-save', tx, 'installment_label', $event)"
              >
                {{ tx.installment_label || '—' }}
              </AccountingInlineCell>
            </td>
            <td
              data-field="amount"
              class="px-2.5 py-1.5 first:pl-4 last:pr-4 text-sm font-medium text-right whitespace-nowrap"
              :class="Number(tx.amount) < 0 ? 'text-success-strong' : 'text-text-default'"
              :data-testid="`tx-cell-amount-${tx.id}`"
            >
              <span class="statement-mobile-label panel-landscape:hidden">Valor</span>
              <AccountingInlineCell
                type="money"
                align="right"
                allow-negative
                :value="tx.amount"
                :saving="inlineSavingKey === `${tx.id}:amount`"
                @save="$emit('inline-save', tx, 'amount', $event)"
              >
                {{ money(tx.amount) }}
              </AccountingInlineCell>
              <!-- Read-only companion: the FX pair is edited from the modal. -->
              <span v-if="tx.original_currency" class="block text-[10px] font-normal text-text-subtle">
                {{ tx.original_amount }} {{ tx.original_currency }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AccountingRowActionsModal
      :open="actionsTx !== null"
      :record="actionsTx"
      :title="actionsTx ? txLabel(actionsTx) : ''"
      :subtitle="txSummary(actionsTx)"
      :actions="txActions"
      test-id-prefix="statement-tx"
      @close="actionsTx = null"
      @select="runTxAction"
    />

    <EntityHistoryRecordModal
      :open="historyTx !== null"
      entity-type="statement_tx"
      :record="historyTx"
      @close="historyTx = null"
    />

    <AccountingNoteModal
      :open="noteTx !== null"
      :subtitle="txSummary(noteTx)"
      :notes="noteTx?.notes ?? ''"
      @close="noteTx = null"
    />
  </section>
</template>

<script setup>
import EntityHistoryRecordModal from '~/components/history/EntityHistoryRecordModal.vue';
import EntityHistorySection from '~/components/history/EntityHistorySection.vue';
import { computed, ref } from 'vue';
import AccountingInlineCell from '~/components/accounting/AccountingInlineCell.vue';
import AccountingNoteModal from '~/components/accounting/AccountingNoteModal.vue';
import AccountingRowActionsButton from '~/components/accounting/AccountingRowActionsButton.vue';
import AccountingRowActionsModal from '~/components/accounting/AccountingRowActionsModal.vue';
import AccountingStatCard from '~/components/accounting/AccountingStatCard.vue';
import AccountingIndicatorGroup from '~/components/accounting/AccountingIndicatorGroup.vue';
import BaseActionMenu from '~/components/base/BaseActionMenu.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import { PANEL_BREAKPOINTS } from '~/config/responsive';
import { useIsMobile } from '~/composables/useIsMobile';
import { leadingRowActions } from '~/utils/accountingRowActions';
import { formatMoney } from '~/utils/formatMoney';
import { formatDate as formatDateBase } from '~/utils/formatDate';

const props = defineProps({
  statement: { type: Object, required: true },
  isUpdating: { type: Boolean, default: false },
  /** Category choices for the inline select: [{ value, label }]. */
  categoryOptions: { type: Array, default: () => [] },
  /** Learned merchants for the inline combobox: [{ value, category, categoryLabel }]. */
  merchantOptions: { type: Array, default: () => [] },
  /** `${txId}:${field}` of the cell whose PATCH is in flight. */
  inlineSavingKey: { type: String, default: null },
});

const emit = defineEmits([
  'finalize', 'reopen', 'delete', 'edit-tx', 'delete-tx',
  'edit-header', 'add-tx', 'upload-pdf', 'delete-pdf', 'inline-save',
]);

const pdfInput = ref(null);
const { isMobile: isNarrowActions } = useIsMobile(PANEL_BREAKPOINTS.landscape - 1);

function onPdfChosen(event) {
  const file = event.target.files?.[0];
  if (file) emit('upload-pdf', file);
  event.target.value = '';
}

const isProcessed = computed(() => props.statement.status === 'processed');

const statementActions = computed(() => {
  const actions = [];
  if (!isProcessed.value) {
    actions.push(
      { action: 'edit', label: 'Editar encabezado', onClick: () => emit('edit-header') },
      { action: 'create', label: 'Agregar transacción', onClick: () => emit('add-tx') },
      { action: 'complete', label: 'Finalizar', onClick: () => emit('finalize') },
    );
  } else {
    actions.push({ action: 'restore', label: 'Reabrir', onClick: () => emit('reopen') });
  }
  actions.push({ action: 'delete', label: 'Eliminar', danger: true, onClick: () => emit('delete') });
  return actions;
});

const maxCategoryTotal = computed(() =>
  Math.max(...props.statement.category_totals.map((row) => Math.abs(Number(row.total))), 1),
);

function categoryPercent(row) {
  return Math.round((Math.abs(Number(row.total)) / maxCategoryTotal.value) * 100);
}

function money(value) {
  if (value === null || value === undefined || value === '') return '—';
  return formatMoney(Number(value));
}

function formatDate(iso) {
  return formatDateBase(iso, { fallback: '' });
}

// ── Transaction row menu ──
// Owned here, like the table: the page keeps receiving edit-tx / delete-tx.
// Eliminar exists only while the statement is still a draft.

const actionsTx = ref(null);
const historyTx = ref(null);
const noteTx = ref(null);

function txLabel(tx) {
  return tx.merchant_name || tx.raw_description || `Transacción #${tx.id}`;
}

function txSummary(tx) {
  return tx ? `${formatDate(tx.transaction_date)} · ${money(tx.amount)}` : '';
}

const txActions = computed(() => (actionsTx.value
  ? [
    ...leadingRowActions(actionsTx.value),
    { id: 'edit', action: 'edit', label: 'Editar' },
    ...(isProcessed.value
      ? []
      : [{ id: 'delete', action: 'delete', label: 'Eliminar', danger: true }]),
  ]
  : []));

const txActionHandlers = {
  history: (tx) => { historyTx.value = tx; },
  notes: (tx) => { noteTx.value = tx; },
  edit: (tx) => emit('edit-tx', tx),
  delete: (tx) => emit('delete-tx', tx),
};

function runTxAction(id, tx) {
  txActionHandlers[id]?.(tx);
}
</script>

<style scoped>
.statement-mobile-label {
  margin-bottom: 0.125rem;
  font-size: 0.6875rem;
  font-weight: 600;
  line-height: 1rem;
  color: var(--color-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

@media (max-width: 1023px) {
  .statement-transactions-table,
  .statement-transactions-table tbody {
    display: block;
    width: 100%;
  }

  .statement-transactions-table thead {
    display: none;
  }

  /* Cells are placed by field, not position: the kebab leads the card like
   * in the Bolsillo cards, then comercio and valor share its first line. */
  .statement-transaction-row {
    display: grid;
    grid-template-columns: 2.75rem minmax(0, 1fr) auto;
    gap: 0.5rem 0.75rem;
    height: auto;
    padding: 0.875rem 1rem;
  }

  .statement-transaction-row > td {
    min-width: 0;
    padding: 0;
  }

  .statement-transaction-row > [data-field="actions"] {
    grid-column: 1;
    grid-row: 1;
    align-self: start;
  }

  .statement-transaction-row > [data-field="merchant_name"] {
    grid-column: 2;
    grid-row: 1;
    font-weight: 600;
  }

  .statement-transaction-row > [data-field="amount"] {
    grid-column: 3;
    grid-row: 1;
  }

  /* The inline cell's editable area is `w-full max-w-full` with a negative
   * inline margin, so in this auto-sized track it laid out 8px narrower than it
   * measured and the amount broke across two lines. Auto width, uncapped, keeps
   * both the same. */
  .statement-transaction-row > [data-field="amount"] :deep(.touch-target) {
    width: auto;
    max-width: none;
  }

  .statement-transaction-row > [data-field="transaction_date"],
  .statement-transaction-row > [data-field="raw_description"],
  .statement-transaction-row > [data-field="category"],
  .statement-transaction-row > [data-field="installment_label"] {
    grid-column: 2 / -1;
  }
}
</style>
