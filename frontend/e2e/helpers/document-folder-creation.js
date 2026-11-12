import { mockApi } from './api.js';

export const folderProject = {
  id: 40, name: 'Proyecto documental de prueba', client: 7,
  client_display_name: 'Cliente de prueba', managed_root_id: 200,
  state: { name: 'Activo', system_key: 'active' },
  is_visible: true, catalog_bucket: 'active',
  counts: { active: { folders: 3, documents: 0 }, archived: { folders: 0, documents: 0 } },
};

export const folderFixture = (overrides = {}) => ({
  id: 200, name: folderProject.name, parent: null, order: 0,
  project: folderProject.id, project_name: folderProject.name, client: 7,
  client_display_name: folderProject.client_display_name,
  folder_kind: 'manual', is_archived: false, is_system_managed: false,
  document_count: 0, children_count: 0, ...overrides,
});

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });

export async function setupFolderCreation(page, { root = true, failCreate = false } = {}) {
  const project = { ...folderProject, managed_root_id: root ? 200 : null };
  const state = {
    created: null,
    folders: root ? [
      folderFixture({ folder_kind: 'project' }),
      folderFixture({ id: 201, name: 'Entregables', parent: 200 }),
      folderFixture({ id: 202, name: 'Diseño aprobado', parent: 201 }),
      folderFixture({ id: 203, name: 'Diseño aprobado', parent: 200 }),
    ] : [],
  };
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'accounts/panel-preferences/documents/') return json({ navigation_mode: 'project' });
    if (apiPath === 'documents/navigation/') return json({
      projects: [project], clients: [],
      totals: project.counts,
      unassigned: { project: { active: { folders: 0, documents: 0 } }, client: { active: { folders: 0, documents: 0 } } },
    });
    if (apiPath === 'accounting/projects/') return json({ results: [{ ...project, client_profile_id: 7 }] });
    if (apiPath === 'document-folders/') return json(state.folders);
    if (apiPath === 'documents/counts/') return json({
      documents: { active: 0, archived: 0, unfiled_active: 0, unfiled_archived: 0 },
      folders: { active: state.folders.length, archived: 0 },
    });
    if (apiPath === 'document-folders/create/' && method === 'POST') {
      state.created = route.request().postDataJSON();
      if (failCreate) return json({ name: ['Ya existe una carpeta con ese nombre.'] }, 400);
      const created = folderFixture({ id: 800, ...state.created });
      state.folders.push(created);
      return json(created, 201);
    }
    if (apiPath === 'documents/' || apiPath === 'document-tags/' || apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    return null;
  });
  return state;
}
