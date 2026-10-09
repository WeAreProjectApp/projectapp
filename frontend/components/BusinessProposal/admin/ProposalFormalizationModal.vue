<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useId } from 'vue';
import EmailRecipientFields from '~/components/emails/EmailRecipientFields.vue';
import { emailRecipient, recipientEmails } from '~/utils/emailRecipients';
import { useProposalFormalizationStore } from '~/stores/proposal_formalization';
import { CONTRACT_DOC_TYPES } from '~/stores/proposals_constants';

const props = defineProps({
  proposal: { type: Object, required: true },
  documents: { type: Array, default: () => [] },
});
const emit = defineEmits(['close', 'sent']);
const store = useProposalFormalizationStore();
const fieldId = useId();
const loading = ref(true);
const busy = ref(false);
const error = ref('');
const options = ref([]);
// Every document of the closing modality starts selected: one contract, or
// the product and service contracts, plus the two annexes.
const selected = ref([]);
const extraIds = ref([]);
const toRecipients = ref(props.proposal.client_email ? [emailRecipient(props.proposal.client_email)] : []);
const ccRecipients = ref([]);
const fields = ref({ subject: '', greeting: '', body: '', footer: '' });
const sections = ref([]);
const preparation = ref(null);
const pdfUrl = ref('');
const pdfTitle = ref('');
const pdfLoading = ref(false);
let previewSeq = 0;
let sectionSeq = 0;
let alive = true;

const additionalDocs = computed(() => props.documents.filter(doc => !CONTRACT_DOC_TYPES.includes(doc.document_type)));
const unavailable = computed(() => options.value.filter(doc => selected.value.includes(doc.key) && !doc.available));
const canPrepare = computed(() => !loading.value && !busy.value && !unavailable.value.length
  && (selected.value.length || extraIds.value.length) && toRecipients.value.length
  && fields.value.subject.trim() && fields.value.greeting.trim() && fields.value.body.trim());
const consumed = computed(() => preparation.value && preparation.value.status !== 'prepared');

function errorMessage(err) {
  const data = err?.response?.data;
  return data?.error || data?.detail || (data ? Object.values(data).flat().join(' ') : '') || 'No se pudo completar la operación. Intenta de nuevo.';
}

async function loadOptions() {
  loading.value = true;
  error.value = '';
  try {
    const result = await store.options(props.proposal.id);
    if (!alive) return;
    options.value = result.documents;
    selected.value = [...new Set(result.documents.map(doc => doc.key))];
    fields.value = result.defaults;
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    loading.value = false;
  }
}

function clearPdf() {
  previewSeq++;
  if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value);
  pdfUrl.value = '';
  pdfTitle.value = '';
  pdfLoading.value = false;
}

async function previewFile(file) {
  clearPdf();
  const seq = previewSeq;
  pdfTitle.value = file.filename;
  pdfLoading.value = true;
  try {
    const blob = await store.file(file.url);
    if (!alive || seq !== previewSeq) return;
    pdfUrl.value = URL.createObjectURL(blob);
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    if (seq === previewSeq) pdfLoading.value = false;
  }
}

function addSection() {
  sections.value.push({ id: ++sectionSeq, text: '', markdown: false });
}
function moveSection(index, offset) {
  const next = index + offset;
  if (next < 0 || next >= sections.value.length) return;
  const item = sections.value.splice(index, 1)[0];
  sections.value.splice(next, 0, item);
}

async function prepare() {
  busy.value = true;
  error.value = '';
  try {
    preparation.value = await store.prepare(props.proposal.id, {
      ...fields.value,
      documents: selected.value,
      additional_doc_ids: extraIds.value,
      recipient_emails: recipientEmails(toRecipients.value),
      cc_emails: recipientEmails(ccRecipients.value),
      sections: sections.value.map(({ text, markdown }) => ({ text, markdown })),
    });
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    busy.value = false;
  }
}

function edit() {
  clearPdf();
  preparation.value = null;
  error.value = '';
}

async function send() {
  busy.value = true;
  error.value = '';
  // An uncertain network response must never enable a second send automatically.
  preparation.value.status = 'sending';
  try {
    preparation.value = await store.send(props.proposal.id, preparation.value.id);
    emit('sent');
  } catch (err) {
    error.value = errorMessage(err);
    if (['expired_preparation', 'stale_preparation', 'attachment_changed'].includes(err?.response?.data?.code)) {
      clearPdf();
      preparation.value = null;
      return;
    }
    try {
      preparation.value = await store.detail(props.proposal.id, preparation.value.id);
      if (preparation.value.status === 'sent') emit('sent');
    } catch {
      preparation.value.status = 'unknown';
    }
  } finally {
    busy.value = false;
  }
}

onMounted(loadOptions);
onBeforeUnmount(() => { alive = false; clearPdf(); });
</script>

<template>
  <BaseModal :model-value="true" :kind="preparation ? 'wizard' : 'form'" :close-on-backdrop="!busy" :close-on-esc="!busy" @close="emit('close')">
    <div class="space-y-5 p-4 panel-portrait:p-6" data-testid="formalization-modal">
      <div class="flex items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold text-text-default">Formalización del proyecto</h2>
          <p class="mt-1 text-sm text-text-muted">{{ preparation ? 'Revisa el correo y los archivos que se enviarán.' : 'Prepara la documentación para revisión y firma.' }}</p>
        </div>
        <BaseButton variant="secondary" size="sm" :disabled="busy" disabled-reason="Espera a que termine la operación." @click="emit('close')">Cerrar</BaseButton>
      </div>
      <p v-if="error" role="alert" class="rounded-lg bg-danger-soft p-3 text-sm text-danger-strong">{{ error }}</p>
      <p v-if="loading" role="status" class="text-sm text-text-muted">Cargando documentos y plantilla…</p>
      <template v-else-if="!preparation">
        <fieldset class="space-y-3 rounded-lg border border-border-muted p-4">
          <legend class="px-1 font-medium text-text-default">Documentos adjuntos</legend>
          <label v-for="doc in options" :key="doc.key" class="block text-sm text-text-default">
            <span class="flex items-center gap-2">
              <input v-model="selected" type="checkbox" :value="doc.key" :data-testid="`formalization-select-${doc.key}`" />
              {{ doc.label }}
            </span>
            <span class="ml-6 block text-xs text-text-muted">{{ doc.description }}</span>
            <span v-if="doc.error" class="ml-6 block text-xs text-danger-strong">{{ doc.error }} Puedes corregirlo en la propuesta o desmarcar este adjunto.</span>
          </label>
          <label v-for="doc in additionalDocs" :key="doc.id" class="flex items-center gap-2 text-sm text-text-default">
            <input v-model="extraIds" type="checkbox" :value="doc.id" /> {{ doc.title }}
          </label>
        </fieldset>
        <EmailRecipientFields v-model:toRecipients="toRecipients" v-model:ccRecipients="ccRecipients" test-id-prefix="formalization-recipients" />
        <BaseFormRow :cols="2" :gap="4">
          <BaseFormField label="Asunto" :for="`${fieldId}-subject`">
            <BaseInput :id="`${fieldId}-subject`" v-model="fields.subject" maxlength="500" data-testid="formalization-subject" />
          </BaseFormField>
          <BaseFormField label="Saludo" :for="`${fieldId}-greeting`">
            <BaseInput :id="`${fieldId}-greeting`" v-model="fields.greeting" maxlength="1000" />
          </BaseFormField>
        </BaseFormRow>
        <label class="block text-sm text-text-default">Introducción
          <textarea v-model="fields.body" rows="3" maxlength="10000" class="mt-1 w-full rounded-lg border border-border-default bg-surface p-2" />
        </label>
        <div v-for="(section, index) in sections" :key="section.id" class="space-y-2 rounded-lg border border-border-muted p-3">
          <label class="block text-sm text-text-default">Sección adicional {{ index + 1 }}
            <textarea v-model="section.text" rows="4" maxlength="10000" class="mt-1 w-full rounded-lg border border-border-default bg-surface p-2" :data-testid="`formalization-section-${index}`" />
          </label>
          <div class="flex flex-wrap items-center gap-2">
            <label class="mr-auto text-xs text-text-default"><input v-model="section.markdown" type="checkbox" /> Markdown</label>
            <BaseButton size="sm" variant="secondary" :disabled="index === 0" disabled-reason="Esta es la primera sección." :aria-label="`Subir sección ${index + 1}`" @click="moveSection(index, -1)">Subir</BaseButton>
            <BaseButton size="sm" variant="secondary" :disabled="index === sections.length - 1" disabled-reason="Esta es la última sección." :aria-label="`Bajar sección ${index + 1}`" @click="moveSection(index, 1)">Bajar</BaseButton>
            <BaseButton size="sm" variant="danger-ghost" :aria-label="`Quitar sección ${index + 1}`" @click="sections.splice(index, 1)">Quitar</BaseButton>
          </div>
        </div>
        <BaseButton variant="secondary" size="sm" :disabled="sections.length >= 20" disabled-reason="Puedes agregar hasta 20 secciones." @click="addSection">Agregar sección</BaseButton>
        <label class="block text-sm text-text-default">Cierre
          <textarea v-model="fields.footer" rows="3" maxlength="10000" class="mt-1 w-full rounded-lg border border-border-default bg-surface p-2" />
        </label>
      </template>
      <template v-else>
        <div class="space-y-1 rounded-lg bg-surface-raised p-3 text-sm text-text-default">
          <p><strong>Para:</strong> {{ preparation.recipient_emails.join(', ') }}</p>
          <p v-if="preparation.cc_emails.length"><strong>CC:</strong> {{ preparation.cc_emails.join(', ') }}</p>
          <p><strong>Asunto:</strong> {{ preparation.subject }}</p>
        </div>
        <p v-if="preparation.status === 'sent'" role="status" class="text-sm text-text-brand">Correo enviado. Puedes consultar el correo y sus adjuntos en el historial de Correos.</p>
        <p v-else-if="consumed" role="status" class="text-sm text-text-muted">{{ preparation.error || 'El envío está en curso o pendiente de confirmación. Consulta el historial antes de preparar otro envío.' }}</p>
        <ul class="divide-y divide-border-muted rounded-lg border border-border-muted">
          <li v-for="file in preparation.files" :key="file.key" class="flex flex-wrap items-center gap-2 p-3">
            <span class="min-w-0 flex-1 break-words text-sm text-text-default">{{ file.filename }}</span>
            <BaseButton v-if="file.mime_type === 'application/pdf'" variant="secondary" size="sm" :aria-label="`Previsualizar ${file.filename}`" @click="previewFile(file)">Previsualizar</BaseButton>
            <a :href="file.url" class="text-sm text-text-brand underline" :download="file.filename">Descargar</a>
          </li>
        </ul>
        <div v-if="pdfTitle" class="space-y-2">
          <div class="flex items-center justify-between gap-2">
            <p class="min-w-0 break-words text-sm text-text-default">{{ pdfTitle }}</p>
            <BaseButton variant="secondary" size="sm" @click="clearPdf">Ver correo</BaseButton>
          </div>
          <p v-if="pdfLoading" role="status" class="text-sm text-text-muted">Cargando PDF…</p>
          <iframe v-else-if="pdfUrl" :src="pdfUrl" title="Documento preparado" class="h-[65vh] w-full rounded-lg border border-border-muted" />
        </div>
        <iframe v-else :srcdoc="preparation.html_preview" sandbox="" title="Correo de formalización" class="h-[65vh] w-full rounded-lg border border-border-muted bg-surface" data-testid="formalization-email-preview" />
        <p class="text-xs text-text-muted">Esta revisión vence en 24 horas. Si cambian los datos de origen, tendrás que preparar y revisar el envío nuevamente.</p>
      </template>
    </div>
    <template #footer>
      <BaseModalActions v-if="!loading && !preparation">
        <BaseButton v-if="!options.length" variant="secondary" @click="loadOptions">Reintentar</BaseButton>
        <BaseButton variant="primary" :loading="busy" :disabled="!canPrepare" disabled-reason="Completa los destinatarios y el mensaje, y corrige o desmarca los documentos no disponibles." data-testid="formalization-prepare" @click="prepare">Preparar vista previa</BaseButton>
      </BaseModalActions>
      <BaseModalActions v-if="!loading && preparation && !consumed">
        <BaseButton variant="secondary" :disabled="busy" disabled-reason="Espera a que termine la operación." @click="edit">Volver a editar</BaseButton>
        <BaseButton variant="primary" :loading="busy" :disabled="busy" data-testid="formalization-send" @click="send">Enviar documentación</BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>
