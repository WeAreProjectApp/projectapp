/**
 * Tests for FolderManagerModal.vue.
 *
 * Covers: rendering, empty state, folder list, create flow,
 * rename flow (start/cancel/commit/Esc), delete flow (ask/confirm/cancel),
 * close, modelValue watcher, handleReorder success and failure.
 */

const mockFolderStore = {
  folderById: (id) => mockFolderStore.folders.find((f) => f.id === id) || null,
  folders: [],
  isUpdating: false,
  fetchFolders: jest.fn(),
  createFolder: jest.fn(),
  updateFolder: jest.fn(),
  deleteFolder: jest.fn(),
  reorderFolders: jest.fn(),
  archivedContentCount: (f) => (f?.archived_document_count || 0)
    + (f?.archived_children_count || 0),
  // Getters de jerarquía, espejo de los del store real document_folders.js.
  get activeFolders() {
    return mockFolderStore.folders.filter((f) => !f.is_archived);
  },
  get rootFolders() {
    return mockFolderStore.folders.filter((f) => f.parent == null && !f.is_archived);
  },
  childrenOf: (id) => mockFolderStore.folders.filter((f) => f.parent === id),
  descendantIdsOf: (id) => {
    const result = new Set();
    const pending = mockFolderStore.folders
      .filter((f) => f.parent === id)
      .map((f) => f.id);
    while (pending.length) {
      const current = pending.pop();
      if (result.has(current)) continue;
      result.add(current);
      mockFolderStore.folders
        .filter((f) => f.parent === current)
        .forEach((f) => pending.push(f.id));
    }
    return result;
  },
};

// Nuxt auto-import — must be set before the component is required
global.useDocumentFolderStore = jest.fn(() => mockFolderStore);

import { mount } from '@vue/test-utils';
import FolderManagerModal from '../../components/panel/documents/FolderManagerModal.vue';
import FolderManagerTree from '../../components/panel/documents/FolderManagerTree.vue';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseSelect from '../../components/base/BaseSelect.vue';

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

const DraggableStub = {
  name: 'Draggable',
  props: ['modelValue', 'itemKey', 'handle', 'ghostClass', 'chosenClass', 'dragClass'],
  emits: ['update:modelValue', 'end'],
  template: '<div data-testid="folder-draggable"><slot name="item" v-for="(el, i) in modelValue" :key="i" :element="el" /></div>',
};

// El formulario compartido tiene su propio spec; acá sólo importa a quién se
// lo entrega este modal y qué hace con lo que le devuelve.
const FolderFormModalStub = {
  name: 'FolderFormModal',
  props: ['modelValue', 'folder', 'initialParent', 'inheritFrom'],
  emits: ['update:modelValue', 'saved', 'change-client'],
  template: '<div class="folder-form-modal-stub" />',
};

const baseFolder = { id: 1, name: 'Design', parent: null, document_count: 3 };
const emptyFolder = { id: 9, name: 'Empty', parent: null, document_count: 0 };

function mountModal(props = {}) {
  return mount(FolderManagerModal, {
    props: { modelValue: true, ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
        draggable: DraggableStub,
        FolderFormModal: FolderFormModalStub,
      },
      components: { BaseFormField, BaseInput, BaseSelect },
    },
  });
}

describe('FolderManagerModal', () => {
  function expectDescribedError(wrapper, control, message) {
    const errorId = control.attributes('aria-describedby');
    const error = wrapper.findAll('[role="alert"]')
      .find((node) => node.attributes('id') === errorId);
    expect(error.exists()).toBe(true);
    expect(error.text()).toBe(message);
  }
  beforeEach(() => {
    mockFolderStore.folders = [];
    mockFolderStore.isUpdating = false;
    mockFolderStore.fetchFolders.mockReset().mockResolvedValue({ success: true });
    mockFolderStore.createFolder.mockReset().mockResolvedValue({ success: true });
    mockFolderStore.updateFolder.mockReset().mockResolvedValue({ success: true });
    mockFolderStore.deleteFolder.mockReset().mockResolvedValue({ success: true });
    mockFolderStore.reorderFolders.mockReset().mockResolvedValue({ success: true });
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  describe('rendering', () => {
    it('renders the modal heading when modelValue is true', () => {
      const wrapper = mountModal();

      expect(wrapper.text()).toContain('Gestionar carpetas');
    });

    it('does not render modal content when modelValue is false', () => {
      const wrapper = mountModal({ modelValue: false });

      expect(wrapper.text()).not.toContain('Gestionar carpetas');
    });

    it('shows the empty state when no folders exist', () => {
      const wrapper = mountModal();

      expect(wrapper.text()).toContain('Sin carpetas todavía');
    });

    it('renders the folder name when folders are in the store', () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal();

      expect(wrapper.text()).toContain('Design');
    });

    it('shows the document count badge for each folder', () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal();

      expect(wrapper.text()).toContain('3');
    });
  });

  // ── handleCreate ──────────────────────────────────────────────────────────

  describe('handleCreate', () => {
    it('calls createFolder with the trimmed name when the form is submitted', async () => {
      const wrapper = mountModal();
      await wrapper.find('input[placeholder]').setValue('  My Folder  ');
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(mockFolderStore.createFolder).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'My Folder', parent: null }),
      );
    });

    // Falla si la validación local vuelve a bloquear preventivamente la acción.
    it('keeps Crear enabled before validation', () => {
      const wrapper = mountModal();

      const createButton = wrapper.findAll('button').find((btn) => btn.text() === 'Crear');
      expect(createButton.element.disabled).toBe(false);
    });

    // Falla si el envío vacío no marca el control o lleva su explicación a otra zona del modal.
    it('marks an empty folder name with its described error', async () => {
      const wrapper = mountModal();
      await wrapper.find('form').trigger('submit');

      const name = wrapper.get('[data-testid="folder-manager-new-name"]');

      expect(mockFolderStore.createFolder).toHaveBeenCalledTimes(0);
      expect(name.attributes('aria-invalid')).toBe('true');
      expectDescribedError(wrapper, name, 'Escribe el nombre de la carpeta.');
    });

    // Falla si corregir el nombre conserva la marca de error obsoleta.
    it('clears the folder name validation after typing', async () => {
      const wrapper = mountModal();
      await wrapper.find('form').trigger('submit');
      const name = wrapper.get('[data-testid="folder-manager-new-name"]');
      const errorId = name.attributes('aria-describedby');

      await name.setValue('Diseño');

      expect(name.attributes('aria-invalid')).toBeUndefined();
      expect(name.attributes('aria-describedby')).toBeUndefined();
      expect(wrapper.findAll('[role="alert"]')
        .some((node) => node.attributes('id') === errorId)).toBe(false);
    });

    it('clears the input and emits changed after a successful create', async () => {
      const wrapper = mountModal();
      await wrapper.find('input[placeholder]').setValue('New Folder');
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.find('input[placeholder]').element.value).toBe('');
      expect(wrapper.emitted('changed')).toHaveLength(1);
    });

    it('shows an error message when createFolder fails', async () => {
      mockFolderStore.createFolder.mockResolvedValue({
        success: false,
        errors: 'Nombre ya existe.',
      });
      const wrapper = mountModal();
      await wrapper.find('input[placeholder]').setValue('Dup');
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(wrapper.text()).toContain('Nombre ya existe.');
    });
  });

  // ── Edit flow ─────────────────────────────────────────────────────────────

  describe('edit flow', () => {
    // El panel de edición inline se consolidó en FolderFormModal, igual que
    // antes el de borrado en DeleteFolderModal: un solo formulario de carpeta,
    // y este modal deja de ser el único camino para editar lo que ya existe.

    it('opens the shared folder form with the folder when the pencil is clicked', async () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal();

      await wrapper.find('[title="Editar carpeta"]').trigger('click');

      const form = wrapper.findComponent({ name: 'FolderFormModal' });
      expect(form.props('modelValue')).toBe(true);
      expect(form.props('folder')).toMatchObject({ id: 1 });
    });

    it('no longer edits inline', async () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal();

      await wrapper.find('[title="Editar carpeta"]').trigger('click');

      // Sólo queda el input de crear: la edición vive en el modal compartido.
      expect(wrapper.findAll('input[type="text"]').length).toBe(1);
    });

    it('refreshes and emits changed after the form saves', async () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal();
      mockFolderStore.fetchFolders.mockClear();

      wrapper.findComponent({ name: 'FolderFormModal' }).vm.$emit('saved', baseFolder);
      await flushPromises();

      // El listado se recarga UNA vez y el padre se entera UNA vez: dos avisos
      // por un guardado harían al gestor refrescar dos veces.
      expect(mockFolderStore.fetchFolders).toHaveBeenCalledTimes(1);
      expect(wrapper.emitted('changed')).toHaveLength(1);
      // Y el formulario deja de apuntar a la carpeta que ya guardó.
      expect(wrapper.findComponent({ name: 'FolderFormModal' }).props('folder'))
        .toBeNull();
    });

    it('passes a folder_has_content conflict up to the cascade', async () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal();

      wrapper.findComponent({ name: 'FolderFormModal' })
        .vm.$emit('change-client', { folder: baseFolder, clientProfileId: 9 });
      await flushPromises();

      expect(wrapper.emitted('change-client')[0][0]).toMatchObject({
        clientProfileId: 9,
      });
    });
  });

  describe('create inherits from the parent folder', () => {
    it('sends the parent folder client and project on create', async () => {
      mockFolderStore.folders = [
        { id: 4, name: 'Kore', parent: null, client: 7, project: 3 },
      ];
      const wrapper = mountModal({ modelValue: false, initialParent: 4 });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();
      await wrapper.find('input[type="text"]').setValue('Diseño');
      await wrapper.find('form').trigger('submit');

      expect(mockFolderStore.createFolder).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'Diseño', parent: 4, client: 7, project: 3 }),
      );
    });

    it('sends no association when the parent has none', async () => {
      mockFolderStore.folders = [{ id: 4, name: 'Varios', parent: null }];
      const wrapper = mountModal({ modelValue: false, initialParent: 4 });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();
      await wrapper.find('input[type="text"]').setValue('Sub');
      await wrapper.find('form').trigger('submit');

      expect(mockFolderStore.createFolder).toHaveBeenCalledWith(
        expect.objectContaining({ client: null, project: null }),
      );
    });
  });

  // ── Delete flow ───────────────────────────────────────────────────────────

  describe('delete flow', () => {
    // El panel inline de borrado se consolidó en DeleteFolderModal: un solo
    // contrato de borrado de carpeta (con reja de confirmación) en toda la app.

    it('opens DeleteFolderModal with the folder when the tree delete icon is clicked', async () => {
      mockFolderStore.folders = [emptyFolder];
      const wrapper = mountModal();

      await wrapper.find('[title="Eliminar carpeta"]').trigger('click');

      const child = wrapper.findComponent({ name: 'DeleteFolderModal' });
      expect(child.props('modelValue')).toBe(true);
      expect(child.props('folder')).toEqual(emptyFolder);
    });

    it('opens the same modal from the archive icon, which offers archiving for a filled folder', async () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal();

      await wrapper.find('[title="Archivar carpeta"]').trigger('click');

      const child = wrapper.findComponent({ name: 'DeleteFolderModal' });
      expect(child.props('modelValue')).toBe(true);
      expect(child.props('folder')).toEqual(baseFolder);
    });

    it('refreshes and emits changed after the child modal reports a delete', async () => {
      mockFolderStore.folders = [emptyFolder];
      const wrapper = mountModal();
      await wrapper.find('[title="Eliminar carpeta"]').trigger('click');

      mockFolderStore.fetchFolders.mockClear();
      wrapper.findComponent({ name: 'DeleteFolderModal' }).vm.$emit('deleted', emptyFolder);
      await flushPromises();

      // La lista se recarga en el scope activo, y el padre avisa una sola vez.
      expect(mockFolderStore.fetchFolders).toHaveBeenCalledTimes(1);
      expect(wrapper.emitted('changed')).toHaveLength(1);
      expect(wrapper.findComponent({ name: 'DeleteFolderModal' }).props('folder')).toBeNull();
    });

    it('re-emits archived with the cascade counts after the child modal archives', async () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal();
      await wrapper.find('[title="Archivar carpeta"]').trigger('click');

      const payload = { folder: baseFolder, folders: 1, documents: 3 };
      wrapper.findComponent({ name: 'DeleteFolderModal' }).vm.$emit('archived', payload);
      await flushPromises();

      expect(wrapper.emitted('archived')).toEqual([[payload]]);
      expect(wrapper.emitted('changed')).toHaveLength(1);
    });
  });

  // ── Close ──────────────────────────────────────────────────────────────────

  describe('close', () => {
    it('emits update:modelValue with false when Cerrar is clicked', async () => {
      const wrapper = mountModal();
      await wrapper.findAll('button').find((btn) => btn.text() === 'Cerrar').trigger('click');

      expect(wrapper.emitted('update:modelValue')[0]).toEqual([false]);
    });
  });

  // ── modelValue watcher ────────────────────────────────────────────────────

  describe('modelValue watcher', () => {
    it('calls fetchFolders when the modal is opened', async () => {
      const wrapper = mountModal({ modelValue: false });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();

      expect(mockFolderStore.fetchFolders).toHaveBeenCalled();
    });
  });

  // ── initialParent prop ──────────────────────────────────────────────────────

  describe('initialParent prop', () => {
    const parentFolder = { id: 5, name: 'Mis Documentos', parent: null, document_count: 0 };

    function optionByText(wrapper, text) {
      return wrapper.findAll('option').find((opt) => opt.text().trim() === text);
    }

    async function openWith(props) {
      mockFolderStore.folders = [parentFolder];
      const wrapper = mountModal({ modelValue: false, ...props });
      await wrapper.setProps({ modelValue: true });
      await flushPromises();
      return wrapper;
    }

    it('pre-selects the initialParent folder in the "Dentro de:" select when opened', async () => {
      const wrapper = await openWith({ initialParent: 5 });

      expect(optionByText(wrapper, 'Mis Documentos').element.selected).toBe(true);
    });

    it('selects the root option when no initialParent is provided', async () => {
      const wrapper = await openWith({});

      expect(optionByText(wrapper, 'Ninguna (carpeta raíz)').element.selected).toBe(true);
    });

    it('resets the select back to initialParent after a successful create', async () => {
      const wrapper = await openWith({ initialParent: 5 });
      await wrapper.find('input[placeholder]').setValue('Nueva');
      await wrapper.find('form').trigger('submit');
      await flushPromises();

      expect(optionByText(wrapper, 'Mis Documentos').element.selected).toBe(true);
    });
  });

  // ── handleReorder ─────────────────────────────────────────────────────────

  describe('handleReorder', () => {
    it('calls reorderFolders with the folder id order when the tree reorders', async () => {
      mockFolderStore.folders = [
        { id: 1, name: 'A', parent: null, document_count: 0 },
        { id: 2, name: 'B', parent: null, document_count: 0 },
      ];
      const wrapper = mountModal();
      wrapper.findComponent(FolderManagerTree).vm.$emit('reorder', { orderedIds: [1, 2] });
      await flushPromises();

      expect(mockFolderStore.reorderFolders).toHaveBeenCalledWith([1, 2]);
    });

    it('shows an error message when reorderFolders fails', async () => {
      mockFolderStore.folders = [{ id: 1, name: 'A', parent: null, document_count: 0 }];
      mockFolderStore.reorderFolders.mockResolvedValue({ success: false });
      const wrapper = mountModal();
      wrapper.findComponent(FolderManagerTree).vm.$emit('reorder', { orderedIds: [1] });
      await flushPromises();

      expect(wrapper.text()).toContain('Error al reordenar');
    });
  });
});
