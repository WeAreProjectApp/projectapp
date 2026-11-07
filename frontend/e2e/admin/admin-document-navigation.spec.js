/**
 * Project/client navigation in the document manager.
 *
 * @flow:admin-document-navigation
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_NAVIGATION } from '../helpers/flow-tags.js';
import { VIEWPORTS } from '../helpers/viewports.js';

test.setTimeout(60_000);

const jsonResponse = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const PROJECT_ROOT = {
  id: 21,
  name: 'Proyecto Atlas',
  slug: 'proyecto-atlas',
  parent: null,
  order: 0,
  project: 41,
  client: 7,
  managed_project: 41,
  folder_kind: 'project',
  is_project_visible: true,
  is_system_managed: true,
  managed_project_state: { name: 'Activo', system_key: 'active' },
  is_archived: false,
  document_count: 0,
  children_count: 0,
  active_document_count: 0,
  active_children_count: 0,
  archived_document_count: 0,
  archived_children_count: 0,
};

const PROJECT_PHASE = {
  id: 23,
  name: 'Fase 1.5',
  slug: 'fase-1-5',
  parent: PROJECT_ROOT.id,
  order: 0,
  project: 41,
  client: 7,
  managed_project: null,
  folder_kind: 'manual',
  is_project_visible: true,
  is_system_managed: false,
  is_archived: false,
  document_count: 1,
  children_count: 0,
  active_document_count: 1,
  active_children_count: 0,
  archived_document_count: 0,
  archived_children_count: 0,
};

const OWN_FOLDER = {
  id: 31,
  name: 'Archivo interno',
  slug: 'archivo-interno',
  parent: null,
  order: 1,
  project: null,
  client: null,
  managed_project: null,
  folder_kind: 'manual',
  is_project_visible: false,
  is_system_managed: false,
  is_archived: false,
  document_count: 1,
  children_count: 0,
  active_document_count: 1,
  active_children_count: 0,
  archived_document_count: 0,
  archived_children_count: 0,
};

const entityDocument = {
  id: 501,
  title: 'Alcance Atlas',
  status: 'published',
  is_archived: false,
  folder: null,
  folder_name: null,
  client: 7,
  client_display_name: 'Cliente Atlas SAS',
  client_name: 'Cliente Atlas SAS',
  project: 41,
  project_name: 'Proyecto Atlas',
  tag_details: [],
  active_states: [],
  created_at: '2026-08-20T10:00:00Z',
};

const unassignedDocument = {
  ...entityDocument,
  id: 502,
  title: 'Plantilla sin proyecto',
  client: null,
  client_display_name: null,
  client_name: null,
  project: null,
  project_name: null,
};

const ownFolderDocument = {
  ...unassignedDocument,
  id: 503,
  title: 'Manual interno',
  folder: OWN_FOLDER.id,
  folder_name: OWN_FOLDER.name,
};

const projectPhaseDocument = {
  ...entityDocument,
  id: 504,
  title: 'Documento de Fase 1.5',
  status: 'draft',
  content_markdown: '# Fase 1.5',
  folder: PROJECT_PHASE.id,
  folder_name: PROJECT_PHASE.name,
};

const navigationPayload = {
  totals: {
    active: { folders: 7, documents: 3 },
    archived: { folders: 2, documents: 1 },
  },
  unassigned: {
    project: {
      active: { folders: 1, documents: 2 },
      archived: { folders: 0, documents: 0 },
    },
    client: {
      active: { folders: 1, documents: 2 },
      archived: { folders: 0, documents: 0 },
    },
  },
  projects: [
    {
      id: 41,
      name: 'Proyecto Atlas',
      client: 7,
      client_display_name: 'Cliente Atlas SAS',
      managed_root_id: PROJECT_ROOT.id,
      state: { name: 'Activo', system_key: 'active', show_in_document_manager: true },
      is_visible: true,
      catalog_bucket: 'active',
      counts: {
        active: { folders: 6, documents: 1 },
        archived: { folders: 2, documents: 1 },
      },
    },
    {
      id: 42,
      name: 'Proyecto suspendido',
      client: 8,
      client_display_name: 'Cliente Pausa',
      managed_root_id: 22,
      state: { name: 'Suspendido', system_key: 'suspended', show_in_document_manager: false },
      is_visible: true,
      catalog_bucket: 'archived',
      counts: {
        active: { folders: 1, documents: 1 },
        archived: { folders: 0, documents: 0 },
      },
    },
    {
      id: 43,
      name: 'Proyecto sin documentos',
      client: 9,
      client_display_name: 'Cliente Nuevo',
      managed_root_id: null,
      state: { name: 'En desarrollo', system_key: 'development' },
      is_visible: true,
      catalog_bucket: 'active',
      counts: {
        active: { folders: 0, documents: 0 },
        archived: { folders: 0, documents: 0 },
      },
    },
  ],
  clients: [
    {
      id: 7,
      name: 'Cliente Atlas SAS',
      is_archived: false,
      catalog_bucket: 'active',
      counts: {
        active: { folders: 6, documents: 1 },
        archived: { folders: 2, documents: 1 },
      },
    },
    {
      id: 8,
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

function documentRowsFor(query) {
  if (query.get('folder') === String(PROJECT_PHASE.id)) {
    return [projectPhaseDocument];
  }
  if (query.get('folder') === String(OWN_FOLDER.id)) {
    return [ownFolderDocument];
  }
  if (query.get('project') === '41' || query.get('client') === '7') {
    return [entityDocument];
  }
  if (query.get('project') === 'none' || query.get('client') === 'none') {
    return [unassignedDocument, ownFolderDocument];
  }
  return [entityDocument, unassignedDocument, ownFolderDocument];
}

async function setupNavigationApi(page, {
  navigationFailures = 0,
  folders = [PROJECT_ROOT, PROJECT_PHASE, OWN_FOLDER],
  navigation = navigationPayload,
} = {}) {
  let preferenceMode = 'project';
  let navigationAttempts = 0;
  const documentRequests = [];

  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') {
      return jsonResponse({ user: { username: 'admin', is_staff: true } });
    }
    if (apiPath === 'accounts/panel-preferences/documents/') {
      if (method === 'PATCH') {
        const payload = route.request().postDataJSON();
        preferenceMode = payload.navigation_mode;
      }
      return jsonResponse({ navigation_mode: preferenceMode });
    }
    if (apiPath === 'documents/navigation/') {
      navigationAttempts += 1;
      if (navigationAttempts <= navigationFailures) {
        return jsonResponse({ detail: 'No pudimos cargar la navegación.' }, 503);
      }
      return jsonResponse(navigation);
    }
    if (apiPath === 'documents/504/detail/') return jsonResponse(projectPhaseDocument);
    if (apiPath === 'document-folders/') {
      return jsonResponse(folders);
    }
    if (apiPath === 'documents/counts/') {
      return jsonResponse({
        documents: {
          active: 3,
          archived: 1,
          unfiled_active: 2,
          unfiled_archived: 0,
        },
        folders: { active: 7, archived: 2 },
      });
    }
    if (apiPath === 'documents/browse/') {
      const requestUrl = route.request().url();
      documentRequests.push(requestUrl);
      const query = new URL(requestUrl).searchParams;
      const rows = documentRowsFor(query);
      const pageSize = Number(query.get('page_size')) || 10;
      const requestedPage = Number(query.get('page')) || 1;
      const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
      const currentPage = Math.min(requestedPage, totalPages);
      const start = (currentPage - 1) * pageSize;
      return jsonResponse({
        results: rows.slice(start, start + pageSize),
        count: rows.length,
        page: currentPage,
        page_size: pageSize,
        total_pages: totalPages,
      });
    }
    if (apiPath === 'documents/') {
      const requestUrl = route.request().url();
      documentRequests.push(requestUrl);
      const query = new URL(requestUrl).searchParams;
      return jsonResponse(documentRowsFor(query));
    }
    if (apiPath === 'document-states/' || apiPath === 'document-state-groups/') {
      return jsonResponse([]);
    }
    if (apiPath === 'document-tags/') return jsonResponse([]);
    if (apiPath.startsWith('accounting/projects/')) return jsonResponse({ results: [] });
    return null;
  });

  return {
    preferenceMode: () => preferenceMode,
    navigationAttempts: () => navigationAttempts,
    documentRequests,
  };
}

async function openDocuments(page) {
  await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Gestor Documental', exact: true }))
    .toBeVisible({ timeout: 35_000 });
}

async function openDocumentsFromPanel(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  const documentsLink = page.getByRole('link', { name: 'Gestor Documental', exact: true });
  await expect(documentsLink).toBeVisible({ timeout: 35_000 });
  await documentsLink.click();
  await expect(page.getByRole('heading', { name: 'Gestor Documental', exact: true }))
    .toBeVisible({ timeout: 35_000 });
}

function expectListContext(page, expected) {
  return expect.poll(() => {
    const url = new URL(page.url());
    return Object.fromEntries([...url.searchParams.entries()].filter(([key]) => key in expected));
  }).toEqual(expected);
}

test.beforeEach(async ({ page }) => {
  await setAuthLocalStorage(page, {
    token: 'document-navigation-token',
    userAuth: { id: 8701, role: 'admin', is_staff: true },
  });
});

test.describe('Admin document project/client navigation', () => {
  // La primera visita compila una página grande de Nuxt. Este flujo necesita
  // estado secuencial además (persistencia y reintento), y tres compilaciones
  // frías en paralelo vuelven flake la navegación antes de montar la página.
  test.describe.configure({ mode: 'serial' });

  test('renders project navigation with recursive inventory', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupNavigationApi(page);
    await openDocumentsFromPanel(page);

    await expect(page.getByTestId('documents-mode-project'))
      .toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('documents-navigation-project-41'))
      .toHaveAttribute('aria-label', 'Proyecto Atlas, 6 carpetas, 1 documentos');
    await expect(page.getByTestId('documents-navigation-project-43'))
      .toHaveAttribute('aria-label', 'Proyecto sin documentos, 0 carpetas, 0 documentos');
    await expect(page.getByTestId('documents-navigation-unassigned'))
      .toContainText('Sin proyecto');
    await expect(page.getByTestId('manual-folder-section'))
      .toContainText('Archivo interno');
  });

  test('swaps active for suspended projects through the lifecycle toggle', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupNavigationApi(page);
    await openDocumentsFromPanel(page);

    await expect(page.getByTestId('inactive-projects-toggle'))
      .toHaveAttribute('aria-checked', 'false');
    await expect(page.getByTestId('documents-navigation-project-42')).toHaveCount(0);
    await expect(page.getByTestId('documents-navigation-project-41')).toBeVisible();

    await page.getByTestId('inactive-projects-toggle').click();

    await expect(page.getByTestId('documents-navigation-archived-group'))
      .toContainText('Proyectos archivados');
    await expect(page.getByTestId('documents-navigation-project-42'))
      .toContainText('Proyecto suspendido');
    // Excluyente: los activos se van mientras el toggle esté encendido.
    await expect(page.getByTestId('documents-navigation-project-41')).toHaveCount(0);
    await expect(page.getByTestId('documents-navigation-project-43')).toHaveCount(0);
  });

  test('returns to Todos when non-active projects are hidden', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupNavigationApi(page);
    await openDocuments(page);

    await page.getByTestId('inactive-projects-toggle').click();
    await page.getByTestId('documents-navigation-project-42').click();
    await expect(page).toHaveURL(/project=42/);

    await page.getByTestId('inactive-projects-toggle').click();

    await expect(page).not.toHaveURL(/project=/);
    await expect(page.getByTestId('documents-navigation-all'))
      .toHaveAttribute('aria-current', 'page');
    await expect(page.getByTestId('documents-navigation-project-42')).toHaveCount(0);
  });

  test('returns to Todos when the active project is hidden by the toggle', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupNavigationApi(page);
    await openDocuments(page);

    await page.getByTestId('documents-navigation-project-41').click();
    await expect(page).toHaveURL(/project=41/);

    await page.getByTestId('inactive-projects-toggle').click();

    await expect(page).not.toHaveURL(/project=/);
    await expect(page.getByTestId('documents-navigation-all'))
      .toHaveAttribute('aria-current', 'page');
    await expect(page.getByTestId('documents-navigation-project-41')).toHaveCount(0);
  });

  test('manual folder selection clears a previously selected project', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const api = await setupNavigationApi(page);
    await openDocuments(page);

    await page.getByTestId('documents-navigation-project-41').click();
    await expect(page).toHaveURL(/project=41/);
    await page.getByRole('button', { name: /^Archivo interno —/ }).click();

    await expect(page).toHaveURL(/folder=31/);
    await expect(page).not.toHaveURL(/project=/);
    await expect(page).not.toHaveURL(/client=/);
    await expect.poll(() => api.documentRequests.at(-1)).toContain('folder=31');
    expect(api.documentRequests.at(-1)).not.toContain('project=');
    expect(api.documentRequests.at(-1)).not.toContain('client=');
  });

  test('restores project-owned folder context after document editing', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupNavigationApi(page);
    await openDocuments(page);

    await page.getByTestId('documents-navigation-project-41').click();
    const phaseLink = page.getByTestId(`folder-open-${PROJECT_PHASE.id}`);
    await expect(phaseLink).toHaveAttribute('href', /project=41/);
    await phaseLink.click();

    await expectListContext(page, { folder: String(PROJECT_PHASE.id), project: '41' });
    await expect(page.getByTestId('documents-navigation-project-41'))
      .toHaveAttribute('aria-current', 'page');
    await expect(page.getByTestId('documents-navigation-all'))
      .not.toHaveAttribute('aria-current', 'page');

    await page.getByTestId(`document-open-${projectPhaseDocument.id}`).click();
    await page.getByRole('link', { name: 'Volver a «Fase 1.5»' }).first().click();
    await page.getByTestId('confirm-modal-secondary').click();

    await expectListContext(page, {
      folder: String(PROJECT_PHASE.id),
      project: '41',
      focus: String(projectPhaseDocument.id),
    });
    await expect(page.getByTestId('documents-navigation-project-41'))
      .toHaveAttribute('aria-current', 'page');
    await expect(page.getByTestId(`document-open-${projectPhaseDocument.id}`))
      .toBeFocused();
  });

  test('contains an unbroken project name inside the folder header', {
    // Bug caught: a 200-character project name expanded the document page beyond a phone or tablet viewport.
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success', '@responsive:documents'],
  }, async ({ page }) => {
    const longProjectName = 'Proyecto'.repeat(25);
    const longFolder = { ...PROJECT_PHASE, project_name: longProjectName };
    const longNavigation = {
      ...navigationPayload,
      projects: navigationPayload.projects.map((project) => (
        project.id === 41 ? { ...project, name: longProjectName } : project
      )),
    };
    await setupNavigationApi(page, { folders: [PROJECT_ROOT, longFolder, OWN_FOLDER], navigation: longNavigation });
    await openDocumentsFromPanel(page);

    await page.getByTestId('documents-navigation-project-41').click();
    await page.getByTestId(`folder-open-${PROJECT_PHASE.id}`).click();
    await expect(page.getByTestId('folder-header-project')).toHaveText(longProjectName);
    await expect(page.getByTestId(`document-open-${projectPhaseDocument.id}`)).toContainText('Documento de Fase 1.5');

    await page.reload({ waitUntil: 'domcontentloaded' });
    for (const profile of ['compact', 'portrait']) {
      await page.setViewportSize(VIEWPORTS[profile]);
      const canvas = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
      }));
      expect(canvas.scrollWidth, `${profile} must keep the document canvas contained`).toBeLessThanOrEqual(canvas.clientWidth + 1);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('folder-header-project')).toHaveText(longProjectName);
      const loadedCanvas = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
      }));
      expect(loadedCanvas.scrollWidth).toBeLessThanOrEqual(loadedCanvas.clientWidth + 1);
      await expect(page.getByTestId(`document-open-${projectPhaseDocument.id}`)).toBeVisible();
      await page.getByTestId('folder-drawer-trigger').click();
      const drawer = page.getByTestId('folder-drawer');
      await expect(drawer).toContainText('Fase 1.5');
      await drawer.getByRole('button', { name: 'Cerrar', exact: true }).click();
    }
    await expect(page.getByTestId('folder-header-name')).toHaveText('Fase 1.5');
    longFolder.project_name = PROJECT_PHASE.project_name;
    longNavigation.projects.find((project) => project.id === 41).name = PROJECT_PHASE.project_name;
    await page.setViewportSize(VIEWPORTS.compact);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('folder-header-project')).toHaveText(PROJECT_PHASE.project_name);
    const normalCanvas = await page.evaluate(() => ({
      width: document.documentElement.clientWidth,
      scroll: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
    }));
    expect(normalCanvas.scroll).toBeLessThanOrEqual(normalCanvas.width + 1);
  });

  test('requests server pages for project-owned folder navigation', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const api = await setupNavigationApi(page);
    await openDocuments(page);
    const initialRequestCount = api.documentRequests.length;

    await page.getByTestId('documents-navigation-project-41').click();
    await expect(page.getByTestId(`document-row-${entityDocument.id}`)).toBeVisible();
    await page.getByTestId(`folder-open-${PROJECT_PHASE.id}`).click();
    await expect(page.getByTestId(`document-row-${projectPhaseDocument.id}`)).toBeVisible();

    await expect.poll(() => api.documentRequests.length - initialRequestCount).toBe(2);
    const requests = api.documentRequests.slice(initialRequestCount).map((requestUrl) => {
      const request = new URL(requestUrl);
      return {
        pathname: request.pathname,
        folder: request.searchParams.get('folder'),
        project: request.searchParams.get('project'),
        page: request.searchParams.get('page'),
        pageSize: request.searchParams.get('page_size'),
      };
    });
    expect(requests).toEqual([
      {
        pathname: '/api/documents/browse/',
        folder: 'root',
        project: '41',
        page: '1',
        pageSize: '10',
      },
      {
        pathname: '/api/documents/browse/',
        folder: String(PROJECT_PHASE.id),
        project: '41',
        page: '1',
        pageSize: '10',
      },
    ]);
  });

  test('filters documents by selected client', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const api = await setupNavigationApi(page);
    await openDocuments(page);

    await page.getByTestId('documents-mode-client').click();
    await page.getByTestId('documents-navigation-client-7').click();

    await expect(page).toHaveURL(/by=client/);
    await expect(page).toHaveURL(/client=7/);
    await expect(page.getByTestId('document-row-501')).toBeVisible();
    await expect(page.getByTestId('document-row-502')).toHaveCount(0);
    await expect.poll(() => api.documentRequests.at(-1))
      .toContain('client=7');
  });

  test('filters documents without a project', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await setupNavigationApi(page);
    await openDocuments(page);

    await page.getByTestId('documents-navigation-unassigned').click();

    await expect(page).toHaveURL(/project=none/);
    await expect(page.getByTestId('document-row-502')).toBeVisible();
    await expect(page.getByTestId('document-row-501')).toHaveCount(0);
  });

  test('filters documents without a client after switching navigation mode', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Catches reusing project=none for client navigation, which would expose client-owned documents.
    await setupNavigationApi(page);
    await openDocuments(page);

    await page.getByTestId('documents-mode-client').click();
    await page.getByTestId('documents-navigation-unassigned').click();

    await expect(page).toHaveURL(/by=client/);
    await expect(page).toHaveURL(/client=none/);
    await expect(page.getByTestId('document-row-502')).toBeVisible();
    await expect(page.getByTestId('document-row-501')).toHaveCount(0);
  });

  test('restores the saved client mode on a later visit', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const api = await setupNavigationApi(page);
    await openDocuments(page);

    await page.getByTestId('documents-mode-client').click();
    await expect.poll(api.preferenceMode).toBe('client');
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('documents-mode-client'))
      .toHaveAttribute('aria-selected', 'true');
  });

  test('keeps own folders usable during a facet error', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await setupNavigationApi(page, { navigationFailures: 1 });
    await openDocuments(page);

    await expect(page.getByText('No pudimos cargar la navegación.', { exact: true }))
      .toBeVisible();
    await page.getByRole('button', { name: /^Archivo interno —/ }).click();

    await expect(page).toHaveURL(/folder=31/);
    await expect(page.getByTestId('document-row-503')).toBeVisible();
  });

  test('retries entity navigation after a facet error', {
    tag: [...ADMIN_DOCUMENT_NAVIGATION, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const api = await setupNavigationApi(page, { navigationFailures: 1 });
    await openDocuments(page);

    await page.getByTestId('documents-navigation-retry').click();

    await expect(page.getByTestId('documents-navigation-project-41')).toBeVisible();
    await expect.poll(api.navigationAttempts).toBe(2);
  });
});
