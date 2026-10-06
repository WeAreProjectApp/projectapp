<template>
  <li class="py-3 flex items-start justify-between gap-3 flex-wrap" :data-testid="`proposal-contract-row-${variant.key}`">
    <div class="min-w-0">
      <div class="text-sm font-medium text-text-default dark:text-white">{{ variant.label }}</div>
      <div v-if="variant.subtitle" class="text-xs text-text-muted mt-0.5">{{ variant.subtitle }}</div>
      <div class="text-xs text-text-subtle dark:text-text-subtle mt-0.5">
        <template v-if="doc">PDF · Generado el {{ formatDate(doc.updated_at || doc.created_at) }}</template>
        <template v-else>PDF · No generado</template>
      </div>
      <p v-if="doc" class="mt-1 text-xs text-text-muted" :data-testid="`proposal-contract-source-${variant.key}`">{{ proposal.contract_params?.[variant.sourceKey] === 'custom' ? 'Personalizado' : 'Plantilla' }}</p>
      <p v-if="doc?.needs_regeneration" class="mt-1 text-xs text-warning-strong" role="status" data-testid="proposal-service-contract-stale">
        Las condiciones del servicio cambiaron. Regenera y revisa el contrato antes de enviarlo.
      </p>
    </div>
    <div class="flex items-center gap-2 flex-wrap">
      <template v-if="doc">
        <ProposalDocumentCopyButton
          :key="`${variant.key}-${proposal.id}-${doc.updated_at || doc.file}`"
          :endpoint="`proposals/${proposal.id}/contract/markdown/${query}`"
          :title="variant.label" :data-testid="copyTestId" />
        <BaseActionButton action="view" :label="previewLabel"
          @click="$emit('preview', variant.label, pdfUrl)"
          class="bg-surface-raised text-text-muted hover:bg-surface-raised" />
        <PanelDownloadLink :url="pdfUrl" filename="contrato.pdf" />
        <PanelDownloadLink :url="draftPdfUrl" filename="borrador.pdf" :label="t('pwa.download.draft')" />
        <BaseButton variant="secondary" size="sm" :disabled="actionsDisabled" disabled-reason="El contrato ya no se puede editar en el estado actual de la propuesta." @click="$emit('edit')">
          {{ doc.needs_regeneration ? 'Regenerar contrato' : 'Editar parámetros' }}
        </BaseButton>
      </template>
      <BaseButton variant="secondary" size="sm" v-else-if="!actionsDisabled" :data-testid="`proposal-generate-contract-${variant.key}`" @click="$emit('generate')">
        Generar contrato
      </BaseButton>
    </div>
  </li>
</template>

<script setup>
import PanelDownloadLink from '~/components/panel/PanelDownloadLink.vue';
import { useI18n } from '#imports';
import { computed } from 'vue';
import ProposalDocumentCopyButton from './ProposalDocumentCopyButton.vue';
import { formatDateTime } from '~/utils/formatDate';

const { t } = useI18n();

const props = defineProps({
  proposal: { type: Object, required: true },
  // One entry of CONTRACT_VARIANTS (stores/proposals_constants.js).
  variant: { type: Object, required: true },
  doc: { type: Object, default: null },
  actionsDisabled: { type: Boolean, default: false },
});

defineEmits(['preview', 'edit', 'generate']);

// The single contract keeps its historical URLs; a split closing names its document.
const query = computed(() => (props.variant.key === 'combined' ? '' : `?variant=${props.variant.key}`));
const pdfUrl = computed(() => `/api/proposals/${props.proposal.id}/contract/pdf/${query.value}`);
const draftPdfUrl = computed(() => `/api/proposals/${props.proposal.id}/contract/draft-pdf/${query.value}`);
const copyTestId = computed(() => (
  props.variant.key === 'combined' ? 'proposal-copy-contract' : `proposal-copy-contract-${props.variant.key}`
));
const previewLabel = computed(() => (
  props.variant.key === 'combined'
    ? 'Vista previa del contrato'
    : `Vista previa del ${props.variant.label.toLowerCase()}`
));

function formatDate(isoString) {
  return formatDateTime(isoString, { fallback: '' });
}
</script>
