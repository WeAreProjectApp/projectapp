<template>
  <section
    class="flex flex-col bg-surface-raised rounded-xl border border-border-default min-w-[260px] flex-1"
    :data-testid="`column-${status}`"
  >
    <header class="flex items-center justify-between px-4 py-3 border-b border-border-default">
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full" :class="dotClass"></span>
        <h2 class="text-sm font-semibold text-text-default">{{ label }}</h2>
        <span class="text-[11px] text-text-subtle">{{ tasks.length }}</span>
      </div>
      <BaseActionButton
        action="create"
        :label="`Agregar tarea en ${label}`"
        class="text-text-subtle hover:text-text-brand transition-colors"
        :data-testid="`add-task-${status}`"
        @click="$emit('add')"
      />
    </header>

    <draggable
      :model-value="orderedTasks"
      :group="`tasks-${boardKey}`"
      :disabled="dragDisabled"
      :data-task-board="boardKey"
      :data-task-status="status"
      data-testid="task-drop-zone"
      item-key="id"
      direction="vertical"
      handle="[data-testid='task-card']"
      class="flex-1 min-h-[80px] overflow-y-auto"
      ghost-class="opacity-30"
      @end="handleDragEnd"
    >
      <template #item="{ element, index }">
        <div :data-sort-task-id="element.id" class="px-3 py-1.5">
          <div
            v-if="index === 0 || assigneeLabel(element) !== assigneeLabel(orderedTasks[index - 1])"
            class="min-w-0 max-w-full px-1 mb-1 text-[10px] font-semibold uppercase tracking-wide text-text-subtle [overflow-wrap:anywhere]"
          >
            {{ assigneeLabel(element) }}
          </div>
          <TaskCard :task="element" @click="$emit('edit', element)" />
        </div>
      </template>
    </draggable>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import draggable from 'vuedraggable';
import TaskCard from './TaskCard.vue';
import { orderTasksByAssignee } from '~/utils/taskBoardOrder';

const props = defineProps({
  status: { type: String, required: true },
  boardKey: { type: String, required: true },
  dragDisabled: { type: Boolean, default: false },
  label: { type: String, required: true },
  tasks: { type: Array, default: () => [] },
});

const emit = defineEmits(['add', 'edit', 'move']);

const dotClass = computed(() => {
  const map = {
    todo: 'bg-text-subtle',
    in_progress: 'bg-info-strong',
    blocked: 'bg-danger-strong',
    done: 'bg-success-strong',
  };
  return map[props.status] || 'bg-text-subtle';
});

const orderedTasks = computed(() => orderTasksByAssignee(props.tasks));
const assigneeLabel = (task) => task.assignee_name || 'Unassigned';

function handleDragEnd({ from, to, item, oldDraggableIndex, newDraggableIndex, originalEvent }) {
  if (to?.dataset.taskBoard !== props.boardKey || !Number.isInteger(newDraggableIndex)) return;
  if (from === to && oldDraggableIndex === newDraggableIndex) return;

  // Native drag can leave Sortable's last placeholder in a list even if the
  // release was outside it. Only commit a drop within the final list.
  const point = originalEvent?.changedTouches?.[0] ?? originalEvent;
  const { top, right, bottom, left } = to.getBoundingClientRect();
  if (!(point?.clientX >= left && point.clientX < right
    && point.clientY >= top && point.clientY < bottom)) return;

  emit('move', {
    taskId: Number(item.dataset.sortTaskId),
    status: to.dataset.taskStatus,
    boardKey: props.boardKey,
    index: newDraggableIndex,
  });
}
</script>
