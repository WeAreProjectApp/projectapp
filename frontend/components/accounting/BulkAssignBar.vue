<template>
  <BaseBulkActionBar
    :selected-count="selected.length"
    :outside-count="outsideCount"
    :filtered-count="filteredIds.length"
    :all-filtered-selected="allFilteredSelected"
    :actions="actionItems"
    :busy="busy"
    :testid-prefix="testidPrefix"
    @select-all="selectAllFiltered"
    @clear="clearSelection"
  >
    <template v-if="settleEnabled" #selection-summary>
      <span class="flex flex-wrap gap-x-3 gap-y-1 text-xs tabular-nums text-text-muted">
        <span :data-testid="`${testidPrefix}-selected-total`">Valor total seleccionado: {{ formatMoney(selectionTotals.total / 100, 'COP') }}</span>
        <span :data-testid="`${testidPrefix}-selected-pending`">Saldo pendiente seleccionado: {{ formatMoney(selectionTotals.pending / 100, 'COP') }}</span>
      </span>
    </template>
  </BaseBulkActionBar>

  <BulkAssignModal
    :open="assignTarget !== null"
    :target="assignTarget || 'client'"
    :rows="rows"
    :selected-ids="selected"
    :entity="entity"
    :record-label="recordLabel"
    :testid-prefix="testidPrefix"
    :busy="busy"
    @close="assignTarget = null"
    @submit="onAssignSubmit"
  />

  <ConfirmModal
    v-model="confirmState.open"
    size="lg"
    :title="confirmState.title"
    :message="confirmState.message"
    :confirm-text="confirmState.confirmText"
    :cancel-text="confirmState.cancelText"
    :variant="confirmState.variant"
    @confirm="handleConfirmed"
    @cancel="handleCancelled"
  >
    <ClientBulkAssignSummary
      v-if="pendingPlan && pendingPlanKind === 'client'"
      :plan="pendingPlan"
      :record-label="recordLabel"
    />
    <ProjectBulkAssignSummary
      v-else-if="pendingPlan"
      :plan="pendingPlan"
      :record-label="recordLabel"
    />
  </ConfirmModal>
</template>

<script setup>
import { computed, ref } from 'vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import BulkAssignModal from '~/components/accounting/BulkAssignModal.vue';
import ClientBulkAssignSummary from '~/components/accounting/ClientBulkAssignSummary.vue';
import ProjectBulkAssignSummary from '~/components/accounting/ProjectBulkAssignSummary.vue';
import BaseBulkActionBar from '~/components/base/BaseBulkActionBar.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { isSettleEligible } from '~/utils/settleAllocation';
import { formatMoney } from '~/utils/formatMoney';
import { buildAssignmentPlan, describeAssignmentPlan } from '~/utils/clientAssignment';
import {
  buildProjectAssignmentPlan,
  describeProjectAssignmentPlan,
} from '~/utils/projectAssignment';

/**
 * Bulk actions over the current selection, for the accounting tables.
 *
 * The bar itself holds only the selection count and ONE control: everything
 * it can do hangs off an actions menu. It used to lay all six controls out at
 * once — a Cliente/Proyecto toggle, a picker, and four buttons — which mixed
 * linking a record with moving money in the same row and became unreadable.
 * Assigning now opens BulkAssignModal (picker + plan + confirm); unlinking,
 * which needs no target, still goes straight to the confirmation; the abono
 * opens its own modal on the page.
 *
 * Shared between hostings and incomes: the two pages used to hold a
 * byte-identical copy of this block, so a fix in one silently left the
 * other behind.
 *
 * Either way the operator confirms against a breakdown of what changes and a
 * list of every record involved — this is a mass edit, and the scope has to
 * be visible before it runs, not after.
 */
const props = defineProps({
  /**
   * FULL record list from the store, not the filtered rows: the selection
   * survives filter and page changes, so it can hold off-screen ids.
   */
  rows: { type: Array, default: () => [] },
  /** Selected row ids (v-model:selected). */
  selected: { type: Array, default: () => [] },
  /** Ids currently passing the filters, for "seleccionar los N filtrados". */
  filteredIds: { type: Array, default: () => [] },
  /** `{ singular, plural }` noun for the copy ('hosting' / 'hostings'). */
  entity: { type: Object, required: true },
  /** data-testid prefix, kept per page ('hostings' / 'incomes'). */
  testidPrefix: { type: String, required: true },
  /** (row) => the row's identity in the confirmation list. */
  recordLabel: { type: Function, required: true },
  /** Store mutation in flight: blocks every action. */
  busy: { type: Boolean, default: false },
  /** Offer the Proyecto actions (pages whose rows carry a project link). */
  projectEnabled: { type: Boolean, default: false },
  /** Offer "Registrar abono" (incomes only: bulk-settle needs expected rows). */
  settleEnabled: { type: Boolean, default: false },
});

const emit = defineEmits([
  'update:selected', 'submit', 'submit-project', 'submit-settle',
]);

const { confirmState, requestConfirm, handleConfirmed, handleCancelled } =
  useConfirmModal();

/** 'client' | 'project' while the assign modal is open, null when closed. */
const assignTarget = ref(null);
const pendingPlan = ref(null);
const pendingPlanKind = ref('client');

const selectionTotals = computed(() => {
  const selected = new Set(props.selected);
  return props.rows.reduce((totals, row) => {
    if (!selected.has(row.id)) return totals;
    totals.total += Math.round(Number(row.total_amount || 0) * 100);
    if (row.kind === 'expected') {
      totals.pending += Math.max(0, Math.round(Number(row.pending_amount || 0) * 100));
    }
    return totals;
  }, { total: 0, pending: 0 });
});

const allFilteredSelected = computed(
  () => props.filteredIds.length > 0
    && props.filteredIds.every((id) => props.selected.includes(id)),
);

/** Selected rows the active filters no longer show — the action still runs on them. */
const outsideCount = computed(() => {
  const filtered = new Set(props.filteredIds);
  return props.selected.filter((id) => !filtered.has(id)).length;
});

const unlinkPlan = computed(() => buildAssignmentPlan({
  rows: props.rows,
  selectedIds: props.selected,
  mode: 'unlink',
}));

const canUnlink = computed(() => unlinkPlan.value.toUnlink.length > 0);

const unlinkProjectPlan = computed(() => buildProjectAssignmentPlan({
  rows: props.rows,
  selectedIds: props.selected,
  mode: 'unlink',
}));

const canUnlinkProject = computed(
  () => unlinkProjectPlan.value.toUnlink.length > 0,
);

/** Selected ids that can take an abono: company expected rows with pending. */
const settleEligibleIds = computed(() => {
  if (!props.settleEnabled) return [];
  const byId = new Map(props.rows.map((row) => [row.id, row]));
  return props.selected.filter((id) => isSettleEligible(byId.get(id)));
});

/** Empty string = the abono action is live. */
const settleBlockedReason = computed(() => {
  if (!props.settleEnabled || settleEligibleIds.value.length > 0) return '';
  return 'Para liquidar se necesitan ingresos esperados de la empresa con saldo pendiente.';
});

/**
 * Lo que se puede hacer con la selección, agrupado: primero vincular, después
 * cobrar. Los divisores se insertan CON su grupo, nunca sueltos — Hostings no
 * habilita el abono, así que un divisor incondicional al final le dejaría una
 * línea separando la nada.
 *
 * "Registrar abono" siempre está presente cuando la página lo habilita y sólo
 * cambia `disabled`, para que el menú no cambie de alto entre selecciones; su
 * razón viaja en `description`, porque un ítem deshabilitado de Headless UI no
 * toma foco ni recibe puntero y un tooltip encima sería inalcanzable.
 */
const actionItems = computed(() => {
  const items = [
    {
      action: 'add-user',
      label: 'Asignar cliente',
      onClick: () => { assignTarget.value = 'client'; },
    },
  ];
  if (props.projectEnabled) {
    items.push({
      action: 'link',
      label: 'Asignar proyecto',
      onClick: () => { assignTarget.value = 'project'; },
    });
  }

  const unlinks = [];
  // Desvincular sólo existe mientras haya algo que desvincular, así que su
  // presencia ya dice que la selección tiene cliente (o proyecto).
  if (canUnlink.value) {
    unlinks.push({
      action: 'unlink',
      label: 'Desvincular cliente',
      danger: true,
      onClick: () => confirmAndSubmit(unlinkPlan.value),
    });
  }
  if (props.projectEnabled && canUnlinkProject.value) {
    unlinks.push({
      action: 'unlink',
      label: 'Quitar proyecto',
      danger: true,
      onClick: () => confirmAndSubmitProject(unlinkProjectPlan.value),
    });
  }
  if (unlinks.length) items.push({ divider: true }, ...unlinks);

  if (props.settleEnabled) {
    items.push({ divider: true }, {
      action: 'settle',
      label: 'Liquidar',
      disabled: settleEligibleIds.value.length === 0,
      description: settleBlockedReason.value,
      onClick: emitSettle,
    });
  }
  return items;
});

function selectAllFiltered() {
  emit('update:selected', [...props.filteredIds]);
}

/**
 * Sin ConfirmModal propio: el modal de abono lista cada ingreso y los
 * totales antes de escribir nada — es la misma garantía que el plan de los
 * assigns, con la distribución además. Sólo viajan los elegibles; el modal
 * anuncia cuántos seleccionados quedaron fuera.
 */
function emitSettle() {
  if (settleEligibleIds.value.length === 0) return;
  emit('submit-settle', {
    ids: settleEligibleIds.value,
    excludedCount: props.selected.length - settleEligibleIds.value.length,
  });
}

function clearSelection() {
  emit('update:selected', []);
}

/**
 * The assign modal already showed the plan and built the payload; the bar
 * only routes it to the right emit. Keyed on the payload's own shape rather
 * than on `assignTarget`, which the close that follows is about to clear.
 */
function onAssignSubmit(payload) {
  emit(Object.hasOwn(payload, 'project') ? 'submit-project' : 'submit', payload);
}

/**
 * Show the plan, and on confirmation hand the parent only the rows that
 * actually change — the same ones the modal listed, so the count reported
 * afterwards matches what was promised.
 */
async function confirmAndSubmit(plan) {
  if (plan.affected.length === 0) return;
  // Kept after the await on purpose: clearing it here would blank the body
  // while the dialog is still transitioning out.
  pendingPlan.value = plan;
  pendingPlanKind.value = 'client';
  const copy = describeAssignmentPlan(plan, { entity: props.entity });
  const confirmed = await requestConfirm({ ...copy, cancelText: 'Cancelar' });
  if (!confirmed) return;
  emit('submit', {
    ids: plan.affected.map((row) => row.id),
    client: plan.mode === 'unlink' ? null : plan.targetClientId,
    mode: plan.mode,
    plan,
  });
}

/** Project twin of `confirmAndSubmit`, emitting `submit-project`. */
async function confirmAndSubmitProject(plan) {
  if (plan.affected.length === 0) return;
  pendingPlan.value = plan;
  pendingPlanKind.value = 'project';
  const copy = describeProjectAssignmentPlan(plan, { entity: props.entity });
  const confirmed = await requestConfirm({ ...copy, cancelText: 'Cancelar' });
  if (!confirmed) return;
  emit('submit-project', {
    ids: plan.affected.map((row) => row.id),
    project: plan.mode === 'unlink' ? null : plan.targetProjectId,
    mode: plan.mode,
    plan,
  });
}
</script>
