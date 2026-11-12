/**
 * E2E tests for the independent own-folder section in the document manager.
 *
 * @flow:admin-document-folders
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_FOLDERS } from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const jsonOk = (body) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const FOLDER_CUENTAS = {
  id: 11,
  name: 'Cuentas de cobro',
  slug: 'cuentas-de-cobro',
  parent: null,
  order: 0,
  project: null,
  client: null,
  managed_project: null,
  folder_kind: 'manual',
  is_system_managed: false,
  is_archived: false,
  document_count: 1,
  children_count: 0,
  active_document_count: 1,
  active_children_count: 0,
  archived_document_count: 0,
  archived_children_count: 0,
};

const FOLDER_CONTRATOS = {
  ...FOLDER_CUENTAS,
  id: 12,
  name: 'Contratos',
  slug: 'contratos',
  order: 1,
  document_count: 0,
  active_document_count: 0,
};

const PROJECT_KORE = {
  ...FOLDER_CUENTAS,
  id: 21,
  name: 'Kore Health',
  slug: 'kore-health',
  project: 41,
  client: 7,
  managed_project: 41,
  folder_kind: 'project',
  is_system_managed: true,
  is_project_visible: true,
  managed_project_state: { name: 'Activo', system_key: 'active' },
  document_count: 2,
  children_count: 1,
  active_document_count: 2,
  active_children_count: 1,
};

const DOC_IN_FOLDER = {
  id: 1,
  title: 'Factura ACME',
  status: 'published',
  is_archived: false,
  client: null,
  client_name: 'ACME',
  project: null,
  created_at: '2026-04-01T10:00:00Z',
  folder: FOLDER_CUENTAS.id,
  folder_name: FOLDER_CUENTAS.name,
  tag_details: [],
  active_states: [],
};

const DOC_ORPHAN = {
  ...DOC_IN_FOLDER,
  id: 2,
  title: 'Borrador sin carpeta',
  status: 'draft',
  client_name: null,
  created_at: '2026-04-02T10:00:00Z',
  folder: null,
  folder_name: null,
};

const NAVIGATION = {
  totals: {
    active: { folders: 3, documents: 2 },
    archived: { folders: 0, documents: 0 },
  },
  unassigned: {
    project: {
      active: { folders: 2, documents: 2 },
      archived: { folders: 0, documents: 0 },
    },
    client: {
      active: { folders: 2, documents: 2 },
      archived: { folders: 0, documents: 0 },
    },
  },
  projects: [{
    id: 41,
    name: 'Kore Health',
    client: 7,
    client_display_name: 'Kore SAS',
    managed_root_id: PROJECT_KORE.id,
    state: { name: 'Activo', system_key: 'active', show_in_document_manager: true },
    is_visible: true,
    catalog_bucket: 'active',
    counts: {
      active: { folders: 1, documents: 0 },
      archived: { folders: 0, documents: 0 },
    },
  }],
  clients: [{
    id: 7,
    name: 'Kore SAS',
    is_archived: false,
    catalog_bucket: 'active',
    counts: {
      active: { folders: 1, documents: 0 },
      archived: { folders: 0, documents: 0 },
    },
  }],
};

async function setupFolderApi(page, folders = [FOLDER_CUENTAS, FOLDER_CONTRATOS]) {
  let preferenceMode = 'project';
  const requestedUrls = [];

  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/') {
      return jsonOk({ user: { username: 'admin', is_staff: true } });
    }
    if (apiPath === 'accounts/panel-preferences/documents/') {
      if (method === 'PATCH') {
        preferenceMode = route.request().postDataJSON().navigation_mode;
      }
      return jsonOk({ navigation_mode: preferenceMode });
    }
    if (apiPath === 'documents/navigation/') return jsonOk(NAVIGATION);
    if (apiPath === 'document-folders/') return jsonOk(folders);
    if (apiPath === 'documents/counts/') {
      return jsonOk({
        documents: { active: 2, archived: 0, unfiled_active: 1, unfiled_archived: 0 },
        folders: { active: folders.length, archived: 0 },
      });
    }
    if (apiPath === 'documents/') {
      const requestUrl = route.request().url();
      requestedUrls.push(requestUrl);
      const folder = new URL(requestUrl).searchParams.get('folder');
      if (folder === String(FOLDER_CUENTAS.id)) return jsonOk([DOC_IN_FOLDER]);
      if (folder === 'none') return jsonOk([DOC_ORPHAN]);
      return jsonOk([DOC_IN_FOLDER, DOC_ORPHAN]);
    }
    if (apiPath === 'document-states/' || apiPath === 'document-state-groups/') {
      return jsonOk([]);
    }
    if (apiPath === 'document-tags/') return jsonOk([]);
    if (apiPath.startsWith('accounting/projects/')) return jsonOk({ results: [] });
    return null;
  });

  return { requestedUrls };
}

async function openDocuments(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  const documentsLink = page.getByRole('link', { name: 'Gestor Documental', exact: true });
  await expect(documentsLink).toBeVisible({ timeout: 35_000 });
  await documentsLink.click();
  await expect(page.getByRole('heading', { name: 'Gestor Documental', exact: true }))
    .toBeVisible({ timeout: 35_000 });
}

test.describe('Admin Document Folders', () => {
  // Evita que la compilación fría de esta página Nuxt compita entre workers.
  test.describe.configure({ mode: 'serial' });

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 8701, role: 'admin', is_staff: true },
    });
  });

  test('filters the list by own-folder id', {
    tag: [...ADMIN_DOCUMENT_FOLDERS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const api = await setupFolderApi(page);
    await openDocuments(page);

    await expect(page.getByTestId('document-row-1')).toBeVisible();
    await expect(page.getByTestId('document-row-2')).toBeVisible();
    await page.getByRole('button', { name: /^Cuentas de cobro —/ }).click();

    await expect.poll(() => api.requestedUrls.at(-1)).toContain('folder=11');
    await expect(page.getByTestId('document-row-1')).toBeVisible();
    await expect(page.getByTestId('document-row-2')).toHaveCount(0);
  });

  test('filters uncategorized documents from Sin carpeta', {
    tag: [...ADMIN_DOCUMENT_FOLDERS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const api = await setupFolderApi(page);
    await openDocuments(page);

    await page.getByRole('button', { name: /^Sin carpeta/ }).click();

    await expect.poll(() => api.requestedUrls.at(-1)).toContain('folder=none');
    await expect(page.getByTestId('document-row-2')).toBeVisible();
    await expect(page.getByTestId('document-row-1')).toHaveCount(0);
  });

  test('preselects the active own folder as the new parent', {
    tag: [...ADMIN_DOCUMENT_FOLDERS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupFolderApi(page);
    await openDocuments(page);

    await page.getByRole('button', { name: /^Cuentas de cobro —/ }).click();
    await page.getByRole('button', { name: 'Nueva carpeta' }).click();

    const parentSelect = page.getByTestId('folder-manager-parent');
    await expect(parentSelect).toBeVisible();
    await expect(parentSelect.locator('option:checked')).toHaveText('Cuentas de cobro');
  });

  test('preserves own folders after switching the navigation mode', {
    tag: [...ADMIN_DOCUMENT_FOLDERS, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // Regression: switching entity mode must not make manual folders disappear.
    await setupFolderApi(page, [PROJECT_KORE, FOLDER_CONTRATOS]);
    await openDocuments(page);

    const ownFolders = page.getByTestId('manual-folder-section');
    await expect(ownFolders).toContainText('Carpetas propias');
    await expect(page.getByTestId('documents-navigation-project-41')).toContainText('Kore Health');
    await expect(ownFolders).toContainText('Contratos');
    await expect(ownFolders).not.toContainText('Kore Health');

    await page.getByTestId('documents-mode-client').click();

    await expect(page.getByTestId('documents-mode-client'))
      .toHaveAttribute('aria-selected', 'true');
    await expect(ownFolders).toContainText('Contratos');
    await expect(ownFolders).not.toContainText('Kore Health');
  });

  test('does not show the PA-108 reconciliation warning', {
    tag: [...ADMIN_DOCUMENT_FOLDERS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Regression: the retired PA-108 warning must not return to the document manager.
    await setupFolderApi(page, [PROJECT_KORE, FOLDER_CONTRATOS]);
    await openDocuments(page);

    await expect(page.getByTestId('documents-navigation-project-41')).toContainText('Kore Health');
    await expect(page.getByText(/Faltan las carpetas gestionadas/)).toHaveCount(0);
    await expect(page.getByText('Revisar proyectos', { exact: true })).toHaveCount(0);
  });

  test('offers a managed project root as a manual-folder parent', {
    tag: [...ADMIN_DOCUMENT_FOLDERS, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await setupFolderApi(page, [PROJECT_KORE]);
    await openDocuments(page);

    await page.getByRole('button', { name: 'Nueva carpeta' }).click();

    const parentSelect = page.getByTestId('folder-manager-parent');
    await expect(parentSelect.locator('option', { hasText: 'Kore Health' })).toHaveCount(1);
    await expect(parentSelect.locator('option:checked')).toHaveText('Ninguna (carpeta raíz)');
  });

});
