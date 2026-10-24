<template>
  <div>
    <TabSplitLayout>
      <template #main>
    <!-- ── Email composer ── -->
    <section class="bg-surface border border-border-muted rounded-xl p-5">
      <div class="flex items-center gap-2 mb-5">
        <svg class="w-5 h-5 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <h3 class="text-sm font-semibold text-text-default dark:text-white">Correo de seguimiento</h3>
      </div>

      <!-- Sub-tab switcher -->
      <div class="mb-5">
        <BaseTabs
          v-model="activeSubTab"
          :tabs="[{ id: 'edit', label: 'Editar' }, { id: 'preview', label: 'Vista previa' }]"
        />
      </div>

      <!-- ── Edit sub-tab ── -->
      <div v-if="activeSubTab === 'edit'" class="space-y-4">
        <EmailRecipientFields
          v-model:toRecipients="toRecipients"
          v-model:ccRecipients="ccRecipients"
          test-id-prefix="diagnostic-email"
        />

        <div>
          <label class="block text-xs text-text-muted dark:text-white/70 mb-1">Asunto</label>
          <input v-model="subject" type="text" placeholder="Asunto del correo"
            class="w-full px-3 py-2 border border-border-default dark:text-white dark:placeholder:text-text-muted rounded-lg text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-emerald-500" />
        </div>

        <div>
          <label class="block text-xs text-text-muted dark:text-white/70 mb-1">Saludo</label>
          <input v-model="greeting" type="text" placeholder="Hola Carlos"
            class="w-full px-3 py-2 border border-border-default dark:text-white dark:placeholder:text-text-muted rounded-lg text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-emerald-500" />
        </div>

        <!-- Sections (draggable) -->
        <div>
          <label class="block text-xs text-text-muted dark:text-white/70 mb-2">Secciones del correo</label>
          <draggable v-model="sections" item-key="id" handle=".drag-handle" ghost-class="opacity-30"
            class="space-y-3">
            <template #item="{ element: section, index: idx }">
              <div class="bg-surface-muted rounded-lg p-3 border border-border-muted">
                <div class="flex items-center gap-2 mb-2">
                  <span class="drag-handle cursor-grab text-text-subtle hover:text-text-muted select-none text-sm">⠿</span>
                  <span class="text-2xs text-text-subtle uppercase tracking-wide">Sección {{ idx + 1 }}</span>

                  <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar" title="Eliminar" v-if="sections.length > 1" @click="removeSection(idx)">
                    <BaseActionIcon action="delete" />
                  </BaseButton>
                </div>
                <BaseRichTextEditor v-model="section.text" :format="section.markdown ? 'markdown_html_v1' : 'plain'" @update:format="section.markdown = true" rows="3" placeholder="Escribe el contenido de esta sección..."
                  class="w-full px-3 py-2 border border-border-default dark:text-white dark:placeholder:text-text-muted rounded-lg text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-emerald-500 resize-y"  />

              </div>
            </template>
          </draggable>
          <BaseButton variant="secondary" size="sm" class="mt-3" @click="addSection">
            <BaseActionIcon action="create" />
            Agregar sección
          </BaseButton>
        </div>

        <div>
          <label class="block text-xs text-text-muted dark:text-white/70 mb-1">Pie de correo</label>
          <BaseRichTextEditor v-model="footer" :format="textFormats['/footer'] || 'plain'" @update:format="textFormats['/footer'] = $event" rows="2" placeholder="Texto de cierre..."
            class="w-full px-3 py-2 border border-border-default dark:text-white dark:placeholder:text-text-muted rounded-lg text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-emerald-500 resize-y"  />
        </div>

        <div>
          <label class="block text-xs text-text-muted dark:text-white/70 mb-1">Adjuntos</label>
          <div class="flex flex-col items-start gap-3">
            <div class="flex flex-wrap items-center gap-2">
              <BaseButton variant="secondary" size="sm" @click="showAttachFromDocsModal = true">
                <BaseActionIcon action="attach" />
                Adjuntar desde Documentos
              </BaseButton>
              <BaseButton variant="ghost" size="sm" v-if="canCreateMarkdownAttachment" @click="showMarkdownModal = true">
                <BaseActionIcon action="create" />
                Crear documento desde markdown
              </BaseButton>
            </div>
            <input ref="fileInput" type="file" multiple
              accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"
              class="text-xs dark:text-white/70 file:mr-2 file:py-1.5 file:px-3 file:border-0 file:text-xs file:font-medium file:bg-primary-soft file:text-text-brand file:rounded-lg hover:file:bg-primary-soft"
              @change="handleFilesChange" />
          </div>
          <div v-if="docRefs.length || attachments.length" class="mt-2 space-y-1">
            <div v-for="(ref, idx) in docRefs" :key="`ref-${ref.key}`"
              class="flex items-center justify-between py-1.5 px-3 bg-primary-soft border border-emerald-100 dark:border-emerald-900/30 rounded-lg">
              <span class="flex items-center gap-2 min-w-0">
                <span class="px-1.5 py-0.5 bg-primary-soft text-text-brand rounded text-2xs font-medium">Documento</span>
                <span class="text-xs text-text-default dark:text-white/70 truncate">{{ ref.label }}</span>
              </span>
              <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar" title="Eliminar" @click="removeDocRef(idx)">
                <BaseActionIcon action="delete" />
              </BaseButton>
            </div>
            <div v-for="(file, idx) in attachments" :key="`file-${idx}`"
              class="flex items-center justify-between py-1.5 px-3 bg-surface-muted rounded-lg">
              <span class="text-xs text-text-default dark:text-white/70 truncate">{{ file.name }}</span>
              <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar" title="Eliminar" @click="removeAttachment(idx)">
                <BaseActionIcon action="delete" />
              </BaseButton>
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between pt-2">
          <p v-if="sendError" class="text-xs text-red-500">{{ sendError }}</p>
          <p v-else-if="sendSuccess" class="text-xs text-text-brand">Correo enviado correctamente.</p>
          <span v-else />
          <BaseButton variant="primary" size="sm" :disabled="!canSend" :loading="sending" @click="handleSend">
            <BaseActionIcon v-if="!sending" action="send" />
            {{ sending ? 'Enviando…' : 'Enviar correo' }}
          </BaseButton>
        </div>
      </div>

      <!-- ── Preview sub-tab ── -->
      <div v-else>
        <div class="mb-3 space-y-1 rounded-lg bg-surface-muted px-3 py-2 text-xs text-text-muted">
          <p><span class="font-medium text-text-default">Para:</span> {{ recipientSummary(toRecipients) || '—' }}</p>
          <p v-if="ccRecipients.length"><span class="font-medium text-text-default">CC:</span> {{ recipientSummary(ccRecipients) }}</p>
        </div>
        <div class="flex items-center gap-2 bg-surface-muted rounded-lg px-3 py-2 mb-4 text-xs text-text-muted">
          <span class="font-medium text-text-default dark:text-white/70">Asunto:</span>
          <span>{{ subject || '(sin asunto)' }}</span>
        </div>

        <!-- Server-rendered preview: the real branded template (emails/branded_email.html) -->
        <ComposedEmailPreview
          :subject="subject"
          :greeting="greeting"
          :sections="sections"
          :footer="footer"
          :textFormats="textFormats"
          :attachment-names="[...docRefs.map(r => r.label), ...attachments.map(f => f.name)]"
        />
      </div>
    </section>

      </template>

      <template #aside>
    <!-- ── History ── -->
    <section class="bg-surface border border-border-muted rounded-xl p-5">
      <div class="flex items-center gap-2 mb-4">
        <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 class="text-sm font-semibold text-text-default dark:text-white">Historial de correos enviados</h3>
      </div>

      <EmailHistoryList
        :history="history"
        :loading="loadingHistory"
        :has-next-page="hasNextPage"
        empty-label="No se han enviado correos desde este diagnóstico."
        @load-more="loadMore"
      >
        <template #entry-meta="{ entry }">
          <span class="text-2xs text-text-subtle">· {{ templateLabel(entry.template_key) }}</span>
        </template>
      </EmailHistoryList>
    </section>
      </template>
    </TabSplitLayout>

    <MarkdownAttachmentModal
      :open="showMarkdownModal"
      :endpoint="`diagnostics/${diagnostic.id}/email/markdown-attachment/`"
      show-diagnostic-templates
      @close="showMarkdownModal = false"
      @attach="handleMarkdownAttach"
    />

    <AttachFromDocumentsModal
      :open="showAttachFromDocsModal"
      source="diagnostic"
      :entity="diagnostic"
      :templates="diagnosticTemplates"
      :preselected="docRefs.map(r => r.key)"
      @close="showAttachFromDocsModal = false"
      @attach="handleDocRefsAttach"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import BaseTabs from '~/components/base/BaseTabs.vue';
import BaseCollapse from '~/components/base/BaseCollapse.vue';
import draggable from 'vuedraggable';
import { useDiagnosticsStore } from '~/stores/diagnostics';
import { DIAGNOSTIC_STATUS } from '~/stores/diagnostics_constants';
import MarkdownAttachmentModal from '~/components/MarkdownAttachmentModal.vue';
import AttachFromDocumentsModal from '~/components/AttachFromDocumentsModal.vue';
import ComposedEmailPreview from '~/components/ComposedEmailPreview.vue';
import EmailHistoryList from '~/components/EmailHistoryList.vue';
import EmailRecipientFields from '~/components/emails/EmailRecipientFields.vue';
import TabSplitLayout from '~/components/panel/TabSplitLayout.vue';
import { useMarkdownAttachmentHandler } from '~/composables/useMarkdownAttachmentHandler';
import { useDocRefsAttachment } from '~/composables/useDocRefsAttachment';
import { validateEmailAttachments } from '~/utils/emailAttachments';
import { get_request } from '~/stores/services/request_http';
import {
  appendEmailRecipients,
  emailRecipient,
  recipientSummary,
} from '~/utils/emailRecipients';

const props = defineProps({
  diagnostic: { type: Object, required: true },
});

const store = useDiagnosticsStore();

let sectionIdSeq = 0;
const nextSectionId = () => ++sectionIdSeq;

const activeSubTab = ref('edit');
const toRecipients = ref(props.diagnostic.client?.email
  ? [emailRecipient(props.diagnostic.client.email, {
    name: props.diagnostic.client.name || '',
    clientId: props.diagnostic.client.id || null,
  })]
  : []);
const ccRecipients = ref([]);
const subject = ref('');
const defaultGreeting = ref(
  props.diagnostic.client?.name ? `Hola ${props.diagnostic.client.name}` : 'Hola',
);
const defaultFooter = ref('Quedamos atentos a tus comentarios.');
const greeting = ref(defaultGreeting.value);
const sections = ref([{ id: nextSectionId(), text: '', markdown: false }]);
const footer = ref(defaultFooter.value);
const textFormats = ref({});
const attachments = ref([]);
const { docRefs, removeDocRef, handleDocRefsAttach, appendDocRefsToFormData, resetDocRefs }
  = useDocRefsAttachment();
const showAttachFromDocsModal = ref(false);
const diagnosticTemplates = ref([]);
const fileInput = ref(null);
const sending = ref(false);
const sendSuccess = ref(false);
const sendError = ref('');

const history = ref([]);
const loadingHistory = ref(false);
const currentPage = ref(1);
const hasNextPage = ref(false);

function addSection() {
  sections.value.push({ id: nextSectionId(), text: '', markdown: false });
}
function removeSection(idx) {
  if (sections.value.length > 1) sections.value.splice(idx, 1);
}

function handleFilesChange(e) {
  const { validFiles, errors } = validateEmailAttachments(Array.from(e.target.files || []));
  sendError.value = errors.length ? errors.join(', ') : '';
  if (validFiles.length) attachments.value.push(...validFiles);
  if (fileInput.value) fileInput.value.value = '';
}

function removeAttachment(idx) {
  attachments.value.splice(idx, 1);
}

const showMarkdownModal = ref(false);
const canCreateMarkdownAttachment = computed(
  () => props.diagnostic.status === DIAGNOSTIC_STATUS.NEGOTIATING,
);

const { handleMarkdownAttach } = useMarkdownAttachmentHandler(attachments);

const canSend = computed(() => {
  if (!toRecipients.value.length) return false;
  if (!subject.value.trim()) return false;
  if (!sections.value.some(s => s.text.trim())) return false;
  return true;
});

let successTimer = null;
onBeforeUnmount(() => { clearTimeout(successTimer); });

async function handleSend() {
  sending.value = true;
  sendError.value = '';
  sendSuccess.value = false;

  const formData = new FormData();
  appendEmailRecipients(formData, toRecipients.value, ccRecipients.value);
  formData.append('subject', subject.value.trim());
  formData.append('greeting', greeting.value.trim());
  formData.append('sections', JSON.stringify(
    sections.value.filter(s => s.text.trim()).map(s => ({ text: s.text, markdown: !!s.markdown })),
  ));
  formData.append('footer', footer.value.trim());
  formData.append('text_formats', JSON.stringify(textFormats.value));
  for (const file of attachments.value) {
    formData.append('attachments', file);
  }
  appendDocRefsToFormData(formData);

  const result = await store.sendCustomEmail(props.diagnostic.id, formData);
  sending.value = false;

  if (result.success) {
    sendSuccess.value = true;
    resetForm();
    await loadHistory(1);
    clearTimeout(successTimer);
    successTimer = setTimeout(() => { sendSuccess.value = false; }, 5000);
  } else {
    sendError.value = result.error && result.error !== 'send_failed'
      ? result.error
      : 'Error al enviar el correo. Intenta de nuevo.';
  }
}

function resetForm() {
  ccRecipients.value = [];
  subject.value = '';
  greeting.value = defaultGreeting.value;
  footer.value = defaultFooter.value;
  sections.value = [{ id: nextSectionId(), text: '', markdown: false }];
  attachments.value = [];
  resetDocRefs();
  if (fileInput.value) fileInput.value.value = '';
}

async function loadHistory(page = 1) {
  loadingHistory.value = true;
  const result = await store.fetchEmailHistory(props.diagnostic.id, page);
  if (result.success) {
    if (page === 1) history.value = result.data.results;
    else history.value.push(...result.data.results);
    currentPage.value = result.data.page;
    hasNextPage.value = result.data.has_next;
  }
  loadingHistory.value = false;
}
function loadMore() { return loadHistory(currentPage.value + 1); }

// Status/date/expand rendering now lives in EmailHistoryList; only the
// diagnostics-specific template label stays here (passed via #entry-meta).
const TEMPLATE_LABELS = {
  diagnostic_custom_email: 'Seguimiento',
  diagnostic_initial_sent: 'Doc 1',
  diagnostic_final_sent: 'Final',
  diagnostic_documents_sent: 'Documentos',
};
function templateLabel(key) { return TEMPLATE_LABELS[key] || key; }

async function loadDefaults() {
  const result = await store.fetchEmailDefaults(props.diagnostic.id);
  if (result.success && result.data) {
    if (result.data.recipient_email) {
      toRecipients.value = [emailRecipient(result.data.recipient_email, {
        name: props.diagnostic.client?.name || '',
        clientId: props.diagnostic.client?.id || null,
      })];
    }
    if (result.data.subject) subject.value = result.data.subject;
    if (result.data.greeting) {
      defaultGreeting.value = result.data.greeting;
      greeting.value = result.data.greeting;
    }
    if (result.data.footer) {
      defaultFooter.value = result.data.footer;
      footer.value = result.data.footer;
    }
  }
}

async function loadDiagnosticTemplates() {
  try {
    const res = await get_request('diagnostic-templates/');
    diagnosticTemplates.value = res.data || [];
  } catch (e) {
    diagnosticTemplates.value = [];
  }
}

onMounted(() => {
  Promise.all([loadDefaults(), loadHistory(), loadDiagnosticTemplates()]);
});
</script>
