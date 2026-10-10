<template>
  <BaseModal
    :model-value="modelValue"
    kind="form"
    title-id="task-form-title"
    @close="close"
  >
        <div class="flex min-h-0 flex-col" data-testid="task-form-modal">
          <div class="flex items-center justify-between px-6 pt-6 pb-4 border-b border-border-default">
            <h3 id="task-form-title" class="text-lg font-semibold text-text-default">
              {{ isEditing ? 'Edit task' : 'New task' }}
            </h3>
            <BaseActionButton action="close" label="Cerrar formulario de tarea" @click="close" />
          </div>

          <form :id="modalFormId" class="flex flex-col flex-1 min-h-0" novalidate @submit.prevent="handleSubmit">
            <div class="px-6 py-4 space-y-4">
            <BaseFormField
              label="Title"
              required
              :error="titleError"
            >
              <template #default="{ errorId, invalid }">
                <BaseInput
                  v-model="form.title"
                  :error="invalid"
                  :aria-describedby="errorId"
                  data-testid="task-title-input"
                  @update:model-value="titleError = ''"
                />
              </template>
            </BaseFormField>

            <BaseFormField label="Description">
              <BaseTextarea v-model="form.description" rows="3" />
            </BaseFormField>

            <BaseFormRow :cols="3" :gap="4">
              <BaseFormField label="Status">
                <BaseSelect v-model="form.status" :options="statusOptions" />
              </BaseFormField>
              <BaseFormField label="Priority">
                <BaseSelect
                  v-model="form.priority"
                  :options="priorityOptions"
                  data-testid="task-priority-select"
                />
              </BaseFormField>
              <BaseFormField label="Tablero">
                <BaseSelect v-model="form.board_type" :options="boardOptions" />
              </BaseFormField>
            </BaseFormRow>

            <BaseFormRow :cols="2" :gap="4">
              <BaseFormField label="Due date">
                <BaseInput v-model="form.due_date" type="date" />
              </BaseFormField>
              <BaseFormField label="Assigned to">
                <BaseSelect v-model="form.assignee_id" :options="assigneeOptions" />
              </BaseFormField>
            </BaseFormRow>

            <!-- Alertas manuales (solo en edición) -->
            <div v-if="isEditing" class="pt-1">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-xs font-semibold text-text-muted uppercase tracking-wide">Alertas</span>
                <span
                  v-if="alerts.length"
                  class="inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-medium rounded-full bg-primary-soft text-text-brand"
                >{{ alerts.length }}</span>
              </div>

              <div v-if="store.alertsLoading" class="text-xs text-text-muted py-1">Cargando alertas…</div>

              <ul v-else-if="alerts.length" class="space-y-1.5 mb-3">
                <li
                  v-for="alert in alerts"
                  :key="alert.id"
                  class="flex items-start justify-between gap-2 px-3 py-2 rounded-lg bg-surface-raised text-sm"
                >
                  <div class="flex-1 min-w-0">
                    <span class="font-medium text-text-default">{{ formatAlertDate(alert.notify_at) }}</span>
                    <span
                      v-if="alert.sent"
                      class="ml-2 text-xs px-1.5 py-0.5 rounded-full bg-primary-soft text-text-brand"
                    >Enviada</span>
                    <span
                      v-else
                      class="ml-2 text-xs px-1.5 py-0.5 rounded-full bg-surface-raised text-text-muted"
                    >Pendiente</span>
                    <p v-if="alert.note" class="text-xs text-text-muted mt-0.5 truncate">{{ alert.note }}</p>
                  </div>
                  <BaseActionButton
                    action="delete"
                    label="Eliminar alerta"
                    variant="danger-ghost"
                    size="sm"
                    class="flex-shrink-0"
                    :disabled="deletingAlertId === alert.id"
                    @click="handleDeleteAlert(alert.id)"
                  />
                </li>
              </ul>
              <p v-else class="text-xs text-text-muted mb-3">No hay alertas definidas.</p>

              <!-- Add alert form -->
              <div class="flex gap-2 items-end">
                <div class="flex-shrink-0">
                  <label class="block text-xs text-text-muted mb-1">Fecha</label>
                  <input
                    v-model="newAlert.notify_at"
                    type="date"
                    class="px-3 py-2 border border-border-default rounded-lg text-sm bg-surface focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring"
                    data-testid="new-alert-date"
                  />
                </div>
                <div class="flex-1 min-w-0">
                  <label class="block text-xs text-text-muted mb-1">Nota</label>
                  <input
                    v-model="newAlert.note"
                    type="text"
                    placeholder="Ej: Revisar avance con el cliente"
                    class="w-full px-3 py-2 border border-border-default rounded-lg text-sm bg-surface focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring"
                  />
                </div>
                <BaseButton
                  variant="primary"
                  class="flex-shrink-0"
                  :disabled="!newAlert.notify_at"
                  :loading="isAddingAlert"
                  @click="handleAddAlert"
                >
                  <BaseActionIcon action="create" />
                  Agregar
                </BaseButton>
              </div>
            </div>

            <!-- Comment thread (edit mode only) -->
            <div v-if="isEditing" class="pt-1">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-xs font-semibold text-text-muted uppercase tracking-wide">Comentarios</span>
                <span
                  v-if="comments.length"
                  class="inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-medium rounded-full bg-info-soft text-info-strong"
                >{{ comments.length }}</span>
              </div>

              <div v-if="store.commentsLoading" class="text-xs text-text-muted py-1">Cargando…</div>

              <ul v-else-if="comments.length" class="space-y-2 mb-3 max-h-40 overflow-y-auto">
                <li
                  v-for="comment in comments"
                  :key="comment.id"
                  class="flex items-start gap-2 px-3 py-2 rounded-lg bg-surface-raised text-sm"
                >
                  <div class="flex-1 min-w-0">
                    <div class="flex items-baseline gap-2">
                      <span class="font-medium text-text-default text-xs">{{ comment.author_name }}</span>
                      <span class="text-[10px] text-text-subtle">{{ formatCommentDate(comment.created_at) }}</span>
                    </div>
                    <p class="mt-0.5 text-xs text-text-muted whitespace-pre-wrap">{{ comment.text }}</p>
                  </div>
                  <BaseActionButton
                    action="delete"
                    label="Eliminar comentario"
                    variant="danger-ghost"
                    size="sm"
                    class="flex-shrink-0"
                    @click="handleDeleteComment(comment.id)"
                  />
                </li>
              </ul>
              <p v-else class="text-xs text-text-muted mb-3">Sin comentarios aún.</p>

              <div class="flex gap-2">
                <input
                  v-model="newComment"
                  type="text"
                  placeholder="Agregar comentario…"
                  class="flex-1 px-3 py-2 border border-border-default rounded-lg text-sm bg-surface focus:ring-2 focus:ring-focus-ring/30 focus:border-focus-ring"
                  @keydown.enter.prevent="handleAddComment"
                />
                <BaseButton
                  variant="primary"
                  class="flex-shrink-0"
                  :disabled="!newComment.trim()"
                  :loading="isAddingComment"
                  @click="handleAddComment"
                >
                  <BaseActionIcon action="create" />
                  Agregar
                </BaseButton>
              </div>
            </div>

            <!-- Archive section (edit mode only) -->
            <div v-if="isEditing" class="pt-1">
              <!-- Already archived: show badge + reason -->
              <div v-if="props.task?.is_archived" class="flex items-start gap-2 px-3 py-2 rounded-lg bg-warning-soft border border-warning-strong/30">
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs font-semibold rounded-full bg-warning-strong/20 text-warning-strong flex-shrink-0">Archivada</span>
                <p v-if="props.task.archive_reason" class="text-xs text-warning-strong flex-1">{{ props.task.archive_reason }}</p>
                <p v-else class="text-xs text-text-subtle italic flex-1">Sin motivo registrado.</p>
              </div>
              <!-- Not archived: show archive trigger / form -->
              <div v-else-if="!showArchiveForm" class="flex items-center gap-2">
                <BaseButton variant="link" size="sm" @click="showArchiveForm = true">Archivar tarea</BaseButton>
              </div>
              <div v-else class="space-y-2 p-3 rounded-lg bg-warning-soft border border-warning-strong/30">
                <label class="block text-xs font-medium text-warning-strong">Motivo del archivo</label>
                <textarea
                  v-model="archiveReason"
                  rows="2"
                  placeholder="Ej: Descartada por cambio de prioridades…"
                  data-testid="task-archive-reason"
                  class="w-full px-3 py-2 border border-input-border rounded-lg text-sm bg-input-bg focus:ring-2 focus:ring-focus-ring/30"
                ></textarea>
                <div class="flex gap-2">
                  <BaseButton variant="primary" size="sm" :disabled="busy" @click="handleArchive">Confirmar archivo</BaseButton>
                  <BaseButton variant="ghost" size="sm" @click="showArchiveForm = false">Cancelar</BaseButton>
                </div>
              </div>
            </div>

            <div
              v-if="isEditing"
              class="flex flex-wrap justify-end gap-2 border-t border-border-muted pt-4"
            >
              <BaseButton
                type="button"
                variant="danger"
                :disabled="busy"
                @click="handleDelete"
              >
                Eliminar
              </BaseButton>
              <BaseButton
                type="button"
                variant="secondary"
                :disabled="busy"
                data-testid="task-duplicate-btn"
                @click="handleDuplicate"
              >
                Duplicar
              </BaseButton>
            </div>

            </div>

          </form>
        </div>
    <template #footer>
      <BaseModalActions>
        <BaseButton type="button" variant="ghost" @click="close">
          Cancelar
        </BaseButton>
        <BaseButton
          type="submit" :form="modalFormId"
          variant="primary"
          :loading="busy"
          data-testid="task-submit-btn"
        >
          {{ isEditing ? 'Guardar' : 'Crear' }}
        </BaseButton>
      </BaseModalActions>
    </template>
  </BaseModal>
</template>

<script setup>
import { useId, computed, ref, watch } from 'vue';
import { useTaskStore } from '~/stores/tasks';
import { usePanelNotify } from '~/composables/usePanelNotify';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  task: { type: Object, default: null },
  defaultStatus: { type: String, default: 'todo' },
  defaultBoardType: { type: String, default: 'standard' },
  busy: { type: Boolean, default: false },
  assignees: { type: Array, default: () => [] },
});

const emit = defineEmits(['update:modelValue', 'submit', 'delete', 'archive', 'duplicate']);

const store = useTaskStore();
const notify = usePanelNotify();

const isEditing = computed(() => Boolean(props.task?.id));
const alerts = computed(() => store.taskAlerts[props.task?.id] ?? []);
const comments = computed(() => store.comments[props.task?.id] ?? []);
const titleError = ref('');

const statusOptions = [
  { value: 'todo', label: 'TO DO' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'done', label: 'Done' },
];
const priorityOptions = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
];
const boardOptions = [
  { value: 'standard', label: 'Sin periodicidad' },
  { value: 'weekly', label: 'Semanal' },
  { value: 'monthly', label: 'Mensual' },
  { value: 'macro', label: 'Macro-tarea' },
];
const assigneeOptions = computed(() => [
  { value: '', label: 'Unassigned' },
  ...props.assignees.map((user) => ({ value: user.id, label: user.name })),
]);

const form = ref(buildForm(props.task, props.defaultStatus));

const newAlert = ref({ notify_at: '', note: '' });
const isAddingAlert = ref(false);
const deletingAlertId = ref(null);

const newComment = ref('');
const isAddingComment = ref(false);

const showArchiveForm = ref(false);
const archiveReason = ref('');

function buildForm(task, defaultStatus, defaultBoardType) {
  if (task) {
    return {
      title: task.title || '',
      description: task.description || '',
      status: task.status || 'todo',
      priority: task.priority || 'medium',
      board_type: task.board_type || 'standard',
      due_date: task.due_date || '',
      assignee_id: task.assignee || '',
    };
  }
  return {
    title: '',
    description: '',
    status: defaultStatus || 'todo',
    priority: 'medium',
    board_type: props.defaultBoardType || 'standard',
    due_date: '',
    assignee_id: '',
  };
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      form.value = buildForm(props.task, props.defaultStatus, props.defaultBoardType);
      newAlert.value = { notify_at: '', note: '' };
      newComment.value = '';
      showArchiveForm.value = false;
      archiveReason.value = '';
      titleError.value = '';
      if (props.task?.id) {
        store.fetchTaskAlerts(props.task.id);
        store.fetchTaskComments(props.task.id);
      }
    }
  },
);

function formatAlertDate(dateStr) {
  if (!dateStr) return '';
  const [y, m, d] = dateStr.split('-');
  return new Date(Number(y), Number(m) - 1, Number(d)).toLocaleDateString('es-CO', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function close() {
  emit('update:modelValue', false);
}

function handleSubmit() {
  if (!form.value.title.trim()) {
    titleError.value = 'Escribe el título de la tarea.';
    return;
  }

  const payload = {
    title: form.value.title.trim(),
    description: form.value.description,
    status: form.value.status,
    priority: form.value.priority,
    board_type: form.value.board_type,
  };
  if (form.value.due_date) payload.due_date = form.value.due_date;
  else payload.due_date = null;
  if (form.value.assignee_id) payload.assignee_id = Number(form.value.assignee_id);
  else payload.assignee_id = null;
  emit('submit', payload);
}

async function handleAddComment() {
  const text = newComment.value.trim();
  if (!text) return;
  isAddingComment.value = true;
  const result = await store.addTaskComment(props.task.id, text);
  if (result.success) {
    newComment.value = '';
  } else {
    notify.error({ title: 'No se pudo agregar el comentario', detail: result?.message || '' });
  }
  isAddingComment.value = false;
}

async function handleDeleteComment(commentId) {
  await store.deleteTaskComment(props.task.id, commentId);
}

async function handleArchive() {
  emit('archive', props.task, archiveReason.value.trim());
}

function formatCommentDate(dateStr) {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('es-CO', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function handleDelete() {
  emit('delete', props.task);
}

function handleDuplicate() {
  emit('duplicate', props.task);
}

async function handleAddAlert() {
  if (!newAlert.value.notify_at) return;
  isAddingAlert.value = true;
  const payload = { notify_at: newAlert.value.notify_at };
  if (newAlert.value.note.trim()) payload.note = newAlert.value.note.trim();
  const result = await store.createTaskAlert(props.task.id, payload);
  if (result.success) {
    newAlert.value = { notify_at: '', note: '' };
  } else {
    notify.error({ title: 'No se pudo crear el recordatorio', detail: result?.message || '' });
  }
  isAddingAlert.value = false;
}

async function handleDeleteAlert(alertId) {
  deletingAlertId.value = alertId;
  await store.deleteTaskAlert(props.task.id, alertId);
  deletingAlertId.value = null;
}

const modalFormId = useId();
</script>
