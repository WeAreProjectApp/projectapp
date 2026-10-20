<script setup>
import { computed, toRef } from 'vue';
import EntityHistoryTabs from '~/components/history/EntityHistoryTabs.vue';
import PocketMovementAllocationDetails from './PocketMovementAllocationDetails.vue';
import { useAccountingRecordDetail } from '~/composables/useAccountingRecordDetail';
import { formatDate } from '~/utils/formatDate';
import { formatMoney } from '~/utils/formatMoney';
import { pocketAttributionLabel, signedPocketAmount } from '~/utils/pocketPresentation';

const props = defineProps({
  open: { type: Boolean, default: false },
  movementId: { type: Number, default: null },
});
const emit = defineEmits(['close']);
const { t } = useI18n();
const localePath = useLocalePath();
const { record, loading, error, reload } = useAccountingRecordDetail(
  'accounting/pocket/', toRef(props, 'movementId'), toRef(props, 'open'),
);
const linked = computed(() => record.value?.linked_record_detail);
const linkedTo = computed(() => {
  if (!linked.value) return null;
  const isExpense = linked.value.type === 'expense';
  return localePath({
    path: `/panel/accounting/${isExpense ? 'expenses' : 'incomes'}`,
    query: { [isExpense ? 'expense' : 'income']: String(linked.value.id) },
  });
});
</script>

<template>
  <BaseModal :model-value="open" kind="detail-compact" title-id="pocket-detail-title" @close="emit('close')">
    <div class="min-w-0 space-y-5 p-5 panel-portrait:p-6" data-testid="pocket-detail-modal">
      <header class="min-w-0 space-y-2">
        <h2 id="pocket-detail-title" class="text-lg font-semibold text-text-default">{{ t('accountingPocket.title') }}</h2>
        <template v-if="record">
          <p class="break-words text-base text-text-default" data-testid="pocket-detail-concept">{{ record.concept }}</p>
          <p class="text-sm text-text-muted">{{ formatDate(record.movement_date) }}</p>
          <p class="break-words text-3xl font-semibold tabular-nums" :class="record.direction === 'out' ? 'text-danger-strong' : 'text-success-strong'" data-testid="pocket-detail-amount">
            {{ signedPocketAmount(record) }}
          </p>
        </template>
      </header>

      <p v-if="loading" role="status" class="text-sm text-text-muted">{{ t('accountingPocket.loading') }}</p>
      <div v-else-if="error" role="alert" class="space-y-3 text-sm text-danger-strong">
        <p>{{ t(`accountingPocket.${error}`) }}</p>
        <BaseButton v-if="error !== 'missing'" variant="secondary" @click="reload">{{ t('accountingPocket.retry') }}</BaseButton>
      </div>

      <EntityHistoryTabs v-else-if="record" :key="record.id" entity-type="pocket" :object-id="record.id">
        <div class="min-w-0 space-y-6">
          <div class="grid min-w-0 gap-6 panel-portrait:grid-cols-2">
            <section class="min-w-0 space-y-3">
              <h3 class="text-sm font-semibold text-text-default">{{ t('accountingPocket.movement') }}</h3>
              <dl class="space-y-3 text-sm">
                <div><dt class="text-text-muted">{{ t('accountingPocket.type') }}</dt><dd class="text-text-default">{{ record.direction_label }}</dd></div>
                <div><dt class="text-text-muted">{{ t('accountingPocket.balance') }}</dt><dd class="tabular-nums text-text-default" data-testid="pocket-detail-balance">{{ formatMoney(record.running_balance) }}</dd></div>
              </dl>
            </section>
            <section class="min-w-0 space-y-3">
              <h3 class="text-sm font-semibold text-text-default">{{ t('accountingPocket.links') }}</h3>
              <dl class="space-y-3 text-sm">
                <div><dt class="text-text-muted">{{ t('accountingPocket.belongsTo') }}</dt><dd class="text-text-default" data-testid="pocket-detail-attribution">{{ pocketAttributionLabel(record.linked_ledger, t) }}</dd></div>
                <div v-if="linked">
                  <dt class="text-text-muted">{{ t('accountingPocket.linked') }} · {{ t(`accountingPocket.${linked.type}`) }}</dt>
                  <dd class="min-w-0"><BaseRowLink :to="linkedTo" class="break-words text-text-brand" data-testid="pocket-detail-linked-record">{{ linked.concept }}</BaseRowLink></dd>
                </div>
                <div v-else-if="!record.allocation_details?.length"><dt class="text-text-muted">{{ t('accountingPocket.linked') }}</dt><dd class="text-text-default">{{ t('accountingPocket.unlinked') }}</dd></div>
                <div v-if="linked?.category_label"><dt class="text-text-muted">{{ t('accountingPocket.category') }}</dt><dd class="text-text-default">{{ linked.category_label }}</dd></div>
              </dl>
            </section>
          </div>
          <PocketMovementAllocationDetails v-if="record.allocation_details?.length && (record.allocation_details.length > 1 || record.allocation_details[0].expected_income_id || record.allocation_details[0].is_credit)" :movement="record" />
          <section class="min-w-0 space-y-2">
            <h3 class="text-sm font-semibold text-text-default">{{ t('accountingPocket.notes') }}</h3>
            <p class="whitespace-pre-wrap break-words text-sm text-text-muted" data-testid="pocket-detail-notes">{{ record.notes || t('accountingPocket.noNotes') }}</p>
          </section>
        </div>
      </EntityHistoryTabs>
    </div>
    <template #footer>
      <BaseModalActions><BaseButton variant="secondary" @click="emit('close')">{{ t('accountingPocket.close') }}</BaseButton></BaseModalActions>
    </template>
  </BaseModal>
</template>
