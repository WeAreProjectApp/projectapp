export function orderTasksByAssignee(tasks) {
  return [...tasks].sort((left, right) => {
    if (!right.assignee_name) return left.assignee_name ? -1 : 0;
    if (!left.assignee_name) return 1;
    return left.assignee_name.localeCompare(right.assignee_name);
  });
}

// The server counts positions in the whole column. Align the drop with the
// neighbouring card in the task's group, which the UI orders by assignee.
export function positionForTaskDrop(tasks, task, index) {
  const column = tasks.filter((candidate) => candidate.id !== task.id);
  const ordered = orderTasksByAssignee(column);
  const sameAssignee = (candidate) => (candidate.assignee_name || '') === (task.assignee_name || '');
  const next = ordered.slice(index).find(sameAssignee);
  if (next) return column.indexOf(next);
  const previous = ordered.slice(0, index).findLast(sameAssignee);
  if (previous) return column.indexOf(previous) + 1;
  return ordered[index] ? column.indexOf(ordered[index]) : column.length;
}
