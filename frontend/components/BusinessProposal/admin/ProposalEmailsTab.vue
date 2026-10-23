<template>
  <div class="space-y-5">
    <section class="rounded-xl border border-border-muted bg-surface p-5" data-testid="proposal-email-intro-card">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 class="text-sm font-semibold text-text-default">Mensaje personalizado del correo de envío</h3>
          <p class="mt-1 max-w-3xl text-xs leading-relaxed text-text-muted">
            Cuenta qué problema concreto tiene el cliente, cómo lo resuelve esta propuesta y qué resultado de negocio espera conseguir.
            Este mensaje aparece después del cuerpo predefinido y antes de los bloques comerciales.
          </p>
        </div>
        <span
          class="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide"
          :class="normalizedEmailIntro ? 'bg-success-soft text-success-strong' : 'bg-warning-soft text-warning-strong'"
        >
          {{ normalizedEmailIntro ? 'Listo para enviar' : 'Requerido para enviar' }}
        </span>
      </div>

      <div class="mt-4">
        <label for="proposal-email-intro" class="mb-1 block text-xs font-medium text-text-muted">
          Mensaje para {{ proposal.client_name || 'el cliente' }}
        </label>
        <BaseRichTextEditor
          id="proposal-email-intro"
          v-model="emailIntroDraft"
          profile="email"
          :format="emailIntroFormat"
          @update:format="emailIntroFormat = $event"
          :rows="7"
          :error="Boolean(emailIntroError)"
          placeholder="Ej. Esta propuesta resuelve… mediante… para lograr…"
          data-testid="proposal-email-intro"
         />
        <p class="mt-1 text-xs text-text-subtle">
          Usa Visual para dar formato o Fuente para editar Markdown. El borrador puede guardarse vacío; se requiere contenido para enviarlo.
        </p>
      </div>

      <div v-if="emailIntroError" class="mt-3 rounded-lg border border-danger-strong/30 bg-danger-soft px-3 py-2 text-sm text-danger-strong" role="alert">
        {{ emailIntroError }}
      </div>

      <div class="mt-4 flex flex-wrap justify-end gap-2">
        <BaseButton variant="secondary" size="sm" @click="previewEmailIntro">
          <BaseActionIcon action="view" />
          Vista previa
        </BaseButton>
        <BaseButton
          variant="primary"
          size="sm"
          :loading="savingEmailIntro"
          :disabled="!isEmailIntroDirty || savingEmailIntro"
          disabled-reason="Modifica el mensaje antes de guardarlo."
          data-testid="proposal-email-intro-save"
          @click="saveEmailIntro"
        >
          {{ savingEmailIntro ? 'Guardando…' : 'Guardar mensaje' }}
        </BaseButton>
      </div>
    </section>

    <TabSplitLayout v-if="hasFollowupComposer">
      <template #main>
    <!-- ── Email composer ── -->
    <section class="bg-surface border border-border-muted rounded-xl p-5">
      <div class="flex items-center gap-2 mb-5">
        <svg class="w-5 h-5 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <h3 class="text-sm font-semibold text-text-default">{{ activeMode === 'proposal' ? 'Correo de seguimiento' : 'Correo general' }}</h3>
      </div>

      <!-- Mode switcher -->
      <div class="inline-flex items-center bg-surface-raised rounded-full p-0.5 mb-4 gap-0.5">
        <button type="button"
          :class="activeMode === 'proposal'
            ? 'bg-primary text-white shadow-sm'
            : 'text-text-muted hover:text-text-default'"
          class="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200"
          @click="activeMode = 'proposal'">
          Seguimiento
          <span
            title="Registra el envío como actividad de la propuesta y actualiza la fecha de seguimiento del vendedor."
            class="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border text-[9px] font-bold cursor-help leading-none"
            :class="activeMode === 'proposal' ? 'border-white/50 text-white/80' : 'border-border-default text-text-subtle dark:border-green-light/40 dark:text-green-light/40'"
          >?</span>
        </button>
        <button type="button"
          :class="activeMode === 'branded'
            ? 'bg-primary text-white shadow-sm'
            : 'text-text-muted hover:text-text-default'"
          class="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200"
          @click="activeMode = 'branded'">
          General
          <span
            title="Envío de marca genérico. No registra actividad ni afecta el seguimiento de la propuesta."
            class="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full border text-[9px] font-bold cursor-help leading-none"
            :class="activeMode === 'branded' ? 'border-white/50 text-white/80' : 'border-border-default text-text-subtle dark:border-green-light/40 dark:text-green-light/40'"
          >?</span>
        </button>
      </div>

      <!-- Sub-tab switcher -->
      <div class="flex gap-4 border-b border-border-muted mb-5">
        <button type="button"
          class="pb-2 text-sm transition-colors border-b-2"
          :class="activeSubTab === 'edit'
            ? 'border-emerald-600 text-text-brand  font-semibold'
            : 'border-transparent text-text-muted hover:text-text-default'"
          @click="activeSubTab = 'edit'">
          Editar
        </button>
        <button type="button"
          class="pb-2 text-sm transition-colors border-b-2"
          :class="activeSubTab === 'preview'
            ? 'border-emerald-600 text-text-brand  font-semibold'
            : 'border-transparent text-text-muted hover:text-text-default'"
          @click="activeSubTab = 'preview'">
          Vista previa
        </button>
      </div>

      <!-- ── Edit sub-tab ── -->
      <div v-if="activeSubTab === 'edit'" class="space-y-4">
        <EmailRecipientFields
          v-model:toRecipients="toRecipients"
          v-model:ccRecipients="ccRecipients"
          test-id-prefix="proposal-email"
        />

        <!-- Subject -->
        <div>
          <label class="block text-xs text-text-muted mb-1">Asunto</label>
          <input v-model="subject" type="text" placeholder="Asunto del correo"
            class="bg-input-bg w-full px-3 py-2 border border-border-default dark:border-white/[0.08]  dark:text-white dark:placeholder:text-green-light/40 rounded-lg text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring" />
        </div>

        <!-- Greeting -->
        <div>
          <label class="block text-xs text-text-muted mb-1">Saludo</label>
          <input v-model="greeting" type="text" placeholder="Hola Carlos"
            class="bg-input-bg w-full px-3 py-2 border border-border-default dark:border-white/[0.08]  dark:text-white dark:placeholder:text-green-light/40 rounded-lg text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring" />
        </div>

        <!-- Sections (draggable) -->
        <div>
          <label class="block text-xs text-text-muted mb-2">Secciones del correo</label>
          <draggable v-model="sections" item-key="id" handle=".drag-handle" ghost-class="opacity-30"
            class="space-y-3">
            <template #item="{ element: section, index: idx }">
              <div class="bg-surface-raised rounded-lg p-3 border border-border-muted">
                <div class="flex items-center gap-2 mb-2">
                  <span class="drag-handle cursor-grab text-text-subtle dark:text-green-light/40 hover:text-text-muted select-none text-sm">⠿</span>
                  <span class="text-[10px] text-text-subtle dark:text-green-light/40 uppercase tracking-wide">Sección {{ idx + 1 }}</span>

                  <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar" title="Eliminar" v-if="sections.length > 1" @click="removeSection(idx)">
                    <BaseActionIcon action="delete" />
                  </BaseButton>
                </div>
                <BaseRichTextEditor v-model="section.text" :format="section.markdown ? 'markdown_html_v1' : 'plain'" @update:format="section.markdown = true" rows="3" placeholder="Escribe el contenido de esta sección..."
                  class="bg-input-bg w-full px-3 py-2 border border-border-default dark:border-white/[0.08]  dark:text-white dark:placeholder:text-green-light/40 rounded-lg text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring resize-y"  />

              </div>
            </template>
          </draggable>
          <BaseButton variant="secondary" size="sm" class="mt-3" @click="addSection">
            <BaseActionIcon action="create" />
            Agregar sección
          </BaseButton>
        </div>

        <!-- Footer -->
        <div>
          <label class="block text-xs text-text-muted mb-1">Pie de correo</label>
          <BaseRichTextEditor v-model="footer" :format="textFormats['/footer'] || 'plain'" @update:format="textFormats['/footer'] = $event" rows="2" placeholder="Texto de cierre..."
            class="bg-input-bg w-full px-3 py-2 border border-border-default dark:border-white/[0.08]  dark:text-white dark:placeholder:text-green-light/40 rounded-lg text-sm focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring resize-y"  />
        </div>

        <!-- Attachments -->
        <div>
          <label class="block text-xs text-text-muted mb-1">Adjuntos</label>
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
                <span class="px-1.5 py-0.5 bg-primary-soft text-text-brand rounded text-[10px] font-medium">Documento</span>
                <span class="text-xs text-text-default truncate">{{ ref.label }}</span>
              </span>
              <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar" title="Eliminar" @click="removeDocRef(idx)">
                <BaseActionIcon action="delete" />
              </BaseButton>
            </div>
            <div v-for="(file, idx) in attachments" :key="`file-${idx}`"
              class="flex items-center justify-between py-1.5 px-3 bg-surface-raised rounded-lg">
              <span class="text-xs text-text-default truncate">{{ file.name }}</span>
              <BaseButton variant="danger-ghost" icon-only size="sm" aria-label="Eliminar" title="Eliminar" @click="removeAttachment(idx)">
                <BaseActionIcon action="delete" />
              </BaseButton>
            </div>
          </div>
        </div>

        <!-- Send button -->
        <div class="flex items-center justify-between pt-2">
          <p v-if="sendError" class="text-xs text-red-500">{{ sendError }}</p>
          <span v-else />
          <BaseButton variant="primary" size="sm" :disabled="!canSend" :loading="sending" @click="handleSend">
            <BaseActionIcon v-if="!sending" action="send" />
            {{ sending ? 'Enviando...' : 'Enviar correo' }}
          </BaseButton>
        </div>
      </div>

      <!-- ── Preview sub-tab ── -->
      <div v-else>
        <div class="mb-3 space-y-1 rounded-lg bg-surface-raised px-3 py-2 text-xs text-text-muted">
          <p><span class="font-medium text-text-default">Para:</span> {{ recipientSummary(toRecipients) || '—' }}</p>
          <p v-if="ccRecipients.length"><span class="font-medium text-text-default">CC:</span> {{ recipientSummary(ccRecipients) }}</p>
        </div>
        <!-- Subject badge -->
        <div class="flex items-center gap-2 bg-surface-raised rounded-lg px-3 py-2 mb-4 text-xs text-text-muted">
          <span class="font-medium text-text-default">Asunto:</span>
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
          :proposal-id="proposal.id"
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
        <h3 class="text-sm font-semibold text-text-default">Historial de correos enviados</h3>
      </div>

      <EmailHistoryList
        :history="history"
        :loading="loadingHistory"
        :has-next-page="hasNextPage"
        empty-label="No se han enviado correos desde esta propuesta."
        @load-more="loadMore"
      />
    </section>
      </template>
    </TabSplitLayout>

    <section v-else class="rounded-xl border border-border-muted bg-surface-raised px-5 py-4">
      <p class="text-sm font-medium text-text-default">El historial y los correos de seguimiento aparecerán después del primer envío.</p>
      <p class="mt-1 text-xs text-text-muted">Mientras la propuesta esté en borrador, prepara y guarda aquí el mensaje personalizado.</p>
    </section>

    <MarkdownAttachmentModal
      :open="showMarkdownModal"
      :endpoint="`proposals/${proposal.id}/proposal-email/markdown-attachment/`"
      @close="showMarkdownModal = false"
      @attach="handleMarkdownAttach"
    />

    <AttachFromDocumentsModal
      :open="showAttachFromDocsModal"
      source="proposal"
      :entity="proposal"
      :preselected="docRefs.map(r => r.key)"
      @close="showAttachFromDocsModal = false"
      @attach="handleDocRefsAttach"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount, onMounted } from 'vue';
import draggable from 'vuedraggable';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useMarkdownAttachmentHandler } from '~/composables/useMarkdownAttachmentHandler';
import { validateEmailAttachments } from '~/utils/emailAttachments';
import MarkdownAttachmentModal from '~/components/MarkdownAttachmentModal.vue';
import AttachFromDocumentsModal from '~/components/AttachFromDocumentsModal.vue';
import ComposedEmailPreview from '~/components/ComposedEmailPreview.vue';
import EmailHistoryList from '~/components/EmailHistoryList.vue';
import EmailRecipientFields from '~/components/emails/EmailRecipientFields.vue';
import TabSplitLayout from '~/components/panel/TabSplitLayout.vue';
import { useDocRefsAttachment } from '~/composables/useDocRefsAttachment';
import {
  appendEmailRecipients,
  emailRecipient,
  recipientSummary,
} from '~/utils/emailRecipients';

const notify = usePanelNotify();

const props = defineProps({
  proposal: { type: Object, required: true },
});
const emit = defineEmits(['email-intro-saved', 'dirty-state-change', 'open-email-preview']);

const activeMode = ref('proposal');

const basePath = computed(() =>
  activeMode.value === 'proposal' ? 'proposal-email' : 'branded-email',
);

const proposalStore = useProposalStore();

// ── Initial proposal email message ──
const emailIntroDraft = ref(props.proposal.email_intro || '');
const savedEmailIntro = ref(props.proposal.email_intro || '');
const emailIntroFormat = ref(props.proposal.text_formats?.['/email_intro'] || 'plain');
const savedEmailIntroFormat = ref(emailIntroFormat.value);
const savingEmailIntro = ref(false);
const emailIntroError = ref('');
const normalizedEmailIntro = computed(() => emailIntroDraft.value.trim());
const isEmailIntroDirty = computed(() => emailIntroDraft.value !== savedEmailIntro.value || emailIntroFormat.value !== savedEmailIntroFormat.value);
const hasFollowupComposer = computed(() => [
  'sent', 'viewed', 'negotiating', 'accepted', 'rejected',
].includes(props.proposal.status));

watch(isEmailIntroDirty, (dirty) => emit('dirty-state-change', dirty), { immediate: true });
watch(
  () => props.proposal.email_intro,
  (value) => {
    const incoming = value || '';
    if (!isEmailIntroDirty.value || incoming === emailIntroDraft.value) {
      emailIntroDraft.value = incoming;
      savedEmailIntro.value = incoming;
      emailIntroFormat.value = props.proposal.text_formats?.['/email_intro'] || 'plain';
      savedEmailIntroFormat.value = emailIntroFormat.value;
    }
  },
);

async function saveEmailIntro() {
  if (!props.proposal.id || savingEmailIntro.value) return;
  savingEmailIntro.value = true;
  emailIntroError.value = '';
  const value = normalizedEmailIntro.value;
  const result = await proposalStore.updateProposal(props.proposal.id, { email_intro: value, text_formats: { ...props.proposal.text_formats, '/email_intro': emailIntroFormat.value } });
  savingEmailIntro.value = false;
  if (result.success) {
    emailIntroDraft.value = value;
    savedEmailIntro.value = value;
    savedEmailIntroFormat.value = emailIntroFormat.value;
    emit('email-intro-saved', value);
    notify.success({ title: 'Mensaje del correo guardado.' });
    return;
  }
  emailIntroError.value = result.message || 'No se pudo guardar el mensaje del correo.';
}

function previewEmailIntro() {
  emit('open-email-preview', emailIntroDraft.value);
}

let sectionIdSeq = 0;
const nextSectionId = () => ++sectionIdSeq;

// ── Composer state ──
const activeSubTab = ref('edit');
const toRecipients = ref(props.proposal.client_email
  ? [emailRecipient(props.proposal.client_email, {
    name: props.proposal.client_name || '',
    clientId: props.proposal.client_id || null,
  })]
  : []);
const ccRecipients = ref([]);
const subject = ref('');
const defaultGreeting = ref(
  props.proposal.client_name ? `Hola ${props.proposal.client_name}` : 'Hola',
);
const defaultFooter = ref('Quedamos atentos a tus comentarios.\nUn abrazo, el equipo de Project App.');
const greeting = ref(defaultGreeting.value);
const sections = ref([{ id: nextSectionId(), text: '', markdown: false }]);
const footer = ref(defaultFooter.value);
const textFormats = ref({});
const attachments = ref([]);
const { docRefs, removeDocRef, handleDocRefsAttach, appendDocRefsToFormData, resetDocRefs }
  = useDocRefsAttachment();
const showAttachFromDocsModal = ref(false);
const fileInput = ref(null);
const sending = ref(false);
const sendError = ref('');

// ── History state ──
const history = ref([]);
const loadingHistory = ref(false);
const currentPage = ref(1);
const hasNextPage = ref(false);

// ── Sections ──
function addSection() {
  sections.value.push({ id: nextSectionId(), text: '', markdown: false });
}

function removeSection(idx) {
  if (sections.value.length > 1) {
    sections.value.splice(idx, 1);
  }
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
const canCreateMarkdownAttachment = true;

const { handleMarkdownAttach } = useMarkdownAttachmentHandler(attachments);

// ── Validation ──
const canSend = computed(() => {
  if (!toRecipients.value.length) return false;
  if (!subject.value.trim()) return false;
  if (!sections.value.some(s => s.text.trim())) return false;
  return true;
});

async function handleSend() {
  sending.value = true;
  sendError.value = '';

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

  const result = await proposalStore.sendComposedEmail(props.proposal.id, formData, basePath.value);
  sending.value = false;

  if (result.success) {
    notify.success('Correo enviado correctamente.');
    resetForm();
    await loadHistory(1);
  } else {
    notify.error('Error al enviar el correo. Intenta de nuevo.');
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

// ── History ──
async function loadHistory(page = 1) {
  loadingHistory.value = true;
  const result = await proposalStore.fetchEmailHistory(props.proposal.id, page, basePath.value);
  if (result.success) {
    if (page === 1) {
      history.value = result.data.results;
    } else {
      history.value.push(...result.data.results);
    }
    currentPage.value = result.data.page;
    hasNextPage.value = result.data.has_next;
  }
  loadingHistory.value = false;
}

async function loadMore() {
  await loadHistory(currentPage.value + 1);
}

// Status/date/expand rendering now lives in the shared EmailHistoryList.

async function loadDefaults() {
  const result = await proposalStore.fetchEmailDefaults(props.proposal.id, basePath.value);
  if (result.success && result.data) {
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

watch(activeMode, async () => {
  resetForm();
  if (hasFollowupComposer.value) {
    await Promise.all([loadDefaults(), loadHistory()]);
  }
});

onMounted(() => {
  if (hasFollowupComposer.value) {
    Promise.all([loadDefaults(), loadHistory()]);
  }
});

watch(hasFollowupComposer, (enabled, wasEnabled) => {
  if (enabled && !wasEnabled) Promise.all([loadDefaults(), loadHistory()]);
});

onBeforeUnmount(() => emit('dirty-state-change', false));
</script>
