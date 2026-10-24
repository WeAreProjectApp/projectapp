<template>
  <section class="space-y-4" aria-labelledby="document-observations-heading">
    <div v-if="view === 'list'" class="space-y-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 id="document-observations-heading" class="text-sm font-semibold text-text-default">
            Observaciones del documento
          </h4>
          <p class="mt-0.5 text-xs text-text-subtle">
            Descartar conserva la decisión; eliminar limpia algo que nunca debió existir.
          </p>
        </div>
        <div class="flex flex-wrap gap-1 rounded-xl border border-border-default bg-surface-raised p-1" role="tablist" aria-label="Secciones de observaciones">
          <!-- design-tokens: allow-raw-button — tab control, not an action button -->
          <button
            v-for="tab in tabs"
            :key="tab.id"
            type="button"
            role="tab"
            :aria-selected="pane === tab.id"
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
            :class="pane === tab.id ? 'bg-surface text-text-default shadow-sm' : 'text-text-muted hover:text-text-default'"
            :data-testid="`document-observation-tab-${tab.id}`"
            @click="selectPane(tab.id)"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>

      <BaseAlert v-if="errorMessage" variant="danger" title="No se pudo completar la acción">
        {{ errorMessage }}
      </BaseAlert>

      <template v-if="pane === 'active'">
        <div v-if="localNotes.length" class="space-y-3" data-testid="document-observation-list">
          <div v-if="canDelete && localNotes.length >= 2" class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-default bg-surface px-3 py-2">
            <BaseCheckbox
              :model-value="allSelected"
              :disabled="busy"
              data-testid="document-observation-select-all"
              @update:model-value="toggleAll"
            >
              Seleccionar todas
            </BaseCheckbox>
            <BaseButton
              v-if="selectedIds.length"
              type="button"
              variant="danger-ghost"
              size="sm"
              :disabled="busy"
              data-testid="document-observation-bulk-delete"
              @click="openBulkDelete"
            >
              Eliminar seleccionadas ({{ selectedIds.length }})
            </BaseButton>
          </div>

          <article
            v-for="note in localNotes"
            :key="note.id"
            class="rounded-xl border border-border-default bg-surface-raised p-3"
            :data-testid="`document-observation-${note.id}`"
          >
            <div class="flex items-start gap-3">
              <BaseCheckbox
                v-if="canDelete && localNotes.length >= 2"
                v-model="selectedIds"
                :value="note.id"
                :disabled="busy"
                :aria-label="`Seleccionar ${note.title || 'observación'}`"
                :data-testid="`document-observation-select-${note.id}`"
              />
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-start justify-between gap-2">
                  <div class="min-w-0">
                    <p class="text-sm font-medium text-text-default">{{ note.title || 'Observación' }}</p>
                    <BaseRichTextContent class="mt-1 text-sm text-text-muted" :source="note.content" :format="note.text_formats?.['/content'] || 'plain'" />
                  </div>
                  <BaseBadge :variant="note.status === 'open' ? 'warning' : 'neutral'" size="sm">
                    {{ noteStatusLabel(note.status) }}
                  </BaseBadge>
                </div>

                <p v-if="note.status === 'discarded'" class="mt-2 text-xs text-text-subtle">
                  Motivo del descarte: {{ note.resolution_note || 'Sin motivo registrado' }}
                </p>
                <p v-else-if="note.status === 'resolved'" class="mt-2 text-xs text-text-subtle">
                  Resolución: {{ note.resolution_note || 'Sin detalle registrado' }}
                </p>

                <div class="mt-3 flex flex-wrap justify-end gap-2">
                  <BaseActionButton
                    action="copy"
                    type="button"
                    variant="ghost"
                    size="sm"
                    :label="noteCopyFeedback(note).label || `Copiar ${note.title || 'observación'}`"
                    :status-label="noteCopyFeedback(note).label"
                    :status-tone="noteCopyFeedback(note).tone"
                    :disabled="busy"
                    :data-testid="`document-observation-copy-${note.id}`"
                    @click="copyNote(note)"
                  />
                  <template v-if="!readonly && note.status === 'open'">
                    <BaseButton type="button" variant="ghost" size="sm" :disabled="busy" :data-testid="`document-observation-edit-${note.id}`" @click="openEdit(note)">
                      Editar
                    </BaseButton>
                    <BaseButton type="button" variant="secondary" size="sm" :disabled="busy" :data-testid="`document-observation-discard-${note.id}`" @click="openFinish(note, 'discarded')">
                      Descartar
                    </BaseButton>
                    <BaseButton type="button" variant="secondary" size="sm" :disabled="busy" :data-testid="`document-observation-resolve-${note.id}`" @click="openFinish(note, 'resolved')">
                      Resolver
                    </BaseButton>
                  </template>
                  <BaseButton
                    v-if="canDelete"
                    type="button"
                    variant="danger-ghost"
                    size="sm"
                    :disabled="busy"
                    :data-testid="`document-observation-delete-${note.id}`"
                    @click="openDelete(note)"
                  >
                    Eliminar
                  </BaseButton>
                </div>
              </div>
            </div>
          </article>
        </div>
        <p v-else class="rounded-xl border border-dashed border-border-default px-4 py-3 text-sm text-text-subtle">
          Aún no hay observaciones.
        </p>

        <div v-if="!readonly" class="space-y-3 rounded-xl border border-border-default bg-surface p-4">
          <p class="text-xs font-semibold uppercase tracking-wide text-text-muted">Nueva observación</p>
          <BaseInput
            v-model="newNote.title"
            maxlength="120"
            :disabled="busy"
            placeholder="Título breve"
            data-testid="document-observation-title"
          />
          <BaseRichTextEditor
            v-model="newNote.content" :format="newNote.text_formats['/content'] || 'plain'" @update:format="newNote.text_formats['/content'] = $event"
            rows="4"
            :disabled="busy"
            placeholder="Describe la observación…"
            data-testid="document-observation-content"
          />
          <label class="flex items-center gap-2 text-sm text-text-muted">
            <BaseToggle v-model="newNote.markNeedsFix" size="sm" :disabled="busy" />
            Marcar también Solucionar bug
          </label>
          <div class="flex justify-end">
            <BaseButton
              type="button"
              variant="secondary"
              size="sm"
              :loading="busy"
              :disabled="!newNote.content.trim()"
              data-testid="document-observation-add"
              @click="addObservation"
            >
              Agregar observación
            </BaseButton>
          </div>
        </div>
      </template>

      <template v-else-if="pane === 'trash'">
        <div v-if="loadingPane" class="rounded-xl border border-border-default px-4 py-5 text-sm text-text-subtle">
          Cargando papelera…
        </div>
        <div v-else-if="deletedNotes.length" class="space-y-3" data-testid="document-observation-trash">
          <article v-for="note in deletedNotes" :key="note.id" class="rounded-xl border border-border-default bg-surface-raised p-3">
            <p class="text-sm font-medium text-text-default">{{ note.title || 'Observación' }}</p>
            <BaseRichTextContent class="mt-1 text-sm text-text-muted" :source="note.content" :format="note.text_formats?.['/content'] || 'plain'" />
            <p class="mt-2 text-xs text-text-subtle">
              Eliminada por {{ note.deleted_by_name || 'Usuario no disponible' }} · {{ formatDate(note.deleted_at) }}
            </p>
            <div v-if="canDelete" class="mt-3 flex justify-end">
              <BaseButton type="button" variant="secondary" size="sm" :loading="busy && actionNote?.id === note.id" :disabled="busy" :data-testid="`document-observation-restore-${note.id}`" @click="restoreObservation(note)">
                Restaurar
              </BaseButton>
            </div>
          </article>
        </div>
        <p v-else class="rounded-xl border border-dashed border-border-default px-4 py-3 text-sm text-text-subtle">
          La papelera está vacía.
        </p>
      </template>

      <template v-else>
        <div v-if="loadingPane" class="rounded-xl border border-border-default px-4 py-5 text-sm text-text-subtle">
          Cargando actividad…
        </div>
        <ol v-else-if="events.length" class="space-y-2" data-testid="document-observation-activity">
          <li v-for="event in events" :key="event.id" class="rounded-xl border border-border-default bg-surface-raised px-4 py-3">
            <p class="text-sm text-text-default">
              {{ event.actor_name || 'Usuario no disponible' }}
              {{ event.event_type === 'deleted' ? 'eliminó' : 'restauró' }} una observación.
            </p>
            <p class="mt-1 text-xs text-text-subtle">{{ formatDate(event.recorded_at) }}</p>
          </li>
        </ol>
        <p v-else class="rounded-xl border border-dashed border-border-default px-4 py-3 text-sm text-text-subtle">
          No hay actividad de eliminación o restauración.
        </p>
      </template>
    </div>

    <form v-else-if="view === 'edit'" class="space-y-4" data-testid="document-observation-edit-form" @submit.prevent="saveEdit">
      <div>
        <h4 class="text-base font-semibold text-text-default">Editar observación</h4>
        <p class="mt-1 text-sm text-text-subtle">Corrige el texto sin cambiar su estado ni su historial.</p>
      </div>
      <BaseInput v-model="editDraft.title" maxlength="120" :disabled="busy" aria-label="Título de la observación" />
      <BaseRichTextEditor v-model="editDraft.content" :format="editDraft.text_formats['/content'] || 'plain'" @update:format="editDraft.text_formats['/content'] = $event" rows="7" :disabled="busy" aria-label="Contenido de la observación" />
      <BaseAlert v-if="errorMessage" variant="danger">{{ errorMessage }}</BaseAlert>
      <div class="flex flex-wrap justify-end gap-2">
        <BaseButton type="button" variant="ghost" :disabled="busy" @click="backToList">Cancelar</BaseButton>
        <BaseButton type="submit" variant="primary" :loading="busy" :disabled="!editDraft.content.trim()">Guardar cambios</BaseButton>
      </div>
    </form>

    <form v-else-if="view === 'finish'" class="space-y-4" data-testid="document-observation-finish-form" @submit.prevent="saveFinish">
      <div>
        <h4 class="text-base font-semibold text-text-default">
          {{ finishOutcome === 'discarded' ? 'Descartar observación' : 'Resolver observación' }}
        </h4>
        <p class="mt-1 text-sm text-text-subtle">
          <template v-if="finishOutcome === 'discarded'">
            La observación existió, pero decidiste no atenderla. Se conservará en el historial con su motivo.
          </template>
          <template v-else>
            La observación quedará atendida y se conservará con el detalle de la solución.
          </template>
        </p>
      </div>
      <NotePreview :note="actionNote" />
      <div class="space-y-1.5">
        <label for="document-observation-resolution" class="text-sm font-medium text-text-default">
          {{ finishOutcome === 'discarded' ? 'Motivo' : 'Resolución' }}
        </label>
        <BaseTextarea
          id="document-observation-resolution"
          v-model="finishDraft.resolutionNote"
          rows="4"
          maxlength="500"
          :disabled="busy"
          data-testid="document-observation-resolution"
        />
        <p class="text-xs text-text-subtle">
          {{ finishOutcome === 'discarded' ? 'Si lo dejas vacío, se mostrará “Sin motivo registrado”.' : 'Si lo dejas vacío, se mostrará “Sin detalle registrado”.' }}
        </p>
      </div>
      <BaseCheckbox v-if="finishOutcome === 'resolved'" v-model="finishDraft.moveCycle" :disabled="busy">
        Abrir el estado Bug atendido si esta era la última observación pendiente
      </BaseCheckbox>
      <BaseAlert v-if="errorMessage" variant="danger">{{ errorMessage }}</BaseAlert>
      <div class="flex flex-wrap justify-end gap-2">
        <BaseButton type="button" variant="ghost" :disabled="busy" @click="backToList">Cancelar</BaseButton>
        <BaseButton type="submit" variant="primary" :loading="busy" data-testid="document-observation-confirm-finish">
          {{ finishOutcome === 'discarded' ? 'Descartar' : 'Marcar como resuelta' }}
        </BaseButton>
      </div>
    </form>

    <div v-else class="space-y-4" data-testid="document-observation-delete-confirmation">
      <div>
        <h4 class="text-base font-semibold text-danger-strong">
          {{ deleteCandidates.length > 1 ? `Eliminar ${deleteCandidates.length} observaciones` : 'Eliminar observación' }}
        </h4>
        <p class="mt-1 text-sm text-text-subtle">
          Eliminar significa que estas observaciones nunca debieron existir. Saldrán de la lista y de los conteos; podrás recuperarlas desde la papelera.
        </p>
      </div>
      <div class="max-h-72 space-y-2 overflow-y-auto rounded-xl border border-border-default bg-surface p-3">
        <NotePreview v-for="note in deleteCandidates" :key="note.id" :note="note" />
      </div>
      <BaseAlert variant="warning" title="Las copias externas no cambian">
        Si el texto se copió a un correo o mensaje, eliminarlo aquí no lo borra de la bandeja ni del dispositivo de nadie.
      </BaseAlert>
      <p class="text-xs text-text-subtle">
        El sistema registrará quién eliminó y cuándo, sin copiar el contenido en la actividad.
      </p>
      <BaseAlert v-if="errorMessage" variant="danger">{{ errorMessage }}</BaseAlert>
      <div class="flex flex-wrap justify-end gap-2">
        <BaseButton type="button" variant="ghost" :disabled="busy" @click="backToList">Cancelar</BaseButton>
        <BaseButton type="button" variant="danger" :loading="busy" data-testid="document-observation-confirm-delete" @click="confirmDelete">
          {{ deleteCandidates.length > 1 ? 'Eliminar seleccionadas' : 'Eliminar observación' }}
        </BaseButton>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue';
import BaseActionButton from '~/components/base/BaseActionButton.vue';
import BaseAlert from '~/components/base/BaseAlert.vue';
import BaseBadge from '~/components/base/BaseBadge.vue';
import BaseButton from '~/components/base/BaseButton.vue';
import BaseCheckbox from '~/components/base/BaseCheckbox.vue';
import BaseInput from '~/components/base/BaseInput.vue';
import BaseTextarea from '~/components/base/BaseTextarea.vue';
import BaseToggle from '~/components/base/BaseToggle.vue';
import NotePreview from '~/components/panel/documents/DocumentObservationPreview.vue';
import { useClipboardFeedback } from '~/composables/useClipboardFeedback';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { useDocumentStateStore } from '~/stores/document_states';

const props = defineProps({
  documentId: { type: [Number, String], required: true },
  notes: { type: Array, default: () => [] },
  readonly: { type: Boolean, default: false },
  allowDeleteWhenReadonly: { type: Boolean, default: false },
});

const emit = defineEmits(['update:notes', 'workflow-changed', 'busy-change']);
const stateStore = useDocumentStateStore();
const notify = usePanelNotify();
const clipboardFeedback = useClipboardFeedback();
const tabs = [
  { id: 'active', label: 'Observaciones' },
  { id: 'trash', label: 'Papelera' },
  { id: 'activity', label: 'Actividad' },
];
const localNotes = ref([]);
const deletedNotes = ref([]);
const events = ref([]);
const selectedIds = ref([]);
const pane = ref('active');
const view = ref('list');
const busy = ref(false);
const loadingPane = ref(false);
const errorMessage = ref('');
const actionNote = ref(null);
const deleteCandidates = ref([]);
const finishOutcome = ref('resolved');
const loadedTrash = ref(false);
const loadedEvents = ref(false);
const newNote = reactive({ title: '', content: '', text_formats: {}, markNeedsFix: true });
const editDraft = reactive({ title: '', content: '', text_formats: {} });
const finishDraft = reactive({ resolutionNote: '', moveCycle: false });
const canDelete = computed(() => !props.readonly || props.allowDeleteWhenReadonly);

const allSelected = computed(
  () => localNotes.value.length > 0 && selectedIds.value.length === localNotes.value.length,
);

watch(
  () => props.notes,
  (notes) => {
    localNotes.value = notes.map((note) => ({ ...note }));
    selectedIds.value = selectedIds.value.filter((id) => localNotes.value.some((note) => note.id === id));
  },
  { deep: true, immediate: true },
);

watch(busy, (value) => emit('busy-change', value), { immediate: true });

function publishNotes() {
  emit('update:notes', localNotes.value.map((note) => ({ ...note })));
  emit('workflow-changed');
}

function resetTransientState() {
  errorMessage.value = '';
  actionNote.value = null;
  deleteCandidates.value = [];
}

function backToList() {
  if (busy.value) return;
  resetTransientState();
  view.value = 'list';
}

async function selectPane(nextPane) {
  if (busy.value) return;
  pane.value = nextPane;
  errorMessage.value = '';
  if (nextPane === 'trash' && !loadedTrash.value) await loadTrash();
  if (nextPane === 'activity' && !loadedEvents.value) await loadEvents();
}

async function loadTrash() {
  loadingPane.value = true;
  const result = await stateStore.fetchDeletedNotes(props.documentId);
  loadingPane.value = false;
  if (!result.success) {
    errorMessage.value = result.message;
    return;
  }
  deletedNotes.value = result.data;
  loadedTrash.value = true;
}

async function loadEvents() {
  loadingPane.value = true;
  const result = await stateStore.fetchNoteEvents(props.documentId);
  loadingPane.value = false;
  if (!result.success) {
    errorMessage.value = result.message;
    return;
  }
  events.value = result.data;
  loadedEvents.value = true;
}

function toggleAll(checked) {
  selectedIds.value = checked ? localNotes.value.map((note) => note.id) : [];
}

function openEdit(note) {
  resetTransientState();
  actionNote.value = note;
  editDraft.title = note.title || '';
  editDraft.content = note.content || '';
  editDraft.text_formats = { ...note.text_formats };
  view.value = 'edit';
}

function openFinish(note, outcome) {
  resetTransientState();
  actionNote.value = note;
  finishOutcome.value = outcome;
  finishDraft.resolutionNote = '';
  finishDraft.moveCycle = false;
  view.value = 'finish';
}

function openDelete(note) {
  resetTransientState();
  actionNote.value = note;
  deleteCandidates.value = [note];
  view.value = 'delete';
}

function openBulkDelete() {
  resetTransientState();
  deleteCandidates.value = localNotes.value.filter((note) => selectedIds.value.includes(note.id));
  if (!deleteCandidates.value.length) return;
  view.value = 'delete';
}

async function addObservation() {
  if (!newNote.content.trim() || busy.value) return;
  busy.value = true;
  errorMessage.value = '';
  const result = await stateStore.createNote(props.documentId, {
    title: newNote.title.trim(),
    content: newNote.content.trim(),
    text_formats: { ...newNote.text_formats },
    mark_needs_fix: newNote.markNeedsFix,
  });
  busy.value = false;
  if (!result.success) {
    errorMessage.value = result.message;
    return;
  }
  localNotes.value.push(result.data);
  newNote.title = '';
  newNote.content = '';
  newNote.text_formats = {};
  publishNotes();
}

async function saveEdit() {
  if (!actionNote.value || !editDraft.content.trim() || busy.value) return;
  busy.value = true;
  errorMessage.value = '';
  const result = await stateStore.updateNote(props.documentId, actionNote.value.id, {
    title: editDraft.title.trim(),
    content: editDraft.content.trim(),
    text_formats: { ...editDraft.text_formats },
  });
  busy.value = false;
  if (!result.success) {
    errorMessage.value = result.message;
    return;
  }
  Object.assign(actionNote.value, result.data);
  publishNotes();
  backToList();
}

async function saveFinish() {
  if (!actionNote.value || busy.value) return;
  busy.value = true;
  errorMessage.value = '';
  const result = await stateStore.finishNote(props.documentId, actionNote.value.id, {
    outcome: finishOutcome.value,
    resolution_note: finishDraft.resolutionNote.trim(),
    move_cycle_to_bug_attended: finishDraft.moveCycle,
  });
  busy.value = false;
  if (!result.success) {
    errorMessage.value = result.message;
    return;
  }
  Object.assign(actionNote.value, result.data.note);
  publishNotes();
  backToList();
}

async function confirmDelete() {
  if (!deleteCandidates.value.length || busy.value) return;
  busy.value = true;
  errorMessage.value = '';
  const ids = deleteCandidates.value.map((note) => note.id);
  const result = ids.length === 1
    ? await stateStore.deleteNote(props.documentId, ids[0])
    : await stateStore.bulkDeleteNotes(props.documentId, ids);
  busy.value = false;
  if (!result.success) {
    errorMessage.value = result.message;
    return;
  }
  localNotes.value = localNotes.value.filter((note) => !ids.includes(note.id));
  selectedIds.value = selectedIds.value.filter((id) => !ids.includes(id));
  loadedTrash.value = false;
  loadedEvents.value = false;
  publishNotes();
  backToList();
}

async function restoreObservation(note) {
  if (busy.value) return;
  actionNote.value = note;
  busy.value = true;
  errorMessage.value = '';
  const result = await stateStore.restoreNote(props.documentId, note.id);
  busy.value = false;
  if (!result.success) {
    errorMessage.value = result.message;
    return;
  }
  deletedNotes.value = deletedNotes.value.filter((candidate) => candidate.id !== note.id);
  localNotes.value.push(result.data.note);
  localNotes.value.sort((left, right) => left.order - right.order || left.id - right.id);
  loadedEvents.value = false;
  publishNotes();
}

async function copyNote(note) {
  await clipboardFeedback.copyText({
    key: `note-${note.id}`,
    text: note.content,
    successLabel: 'Observación copiada',
    errorLabel: 'No se pudo copiar la observación',
    onError: () => notify.error({
      title: 'No se pudo copiar al portapapeles',
      detail: 'Tu navegador bloqueó el acceso al portapapeles.',
    }),
  });
}

function noteCopyFeedback(note) {
  return clipboardFeedback.feedbackFor(`note-${note.id}`);
}

function noteStatusLabel(status) {
  return { open: 'Pendiente', resolved: 'Resuelta', discarded: 'Descartada' }[status] || status;
}

function formatDate(value) {
  if (!value) return 'Fecha no disponible';
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}
</script>
