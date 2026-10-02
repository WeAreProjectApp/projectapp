<template>
  <BaseModal :model-value="visible" kind="form" @update:model-value="(open) => { if (!open) $emit('close') }">
    <div class="sticky top-0 bg-surface border-b border-border-muted px-6 py-4 rounded-t-2xl z-10 flex items-start justify-between">
      <div>
        <h2 class="text-lg font-semibold text-text-default">Acciones de la propuesta</h2>
        <p class="text-xs text-text-muted mt-1">
          Selecciona una acción para esta propuesta.
        </p>
      </div>
      <BaseActionButton
        action="close"
        label="Cerrar acciones de la propuesta"
        class="w-11 h-11 -m-2"
        @click="$emit('close')"
      />
    </div>

    <div class="px-4 sm:px-6 py-4 space-y-2">
      <component
        v-for="action in actions"
        :key="action.key"
        :is="action.href ? 'a' : 'button'"
        :href="action.href || null"
        :target="action.href ? '_blank' : null"
        :rel="action.href ? 'noopener' : null"
        :type="action.href ? null : 'button'"
        :data-testid="'proposal-action-' + action.key"
        class="w-full flex items-start gap-3 p-3 rounded-xl border border-border-muted hover:bg-surface-raised motion-safe:transition-colors motion-safe:duration-fast text-left focus:outline-none focus:ring-2 focus:ring-focus-ring/40"
        @click="handleActionClick(action)"
      >
        <span class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-raised text-text-subtle">
          <BaseActionIcon :action="action.action" />
        </span>
        <span class="flex-1 min-w-0">
          <span class="flex items-center gap-2 flex-wrap">
            <span class="text-sm font-medium text-text-default">{{ action.label }}</span>
            <span
              v-if="action.key === suggestedKey"
              class="text-2xs uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-primary-soft text-text-brand"
            >
              Sugerido
            </span>
          </span>
          <span class="block text-xs text-text-muted mt-0.5">
            {{ action.description }}
          </span>
        </span>
      </component>

      <p v-if="actions.length === 0" class="text-sm text-text-muted text-center py-6">
        No hay acciones disponibles para esta propuesta.
      </p>

      <!-- Cambiar estado (modo admin) -->
      <div class="mt-2 pt-3 border-t border-border-muted">
        <div class="flex items-center justify-between gap-3 p-3">
          <div class="min-w-0">
            <span class="text-sm font-medium text-text-default block">Cambiar estado</span>
            <span class="text-xs text-text-muted block mt-0.5">
              Fuerza cualquier estado. Fuera del flujo normal no se envían correos ni automatizaciones.
            </span>
          </div>
          <ProposalStatusSelect
            :proposal="proposal"
            data-testid="proposal-actions-status-select"
            @change="(s) => { $emit('change-status', s); $emit('close'); }"
          />
        </div>
      </div>
    </div>
  </BaseModal>
</template>

<script setup>
import { computed } from 'vue';
import BaseModal from '~/components/base/BaseModal.vue';
import ProposalStatusSelect from '~/components/panel/proposal/ProposalStatusSelect.vue';
import { getProposalNextAction } from '~/utils/proposalNextAction';

const props = defineProps({
  visible: { type: Boolean, default: false },
  proposal: { type: Object, default: () => ({}) },
});

const emit = defineEmits([
  'send', 'send-multi', 'resend', 'negotiate', 'approve', 'launch', 'finish', 'reject',
  'discount-offer', 'change-status', 'close',
]);

const suggestedKey = computed(() => getProposalNextAction(props.proposal)?.key || null);

const actions = computed(() => {
  const p = props.proposal || {};
  const status = p.status;
  const transitions = p.available_transitions || [];
  const hasEmail = Boolean(p.client_email);
  const list = [];

  if (status === 'draft' && hasEmail) {
    list.push({
      key: 'send',
      action: 'send',
      label: 'Enviar al Cliente',
      description: 'Envía por email la propuesta con el mensaje preparado en Correos.',
      dotClass: 'bg-info-strong',
    });
  }
  if (['sent', 'viewed'].includes(status) && hasEmail) {
    list.push({
      key: 'resend',
      action: 'resend',
      label: 'Re-enviar al Cliente',
      description: 'Permite editar el mensaje y vuelve a enviar sin cambiar la fecha de expiración.',
      dotClass: 'bg-info-strong',
    });
  }
  if (hasEmail) {
    list.push({
      key: 'send-multi',
      action: 'send',
      label: 'Enviar varias propuestas como un solo correo',
      description: 'Envía varias propuestas con sus mensajes guardados y PDFs en un único correo.',
      dotClass: 'bg-info-strong',
    });
  }
  if (transitions.includes('negotiating')) {
    list.push({
      key: 'negotiate',
      action: 'negotiate',
      label: 'Pasar a Negociación',
      description: 'Genera el contrato y mueve la propuesta al estado Negociación.',
      dotClass: 'bg-warning-strong',
    });
  }
  if (transitions.includes('accepted')) {
    list.push({
      key: 'approve',
      action: 'approve',
      label: 'Aprobar',
      description: 'Marca la propuesta como aceptada por el cliente.',
      dotClass: 'bg-success-strong',
    });
  }
  if (['accepted', 'negotiating'].includes(status)) {
    list.push({
      key: 'launch',
      action: 'launch',
      label: p.linked_project ? 'Revisar vinculación' : 'Completar revisión',
      description: 'Valida cliente, proyecto y documentos antes de sincronizar. Permite revisar después.',
      dotClass: 'bg-primary',
    });
  }
  if (Number(p.discount_percent) > 0 && hasEmail) {
    list.push({
      key: 'discount-offer',
      action: 'discount-offer',
      label: 'Enviar oferta de descuento',
      description: `Ofrece el descuento del ${p.discount_percent}% al cliente, con previsualización antes de enviar.`,
      dotClass: 'bg-danger-strong',
    });
  }
  if (transitions.includes('finished')) {
    list.push({
      key: 'finish',
      action: 'finish',
      label: 'Marcar como finalizada',
      description: 'Cierra la propuesta como finalizada y notifica al cliente.',
      dotClass: 'bg-primary',
    });
  }
  if (transitions.includes('rejected')) {
    list.push({
      key: 'reject',
      action: 'reject',
      label: 'Rechazar',
      description: 'Registra que la propuesta fue rechazada.',
      dotClass: 'bg-danger-strong',
    });
  }
  if (p.uuid) {
    list.push({
      key: 'preview',
      action: 'open-external',
      label: 'Vista previa pública',
      description: 'Abre la propuesta en una nueva pestaña tal como la ve el cliente.',
      dotClass: 'bg-surface-raised border border-border-default',
      href: '/proposal/' + p.uuid + '?preview=1',
    });
  }

  return list;
});

function handleActionClick(action) {
  if (!action.href) emit(action.key);
  emit('close');
}
</script>
