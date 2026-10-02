<template>
  <BaseModal
    :model-value="modelValue"
    kind="workspace"
    full-height
    :close-on-backdrop="!threadStore.isSaving"
    :close-on-esc="!threadStore.isSaving"
    @update:model-value="handleRequestedVisibility"
  >
    <div class="flex flex-shrink-0 items-center justify-between gap-3 border-b border-border-muted px-4 py-4 sm:px-6">
      <div class="min-w-0">
        <h2 class="truncate text-lg font-semibold text-text-default" data-testid="document-thread-title">
          {{ thread ? thread.title : 'Enlazar documentos' }}
        </h2>
        <p class="mt-0.5 text-xs text-text-subtle">
          {{ thread ? `${members.length} documentos relacionados` : 'Crea una historia independiente de las carpetas' }}
        </p>
      </div>
      <BaseActionButton action="close" label="Cerrar hilo de documentos" @click="requestClose" />
    </div>

    <div v-if="threadStore.isLoadingThread" class="flex min-h-0 flex-1 items-center justify-center" role="status">
      <span class="text-sm text-text-subtle">Cargando hilo…</span>
    </div>

    <template v-else>
      <div class="flex-shrink-0 px-4 pt-4 sm:px-6">
        <BaseResponsiveTabs
          v-model="activeTab"
          :tabs="tabs"
          variant="underline"
          full-width
          aria-label="Secciones del hilo"
        />
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-5 sm:px-6" data-testid="document-thread-content">
        <BaseAlert v-if="saveError" variant="danger" title="No se pudo guardar el hilo" class="mb-4">
          {{ saveError }}
        </BaseAlert>

        <section v-if="activeTab === 'relate'" class="grid gap-5 panel-landscape:grid-cols-2" data-testid="document-thread-relate">
          <div class="min-w-0 space-y-4">
            <div>
              <label for="document-thread-name" class="mb-1 block text-sm font-medium text-text-default">
                Nombre del hilo
              </label>
              <input
                id="document-thread-name"
                v-model="draftTitle"
                type="text"
                maxlength="255"
                class="w-full rounded-xl border border-border-default bg-surface px-3 py-2.5 text-sm text-text-default outline-none focus:border-focus-ring focus:ring-2 focus:ring-focus-ring/30"
                data-testid="document-thread-name"
              >
            </div>

            <div>
              <div class="mb-2 flex items-center justify-between gap-2">
                <h3 class="text-sm font-semibold text-text-default">Documentos del hilo</h3>
                <BaseBadge variant="neutral" size="sm">{{ members.length }}</BaseBadge>
              </div>
              <div class="space-y-2">
                <article
                  v-for="member in members"
                  :key="member.document.id"
                  class="rounded-xl border border-border-muted bg-surface-raised p-3"
                  :data-testid="`thread-member-${member.document.id}`"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <p class="whitespace-normal [overflow-wrap:anywhere] text-sm font-medium text-text-default">{{ member.document.title }}</p>
                      <p class="mt-0.5 whitespace-normal [overflow-wrap:anywhere] text-xs text-text-subtle">{{ metadataLine(member.document) }}</p>
                      <BaseBadge v-if="member.document.is_archived" variant="warning" size="sm" class="mt-2">
                        Archivado
                      </BaseBadge>
                    </div>
                    <BaseActionButton
                      action="delete"
                      :label="`Retirar ${member.document.title} del hilo`"
                      :disabled="!thread && member.document.id === document.id"
                      disabled-reason="El documento desde el que creas el hilo debe permanecer incluido."
                      @click="removeMember(member.document.id)"
                    />
                  </div>
                  <label class="mt-3 block text-xs font-medium text-text-muted">
                    Fecha en la cronología
                    <input
                      v-model="member.occurred_on"
                      type="date"
                      class="mt-1 w-full rounded-lg border border-border-default bg-surface px-3 py-2 text-sm text-text-default"
                      :data-testid="`thread-date-${member.document.id}`"
                    >
                  </label>
                </article>
              </div>
            </div>
          </div>

          <div class="min-w-0 rounded-xl border border-border-muted bg-surface-raised p-4">
            <h3 class="text-sm font-semibold text-text-default">Buscar documentos</h3>
            <p class="mt-1 text-xs text-text-subtle">Busca por título, carpeta, cliente o proyecto.</p>
            <input
              v-model="search"
              type="search"
              placeholder="Buscar documento…"
              class="mt-3 w-full rounded-xl border border-border-default bg-surface px-3 py-2.5 text-sm text-text-default outline-none focus:border-focus-ring focus:ring-2 focus:ring-focus-ring/30"
              data-testid="document-thread-search"
            >
            <BaseCheckbox
              v-model="includeArchived"
              class="mt-3"
              data-testid="document-thread-include-archived"
            >
              Incluir documentos archivados
            </BaseCheckbox>

            <div v-if="threadStore.isLoadingCandidates" class="py-10 text-center text-sm text-text-subtle" role="status">
              Buscando…
            </div>
            <div v-else-if="!threadStore.candidates.length" class="py-10 text-center text-sm text-text-subtle">
              No hay documentos disponibles con estos filtros.
            </div>
            <div v-else class="mt-4 space-y-2" data-testid="document-thread-candidates">
              <!-- design-tokens: allow-raw-button — selectable document row -->
              <button
                v-for="row in candidateRows"
                :key="row.candidate.id"
                type="button"
                class="w-full rounded-xl border border-border-muted bg-surface p-3 text-left transition-colors"
                :class="row.blocked ? 'cursor-not-allowed opacity-55' : 'hover:border-border-default'"
                :aria-disabled="row.blocked || undefined"
                :aria-describedby="row.blocked ? `thread-candidate-reason-${row.candidate.id}` : undefined"
                :data-testid="`thread-candidate-${row.candidate.id}`"
                @click="addCandidate(row.candidate)"
              >
                <span class="block whitespace-normal [overflow-wrap:anywhere] text-sm font-medium text-text-default">{{ row.candidate.title }}</span>
                <span class="mt-0.5 block whitespace-normal [overflow-wrap:anywhere] text-xs text-text-subtle">{{ metadataLine(row.candidate) }}</span>
                <span
                  v-if="row.candidate.thread_summary || row.candidate.is_archived"
                  class="mt-2 flex flex-wrap items-center gap-1"
                >
                  <BaseBadge v-if="row.candidate.thread_summary" variant="info" size="sm">
                    Hilo · {{ row.candidate.thread_summary.document_count }}
                  </BaseBadge>
                  <BaseBadge v-if="row.candidate.is_archived" variant="warning" size="sm">Archivado</BaseBadge>
                </span>
                <span
                  v-if="row.blocked"
                  :id="`thread-candidate-reason-${row.candidate.id}`"
                  class="mt-1 block text-xs text-warning-strong"
                >
                  {{ row.reason }}
                </span>
              </button>
            </div>

            <BasePagination
              :current-page="candidatePage"
              :total-pages="candidateTotalPages"
              :total-items="threadStore.candidateCount"
              :range-from="candidateRangeFrom"
              :range-to="candidateRangeTo"
              aria-label="Resultados de documentos"
              @prev="goToCandidatePage(candidatePage - 1)"
              @next="goToCandidatePage(candidatePage + 1)"
              @go="goToCandidatePage"
            />
          </div>
        </section>

        <section v-else-if="activeTab === 'detail'" class="flex min-h-[28rem] flex-col" data-testid="document-thread-detail">
          <div v-if="selectedMetadata" class="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="break-words text-lg font-semibold text-text-default">{{ selectedMetadata.title }}</h3>
              <p class="mt-1 text-sm text-text-subtle">{{ metadataLine(selectedMetadata) }}</p>
            </div>
            <div class="flex gap-2">
              <BaseButton
                variant="secondary"
                size="sm"
                :disabled="!selectedDetail?.content_markdown"
                disabled-reason="Este documento no tiene contenido editable para mostrar."
                @click="detailMode = 'markdown'"
              >
                Contenido
              </BaseButton>
              <BaseButton variant="secondary" size="sm" @click="detailMode = 'pdf'">PDF</BaseButton>
            </div>
          </div>
          <div v-if="threadStore.isLoadingDetail" class="flex flex-1 items-center justify-center text-sm text-text-subtle" role="status">
            Cargando documento…
          </div>
          <PdfPreviewPane
            v-else-if="detailMode === 'pdf' && selectedDocumentId"
            class="min-h-[24rem]"
            :src="`/api/documents/${selectedDocumentId}/pdf/?inline=1`"
            :active="activeTab === 'detail'"
            error-message="Este documento todavía no tiene un PDF disponible."
            test-id-prefix="thread-document-pdf"
          />
          <div v-else-if="selectedDetail?.content_markdown" class="rounded-xl border border-border-muted bg-surface p-5">
            <DocumentMarkdownBody :markdown="selectedDetail.content_markdown" variant="full" />
          </div>
          <BaseEmptyState v-else title="Sin contenido para mostrar" description="Selecciona PDF para intentar abrir el archivo generado." />
        </section>

        <section v-else class="mx-auto max-w-4xl" data-testid="document-thread-timeline">
          <div v-if="!chronologyItems.length" class="py-10 text-center text-sm text-text-subtle">El hilo está vacío.</div>
          <ol v-else class="relative ml-3 border-l border-border-default pl-6">
            <li v-for="member in chronologyItems" :key="member.document.id" class="relative pb-6 last:pb-0">
              <span class="absolute -left-[1.82rem] top-1.5 h-3 w-3 rounded-full border-2 border-surface bg-primary" aria-hidden="true" />
              <!-- design-tokens: allow-raw-button — selectable timeline row -->
              <button
                type="button"
                class="w-full rounded-xl border border-border-muted bg-surface p-4 text-left hover:border-border-default"
                :data-testid="`thread-timeline-${member.document.id}`"
                @click="openDetail(member.document.id)"
              >
                <span class="text-xs font-semibold uppercase tracking-wide text-text-brand">{{ formatDate(member.occurred_on) }}</span>
                <span class="mt-1 block break-words text-sm font-semibold text-text-default">{{ member.document.title }}</span>
                <span class="mt-1 block text-xs text-text-subtle">{{ metadataLine(member.document) }}</span>
                <BaseBadge v-if="member.document.is_archived" variant="warning" size="sm" class="mt-2">Archivado</BaseBadge>
              </button>
            </li>
          </ol>
        </section>
      </div>


    </template>
    <template #footer>
      <BaseModalActions v-if="!threadStore.isLoadingThread">
        <BaseButton
          v-if="thread && activeTab === 'relate'"
          variant="danger"
          size="sm"
          :disabled="threadStore.isSaving"
          data-testid="document-thread-dissolve"
          @click="confirmDissolve"
        >
          Disolver hilo
        </BaseButton>
        <span v-else />
        <div class="flex flex-col-reverse gap-2 panel-portrait:flex-row panel-portrait:items-center">
          <BaseButton variant="secondary" size="md" :disabled="threadStore.isSaving" @click="requestClose">Cerrar</BaseButton>
          <BaseButton
            v-if="activeTab === 'relate'"
            variant="primary"
            size="md"
            :loading="threadStore.isSaving"
            :disabled="!canSave"
            disabled-reason="Agrega al menos dos documentos y un nombre para guardar."
            data-testid="document-thread-save"
            @click="saveThread"
          >
            Guardar hilo
          </BaseButton>
        </div>
      </BaseModalActions>
    </template>
  </BaseModal>

  <ConfirmModal
    v-model="confirmState.open"
    :title="confirmState.title"
    :message="confirmState.message"
    :confirm-text="confirmState.confirmText"
    :cancel-text="confirmState.cancelText"
    :variant="confirmState.variant"
    :loading="confirmState.busy"
    @confirm="handleConfirmed"
    @cancel="handleCancelled"
  />
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import PdfPreviewPane from '~/components/base/PdfPreviewPane.vue';
import DocumentMarkdownBody from './DocumentMarkdownBody.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useDocumentThreadStore } from '~/stores/document_threads';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  document: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue', 'saved']);

const threadStore = useDocumentThreadStore();
const notify = usePanelNotify();
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const thread = computed(() => threadStore.currentThread);
const activeTab = ref('relate');
const draftTitle = ref('');
const members = ref([]);
const baseline = ref('');
const search = ref('');
const includeArchived = ref(false);
const candidatePage = ref(1);
const selectedDocumentId = ref(null);
const selectedDetail = ref(null);
const detailMode = ref('markdown');
const saveError = ref('');
let searchTimer = null;
let initializeToken = 0;
let detailToken = 0;

const tabs = computed(() => [
  { id: 'relate', label: 'Relacionar', badge: members.value.length },
  { id: 'detail', label: 'Detalle' },
  { id: 'timeline', label: 'Cronología', badge: members.value.length },
]);
const selectedIds = computed(() => new Set(members.value.map(item => item.document.id)));
// El backend es dueño de la copia del bloqueo permanente («ya pertenece a otro hilo»):
// esa frase acompaña al 409 del servicio y no se reescribe acá. El borrador local es el
// único que sabe qué agregaste en esta sesión, así que ese motivo —y sólo ese— nace acá.
const IN_DRAFT_REASON = 'Ya está en este hilo.';
const candidateRows = computed(() => threadStore.candidates.map((candidate) => {
  const reason = candidate.unavailable_reason
    || (selectedIds.value.has(candidate.id) ? IN_DRAFT_REASON : '');
  return { candidate, reason, blocked: Boolean(reason) };
}));
const candidateTotalPages = computed(() => Math.max(1, Math.ceil(threadStore.candidateCount / 20)));
const candidateRangeFrom = computed(() => (
  threadStore.candidateCount ? ((candidatePage.value - 1) * 20) + 1 : 0
));
const candidateRangeTo = computed(() => Math.min(candidatePage.value * 20, threadStore.candidateCount));
const selectedMetadata = computed(() => (
  members.value.find(item => item.document.id === selectedDocumentId.value)?.document || null
));
const chronologyItems = computed(() => members.value
  .map((item, index) => ({ ...item, _stableIndex: index }))
  .sort((left, right) => (
    String(left.occurred_on).localeCompare(String(right.occurred_on))
    || left._stableIndex - right._stableIndex
  )));
const signature = computed(() => JSON.stringify({
  title: draftTitle.value.trim(),
  items: members.value.map(item => ({
    document_id: item.document.id,
    occurred_on: item.occurred_on,
  })),
}));
const isDirty = computed(() => Boolean(baseline.value) && signature.value !== baseline.value);
const canSave = computed(() => (
  draftTitle.value.trim()
  && members.value.length >= (thread.value ? 1 : 2)
  && isDirty.value
));

function normalizeDocument(document) {
  return {
    ...document,
    folder: document.folder && typeof document.folder === 'object'
      ? document.folder
      : (document.folder ? { id: document.folder, name: document.folder_name || 'Carpeta' } : null),
    client: document.client && typeof document.client === 'object'
      ? document.client
      : ((document.client || document.client_display_name || document.client_name)
        ? { id: document.client || null, name: document.client_display_name || document.client_name || 'Cliente' }
        : null),
    project: document.project && typeof document.project === 'object'
      ? document.project
      : (document.project ? { id: document.project, name: document.project_name || 'Proyecto' } : null),
  };
}

function bogotaDate(value) {
  if (!value) return '';
  const parts = new Intl.DateTimeFormat('en-US', {
    year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'America/Bogota',
  }).formatToParts(new Date(value));
  const byType = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${byType.year}-${byType.month}-${byType.day}`;
}

async function initialize() {
  if (!props.document?.id) return;
  const token = ++initializeToken;
  const documentId = props.document.id;
  threadStore.reset();
  activeTab.value = 'relate';
  draftTitle.value = '';
  members.value = [];
  baseline.value = '';
  saveError.value = '';
  search.value = '';
  includeArchived.value = false;
  candidatePage.value = 1;
  selectedDocumentId.value = documentId;
  selectedDetail.value = null;
  const result = await threadStore.fetchThread(documentId);
  if (token !== initializeToken || !props.modelValue || props.document?.id !== documentId) return;
  if (!result.success) {
    saveError.value = result.message;
    return;
  }
  if (result.data) {
    draftTitle.value = result.data.title;
    members.value = result.data.items.map(item => ({
      document: normalizeDocument(item.document),
      occurred_on: item.occurred_on,
    }));
    activeTab.value = 'timeline';
  } else {
    const detailResult = await threadStore.fetchDocumentDetail(documentId);
    if (token !== initializeToken || !props.modelValue || props.document?.id !== documentId) return;
    const source = normalizeDocument(detailResult.success ? detailResult.data : props.document);
    draftTitle.value = source.title;
    members.value = [{
      document: source,
      occurred_on: source.issue_date || bogotaDate(source.created_at),
    }];
    activeTab.value = 'relate';
  }
  baseline.value = signature.value;
  await loadCandidates();
}

async function loadCandidates() {
  if (!props.modelValue || !props.document?.id) return;
  const result = await threadStore.fetchCandidates({
    documentId: props.document.id,
    threadId: thread.value?.id,
    search: search.value,
    includeArchived: includeArchived.value,
    page: candidatePage.value,
  });
  if (!result.success && !result.stale) saveError.value = result.message;
}

function addCandidate(candidate) {
  if (!candidate.available || selectedIds.value.has(candidate.id)) return;
  members.value.push({
    document: normalizeDocument(candidate),
    occurred_on: candidate.default_occurred_on,
  });
}

function removeMember(documentId) {
  members.value = members.value.filter(item => item.document.id !== documentId);
  if (selectedDocumentId.value === documentId) {
    selectedDocumentId.value = members.value[0]?.document.id || null;
  }
}

async function saveThread() {
  saveError.value = '';
  const payload = {
    title: draftTitle.value.trim(),
    items: members.value.map(item => ({
      document_id: item.document.id,
      occurred_on: item.occurred_on || null,
    })),
  };
  if (thread.value && members.value.length === 1) {
    const confirmed = await requestConfirm({
      title: 'Disolver el hilo',
      message: 'Un hilo necesita al menos dos documentos. Al guardar, el documento restante quedará independiente.',
      confirmText: 'Disolver y guardar',
      variant: 'danger',
    });
    if (!confirmed) return;
  }
  const result = thread.value
    ? await threadStore.updateThread(thread.value.id, payload)
    : await threadStore.createThread(payload);
  if (!result.success) {
    saveError.value = result.message;
    return;
  }
  notify.success({ title: result.data?.dissolved ? 'Hilo disuelto' : 'Hilo guardado' });
  emit('saved', { thread: threadStore.currentThread, documentId: props.document.id });
  if (!threadStore.currentThread
    || !threadStore.currentThread.items.some(item => item.document.id === props.document.id)) {
    emit('update:modelValue', false);
    return;
  }
  members.value = threadStore.currentThread.items.map(item => ({
    document: normalizeDocument(item.document),
    occurred_on: item.occurred_on,
  }));
  draftTitle.value = threadStore.currentThread.title;
  baseline.value = signature.value;
  activeTab.value = 'timeline';
}

async function confirmDissolve() {
  const confirmed = await requestConfirm({
    title: 'Disolver hilo',
    message: `Los ${members.value.length} documentos quedarán independientes. Los documentos no se eliminarán.`,
    confirmText: 'Disolver hilo',
    variant: 'danger',
  });
  if (!confirmed) return;
  const result = await threadStore.dissolveThread(thread.value.id);
  if (!result.success) {
    saveError.value = result.message;
    return;
  }
  notify.success({ title: 'Hilo disuelto' });
  emit('saved', { thread: null, documentId: props.document.id });
  emit('update:modelValue', false);
}

async function requestClose() {
  if (isDirty.value) {
    const confirmed = await requestConfirm({
      title: 'Descartar cambios del hilo',
      message: 'Los documentos y fechas que cambiaste no se guardarán.',
      confirmText: 'Descartar cambios',
      variant: 'warning',
    });
    if (!confirmed) return;
  }
  emit('update:modelValue', false);
}

function handleRequestedVisibility(value) {
  if (value) emit('update:modelValue', true);
  else requestClose();
}

async function openDetail(documentId) {
  selectedDocumentId.value = documentId;
  activeTab.value = 'detail';
}

async function loadSelectedDetail() {
  const token = ++detailToken;
  const documentId = selectedDocumentId.value;
  if (activeTab.value !== 'detail' || !documentId) return;
  const result = await threadStore.fetchDocumentDetail(documentId);
  if (token !== detailToken || activeTab.value !== 'detail' || selectedDocumentId.value !== documentId) return;
  if (!result.success) {
    saveError.value = result.message;
    selectedDetail.value = null;
    return;
  }
  selectedDetail.value = result.data;
  detailMode.value = result.data?.content_markdown ? 'markdown' : 'pdf';
}

function metadataLine(document) {
  return [
    document.folder?.name || 'Sin carpeta',
    document.client?.name || 'Sin cliente',
    document.project?.name || 'Sin proyecto',
  ].join(' · ');
}

function formatDate(value) {
  if (!value) return 'Sin fecha';
  return new Intl.DateTimeFormat('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`));
}

function goToCandidatePage(page) {
  candidatePage.value = Math.min(Math.max(Number(page) || 1, 1), candidateTotalPages.value);
  loadCandidates();
}

watch(() => props.modelValue, open => {
  if (open) initialize();
  else initializeToken += 1;
}, { immediate: true });
watch([search, includeArchived], () => {
  candidatePage.value = 1;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadCandidates, 300);
});
watch([activeTab, selectedDocumentId], loadSelectedDetail);
onBeforeUnmount(() => {
  initializeToken += 1;
  detailToken += 1;
  clearTimeout(searchTimer);
});
</script>
