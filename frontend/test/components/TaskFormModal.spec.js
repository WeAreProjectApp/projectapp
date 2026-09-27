/**
 * Tests for TaskFormModal.vue.
 *
 * Covers: rendering, heading per mode, form population, submit payload,
 * close actions, delete, archive flow, modelValue watcher,
 * comment and alert CRUD.
 */

const mockTaskStore = {
  taskAlerts: {},
  comments: {},
  alertsLoading: false,
  commentsLoading: false,
  fetchTaskAlerts: jest.fn(),
  fetchTaskComments: jest.fn(),
  addTaskComment: jest.fn(),
  deleteTaskComment: jest.fn(),
  createTaskAlert: jest.fn(),
  deleteTaskAlert: jest.fn(),
};

jest.mock('../../stores/tasks', () => ({
  useTaskStore: () => mockTaskStore,
}));

import { mount } from '@vue/test-utils';
import TaskFormModal from '../../components/Tasks/TaskFormModal.vue';
import BaseButton from '../../components/base/BaseButton.vue';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseModal from '../../components/base/BaseModal.vue';
import BaseModalActions from '../../components/base/BaseModalActions.vue';
import BaseSelect from '../../components/base/BaseSelect.vue';
import BaseTextarea from '../../components/base/BaseTextarea.vue';

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

const baseTask = {
  id: 1,
  title: 'Fix the bug',
  description: 'Something is broken',
  status: 'in_progress',
  priority: 'high',
  board_type: 'standard',
  due_date: '2026-05-01',
  assignee: '',
  is_archived: false,
};

function mountModal(props = {}, attachToBody = false) {
  return mount(TaskFormModal, {
    props: {
      modelValue: true,
      ...props,
    },
    attachTo: attachToBody ? document.body : undefined,
    global: {
      // Nuxt auto-imports base components in the app; jest does not.
      components: {
        BaseButton,
        BaseFormField,
        BaseInput,
        BaseModal,
        BaseModalActions,
        BaseSelect,
        BaseTextarea,
      },
      stubs: {
        NuxtLink: { template: '<a><slot /></a>' },
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
      },
    },
  });
}

describe('TaskFormModal', () => {
  beforeEach(() => {
    mockTaskStore.taskAlerts = {};
    mockTaskStore.comments = {};
    mockTaskStore.alertsLoading = false;
    mockTaskStore.commentsLoading = false;
    mockTaskStore.fetchTaskAlerts.mockReset().mockResolvedValue({ success: true });
    mockTaskStore.fetchTaskComments.mockReset().mockResolvedValue({ success: true });
    mockTaskStore.addTaskComment.mockReset().mockResolvedValue({ success: true });
    mockTaskStore.deleteTaskComment.mockReset().mockResolvedValue({ success: true });
    mockTaskStore.createTaskAlert.mockReset().mockResolvedValue({ success: true });
    mockTaskStore.deleteTaskAlert.mockReset().mockResolvedValue({ success: true });
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  describe('rendering', () => {
    it('renders the modal wrapper when modelValue is true', () => {
      const wrapper = mountModal();

      expect(wrapper.find('[data-testid="task-form-modal"]').exists()).toBe(true);
    });

    it('does not render modal content when modelValue is false', () => {
      const wrapper = mountModal({ modelValue: false });

      expect(wrapper.find('[data-testid="task-form-modal"]').exists()).toBe(false);
    });

    it('shows New task heading when no task id is provided', () => {
      const wrapper = mountModal();

      expect(wrapper.text()).toContain('New task');
    });

    it('shows Edit task heading when the task has an id', () => {
      const wrapper = mountModal({ task: baseTask });

      expect(wrapper.text()).toContain('Edit task');
    });

    it('renders the title input', () => {
      const wrapper = mountModal();

      expect(wrapper.find('[data-testid="task-title-input"]').exists()).toBe(true);
    });

    it('shows Crear on the submit button for a new task', () => {
      const wrapper = mountModal();

      expect(wrapper.find('[data-testid="task-submit-btn"]').text()).toBe('Crear');
    });

    it('shows Guardar on the submit button when editing an existing task', () => {
      const wrapper = mountModal({ task: baseTask });

      expect(wrapper.find('[data-testid="task-submit-btn"]').text()).toBe('Guardar');
    });
  });

  // ── Form population ────────────────────────────────────────────────────────

  describe('form population', () => {
    it('populates the title input from the task prop when editing', () => {
      const wrapper = mountModal({ task: baseTask });

      expect(wrapper.find('[data-testid="task-title-input"]').element.value).toBe('Fix the bug');
    });

    it('leaves the title input empty for a new task', () => {
      const wrapper = mountModal();

      expect(wrapper.find('[data-testid="task-title-input"]').element.value).toBe('');
    });

    it('keeps submit available and explains the missing title beside its field', async () => {
      const wrapper = mountModal();

      const submit = wrapper.find('[data-testid="task-submit-btn"]');
      expect(submit.element.disabled).toBe(false);

      await wrapper.find('form').trigger('submit');

      expect(wrapper.text()).toContain('Escribe el título de la tarea.');
      expect(wrapper.find('[data-testid="task-title-input"]').attributes('aria-invalid')).toBe('true');
      expect(wrapper.emitted('submit')).toBeUndefined();
    });
  });

  // ── handleSubmit ──────────────────────────────────────────────────────────

  describe('handleSubmit', () => {
    it('emits submit with a trimmed title from the footer save action', async () => {
      // Falla si el botón fijo pierde la asociación con el formulario de tarea.
      const wrapper = mountModal({}, true);
      await wrapper.find('[data-testid="task-title-input"]').setValue('  My new task  ');
      const submit = wrapper.get('[data-testid="task-submit-btn"]');

      submit.element.click();
      await flushPromises();

      expect(wrapper.emitted('submit')[0][0].title).toBe('My new task');
      wrapper.unmount();
    });

    it('includes status, priority, and board_type in the submit payload', async () => {
      const wrapper = mountModal({ task: baseTask });
      await wrapper.find('form').trigger('submit');

      const payload = wrapper.emitted('submit')[0][0];
      expect(payload.status).toBe('in_progress');
      expect(payload.priority).toBe('high');
      expect(payload.board_type).toBe('standard');
    });

    it('sets due_date to null in the payload when the date input is empty', async () => {
      const wrapper = mountModal();
      await wrapper.find('[data-testid="task-title-input"]').setValue('No date task');
      await wrapper.find('form').trigger('submit');

      expect(wrapper.emitted('submit')[0][0].due_date).toBeNull();
    });
  });

  // ── Close ──────────────────────────────────────────────────────────────────

  describe('close', () => {
    it('emits update:modelValue with false when Cancelar is clicked', async () => {
      const wrapper = mountModal();
      await wrapper.findAll('button').find((btn) => btn.text() === 'Cancelar').trigger('click');

      expect(wrapper.emitted('update:modelValue')[0]).toEqual([false]);
    });

    it('emits update:modelValue with false when the accessible close action is clicked', async () => {
      const wrapper = mountModal();
      await wrapper.get('button[aria-label="Cerrar formulario de tarea"]').trigger('click');

      expect(wrapper.emitted('update:modelValue')[0]).toEqual([false]);
    });
  });

  // ── handleDelete ──────────────────────────────────────────────────────────

  describe('handleDelete', () => {
    it('emits delete with the task object when Eliminar is clicked', async () => {
      const wrapper = mountModal({ task: baseTask });
      await wrapper.findAll('button').find((btn) => btn.text() === 'Eliminar').trigger('click');

      expect(wrapper.emitted('delete')[0][0]).toEqual(baseTask);
    });
  });

  // ── handleArchive ──────────────────────────────────────────────────────────

  describe('handleArchive', () => {
    it('shows the archive form when Archivar tarea is clicked', async () => {
      const wrapper = mountModal({ task: baseTask });
      await wrapper.findAll('button').find((btn) => btn.text().includes('Archivar tarea')).trigger('click');

      expect(wrapper.text()).toContain('Confirmar archivo');
    });

    it('emits archive with the task and trimmed reason when Confirmar archivo is clicked', async () => {
      const wrapper = mountModal({ task: baseTask });
      await wrapper.findAll('button').find((btn) => btn.text().includes('Archivar tarea')).trigger('click');
      await wrapper.get('[data-testid="task-archive-reason"]').setValue('  Ya no es necesaria  ');
      await wrapper.findAll('button').find((btn) => btn.text().includes('Confirmar archivo')).trigger('click');

      expect(wrapper.emitted('archive')[0][0]).toEqual(baseTask);
      expect(wrapper.emitted('archive')[0][1]).toBe('Ya no es necesaria');
    });

    it('hides the archive form when the cancel link is clicked', async () => {
      const wrapper = mountModal({ task: baseTask });
      await wrapper.findAll('button').find((btn) => btn.text().includes('Archivar tarea')).trigger('click');
      await wrapper.findAll('button').find((btn) => btn.text() === 'Cancelar').trigger('click');

      expect(wrapper.text()).not.toContain('Confirmar archivo');
    });
  });

  // ── modelValue watcher ────────────────────────────────────────────────────

  describe('modelValue watcher', () => {
    it('fetches alerts and comments when the modal opens with an existing task', async () => {
      const wrapper = mountModal({ modelValue: false, task: baseTask });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      expect(mockTaskStore.fetchTaskAlerts).toHaveBeenCalledWith(1);
      expect(mockTaskStore.fetchTaskComments).toHaveBeenCalledWith(1);
    });

    it('does not fetch when the modal opens for a new task with no id', async () => {
      const wrapper = mountModal({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      expect(mockTaskStore.fetchTaskAlerts).not.toHaveBeenCalled();
      expect(mockTaskStore.fetchTaskComments).not.toHaveBeenCalled();
    });
  });

  // ── handleAddComment ──────────────────────────────────────────────────────

  describe('handleAddComment', () => {
    it('calls store.addTaskComment when Enter is pressed in the comment input', async () => {
      const wrapper = mountModal({ task: baseTask });
      const commentInput = wrapper.find('input[placeholder="Agregar comentario…"]');
      await commentInput.setValue('Great progress!');
      await commentInput.trigger('keydown', { key: 'Enter' });
      await flushPromises();

      expect(mockTaskStore.addTaskComment).toHaveBeenCalledWith(1, 'Great progress!');
    });

    it('clears the comment input after a successful add', async () => {
      const wrapper = mountModal({ task: baseTask });
      const commentInput = wrapper.find('input[placeholder="Agregar comentario…"]');
      await commentInput.setValue('Great progress!');
      await commentInput.trigger('keydown', { key: 'Enter' });
      await flushPromises();

      expect(commentInput.element.value).toBe('');
    });
  });

  // ── handleDeleteComment ───────────────────────────────────────────────────

  describe('handleDeleteComment', () => {
    it('calls store.deleteTaskComment when the comment delete button is clicked', async () => {
      mockTaskStore.comments = {
        1: [{ id: 20, author_name: 'Carlos', created_at: '2026-04-10T10:00:00Z', text: 'A comment' }],
      };
      const wrapper = mountModal({ task: baseTask });
      await wrapper.find('li').find('button').trigger('click');
      await flushPromises();

      expect(mockTaskStore.deleteTaskComment).toHaveBeenCalledWith(1, 20);
    });
  });

  // ── handleDeleteAlert ─────────────────────────────────────────────────────

  describe('handleDeleteAlert', () => {
    it('calls store.deleteTaskAlert when the alert delete button is clicked', async () => {
      mockTaskStore.taskAlerts = {
        1: [{ id: 10, notify_at: '2026-05-01', sent: false, note: 'Check client' }],
      };
      const wrapper = mountModal({ task: baseTask });
      await wrapper.find('li').find('button').trigger('click');
      await flushPromises();

      expect(mockTaskStore.deleteTaskAlert).toHaveBeenCalledWith(1, 10);
    });
  });

  // ── handleAddAlert ────────────────────────────────────────────────────────

  describe('handleAddAlert', () => {
    it('calls store.createTaskAlert with the date when the add button is clicked', async () => {
      const wrapper = mountModal({ task: baseTask });
      const dateInputs = wrapper.findAll('input[type="date"]');
      await dateInputs[1].setValue('2026-06-01');
      const addButtons = wrapper.findAll('button').filter((btn) => btn.text().trim() === 'Agregar');
      await addButtons[0].trigger('click');
      await flushPromises();

      expect(mockTaskStore.createTaskAlert).toHaveBeenCalledWith(1, { notify_at: '2026-06-01' });
    });
  });
});
