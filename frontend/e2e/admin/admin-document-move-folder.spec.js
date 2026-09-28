/**
 * E2E tests for admin document move-folder flow.
 *
 * Covers: MoveFolderModal renders folder list; selecting a folder PATCHes
 * documents/{id}/update/ with folder_id; "Sin carpeta" PATCHes with null.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_MOVE_FOLDER } from '../helpers/flow-tags.js';

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

const FOLDER_DISENO = { id: 10, name: 'Diseño', slug: 'diseno', parent: null, order: 0, document_count: 1, children_count: 0 };
const FOLDER_DEV    = { id: 11, name: 'Dev', slug: 'dev', parent: null, order: 1, document_count: 0, children_count: 0 };

const DOC = {
  id: 5, title: 'Brief de Proyecto', status: 'published',
  client_name: 'TechCorp', created_at: '2026-04-01T10:00:00Z',
  folder: FOLDER_DISENO.id, folder_id: FOLDER_DISENO.id, folder_name: FOLDER_DISENO.name,
  tag_details: [],
};

function jsonOk(body) {
  return { status: 200, contentType: 'application/json', body: JSON.stringify(body) };
}

test.describe('Admin Document Move Folder', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 8800, role: 'admin', is_staff: true },
    });
  });

  test('move modal renders folder list with Sin carpeta option', {
    tag: [...ADMIN_DOCUMENT_MOVE_FOLDER, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') return jsonOk([DOC]);
      if (apiPath === 'document-folders/') return jsonOk([FOLDER_DISENO, FOLDER_DEV]);
      if (apiPath === 'document-tags/') return jsonOk([]);
      return null;
    });

    await page.goto('/panel', { waitUntil: 'domcontentloaded' });
    await page.getByRole('link', { name: 'Gestor Documental', exact: true }).click();
    await expect(page.getByText('Brief de Proyecto').first()).toBeVisible({ timeout: 15000 });

    await page.getByRole('row', { name: /Brief de Proyecto/i }).getByRole('button', { name: /^Acciones de / }).click();
    await page.getByRole('button', { name: 'Mover a carpeta' }).click();

    const modal = page.getByRole('dialog', { name: /Mover documento/i });
    await expect(modal).toBeVisible();
    await expect(modal.getByRole('button', { name: 'Sin carpeta' })).toBeVisible();
    await expect(modal.getByRole('button', { name: 'Diseño' })).toBeVisible();
    await expect(modal.getByRole('button', { name: 'Dev' })).toBeVisible();
  });

  test('selecting a folder PATCHes documents/{id}/update/ with folder_id', {
    tag: [...ADMIN_DOCUMENT_MOVE_FOLDER, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let patchBody = null;

    await mockApi(page, async ({ apiPath, method, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/' && method === 'GET') return jsonOk([DOC]);
      if (apiPath === 'document-folders/') return jsonOk([FOLDER_DISENO, FOLDER_DEV]);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath === `documents/${DOC.id}/update/` && method === 'PATCH') {
        patchBody = route.request().postDataJSON();
        return jsonOk({ ...DOC, ...patchBody });
      }
      return null;
    });

    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Brief de Proyecto').first()).toBeVisible({ timeout: 15000 });

    await page.getByRole('row', { name: /Brief de Proyecto/i }).getByRole('button', { name: /^Acciones de / }).click();
    await page.getByRole('button', { name: 'Mover a carpeta' }).click();
    const modal = page.getByRole('dialog', { name: /Mover documento/i });
    await expect(modal).toBeVisible();

    await modal.getByRole('button', { name: 'Dev' }).click();

    await expect(() => expect(patchBody).not.toBeNull()).toPass({ timeout: 5000 });
    expect(patchBody.folder_id).toBe(FOLDER_DEV.id);
  });

  test('a failed move keeps the modal open and shows an error message', {
    // Bug this catches: a move failure that still closes the modal, leaving
    // the admin unaware the document was not actually relocated.
    tag: [...ADMIN_DOCUMENT_MOVE_FOLDER, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/' && method === 'GET') return jsonOk([DOC]);
      if (apiPath === 'document-folders/') return jsonOk([FOLDER_DISENO, FOLDER_DEV]);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath === `documents/${DOC.id}/update/` && method === 'PATCH') {
        return { status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'Internal error' }) };
      }
      return null;
    });

    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Brief de Proyecto').first()).toBeVisible({ timeout: 15000 });

    await page.getByRole('row', { name: /Brief de Proyecto/i }).getByRole('button', { name: /^Acciones de / }).click();
    await page.getByRole('button', { name: 'Mover a carpeta' }).click();
    const modal = page.getByRole('dialog', { name: /Mover documento/i });
    await expect(modal).toBeVisible();

    await modal.getByRole('button', { name: 'Dev' }).click();

    await expect(modal.getByText('No se pudo mover el documento.')).toBeVisible({ timeout: 10000 });
    // The modal STAYS visible — the failure never closed it.
    await expect(modal).toBeVisible();
  });

  test('"Sin carpeta" PATCHes documents/{id}/update/ with folder_id null', {
    tag: [...ADMIN_DOCUMENT_MOVE_FOLDER, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let patchBody = null;

    await mockApi(page, async ({ apiPath, method, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/' && method === 'GET') return jsonOk([DOC]);
      if (apiPath === 'document-folders/') return jsonOk([FOLDER_DISENO, FOLDER_DEV]);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath === `documents/${DOC.id}/update/` && method === 'PATCH') {
        patchBody = route.request().postDataJSON();
        return jsonOk({ ...DOC, ...patchBody });
      }
      return null;
    });

    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Brief de Proyecto').first()).toBeVisible({ timeout: 15000 });

    await page.getByRole('row', { name: /Brief de Proyecto/i }).getByRole('button', { name: /^Acciones de / }).click();
    await page.getByRole('button', { name: 'Mover a carpeta' }).click();
    const modal = page.getByRole('dialog', { name: /Mover documento/i });
    await expect(modal).toBeVisible();

    await modal.getByRole('button', { name: 'Sin carpeta' }).click();

    await expect(() => expect(patchBody).not.toBeNull()).toPass({ timeout: 5000 });
    expect(patchBody.folder_id).toBeNull();
  });

  test('asks before overwriting the client of a document moved to another owner folder', {
    tag: [...ADMIN_DOCUMENT_MOVE_FOLDER, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    // La carpeta organiza, no es dueña: mover no decide por el operador.
    const ownedFolder = {
      ...FOLDER_DEV, client: 7, client_display_name: 'Kore SAS',
    };
    const ownedDoc = { ...DOC, client: 9, client_display_name: 'Ana Pérez' };
    let patchBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') return jsonOk([ownedDoc]);
      if (apiPath === 'document-folders/') return jsonOk([FOLDER_DISENO, ownedFolder]);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath === 'documents/5/update/' && method === 'PATCH') {
        patchBody = route.request().postDataJSON();
        return jsonOk({ ...ownedDoc, folder: ownedFolder.id });
      }
      return null;
    });

    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('Brief de Proyecto').first()).toBeVisible({ timeout: 15000 });
    await page.getByRole('row', { name: /Brief de Proyecto/i }).getByRole('button', { name: /^Acciones de / }).click();
    await page.getByRole('button', { name: 'Mover a carpeta' }).click();

    const modal = page.getByRole('dialog', { name: /Mover documento/i });
    await modal.getByRole('button', { name: /^Dev/ }).click();

    // Nada se movió todavía: primero la pregunta.
    await expect(page.getByTestId('move-folder-client-choice')).toBeVisible();
    expect(patchBody).toBeNull();

    await page.getByTestId('move-folder-adopt-client').click();

    await expect.poll(() => patchBody).not.toBeNull();
    expect(patchBody.adopt_folder_client).toBe(true);
    expect(patchBody.folder_id).toBe(11);
  });
  test('moves the live contract using a compact write response', {
    tag: [...ADMIN_DOCUMENT_MOVE_FOLDER, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    let location = FOLDER_DISENO;
    let receivedPayload;
    await mockApi(page, async ({ apiPath, method, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') return jsonOk([{ ...DOC, folder: location.id, folder_name: location.name, is_contract_mirror: true, movable: true }]);
      if (apiPath === 'document-folders/') return jsonOk([FOLDER_DISENO, FOLDER_DEV]);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath === 'documents/5/update/' && method === 'PATCH') {
        receivedPayload = route.request().postDataJSON();
        location = FOLDER_DEV;
        return jsonOk({ id: DOC.id, title: DOC.title, folder_id: location.id, folder_name: location.name, status: 'published', editable: false, movable: true, etag: 'moved' });
      }
      return null;
    });
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    const row = page.getByRole('row', { name: /Brief de Proyecto/i });
    await row.getByRole('button', { name: /^Acciones de / }).click();
    await page.getByRole('button', { name: 'Mover a carpeta' }).click();
    const modal = page.getByRole('dialog', { name: /Mover documento/i });
    await modal.getByRole('button', { name: 'Dev' }).click();
    await expect(modal).toBeHidden();
    expect(receivedPayload).toEqual({ folder_id: FOLDER_DEV.id });
    await expect(row).toContainText('Dev');
  });

  test('a protected destination keeps the document in its current folder', {
    tag: [...ADMIN_DOCUMENT_MOVE_FOLDER, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'documents/') return jsonOk([DOC]);
      if (apiPath === 'document-folders/') return jsonOk([FOLDER_DISENO, FOLDER_DEV]);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath === 'documents/5/update/' && method === 'PATCH') {
        return { status: 409, contentType: 'application/json', body: JSON.stringify({ code: 'system_managed_folder', message: 'Destino protegido.' }) };
      }
      return null;
    });
    await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
    await page.getByRole('row', { name: /Brief de Proyecto/i }).getByRole('button', { name: /^Acciones de / }).click();
    await page.getByRole('button', { name: 'Mover a carpeta' }).click();
    const modal = page.getByRole('dialog', { name: /Mover documento/i });
    await modal.getByRole('button', { name: 'Dev' }).click();
    await expect(modal.getByText('No se pudo mover el documento.')).toBeVisible();
    await expect(modal).toBeVisible();
  });

});
