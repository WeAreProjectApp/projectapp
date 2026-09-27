<template>
  <BaseModal
    :model-value="visible"
    kind="form"
    @update:model-value="(open) => { if (!open) handleClose() }"
  >
    <div class="sticky top-0 z-10 flex items-start justify-between gap-3 rounded-t-2xl border-b border-border-muted bg-surface px-6 py-4">
      <div>
        <h2 class="text-lg font-semibold text-text-default">Re-enviar propuesta</h2>
        <p class="mt-1 text-xs text-text-muted">
          Se conservará la fecha de expiración. Puedes ajustar el mensaje antes de enviarlo.
        </p>
      </div>
      <BaseActionButton action="close" label="Cerrar reenvío" @click="handleClose" />
    </div>

    <div class="space-y-4 px-6 py-5">
      <div class="rounded-xl border border-border-muted bg-surface-raised px-4 py-3 text-sm">
        <p class="font-medium text-text-default">{{ proposal.title }}</p>
        <p class="mt-1 text-xs text-text-muted">Para {{ proposal.client_email || 'correo pendiente' }}</p>
      </div>

      <div>
        <label for="proposal-resend-email-intro" class="mb-1 block text-sm font-medium text-text-default">
          Mensaje personalizado
        </label>
        <p class="mb-2 text-xs leading-relaxed text-text-muted">
          Explica de forma puntual el problema del cliente, cómo lo resuelve esta propuesta y el resultado de negocio esperado.
        </p>
        <BaseTextarea
          id="proposal-resend-email-intro"
          v-model="messageDraft"
          :rows="7"
          :error="Boolean(errorMessage)"
          placeholder="Ej. Esta propuesta resuelve… mediante… para lograr…"
          data-testid="proposal-resend-email-intro"
        />
        <p class="mt-1 text-xs text-text-subtle">Texto plano. Se permiten saltos de línea; no HTML ni Markdown.</p>
      </div>

      <div v-if="errorMessage" class="rounded-lg border border-danger-strong/30 bg-danger-soft px-3 py-2" role="alert">
        <p class="text-sm font-medium text-danger-strong">{{ errorMessage }}</p>
        <p v-if="errorHint" class="mt-1 text-xs text-danger-strong">{{ errorHint }}</p>
      </div>
    </div>

    <template #footer>
      <BaseModalActions>
        <BaseButton variant="secondary" size="md" :disabled="sending" @click="handleClose">
          Cancelar
        </BaseButton>
        <BaseButton
          variant="primary"
          size="md"
          :loading="sending"
          :disabled="!normalizedMessage || sending"
          disabled-reason="Escribe el mensaje personalizado antes de reenviar."
          data-testid="proposal-resend-confirm"
          @click="handleResend"
        >
          {{ sending ? 'Re-enviando…' : 'Guardar y re-enviar' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useProposalStore } from '~/stores/proposals';

const props = defineProps({
  visible: { type: Boolean, default: false },
  proposal: { type: Object, default: () => ({}) },
});

const emit = defineEmits(['close', 'resent']);
const proposalStore = useProposalStore();
const messageDraft = ref('');
const sending = ref(false);
const errorMessage = ref('');
const errorHint = ref('');

const normalizedMessage = computed(() => messageDraft.value.trim());

watch(
  () => [props.visible, props.proposal?.id],
  ([open]) => {
    if (!open) return;
    messageDraft.value = props.proposal?.email_intro || '';
    errorMessage.value = '';
    errorHint.value = '';
  },
  { immediate: true },
);

function handleClose() {
  if (sending.value) return;
  emit('close');
}

async function handleResend() {
  if (!props.proposal?.id || !normalizedMessage.value || sending.value) return;
  sending.value = true;
  errorMessage.value = '';
  errorHint.value = '';
  try {
    const result = await proposalStore.resendProposal(
      props.proposal.id,
      normalizedMessage.value,
    );
    if (result.success) {
      emit('resent', result);
      emit('close');
      return;
    }
    errorMessage.value = result.message || 'No se pudo re-enviar la propuesta.';
    errorHint.value = result.hint || '';
  } finally {
    sending.value = false;
  }
}
</script>
