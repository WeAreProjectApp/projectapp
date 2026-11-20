import { mount } from '@vue/test-utils'

jest.mock('vuedraggable', () => ({
  name: 'draggable',
  props: ['modelValue', 'itemKey', 'group', 'ghostClass'],
  emits: ['update:modelValue', 'end'],
  template: '<div><slot v-for="(element, index) in modelValue" name="item" :element="element" :index="index" /></div>',
}))

jest.mock('../../components/Tasks/TaskCard.vue', () => ({
  name: 'TaskCard',
  props: ['task'],
  template: '<div data-testid="task-card">{{ task.title }}</div>',
}))

import TaskColumn from '../../components/Tasks/TaskColumn.vue'

function mountColumn(props = {}) {
  return mount(TaskColumn, {
    props: {
      status: 'todo',
      boardKey: 'standard',
      label: 'Por hacer',
      tasks: [],
      ...props,
    },
  })
}

describe('TaskColumn', () => {
  it('renders the column label prop text', () => {
    const wrapper = mountColumn({ label: 'En progreso' })
    expect(wrapper.text()).toContain('En progreso')
  })

  it('container has data-testid column-todo for status todo', () => {
    const wrapper = mountColumn({ status: 'todo' })
    expect(wrapper.find('[data-testid="column-todo"]').exists()).toBe(true)
  })

  it('container has data-testid column-in_progress for status in_progress', () => {
    const wrapper = mountColumn({ status: 'in_progress', label: 'En progreso' })
    expect(wrapper.find('[data-testid="column-in_progress"]').exists()).toBe(true)
  })

  it('container has data-testid column-blocked for status blocked', () => {
    const wrapper = mountColumn({ status: 'blocked', label: 'Bloqueado' })
    expect(wrapper.find('[data-testid="column-blocked"]').exists()).toBe(true)
  })

  it('container has data-testid column-done for status done', () => {
    const wrapper = mountColumn({ status: 'done', label: 'Hecho' })
    expect(wrapper.find('[data-testid="column-done"]').exists()).toBe(true)
  })

  it('add-task button has correct data-testid for the column status', () => {
    const wrapper = mountColumn({ status: 'todo' })
    expect(wrapper.find('[data-testid="add-task-todo"]').exists()).toBe(true)
  })

  it('clicking add-task button emits add', async () => {
    const wrapper = mountColumn({ status: 'todo' })
    await wrapper.find('[data-testid="add-task-todo"]').trigger('click')
    expect(wrapper.emitted('add')).toBeTruthy()
  })

  it('renders a drop zone for an empty column', () => {
    const wrapper = mountColumn({ tasks: [] })
    const dropZone = wrapper.get('[data-testid="task-drop-zone"]')
    expect(dropZone.attributes('data-task-status')).toBe('todo')
    expect(dropZone.findAll('[data-testid="task-card"]')).toHaveLength(0)
  })

  it('renders task count in header', () => {
    const tasks = [
      { id: 1, title: 'A', assignee_name: 'Alice' },
      { id: 2, title: 'B', assignee_name: 'Alice' },
    ]
    const wrapper = mountColumn({ tasks })
    expect(wrapper.text()).toContain('2')
  })

  // ── dotClass computed ──────────────────────────────────────────────────────

  it('dotClass is bg-text-subtle for todo status', () => {
    const wrapper = mountColumn({ status: 'todo' })
    const dot = wrapper.find('span.rounded-full')
    expect(dot.classes()).toContain('bg-text-subtle')
  })

  it('dotClass is bg-info-strong for in_progress status', () => {
    const wrapper = mountColumn({ status: 'in_progress', label: 'En progreso' })
    const dot = wrapper.find('span.rounded-full')
    expect(dot.classes()).toContain('bg-info-strong')
  })

  it('dotClass is bg-danger-strong for blocked status', () => {
    const wrapper = mountColumn({ status: 'blocked', label: 'Bloqueado' })
    const dot = wrapper.find('span.rounded-full')
    expect(dot.classes()).toContain('bg-danger-strong')
  })

  it('dotClass is bg-success-strong for done status', () => {
    const wrapper = mountColumn({ status: 'done', label: 'Hecho' })
    const dot = wrapper.find('span.rounded-full')
    expect(dot.classes()).toContain('bg-success-strong')
  })

  it('dotClass falls back to bg-text-subtle for unknown status', () => {
    const wrapper = mountColumn({ status: 'unknown', label: 'Custom' })
    const dot = wrapper.find('span.rounded-full')
    expect(dot.classes()).toContain('bg-text-subtle')
  })

  // ── groupedTasks computed ──────────────────────────────────────────────────

  it('groupedTasks renders assignee group names for assigned tasks', () => {
    const tasks = [
      { id: 1, title: 'Task A', assignee_name: 'Alice' },
      { id: 2, title: 'Task B', assignee_name: 'Bob' },
    ]
    const wrapper = mountColumn({ tasks })
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
  })

  it('groupedTasks renders Unassigned group for tasks with null assignee_name', () => {
    const tasks = [{ id: 1, title: 'No owner', assignee_name: null }]
    const wrapper = mountColumn({ tasks })
    expect(wrapper.text()).toContain('Unassigned')
  })

  it('emits the destination status from the completed drag', async () => {
    const wrapper = mountColumn({ tasks: [{ id: 9, title: 'Moving task' }] })
    const source = wrapper.getComponent({ name: 'draggable' })
    const target = document.createElement('div')
    target.dataset.taskBoard = 'standard'
    target.dataset.taskStatus = 'in_progress'
    target.getBoundingClientRect = () => ({ left: 0, top: 0, right: 100, bottom: 100 })

    await source.vm.$emit('end', {
      from: source.element, to: target, item: wrapper.get('[data-sort-task-id="9"]').element,
      oldDraggableIndex: 2, newDraggableIndex: 1, originalEvent: { clientX: 50, clientY: 50 },
    })

    expect(wrapper.emitted('move')).toEqual([[{
      taskId: 9, status: 'in_progress', boardKey: 'standard', index: 1,
    }]])
  })

  it('discards a release outside the destination', async () => {
    const wrapper = mountColumn({ tasks: [{ id: 9, title: 'Moving task' }] })
    const source = wrapper.getComponent({ name: 'draggable' })
    source.element.getBoundingClientRect = () => ({ left: 0, top: 0, right: 100, bottom: 100 })

    await source.vm.$emit('end', {
      from: source.element, to: source.element, item: wrapper.get('[data-sort-task-id="9"]').element,
      oldDraggableIndex: 2, newDraggableIndex: 1, originalEvent: { clientX: 200, clientY: 50 },
    })

    expect(wrapper.emitted('move')).toBeUndefined()
  })
})
