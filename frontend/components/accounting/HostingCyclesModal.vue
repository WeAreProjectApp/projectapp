<template>
  <BaseModal :model-value="open" kind="detail" title-id="hosting-cycles-title" @close="emit('close')">
    <div class="px-6 pt-6 pb-2">
      <h3 id="hosting-cycles-title" class="text-lg font-bold text-text-default">
        Ciclos de pago — {{ record?.display_label || record?.client_name }}
      </h3>
      <p class="text-sm text-text-muted mt-1">
        El total pagado del hosting es la suma de este histórico
        ({{ formatMoney(record?.total_paid ?? 0, 'COP') }} en
        {{ record?.cycles_count ?? 0 }} ciclo{{ (record?.cycles_count ?? 0) === 1 ? '' : 's' }}).
      </p>
    </div>

    <div class="px-6 py-4 space-y-5">
      <HostingCycleReceiptForm v-if="open && record" :record="record" @changed="paymentChanged"
        @next-income="emit('next-income', $event)" />

      <!-- History -->
      <div>
        <p class="text-xs font-semibold text-text-subtle uppercase tracking-wider mb-2">Histórico</p>
        <p v-if="loading" class="text-sm text-text-subtle py-4">Cargando ciclos...</p>
        <p v-else-if="cycles.length === 0" class="text-sm text-text-subtle py-4">
          Sin ciclos registrados todavía.
        </p>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs text-text-subtle uppercase tracking-wider">
                <th class="px-3 py-2">Pago</th>
                <th class="px-3 py-2">Modalidad</th>
                <th class="px-3 py-2">Período</th>
                <th class="px-3 py-2 text-right">Monto</th>
                <th class="px-3 py-2 text-right"></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="cycle in cycles"
                :key="cycle.id"
                class="border-t border-border-muted"
              >
                <td class="px-3 py-2 whitespace-nowrap">{{ cycle.paid_at }}</td>
                <td class="px-3 py-2">
                  {{ cycle.modality_label }}
                  <span
                    v-if="cycle.is_backfill"
                    class="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-surface-raised text-text-muted"
                    :title="cycle.notes"
                  >
                    histórico × {{ cycle.cycles_represented }}
                  </span>
                </td>
                <td class="px-3 py-2 text-text-muted text-xs whitespace-nowrap">
                  {{ cycle.period_from || '—' }} → {{ cycle.period_to || '—' }}
                </td>
                <td class="px-3 py-2 text-right tabular-nums">
                  {{ formatMoney(cycle.amount, 'COP') }}
                </td>
                <td class="px-3 py-2 text-right">
                  <BaseActionButton
                    action="delete"
                    label="Eliminar ciclo"
                    variant="danger-ghost"
                    size="sm"
                    :disabled="Boolean(cycle.receipt_allocation_id)"
                    :disabled-reason="cycle.receipt_allocation_id ? $t('hostingBilling.correctReceipt') : ''"
                    @click="askDelete(cycle)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>

    <ConfirmModal
      v-model="deleteConfirmOpen"
      title="Eliminar ciclo"
      :message="deleteMessage"
      confirm-text="Eliminar"
      cancel-text="Cancelar"
      variant="danger"
      @confirm="confirmDelete"
      @cancel="cycleToDelete = null"
    />
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="secondary" @click="emit('close')">Cerrar</BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import HostingCycleReceiptForm from './billing/HostingCycleReceiptForm.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useAccountingStore } from '~/stores/accounting';
import { formatMoney } from '~/utils/formatMoney';

const props = defineProps({
  open: { type: Boolean, default: false },
  record: { type: Object, default: null },
});

const emit = defineEmits(['close', 'changed', 'next-income']);

const store = useAccountingStore();
const notify = usePanelNotify();

const cycles = ref([]);
const loading = ref(false);
let sequence = 0;

async function loadCycles() {
  if (!props.record) return;
  const current = ++sequence;
  loading.value = true;
  const result = await store.fetchHostingCycles(props.record.id);
  if (current !== sequence) return;
  loading.value = false;
  if (result.success) {
    cycles.value = result.data;
  } else {
    notify.error({ title: 'No se pudieron cargar los ciclos', detail: result.message });
  }
}

watch(
  [() => props.open, () => props.record?.id],
  () => {
    sequence += 1;
    cycles.value = [];
    if (props.open) loadCycles();
  },
  { immediate: true },
);

function paymentChanged() { loadCycles(); emit('changed'); }

const deleteConfirmOpen = ref(false);
const cycleToDelete = ref(null);

const deleteMessage = computed(() => {
  const cycle = cycleToDelete.value;
  if (!cycle) return '';
  return (
    `Se eliminará el ciclo del ${cycle.paid_at} por ${formatMoney(cycle.amount, 'COP')} ` +
    'y se recalculará el total pagado. La vigencia del hosting no se revierte.'
  );
});

function askDelete(cycle) {
  if (cycle.receipt_allocation_id) return;
  cycleToDelete.value = cycle;
  deleteConfirmOpen.value = true;
}

async function confirmDelete() {
  const cycle = cycleToDelete.value;
  cycleToDelete.value = null;
  if (!cycle || !props.record) return;
  const result = await store.deleteHostingCycle(props.record.id, cycle.id);
  if (result.success) {
    notify.success({ title: 'Ciclo eliminado' });
    loadCycles();
    emit('changed');
  } else {
    notify.error({ title: 'No se pudo eliminar el ciclo', detail: result.message });
  }
}
</script>
