/**
 * E2E tests for the admin document folder management flow.
 *
 * @flow:admin-document-folder-manage
 * Covers: FolderManagerModal create with the root-parent default, inline
 *         rename through the edit panel, delete confirmation for empty
 *         folders and the blocking panel for folders with documents, plus
 *         the sidebar row actions (DELETE-typed confirmation on empty folders,
 *         delete disabled on folders that still hold content — archived
 *         included, matching the backend 409 — and archive as the way out).
 *         Drag-reorder is intentionally not asserted (flaky in CI).
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_FOLDER_MANAGE } from '../helpers/flow-tags.js';
import { viewportUse } from '../helpers/viewports.js';

const authCheck = { status: 200, contentType: 'application/json', body: JSON.stringify({ user: { username: 'admin', is_staff: true } }) };

// `folder_kind` va en todas las fixtures porque el serializer siempre lo manda:
// omitirlo dejaba pasar guardas que en produccion si distinguen la clase de raiz.
const emptyFolder = { id: 10, name: 'Contratos', parent: null, position: 1, document_count: 0, folder_kind: 'manual' };
const busyFolder = { id: 11, name: 'Facturas', parent: null, position: 2, document_count: 3, folder_kind: 'manual' };
const project = {
  id: 40,
  name: 'Kore rediseño',
  status: 'active',
  status_label: 'Activo',
  client_profile_id: 7,
  client_display_name: 'Kore SAS',
};

const ownedFolder = {
  ...emptyFolder,
  project: 40,
  client: 7,
  client_display_name: 'Kore SAS',
  project_name: 'Kore rediseño',
};

const navigationPayload = {
  totals: {
    active: { folders: 1, documents: 0 },
    archived: { folders: 0, documents: 0 },
  },
  unassigned: {
    project: {
      active: { folders: 0, documents: 0 },
      archived: { folders: 0, documents: 0 },
    },
    client: {
      active: { folders: 0, documents: 0 },
      archived: { folders: 0, documents: 0 },
    },
  },
  projects: [{
    id: 40,
    name: 'Kore rediseño',
    client: 7,
    client_display_name: 'Kore SAS',
    managed_root_id: null,
    state: { name: 'Activo', system_key: 'active' },
    is_visible: true,
    catalog_bucket: 'active',
    counts: {
      active: { folders: 1, documents: 0 },
      archived: { folders: 0, documents: 0 },
    },
  }],
  clients: [],
};

function baseRoutes(apiPath, folders) {
  if (apiPath === 'auth/check/') return authCheck;
  if (apiPath === 'accounts/panel-preferences/documents/') {
    return { status: 200, contentType: 'application/json', body: JSON.stringify({ navigation_mode: 'project' }) };
  }
  if (apiPath === 'documents/navigation/') {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(navigationPayload) };
  }
  if (apiPath === 'documents/') return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
  if (apiPath === 'document-folders/') return { status: 200, contentType: 'application/json', body: JSON.stringify(folders) };
  if (apiPath === 'document-tags/') return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
  if (apiPath.startsWith('accounting/projects/')) return { status: 200, contentType: 'application/json', body: JSON.stringify({ results: [project] }) };
  return null;
}

async function openFolderManager(page) {
  await page.goto('/panel/documents');
  await page.getByRole('button', { name: /Gestionar/i }).click();
}

/** Abre una carpeta asignada desde su proyecto, sin duplicarla como huérfana. */
async function openOwnedFolder(page) {
  await page.getByTestId('documents-navigation-project-40').click();
  const row = page.getByRole('row', { name: /Contratos/i });
  await expect(row).toBeVisible();
  await row.click();
}

test.describe('Admin Document Folder Manage', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, { token: 'e2e-token', userAuth: { id: 8700, role: 'admin', is_staff: true } });
  });

  test('restores focus after closing the named folder manager', {
    // Bug caught: Gestionar carpetas was an unnamed overlay that left focus behind it or on BODY.
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath, [emptyFolder]));
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });

    const opener = page.getByRole('button', { name: 'Gestionar', exact: true });
    await opener.click();
    const dialog = page.getByRole('dialog', { name: 'Gestionar carpetas' });
    await expect(dialog).toHaveAttribute('aria-modal', 'true');
    await expect(dialog.getByTestId('folder-manager-new-name')).toBeFocused();
    const edit = dialog.getByRole('button', { name: 'Editar carpeta', exact: true });
    await edit.hover();
    await edit.click();
    const child = page.getByRole('dialog', { name: 'Editar "Contratos"' });
    await expect(child).toBeVisible();
    await child.getByRole('button', { name: 'Cancelar', exact: true }).click();
    await expect(edit).toBeFocused();
    await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe('hidden');

    await dialog.getByRole('button', { name: 'Cerrar', exact: true }).first().click();
    await expect(opener).toBeFocused();
  });

  test.describe('folder manager from the compact drawer', () => {
    test.use(viewportUse('compact'));

    test('returns focus to Cambiar navegación after its drawer opener unmounts', {
      // Bug caught: closing the manager opened from the drawer returned focus to a removed button.
      tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success', '@responsive:documents'],
    }, async ({ page }) => {
      await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath, [emptyFolder]));
      await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });

      const drawerTrigger = page.getByTestId('folder-drawer-trigger');
      await drawerTrigger.click();
      const drawer = page.getByTestId('folder-drawer');
      await drawer.getByRole('button', { name: 'Gestionar', exact: true }).click();

      const dialog = page.getByRole('dialog', { name: 'Gestionar carpetas' });
      await expect(dialog.getByTestId('folder-manager-new-name')).toBeFocused();
      await dialog.getByRole('button', { name: 'Cerrar', exact: true }).first().click();

      await expect(drawerTrigger).toBeFocused();
      await expect(drawerTrigger).toContainText('Cambiar navegación');
    });
  });

  test('creates a root folder from the manager form', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let createBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'document-folders/create/' && method === 'POST') {
        createBody = route.request().postDataJSON();
        return { status: 201, contentType: 'application/json', body: JSON.stringify({ id: 12, name: createBody.name, parent: null, position: 1, document_count: 0 }) };
      }
      return baseRoutes(apiPath, [emptyFolder]);
    });
    await openFolderManager(page);

    await page.getByTestId('folder-manager-new-name').fill('Propuestas 2026');
    await page.getByRole('button', { name: 'Crear', exact: true }).click();

    await expect.poll(() => createBody).not.toBeNull();
    expect(createBody.name).toBe('Propuestas 2026');
  });

  test('renames a folder through the shared folder form', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let patchBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'document-folders/10/update/' && method === 'PATCH') {
        patchBody = route.request().postDataJSON();
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...emptyFolder, name: patchBody.name }) };
      }
      return baseRoutes(apiPath, [emptyFolder]);
    });
    await openFolderManager(page);

    // El panel inline se retiró: el lápiz abre el formulario compartido, el
    // mismo que se abre desde la fila del panel lateral y desde la cabecera.
    await page.locator('button[title="Editar carpeta"]').first().click();
    const editInput = page.getByTestId('folder-form-name');
    await expect(editInput).toHaveValue('Contratos');
    await editInput.fill('Contratos firmados');
    await page.getByTestId('folder-form-save').click();

    await expect.poll(() => patchBody).not.toBeNull();
    expect(patchBody.name).toBe('Contratos firmados');
  });

  test('edits a folder from its sidebar row, without opening the manager', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let patchBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'document-folders/10/update/' && method === 'PATCH') {
        patchBody = route.request().postDataJSON();
        return { status: 200, contentType: 'application/json', body: JSON.stringify({ ...emptyFolder, name: patchBody.name }) };
      }
      return baseRoutes(apiPath, [emptyFolder]);
    });
    await page.goto('/panel/documents');

    await page.getByTestId('folder-edit').first().click();
    await expect(page.getByTestId('folder-form-name')).toHaveValue('Contratos');
    await page.getByTestId('folder-form-name').fill('Contratos 2026');
    await page.getByTestId('folder-form-save').click();

    await expect.poll(() => patchBody).not.toBeNull();
    expect(patchBody.name).toBe('Contratos 2026');
  });

  test('edits the folder you are standing in, from its header', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath, [ownedFolder]));
    await page.goto('/panel/documents');

    await openOwnedFolder(page);

    // La cabecera dice de quién es la carpeta y ofrece editarla ahí mismo.
    await expect(page.getByTestId('folder-header-name')).toHaveText('Contratos');
    await expect(page.getByTestId('folder-header-client')).toContainText('Kore SAS');
    await page.getByTestId('folder-header-edit').click();

    await expect(page.getByTestId('folder-form-name')).toHaveValue('Contratos');
  });

  test('the document project picker keeps its option fully usable in the form modal', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // Bug caught: a project result inside a short document modal could be
    // clipped before an administrator had a chance to select it.
    await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath, [ownedFolder]));
    await page.goto('/panel');
    await page.getByRole('navigation', { name: 'Navegación del panel' })
      .getByRole('link', { name: 'Gestor Documental' })
      .click();
    await expect(page).toHaveURL(/\/panel\/documents/);
    await openOwnedFolder(page);
    await page.getByTestId('folder-header-edit').click();
    await page.getByTestId('folder-form-project').click();
    const option = page.getByTestId('folder-form-project-option-40');
    await expect(option).toBeInViewport({ ratio: 1 });
    await option.click();
    await expect(page.getByTestId('folder-form-project')).toHaveValue('Kore rediseño');
  });

  test('deletes an empty folder after the destructive confirmation', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let deleteCalled = false;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'document-folders/10/delete/' && method === 'DELETE') {
        deleteCalled = true;
        return { status: 204, contentType: 'application/json', body: '' };
      }
      return baseRoutes(apiPath, [emptyFolder]);
    });
    await openFolderManager(page);

    await page.getByTestId('folder-manager-delete').first().click();
    await expect(page.getByText('Eliminar "Contratos"')).toBeVisible();
    // El gestor delega en DeleteFolderModal: un solo contrato de borrado, con
    // la misma reja escrita que la papelera del sidebar.
    await page.getByTestId('delete-folder-type-input').fill('DELETE');
    await page.getByTestId('delete-folder-confirm').click();

    await expect.poll(() => deleteCalled).toBe(true);
  });

  test('blocks deleting a folder that still holds documents', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    let deleteCalled = false;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath.startsWith('document-folders/') && method === 'DELETE') {
        deleteCalled = true;
        return { status: 204, contentType: 'application/json', body: '' };
      }
      return baseRoutes(apiPath, [busyFolder]);
    });
    await openFolderManager(page);

    await page.getByTestId('folder-manager-delete').first().click();

    await expect(page.getByRole('button', { name: 'Confirmar eliminación' })).toBeHidden();
    expect(deleteCalled).toBe(false);
  });

  test('deletes an empty folder from the sidebar after typing DELETE', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let deleteCalled = false;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'document-folders/10/delete/' && method === 'DELETE') {
        deleteCalled = true;
        return { status: 204, contentType: 'application/json', body: '' };
      }
      return baseRoutes(apiPath, [emptyFolder]);
    });
    await page.goto('/panel/documents');

    await page.getByRole('button', { name: 'Eliminar carpeta Contratos' }).click();

    const confirmBtn = page.getByTestId('delete-folder-confirm');
    await expect(confirmBtn).toBeDisabled();
    await page.getByTestId('delete-folder-type-input').fill('delete');
    await expect(confirmBtn).toBeDisabled();
    await page.getByTestId('delete-folder-type-input').fill('DELETE');
    await expect(confirmBtn).toBeEnabled();
    await confirmBtn.click();

    await expect.poll(() => deleteCalled).toBe(true);
  });

  test('the sidebar delete icon goes inert for a filled folder, and archive takes over', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let deleteCalled = false;
    let archiveCalled = false;
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath.startsWith('document-folders/') && method === 'DELETE') {
        deleteCalled = true;
        return { status: 204, contentType: 'application/json', body: '' };
      }
      if (apiPath === 'document-folders/11/archive/' && method === 'PATCH') {
        archiveCalled = true;
        return {
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            folder: { ...busyFolder, is_archived: true },
            archived_folders: 0,
            archived_documents: 3,
          }),
        };
      }
      return baseRoutes(apiPath, [busyFolder]);
    });
    await page.goto('/panel/documents');

    // El backend responde 409 con cualquier contenido, así que el ícono lo
    // dice de entrada en vez de llevar a un modal sin salida.
    const deleteButton = page.getByTestId('folder-delete');
    const deleteTooltipProxy = page.locator('[data-disabled-action-proxy]', {
      has: deleteButton,
    });
    await expect(deleteButton).toBeDisabled();
    // El tooltip sólo aparece al pasar por encima; es donde vive la explicación.
    await deleteTooltipProxy.hover();
    await expect(page.getByRole('tooltip')).toContainText('No se puede eliminar');

    await page.getByTestId('folder-archive').click();
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByText('Carpeta archivada')).toBeVisible();
    await expect.poll(() => archiveCalled).toBe(true);
    expect(deleteCalled).toBe(false);
  });

  test('surfaces the backend conflict when the folder filled up behind the icon', {
    tag: [...ADMIN_DOCUMENT_FOLDER_MANAGE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'document-folders/10/delete/' && method === 'DELETE') {
        return {
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: 'La carpeta tiene 2 documento(s). Muévelos o elimínalos antes de borrarla.',
            document_count: 2,
          }),
        };
      }
      return baseRoutes(apiPath, [emptyFolder]);
    });
    await page.goto('/panel/documents');

    await page.getByRole('button', { name: 'Eliminar carpeta Contratos' }).click();
    await page.getByTestId('delete-folder-type-input').fill('DELETE');
    await page.getByTestId('delete-folder-confirm').click();

    await expect(page.getByTestId('delete-folder-error'))
      .toContainText('La carpeta tiene 2 documento(s)');
    await expect(page.getByTestId('delete-folder-confirm')).toBeVisible();
  });
});
