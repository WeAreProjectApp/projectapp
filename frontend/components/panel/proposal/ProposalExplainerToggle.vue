<script setup>
import { computed, onMounted, ref } from 'vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import { useExplainerVideosStore } from '~/stores/explainer_videos';

const props = defineProps({
  proposal: { type: Object, required: true },
  modelValue: { type: Boolean, default: true },
  language: { type: String, default: 'es' },
  showLegal: { type: Boolean, default: true },
  saving: { type: Boolean, default: false },
});
defineEmits(['update:modelValue']);
const store = useExplainerVideosStore();
const loadFailed = ref(false);
async function loadSettings() {
  const result = await store.fetchSettings();
  loadFailed.value = !result.success;
}
onMounted(() => {
  if (!store.settings && !store.isLoading) loadSettings();
});
const unavailableReason = computed(() => {
  if (loadFailed.value) return 'No se pudo consultar el control general.';
  if (!store.settings) return 'Consultando el control general…';
  if (!store.isVisible('proposal')) return 'Oculto: el control general está apagado en Propuestas → Configuraciones.';
  if (props.language !== 'es') return 'Oculto: el video solo está disponible en español.';
  if (!props.showLegal) return 'Oculto: activa Contrato y condiciones para mostrar las cuatro opciones.';
  if (!props.proposal.sections?.some(section => section.section_type === 'technical_document' && section.is_enabled)) {
    return 'Oculto: añade y activa el detalle técnico para mostrar las cuatro opciones.';
  }
  if (!props.proposal.is_active) return 'Oculto: la propuesta está inactiva.';
  return '';
});
const status = computed(() => unavailableReason.value || (props.modelValue
  ? 'Visible al abrir la propuesta. Se reproduce cuando el cliente lo elige.'
  : 'Oculto para este cliente.'));
</script>

<template>
  <div data-testid="proposal-explainer-preference">
    <p class="text-xs text-text-subtle">Video de bienvenida</p>
    <div class="mt-1 flex items-center gap-2">
      <BaseToggle
        :model-value="modelValue"
        :disabled="saving || !store.settings || store.isUpdating"
        disabled-reason="Espera a que termine de cargar o guardar la configuración."
        size="sm"
        aria-label="Mostrar video de bienvenida"
        data-testid="proposal-explainer-toggle"
        @update:model-value="$emit('update:modelValue', $event)"
      />
      <span class="text-xs text-text-muted">Mostrar video de bienvenida</span>
    </div>
    <p class="mt-1 text-xs leading-5 text-text-muted" role="status" data-testid="proposal-explainer-status">{{ status }}</p>
    <BaseButton v-if="loadFailed" variant="secondary" size="sm" :loading="store.isLoading" @click="loadSettings">
      Reintentar
    </BaseButton>
  </div>
</template>
