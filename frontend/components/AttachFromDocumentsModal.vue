<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
    @click.self="$emit('close')">
    <div class="bg-surface rounded-xl shadow-xl max-w-lg w-full max-h-[85vh] flex flex-col border border-border-default dark:border-white/[0.08]">
      <header class="flex items-center justify-between px-5 py-4 border-b border-border-muted">
        <h3 class="text-sm font-semibold text-text-default">
          Adjuntar desde Documentos
        </h3>
        <BaseActionButton action="close" label="Cerrar selector de documentos" @click="$emit('close')" />
      </header>

      <div class="flex-1 overflow-y-auto px-5 py-3">
        <p v-if="!availableDocs.length" class="text-xs text-text-subtle dark:text-white/40 py-6 text-center">
          No hay documentos disponibles para adjuntar.
        </p>
        <ul v-else class="divide-y divide-border-muted dark:divide-white/[0.06]">
          <li v-for="doc in availableDocs" :key="doc.key" class="py-2.5 flex items-center gap-3">
            <input :id="`attach-${doc.key}`" v-model="selectedKeys" type="checkbox" :value="doc.key"
              class="rounded border-input-border dark:border-white/[0.15] text-text-brand focus:ring-focus-ring/30" />
            <label :for="`attach-${doc.key}`" class="flex-1 min-w-0 cursor-pointer">
              <div class="text-sm text-text-default truncate">{{ doc.label }}</div>
              <div class="text-[11px] text-text-subtle dark:text-white/40 mt-0.5">{{ doc.description }}</div>
            </label>
          </li>
        </ul>
      </div>

      <footer class="flex items-center justify-end gap-2 px-5 py-3 border-t border-border-muted">
        <BaseButton variant="ghost" size="sm" @click="$emit('close')">
          Cancelar
        </BaseButton>
        <BaseControlGate
          :reasons="!selectedKeys.length ? ['Selecciona al menos un documento para adjuntar.'] : []"
          label="Adjuntar no disponible"
          align="end"
        >
          <template #default="{ describedBy }">
            <BaseButton
              variant="primary"
              size="sm"
              :disabled="!selectedKeys.length"
              disabled-reason="Selecciona al menos un documento para adjuntar."
              :aria-describedby="describedBy"
              @click="confirm"
            >
              Adjuntar ({{ selectedKeys.length }})
            </BaseButton>
          </template>
        </BaseControlGate>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { CONTRACT_DOC_TYPES, CONTRACT_VARIANTS, contractVariantsFor } from '~/stores/proposals_constants';

const props = defineProps({
  open: { type: Boolean, default: false },
  /** 'proposal' | 'diagnostic' */
  source: { type: String, required: true },
  /** Proposal or Diagnostic object (with uploaded files list) */
  entity: { type: Object, required: true },
  /** Static diagnostic MD templates (only used when source === 'diagnostic') */
  templates: { type: Array, default: () => [] },
  /** Already-selected keys to pre-check */
  preselected: { type: Array, default: () => [] },
});

const emit = defineEmits(['close', 'attach']);

const selectedKeys = ref([...props.preselected]);

watch(() => props.open, (open) => {
  if (open) selectedKeys.value = [...props.preselected];
});

const availableDocs = computed(() => {
  if (props.source === 'proposal') return proposalDocs();
  if (props.source === 'diagnostic') return diagnosticDocs();
  return [];
});

function contractRef(source, variantKey) {
  return variantKey === 'combined' ? { source } : { source, variant: variantKey };
}

function proposalDocs() {
  const proposal = props.entity || {};
  const documents = proposal.proposal_documents || [];
  const list = [];
  // Contracts of the closing modality: the single contract, or the product and
  // service contracts. A split closing names the document it attaches.
  for (const variantKey of contractVariantsFor(proposal)) {
    const variant = CONTRACT_VARIANTS[variantKey];
    if (!documents.some(d => d.document_type === variant.docType)) continue;
    const suffix = variantKey === 'combined' ? '' : `:${variantKey}`;
    list.push({
      key: `contract_pdf${suffix}`,
      label: `${variant.label} (PDF)`,
      description: 'Versión final generada',
      ref: contractRef('contract_pdf', variantKey),
    });
    list.push({
      key: `contract_draft${suffix}`,
      label: `${variant.label} (borrador)`,
      description: 'PDF con marca de agua',
      ref: contractRef('contract_draft', variantKey),
    });
  }
  list.push({
    key: 'commercial_pdf',
    label: 'Propuesta comercial (PDF)',
    description: 'PDF con branding',
    ref: { source: 'commercial_pdf' },
  });
  list.push({
    key: 'technical_pdf',
    label: 'Detalle técnico (PDF)',
    description: 'PDF con branding',
    ref: { source: 'technical_pdf' },
  });
  for (const doc of documents) {
    if (CONTRACT_DOC_TYPES.includes(doc.document_type)) continue;
    list.push({
      key: `proposal_document:${doc.id}`,
      label: doc.title,
      description: doc.document_type_display || 'Documento adjunto',
      ref: { source: 'proposal_document', id: doc.id },
    });
  }
  return list;
}

function diagnosticDocs() {
  const diagnostic = props.entity || {};
  const list = [];
  const nda = (diagnostic.attachments || []).find(
    (a) => a.document_type === 'confidentiality_agreement' && a.is_generated,
  );
  if (nda) {
    list.push({
      key: 'nda_final',
      label: 'Acuerdo de confidencialidad (PDF)',
      description: 'Versión final generada',
      ref: { source: 'nda_final' },
    });
    list.push({
      key: 'nda_draft',
      label: 'Acuerdo de confidencialidad (borrador)',
      description: 'PDF con marca de agua',
      ref: { source: 'nda_draft' },
    });
  }
  for (const t of (props.templates || [])) {
    list.push({
      key: `template:${t.slug}`,
      label: t.title,
      description: `${t.filename} · plantilla markdown`,
      ref: { source: 'template', slug: t.slug },
    });
  }
  for (const att of (diagnostic.attachments || [])) {
    if (att.document_type === 'confidentiality_agreement' && att.is_generated) continue;
    list.push({
      key: `attachment:${att.id}`,
      label: att.title,
      description: att.document_type_display || 'Documento adjunto',
      ref: { source: 'attachment', id: att.id },
    });
  }
  return list;
}

function confirm() {
  const picked = availableDocs.value.filter(d => selectedKeys.value.includes(d.key));
  emit('attach', picked.map(d => ({ key: d.key, label: d.label, ref: d.ref })));
  emit('close');
}
</script>
