<template>
  <template v-if="entry.status === 'failed'">
    <BaseButton
      v-if="entry.is_retryable"
      variant="secondary"
      size="sm"
      :loading="busy"
      :data-testid="`email-history-retry-${entry.id}`"
      @click="confirmRetry"
    >{{ t('panelUsability.retry') }}</BaseButton>
    <p v-else class="text-xs text-text-muted" :data-testid="`email-history-retry-blocked-${entry.id}`">
      {{ entry.retry_blocked_reason || t('panelUsability.retryUnavailable') }}
    </p>
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="t('panelUsability.cancel')"
      :loading="confirmState.busy"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />
  </template>
</template>

<script setup>
import { ref } from 'vue';
import BaseButton from '~/components/base/BaseButton.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { useEmailStore } from '~/stores/emails';

const props = defineProps({ entry: { type: Object, required: true }, subject: { type: String, default: '' } });
const emit = defineEmits(['attempted']);
const { t } = useI18n();
const store = useEmailStore();
const busy = ref(false);
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();

function confirmRetry() {
  if (busy.value || confirmState.value.open) return;
  const id = props.entry.id;
  requestConfirm({
    title: t('panelUsability.retry'),
    message: t('panelUsability.retryQuestion', { subject: props.subject, recipient: props.entry.recipient || props.entry.email }),
    confirmText: t('panelUsability.retry'),
    waitForConfirm: true,
    onConfirm: async () => {
      busy.value = true;
      try {
        const result = await store.retryEmail(id);
        emit('attempted', result);
      } finally {
        busy.value = false;
      }
    },
  });
}
</script>
