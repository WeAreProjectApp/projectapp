<template>
  <div>
    <!-- Page header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
      <div>
        <h1 class="text-2xl font-light text-text-default">Tasks</h1>
        <p class="text-sm text-text-muted mt-1">Tableros internos del equipo.</p>
      </div>
      <BaseButton
        variant="primary"
        size="md"
        data-testid="new-task-btn"
        @click="openCreate('todo')"
      >
        <BaseActionIcon action="create" />
        Nueva tarea
      </BaseButton>
    </div>

    <p v-if="taskLinkError" role="alert" class="mb-4 text-sm text-warning-strong" data-testid="task-link-status">{{ taskLinkError }}</p>
    <div v-if="taskStore.isLoading" class="text-center py-12 text-text-subtle text-sm">
      Cargando tableros…
    </div>

    <div v-else class="space-y-4">
      <!-- ── 4 collapsible boards ── -->
      <div
        v-for="board in boards"
        :key="board.key"
        class="rounded-xl border border-border-default overflow-hidden"
      >
        <!-- Board header (toggle) -->
        <button
          type="button"
          class="w-full flex items-center justify-between px-4 py-3 bg-surface-raised hover:bg-border-muted transition-colors text-left"
          @click="toggleBoard(board.key)"
        >
          <div class="flex items-center gap-3">
            <span class="text-base font-semibold text-text-default">{{ board.label }}</span>
            <span class="text-xs text-text-subtle">{{ boardTaskCount(board.key) }} tarea{{ boardTaskCount(board.key) === 1 ? '' : 's' }}</span>
          </div>
          <BaseActionIcon :action="openBoards[board.key] ? 'collapse' : 'expand'" />
        </button>

        <!-- Board content -->
        <div v-if="openBoards[board.key]" class="p-3">
          <!-- Macro board: flat card list -->
          <div v-if="board.key === 'macro'">
            <div v-if="!taskStore.boardTasks.macro.length" class="text-sm text-text-subtle py-4 text-center">Sin macro-tareas todavía.</div>
            <ul v-else class="space-y-2">
              <li
                v-for="task in taskStore.boardTasks.macro"
                :key="task.id"
                class="flex items-center justify-between px-4 py-3 rounded-lg bg-surface border border-border-default cursor-pointer hover:bg-surface-raised transition-colors"
                @click="openEdit(task)"
              >
                <div class="flex min-w-0 flex-1 items-center gap-3">
                  <span
                    class="inline-block w-2 h-2 rounded-full flex-shrink-0"
                    :class="priorityDot(task.priority)"
                  />
                  <BaseRowLink
                    :to="taskDetailTo(task.id)"
                    :data-testid="`task-open-${task.id}`"
                    class="min-w-0 max-w-full flex-1 truncate text-sm font-medium text-text-default hover:text-text-brand transition-colors"
                    :title="task.title"
                  >{{ task.title }}</BaseRowLink>
                </div>
                <div class="flex items-center gap-2 flex-shrink-0 ml-3">
                  <span v-if="task.due_date" class="text-xs" :class="task.is_overdue ? 'text-danger-strong' : 'text-text-subtle'">{{ task.due_date }}</span>
                  <span
                    v-if="task.assignee_name"
                    class="max-w-40 truncate text-xs text-text-subtle"
                    :title="task.assignee_name"
                  >{{ task.assignee_name }}</span>
                </div>
              </li>
            </ul>
            <button
              type="button"
              class="mt-3 text-xs text-text-brand hover:underline"
              @click="openCreateOnBoard('macro', 'todo')"
            ><BaseActionIcon action="create" /> Agregar macro-tarea</button>
          </div>

          <!-- Kanban boards -->
          <div v-else class="flex gap-2 overflow-x-auto pb-2">
            <TaskColumn
              v-for="col in columns"
              :key="col.status"
              :status="col.status"
              :label="col.label"
              :tasks="(taskStore.boardTasks[board.key] || {})[col.status] || []"
              @add="openCreateOnBoard(board.key, col.status)"
              @edit="openEdit"
              @move="handleMove"
            />
          </div>
        </div>
      </div>

      <!-- ── Archived tasks accordion ── -->
      <div class="rounded-xl border border-border-default overflow-hidden">
        <button
          type="button"
          class="w-full flex items-center justify-between px-4 py-3 bg-surface-raised hover:bg-border-muted transition-colors text-left"
          @click="toggleArchive"
        >
          <div class="flex items-center gap-3">
            <span class="text-sm font-semibold text-text-muted">Archivadas</span>
            <span v-if="taskStore.archivedTasks.length" class="text-xs text-text-subtle">{{ taskStore.archivedTasks.length }}</span>
          </div>
          <BaseActionIcon :action="archiveOpen ? 'collapse' : 'expand'" />
        </button>

        <div v-if="archiveOpen" class="p-4">
          <div v-if="taskStore.archivedLoading" class="text-sm text-text-subtle py-4 text-center">Cargando…</div>
          <div v-else-if="!taskStore.archivedTasks.length" class="text-sm text-text-subtle py-4 text-center">No hay tareas archivadas.</div>
          <ul v-else class="space-y-2">
            <li
              v-for="task in taskStore.archivedTasks"
              :key="task.id"
              :data-testid="`archived-task-${task.id}`"
              class="flex items-center justify-between px-4 py-3 rounded-lg bg-surface border border-border-default"
            >
              <div class="min-w-0">
                <p class="max-w-full truncate text-sm font-medium text-text-muted" :title="task.title">{{ task.title }}</p>
                <p
                  v-if="task.archive_reason"
                  class="mt-0.5 max-w-full truncate text-xs text-text-subtle"
                  :title="task.archive_reason"
                >{{ task.archive_reason }}</p>
                <p class="text-xs text-text-subtle mt-0.5">{{ boardLabel(task.board_type) }}</p>
              </div>
              <button
                type="button"
                :disabled="taskStore.isUpdating"
                class="ml-4 flex-shrink-0 text-xs text-text-brand hover:underline disabled:opacity-50"
                @click="handleUnarchive(task)"
              >Restaurar</button>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Task form modal -->
    <TaskFormModal
      v-model="showModal"
      :task="editingTask"
      :default-status="defaultStatus"
      :default-board-type="activeBoardForCreate"
      :busy="taskStore.isUpdating"
      :assignees="taskStore.assignees"
      @submit="handleSubmit"
      @delete="handleDelete"
      @archive="handleArchive"
      @duplicate="handleDuplicate"
    />

    <!-- Confirm modal -->
    <ConfirmModal
      v-model="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      @confirm="handleConfirmed"
      @cancel="handleCancelled"
    />
  </div>
</template>

<script setup>
import { useRadarFocus } from '~/composables/useRadarFocus';
import { useDashboardAttentionText } from '~/composables/useDashboardAttentionText';
import { computed, reactive, ref, watch } from 'vue';
import TaskColumn from '~/components/Tasks/TaskColumn.vue';
import TaskFormModal from '~/components/Tasks/TaskFormModal.vue';
import ConfirmModal from '~/components/ConfirmModal.vue';
import { useConfirmModal } from '~/composables/useConfirmModal';
import { usePanelNotify } from '~/composables/usePanelNotify';
import { usePanelRefresh } from '~/composables/usePanelRefresh';
import { useDetailQueryParam } from '~/composables/useDetailQueryParam';

definePageMeta({ layout: 'admin', middleware: ['admin-auth'] });

const taskStore = useTaskStore();
const route = useRoute();
const radarFocus = useRadarFocus();
const radarText = useDashboardAttentionText();
const taskLinkError = ref('');
// Editar una tarea tiene dirección propia (`?task=`): así la fila puede
// publicarla en un enlace y la URL se puede compartir o recargar. Crear no
// tiene qué direccionar — todavía no hay entidad —, así que sigue siendo estado
// local de la página.
const {
  openRow: editingTask,
  isOpen: isEditingTask,
  toFor: taskDetailTo,
  open: openTaskById,
  close: closeTaskDetail,
} = useDetailQueryParam('task', { resolve: (id) => taskStore.getTaskById(id) });

const creatingTask = ref(false);

const showModal = computed({
  get: () => creatingTask.value || (isEditingTask.value && editingTask.value !== null),
  set: (open) => {
    if (open) return;
    creatingTask.value = false;
    if (isEditingTask.value) closeTaskDetail();
  },
});
const defaultStatus = ref('todo');
const activeBoardForCreate = ref('standard');
const { confirmState, requestConfirm, handleConfirmed, handleCancelled } = useConfirmModal();
const notify = usePanelNotify();

const boards = [
  { key: 'macro',    label: 'Macro-Tareas' },
  { key: 'standard', label: 'Sin periodicidad' },
  { key: 'weekly',   label: 'Semanal' },
  { key: 'monthly',  label: 'Mensual' },
];

const columns = [
  { status: 'todo',        label: 'TO DO' },
  { status: 'in_progress', label: 'In Progress' },
  { status: 'blocked',     label: 'Blocked' },
  { status: 'done',        label: 'Done' },
];

const BOARD_LABELS = {
  standard: 'Sin periodicidad',
  weekly:   'Semanal',
  monthly:  'Mensual',
  macro:    'Macro-Tareas',
};

const openBoards = reactive({ standard: true, weekly: false, monthly: false, macro: false });
const archiveOpen = ref(false);

function toggleBoard(key) {
  openBoards[key] = !openBoards[key];
}

function toggleArchive() {
  archiveOpen.value = !archiveOpen.value;
  if (archiveOpen.value && !taskStore.archivedTasks.length) {
    taskStore.fetchArchivedTasks();
  }
}

function boardTaskCount(boardKey) {
  const board = taskStore.boardTasks[boardKey];
  if (!board) return 0;
  if (Array.isArray(board)) return board.length;
  return Object.values(board).reduce((s, list) => s + list.length, 0);
}

function boardLabel(key) {
  return BOARD_LABELS[key] || key;
}

function priorityDot(priority) {
  if (priority === 'high') return 'bg-danger-strong';
  if (priority === 'medium') return 'bg-warning-strong';
  return 'bg-border-default';
}

async function revealLinkedTask() {
  const id = Number(route.query.task);
  taskLinkError.value = '';
  if (!Number.isInteger(id) || id < 1) return;
  const task = taskStore.getTaskById(id);
  if (task) {
    openBoards[task.board_type] = true;
    await radarFocus(`[data-task-id="${id}"], [data-testid="task-open-${id}"]`);
    return;
  }
  const result = await taskStore.fetchArchivedTasks();
  if (Number(route.query.task) !== id) return;
  if (!result?.success) {
    taskLinkError.value = radarText.value.detailError;
    return;
  }
  const archived = taskStore.archivedTasks.find((row) => row.id === id);
  if (archived) {
    archiveOpen.value = true;
    taskLinkError.value = radarText.value.changed;
    await radarFocus(`[data-testid="archived-task-${id}"]`);
  } else {
    taskLinkError.value = radarText.value.missing;
  }
}
async function loadTasks() {
  await Promise.all([taskStore.fetchAllBoards(), taskStore.fetchAssignees()]);
  await revealLinkedTask();
}
watch(() => route.query.task, revealLinkedTask);

onMounted(loadTasks);
usePanelRefresh(loadTasks);

function openCreate(status) {
  defaultStatus.value = status || 'todo';
  activeBoardForCreate.value = 'standard';
  creatingTask.value = true;
}

function openCreateOnBoard(boardKey, status) {
  defaultStatus.value = status || 'todo';
  activeBoardForCreate.value = boardKey;
  creatingTask.value = true;
}

function openEdit(task) {
  openTaskById(task.id);
}

// Show the backend's normalized message when a task action fails.
function notifyTaskFailure(result, fallbackTitle) {
  notify.error({ title: fallbackTitle, detail: result?.message || '' });
}

async function handleSubmit(payload) {
  const isEdit = !!editingTask.value?.id;
  const result = isEdit
    ? await taskStore.updateTask(editingTask.value.id, payload)
    : await taskStore.createTask(payload);
  if (result.success) {
    showModal.value = false;
    notify.success({ title: isEdit ? 'Tarea actualizada' : 'Tarea creada' });
  } else {
    notifyTaskFailure(result, isEdit ? 'No se pudo actualizar la tarea' : 'No se pudo crear la tarea');
  }
}

async function handleDelete(task) {
  if (!task?.id) return;
  const confirmed = await requestConfirm({
    title: 'Eliminar tarea',
    message: `"${task.title}" se eliminará de forma permanente. Esta acción no se puede deshacer.`,
    confirmText: 'Eliminar',
    variant: 'danger',
  });
  if (!confirmed) return;
  const result = await taskStore.deleteTask(task.id);
  if (result.success) {
    showModal.value = false;
    notify.success({ title: 'Tarea eliminada' });
  } else {
    notifyTaskFailure(result, 'No se pudo eliminar la tarea');
  }
}

async function handleDuplicate(task) {
  if (!task?.id) return;
  const result = await taskStore.duplicateTask(task.id);
  if (result.success) {
    showModal.value = false;
    notify.success({ title: 'Tarea duplicada' });
  } else {
    notifyTaskFailure(result, 'No se pudo duplicar la tarea');
  }
}

async function handleArchive(task, reason) {
  if (!task?.id) return;
  const result = await taskStore.archiveTask(task.id, reason);
  if (result.success) {
    showModal.value = false;
    // Con el acordeón abierto se refetchea de una: vaciar la lista dejaba
    // "No hay tareas archivadas" en pantalla con la tarea recién archivada
    // existiendo en el servidor. Cerrado, vaciar conserva la lazy-load de
    // toggleArchive (al abrir con lista vacía, refetchea).
    if (archiveOpen.value) {
      await taskStore.fetchArchivedTasks();
    } else {
      taskStore.archivedTasks = [];
    }
    notify.success({ title: 'Tarea archivada' });
  } else {
    notifyTaskFailure(result, 'No se pudo archivar la tarea');
  }
}

async function handleUnarchive(task) {
  if (!task?.id) return;
  const result = await taskStore.unarchiveTask(task.id);
  if (result.success) {
    notify.success({ title: 'Tarea restaurada' });
  } else {
    notifyTaskFailure(result, 'No se pudo restaurar la tarea');
  }
}

async function handleMove({ taskId, status, position }) {
  const result = await taskStore.moveTask(taskId, status, position);
  if (!result.success) {
    notifyTaskFailure(result, 'No se pudo mover la tarea');
  }
}
</script>
