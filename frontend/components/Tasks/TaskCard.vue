<template>
  <div
    class="group bg-surface border border-border-default rounded-lg p-3 shadow-card hover:shadow-raised cursor-pointer transition-all"
    data-testid="task-card"
    :data-task-id="task.id"
  >
    <h3
      class="line-clamp-2 min-w-0 max-w-full text-sm font-medium text-text-default [overflow-wrap:anywhere]"
      :title="task.title"
    >
      {{ task.title }}
    </h3>

    <div
      class="mt-2 flex min-w-0 max-w-full flex-wrap items-center gap-2 text-[11px] text-text-muted"
      data-testid="task-card-meta"
    >
      <span
        class="inline-flex min-w-0 max-w-full flex-wrap items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide [overflow-wrap:anywhere]"
        :class="priorityBadgeClass"
      >
        {{ priorityLabel }}
      </span>

      <span
        v-if="task.assignee_name"
        class="min-w-0 max-w-full truncate"
        :title="task.assignee_email || task.assignee_name"
      >
        👤 {{ task.assignee_name }}
      </span>
      <span v-else class="text-text-subtle">Unassigned</span>

      <span
        v-if="task.due_date"
        class="whitespace-nowrap"
        :class="task.is_overdue ? 'text-danger-strong font-semibold' : ''"
      >
        📅 {{ formatDayMonth(task.due_date) }}
      </span>
    </div>

    <p
      v-if="task.description"
      class="mt-2 line-clamp-2 min-w-0 max-w-full text-xs text-text-muted [overflow-wrap:anywhere]"
    >
      {{ task.description }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { formatDayMonth } from '~/utils/formatDate';

const props = defineProps({
  task: { type: Object, required: true },
});

const priorityLabel = computed(() => {
  const map = { low: 'Low', medium: 'Medium', high: 'High' };
  return map[props.task.priority] || props.task.priority;
});

const priorityBadgeClass = computed(() => {
  const map = {
    low: 'bg-surface-raised text-text-muted',
    medium: 'bg-info-soft text-info-strong',
    high: 'bg-danger-soft text-danger-strong',
  };
  return map[props.task.priority] || map.medium;
});
</script>
