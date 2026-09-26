<template>
  <div class="space-y-8">
    <!-- ── Documentos (lista unificada) ── -->
    <section class="bg-surface border border-border-muted rounded-xl p-5">
      <div class="flex items-center gap-2 mb-4">
        <svg class="w-5 h-5 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <h3 class="text-sm font-semibold text-text-default dark:text-white">Documentos para formalización</h3>
      </div>

      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p class="text-xs text-text-muted">Versiones formales con alcance y condiciones del proyecto.</p>
        <BaseButton variant="primary" size="sm" data-testid="proposal-formalization-open" @click="formalizationOpen = true">Preparar correo de formalización</BaseButton>
      </div>

      <!-- Modalidad de cierre: un contrato, o producto y servicio por separado -->
      <div v-if="showModality" class="mb-4 rounded-lg border border-border-muted bg-surface-raised p-4" data-testid="proposal-contract-modality">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="min-w-0">
            <p class="text-sm font-medium text-text-default dark:text-white">Modalidad de cierre</p>
            <p class="text-xs text-text-muted mt-0.5">
              Un solo contrato, o el producto (desarrollo e implementación) y el servicio (hosting, mantenimiento y soporte) por separado.
            </p>
          </div>
          <BaseSegmented
            :model-value="modality"
            size="sm"
            :options="modalityOptions"
            :disabled="modalityDisabled"
            :disabled-reason="modalityDisabledReason"
            aria-label="Modalidad de cierre"
            @update:model-value="changeModality"
          />
        </div>
        <p v-if="customSplitNotice" class="mt-3 text-xs text-text-muted" role="note" data-testid="proposal-contract-modality-custom-notice">
          El contrato único de esta propuesta es personalizado. Los contratos de producto y servicio parten del texto estándar; personalízalos desde «Editar parámetros» si hace falta.
        </p>
      </div>

      <ul class="divide-y divide-border-muted">
        <!-- Contrato(s) de la modalidad de cierre -->
        <ProposalContractRow
          v-for="variant in contractVariants"
          :key="variant.key"
          :proposal="proposal"
          :variant="variant"
          :doc="contractDocFor(variant)"
          :actions-disabled="contractActionsDisabled"
          @preview="openPdfPreview"
          @edit="$emit('editContract', variant.key)"
          @generate="$emit('generateContract', variant.key)"
        />

        <!-- Propuesta comercial -->
        <li class="py-3 flex items-start justify-between gap-3 flex-wrap">
          <div class="min-w-0">
            <div class="text-sm font-medium text-text-default dark:text-white">Propuesta comercial formal</div>
            <div class="text-xs text-text-subtle dark:text-text-subtle mt-0.5">PDF formal · Contenido curado</div>
          </div>
          <div class="flex items-center gap-2 flex-wrap">
            <ProposalDocumentCopyButton :endpoint="`proposals/${proposal.id}/formalization/markdown/commercial/`"
              title="Propuesta comercial formal" data-testid="proposal-copy-commercial" />
            <BaseActionButton action="view" label="Vista previa de la propuesta comercial"
              @click="openPdfPreview('Propuesta comercial', commercialPdfUrl)"
              class="bg-surface-raised text-text-muted hover:bg-surface-raised" />
            <a :href="commercialPdfUrl" target="_blank"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary-soft text-text-brand rounded-lg text-xs font-medium hover:bg-primary-soft transition-colors">
              <BaseActionIcon action="download" />
              Descargar PDF
            </a>
          </div>
        </li>

        <!-- Detalle técnico -->
        <li class="py-3 flex items-start justify-between gap-3 flex-wrap">
          <div class="min-w-0">
            <div class="text-sm font-medium text-text-default dark:text-white">Detalle técnico formal</div>
            <div class="text-xs text-text-subtle dark:text-text-subtle mt-0.5">PDF formal · Contenido curado</div>
          </div>
          <div class="flex items-center gap-2 flex-wrap">
            <ProposalDocumentCopyButton :endpoint="`proposals/${proposal.id}/formalization/markdown/technical/`"
              title="Detalle técnico formal" data-testid="proposal-copy-technical" />
            <BaseActionButton action="view" label="Vista previa del detalle técnico"
              @click="openPdfPreview('Detalle técnico', technicalPdfUrl)"
              class="bg-surface-raised text-text-muted hover:bg-surface-raised" />
            <a :href="technicalPdfUrl" target="_blank"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary-soft text-text-brand rounded-lg text-xs font-medium hover:bg-primary-soft transition-colors">
              <BaseActionIcon action="download" />
              Descargar PDF
            </a>
          </div>
        </li>
      </ul>
    </section>

    <!-- ── Documentos adjuntos ── -->
    <section class="bg-surface border border-border-muted rounded-xl p-5">
      <div class="flex items-center gap-2 mb-4">
        <svg class="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
        <h3 class="text-sm font-semibold text-text-default dark:text-white">Documentos adjuntos</h3>
      </div>

      <div v-if="additionalDocs.length" class="space-y-2 mb-4">
        <div v-for="doc in additionalDocs" :key="doc.id"
          :data-testid="`proposal-attachment-${doc.id}`"
          class="flex flex-wrap items-center justify-between gap-3 py-2 px-3 bg-surface-raised rounded-lg">
          <div class="flex items-center gap-2 min-w-0">
            <span class="px-2 py-0.5 bg-surface-raised text-text-muted/60 rounded text-[10px] font-medium">
              {{ doc.document_type_display }}
            </span>
            <a :href="doc.file" target="_blank" class="text-xs text-text-brand hover:text-text-brand font-medium truncate">
              {{ doc.title }}
            </a>
          </div>
          <div class="flex items-center gap-1 flex-wrap">
            <ProposalDocumentCopyButton :endpoint="`proposals/${proposal.id}/documents/${doc.id}/markdown/`"
              :title="doc.title" :disabled-reason="copyUnavailableReason(doc.file)"
              :data-testid="`proposal-copy-attachment-${doc.id}`" />
            <BaseActionButton
              action="view"
              :label="`Vista previa de ${doc.title}`"
              :disabled="!canPreviewFile(doc.file) && !isOfficeFile(doc.file)"
              :disabled-reason="copyUnavailableReason(doc.file)"
              @click="openDocPreview(doc)"
            />
            <BaseActionButton action="download" :label="`Descargar ${doc.title}`"
              :loading="downloadingDocId === doc.id" :disabled="downloadingDocId !== null"
              disabled-reason="Espera mientras se descarga el archivo."
              @click="downloadAttachment(doc)" />
            <BaseActionButton
              v-if="!doc.is_generated"
              action="delete"
              label="Eliminar documento"
              variant="danger-ghost"
              size="sm"
              @click="handleDelete(doc.id)"
            />
          </div>
        </div>
      </div>
      <p v-else class="text-xs text-text-subtle dark:text-text-subtle mb-4">No hay documentos adjuntos.</p>

      <!-- Upload form -->
      <div class="border-t border-border-muted pt-4">
        <p class="text-xs text-text-muted mb-3">Subir documento (otrosí, anexo, documento del cliente, etc.)</p>
        <div class="flex flex-wrap items-end gap-3">
          <div class="flex-1 min-w-[150px]">
            <label class="block text-xs text-text-subtle dark:text-text-subtle mb-1">Título</label>
            <input v-model="uploadTitle" type="text" placeholder="Ej: Anexo técnico"
              class="w-full px-3 py-2 border border-border-default dark:bg-primary-strong dark:text-white rounded-lg text-xs focus:ring-2 focus:ring-focus-ring/30" />
          </div>
          <div class="w-36">
            <label class="block text-xs text-text-subtle dark:text-text-subtle mb-1">Tipo</label>
            <select v-model="uploadType"
              class="w-full px-3 py-2 border border-border-default dark:bg-primary-strong dark:text-white rounded-lg text-xs focus:ring-2 focus:ring-focus-ring/30">
              <option value="amendment">Otrosí</option>
              <option value="legal_annex">Anexo legal</option>
              <option value="client_document">Doc. del cliente</option>
              <option value="other">Otro</option>
            </select>
          </div>
          <div v-if="uploadType === 'other'" class="min-w-[120px]">
            <label class="block text-xs text-text-subtle dark:text-text-subtle mb-1">Nombre categoría</label>
            <input v-model="uploadCustomLabel" type="text" placeholder="Ej: Diseños"
              class="w-full px-3 py-2 border border-border-default dark:bg-primary-strong dark:text-white rounded-lg text-xs focus:ring-2 focus:ring-focus-ring/30" />
          </div>
          <div>
            <label class="block text-xs text-text-subtle dark:text-text-subtle mb-1">Archivo</label>
            <input ref="fileInput" type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"
              class="text-xs dark:text-white/70 file:mr-2 file:py-1.5 file:px-3 file:border-0 file:text-xs file:font-medium file:bg-primary-soft file:text-text-brand file:rounded-lg hover:file:bg-primary-soft" />
          </div>
          <BaseButton variant="primary" size="sm" :disabled="isUploading" @click="handleUpload">
            {{ isUploading ? 'Subiendo...' : 'Subir' }}
          </BaseButton>
        </div>
      </div>
    </section>

    <ProposalFormalizationModal v-if="formalizationOpen" :proposal="proposal" :documents="documents" @close="closeFormalization" @sent="formalizationSent = true" />
    <MarkdownPreviewModal v-model="previewOpen" :title="previewTitle">
      <div v-if="previewLoading"
        class="flex items-center justify-center h-[60vh] text-sm text-text-muted">
        Cargando vista previa…
      </div>
      <div v-else-if="previewError"
        class="flex items-center justify-center h-[60vh] text-sm text-red-500">
        {{ previewError }}
      </div>
      <div v-else-if="previewKind === 'markdown'" class="min-w-0 overflow-x-auto">
        <p v-if="previewWarnings.length" class="mb-4 text-sm text-text-muted" role="status">{{ previewWarnings.join(' ') }}</p>
        <DocumentMarkdownBody :markdown="previewMarkdown" variant="full" standard-markdown />
      </div>
      <iframe v-else-if="previewKind === 'pdf' && previewUrl" :src="previewUrl"
        class="w-full h-[80vh] border-0 rounded-lg bg-surface" title="Vista previa"></iframe>
      <img v-else-if="previewKind === 'image' && previewUrl" :src="previewUrl"
        class="max-w-full mx-auto" :alt="previewTitle" />
    </MarkdownPreviewModal>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue';
import ProposalDocumentCopyButton from './ProposalDocumentCopyButton.vue';
import ProposalContractRow from './ProposalContractRow.vue';
import DocumentMarkdownBody from '~/components/panel/documents/DocumentMarkdownBody.vue';
import { get_request } from '~/stores/services/request_http';
import { downloadBlob, filenameFromDisposition } from '~/utils/downloadFile';
import ProposalFormalizationModal from './ProposalFormalizationModal.vue';
import { usePanelNotify } from '~/composables/usePanelNotify';
import {
  CONTRACT_DOC_TYPES,
  CONTRACT_LOCKED_STATUSES,
  CONTRACT_MODALITY,
  CONTRACT_MODALITY_EDITABLE_STATUSES,
  CONTRACT_MODALITY_VISIBLE_STATUSES,
  CONTRACT_VARIANTS,
  contractVariantsFor,
} from '~/stores/proposals_constants';
import { isPdfUrl, isImageUrl, canPreviewFile } from '~/utils/filePreview';
import MarkdownPreviewModal from '~/components/panel/documents/MarkdownPreviewModal.vue';

const notify = usePanelNotify();

const props = defineProps({
  proposal: { type: Object, required: true },
  documents: { type: Array, default: () => [] },
});

const emit = defineEmits(['refresh', 'editContract', 'generateContract']);

const proposalStore = useProposalStore();
const isUploading = ref(false);
const formalizationOpen = ref(false);
const formalizationSent = ref(false);

function closeFormalization() {
  formalizationOpen.value = false;
  if (formalizationSent.value) {
    formalizationSent.value = false;
    emit('refresh');
  }
}
const uploadTitle = ref('');
const uploadType = ref('other');
const uploadCustomLabel = ref('');
const fileInput = ref(null);

const contractVariants = computed(() =>
  contractVariantsFor(props.proposal).map((key) => CONTRACT_VARIANTS[key]),
);

function contractDocFor(variant) {
  return props.documents.find(d => d.document_type === variant.docType) || null;
}

const contractActionsDisabled = computed(() =>
  CONTRACT_LOCKED_STATUSES.includes(props.proposal?.status),
);

// ── Modalidad de cierre ──
const modality = computed(() => props.proposal?.contract_modality || CONTRACT_MODALITY.SINGLE);
const showModality = computed(() => CONTRACT_MODALITY_VISIBLE_STATUSES.includes(props.proposal?.status));
const savingModality = ref(false);
const modalityDisabled = computed(() =>
  savingModality.value || !CONTRACT_MODALITY_EDITABLE_STATUSES.includes(props.proposal?.status),
);
const modalityDisabledReason = computed(() => (
  savingModality.value
    ? 'Guardando la modalidad de cierre…'
    : 'La modalidad de cierre se elige durante la negociación.'
));
const modalityOptions = [
  { value: CONTRACT_MODALITY.SINGLE, label: 'Contrato único', testId: 'proposal-contract-modality-single' },
  { value: CONTRACT_MODALITY.SPLIT, label: 'Producto y servicio', testId: 'proposal-contract-modality-split' },
];
const customSplitNotice = computed(() => {
  const params = props.proposal?.contract_params || {};
  return modality.value === CONTRACT_MODALITY.SPLIT && params.contract_source === 'custom';
});

async function changeModality(value) {
  // BaseSegmented also emits when the selected option is clicked again.
  if (value === modality.value || savingModality.value) return;
  savingModality.value = true;
  const result = await proposalStore.updateContractModality(props.proposal.id, value);
  savingModality.value = false;
  if (result.success) {
    notify.success(value === CONTRACT_MODALITY.SPLIT
      ? 'El negocio se cierra con contrato de producto y contrato de servicio.'
      : 'El negocio se cierra con un contrato único.');
  } else {
    notify.error(result.message || 'No se pudo cambiar la modalidad de cierre.');
  }
}

const commercialPdfUrl = computed(() =>
  `/api/proposals/${props.proposal.id}/formalization/pdf/commercial/`,
);
const technicalPdfUrl = computed(() =>
  `/api/proposals/${props.proposal.id}/formalization/pdf/technical/`,
);

const additionalDocs = computed(() =>
  props.documents.filter(d => !CONTRACT_DOC_TYPES.includes(d.document_type)),
);

const previewOpen = ref(false);
const previewMarkdown = ref('');
const previewWarnings = ref([]);
const downloadingDocId = ref(null);
const previewKind = ref('pdf');
const previewTitle = ref('Vista previa');
const previewUrl = ref('');
const previewLoading = ref(false);
const previewError = ref('');
let previewRequestId = 0;
let previewAbortController = null;

function releasePreviewObjectUrl() {
  if (previewUrl.value && typeof URL !== 'undefined') {
    URL.revokeObjectURL(previewUrl.value);
  }
  previewUrl.value = '';
}

function abortInflightPreview() {
  if (previewAbortController) {
    previewAbortController.abort();
    previewAbortController = null;
  }
}

async function loadPreviewBlob(kind, title, url) {
  abortInflightPreview();
  releasePreviewObjectUrl();
  previewKind.value = kind;
  previewTitle.value = title || 'Vista previa';
  previewError.value = '';
  previewLoading.value = true;
  previewOpen.value = true;

  const controller = new AbortController();
  previewAbortController = controller;
  const requestId = ++previewRequestId;
  try {
    const response = await fetch(url, { credentials: 'include', signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    if (requestId !== previewRequestId || !previewOpen.value) return;
    previewUrl.value = URL.createObjectURL(blob);
  } catch (err) {
    if (requestId !== previewRequestId || err?.name === 'AbortError') return;
    previewError.value = 'No se pudo cargar la vista previa.';
    notify.error('No se pudo cargar la vista previa.');
  } finally {
    if (requestId === previewRequestId) {
      previewLoading.value = false;
      previewAbortController = null;
    }
  }
}

function openPdfPreview(title, url) {
  loadPreviewBlob('pdf', title, url);
}

function openDocPreview(doc) {
  const file = doc?.file || '';
  if (isPdfUrl(file)) {
    loadPreviewBlob('pdf', doc?.title, file);
  } else if (isImageUrl(file)) {
    loadPreviewBlob('image', doc?.title, file);
  } else if (isOfficeFile(file)) {
    loadMarkdownPreview(doc);
  }
}

function isOfficeFile(file) {
  return /\.(docx|xlsx)(?:\?|#|$)/i.test(file || '');
}

function copyUnavailableReason(file) {
  if (isPdfUrl(file) || isOfficeFile(file)) return '';
  if (/\.(doc|xls)(?:\?|#|$)/i.test(file || '')) return 'Convierte el archivo a DOCX o XLSX para visualizar y copiar su contenido.';
  if (isImageUrl(file)) return 'La imagen no tiene texto extraíble. Se requiere reconocimiento de texto.';
  return 'No hay contenido compatible para copiar. Puedes descargar el archivo original.';
}

async function loadMarkdownPreview(doc) {
  abortInflightPreview();
  releasePreviewObjectUrl();
  previewKind.value = 'markdown';
  previewTitle.value = doc.title;
  previewMarkdown.value = '';
  previewWarnings.value = [];
  previewError.value = '';
  previewLoading.value = true;
  previewOpen.value = true;
  const controller = new AbortController();
  previewAbortController = controller;
  const requestId = ++previewRequestId;
  try {
    const { data } = await get_request(`proposals/${props.proposal.id}/documents/${doc.id}/markdown/`, { signal: controller.signal });
    if (requestId !== previewRequestId || !previewOpen.value) return;
    previewMarkdown.value = data.markdown;
    previewWarnings.value = data.warnings || [];
  } catch (error) {
    if (requestId !== previewRequestId || controller.signal.aborted) return;
    previewError.value = error.response?.data?.error || 'No se pudo cargar la vista previa.';
  } finally {
    if (requestId === previewRequestId) {
      previewLoading.value = false;
      previewAbortController = null;
    }
  }
}

async function downloadAttachment(doc) {
  if (downloadingDocId.value !== null) return;
  downloadingDocId.value = doc.id;
  try {
    const response = await get_request(`proposals/${props.proposal.id}/documents/${doc.id}/download/`, { responseType: 'blob' });
    downloadBlob(response.data, filenameFromDisposition(response.headers['content-disposition']) || doc.file?.split('/').pop() || doc.title);
  } catch {
    notify.error('No se pudo descargar el archivo. Vuelve a intentarlo.');
  } finally {
    downloadingDocId.value = null;
  }
}

watch(previewOpen, (open) => {
  if (!open) {
    previewRequestId++;
    abortInflightPreview();
    releasePreviewObjectUrl();
    previewLoading.value = false;
    previewError.value = '';
  }
});

onBeforeUnmount(() => {
  abortInflightPreview();
  releasePreviewObjectUrl();
});

async function handleUpload() {
  const file = fileInput.value?.files?.[0];
  if (!file) return;

  isUploading.value = true;
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', uploadTitle.value || file.name);
  formData.append('document_type', uploadType.value);
  if (uploadType.value === 'other' && uploadCustomLabel.value) {
    formData.append('custom_type_label', uploadCustomLabel.value);
  }

  const result = await proposalStore.uploadProposalDocument(props.proposal.id, formData);
  if (result.success) {
    uploadTitle.value = '';
    uploadCustomLabel.value = '';
    if (fileInput.value) fileInput.value.value = '';
    emit('refresh');
    notify.success('Documento subido.');
  } else {
    notify.error('No se pudo subir el documento.');
  }
  isUploading.value = false;
}

async function handleDelete(docId) {
  const result = await proposalStore.deleteProposalDocument(props.proposal.id, docId);
  if (result.success) {
    emit('refresh');
    notify.success('Documento eliminado.');
  } else {
    notify.error('No se pudo eliminar el documento.');
  }
}
</script>
