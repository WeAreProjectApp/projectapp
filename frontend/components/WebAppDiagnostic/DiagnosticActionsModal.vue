<template>
  <BaseModal :model-value="visible" kind="form" @update:model-value="(open) => { if (!open) $emit('close') }">
    <div class="sticky top-0 bg-surface border-b border-border-muted px-6 py-4 rounded-t-2xl z-10 flex items-start justify-between">
      <div>
        <h2 class="text-lg font-semibold text-text-default">Acciones del diagnóstico</h2>
        <p class="text-xs text-text-muted mt-1">
          Selecciona una acción para este diagnóstico.
        </p>
      </div>
      <BaseActionButton
        action="close"
        label="Cerrar acciones del diagnóstico"
        class="w-11 h-11 -m-2 flex items-center justify-center rounded-lg text-text-subtle hover:text-text-default hover:bg-surface-raised motion-safe:transition-colors motion-safe:duration-fast focus:outline-none focus:ring-2 focus:ring-focus-ring/40"
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
        :data-testid="'diagnostic-action-' + action.key"
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
          <BaseRichTextContent class="block text-xs text-text-muted mt-0.5" :source="action.description" :format="action.text_formats?.['/description'] || 'plain'" />
        </span>
      </component>

      <p v-if="actions.length === 0" class="text-sm text-text-muted text-center py-6">
        No hay acciones disponibles para este diagnóstico.
      </p>
    </div>
  </BaseModal>
</template>

<script setup>
import { computed } from 'vue';
import BaseModal from '~/components/base/BaseModal.vue';
import { getDiagnosticNextAction } from '~/utils/diagnosticNextAction';

const props = defineProps({
  visible: { type: Boolean, default: false },
  diagnostic: { type: Object, default: () => ({}) },
});

const emit = defineEmits([
  'send', 'resend', 'analyze', 'send-final', 'delete', 'close',
]);

const suggestedKey = computed(() => getDiagnosticNextAction(props.diagnostic)?.key || null);

const TERMINAL = new Set(['accepted', 'rejected', 'finished']);

const actions = computed(() => {
  const d = props.diagnostic || {};
  const status = d.status;
  const transitions = d.available_transitions || [];
  const hasEmail = Boolean(d.client?.email);
  const list = [];

  if (status === 'draft' && hasEmail) {
    list.push({
      key: 'send',
      action: 'send',
      label: 'Enviar envío inicial',
      description: 'Envía por email el diagnóstico inicial al cliente.',
      dotClass: 'bg-info-strong',
    });
  }
  if (['sent', 'viewed'].includes(status) && hasEmail) {
    list.push({
      key: 'resend',
      action: 'resend',
      label: 'Re-enviar al cliente',
      description: 'Vuelve a enviar el email del diagnóstico inicial.',
      dotClass: 'bg-info-strong',
    });
  }
  if (transitions.includes('negotiating')) {
    list.push({
      key: 'analyze',
      action: 'analyze',
      label: 'Marcar en análisis',
      description: 'Confirma que el cliente autorizó y mueve a Negociación.',
      dotClass: 'bg-warning-strong',
    });
  }
  if (status === 'negotiating' && !d.final_sent_at) {
    list.push({
      key: 'send-final',
      action: 'send',
      label: 'Enviar diagnóstico final',
      description: 'Envía por email el diagnóstico final con el análisis completo.',
      dotClass: 'bg-primary',
    });
  }
  if (d.public_url) {
    list.push({
      key: 'preview',
      action: 'open-external',
      label: 'Vista previa pública',
      description: 'Abre el diagnóstico en una nueva pestaña tal como lo ve el cliente.',
      dotClass: 'bg-surface-raised border border-border-default',
      href: d.public_url,
    });
  }
  if (status && !TERMINAL.has(status)) {
    list.push({
      key: 'delete',
      action: 'delete',
      label: 'Eliminar',
      description: 'Elimina el diagnóstico. Esta acción no se puede deshacer.',
      dotClass: 'bg-danger-strong',
    });
  }

  return list;
});

function handleActionClick(action) {
  if (!action.href) emit(action.key);
  emit('close');
}
</script>
