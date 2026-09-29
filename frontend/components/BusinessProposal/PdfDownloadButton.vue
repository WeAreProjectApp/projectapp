<template>
  <BaseButton
    unstyled
    icon-only
    class="pdf-download fixed bottom-[4.75rem] right-4 z-40
           w-12 h-12 rounded-full
           bg-white/90 backdrop-blur-sm shadow-lg border border-border-default
           flex items-center justify-center text-text-default
           hover:bg-primary-soft hover:text-text-brand hover:border-emerald-200
           transition-colors"
    :disabled="isGenerating || isExpired"
    :aria-describedby="message ? messageId : undefined"
    :aria-label="isGenerating ? 'Generando PDF' : 'Descargar PDF'"
    :title="message || (isGenerating ? 'Generando...' : 'Descargar PDF')"
    @click="downloadPdf"
  >
    <!-- Spinner while generating -->
    <svg v-if="isGenerating" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
    <!-- Download icon -->
    <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  </BaseButton>
  <p v-if="message" :id="messageId" role="status"
    class="fixed bottom-32 right-4 z-40 max-w-[calc(100vw-2rem)] w-72 rounded-xl border border-border-default bg-surface p-3 text-sm text-text-default shadow-lg">
    {{ message }}
  </p>
</template>

<script setup>
import { computed, useId } from 'vue';
import { useProposalPdfDownload } from '~/composables/useProposalPdfDownload';

const props = defineProps({
  viewMode: {
    type: String,
    default: '',
  },
  selectedModuleIds: {
    type: Array,
    default: null,
  },
});

const proposalStore = useProposalStore();
const messageId = useId();
const pdfUrl = computed(() => {
  const uuid = proposalStore.currentProposal?.uuid;
  if (props.viewMode === 'legal') return `/api/proposals/${uuid}/contract/draft-pdf/`;
  const params = new URLSearchParams();
  if (props.selectedModuleIds?.length) params.set('selected_modules', props.selectedModuleIds.join(','));
  if (props.viewMode === 'technical') params.set('doc', 'technical');
  const query = params.toString();
  return `/api/proposals/${uuid}/pdf/${query ? `?${query}` : ''}`;
});
const pdfFilename = computed(() => {
  const proposal = proposalStore.currentProposal;
  const title = proposal?.title || proposal?.client_name || 'Propuesta';
  const safeName = title.replace(/[^\w\sáéíóúñÁÉÍÓÚÑ-]/g, '').trim().replace(/\s+/g, '_').slice(0, 100);
  const date = proposal?.created_at ? new Date(proposal.created_at) : new Date();
  const suffix = `${String(date.getDate()).padStart(2, '0')}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getFullYear()).slice(-2)}`;
  const prefix = props.viewMode === 'technical' ? 'Detalle_Tecnico'
    : props.viewMode === 'legal' ? 'Borrador_Contrato' : 'Propuesta_Comercial';
  return `${prefix}_${safeName}_${suffix}.pdf`;
});
const { isGenerating, isExpired, message, downloadPdf } = useProposalPdfDownload({
  proposal: () => proposalStore.currentProposal,
  url: pdfUrl,
  filename: pdfFilename,
  isLegal: () => props.viewMode === 'legal',
});
</script>
