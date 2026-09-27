<template>
  <div class="w-full">
    <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
      <div>
        <NuxtLink
          :to="localePath('/panel/documents')"
          class="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text-default transition-colors"
          aria-label="Volver a documentos"
        >
        <BaseActionIcon action="back" />
          Volver a documentos
        </NuxtLink>
        <h1 class="text-2xl font-light text-text-default mt-2">Nuevo Documento</h1>
        <p class="text-sm text-text-muted mt-1">Crea un documento a partir de Markdown (pegado o subido).</p>
      </div>
      <!-- Sólo acciones: lo que falta para crear se dice bajo cada campo al
           intentarlo, así la fila no cambia de alto ni desalinea Cancelar. -->
      <div class="hidden items-center gap-3 panel-landscape:flex" data-testid="doc-create-actions">
        <NuxtLink :to="localePath('/panel/documents')" class="text-sm text-text-muted hover:text-text-default">
          Cancelar
        </NuxtLink>
        <BaseButton
          variant="primary"
          size="md"
          type="submit"
          form="doc-create-form"
          :loading="documentStore.isUpdating"
        >
          {{ documentStore.isUpdating ? 'Creando...' : 'Crear Documento' }}
        </BaseButton>
      </div>
    </div>

    <form
      id="doc-create-form"
      class="grid grid-cols-1 gap-6 panel-landscape:grid-cols-[20rem_minmax(0,1fr)] panel-desktop:grid-cols-[24rem_minmax(0,1fr)]"
      @submit.prevent="handleSubmit"
    >
      <!-- En un formulario de creación no hay versión guardada a la que
           volver, así que no se ofrece "Descartar cambios": la salida sin
           guardar vive en el diálogo. -->
      <UnsavedChangesNotice
        v-if="hasChanges"
        class="panel-landscape:col-span-2"
        :title="unsavedTitle"
        :detail="unsavedDetail"
        message="Este documento todavía no existe. Si sales de esta página, se pierde."
        :can-save="false"
        :can-discard="false"
        testid="doc-create-unsaved-notice"
      />

      <aside
        class="bg-surface rounded-xl shadow-sm border border-border-muted p-5 sm:p-6
               panel-landscape:sticky panel-landscape:top-6 panel-landscape:self-start panel-landscape:max-h-[calc(100vh-7rem)] panel-landscape:overflow-y-auto"
      >
        <div class="space-y-6">
          <div class="space-y-4">
            <h2 class="text-xs uppercase tracking-wide font-semibold text-text-muted">Identificación</h2>
            <!-- aria-required y no `required`: la validación nativa cortaría el
                 envío en el título y el aviso del contenido no llegaría a verse. -->
            <BaseFormField
              v-slot="{ errorId }"
              label="Título"
              for="doc-title"
              required
              :error="titleError"
            >
              <input
                id="doc-title"
                v-model="form.title"
                type="text"
                aria-required="true"
                placeholder="Mi Documento"
                :aria-describedby="errorId"
                class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm bg-surface text-text-default placeholder:text-text-subtle
                       focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              />
            </BaseFormField>
            <div class="rounded-xl border border-border-default bg-surface-raised p-3">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <p class="text-sm font-medium text-text-default">Notas</p>
                    <BaseBadge v-if="hasNotes" variant="success" size="sm">Agregadas</BaseBadge>
                  </div>
                  <p class="text-xs text-text-subtle mt-1">Asunto, correo, WhatsApp y notas personalizadas.</p>
                </div>
                <BaseActionButton
                  type="button"
                  action="notes"
                  variant="secondary"
                  :label="notesActionLabel"
                  data-testid="doc-client-note-open"
                  @click="showClientNote = true"
                />
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Cliente</label>
              <ClientAutocomplete
                v-model="form.client"
                :initial-label="clientDisplayName"
                test-id="doc-client-autocomplete"
                allow-create
                @select="onClientSelect"
                @create-new="onCreateNewClient"
              />
              <p
                v-if="suggestedFromFolder"
                class="text-xs text-text-subtle mt-1"
                data-testid="doc-client-suggested-hint"
              >
                {{ inheritedFromFolder
                  ? 'Heredado de la carpeta — puedes cambiarlo o quitarlo.'
                  : 'Sugerido por la carpeta — puedes cambiarlo o quitarlo.' }}
              </p>
              <p v-else class="text-xs text-text-subtle mt-1">
                Opcional. Las plantillas y notas pueden no tener dueño.
              </p>
            </div>

            <!-- Inline client creation: the clients module without leaving the form -->
            <div
              v-if="inlineClientOpen"
              class="rounded-xl border border-border-default bg-surface-raised p-4 space-y-3"
              data-testid="doc-inline-client"
              @keydown.enter="keepInlineClientEnter"
            >
              <p class="text-sm font-medium text-text-default">Crear cliente nuevo</p>
              <ClientFormFields
                v-model="inlineClient"
                testid-prefix="doc-inline-client"
                dense
              />
              <div class="flex justify-end gap-2">
                <BaseButton type="button" variant="secondary" size="sm" @click="inlineClientOpen = false">
                  Cancelar
                </BaseButton>
                <BaseButton
                  type="button"
                  variant="primary"
                  size="sm"
                  :disabled="creatingClient"
                  data-testid="doc-inline-client-save"
                  @click="createInlineClient"
                >
                  {{ creatingClient ? 'Creando...' : 'Crear cliente' }}
                </BaseButton>
              </div>
            </div>

            <ProjectSelect
              v-model="form.project"
              :client-profile-id="form.client"
              :client-label="clientDisplayName"
              :allow-no-client="true"
              :auto-select-single="true"
              testid="doc-project-select"
              @select="onProjectSelect"
            />
          </div>

          <hr class="border-border-muted" />

          <div class="space-y-4">
            <h2 class="text-xs uppercase tracking-wide font-semibold text-text-muted">Organización</h2>
            <DocumentFolderSelect v-model="form.folder_id" testid="doc-folder-select" />
            <p class="text-xs text-text-subtle">
              El documento iniciará en Borrador. Podrás agregar estados y señales al terminar de crearlo.
            </p>
          </div>

          <hr class="border-border-muted" />

          <div class="space-y-4">
            <h2 class="text-xs uppercase tracking-wide font-semibold text-text-muted">Opciones de exportación</h2>
            <div>
              <label class="block text-sm font-medium text-text-default mb-1">Idioma</label>
              <select
                v-model="form.language"
                class="w-full px-4 py-2.5 border border-border-default rounded-xl text-sm bg-surface text-text-default
                       focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
              >
                <option value="es">Español</option>
                <option value="en">English</option>
              </select>
            </div>
            <div class="space-y-1">
              <label
                v-for="option in coverOptions"
                :key="option.key"
                class="flex items-center gap-3 cursor-pointer py-1.5 px-1 select-none"
                :data-testid="option.testId"
              >
                <BaseToggle v-model="form[option.key]" />
                <span class="text-sm font-medium text-text-default">{{ option.label }}</span>
              </label>
              <p class="text-xs text-text-subtle pt-1 px-1" data-testid="doc-included-pages">
                El PDF incluirá: {{ includedPagesLabel }}
              </p>
            </div>
          </div>
        </div>
      </aside>

      <section
        class="bg-surface rounded-xl shadow-sm border border-border-muted p-5 sm:p-6
               flex flex-col min-w-0"
      >
        <div class="flex gap-1 mb-5 bg-surface-raised rounded-xl p-1 w-full sm:w-fit">
          <!-- design-tokens: allow-raw-button — segmented mode control -->
          <button
            v-for="tab in modeTabs"
            :key="tab.id"
            type="button"
            :class="[
              'inline-flex items-center justify-center gap-2 flex-1 sm:flex-none sm:min-w-[11rem] px-4 py-2 text-sm rounded-lg transition-all',
              mode === tab.id
                ? 'bg-surface shadow-sm font-medium text-text-default ring-1 ring-focus-ring/20'
                : 'text-text-muted hover:text-text-default'
            ]"
            @click="mode = tab.id"
          >
              <BaseActionIcon :action="tab.action" />
            {{ tab.label }}
          </button>
        </div>

        <!-- Un campo por modo: cada uno se monta con su control, así el aviso
             queda enlazado al editor o al archivo que se está mostrando. -->
        <BaseFormField
          v-if="mode === 'paste'"
          ref="contentField"
          :error="contentError"
          class="flex min-h-0 flex-1 flex-col"
        >
          <DocumentEditorContent
            v-model="form.content_markdown"
            textarea-id="doc-markdown"
            label="Contenido Markdown"
            required
            placeholder="# Mi Documento&#10;&#10;Escribe o pega tu contenido en formato Markdown..."
            :theme="form.template_style"
            pane-class="min-h-[24rem] panel-desktop:h-[calc(100vh-20rem)]"
          >
            <template #tools>
              <BaseSegmented
                v-model="form.template_style"
                size="sm"
                :options="templateStyleOptions"
                aria-label="Estilo de plantilla"
              />
            </template>
          </DocumentEditorContent>
        </BaseFormField>

        <BaseFormField
          v-if="mode === 'upload'"
          v-slot="{ errorId, invalid }"
          ref="contentField"
          label="Archivo Markdown (.md)"
          required
          :error="contentError"
          class="flex flex-1 flex-col"
        >
          <div
            :class="[
              'border-2 border-dashed rounded-xl p-8 sm:p-10 text-center transition-colors',
              isDragging
                ? 'border-emerald-500 bg-primary-soft'
                : 'border-border-default hover:border-border-default'
            ]"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="handleDragLeave"
            @drop.prevent="handleDrop"
          >
            <svg class="w-10 h-10 mx-auto text-text-subtle" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p class="mt-3 text-sm text-text-muted">
              Arrastra un archivo <code class="text-xs px-1 py-0.5 bg-surface-raised rounded">.md</code> aquí
            </p>
            <p class="text-xs text-text-subtle mt-1">o</p>
            <label
              class="mt-3 inline-flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-xl text-sm font-medium
                     hover:bg-primary cursor-pointer transition-colors shadow-sm"
            >
              Seleccionar archivo
              <input type="file" accept=".md,.markdown,.txt" class="hidden" @change="handleFileUpload" />
            </label>
            <p v-if="uploadedFileName" class="mt-4 text-xs text-text-muted">
              <span class="font-medium">Archivo:</span> {{ uploadedFileName }}
            </p>
          </div>
          <!-- El campo enlaza su aviso al primer control, que aquí es el input
               de archivo oculto: el contenido cargado lleva su propio enlace. -->
          <textarea
            v-model="form.content_markdown"
            rows="12"
            readonly
            placeholder="El contenido del archivo aparecerá aquí..."
            :aria-invalid="invalid || undefined"
            :aria-describedby="errorId"
            class="w-full mt-4 px-4 py-3 border border-border-default rounded-xl text-sm font-mono leading-relaxed
                   bg-surface-raised text-text-muted placeholder:text-text-subtle outline-none resize-y"
          ></textarea>
        </BaseFormField>

        <div
          class="mt-5 flex flex-wrap items-center justify-end gap-4 panel-landscape:hidden"
          data-testid="doc-create-actions-compact"
        >
          <NuxtLink :to="localePath('/panel/documents')" class="text-sm text-text-muted hover:text-text-default">
            Cancelar
          </NuxtLink>
          <BaseButton
            variant="primary"
            size="md"
            type="submit"
            class="sm:px-6"
            :loading="documentStore.isUpdating"
          >
            {{ documentStore.isUpdating ? 'Creando...' : 'Crear Documento' }}
          </BaseButton>
        </div>
      </section>
    </form>

    <DocumentClientNoteModal
      v-model="showClientNote"
      :subject="form.client_email_subject"
      :email-body="form.client_email_body"
      :whatsapp-message="form.client_whatsapp_message"
      :custom-notes="form.client_custom_notes"
      mode="draft"
      @submit="applyClientNoteDraft"
    />

    <!-- Sin este modal el guard abriría un diálogo que nadie renderiza y la
         navegación quedaría bloqueada en silencio. -->
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      :require-type-text="confirmState.requireTypeText"
      :hide-cancel="confirmState.hideCancel"
      :secondary-text="confirmState.secondaryText"
      :secondary-variant="confirmState.secondaryVariant"
      :secondary-hint="confirmState.secondaryHint"
      :loading="confirmState.busy"
      @confirm="handleConfirmed"
      @secondary="handleSecondaryAction"
      @cancel="handleCancelled"
    />
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch, nextTick } from 'vue';
import DocumentEditorContent from '~/components/panel/documents/DocumentEditorContent.vue';
import DocumentClientNoteModal from '~/components/panel/documents/DocumentClientNoteModal.vue';
import DocumentFolderSelect from '~/components/panel/documents/DocumentFolderSelect.vue';
import ClientAutocomplete from '~/components/ui/ClientAutocomplete.vue';
import ProjectSelect from '~/components/accounting/ProjectSelect.vue';
import ClientFormFields from '~/components/clients/ClientFormFields.vue';
import UnsavedChangesNotice from '~/components/panel/UnsavedChangesNotice.vue';
import { clientFormPayload, emptyClientForm } from '~/utils/billingCode';
import { useProposalClientsStore } from '~/stores/proposal_clients';
import { useClientProjectCascade } from '~/composables/useClientProjectCascade';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useUnsavedGuard } from '~/composables/useUnsavedGuard';
import { describeIncludedPages } from '~/utils/documentCoverPages';
import { folderPathLabel, resolveFolderPreselection } from '~/utils/folderOptions';

const localePath = useLocalePath();
definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const documentStore = useDocumentStore();
const folderStore = useDocumentFolderStore();
const clientsStore = useProposalClientsStore();
const notify = usePanelNotify();
const mode = ref('paste');
const uploadedFileName = ref('');
const showClientNote = ref(false);
const isDragging = ref(false);
const route = useRoute();

const clientDisplayName = ref('');
// Una decisión del operador (elegir, crear o limpiar cliente) apaga la
// sugerencia por carpeta para siempre en este form.
const clientTouched = ref(false);
const suggestedFromFolder = ref(false);
// Distingue el dato firme (la carpeta lo dice) de la conjetura por mayoría.
const inheritedFromFolder = ref(false);
const inlineClientOpen = ref(false);
const inlineClient = ref(emptyClientForm());
const creatingClient = ref(false);

const form = reactive({
  title: '',
  client: null,
  project: null,
  language: 'es',
  include_portada: true,
  include_subportada: true,
  include_contraportada: true,
  content_markdown: '',
  client_email_subject: '',
  client_email_body: '',
  client_whatsapp_message: '',
  client_custom_notes: [],
  folder_id: null,
  template_style: 'professional',
});

const CREATE_FIELD_LABELS = {
  title: 'título',
  client: 'cliente',
  project: 'proyecto',
  language: 'idioma',
  include_portada: 'portada',
  include_subportada: 'subportada',
  include_contraportada: 'contraportada',
  content_markdown: 'contenido',
  client_email_subject: 'asunto del correo',
  client_email_body: 'correo para el cliente',
  client_whatsapp_message: 'WhatsApp para el cliente',
  client_custom_notes: 'notas adicionales',
  folder_id: 'carpeta',
  template_style: 'estilo de plantilla',
};

// `save` queda en null a propósito: handleSubmit navega al editor, y llamarlo
// desde dentro del guard de navegación sería navegación reentrante. Quedan dos
// salidas —seguir editando o salir sin guardar—, que es lo honesto acá.
const {
  hasChanges,
  unsavedTitle,
  unsavedDetail,
  commit: commitBaseline,
  confirmState,
  handleConfirmed,
  handleSecondaryAction,
  handleCancelled,
} = useUnsavedGuard({
  snapshot: () => ({ ...form }),
  labels: CREATE_FIELD_LABELS,
});

// El refresh acá sólo recarga carpetas: no pisa el formulario, así
// que no necesita el guard.
usePanelRefresh(() => folderStore.fetchFolders());

// «Nuevo documento» trae la carpeta abierta en `?folder=`, y puede ser una del
// archivado automático (o una archivada) que el backend rechaza como destino.
// Se propone la elegible más cercana hacia arriba y se dice por qué: se fija
// antes de que corra el watcher, así nunca se sugiere un cliente desde la otra.
function applyFolderPreselection(raw, listLoaded) {
  if (!listLoaded) {
    // Sin la lista no hay cómo validarla: queda la pedida y decide el backend.
    const numeric = Number(raw);
    if (raw != null && raw !== '' && Number.isInteger(numeric)) form.folder_id = numeric;
    return;
  }
  const { folderId, requested } = resolveFolderPreselection(folderStore.folders, raw);
  if (folderId != null) form.folder_id = folderId;
  if (!requested || folderId === Number(requested.id)) return;
  const reason = requested.is_archived
    ? `«${requested.name}» está archivada.`
    : `«${requested.name}» sólo recibe documentos generados por el sistema.`;
  notify.info({
    title: 'Carpeta ajustada',
    detail: folderId != null
      ? `${reason} Se propone «${folderPathLabel(folderStore.folders, folderId)}»; puedes cambiarla.`
      : `${reason} El documento queda sin carpeta; puedes elegir una.`,
    duration: 7000,
  });
}

onMounted(async () => {
  const loaded = await folderStore.fetchFolders();
  applyFolderPreselection(route.query.folder, Boolean(loaded?.success));
  // Deja correr el watcher de carpeta y espera su sugerencia: recién con todo
  // lo que puso el arranque en su sitio, la baseline representa "sin tocar".
  await nextTick();
  if (pendingFolderSuggestion) await pendingFolderSuggestion;
  commitBaseline();
});

// Crear Documento sigue disponible: lo que falta se dice bajo cada campo
// recién al intentarlo, y el rechazo del API por campo vive en el mismo lugar.
const validationAttempted = ref(false);
const apiFieldErrors = reactive({ title: '', markdown: '' });
const contentField = ref(null);

const titleError = computed(() => (
  apiFieldErrors.title
  || (validationAttempted.value && !form.title.trim()
    ? 'Escribe el título del documento.'
    : '')
));

const contentError = computed(() => (
  apiFieldErrors.markdown
  || (validationAttempted.value && !form.content_markdown.trim()
    ? 'Pega, escribe o carga el contenido Markdown.'
    : '')
));

// Corregir el valor retira el rechazo del API; un watch cubre tipear, pegar y
// cargar un archivo por igual.
watch(() => form.title, () => { apiFieldErrors.title = ''; });
watch(() => form.content_markdown, () => { apiFieldErrors.markdown = ''; });

// Bajo landscape el botón queda al pie y el título arriba, fuera de vista: sin
// llevar al operador al campo, el intento parecería no haber hecho nada.
async function revealFirstInvalidField() {
  await nextTick();
  if (titleError.value) {
    document.getElementById('doc-title')?.focus();
    return;
  }
  if (!contentError.value) return;
  contentField.value?.$el?.scrollIntoView?.({ block: 'center' });
  if (mode.value === 'paste') {
    document.getElementById('doc-markdown')?.focus({ preventScroll: true });
  }
}

const hasNotes = computed(() => [
  form.client_email_subject,
  form.client_email_body,
  form.client_whatsapp_message,
].some((value) => value.trim()) || form.client_custom_notes.length > 0);

const notesActionLabel = computed(() => (
  hasNotes.value ? 'Editar notas' : 'Agregar notas'
));

function applyClientNoteDraft(note) {
  form.client_email_subject = note.subject;
  form.client_email_body = note.emailBody;
  form.client_whatsapp_message = note.whatsappMessage;
  form.client_custom_notes = note.customNotes;
  showClientNote.value = false;
  notify.info({
    title: 'Notas aplicadas al borrador',
    detail: 'Todavía falta crear el documento para guardarlas.',
    duration: 7000,
  });
}

// Elegir cliente o proyecto es una decisión del operador: retira la
// sugerencia de la carpeta y evita que vuelva a proponerse.
const { onClientSelect, onProjectSelect } = useClientProjectCascade(
  form,
  clientDisplayName,
  {
    onOperatorChoice() {
      clientTouched.value = true;
      suggestedFromFolder.value = false;
    },
  },
);

function onCreateNewClient(typedName) {
  inlineClientOpen.value = true;
  inlineClient.value = { ...emptyClientForm(), name: typedName || '' };
}

async function createInlineClient() {
  creatingClient.value = true;
  const result = await clientsStore.createClient(clientFormPayload(inlineClient.value));
  creatingClient.value = false;
  if (result.success && result.data?.id) {
    inlineClientOpen.value = false;
    onClientSelect(result.data);
  }
}

// La caja de cliente nuevo vive dentro del formulario del documento: Enter en
// uno de sus campos lo enviaría y crearía el documento sin ese cliente. Sus
// botones conservan Enter.
function keepInlineClientEnter(event) {
  if (event.target?.tagName === 'INPUT') event.preventDefault();
}

function clearSuggestedClient() {
  form.client = null;
  clientDisplayName.value = '';
  form.project = null;
  suggestedFromFolder.value = false;
  inheritedFromFolder.value = false;
}

// La carpeta ya está diciendo de quién es: al fijarla (incluido ?folder= de
// la URL) se propone su asociación —la propia si la tiene, si no la mayoritaria
// de sus documentos. Sólo prellenado — nunca pisa una
// decisión del operador, y cambiar de carpeta re-propone o retira lo sugerido.
async function runFolderClientSuggestion(folderId) {
  if (clientTouched.value) return;
  if (form.client && !suggestedFromFolder.value) return;
  if (!Number.isInteger(folderId)) {
    if (suggestedFromFolder.value) clearSuggestedClient();
    return;
  }
  const result = await documentStore.resolveFolderAssociation(folderId);
  if (clientTouched.value) return;
  if (result.success && result.data?.client) {
    form.client = result.data.client;
    clientDisplayName.value = result.data.client_display_name || '';
    // La carpeta asociada trae también su proyecto; la heurística no.
    if (result.data.project) form.project = result.data.project;
    suggestedFromFolder.value = true;
    inheritedFromFolder.value = result.data.source === 'folder';
  } else if (suggestedFromFolder.value) {
    clearSuggestedClient();
  }
}

// Se guarda la promesa en curso para que el arranque pueda esperarla antes de
// fijar la baseline: la sugerencia llega DESPUÉS del mount y, sin esperarla,
// entrar desde una carpeta dejaría el formulario "sucio" sin que nadie lo toque.
let pendingFolderSuggestion = null;

watch(() => form.folder_id, (folderId) => {
  pendingFolderSuggestion = runFolderClientSuggestion(folderId);
});

const coverOptions = [
  { key: 'include_portada', label: 'Incluir portada', testId: 'doc-cover-portada' },
  { key: 'include_subportada', label: 'Incluir subportada', testId: 'doc-cover-subportada' },
  { key: 'include_contraportada', label: 'Incluir contraportada', testId: 'doc-cover-contraportada' },
];

// Qué páginas va a traer el PDF, en el orden en que salen: las casillas dicen
// qué se incluye, esto dice cómo queda.
const includedPagesLabel = computed(() => describeIncludedPages(form));

const templateStyleOptions = [
  { value: 'friendly', label: 'Amigable', testId: 'doc-style-friendly' },
  { value: 'professional', label: 'Profesional', testId: 'doc-style-professional' },
];

const modeTabs = [
  {
    id: 'paste',
    label: 'Pegar Markdown',
    action: 'paste',
  },
  {
    id: 'upload',
    label: 'Cargar Archivo',
    action: 'upload',
  },
];

function readMarkdownFile(file) {
  if (!file) return;
  uploadedFileName.value = file.name;
  const reader = new FileReader();
  reader.onload = (e) => {
    form.content_markdown = e.target?.result || '';
  };
  reader.readAsText(file);
}

function handleFileUpload(event) {
  readMarkdownFile(event.target.files?.[0]);
}

function handleDragLeave(event) {
  // dragleave also fires when the cursor enters a child; ignore those so the highlight doesn't flicker.
  if (!event.currentTarget.contains(event.relatedTarget)) {
    isDragging.value = false;
  }
}

function handleDrop(event) {
  isDragging.value = false;
  readMarkdownFile(event.dataTransfer?.files?.[0]);
}

async function handleSubmit() {
  validationAttempted.value = true;
  if (titleError.value || contentError.value) {
    await revealFirstInvalidField();
    return;
  }

  const payload = {
    title: form.title.trim(),
    // Siempre presentes, null incluido: es lo que permite guardar sin dueño.
    client: form.client ?? null,
    project: form.project ?? null,
    language: form.language,
    include_portada: form.include_portada,
    include_subportada: form.include_subportada,
    include_contraportada: form.include_contraportada,
    markdown: form.content_markdown,
    client_email_subject: form.client_email_subject,
    client_email_body: form.client_email_body,
    client_whatsapp_message: form.client_whatsapp_message,
    client_custom_notes: form.client_custom_notes,
    folder_id: form.folder_id,
    template_style: form.template_style,
  };

  const result = await documentStore.createFromMarkdown(payload);
  if (result.success) {
    notify.success({ title: 'Documento creado' });
    // Lo del formulario ya está persistido: re-fijar la baseline desarma el
    // guard y la redirección al editor pasa sin preguntar nada.
    commitBaseline();
    navigateTo(localePath(`/panel/documents/${result.data.id}/edit`));
  } else {
    // Título y contenido tienen campo propio; el resto de rechazos sigue en la
    // notificación con el formato de siempre.
    const { title = '', markdown = '', ...otherFieldErrors } = result.fieldErrors || {};
    apiFieldErrors.title = title;
    apiFieldErrors.markdown = markdown;
    const fieldDetail = Object.entries(otherFieldErrors)
      .map(([k, v]) => `${k}: ${v}`)
      .join(' · ');
    if (title || markdown) await revealFirstInvalidField();
    if (fieldDetail || !(title || markdown)) {
      notify.error({
        title: 'No se pudo crear el documento',
        detail: fieldDetail || result.message,
      });
    }
  }
}
</script>
