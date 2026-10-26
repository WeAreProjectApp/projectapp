/**
 * Tests for FolderBreadcrumb.vue.
 *
 * Navegar el archivo exige que la ruta se resuelva también sobre carpetas
 * archivadas, y que soltar algo activo dentro de una archivada se rechace.
 */

const mockFolderStore = {
  folders: [],
  ancestorsOf: (id) => {
    const chain = [];
    let current = mockFolderStore.folders.find((f) => f.id === id) || null;
    while (current) {
      chain.unshift(current);
      current = current.parent == null
        ? null
        : mockFolderStore.folders.find((f) => f.id === current.parent) || null;
    }
    return chain;
  },
  folderById: (id) => mockFolderStore.folders.find((f) => f.id === id) || null,
  descendantIdsOf: () => new Set(),
};

global.useDocumentFolderStore = jest.fn(() => mockFolderStore);

import { mount } from '@vue/test-utils';
import FolderBreadcrumb from '../../components/panel/documents/FolderBreadcrumb.vue';

function mountCrumb(props = {}) {
  return mount(FolderBreadcrumb, { props: { activeId: 'all', ...props } });
}

describe('FolderBreadcrumb', () => {
  beforeEach(() => {
    mockFolderStore.folders = [
      { id: 1, name: 'Clientes', parent: null },
      { id: 2, name: '2026', parent: 1 },
      { id: 3, name: 'temp', parent: null, is_archived: true },
      { id: 4, name: 'Actas', parent: 3, is_archived: true },
    ];
  });

  it('renders the active path', () => {
    const wrapper = mountCrumb({ activeId: 2 });

    expect(wrapper.text()).toContain('Clientes');
    expect(wrapper.text()).toContain('2026');
  });

  it('renders a path when its host already provides the root control', () => {
    const wrapper = mountCrumb({ activeId: 2, showRoot: false, ariaLabel: 'Ubicación' });

    expect(wrapper.find('nav').attributes('aria-label')).toBe('Ubicación');
    expect(wrapper.findAll('button').map((button) => button.text())).toEqual(['Clientes']);
    expect(wrapper.text()).toContain('2026');
  });

  it('resolves a path that runs through archived folders', () => {
    const wrapper = mountCrumb({ activeId: 4 });

    expect(wrapper.text()).toContain('temp');
    expect(wrapper.text()).toContain('Actas');
  });

  it('flags the archived segments of the path', () => {
    const wrapper = mountCrumb({ activeId: 4 });

    expect(wrapper.text()).toContain('Archivado');
  });

  it('lets the root crumb be renamed and retargeted for the archive', async () => {
    const wrapper = mountCrumb({ activeId: 4, rootLabel: 'Archivados', rootValue: 'root' });

    const root = wrapper.find('[data-testid="folder-breadcrumb-root"]');
    expect(root.text()).toBe('Archivados');

    await root.trigger('click');
    expect(wrapper.emitted('select')).toEqual([['root']]);
  });

  it('defaults the root crumb to the active listing', async () => {
    const wrapper = mountCrumb({ activeId: 2 });

    await wrapper.find('[data-testid="folder-breadcrumb-root"]').trigger('click');

    expect(wrapper.emitted('select')).toEqual([['all']]);
  });

  it('refuses to nest a folder inside an archived crumb', async () => {
    // Dejaría contenido activo sin ubicación alcanzable, que es justo el
    // estado que esta tanda elimina.
    const wrapper = mountCrumb({ activeId: 4, draggingFolderId: 1 });

    const crumb = wrapper.findAll('button').find((b) => b.text() === 'temp');
    await crumb.trigger('drop');

    expect(wrapper.emitted('nest')).toBeUndefined();
  });

  it('accepts nesting into an active crumb', async () => {
    const wrapper = mountCrumb({ activeId: 2, draggingFolderId: 9 });

    const crumb = wrapper.findAll('button').find((b) => b.text() === 'Clientes');
    await crumb.trigger('drop');

    expect(wrapper.emitted('nest')).toEqual([[{ destId: 1, draggedFolderId: 9 }]]);
  });
});
