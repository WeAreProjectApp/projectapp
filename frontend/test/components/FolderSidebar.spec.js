/**
 * Tests for FolderSidebar.vue.
 *
 * Covers: Todos/Sin-carpeta entries, folder list, select emits,
 * manage emits, active styling, reorderFolders on drag-end,
 * folder-drop emit on document drop, row alignment, the archived-content
 * badge, and the two row actions: archivar (siempre disponible, es la salida
 * de una carpeta con contenido) y eliminar (deshabilitado en cuanto la carpeta
 * contiene algo, archivado incluido, igual que el 409 del backend).
 */

const archivedContentCount = (f) => (f?.archived_document_count || 0)
  + (f?.archived_children_count || 0);

/**
 * Conteo DIRECTO por ámbito — el stand-in del rollup en este spec.
 *
 * El algoritmo del subárbol NO se reimplementa acá a propósito: un mock que lo
 * calculara haría que el spec asertara su propia copia. Vive testeado en
 * `test/utils/folderRollup.test.js` y en el store; lo que este archivo fija es
 * que la fila lee el getter recursivo y no `document_count`, y para eso alcanza
 * con que el mock pueda devolver un número distinto del directo.
 */
const directDocs = (f, scope = 'active') => (scope === 'archived'
  ? (f?.archived_document_count ?? (f?.is_archived ? f?.document_count : 0) ?? 0)
  : (f?.active_document_count ?? (f?.is_archived ? 0 : f?.document_count) ?? 0));

const mockFolderStore = {
  reorderFolders: jest.fn(),
  fetchFolders: jest.fn(),
  recursiveDocumentCount: jest.fn(directDocs),
  rollupOf: jest.fn((folder, scope = 'active') => ({
    docs: directDocs(folder, scope),
    subs: folder?.children_count || 0,
  })),
  // Espejo de los getters reales: el ícono de eliminar depende de ellos.
  archivedContentCount,
  totalContentCount: (f) => (f?.active_document_count ?? f?.document_count ?? 0)
    + (f?.active_children_count ?? f?.children_count ?? 0)
    + archivedContentCount(f),
};

// Nuxt auto-import — must be set before the component is required
global.useDocumentFolderStore = jest.fn(() => mockFolderStore);

import { mount } from '@vue/test-utils';
import FolderSidebar from '../../components/panel/documents/FolderSidebar.vue';

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

const folderA = { id: 1, name: 'Propuestas', document_count: 5, children_count: 0 };
const folderB = { id: 2, name: 'Contratos', document_count: 2, children_count: 0 };
const emptyFolder = { id: 3, name: 'Xpandia Project', document_count: 0, children_count: 0 };
const parentFolder = { id: 4, name: 'Clientes', document_count: 0, children_count: 2 };
// Estado mixto: activa por fuera, con archivados dentro — lo que deja una
// restauración por cadena.
const mixedFolder = {
  id: 5,
  name: 'temp',
  document_count: 0,
  children_count: 0,
  active_document_count: 0,
  active_children_count: 0,
  archived_document_count: 2,
  archived_children_count: 0,
};
// Cuatro contadores distintos entre sí para que el número de la fila delate de
// cuál de los dos ámbitos salió (la insignia suma 3+1=4, y no colisiona).
const scopedFolder = {
  id: 6,
  name: 'Mixta',
  document_count: 0,
  children_count: 0,
  active_document_count: 7,
  active_children_count: 0,
  archived_document_count: 3,
  archived_children_count: 1,
};
const projectFolder = {
  id: 10,
  name: 'Kore Health',
  folder_kind: 'project',
  is_project_visible: true,
  managed_project_state: { name: 'Activo', system_key: 'active' },
  document_count: 2,
  children_count: 1,
};
const hiddenProjectFolder = {
  id: 11,
  name: 'Candle',
  folder_kind: 'project',
  is_project_visible: false,
  managed_project_state: { name: 'Suspendido', system_key: 'suspended' },
  document_count: 1,
  children_count: 0,
};
const navigationFacets = {
  totals: {
    active: { folders: 8, documents: 21 },
    archived: { folders: 2, documents: 5 },
  },
  unassigned: {
    project: {
      active: { folders: 1, documents: 3 },
      archived: { folders: 0, documents: 1 },
    },
    client: {
      active: { folders: 2, documents: 4 },
      archived: { folders: 1, documents: 0 },
    },
  },
  projects: [
    {
      id: 91,
      name: 'Kore Health',
      is_visible: true,
      catalog_bucket: 'active',
      state: { name: 'Activo' },
      counts: {
        active: { folders: 3, documents: 9 },
        archived: { folders: 1, documents: 2 },
      },
    },
    {
      id: 92,
      name: 'Candle',
      is_visible: true,
      catalog_bucket: 'archived',
      state: { name: 'Suspendido' },
      counts: {
        active: { folders: 1, documents: 2 },
        archived: { folders: 0, documents: 0 },
      },
    },
    {
      id: 93,
      name: 'Mimittos',
      is_visible: true,
      catalog_bucket: 'active',
      state: { name: 'En desarrollo' },
      counts: {
        active: { folders: 0, documents: 0 },
        archived: { folders: 0, documents: 0 },
      },
    },
  ],
  clients: [
    {
      id: 71,
      name: 'Kore SAS',
      is_archived: false,
      catalog_bucket: 'active',
      counts: {
        active: { folders: 4, documents: 10 },
        archived: { folders: 2, documents: 5 },
      },
    },
    {
      id: 72,
      name: 'Cliente histórico',
      is_archived: true,
      catalog_bucket: 'archived',
      counts: {
        active: { folders: 0, documents: 0 },
        archived: { folders: 0, documents: 0 },
      },
    },
  ],
};

// Stub that renders all items from v-model and can emit @end
const DraggableStub = {
  name: 'draggable',
  props: ['modelValue', 'itemKey', 'handle', 'ghostClass', 'chosenClass', 'disabled', 'tag'],
  emits: ['update:modelValue', 'start', 'end'],
  template: `
    <div data-testid="folder-draggable">
      <slot name="item" v-for="(el, i) in modelValue" :key="i" :element="el" />
    </div>
  `,
};

// BaseTooltip is a Nuxt auto-import; the stub keeps the trigger (and the body,
// which the real component only reveals on hover) reachable from the spec.
const BaseTooltipStub = {
  name: 'BaseTooltip',
  props: ['position', 'width', 'minWidth'],
  template: `
    <div data-testid="tooltip">
      <slot name="trigger" />
      <span data-testid="tooltip-body"><slot /></span>
    </div>
  `,
};

const mountedWrappers = [];

function mountSidebar(props = {}) {
  const wrapper = mount(FolderSidebar, {
    props: {
      folders: [],
      activeId: 'all',
      navigationFacets,
      isDragging: false,
      ...props,
    },
    global: {
      stubs: {
        draggable: DraggableStub,
        NuxtLink: { template: '<a :href="to"><slot /></a>', props: ['to'] },
      },
      components: { BaseTooltip: BaseTooltipStub },
    },
  });
  mountedWrappers.push(wrapper);
  return wrapper;
}

function folderNameButton(wrapper, name) {
  return wrapper.get('[data-testid="manual-folder-section"]')
    .findAll('button')
    .find((button) => button.text().includes(name));
}

describe('FolderSidebar', () => {
  beforeEach(() => {
    mockFolderStore.reorderFolders.mockReset().mockResolvedValue({ success: true });
    mockFolderStore.fetchFolders.mockReset().mockResolvedValue({ success: true });
    mockFolderStore.recursiveDocumentCount.mockReset().mockImplementation(directDocs);
    mockFolderStore.rollupOf.mockReset().mockImplementation((folder, scope = 'active') => ({
      docs: directDocs(folder, scope),
      subs: folder?.children_count || 0,
    }));
  });

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount());
    document.body.innerHTML = '';
  });

  // ── Static entries ────────────────────────────────────────────────────────

  describe('static entries', () => {
    it('renders the catalog inventories in Todos', () => {
      const wrapper = mountSidebar();
      const allEntry = wrapper.get('[data-testid="documents-navigation-all"]');

      expect(allEntry.text()).toContain('Todos');
      expect(allEntry.text()).toContain('8');
      expect(allEntry.text()).toContain('21');
    });

    it('renders the Sin carpeta entry', () => {
      const wrapper = mountSidebar();

      expect(wrapper.text()).toContain('Sin carpeta');
    });

    it('always renders the active unassigned entity, including at zero', () => {
      const wrapper = mountSidebar({
        navigationFacets: {
          totals: {},
          unassigned: { project: {}, client: {} },
          projects: [],
          clients: [],
        },
      });

      expect(wrapper.get('[data-testid="documents-navigation-unassigned"]').text())
        .toContain('Sin proyecto');
    });
  });

  describe('project/client navigation', () => {
    it('uses the shared project/client switch', async () => {
      const wrapper = mountSidebar();

      await wrapper.get('[data-testid="documents-mode-client"]').trigger('click');

      expect(wrapper.emitted('update:navigation-mode')).toEqual([['client']]);
    });

    it('labels each entity inventory count', () => {
      const wrapper = mountSidebar();
      const row = wrapper.get('[data-testid="documents-navigation-project-91"]');

      expect(row.attributes('aria-label')).toBe('Kore Health, 3 carpetas, 9 documentos');
      expect(row.text()).toContain('3');
      expect(row.text()).toContain('9');
    });

    it('switches counts with the archive scope', () => {
      const wrapper = mountSidebar({ archiveScope: 'archived' });

      expect(wrapper.get('[data-testid="documents-navigation-project-91"]')
        .attributes('aria-label')).toBe('Kore Health, 1 carpetas, 2 documentos');
    });

    it('renders the client navigation inventory', () => {
      const wrapper = mountSidebar({ navigationMode: 'client' });

      expect(wrapper.text()).toContain('Kore SAS');
      expect(wrapper.get('[data-testid="documents-navigation-unassigned"]').text())
        .toContain('Sin cliente');
    });

    it('emits the selected entity independently from folder selection', async () => {
      const wrapper = mountSidebar();

      await wrapper.get('[data-testid="documents-navigation-project-91"]').trigger('click');

      expect(wrapper.emitted('select-entity')).toEqual([[91]]);
      expect(wrapper.emitted('select')).toBeUndefined();
    });

    it('keeps a stale selected id reachable as an unavailable row', () => {
      const wrapper = mountSidebar({ navigationSelection: 999 });

      expect(wrapper.get('[data-testid="documents-navigation-project-999"]').text())
        .toContain('No disponible');
    });
  });

  // ── Folder list ───────────────────────────────────────────────────────────

  describe('folder list', () => {
    it('renders all folders from the folders prop', () => {
      const wrapper = mountSidebar({ folders: [folderA, folderB] });

      expect(wrapper.text()).toContain('Propuestas');
      expect(wrapper.text()).toContain('Contratos');
    });

    it('keeps project roots out of the independent manual-folder section', () => {
      const wrapper = mountSidebar({ folders: [projectFolder, folderA] });

      expect(wrapper.get('[data-testid="manual-folder-section"]').text())
        .toContain('Propuestas');
      expect(wrapper.get('[data-testid="manual-folder-section"]').text())
        .not.toContain('Kore Health');
    });

    it('keeps zero-content projects in the active catalog', () => {
      const wrapper = mountSidebar();

      expect(wrapper.text()).toContain('Kore Health');
      expect(wrapper.get('[data-testid="documents-navigation-project-93"]')
        .attributes('aria-label')).toBe('Mimittos, 0 carpetas, 0 documentos');
    });

    it('swaps active for inactive projects when the lifecycle toggle is on', async () => {
      const wrapper = mountSidebar();

      expect(wrapper.find('[data-testid="documents-navigation-archived-group"]').exists())
        .toBe(false);
      expect(wrapper.text()).not.toContain('Candle');
      expect(wrapper.find('[data-testid="documents-navigation-project-91"]').exists())
        .toBe(true);
      expect(wrapper.find('[data-testid="documents-navigation-project-93"]').exists())
        .toBe(true);

      await wrapper.get('[data-testid="inactive-projects-toggle"]').trigger('click');
      expect(wrapper.emitted('toggle-inactive-projects')).toEqual([[true]]);
      await wrapper.setProps({ showInactiveProjects: true });

      const group = wrapper.get('[data-testid="documents-navigation-archived-group"]');
      expect(group.text()).toContain('Proyectos archivados');
      expect(group.text()).toContain('Candle');
      // El toggle es excluyente: los activos dejan de listarse.
      expect(wrapper.find('[data-testid="documents-navigation-project-91"]').exists())
        .toBe(false);
      expect(wrapper.find('[data-testid="documents-navigation-project-93"]').exists())
        .toBe(false);
    });

    it('explains the empty catalog when no project is inactive', async () => {
      const activeOnly = {
        ...navigationFacets,
        projects: navigationFacets.projects.filter(
          (entry) => entry.catalog_bucket === 'active',
        ),
      };
      const wrapper = mountSidebar({
        navigationFacets: activeOnly,
        showInactiveProjects: true,
      });

      expect(wrapper.get('[data-testid="project-empty-fallback"]').text())
        .toBe('No hay proyectos no activos.');
    });

    it('governs archived clients with the same exclusive switch as projects', async () => {
      // El interruptor gobierna los DOS modos. Antes el modo cliente listaba
      // los archivados siempre y ni siquiera ofrecía el control, así que el
      // mismo panel se comportaba distinto según el modo y archivar un cliente
      // no lo sacaba de la vista.
      const wrapper = mountSidebar({ navigationMode: 'client' });
      const control = wrapper.get('[data-testid="inactive-projects-control"]');

      expect(control.text()).toContain('Ver clientes archivados');
      expect(wrapper.find('[data-testid="documents-navigation-archived-group"]').exists())
        .toBe(false);

      await wrapper.setProps({ showInactiveProjects: true });

      expect(wrapper.get('[data-testid="documents-navigation-archived-group"]')
        .text()).toContain('Cliente histórico');
    });

    it('renders the recursive manual section inventory', () => {
      mockFolderStore.rollupOf.mockImplementation((folder) => (
        folder.id === projectFolder.id
          ? { docs: 9, subs: 3 }
          : { docs: 4, subs: 2 }
      ));

      const wrapper = mountSidebar({ folders: [projectFolder, folderA] });

      expect(wrapper.get('[data-testid="manual-folder-section-count"]').text())
        .toBe('3 carp. · 4 docs');
    });

    it('does not expose manual actions for project roots', () => {
      const wrapper = mountSidebar({ folders: [projectFolder] });
      const projectRow = wrapper.get('[data-testid="documents-navigation-project-91"]');

      expect(projectRow.text()).toContain('Kore Health');
      expect(projectRow.find('[data-testid="folder-edit"]').exists()).toBe(false);
      expect(projectRow.find('[data-testid="folder-archive"]').exists()).toBe(false);
      expect(projectRow.find('[data-testid="folder-delete"]').exists()).toBe(false);
    });

    it('hides structural actions for a system-managed folder', () => {
      const wrapper = mountSidebar({
        folders: [{ ...folderA, is_system_managed: true }],
      });

      expect(wrapper.find('[data-testid="folder-edit"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="folder-archive"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="folder-delete"]').exists()).toBe(false);
      expect(wrapper.find('.folder-drag-handle').exists()).toBe(false);
    });

    it('does not expose reconciliation diagnostics in the navigation', () => {
      const wrapper = mountSidebar();

      expect(wrapper.get('[data-testid="documents-navigation-project-91"]').text())
        .toContain('Kore Health');
      expect(wrapper.text()).not.toContain('PA-108');
      expect(wrapper.text()).not.toContain('Revisar proyectos');
      expect(wrapper.text()).not.toContain('Faltan las carpetas gestionadas');
    });
  });

  // ── Los dos contadores de la fila ─────────────────────────────────────────

  describe('row counters', () => {
    it('reports what the branch holds, not what hangs directly off the folder', () => {
      // El bug: «Xpandia Project» decía 0 teniendo 6 documentos en subcarpetas,
      // y ese cero era la única señal de dónde había algo.
      mockFolderStore.recursiveDocumentCount.mockReturnValue(6);
      const wrapper = mountSidebar({ folders: [{ ...emptyFolder, children_count: 3 }] });

      expect(wrapper.find('[data-testid="folder-document-count"]').text()).toBe('6');
      expect(emptyFolder.document_count).toBe(0);
    });

    it('counts the subfolders you will actually see when you enter', () => {
      // Directas a propósito: entrar lista los hijos de la carpeta, así que un
      // total del subárbol prometería filas que ese clic no muestra.
      const wrapper = mountSidebar({ folders: [parentFolder] });

      expect(wrapper.find('[data-testid="folder-subfolder-count"]').text()).toBe('2');
    });

    it('drops the subfolder counter when the folder has none', () => {
      const wrapper = mountSidebar({ folders: [folderA] });

      expect(wrapper.find('[data-testid="folder-subfolder-count"]').exists()).toBe(false);
      expect(wrapper.find('[data-testid="folder-document-count"]').text()).toBe('5');
    });

    it('asks for the branch of the mode being viewed', () => {
      mountSidebar({ folders: [scopedFolder], archiveScope: 'archived' });

      expect(mockFolderStore.recursiveDocumentCount)
        .toHaveBeenCalledWith(scopedFolder, 'archived');
    });

    it('names both counters for a screen reader instead of two bare numbers', () => {
      const wrapper = mountSidebar({ folders: [parentFolder] });

      expect(folderNameButton(wrapper, 'Clientes').attributes('aria-label'))
        .toBe('Clientes — 2 subcarpetas, 0 documentos');
    });

    it('keeps the delete guard on the direct inventory the server rejects with', () => {
      // Aunque la rama guarde 12 documentos, el 409 habla de la subcarpeta que
      // cuelga directo: el tooltip tiene que citar ESO, no el total.
      mockFolderStore.recursiveDocumentCount.mockReturnValue(12);
      const wrapper = mountSidebar({ folders: [parentFolder] });

      const deleteButton = wrapper.get('[data-testid="folder-delete"]');
      const deleteTooltipProxy = deleteButton.element.closest('[data-disabled-action-proxy]');

      expect(deleteButton.element.disabled).toBe(true);
      expect(deleteTooltipProxy).not.toBeNull();
      expect(deleteTooltipProxy.getAttribute('aria-label')).toContain('contiene 2 subcarpetas');
      expect(deleteTooltipProxy.getAttribute('aria-label')).not.toContain('contiene 12 documentos');
    });
  });

  // ── Select emits ──────────────────────────────────────────────────────────

  describe('select emits', () => {
    it('uses the catalog Todos row instead of duplicating it in manual folders', async () => {
      const wrapper = mountSidebar();

      await wrapper.get('[data-testid="documents-navigation-all"]').trigger('click');

      expect(wrapper.emitted('select-entity')).toEqual([['all']]);
      expect(wrapper.get('[data-testid="manual-folder-section"]').text())
        .not.toContain('Todos los documentos');
    });

    it('emits select with none when the Sin carpeta button is clicked', async () => {
      const wrapper = mountSidebar();
      const sinCarpetaBtn = wrapper.findAll('button').find(b => b.text().includes('Sin carpeta'));
      await sinCarpetaBtn.trigger('click');

      expect(wrapper.emitted('select')).toEqual([['none']]);
    });

    it('emits select with the folder id when a folder button is clicked', async () => {
      const wrapper = mountSidebar({ folders: [folderA] });
      const folderBtn = wrapper.findAll('button').find(b => b.text().includes('Propuestas'));
      await folderBtn.trigger('click');

      expect(wrapper.emitted('select')).toEqual([[folderA.id]]);
    });
  });

  // ── Manage emits ──────────────────────────────────────────────────────────

  describe('manage emits', () => {
    it('emits manage when the Gestionar link is clicked', async () => {
      const wrapper = mountSidebar();
      const gestionarBtn = wrapper.findAll('button').find(b => b.text() === 'Gestionar');
      await gestionarBtn.trigger('click');

      expect(wrapper.emitted('manage')).toBeTruthy();
    });

    it('emits manage when the Nueva carpeta button is clicked', async () => {
      const wrapper = mountSidebar();
      const nuevaBtn = wrapper.findAll('button').find(b => b.text().includes('Nueva carpeta'));
      await nuevaBtn.trigger('click');

      expect(wrapper.emitted('manage')).toBeTruthy();
    });
  });

  // ── Active styling ────────────────────────────────────────────────────────

  describe('active styling', () => {
    it('applies active class to the catalog Todos entry', () => {
      const wrapper = mountSidebar({ navigationSelection: 'all' });
      const todosBtn = wrapper.get('[data-testid="documents-navigation-all"]');

      expect(todosBtn.classes()).toContain('bg-primary-soft');
    });

    it('applies active class to a folder entry matching activeId', () => {
      const wrapper = mountSidebar({ folders: [folderA], activeId: folderA.id });
      const folderDiv = wrapper.find(`[data-testid="folder-draggable"]`);

      expect(folderDiv.text()).toContain('Propuestas');
      // The inner button wrapper should have the active class
      const folderBtn = wrapper.findAll('button').find(b => b.text().includes('Propuestas'));
      expect(folderBtn.classes()).not.toContain('bg-emerald-50'); // button itself, parent div has class
    });
  });

  // ── Row alignment ─────────────────────────────────────────────────────────

  describe('row alignment', () => {
    it('starts folder names on the same horizontal axis as Sin carpeta', () => {
      const wrapper = mountSidebar({ folders: [folderA] });
      const unfiledBtn = folderNameButton(wrapper, 'Sin carpeta');
      const folderBtn = folderNameButton(wrapper, 'Propuestas');

      expect(unfiledBtn.classes()).toContain('px-3');
      expect(folderBtn.classes()).toContain('px-3');
    });

    it('truncates a long folder name instead of wrapping or pushing the counter', () => {
      const longName = 'Documentación comercial de clientes corporativos 2026';
      const wrapper = mountSidebar({
        folders: [{ id: 9, name: longName, document_count: 3, children_count: 0 }],
      });
      // El nombre vive dentro de la columna que comparte con el cliente, así
      // que se busca por su `title` —que sólo lleva él— y no por ser el primer
      // span de la fila.
      const nameSpan = folderNameButton(wrapper, longName)
        .find(`span[title="${longName}"]`);

      expect(nameSpan.classes()).toContain('truncate');
    });
  });

  // ── Row actions ───────────────────────────────────────────────────────────

  describe('delete affordance', () => {
    it('emits delete with the folder when an empty folder’s delete icon is clicked', async () => {
      const wrapper = mountSidebar({ folders: [emptyFolder] });

      await wrapper.find('[data-testid="folder-delete"]').trigger('click');

      expect(wrapper.emitted('delete')).toEqual([[emptyFolder]]);
    });

    it('disables delete for a folder that still holds documents', async () => {
      const wrapper = mountSidebar({ folders: [folderA] });

      const button = wrapper.find('[data-testid="folder-delete"]');
      expect(button.element.disabled).toBe(true);
      await button.trigger('click');
      expect(wrapper.emitted('delete')).toBeUndefined();
    });

    it('disables delete for a folder that only holds subfolders', () => {
      const wrapper = mountSidebar({ folders: [parentFolder] });

      expect(wrapper.find('[data-testid="folder-delete"]').element.disabled).toBe(true);
    });

    it('disables delete when the only content left is archived', () => {
      // El 409 del backend cuenta lo archivado, así que el ícono también.
      const wrapper = mountSidebar({ folders: [mixedFolder] });

      expect(wrapper.find('[data-testid="folder-delete"]').element.disabled).toBe(true);
    });

    it('explains in one horizontal tooltip why a filled folder cannot be deleted', async () => {
      const wrapper = mountSidebar({ folders: [folderA] });
      const button = wrapper.get('[data-testid="folder-delete"]');

      expect(button.attributes('title')).toBeUndefined();
      await wrapper.get('[data-disabled-action-proxy]').trigger('click');
      const tooltips = document.body.querySelectorAll('[role="tooltip"]');
      expect(tooltips).toHaveLength(1);
      expect(tooltips[0].textContent).toContain('No se puede eliminar');
      expect(tooltips[0].textContent).toContain('Archívala en su lugar');
      expect(tooltips[0].className).toContain('whitespace-nowrap');
    });

    it('names the action in the tooltip when the folder can be deleted', async () => {
      const wrapper = mountSidebar({ folders: [emptyFolder] });

      await wrapper.get('[data-testid="folder-delete"]').trigger('focusin');
      expect(document.body.querySelector('[role="tooltip"]').textContent)
        .toContain('Eliminar carpeta');
    });
  });

  describe('archive affordance', () => {
    it('emits archive with the folder when the archive icon is clicked', async () => {
      const wrapper = mountSidebar({ folders: [folderA] });

      await wrapper.find('[data-testid="folder-archive"]').trigger('click');

      expect(wrapper.emitted('archive')).toEqual([[folderA]]);
    });

    it('stays enabled for a filled folder — it is the way out', async () => {
      const wrapper = mountSidebar({ folders: [folderA] });

      expect(wrapper.find('[data-testid="folder-archive"]').element.disabled).toBe(false);
      await wrapper.get('[data-testid="folder-archive"]').trigger('focusin');
      expect(document.body.querySelector('[role="tooltip"]').textContent)
        .toContain('Archivar carpeta');
    });
  });

  describe('archived content indicator', () => {
    it('shows the badge on a folder that still holds archived items', () => {
      const wrapper = mountSidebar({ folders: [mixedFolder] });

      expect(wrapper.find('[data-testid="folder-archived-badge"]').text()).toContain('2');
    });

    it('hides the badge when nothing is archived inside', () => {
      const wrapper = mountSidebar({ folders: [folderA] });

      expect(wrapper.find('[data-testid="folder-archived-badge"]').exists()).toBe(false);
    });

    it('emits view-archived so the row can be opened in its archived scope', async () => {
      const wrapper = mountSidebar({ folders: [mixedFolder] });

      await wrapper.find('[data-testid="folder-archived-badge"]').trigger('click');

      expect(wrapper.emitted('view-archived')).toEqual([[mixedFolder]]);
    });
  });

  // ── Interruptor de modo archivado ─────────────────────────────────────────
  // «Archivados» dejó de ser una pseudo-entrada de la lista de carpetas: como
  // fila se leía igual que un destino, y el usuario no tenía cómo saber que el
  // archivo es el ÁMBITO en que se ve todo el panel.

  describe('archived mode switch', () => {
    const switchOf = (w) => w.find('[data-testid="folder-archived-entry"]');

    it('reflects the mode it is in', () => {
      expect(switchOf(mountSidebar()).attributes('aria-checked')).toBe('false');
      expect(
        switchOf(mountSidebar({ archiveScope: 'archived' })).attributes('aria-checked'),
      ).toBe('true');
    });

    it('emits the flip in both directions', async () => {
      const off = mountSidebar();
      await switchOf(off).trigger('click');
      expect(off.emitted('toggle-archived')).toEqual([[true]]);

      const on = mountSidebar({ archiveScope: 'archived' });
      await switchOf(on).trigger('click');
      expect(on.emitted('toggle-archived')).toEqual([[false]]);
    });

    it('shows the archived total beside the switch', () => {
      const wrapper = mountSidebar({ archivedCount: 23 });

      expect(wrapper.find('[data-testid="folder-archived-count"]').text()).toBe('23');
    });

    it('places the content archive switch immediately before own folders', () => {
      const wrapper = mountSidebar();
      const archiveControl = wrapper.get('[data-testid="document-archive-control"]');
      const manualSection = wrapper.get('[data-testid="manual-folder-section"]');

      // El switch es de OTRO eje que el acordeón de entidades, así que queda
      // fuera de él y pegado a «Carpetas propias»: son dos <li> hermanos.
      expect(archiveControl.element.nextElementSibling).toBe(manualSection.element);
    });

    it('offers both sections open, with an accessible collapse trigger each', () => {
      const wrapper = mountSidebar();
      const entities = wrapper.get('[data-testid="entities-section-toggle"]');
      const manual = wrapper.get('[data-testid="manual-folder-section-toggle"]');

      // Abiertas al entrar: recoger es una decisión del usuario, no el default.
      expect(entities.attributes('aria-expanded')).toBe('true');
      expect(manual.attributes('aria-expanded')).toBe('true');
      // El trigger tiene que apuntar al cuerpo que abre, o el lector de
      // pantalla no sabe qué se desplegó.
      expect(wrapper.find(`#${entities.attributes('aria-controls')}`).exists()).toBe(true);
      expect(wrapper.find(`#${manual.attributes('aria-controls')}`).exists()).toBe(true);
      expect(entities.text()).toContain('Proyectos');
    });

    it('collapses the entity catalog without losing it from the DOM', async () => {
      const wrapper = mountSidebar();
      const entities = wrapper.get('[data-testid="entities-section-toggle"]');

      await entities.trigger('click');

      expect(entities.attributes('aria-expanded')).toBe('false');
      const body = wrapper.get(`#${entities.attributes('aria-controls')}`);
      // BaseCollapse lo deja inerte y oculto a la asistencia, no lo desmonta:
      // así la animación de altura tiene de dónde partir.
      expect(body.attributes('aria-hidden')).toBe('true');
      expect(body.attributes('inert')).toBeDefined();

      // El estado es de módulo (lo comparten el panel fijo y el del drawer), así
      // que dejarlo plegado se filtraría al resto del archivo.
      await entities.trigger('click');
      expect(entities.attributes('aria-expanded')).toBe('true');
    });

    it('names the client catalog when the sidebar navigates by client', () => {
      const wrapper = mountSidebar({ navigationMode: 'client' });

      expect(wrapper.get('[data-testid="entities-section-toggle"]').text())
        .toContain('Clientes');
    });

    it('goes inert while a search is running', async () => {
      // La búsqueda recorre los dos estados: un mando que no filtra, no se ofrece.
      const wrapper = mountSidebar({ scopeLocked: true });

      await switchOf(wrapper).trigger('click');

      expect(switchOf(wrapper).attributes('aria-checked')).toBe('false');
      expect(wrapper.emitted('toggle-archived')).toBeUndefined();
    });

    it('lights the folder you are standing in, archive included', () => {
      // Lo contrario de la regla de resaltado único que regía antes: con el modo
      // declarado por el interruptor, apagar la fila activa dejaba al panel sin
      // decir dónde estaba parado el usuario.
      const wrapper = mountSidebar({
        folders: [folderA], archiveScope: 'archived', activeId: folderA.id,
      });

      const row = wrapper.find('[data-testid="folder-archive"]').element
        .closest('.transition-all');
      expect(row.className).toContain('text-text-brand');
    });

    it('counts what the mode shows, not what the folder holds when active', () => {
      // El contador de la fila decía activos mientras el listado mostraba
      // archivados: los números no cuadraban y parecía que faltaban documentos.
      const active = mountSidebar({ folders: [scopedFolder] });
      const archived = mountSidebar({ folders: [scopedFolder], archiveScope: 'archived' });

      expect(folderNameButton(active, 'Mixta').text()).toContain('7');
      expect(folderNameButton(active, 'Mixta').text()).not.toContain('3');
      expect(folderNameButton(archived, 'Mixta').text()).toContain('3');
      expect(folderNameButton(archived, 'Mixta').text()).not.toContain('7');
    });
  });

  // ── Folder drag reorder ───────────────────────────────────────────────────

  describe('folder reorder', () => {
    it('calls reorderFolders when draggable emits end with a changed order', async () => {
      const wrapper = mountSidebar({ folders: [folderA, folderB] });

      const dragList = wrapper.findComponent({ name: 'draggable' });
      // Sortable publishes its reordered list through the v-model boundary.
      await dragList.vm.$emit('update:modelValue', [folderB, folderA]);
      await dragList.vm.$emit('end');
      await flushPromises();

      expect(mockFolderStore.reorderFolders).toHaveBeenCalledWith([folderB.id, folderA.id]);
    });

    it('does not call reorderFolders when the order is unchanged after drag-end', async () => {
      const wrapper = mountSidebar({ folders: [folderA, folderB] });

      await wrapper.findComponent({ name: 'draggable' }).vm.$emit('end');
      await flushPromises();

      expect(mockFolderStore.reorderFolders).not.toHaveBeenCalled();
    });
  });

  // ── Document drop ─────────────────────────────────────────────────────────

  describe('document drop on folder', () => {
    it('emits folder-drop with null when a document is dropped on Sin carpeta', async () => {
      const wrapper = mountSidebar({ isDragging: true });
      const sinCarpetaBtn = wrapper.findAll('button').find(b => b.text().includes('Sin carpeta'));
      await sinCarpetaBtn.trigger('drop');

      expect(wrapper.emitted('folder-drop')).toEqual([[null]]);
    });
  });

  // ── Row actions: editar ───────────────────────────────────────────────────

  describe('edit action', () => {
    const folders = [
      { id: 1, name: 'Kore', client: 7, client_display_name: 'Kore SAS' },
      { id: 2, name: 'Con proyecto', project: 91 },
      { id: 3, name: 'Sin dueño' },
    ];

    it('offers editing right where archiving and deleting already are', async () => {
      const wrapper = mountSidebar({ folders });

      const edit = wrapper.find('[data-testid="folder-edit"]');
      expect(edit.exists()).toBe(true);

      await edit.trigger('click');
      expect(wrapper.emitted('edit')[0][0].id).toBe(3);
    });

    it('keeps client and project folders out of the unassigned section', () => {
      const wrapper = mountSidebar({ folders });
      const section = wrapper.get('[data-testid="manual-folder-section"]');

      expect(section.text()).toContain('Carpetas propias');
      expect(section.text()).toContain('Sin dueño');
      expect(section.text()).not.toContain('Kore');
      expect(section.text()).not.toContain('Con proyecto');
    });

    it('says nothing about the client when the folder has none', () => {
      const wrapper = mountSidebar({ folders });

      expect(wrapper.find('[data-testid="folder-client-3"]').exists()).toBe(false);
    });
  });
});
