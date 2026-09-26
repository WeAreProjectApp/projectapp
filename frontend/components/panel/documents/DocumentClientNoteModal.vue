<template>
  <BaseModal
    :model-value="modelValue"
    kind="form-wide"
    full-height
    initial-focus="#document-client-note-subject"
    @update:model-value="updateOpenState"
  >
    <div class="min-h-0 flex-1 space-y-6 overflow-y-auto p-6" data-testid="document-client-note-modal">
      <div>
        <h3 class="text-base font-semibold text-text-default">Notas</h3>
        <p class="mt-1 text-xs text-text-muted">
          Guarda textos listos para usar y observaciones privadas. No aparecen en el PDF ni en el portal del cliente.
        </p>
      </div>

      <BaseAlert v-if="readonly" variant="warning">
        Esta cuenta de cobro ya fue emitida y es de solo lectura. Anúlala y crea una nueva para cambiar sus notas.
      </BaseAlert>
      <BaseAlert v-else-if="immutableContent" variant="info">
        El PDF y los mensajes guardados con esta versión son inmutables. Puedes
        agregar y gestionar observaciones privadas más abajo.
      </BaseAlert>

      <section class="space-y-5" aria-labelledby="document-client-messages-heading">
        <h4 id="document-client-messages-heading" class="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Mensajes para el cliente
        </h4>

        <div class="space-y-1.5">
          <div class="flex items-center justify-between gap-3">
            <label for="document-client-note-subject" class="text-sm font-medium text-text-default">Asunto del correo</label>
            <BaseActionButton
              action="copy"
              type="button"
              variant="ghost"
              size="sm"
              :label="copyLabel('subject', 'asunto')"
              :status-label="copyStatus('subject', 'asunto')"
              :status-tone="copyTone('subject')"
              :disabled="isBusy || !draft.subject.trim()"
              :disabled-reason="isBusy ? busyDisabledReason : !draft.subject.trim() ? 'Escribe un asunto antes de copiarlo.' : ''"
              data-testid="client-note-copy-subject"
              @click="copyText('subject', draft.subject, 'asunto')"
            />
          </div>
          <BaseInput
            id="document-client-note-subject"
            v-model="draft.subject"
            :disabled="readonly || immutableContent || isBusy"
            :disabled-reason="fieldDisabledReason"
            maxlength="255"
            placeholder="Asunto breve y concreto"
            data-testid="client-note-subject"
          />
        </div>

        <div class="space-y-1.5">
          <div class="flex items-center justify-between gap-3">
            <label for="document-client-note-email" class="text-sm font-medium text-text-default">Correo</label>
            <BaseActionButton
              action="copy"
              type="button"
              variant="ghost"
              size="sm"
              :label="copyLabel('email', 'correo')"
              :status-label="copyStatus('email', 'correo')"
              :status-tone="copyTone('email')"
              :disabled="isBusy || !draft.emailBody.trim()"
              :disabled-reason="isBusy ? busyDisabledReason : !draft.emailBody.trim() ? 'Escribe el correo antes de copiarlo.' : ''"
              data-testid="client-note-copy-email"
              @click="copyText('email', draft.emailBody, 'correo')"
            />
          </div>
          <!-- Los textos crecen con su contenido: el correo se lee completo
               sin scroll interno y lo que desplaza es el cuerpo del modal. -->
          <BaseTextarea
            id="document-client-note-email"
            v-model="draft.emailBody"
            v-auto-resize
            :disabled="readonly || immutableContent || isBusy"
            :disabled-reason="fieldDisabledReason"
            rows="9"
            placeholder="Saludo, contenido y cierre del correo…"
            data-testid="client-note-email"
          />
        </div>

        <div class="space-y-1.5">
          <div class="flex items-center justify-between gap-3">
            <label for="document-client-note-whatsapp" class="text-sm font-medium text-text-default">WhatsApp</label>
            <BaseActionButton
              action="copy"
              type="button"
              variant="ghost"
              size="sm"
              :label="copyLabel('whatsapp', 'WhatsApp')"
              :status-label="copyStatus('whatsapp', 'WhatsApp')"
              :status-tone="copyTone('whatsapp')"
              :disabled="isBusy || !draft.whatsappMessage.trim()"
              :disabled-reason="isBusy ? busyDisabledReason : !draft.whatsappMessage.trim() ? 'Escribe el mensaje antes de copiarlo.' : ''"
              data-testid="client-note-copy-whatsapp"
              @click="copyText('whatsapp', draft.whatsappMessage, 'WhatsApp')"
            />
          </div>
          <BaseTextarea
            id="document-client-note-whatsapp"
            v-model="draft.whatsappMessage"
            v-auto-resize
            :disabled="readonly || immutableContent || isBusy"
            :disabled-reason="fieldDisabledReason"
            rows="5"
            placeholder="Mensaje breve que invita a revisar el correo…"
            data-testid="client-note-whatsapp"
          />
        </div>
      </section>

      <section
        v-if="!documentId"
        class="space-y-3 border-t border-border-muted pt-5"
        aria-labelledby="document-custom-notes-heading"
      >
        <div class="flex items-center justify-between gap-3">
          <div>
            <h4 id="document-custom-notes-heading" class="text-sm font-semibold text-text-default">Notas adicionales</h4>
            <p class="mt-0.5 text-xs text-text-subtle">Agrega títulos y contenidos personalizados.</p>
          </div>
          <BaseButton
            v-if="!readonly && !immutableContent"
            type="button"
            variant="secondary"
            size="sm"
            :disabled="isBusy"
            :disabled-reason="busyDisabledReason"
            data-testid="client-note-add-custom"
            @click="addCustomNote"
          >
            <BaseActionIcon action="create" />
            Agregar nota
          </BaseButton>
        </div>

        <p v-if="!draft.customNotes.length" class="rounded-xl border border-dashed border-border-default bg-surface-raised px-4 py-3 text-sm text-text-subtle" data-testid="client-note-custom-empty">
          Aún no hay notas adicionales.
        </p>

        <article
          v-for="(note, index) in draft.customNotes"
          :key="note.key"
          class="space-y-3 rounded-xl border border-border-default bg-surface-raised p-4"
          :data-testid="`client-note-custom-${index}`"
        >
          <div class="flex items-center justify-between gap-3">
            <p class="text-xs font-semibold uppercase tracking-wide text-text-muted">Nota {{ index + 1 }}</p>
            <BaseActionButton
              v-if="!readonly && !immutableContent"
              action="delete"
              type="button"
              variant="danger-ghost"
              size="sm"
              :label="`Eliminar nota ${index + 1}`"
              :disabled="isBusy"
              :disabled-reason="busyDisabledReason"
              :data-testid="`client-note-custom-delete-${index}`"
              @click="removeCustomNote(index)"
            />
          </div>

          <div class="space-y-1.5">
            <div class="flex items-center justify-between gap-3">
              <label :for="`document-custom-note-title-${index}`" class="text-sm font-medium text-text-default">Título</label>
              <BaseActionButton
                action="copy"
                type="button"
                variant="ghost"
                size="sm"
                :label="copyLabel(`custom-title-${note.key}`, `título de la nota ${index + 1}`)"
                :status-label="copyStatus(`custom-title-${note.key}`, `título de la nota ${index + 1}`)"
                :status-tone="copyTone(`custom-title-${note.key}`)"
                :disabled="isBusy || !note.title.trim()"
                :disabled-reason="isBusy ? busyDisabledReason : !note.title.trim() ? 'Escribe el título antes de copiarlo.' : ''"
                :data-testid="`client-note-custom-copy-title-${index}`"
                @click="copyText(`custom-title-${note.key}`, note.title, `título de la nota ${index + 1}`)"
              />
            </div>
            <BaseInput
              :id="`document-custom-note-title-${index}`"
              v-model="note.title"
              :disabled="readonly || immutableContent || isBusy"
              :disabled-reason="fieldDisabledReason"
              :error="validationAttempted && !note.title.trim()"
              maxlength="255"
              placeholder="Ej. Contexto para seguimiento"
              :data-testid="`client-note-custom-title-${index}`"
            />
            <p v-if="validationAttempted && !note.title.trim()" class="text-xs text-danger-strong" :data-testid="`client-note-custom-title-error-${index}`">
              El título es obligatorio.
            </p>
          </div>

          <div class="space-y-1.5">
            <div class="flex items-center justify-between gap-3">
              <label :for="`document-custom-note-content-${index}`" class="text-sm font-medium text-text-default">Contenido</label>
              <BaseActionButton
                action="copy"
                type="button"
                variant="ghost"
                size="sm"
                :label="copyLabel(`custom-content-${note.key}`, `contenido de la nota ${index + 1}`)"
                :status-label="copyStatus(`custom-content-${note.key}`, `contenido de la nota ${index + 1}`)"
                :status-tone="copyTone(`custom-content-${note.key}`)"
                :disabled="isBusy || !note.content.trim()"
                :disabled-reason="isBusy ? busyDisabledReason : !note.content.trim() ? 'Escribe el contenido antes de copiarlo.' : ''"
                :data-testid="`client-note-custom-copy-content-${index}`"
                @click="copyText(`custom-content-${note.key}`, note.content, `contenido de la nota ${index + 1}`)"
              />
            </div>
            <BaseTextarea
              :id="`document-custom-note-content-${index}`"
              v-model="note.content"
              v-auto-resize
              :disabled="readonly || immutableContent || isBusy"
              :disabled-reason="fieldDisabledReason"
              :error="validationAttempted && !note.content.trim()"
              rows="5"
              placeholder="Escribe el contenido de la nota…"
              :data-testid="`client-note-custom-content-${index}`"
            />
            <p v-if="validationAttempted && !note.content.trim()" class="text-xs text-danger-strong" :data-testid="`client-note-custom-content-error-${index}`">
              El contenido es obligatorio.
            </p>
          </div>
        </article>
      </section>

      <DocumentObservationManager
        v-else
        :key="`${documentId}-${modelValue}`"
        :document-id="documentId"
        :notes="localNotes"
        :readonly="readonly"
        allow-delete-when-readonly
        class="border-t border-border-muted pt-5"
        @update:notes="localNotes = $event"
        @workflow-changed="emit('workflow-changed')"
        @busy-change="observationBusy = $event"
      />

      <p
        v-if="mode === 'draft' && !readonly && !immutableContent"
        class="rounded-xl border border-warning-soft bg-warning-soft px-4 py-3 text-sm text-warning-strong"
        data-testid="client-note-draft-hint"
      >
        Estas notas se aplicarán al borrador. Quedarán guardadas cuando crees el documento.
      </p>
    </div>

    <!-- Fuera del área que desplaza: con correos y observaciones largas el
         guardado quedaba fuera de la vista, y un pie superpuesto escondía la
         línea que se escribe al final del correo. -->
    <BaseModalActions class="flex-shrink-0" data-testid="client-note-actions">
      <!-- En móvil las acciones se apilan en orden inverso: order-last lo deja
           encima de los botones; desde portrait vuelve a la izquierda. -->
      <BaseBadge
        v-if="hasChanges"
        variant="warning"
        size="sm"
        class="order-last self-center panel-portrait:order-none panel-portrait:mr-auto"
        data-testid="client-note-unsaved"
      >
        {{ mode === 'draft' ? 'Cambios sin aplicar' : 'Cambios sin guardar' }}
      </BaseBadge>
      <BaseButton type="button" variant="ghost" :disabled="isBusy" :disabled-reason="busyDisabledReason" data-testid="client-note-cancel" @click="close">
        {{ readonly || immutableContent ? 'Cerrar' : 'Cancelar' }}
      </BaseButton>
      <BaseButton v-if="!readonly && !immutableContent" type="button" variant="primary" :disabled="isBusy || !hasChanges" :disabled-reason="submitDisabledReason" :loading="saving" data-testid="client-note-submit" @click="submit">
        {{ mode === 'draft' ? 'Aplicar al borrador' : 'Guardar cambios' }}
      </BaseButton>
    </BaseModalActions>
  </BaseModal>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue';
import DocumentObservationManager from '~/components/panel/documents/DocumentObservationManager.vue';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { vAutoResize } from '~/utils/autoResizeDirective';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  subject: { type: String, default: '' },
  emailBody: { type: String, default: '' },
  whatsappMessage: { type: String, default: '' },
  customNotes: { type: Array, default: () => [] },
  documentId: { type: [Number, String], default: null },
  notes: { type: Array, default: () => [] },
  readonly: { type: Boolean, default: false },
  immutableContent: { type: Boolean, default: false },
  mode: {
    type: String,
    default: 'save',
    validator: (value) => ['save', 'draft'].includes(value),
  },
  saving: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue', 'submit', 'workflow-changed']);
const notify = usePanelNotify();
const clipboardFeedback = useClipboardFeedback();
const validationAttempted = ref(false);
const observationBusy = ref(false);
const localNotes = ref([]);
const isBusy = computed(() => props.saving || observationBusy.value);
const busyDisabledReason = computed(() => {
  if (props.saving) return 'Guardando los cambios. Espera un momento.';
  if (observationBusy.value) return 'Actualizando las observaciones. Espera un momento.';
  return '';
});
const fieldDisabledReason = computed(() => {
  if (props.readonly) {
    return 'Esta cuenta de cobro ya fue emitida y es de solo lectura. Anúlala y crea una nueva para cambiarla.';
  }
  if (props.immutableContent) {
    return 'Esta versión conserva exactamente lo enviado y no se puede modificar.';
  }
  return busyDisabledReason.value || undefined;
});
const draft = reactive({ subject: '', emailBody: '', whatsappMessage: '', customNotes: [] });
// Lo que había al abrir, con la misma forma que se envía: el botón se habilita
// sólo cuando guardar cambiaría algo.
const openedSnapshot = ref('');
const hasChanges = computed(() => JSON.stringify(normalizedDraft()) !== openedSnapshot.value);
const submitDisabledReason = computed(() => {
  if (isBusy.value) return busyDisabledReason.value;
  if (!hasChanges.value) {
    return props.mode === 'draft' ? 'No hay cambios para aplicar.' : 'No hay cambios por guardar.';
  }
  return '';
});
let nextCustomNoteKey = 0;

function makeDraftNote(note = {}) {
  nextCustomNoteKey += 1;
  return {
    key: nextCustomNoteKey,
    title: typeof note.title === 'string' ? note.title : '',
    content: typeof note.content === 'string' ? note.content : '',
  };
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    draft.subject = props.subject;
    draft.emailBody = props.emailBody;
    draft.whatsappMessage = props.whatsappMessage;
    draft.customNotes = props.customNotes.map(makeDraftNote);
    openedSnapshot.value = JSON.stringify(normalizedDraft());
    localNotes.value = props.notes.map((note) => ({ ...note }));
    clipboardFeedback.clearAllFeedback();
    validationAttempted.value = false;
    observationBusy.value = false;
  },
  { immediate: true },
);

watch(
  () => props.notes,
  (notes) => { localNotes.value = notes.map((note) => ({ ...note })); },
  { deep: true },
);

function updateOpenState(open) {
  if (!open && isBusy.value) return;
  emit('update:modelValue', open);
}

function close() {
  if (isBusy.value) return;
  emit('update:modelValue', false);
}

function addCustomNote() {
  draft.customNotes.push(makeDraftNote());
}

function removeCustomNote(index) {
  draft.customNotes.splice(index, 1);
}

function normalizedDraft() {
  return {
    subject: draft.subject.trim(),
    emailBody: draft.emailBody.trim(),
    whatsappMessage: draft.whatsappMessage.trim(),
    customNotes: draft.customNotes.map((note) => ({
      title: note.title.trim(),
      content: note.content.trim(),
    })),
  };
}

function submit() {
  validationAttempted.value = true;
  if (draft.customNotes.some((note) => !note.title.trim() || !note.content.trim())) return;
  emit('submit', normalizedDraft());
}

function copyLabel(field, label) {
  return clipboardFeedback.feedbackFor(field).label || `Copiar ${label}`;
}

function copyStatus(field) {
  return clipboardFeedback.feedbackFor(field).label;
}

function copyTone(field) {
  return clipboardFeedback.feedbackFor(field).tone;
}

async function copyText(field, value, label) {
  await clipboardFeedback.copyText({
    key: field,
    text: value,
    successLabel: `Copiado: ${label}`,
    errorLabel: `No se pudo copiar: ${label}`,
    onError: () => notify.error({
      title: 'No se pudo copiar al portapapeles',
      detail: 'Tu navegador bloqueó el acceso al portapapeles.',
    }),
  });
}
</script>
