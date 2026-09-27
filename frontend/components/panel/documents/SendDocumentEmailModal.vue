<template>
  <Teleport to="body">
    <Transition name="fade-modal">
      <div
        v-if="modelValue && document"
        class="fixed inset-0 z-[9990] flex items-stretch justify-stretch bg-black/40 p-0 backdrop-blur-sm panel-portrait:items-center panel-portrait:justify-center panel-portrait:p-4"
        @click.self="close"
      >
        <div class="flex h-[100dvh] w-full max-w-2xl flex-col bg-surface shadow-2xl panel-portrait:h-auto panel-portrait:max-h-[90dvh] panel-portrait:rounded-2xl">

          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-border-muted flex-shrink-0">
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="w-8 h-8 rounded-lg bg-primary-soft flex items-center justify-center flex-shrink-0">
                <svg class="w-4 h-4 text-text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div class="min-w-0">
                <h3 class="text-base font-semibold text-text-default">Enviar por correo</h3>
                <p class="text-xs text-text-muted truncate">{{ document.title }}</p>
              </div>
            </div>
            <BaseButton
              variant="ghost"
              icon-only
              size="md"
              class="flex-shrink-0 ml-2"
              aria-label="Cerrar"
              title="Cerrar"
              :disabled="isSending || isTransitioning"
              @click="close"
            >
              <BaseActionIcon action="close" />
            </BaseButton>
          </div>

          <!-- Tab switcher -->
          <div v-if="!postSendData" class="flex gap-4 border-b border-border-muted px-6 flex-shrink-0">
            <button
              type="button"
              class="pb-3 pt-2 text-sm transition-colors border-b-2"
              :class="activeTab === 'edit'
              ? 'border-emerald-600 text-text-brand font-semibold'
              : 'border-transparent text-text-muted hover:text-text-default'"
              @click="activeTab = 'edit'"
            >
              Editar
            </button>
            <button
              type="button"
              class="pb-3 pt-2 text-sm transition-colors border-b-2"
              :class="activeTab === 'preview'
              ? 'border-emerald-600 text-text-brand font-semibold'
              : 'border-transparent text-text-muted hover:text-text-default'"
              @click="activeTab = 'preview'"
            >
              Vista previa
            </button>
          </div>

          <!-- Body -->
          <div class="min-h-0 flex-1 overflow-y-auto px-6 py-5">

            <div v-if="postSendData" class="space-y-4" data-testid="document-email-post-send">
              <BaseAlert variant="success" title="Correo enviado">
                El mensaje se envió a {{ postSendRecipient }} con {{ postSendData.document_ids?.length || 0 }} documento(s) adjunto(s).
              </BaseAlert>
              <div class="rounded-xl border border-border-default bg-surface-raised p-4">
                <h4 class="text-sm font-semibold text-text-default">Actualizar el ciclo de los documentos</h4>
                <p class="mt-1 text-sm text-text-muted">
                  Puedes marcar ahora los documentos elegibles como Enviado. Elegir “Ahora no” no cambia sus estados y el correo seguirá enviado.
                </p>
              </div>
              <BaseAlert v-if="errorMsg" variant="danger" title="El correo salió, pero el estado no cambió">
                {{ errorMsg }} Puedes reintentar sin volver a enviar el correo.
              </BaseAlert>
            </div>

            <!-- ── EDIT ── -->
            <div v-else-if="activeTab === 'edit'" class="space-y-4">
              <EmailRecipientFields
                v-model:toRecipients="toRecipients"
                v-model:ccRecipients="ccRecipients"
                test-id-prefix="document-email"
              />

              <!-- Subject -->
              <div>
                <label class="block text-xs text-text-muted mb-1">Asunto</label>
                <input
                  v-model="subject"
                  type="text"
                  placeholder="Asunto del correo"
                  class="bg-input-bg w-full px-3 py-2 border border-border-default rounded-lg text-sm text-text-default focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                />
              </div>

              <!-- Greeting -->
              <div>
                <label class="block text-xs text-text-muted mb-1">Saludo</label>
                <input
                  v-model="greeting"
                  type="text"
                  placeholder="Hola Carlos"
                  class="bg-input-bg w-full px-3 py-2 border border-border-default rounded-lg text-sm text-text-default focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none"
                />
              </div>

              <!-- Sections -->
              <div>
                <label class="block text-xs text-text-muted mb-2">Secciones del correo</label>
                <div class="space-y-3">
                  <div
                    v-for="(section, idx) in sections"
                    :key="section.id"
                    class="bg-surface-raised rounded-lg p-3 border border-border-muted"
                  >
                    <div class="flex items-center gap-2 mb-2">
                      <span class="text-2xs text-text-subtle uppercase tracking-wide">Sección {{ idx + 1 }}</span>
                      <div class="ml-auto flex items-center gap-1">
                        <BaseButton
                          variant="ghost"
                          icon-only
                          size="sm"
                          :disabled="idx === 0"
                          title="Subir"
                          aria-label="Subir sección"
                          @click="moveSection(idx, -1)"
                        >
                          <BaseActionIcon action="move-up" />
                        </BaseButton>
                        <BaseButton
                          variant="ghost"
                          icon-only
                          size="sm"
                          :disabled="idx === sections.length - 1"
                          title="Bajar"
                          aria-label="Bajar sección"
                          @click="moveSection(idx, 1)"
                        >
                          <BaseActionIcon action="move-down" />
                        </BaseButton>
                        <BaseButton
                          v-if="sections.length > 1"
                          variant="danger-ghost"
                          icon-only
                          size="sm"
                          title="Eliminar sección"
                          aria-label="Eliminar sección"
                          @click="removeSection(idx)"
                        >
                          <BaseActionIcon action="delete" />
                        </BaseButton>
                      </div>
                    </div>
                    <textarea
                      v-model="section.text"
                      rows="3"
                      placeholder="Escribe el contenido de esta sección..."
                      class="bg-input-bg w-full px-3 py-2 border border-border-default rounded-lg text-sm text-text-default focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none resize-y"
                    />
                  </div>
                </div>
                <BaseButton variant="secondary" size="sm" class="mt-3" @click="addSection">
                  <BaseActionIcon action="create" />
                  Agregar sección
                </BaseButton>
              </div>

              <!-- Footer text -->
              <div>
                <label class="block text-xs text-text-muted mb-1">Pie de correo</label>
                <textarea
                  v-model="footer"
                  rows="2"
                  placeholder="Saludos cordiales..."
                  class="bg-input-bg w-full px-3 py-2 border border-border-default rounded-lg text-sm text-text-default focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring outline-none resize-y"
                />
              </div>

              <!-- Attachments -->
              <div>
                <label class="block text-xs text-text-muted mb-2">Documentos adjuntos (PDF)</label>
                <div class="space-y-1.5">
                  <div
                    v-for="docId in selectedDocIds"
                    :key="docId"
                    class="flex items-center gap-2 px-3 py-2 bg-surface-raised rounded-lg border border-border-muted text-sm"
                  >
                    <svg class="w-4 h-4 text-text-subtle flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span class="flex-1 min-w-0 truncate text-text-default">{{ docTitle(docId) }}.pdf</span>
                    <BaseButton
                      v-if="docId !== document.id"
                      variant="danger-ghost"
                      icon-only
                      size="sm"
                      title="Quitar"
                      aria-label="Quitar adjunto"
                      @click="removeAttachment(docId)"
                    >
                      <BaseActionIcon action="remove" />
                    </BaseButton>
                    <span v-else class="text-2xs uppercase tracking-wide text-text-subtle">Principal</span>
                  </div>
                </div>
                <BaseButton variant="secondary" size="sm" class="mt-2" @click="showPicker = true">
                  <BaseActionIcon action="attach" />
                  Adjuntar otro documento
                </BaseButton>

                <!-- Picker -->
                <div
                  v-if="showPicker"
                  class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
                  @click.self="showPicker = false"
                >
                  <div class="bg-surface rounded-xl shadow-xl max-w-md w-full max-h-[70vh] flex flex-col border border-border-default">
                    <header class="flex items-center justify-between px-5 py-3 border-b border-border-muted">
                      <h4 class="text-sm font-semibold text-text-default">Seleccionar documentos</h4>
                      <BaseButton variant="ghost" icon-only size="sm" aria-label="Cerrar" title="Cerrar" @click="showPicker = false">
                        <BaseActionIcon action="close" />
                      </BaseButton>
                    </header>
                    <div class="min-h-0 flex-1 overflow-y-auto px-5 py-3">
                      <p v-if="!availableDocs.length" class="text-xs text-text-subtle py-6 text-center">
                        No hay otros documentos disponibles para adjuntar.
                      </p>
                      <ul v-else class="divide-y divide-border-muted">
                        <li v-for="d in availableDocs" :key="d.id" class="py-2 flex items-center gap-3">
                          <input
                            :id="`pick-${d.id}`"
                            v-model="selectedDocIds"
                            type="checkbox"
                            :value="d.id"
                            class="rounded border-input-border text-text-brand focus:ring-focus-ring/30"
                          />
                          <label :for="`pick-${d.id}`" class="flex-1 min-w-0 cursor-pointer">
                            <div class="text-sm text-text-default truncate">{{ d.title }}</div>
                            <div v-if="d.folder_name" class="mt-0.5 flex items-center gap-1 text-[11px] text-text-subtle"><BaseActionIcon action="folders" /> {{ d.folder_name }}</div>
                          </label>
                        </li>
                      </ul>
                    </div>
                    <BaseModalActions class="pb-[max(1rem,env(safe-area-inset-bottom))]">
                      <BaseButton variant="primary" size="sm" @click="showPicker = false">
                        Listo
                      </BaseButton>
                    </BaseModalActions>
                  </div>
                </div>
              </div>
            </div>

            <!-- ── PREVIEW ── -->
            <div v-else class="bg-surface border border-border-muted rounded-lg p-6 text-text-default">
              <div class="text-xs text-text-subtle mb-1"><strong>Para:</strong> {{ recipientSummary(toRecipients) || '—' }}</div>
              <div v-if="ccRecipients.length" class="text-xs text-text-subtle mb-1"><strong>CC:</strong> {{ recipientSummary(ccRecipients) }}</div>
              <div class="text-xs text-text-subtle mb-4"><strong>Asunto:</strong> {{ subject || '—' }}</div>
              <hr class="border-border-muted mb-4" />
              <p v-if="greeting" class="mb-3 text-sm">{{ greeting }}</p>
              <p
                v-for="section in sections"
                :key="`prev-${section.id}`"
                class="mb-3 text-sm whitespace-pre-wrap"
              >
                {{ section.text }}
              </p>
              <p v-if="footer" class="mt-4 pt-3 border-t border-border-muted text-sm whitespace-pre-wrap text-text-muted">
                {{ footer }}
              </p>
              <div v-if="selectedDocIds.length" class="mt-4 pt-3 border-t border-border-muted">
                <p class="text-xs text-text-subtle mb-1.5">Adjuntos:</p>
                <ul class="space-y-1">
                  <li v-for="docId in selectedDocIds" :key="`prev-att-${docId}`" class="text-xs text-text-default flex items-center gap-2">
                    <svg class="w-3.5 h-3.5 text-text-subtle" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    {{ docTitle(docId) }}.pdf
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Error / status -->
          <div v-if="!postSendData && (errorMsg || successMsg)" class="px-6 pb-2 flex-shrink-0">
            <p
              v-if="errorMsg"
              class="text-xs px-3 py-2 rounded-lg"
              :class="rateLimited
              ? 'text-warning-strong bg-warning-soft'
              : 'text-danger-strong bg-danger-soft'"
            >
              {{ errorMsg }}
            </p>
            <p v-else-if="successMsg" class="text-xs text-success-strong bg-success-soft px-3 py-2 rounded-lg">
              {{ successMsg }}
            </p>
          </div>

          <!-- Footer buttons -->
          <BaseModalActions class="pb-[max(1rem,env(safe-area-inset-bottom))]">
            <template v-if="postSendData">
              <BaseButton
                variant="ghost"
                :disabled="isTransitioning"
                disabled-reason="Actualizando el estado de los documentos. Espera un momento."
                data-testid="document-email-skip-sent-state"
                @click="completePostSend"
              >
                Ahora no
              </BaseButton>
              <BaseButton variant="primary" :loading="isTransitioning" data-testid="document-email-confirm-sent-state" @click="markDocumentsAsSent">
                Marcar como Enviado
              </BaseButton>
            </template>
            <template v-else>
              <BaseButton variant="ghost" :disabled="isSending" @click="close">
                Cancelar
              </BaseButton>
              <BaseButton variant="primary" :disabled="!canSend" :loading="isSending" @click="send">
                Enviar
              </BaseButton>
            </template>
          </BaseModalActions>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useDocumentStateStore } from '~/stores/document_states';
import EmailRecipientFields from '~/components/emails/EmailRecipientFields.vue';
import { recipientSummary } from '~/utils/emailRecipients';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  document: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue', 'sent']);

const documentStore = useDocumentStore();
const stateStore = useDocumentStateStore();

const activeTab = ref('edit');
const toRecipients = ref([]);
const ccRecipients = ref([]);
const subject = ref('');
const greeting = ref('');
const footer = ref('');
const sections = ref([{ id: 1, text: '' }]);
const selectedDocIds = ref([]);
const showPicker = ref(false);
const isSending = ref(false);
const errorMsg = ref('');
const successMsg = ref('');
const rateLimited = ref(false);
const isTransitioning = ref(false);
const postSendData = ref(null);
const postSendRecipient = ref('');

let nextSectionId = 2;

const canSend = computed(() => {
  if (!toRecipients.value.length || !subject.value.trim()) return false;
  return sections.value.some((s) => s.text.trim().length > 0);
});

const availableDocs = computed(() => {
  if (!props.document) return [];
  return documentStore.documents.filter((d) => d.id !== props.document.id);
});

watch(
  () => [props.modelValue, props.document],
  async ([open, doc]) => {
    if (!open || !doc) return;
    activeTab.value = 'edit';
    toRecipients.value = [];
    ccRecipients.value = [];
    subject.value = doc.title || '';
    sections.value = [{ id: 1, text: '' }];
    nextSectionId = 2;
    selectedDocIds.value = [doc.id];
    errorMsg.value = '';
    successMsg.value = '';
    rateLimited.value = false;
    isTransitioning.value = false;
    postSendData.value = null;
    postSendRecipient.value = '';
    const result = await documentStore.getEmailDefaults();
    if (result.success && result.data) {
      greeting.value = result.data.greeting || '';
      footer.value = result.data.footer || '';
      if (!subject.value && result.data.subject) {
        subject.value = result.data.subject;
      }
    }
  },
  { immediate: true },
);

function close() {
  if (isSending.value || isTransitioning.value) return;
  emit('update:modelValue', false);
}

function addSection() {
  sections.value.push({ id: nextSectionId++, text: '' });
}

function removeSection(idx) {
  if (sections.value.length <= 1) return;
  sections.value.splice(idx, 1);
}

function moveSection(idx, delta) {
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= sections.value.length) return;
  const arr = sections.value;
  [arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]];
}

function removeAttachment(docId) {
  selectedDocIds.value = selectedDocIds.value.filter((id) => id !== docId);
}

function docTitle(docId) {
  if (props.document && docId === props.document.id) return props.document.title;
  const found = documentStore.documents.find((d) => d.id === docId);
  return found?.title || `documento-${docId}`;
}

async function send() {
  if (!canSend.value || isSending.value) return;
  isSending.value = true;
  errorMsg.value = '';
  successMsg.value = '';
  rateLimited.value = false;
  const payload = {
    recipient_emails: toRecipients.value,
    cc_emails: ccRecipients.value,
    subject: subject.value.trim(),
    greeting: greeting.value.trim(),
    footer: footer.value.trim(),
    sections: sections.value.map((s) => s.text).filter((t) => t.trim().length > 0),
    document_ids: selectedDocIds.value,
  };
  const result = await documentStore.sendDocumentEmail(payload);
  isSending.value = false;
  if (result.success) {
    const destinationSummary = recipientSummary(toRecipients.value);
    const ccSummary = recipientSummary(ccRecipients.value);
    successMsg.value = `Correo enviado a ${destinationSummary}${ccSummary ? ` con CC a ${ccSummary}` : ''}.`;
    emit('sent', result.data);
    if (result.data?.offer_sent_transition) {
      postSendData.value = result.data;
      postSendRecipient.value = `${destinationSummary}${ccSummary ? ` (CC: ${ccSummary})` : ''}`;
      return;
    }
    setTimeout(close, 1200);
  } else {
    rateLimited.value = result.code === 'rate_limited';
    errorMsg.value = result.errors?.error || 'No se pudo enviar el correo.';
  }
}

function completePostSend() {
  if (isTransitioning.value) return;
  close();
}

async function markDocumentsAsSent() {
  if (!postSendData.value || isTransitioning.value) return;
  isTransitioning.value = true;
  errorMsg.value = '';
  await stateStore.fetchCatalog();
  const sentState = stateStore.stateByKey('sent');
  const eligibleIds = (postSendData.value.document_ids || []).filter((id) => {
    const candidate = id === props.document?.id
      ? props.document
      : documentStore.documents.find((item) => item.id === id);
    return candidate?.document_type_code !== 'collection_account';
  });
  if (!sentState) {
    errorMsg.value = 'No está disponible el estado Enviado.';
    isTransitioning.value = false;
    return;
  }
  const transitions = await Promise.all(
    eligibleIds.map((id) => stateStore.openEpisode(id, sentState.id, null, 'email')),
  );
  isTransitioning.value = false;
  if (transitions.some((transition) => !transition.success)) {
    errorMsg.value = 'Algunos documentos no pudieron marcarse como Enviado.';
    return;
  }
  successMsg.value = eligibleIds.length
    ? 'Correo enviado y estado Enviado registrado.'
    : 'Correo enviado; no había documentos elegibles para cambiar de estado.';
  close();
}
</script>
