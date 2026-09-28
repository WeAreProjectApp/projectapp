/**
 * Tests for MoveFolderModal.vue.
 *
 * Covers: visibility, document title, folder list, moveToFolder flows
 * (null/folder-id), changed emit, error display, close/cancel emits.
 */

const mockDocumentStore = {
  updateDocument: jest.fn(),
};

const mockFolderStore = {
  folders: [],
  // El selector de destino sólo puede ofrecer carpetas activas.
  get activeFolders() {
    return mockFolderStore.folders.filter((f) => !f.is_archived);
  },
  childrenOf: (id) => mockFolderStore.folders.filter((f) => (f.parent ?? null) === id),
};

// Nuxt auto-imports — must be set before the component is required
global.useDocumentStore = jest.fn(() => mockDocumentStore);
global.useDocumentFolderStore = jest.fn(() => mockFolderStore);

import { mount } from '@vue/test-utils';
import MoveFolderModal from '../../components/panel/documents/MoveFolderModal.vue';

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

const baseDocument = { id: 10, title: 'Especificaciones técnicas', folder: null };
const baseFolder = { id: 3, name: 'Propuestas', parent: null, document_count: 5 };

function mountModal(props = {}) {
  return mount(MoveFolderModal, {
    props: { modelValue: true, document: baseDocument, ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        Transition: { template: '<div><slot /></div>' },
      },
    },
  });
}

describe('MoveFolderModal', () => {
  beforeEach(() => {
    mockFolderStore.folders = [];
    mockDocumentStore.updateDocument.mockReset().mockResolvedValue({ success: true });
  });

  // ── Visibility ────────────────────────────────────────────────────────────

  describe('visibility', () => {
    it('does not render modal content when modelValue is false', () => {
      const wrapper = mountModal({ modelValue: false });

      expect(wrapper.text()).not.toContain('Mover documento');
    });

    it('does not render modal content when document prop is null', () => {
      const wrapper = mountModal({ document: null });

      expect(wrapper.text()).not.toContain('Mover documento');
    });

    it('renders the document title in the modal header', () => {
      const wrapper = mountModal();

      expect(wrapper.text()).toContain('Especificaciones técnicas');
    });
  });

  // ── Folder options ────────────────────────────────────────────────────────

  describe('folder list', () => {
    it('renders the Sin carpeta option', () => {
      const wrapper = mountModal();

      expect(wrapper.text()).toContain('Sin carpeta');
    });

    it('renders all folders from the store', () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal();

      expect(wrapper.text()).toContain('Propuestas');
    });

    it('shows empty state when there are no folders', () => {
      mockFolderStore.folders = [];
      const wrapper = mountModal();

      expect(wrapper.text()).toContain('No hay carpetas creadas.');
    });
  });

  // ── Move to folder ────────────────────────────────────────────────────────

  describe('moveToFolder', () => {
    it('calls updateDocument with null when Sin carpeta is clicked', async () => {
      const wrapper = mountModal({
        document: { ...baseDocument, folder: 5 },
      });
      const sinCarpetaBtn = wrapper.findAll('button').find(b => b.text().includes('Sin carpeta'));
      await sinCarpetaBtn.trigger('click');
      await flushPromises();

      expect(mockDocumentStore.updateDocument).toHaveBeenCalledWith(
        baseDocument.id,
        { folder_id: null }
      );
    });

    it('calls updateDocument with the folder id when a folder button is clicked', async () => {
      mockFolderStore.folders = [baseFolder];
      const wrapper = mountModal({ document: { ...baseDocument, folder: null } });
      const folderBtn = wrapper.findAll('button').find(b => b.text().includes('Propuestas'));
      await folderBtn.trigger('click');
      await flushPromises();

      expect(mockDocumentStore.updateDocument).toHaveBeenCalledWith(
        baseDocument.id,
        { folder_id: baseFolder.id }
      );
    });

    it('emits changed after a successful move', async () => {
      const wrapper = mountModal({
        document: { ...baseDocument, folder: 5 },
      });
      const sinCarpetaBtn = wrapper.findAll('button').find(b => b.text().includes('Sin carpeta'));
      await sinCarpetaBtn.trigger('click');
      await flushPromises();

      expect(wrapper.emitted('changed')).toBeTruthy();
    });

    it('shows an error message when the move fails', async () => {
      mockDocumentStore.updateDocument.mockResolvedValueOnce({ success: false });
      const wrapper = mountModal({
        document: { ...baseDocument, folder: 5 },
      });
      const sinCarpetaBtn = wrapper.findAll('button').find(b => b.text().includes('Sin carpeta'));
      await sinCarpetaBtn.trigger('click');
      await flushPromises();

      expect(wrapper.text()).toContain('No se pudo mover el documento.');
    });

    it('does not call updateDocument when the current folder is already selected', async () => {
      // document.folder === null and clicking Sin carpeta (null) → should just close
      const wrapper = mountModal({ document: { ...baseDocument, folder: null } });
      const sinCarpetaBtn = wrapper.findAll('button').find(b => b.text().includes('Sin carpeta'));
      await sinCarpetaBtn.trigger('click');
      await flushPromises();

      expect(mockDocumentStore.updateDocument).not.toHaveBeenCalled();
    });
  });

  // ── Close / cancel ────────────────────────────────────────────────────────

  describe('close', () => {
    it('emits update:modelValue false when the cancel button is clicked', async () => {
      const wrapper = mountModal();
      const cancelBtn = wrapper.findAll('button').find(b => b.text() === 'Cancelar');
      await cancelBtn.trigger('click');

      expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
    });

    it('emits update:modelValue false when the header close button is clicked', async () => {
      const wrapper = mountModal();
      await wrapper.find('button[aria-label="Cerrar"]').trigger('click');

      expect(wrapper.emitted('update:modelValue')).toEqual([[false]]);
    });
  });

  // ── Cliente distinto al de la carpeta destino ─────────────────────────────

  describe('moving into another client folder', () => {
    // La carpeta organiza, no es dueña: un documento PUEDE quedar con un
    // cliente distinto al de su carpeta. Por eso mover no decide solo — salvo
    // cuando el documento no tiene cliente, donde adoptar no pisa nada.
    const kore = { id: 3, name: 'Kore', client: 7, client_display_name: 'Kore SAS' };
    const ownDoc = { id: 1, title: 'Contrato', folder: null, client: 9 };
    const looseDoc = { id: 2, title: 'Suelto', folder: null, client: null };

    beforeEach(() => {
      mockFolderStore.folders = [kore];
    });

    function folderButton(wrapper) {
      return wrapper.findAll('button').find((b) => b.text().includes('Kore'));
    }

    it('asks before overwriting a client the document already has', async () => {
      const wrapper = mountModal({ document: ownDoc });

      await folderButton(wrapper).trigger('click');
      await flushPromises();

      expect(mockDocumentStore.updateDocument).not.toHaveBeenCalled();
      expect(wrapper.find('[data-testid="move-folder-client-choice"]').exists()).toBe(true);
    });

    it('moves a contract without offering to adopt the destination client', async () => {
      const wrapper = mountModal({ document: { ...ownDoc, is_contract_mirror: true } });
      await folderButton(wrapper).trigger('click');
      await flushPromises();
      expect(mockDocumentStore.updateDocument).toHaveBeenCalledWith(ownDoc.id, { folder_id: 3 });
      expect(wrapper.find('[data-testid="move-folder-client-choice"]').exists()).toBe(false);
    });

    it('keeps the document client when that is the answer', async () => {
      const wrapper = mountModal({ document: ownDoc });
      await folderButton(wrapper).trigger('click');
      await flushPromises();

      await wrapper.find('[data-testid="move-folder-keep-client"]').trigger('click');
      await flushPromises();

      expect(mockDocumentStore.updateDocument).toHaveBeenCalledWith(1, {
        folder_id: 3,
      });
    });

    it('adopts the folder client when that is the answer', async () => {
      const wrapper = mountModal({ document: ownDoc });
      await folderButton(wrapper).trigger('click');
      await flushPromises();

      await wrapper.find('[data-testid="move-folder-adopt-client"]').trigger('click');
      await flushPromises();

      expect(mockDocumentStore.updateDocument).toHaveBeenCalledWith(1, {
        folder_id: 3, adopt_folder_client: true,
      });
    });

    it('does not ask when the document has no client to lose', async () => {
      const wrapper = mountModal({ document: looseDoc });

      await folderButton(wrapper).trigger('click');
      await flushPromises();

      expect(mockDocumentStore.updateDocument).toHaveBeenCalledWith(2, {
        folder_id: 3,
      });
      expect(wrapper.find('[data-testid="move-folder-client-choice"]').exists()).toBe(false);
    });

    it('does not ask when both already belong to the same client', async () => {
      const wrapper = mountModal({
        document: { id: 4, title: 'Suyo', folder: null, client: 7 },
      });

      await folderButton(wrapper).trigger('click');
      await flushPromises();

      expect(mockDocumentStore.updateDocument).toHaveBeenCalled();
      expect(wrapper.find('[data-testid="move-folder-client-choice"]').exists()).toBe(false);
    });
  });
});
