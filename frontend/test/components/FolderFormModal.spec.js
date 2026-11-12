/**
 * Tests for FolderFormModal.vue — el único formulario de carpeta.
 *
 * Cubre las dos modalidades (crear y editar) sobre un mismo form, la herencia
 * de cliente/proyecto desde la carpeta contenedora al crear, que lo heredado
 * se pueda cambiar antes de guardar, y el 409 `folder_has_content` que remite
 * el cambio de cliente a la cascada en vez de tragárselo.
 */

const mockFolderStore = {
  createFolder: jest.fn(),
  updateFolder: jest.fn(),
  fetchFolders: jest.fn(),
  childrenOf: jest.fn(() => []),
  descendantIdsOf: jest.fn(() => new Set()),
  folderById: jest.fn(() => null),
  isUpdating: false,
};

global.useDocumentFolderStore = jest.fn(() => mockFolderStore);

import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import FolderFormModal from '../../components/panel/documents/FolderFormModal.vue';
import BaseModal from '../../components/base/BaseModal.vue';
import BaseInput from '../../components/base/BaseInput.vue';
import BaseButton from '../../components/base/BaseButton.vue';
import BaseAlert from '../../components/base/BaseAlert.vue';
import BaseFormField from '../../components/base/BaseFormField.vue';
import BaseModalActions from '../../components/base/BaseModalActions.vue';
import BaseSelect from '../../components/base/BaseSelect.vue';

const ClientAutocompleteStub = {
  name: 'ClientAutocomplete',
  props: ['modelValue', 'initialLabel'],
  emits: ['update:modelValue', 'select'],
  template: '<div class="client-autocomplete-stub" />',
};

const ProjectSelectStub = {
  name: 'ProjectSelect',
  props: ['modelValue', 'clientProfileId', 'clientLabel', 'allowNoClient'],
  emits: ['update:modelValue', 'select'],
  template: '<div class="project-select-stub" />',
};

function mountModal(props = {}) {
  return mount(FolderFormModal, {
    props: { modelValue: true, ...props },
    global: {
      components: {
        BaseAlert,
        BaseButton,
        BaseFormField,
        BaseInput,
        BaseModal,
        BaseModalActions,
        BaseSelect,
      },
      stubs: {
        NuxtLink: { template: '<a><slot /></a>' },
        Teleport: true,
        Transition: false,
        ClientAutocomplete: ClientAutocompleteStub,
        ProjectSelect: ProjectSelectStub,
      },
    },
  });
}

const nameInput = (w) => w.find('[data-testid="folder-form-name"]');
const saveButton = (w) => w.find('[data-testid="folder-form-save"]');
const clientField = (w) => w.findComponent(ClientAutocompleteStub);
const projectField = (w) => w.findComponent(ProjectSelectStub);

describe('FolderFormModal', () => {
  beforeEach(() => {
    mockFolderStore.createFolder.mockReset().mockResolvedValue({
      success: true, data: { id: 10, name: 'Nueva' },
    });
    mockFolderStore.updateFolder.mockReset().mockResolvedValue({
      success: true, data: { id: 5, name: 'Kore' },
    });
    mockFolderStore.fetchFolders.mockReset().mockResolvedValue({ success: true });
    mockFolderStore.childrenOf.mockReset().mockReturnValue([]);
    mockFolderStore.descendantIdsOf.mockReset().mockReturnValue(new Set());
  });

  describe('creating', () => {
    it('creates the folder with the association the operator chose', async () => {
      const wrapper = mountModal();
      await nameInput(wrapper).setValue('Kore');
      clientField(wrapper).vm.$emit('select', { id: 7, name: 'Kore SAS' });
      await nextTick();

      await wrapper.find('form').trigger('submit');

      expect(mockFolderStore.createFolder).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'Kore', client: 7 }),
      );
    });

    it('inherits the client and project of the folder it is created inside', async () => {
      const wrapper = mountModal({
        inheritFrom: {
          id: 3, name: 'Kore', client: 7, client_display_name: 'Kore SAS', project: 4,
        },
        initialParent: 3,
      });
      await nextTick();
      await nameInput(wrapper).setValue('Diseño');

      await wrapper.find('form').trigger('submit');

      expect(mockFolderStore.createFolder).toHaveBeenCalledWith(
        expect.objectContaining({ client: 7, project: 4, parent: 3 }),
      );
    });

    it('lets the operator drop what was inherited — it is a default, not a leash', async () => {
      const wrapper = mountModal({
        inheritFrom: { id: 3, name: 'Kore', client: 7, project: 4 },
        initialParent: 3,
      });
      await nextTick();
      await nameInput(wrapper).setValue('Suelta');
      clientField(wrapper).vm.$emit('select', null);
      await nextTick();

      await wrapper.find('form').trigger('submit');

      expect(mockFolderStore.createFolder).toHaveBeenCalledWith(
        expect.objectContaining({ client: null, project: null }),
      );
    });

    it('refuses to save without a name', async () => {
      const wrapper = mountModal();

      expect(saveButton(wrapper).element.disabled).toBe(false);
      await wrapper.find('form').trigger('submit');

      expect(wrapper.text()).toContain('Escribe el nombre de la carpeta.');
      expect(nameInput(wrapper).attributes('aria-invalid')).toBe('true');
      expect(mockFolderStore.createFolder).not.toHaveBeenCalled();
    });
  });

  describe('editing', () => {
    const folder = {
      id: 5,
      name: 'Kore',
      parent: null,
      client: 7,
      client_display_name: 'Kore SAS',
      project: 4,
      project_name: 'Kore - Diseño',
    };

    it('opens with the folder already loaded into the form', async () => {
      const wrapper = mountModal({ folder });
      await nextTick();

      expect(nameInput(wrapper).element.value).toBe('Kore');
      expect(clientField(wrapper).props('modelValue')).toBe(7);
      expect(projectField(wrapper).props('modelValue')).toBe(4);
    });

    it('patches only the folder it was handed', async () => {
      const wrapper = mountModal({ folder });
      await nextTick();
      await nameInput(wrapper).setValue('Kore Health');

      await wrapper.find('form').trigger('submit');

      expect(mockFolderStore.updateFolder).toHaveBeenCalledWith(
        5, expect.objectContaining({ name: 'Kore Health' }),
      );
      expect(mockFolderStore.createFolder).not.toHaveBeenCalled();
    });

    it('emits saved so the caller can refresh', async () => {
      const wrapper = mountModal({ folder });
      await nextTick();
      await nameInput(wrapper).setValue('Kore Health');

      await wrapper.find('form').trigger('submit');
      await nextTick();

      // El payload guardado viaja con el evento: el caller refresca con él.
      expect(wrapper.emitted('saved')[0]).toEqual([{ id: 5, name: 'Kore' }]);
      expect(wrapper.emitted('update:modelValue')[0]).toEqual([false]);
    });

    it('hands a folder_has_content conflict to the cascade instead of erroring', async () => {
      mockFolderStore.updateFolder.mockResolvedValue({
        success: false,
        errors: { code: 'folder_has_content' },
        code: 'folder_has_content',
      });
      const wrapper = mountModal({ folder });
      await nextTick();
      clientField(wrapper).vm.$emit('select', { id: 9, name: 'Ana' });
      await nextTick();

      await wrapper.find('form').trigger('submit');
      await nextTick();

      expect(wrapper.emitted('change-client')).toBeTruthy();
      expect(wrapper.emitted('change-client')[0][0]).toMatchObject({
        folder: expect.objectContaining({ id: 5 }),
        clientProfileId: 9,
      });
    });

    it('shows a backend name failure beside the name field', async () => {
      mockFolderStore.updateFolder.mockResolvedValue({
        success: false, errors: { name: ['Ya existe.'] },
      });
      const wrapper = mountModal({ folder });
      await nextTick();
      await nameInput(wrapper).setValue('Repetida');

      await wrapper.find('form').trigger('submit');
      await nextTick();

      expect(wrapper.text()).toContain('Ya existe.');
      expect(nameInput(wrapper).attributes('aria-invalid')).toBe('true');
      expect(wrapper.find('[data-testid="folder-form-error"]').exists()).toBe(false);
      expect(wrapper.emitted('saved')).toBeFalsy();
    });
  });
});
