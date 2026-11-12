/**
 * Tests for FolderManagerTree.vue.
 *
 * Covers the per-folder action cluster: editar / archivar / eliminar, and the
 * events each one emits. Archivar vive aquí — y no en la fila del sidebar —
 * porque este es el único sitio donde editar y eliminar ya conviven con
 * espacio de sobra.
 */

const mockFolderStore = {
  childrenOf: jest.fn(() => []),
};

// Nuxt auto-import — must be set before the component is required
global.useDocumentFolderStore = jest.fn(() => mockFolderStore);

import { mount } from '@vue/test-utils';
import FolderManagerTree from '../../components/panel/documents/FolderManagerTree.vue';

const folder = { id: 4, name: 'Contratos', parent: null, document_count: 3, children_count: 0 };

function mountTree(props = {}) {
  return mount(FolderManagerTree, {
    props: { siblings: [folder], parentId: null, depth: 0, ...props },
    global: {
      stubs: {
        draggable: {
          props: ['modelValue'],
          template: '<div><template v-for="el in modelValue"><slot name="item" :element="el" /></template></div>',
        },
      },
    },
  });
}

describe('FolderManagerTree', () => {
  beforeEach(() => {
    mockFolderStore.childrenOf.mockReset().mockReturnValue([]);
  });

  it('renders the archive button between edit and delete', () => {
    const wrapper = mountTree();
    const titles = wrapper.findAll('button').map((b) => b.attributes('title'));

    const editAt = titles.indexOf('Editar carpeta');
    const archiveAt = titles.indexOf('Archivar carpeta');
    const deleteAt = titles.indexOf('Eliminar carpeta');

    expect(archiveAt).toBeGreaterThan(editAt);
    expect(archiveAt).toBeLessThan(deleteAt);
  });

  it('emits archive with the folder', async () => {
    const wrapper = mountTree();

    await wrapper.find('[data-testid="folder-manager-archive"]').trigger('click');

    expect(wrapper.emitted('archive')).toEqual([[folder]]);
  });

  it('emits delete with the folder', async () => {
    const wrapper = mountTree();

    await wrapper.find('[data-testid="folder-manager-delete"]').trigger('click');

    expect(wrapper.emitted('delete')).toEqual([[folder]]);
  });

  it('offers archiving even for a folder that holds documents', () => {
    // Es el punto: archivar no destruye nada, así que no comparte la
    // restricción de eliminar.
    const wrapper = mountTree({ siblings: [{ ...folder, document_count: 12 }] });

    expect(wrapper.find('[data-testid="folder-manager-archive"]').exists()).toBe(true);
  });

  it('hides structural controls for a system-managed folder', () => {
    const wrapper = mountTree({
      siblings: [{ ...folder, is_system_managed: true }],
    });

    expect(wrapper.find('.folder-tree-handle').exists()).toBe(false);
    expect(wrapper.find('[data-testid="folder-manager-archive"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="folder-manager-delete"]').exists()).toBe(false);
  });
});
