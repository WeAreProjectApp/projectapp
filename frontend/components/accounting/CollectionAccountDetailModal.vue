<template>
  <BaseModal
    :model-value="open"
    kind="workspace"
    size="full"
    full-height
    title-id="collection-detail-title"
    @close="emit('close')"
  >
    <div class="flex flex-col h-full" data-testid="collection-detail-modal">
      <EntityHistorySection v-if="open && record?.id" entity-type="collection_account" :object-id="record.id" class="mx-5" />
      <!-- Header -->
      <div class="px-6 pt-6 pb-4 border-b border-border-muted">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 id="collection-detail-title" class="text-lg font-bold text-text-default">
              {{ record?.public_number || `Cuenta #${record?.id}` }}
            </h3>
            <p class="text-sm text-text-muted mt-1">
              {{ record?.billing_concept || record?.title }}
            </p>
          </div>
          <div class="flex items-center gap-3">
            <span
              class="text-xs px-2.5 py-1 rounded-full font-medium"
              :class="collectionStatusBadgeClass(record)"
              data-testid="collection-detail-status"
            >
              {{ record?.is_overdue ? 'Vencida' : record?.commercial_status_label }}
            </span>
            <span
              class="text-lg font-semibold text-text-default tabular-nums"
              data-testid="collection-detail-total"
            >
              {{ money(record?.total) }}
            </span>
          </div>
        </div>
        <div class="mt-4">
          <BaseSegmented v-model="tab" :options="TABS" />
        </div>
      </div>

      <!-- Resumen -->
      <div
        v-if="tab === 'summary'"
        class="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-6"
        data-testid="collection-detail-tab-summary"
      >
        <!-- Cliente y proyecto -->
        <section class="grid gap-4 sm:grid-cols-3">
          <div>
            <p class="text-xs uppercase tracking-wider text-text-subtle">Cliente</p>
            <p class="text-sm text-text-default mt-1" data-testid="collection-detail-client">
              {{ record?.client_display_name || 'Sin cliente' }}
            </p>
          </div>
          <div>
            <p class="text-xs uppercase tracking-wider text-text-subtle">Proyecto</p>
            <p class="text-sm mt-1" data-testid="collection-detail-project">
              <span v-if="record?.project_name" class="text-text-default">
                {{ record.project_name }}
              </span>
              <span v-else class="text-text-subtle">
                Sin proyecto — típico de un cobro por diagnóstico
              </span>
            </p>
          </div>
          <div>
            <!-- A cuenta with a zero-day term has no vencimiento, so the label
                 itself shrinks. Keeping "Emisión / Vence" over formatDate's
                 fallback printed the very dash the document avoids. -->
            <p class="text-xs uppercase tracking-wider text-text-subtle">
              {{ record?.due_date ? 'Emisión / Vence' : 'Emisión' }}
            </p>
            <p
              class="text-sm text-text-default mt-1"
              data-testid="collection-detail-dates"
            >
              {{ formatDate(record?.issue_date) }}
              <span v-if="record?.due_date">· {{ formatDate(record.due_date) }}</span>
            </p>
          </div>
        </section>

        <CollectionAccountContextEditor v-if="record?.project_id" :account-id="record.id" :project-id="record.project_id" @saved="load" />

        <!-- The document froze a name that no longer matches the relation.
             Surfacing it is the point: this is exactly the confusion the
             separate columns exist to remove. -->
        <div
          v-if="printedNameDiffers"
          class="rounded-xl bg-warning-soft text-warning-strong px-4 py-3 text-sm"
          data-testid="collection-detail-name-mismatch"
        >
          El documento se emitió a nombre de
          <strong>{{ record.customer_name }}</strong>, pero el cliente
          registrado es <strong>{{ record.client_display_name }}</strong>.
          Los documentos emitidos no se reescriben: para corregirlo, anula
          esta cuenta y emite una nueva.
        </div>

        <!-- Detalle -->
        <section v-if="detail?.items?.length">
          <h4 class="text-sm font-semibold text-text-default mb-2">Detalle</h4>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[480px] text-sm">
              <thead>
                <tr class="text-left text-xs text-text-subtle uppercase tracking-wider">
                  <th class="px-3 py-2">Descripción</th>
                  <th class="px-3 py-2">Período</th>
                  <th class="px-3 py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in detail.items"
                  :key="item.id"
                  class="border-t border-border-muted"
                  data-testid="collection-detail-item-row"
                >
                  <td class="px-3 py-2 text-text-default whitespace-pre-line">
                    {{ item.description }}
                  </td>
                  <td class="px-3 py-2 text-text-muted text-xs whitespace-nowrap">
                    <span v-if="item.period_start">
                      {{ formatDate(item.period_start) }} → {{ formatDate(item.period_end) }}
                    </span>
                    <span v-else>—</span>
                  </td>
                  <td class="px-3 py-2 text-right tabular-nums text-text-default">
                    {{ money(item.line_total) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- Ingreso vinculado -->
        <section>
          <h4 class="text-sm font-semibold text-text-default mb-2">Ingreso vinculado</h4>

          <p v-if="incomeLoading" class="text-sm text-text-subtle">Cargando el ingreso...</p>

          <p
            v-else-if="!record?.income_record_id"
            class="text-sm text-text-subtle"
            data-testid="collection-detail-no-income"
          >
            <span v-if="record?.origin === 'hosting'">
              Esta cuenta se emitió desde un hosting, así que no tiene un
              ingreso vinculado.
            </span>
            <span v-else>Esta cuenta no tiene un ingreso vinculado.</span>
          </p>

          <p
            v-else-if="incomeError"
            class="text-sm text-danger-strong"
            data-testid="collection-detail-income-error"
          >
            No se pudo cargar el ingreso vinculado.
          </p>

          <div v-else-if="income" class="space-y-4" data-testid="collection-detail-income">
            <div class="grid gap-4 sm:grid-cols-4">
              <div>
                <p class="text-xs uppercase tracking-wider text-text-subtle">Concepto</p>
                <p class="text-sm text-text-default mt-1">{{ income.concept }}</p>
              </div>
              <div>
                <p class="text-xs uppercase tracking-wider text-text-subtle">Período</p>
                <p class="text-sm text-text-default mt-1">{{ income.period_label }}</p>
              </div>
              <div>
                <p class="text-xs uppercase tracking-wider text-text-subtle">Monto</p>
                <p class="text-sm text-text-default mt-1 tabular-nums">
                  {{ money(income.total_amount) }}
                </p>
              </div>
              <div>
                <p class="text-xs uppercase tracking-wider text-text-subtle">Estado</p>
                <div class="mt-1" data-testid="collection-detail-income-status">
                  <IncomePaymentStateCell :row="income" />
                </div>
              </div>
            </div>

            <!-- El split de socios: lo que dejó de ocupar dos columnas en la
                 tabla de ingresos vive aquí. -->
            <div class="grid gap-4 sm:grid-cols-3 text-sm">
              <div>
                <span class="text-text-subtle">Gustavo:</span>
                <span class="text-text-default tabular-nums ml-1">
                  {{ money(income.gustavo_amount) }}
                </span>
              </div>
              <div>
                <span class="text-text-subtle">Carlos:</span>
                <span class="text-text-default tabular-nums ml-1">
                  {{ money(income.carlos_amount) }}
                </span>
              </div>
              <div>
                <span class="text-text-subtle">Empresa:</span>
                <span class="text-text-default tabular-nums ml-1">
                  {{ money(income.company_amount) }}
                </span>
              </div>
            </div>

            <!-- Historial de liquidación -->
            <div>
              <h5 class="text-sm font-semibold text-text-default mb-2">
                Historial de liquidación
              </h5>
              <p
                v-if="!settlements.length"
                class="text-sm text-text-subtle"
                data-testid="collection-detail-settlements-empty"
              >
                Sin liquidaciones registradas.
              </p>
              <div v-else class="overflow-x-auto">
                <table class="w-full min-w-[480px] text-sm">
                  <thead>
                    <tr class="text-left text-xs text-text-subtle uppercase tracking-wider">
                      <th class="px-3 py-2">Fecha</th>
                      <th class="px-3 py-2">Concepto</th>
                      <th class="px-3 py-2">Tipo</th>
                      <th class="px-3 py-2 text-right">Monto</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in settlements"
                      :key="`${row.kind}-${row.id}`"
                      class="border-t border-border-muted"
                      data-testid="collection-detail-settlement-row"
                    >
                      <td class="px-3 py-2 text-text-muted text-xs whitespace-nowrap">
                        {{ formatDate(row.date) }}
                      </td>
                      <td class="px-3 py-2 text-text-default">{{ row.concept }}</td>
                      <td class="px-3 py-2 text-text-muted text-xs">{{ row.label }}</td>
                      <td class="px-3 py-2 text-right tabular-nums text-text-default">
                        {{ money(row.amount) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- Documento -->
      <div
        v-else
        class="flex-1 min-h-0 flex flex-col px-6 py-5"
        data-testid="collection-detail-tab-document"
      >
        <embed
          v-if="pdfState === 'ready'"
          :src="pdfSrc"
          type="application/pdf"
          class="flex-1 min-h-0 w-full rounded-xl border border-border-default bg-surface-raised"
          data-testid="collection-detail-pdf"
        >
        <div
          v-else-if="pdfState === 'loading'"
          class="flex-1 min-h-0 flex items-center justify-center gap-2 rounded-xl border border-border-default text-sm text-text-subtle"
          data-testid="collection-detail-pdf-loading"
        >
          <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          Cargando el documento…
        </div>
        <div
          v-else
          class="flex-1 min-h-0 flex flex-col items-center justify-center gap-1 rounded-xl border border-border-default px-6 text-center"
          data-testid="collection-detail-pdf-error"
        >
          <p class="text-sm font-medium text-text-default">
            No pudimos mostrar el documento.
          </p>
          <p class="text-sm text-text-subtle">
            Revísalo con «Descargar PDF», abajo a la derecha.
          </p>
        </div>
      </div>

      <!-- Footer -->
    </div>
    <template #footer>
      <BaseModalActions>
        <!-- The optional exit, not the default: the point of this modal is
             that consulting the income no longer costs you your place. -->
        <BaseButton
          v-if="record?.income_record_id"
          variant="ghost"
          data-testid="collection-detail-go-to-income"
          @click="emit('go-to-income', record.income_record_id)"
        >
          <BaseActionIcon action="forward" /> Ver en Ingresos
        </BaseButton>
        <span v-else></span>
        <div class="flex flex-col-reverse gap-2 panel-portrait:flex-row panel-portrait:items-center">
          <BaseButton
            variant="secondary"
            data-testid="collection-detail-pdf-download"
            @click="emit('download', record)"
          >
            Descargar PDF
          </BaseButton>
          <BaseButton variant="primary" @click="emit('close')">Cerrar</BaseButton>
        </div>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import EntityHistorySection from '~/components/history/EntityHistorySection.vue';
import { computed, ref, watch } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseSegmented from '~/components/base/BaseSegmented.vue';
import IncomePaymentStateCell from '~/components/accounting/IncomePaymentStateCell.vue';
import CollectionAccountContextEditor from '~/components/accounting/billing/CollectionAccountContextEditor.vue';
import { useAccountingStore } from '~/stores/accounting';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';
import { collectionStatusBadgeClass } from '~/utils/collectionStatus';

/**
 * Everything about one cuenta de cobro in the place the operator already is:
 * the linked income with its settlement history, and the emitted document.
 *
 * Keyed on the cuenta rather than the income because a cuenta raised from a
 * hosting has no income at all — those rows used to have no inspection
 * action whatsoever.
 */
const props = defineProps({
  open: { type: Boolean, default: false },
  /** The list row. */
  record: { type: Object, default: null },
});

const emit = defineEmits(['close', 'go-to-income', 'download']);

const store = useAccountingStore();
const TABS = [
  { value: 'summary', label: 'Resumen' },
  { value: 'document', label: 'Documento' },
];

const tab = ref('summary');
const detail = ref(null);
const income = ref(null);
const incomeLoading = ref(false);
const incomeError = ref(false);

function money(value) {
  return formatMoney(Number(value ?? 0), 'COP');
}

const printedNameDiffers = computed(() => {
  const printed = (props.record?.customer_name || '').trim();
  const linked = (props.record?.client_display_name || '').trim();
  return Boolean(printed && linked && printed !== linked);
});

/** Inline so the viewer renders it instead of the browser downloading it. */
const pdfSrc = computed(() =>
  props.record
    ? `/api/accounting/collection-accounts/${props.record.id}/pdf/?inline=1`
    : '',
);

// <embed> gives no load/error events, so the viewer's state comes from
// probing the URL with fetch; probed lazily on entering the Documento tab.
const pdfState = ref('idle');

async function probePdf() {
  if (!pdfSrc.value) {
    pdfState.value = 'error';
    return;
  }
  pdfState.value = 'loading';
  try {
    const response = await fetch(pdfSrc.value, { credentials: 'same-origin' });
    pdfState.value = response.ok ? 'ready' : 'error';
  } catch {
    pdfState.value = 'error';
  }
}

watch(tab, (value) => {
  if (value === 'document' && pdfState.value === 'idle') probePdf();
});

/** Liquid children and linked deductions, oldest first, as one list. */
const settlements = computed(() => {
  const liquid = (income.value?.liquid ?? []).map((row) => ({
    id: row.id,
    kind: 'liquid',
    concept: row.concept,
    amount: row.total_amount,
    date: row.period_date,
    label: 'Liquidación',
  }));
  const deductions = (income.value?.expenses ?? []).map((row) => ({
    id: row.id,
    kind: 'deduction',
    concept: row.concept,
    amount: row.total_amount,
    date: row.period_date,
    label: row.deduction_type_label || 'Deducción',
  }));
  return [...liquid, ...deductions].sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  );
});

async function load() {
  detail.value = null;
  income.value = null;
  incomeError.value = false;
  tab.value = 'summary';
  pdfState.value = 'idle';
  if (!props.record) return;

  const documentResult = await store.fetchCollectionAccount(props.record.id);
  if (documentResult.success) detail.value = documentResult.data;

  if (!props.record.income_record_id) return;
  incomeLoading.value = true;
  const incomeResult = await store.fetchIncomeDetail(props.record.income_record_id);
  incomeLoading.value = false;
  if (incomeResult.success) {
    income.value = { ...incomeResult.data.income, ...incomeResult.data };
  } else {
    incomeError.value = true;
  }
}

watch(
  () => [props.open, props.record?.id],
  () => {
    if (props.open) load();
  },
  { immediate: true },
);
</script>
