<template>
  <BasePageShell>
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

    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Extractos de tarjeta</h1>
        <p class="text-sm text-text-subtle mt-1">
          Libro analítico mensual de la tarjeta de crédito. Se alimenta desde el
          chat del asistente (conector contable) adjuntando el extracto del banco.
        </p>
      </div>
      <BaseButton
        variant="secondary"
        size="md"
        class="w-full panel-portrait:w-auto"
        data-testid="statements-copy-prompt"
        @click="copyKickoffPrompt"
      >
        Copiar prompt
      </BaseButton>
    </div>

    <AccountingSubnav active="statements" />

    <!-- Year + card filters -->
    <div class="flex flex-wrap items-center gap-3 mb-6">
      <BaseSegmented v-model="selectedYear" :options="yearOptions" />
      <BaseSelect
        v-if="cardOptions.length > 1"
        v-model="selectedCard"
        :options="cardOptions"
        class="w-full panel-portrait:w-56"
        data-testid="statements-card-filter"
      />
    </div>

    <!-- Loading -->
    <div v-if="store.isLoading && !status" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-focus-ring/30 border-t-focus-ring rounded-full animate-spin" />
    </div>

    <template v-else-if="status">
      <StatementMonthGrid
        :months="status.months"
        :selected-id="selectedStatementId"
        class="mb-6"
        @select="selectStatement"
      />

      <StatementDetail
        v-if="detail"
        :statement="detail"
        :is-updating="store.isUpdating"
        :category-options="categoryOptions"
        :merchant-options="merchantOptions"
        :inline-saving-key="inlineSavingKey"
        class="mb-6"
        @finalize="handleFinalize"
        @reopen="handleReopen"
        @delete="handleDeleteStatement"
        @edit-tx="openTxModal"
        @delete-tx="handleDeleteTx"
        @edit-header="headerModalOpen = true"
        @add-tx="openCreateTxModal"
        @upload-pdf="handleUploadPdf"
        @delete-pdf="handleDeletePdf"
        @inline-save="saveTxInline"
      />

      <!-- Learned merchant aliases -->
      <button
        type="button"
        class="flex items-center gap-2 text-sm font-medium text-text-default hover:text-text-brand transition-colors"
        :aria-expanded="aliasesOpen"
        aria-controls="statement-aliases"
        data-testid="statements-aliases-toggle"
        @click="aliasesOpen = !aliasesOpen"
      >
        <BaseActionIcon :action="aliasesOpen ? 'collapse' : 'expand'" />
        Comercios aprendidos ({{ store.merchantAliases.length }})
      </button>
      <BaseCollapse id="statement-aliases" :open="aliasesOpen">
        <StatementAliasTable
          :aliases="store.merchantAliases"
          :category-options="categoryOptions"
          :merchant-options="merchantOptions"
          :inline-saving-key="aliasSavingKey"
          @inline-save="saveAliasInline"
          @delete="handleDeleteAlias"
        />
      </BaseCollapse>
    </template>

    <AccountingErrorState v-else @retry="loadStatus" />

    <!-- Statement header edit modal -->
    <StatementHeaderFormModal
      :open="headerModalOpen"
      :statement="detail"
      :saving="store.isUpdating"
      @close="headerModalOpen = false"
      @submit="saveHeader"
    />

    <!-- Transaction create/edit modal -->
    <BaseModal v-model="txModalOpen" kind="form" padding="md">
      <h3 class="text-base font-medium text-text-default mb-4">
        {{ txForm.id ? 'Editar transacción' : 'Agregar transacción' }}
      </h3>
      <div class="space-y-3">
        <BaseFormField label="Fecha" required>
          <BaseInput v-model="txForm.transaction_date" type="date" data-testid="tx-date-input" />
        </BaseFormField>
        <BaseFormField label="Descripción del extracto" required>
          <BaseInput v-model="txForm.raw_description" data-testid="tx-description-input" />
        </BaseFormField>
        <BaseFormField label="Comercio">
          <AccountingMerchantInput
            v-model="txForm.merchant_name"
            :options="merchantOptions"
            test-id="tx-merchant-input"
          />
        </BaseFormField>
        <BaseFormField label="Categoría">
          <BaseSelect v-model="txForm.category" :options="categoryOptions" />
        </BaseFormField>
        <BaseFormField label="Cuota">
          <div class="flex items-center gap-2">
            <BaseInput
              v-model="txForm.installment_number"
              type="number"
              min="1"
              class="w-20"
              placeholder="Cuota"
              data-testid="tx-installment-number"
            />
            <span class="text-text-subtle">de</span>
            <BaseInput
              v-model="txForm.installments_total"
              type="number"
              min="1"
              class="w-20"
              placeholder="Total"
              data-testid="tx-installment-total"
            />
          </div>
        </BaseFormField>
        <BaseFormField label="Valor (COP)">
          <BaseCurrencyInput v-model="txForm.amount" allow-negative data-testid="tx-amount-input" />
        </BaseFormField>
        <BaseFormField label="Notas">
          <BaseTextarea v-model="txForm.notes" :rows="2" />
        </BaseFormField>
      </div>
      <template #footer>
        <BaseModalActions>
          <BaseButton variant="ghost" size="sm" @click="txModalOpen = false">Cancelar</BaseButton>
          <BaseButton
            variant="primary"
            size="sm"
            :disabled="store.isUpdating"
            data-testid="tx-save"
            @click="saveTx"
          >
            Guardar
          </BaseButton>
        </BaseModalActions>
      </template>
    </BaseModal>
  </BasePageShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue';
import AccountingErrorState from '~/components/accounting/AccountingErrorState.vue';
import AccountingMerchantInput from '~/components/accounting/AccountingMerchantInput.vue';
import AccountingSubnav from '~/components/accounting/AccountingSubnav.vue';
import StatementAliasTable from '~/components/accounting/StatementAliasTable.vue';
import StatementDetail from '~/components/accounting/StatementDetail.vue';
import StatementHeaderFormModal from '~/components/accounting/StatementHeaderFormModal.vue';
import StatementMonthGrid from '~/components/accounting/StatementMonthGrid.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseCollapse from '~/components/base/BaseCollapse.vue';
import BaseCurrencyInput from '~/components/base/BaseCurrencyInput.vue';
import BaseFormField from '~/components/base/BaseFormField.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseModal from '~/components/base/BaseModal.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import BaseSelect from '~/components/base/BaseSelect.vue';
import BaseTextarea from '~/components/base/BaseTextarea.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useAccountingStore } from '~/stores/accounting';

definePageMeta({ layout: 'admin', middleware: ['admin-auth', 'superuser-only'] });

const KICKOFF_PROMPT =
  'Adjunto el extracto de mi tarjeta de crédito. Procésalo con las herramientas '
  + 'del conector de contabilidad: empieza llamando get_statement_instructions '
  + 'y sigue el flujo completo (verificar mes, extraer, resolver comercios '
  + 'conmigo, guardar y consolidar).';

const CATEGORY_OPTIONS = [
  { value: 'software', label: 'Software y suscripciones' },
  { value: 'advertising', label: 'Publicidad' },
  { value: 'fuel', label: 'Gasolina' },
  { value: 'groceries', label: 'Supermercado' },
  { value: 'restaurants', label: 'Restaurantes' },
  { value: 'utilities', label: 'Servicios' },
  { value: 'travel', label: 'Viajes' },
  { value: 'shopping', label: 'Compras' },
  { value: 'other', label: 'Otros' },
];

const store = useAccountingStore();
const notify = usePanelNotify();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();

const currentYear = new Date().getFullYear();
const selectedYear = ref(currentYear);
const selectedCard = ref('');
const selectedStatementId = ref(null);
const aliasesOpen = ref(false);
const categoryOptions = CATEGORY_OPTIONS;

const status = computed(() => store.statementStatus);
const detail = computed(() => store.statementDetail);

// Year range comes from the backend (card catalog `statements_since`);
// before the first load it falls back to the current year only.
const yearOptions = computed(() =>
  (status.value?.year_options || [currentYear]).map((year) => ({
    value: year,
    label: String(year),
    testId: `statements-year-${year}`,
  })),
);

watch(yearOptions, (options) => {
  if (!options.some((option) => option.value === selectedYear.value)) {
    selectedYear.value = options[options.length - 1].value;
  }
});

const cardOptions = computed(() => [
  { value: '', label: 'Todas las tarjetas' },
  ...(status.value?.cards || []).map((card) => ({ value: card, label: card })),
]);

// Learned merchants feed the inline combobox. Several descriptors can map to
// the same merchant, so the list is deduplicated by name.
const merchantOptions = computed(() => {
  const byName = new Map();
  store.merchantAliases.forEach((alias) => {
    if (!alias.merchant_name || byName.has(alias.merchant_name)) return;
    byName.set(alias.merchant_name, {
      value: alias.merchant_name,
      category: alias.default_category || null,
      categoryLabel: alias.default_category_label || '',
    });
  });
  return [...byName.values()].sort((a, b) => a.value.localeCompare(b.value, 'es'));
});

async function loadStatus() {
  await store.fetchStatementStatus(selectedYear.value, selectedCard.value);
  if (
    selectedStatementId.value
    && !statementVisible(selectedStatementId.value)
  ) {
    selectedStatementId.value = null;
    store.statementDetail = null;
  }
}

function statementVisible(id) {
  return (status.value?.months || []).some((month) =>
    month.statements.some((statement) => statement.id === id),
  );
}

async function loadAll() {
  await Promise.all([
    loadStatus(),
    store.fetchRecords('merchantAliases'),
  ]);
  if (selectedStatementId.value) {
    await store.fetchStatementDetail(selectedStatementId.value);
  }
}

onMounted(loadAll);
usePanelRefresh(loadAll);
watch([selectedYear, selectedCard], loadStatus);

async function selectStatement(id) {
  selectedStatementId.value = id;
  const result = await store.fetchStatementDetail(id);
  if (!result.success) notify.error('No se pudo cargar el extracto.');
}

async function handleFinalize() {
  const result = await store.finalizeStatement(detail.value.id);
  if (result.success) {
    notify.success('Extracto consolidado.');
    await loadStatus();
    return;
  }
  const message = result.message || 'No se pudo finalizar el extracto.';
  if (message.includes('diferencia')) {
    requestConfirm({
      title: 'Los totales no cuadran',
      message: `${message} ¿Cerrar de todas formas?`,
      variant: 'danger',
      confirmText: 'Forzar cierre',
      onConfirm: async () => {
        const forced = await store.finalizeStatement(detail.value.id, true);
        if (forced.success) {
          notify.success('Extracto consolidado (forzado).');
          await loadStatus();
        } else {
          notify.error('No se pudo finalizar el extracto.');
        }
      },
    });
  } else {
    notify.error(message);
  }
}

async function handleReopen() {
  const result = await store.reopenStatement(detail.value.id);
  if (result.success) {
    notify.success('Extracto reabierto.');
    await loadStatus();
  } else {
    notify.error('No se pudo reabrir el extracto.');
  }
}

function handleDeleteStatement() {
  const statement = detail.value;
  requestConfirm({
    title: 'Eliminar extracto',
    message: `¿Eliminar el extracto de ${statement.card_name} (${statement.period_label}) con sus ${statement.transactions.length} transacciones?`,
    variant: 'danger',
    confirmText: 'Eliminar',
    onConfirm: async () => {
      const result = await store.deleteRecord('statements', statement.id);
      if (result.success) {
        notify.success('Extracto eliminado.');
        selectedStatementId.value = null;
        store.statementDetail = null;
        await loadStatus();
      } else {
        notify.error('No se pudo eliminar el extracto.');
      }
    },
  });
}

// ── Statement header editing ──

const headerModalOpen = ref(false);

async function saveHeader(payload) {
  const result = await store.updateRecord('statements', detail.value.id, payload);
  if (result.success) {
    headerModalOpen.value = false;
    notify.success('Encabezado actualizado.');
    await Promise.all([
      store.fetchStatementDetail(detail.value.id),
      loadStatus(),
    ]);
  } else {
    notify.error(result.message || 'No se pudo actualizar el encabezado.');
  }
}

// ── Statement PDF ──

async function handleUploadPdf(file) {
  const result = await store.uploadStatementPdf(detail.value.id, file);
  if (result.success) {
    notify.success('PDF del extracto guardado.');
  } else {
    notify.error(result.message || 'No se pudo subir el PDF.');
  }
}

function handleDeletePdf() {
  requestConfirm({
    title: 'Eliminar PDF del extracto',
    message: '¿Eliminar el PDF adjunto? El archivo se borra del servidor.',
    variant: 'danger',
    confirmText: 'Eliminar',
    onConfirm: async () => {
      const result = await store.deleteStatementPdf(detail.value.id);
      if (result.success) {
        notify.success('PDF eliminado.');
      } else {
        notify.error(result.message || 'No se pudo eliminar el PDF.');
      }
    },
  });
}

// ── Transaction editing ──

const txModalOpen = ref(false);
const txForm = reactive({
  id: null,
  transaction_date: '',
  raw_description: '',
  merchant_name: '',
  category: 'other',
  installment_number: '',
  installments_total: '',
  amount: null,
  notes: '',
});

async function openTxModal(tx) {
  // Ask before opening rather than on save: stacking a confirm on top of the
  // modal reads badly, and the answer decides whether editing is possible.
  if (!await ensureDraft()) return;
  txForm.id = tx.id;
  txForm.transaction_date = tx.transaction_date;
  txForm.raw_description = tx.raw_description;
  txForm.merchant_name = tx.merchant_name;
  txForm.category = tx.category;
  txForm.installment_number = tx.installment_number ?? '';
  txForm.installments_total = tx.installments_total ?? '';
  txForm.amount = tx.amount === null || tx.amount === '' ? null : Number(tx.amount);
  txForm.notes = tx.notes || '';
  txModalOpen.value = true;
}

function openCreateTxModal() {
  txForm.id = null;
  txForm.transaction_date = new Date().toISOString().slice(0, 10);
  txForm.raw_description = '';
  txForm.merchant_name = '';
  txForm.category = 'other';
  txForm.installment_number = '';
  txForm.installments_total = '';
  txForm.amount = null;
  txForm.notes = '';
  txModalOpen.value = true;
}

async function saveTx() {
  if (!txForm.transaction_date || !txForm.raw_description) {
    notify.error('La fecha y la descripción son obligatorias.');
    return;
  }
  const number = Number(txForm.installment_number) || null;
  const total = Number(txForm.installments_total) || null;
  if (Boolean(number) !== Boolean(total) || (number && total && number > total)) {
    notify.error('Cuota inválida. Indica ambos números y que la cuota no supere el total.');
    return;
  }
  const payload = {
    transaction_date: txForm.transaction_date,
    raw_description: txForm.raw_description,
    merchant_name: txForm.merchant_name,
    category: txForm.category,
    installment_number: number,
    installments_total: total,
    amount: txForm.amount,
    notes: txForm.notes,
    is_identified: Boolean(txForm.merchant_name),
  };
  if (!txForm.id) {
    const created = await store.createStatementTransactions(detail.value.id, [payload]);
    if (created.success) {
      txModalOpen.value = false;
      notify.success('Transacción agregada.');
    } else {
      notify.error(created.message || 'No se pudo agregar la transacción.');
    }
    return;
  }
  const result = await store.updateStatementTransaction(
    detail.value.id, txForm.id, payload,
  );
  if (result.success) {
    txModalOpen.value = false;
    notify.success('Transacción actualizada.');
    await store.fetchStatementDetail(detail.value.id);
  } else {
    notify.error(result.message || 'No se pudo actualizar la transacción.');
  }
}

// ── Inline row editing ──

const inlineSavingKey = ref(null);

function inlinePayload(field, value, meta, tx) {
  if (field === 'merchant_name') {
    // Clearing the name also drops the identified flag (badge returns).
    const payload = { merchant_name: value, is_identified: Boolean(value) };
    // A merchant picked from the catalog brings its default category, but it
    // must not overwrite a category the row already got right.
    if (meta?.category && tx.category === 'other') payload.category = meta.category;
    return payload;
  }
  if (field === 'installment_label') {
    // The installments cell emits `null` to clear, or a { number, total } pair.
    if (value === null) return { installment_number: null, installments_total: null };
    const { number, total } = value;
    if (!number || !total || number > total) return null;
    return { installment_number: number, installments_total: total };
  }
  return { [field]: value };
}

async function saveTxInline(tx, field, value, meta) {
  if (field === 'raw_description' && !String(value).trim()) {
    notify.error('La descripción no puede quedar vacía.');
    return;
  }
  const payload = inlinePayload(field, value, meta, tx);
  if (!payload) {
    notify.error('Cuota inválida. Indica ambos números y que la cuota no supere el total.');
    return;
  }
  if (!await ensureDraft()) return;
  await applyTxInline(tx, field, payload);
}

/**
 * A processed statement is reconciled against the bank, so the backend refuses
 * edits. Reopening is the honest way through — the owner just has to finalize
 * it again afterwards. Returns false when the edit must not proceed.
 */
async function ensureDraft() {
  if (detail.value.status !== 'processed') return true;
  const confirmed = await requestConfirm({
    title: 'Extracto finalizado',
    message: 'Este extracto ya está consolidado. ¿Reabrirlo para corregirlo? '
      + 'Recuerda finalizarlo de nuevo cuando termines.',
    confirmText: 'Reabrir y editar',
  });
  if (!confirmed) return false;
  const reopened = await store.reopenStatement(detail.value.id);
  if (!reopened.success) {
    notify.error(reopened.message || 'No se pudo reabrir el extracto.');
    return false;
  }
  await loadStatus();
  return true;
}

async function applyTxInline(tx, field, payload) {
  inlineSavingKey.value = `${tx.id}:${field}`;
  const result = await store.updateStatementTransaction(detail.value.id, tx.id, payload);
  inlineSavingKey.value = null;
  if (!result.success) {
    notify.error(result.message || 'No se pudo actualizar la transacción.');
    return;
  }
  notify.success('Transacción actualizada.');
  // Header sums and category totals are server-computed.
  await store.fetchStatementDetail(detail.value.id);
  if (field === 'merchant_name' && payload.merchant_name) {
    await offerAliasLearning(tx, payload);
  }
}

/**
 * A hand-typed merchant is worth remembering: the same descriptor will come
 * back every month, and the alias saves the correction from scratch.
 */
async function offerAliasLearning(tx, payload) {
  const merchantName = payload.merchant_name;
  const confirmed = await requestConfirm({
    title: 'Recordar este comercio',
    message: `¿Recordar "${tx.raw_description}" como ${merchantName} para los próximos extractos?`,
    confirmText: 'Recordar',
    cancelText: 'No, solo esta vez',
  });
  if (!confirmed) return;
  const result = await store.learnMerchantAlias({
    raw_description: tx.raw_description,
    merchant_name: merchantName,
    category: payload.category || tx.category,
    statement_id: detail.value.id,
  });
  if (!result.success) {
    notify.error(result.message || 'No se pudo guardar el comercio.');
    return;
  }
  const applied = result.data?.applied || 0;
  notify.success(
    applied
      ? `Comercio recordado y aplicado a ${applied} transacción(es) más.`
      : 'Comercio recordado.',
  );
  if (applied) await store.fetchStatementDetail(detail.value.id);
}

function handleDeleteTx(tx) {
  requestConfirm({
    title: 'Eliminar transacción',
    message: `¿Eliminar "${tx.merchant_name || tx.raw_description}"?`,
    variant: 'danger',
    confirmText: 'Eliminar',
    onConfirm: async () => {
      const result = await store.deleteStatementTransaction(detail.value.id, tx.id);
      if (result.success) {
        notify.success('Transacción eliminada.');
        await store.fetchStatementDetail(detail.value.id);
      } else {
        notify.error('No se pudo eliminar la transacción.');
      }
    },
  });
}

// ── Aliases ──

const aliasSavingKey = ref(null);

const ALIAS_REQUIRED_LABELS = {
  match_text: 'El texto a mapear no puede quedar vacío.',
  merchant_name: 'El comercio no puede quedar vacío.',
};

/**
 * Aliases are a global catalogue, so unlike the transaction cells this skips
 * `ensureDraft()` — the open statement's status has no say over it. The PATCH
 * response replaces the record in the store, which is what brings back the
 * server-normalized `match_text` and the fresh category label; `merchantOptions`
 * derives from that same list, so the transaction combobox follows along.
 */
async function saveAliasInline(alias, field, value) {
  if (ALIAS_REQUIRED_LABELS[field] && !String(value).trim()) {
    notify.error(ALIAS_REQUIRED_LABELS[field]);
    return;
  }
  aliasSavingKey.value = `${alias.id}:${field}`;
  const result = await store.updateRecord('merchantAliases', alias.id, { [field]: value });
  aliasSavingKey.value = null;
  if (result.success) {
    notify.success('Comercio actualizado.');
  } else {
    notify.error(result.message || 'No se pudo actualizar el comercio.');
  }
}

function handleDeleteAlias(alias) {
  requestConfirm({
    title: 'Eliminar alias',
    message: `¿Eliminar el alias "${alias.match_text}" → ${alias.merchant_name}? Los próximos extractos dejarán de resolverlo automáticamente.`,
    variant: 'danger',
    confirmText: 'Eliminar',
    onConfirm: async () => {
      const result = await store.deleteRecord('merchantAliases', alias.id);
      if (result.success) {
        notify.success('Alias eliminado.');
      } else {
        notify.error('No se pudo eliminar el alias.');
      }
    },
  });
}

// ── Kick-off prompt ──

async function copyKickoffPrompt() {
  try {
    await navigator.clipboard.writeText(KICKOFF_PROMPT);
    notify.success('Prompt copiado. Pégalo en el chat del asistente junto con el PDF del extracto.');
  } catch {
    notify.error('No se pudo copiar el prompt.');
  }
}
</script>
