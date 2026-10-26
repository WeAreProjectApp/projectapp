/**
 * Secure-link folder filing in the administrative panel.
 *
 * Covers: inheriting a selected folder when creating a link, and preserving
 * the move form when the server rejects a stale or failed move.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { chooseRowAction } from '../helpers/row-actions.js';
import { json, secureLinkRow, secureLinkTypes } from '../helpers/secure-links.js';

test.setTimeout(60_000);

const CREATED_URL = 'https://projectapp.test/es-co/secure-link/view#secure-folder-e2e';
const CLIENT_ID = 73;
const PROJECT_ID = 91;
const ROOT_FOLDER = {
  id: 401,
  name: 'Proyecto Atlas',
  parent: null,
  order: 0,
  client: CLIENT_ID,
  project: PROJECT_ID,
  managed_project: null,
  folder_kind: 'manual',
  is_archived: false,
  is_read_only: false,
  link_count: 0,
  archived_link_count: 0,
  updated_at: '2026-10-20T12:00:00Z',
};
const CHILD_FOLDER = {
  ...ROOT_FOLDER,
  id: 402,
  name: 'Accesos de lanzamiento',
  parent: ROOT_FOLDER.id,
  order: 0,
  updated_at: '2026-10-20T12:01:00Z',
};
const DESTINATION_FOLDER = {
  ...ROOT_FOLDER,
  id: 403,
  name: 'Revisión legal',
  client: null,
  project: null,
  updated_at: '2026-10-20T12:02:00Z',
};
const FOLDERS = [ROOT_FOLDER, CHILD_FOLDER, DESTINATION_FOLDER];

const navigation = {
  totals: { active: { folders: 3, documents: 1 }, archived: { folders: 0, documents: 0 } },
  unassigned: {
    project: { active: { folders: 1, documents: 0 }, archived: { folders: 0, documents: 0 } },
    client: { active: { folders: 1, documents: 0 }, archived: { folders: 0, documents: 0 } },
  },
  projects: [{
    id: PROJECT_ID,
    name: 'Proyecto Atlas',
    client: CLIENT_ID,
    client_name: 'Cliente Atlas',
    managed_root_id: null,
    catalog_bucket: 'active',
    counts: { active: { folders: 2, documents: 1 }, archived: { folders: 0, documents: 0 } },
  }],
  clients: [{
    id: CLIENT_ID,
    name: 'Cliente Atlas',
    catalog_bucket: 'active',
    counts: { active: { folders: 2, documents: 1 }, archived: { folders: 0, documents: 0 } },
  }],
};

function listPayload(rows) {
  const lifecycleCounts = rows.reduce((counts, row) => {
    counts[row.lifecycle_status || row.status] += 1;
    return counts;
  }, { ready: 0, sent: 0, opened: 0, expired: 0, revoked: 0 });
  return {
    results: rows,
    count: rows.length,
    page: 1,
    page_size: 25,
    counts: { active: rows.length, consumed: 0, expired: 0, revoked: 0, all: rows.length },
    lifecycle_counts: { ...lifecycleCounts, all: rows.length },
    unopened_received: 0,
    public_create_url: 'https://projectapp.test/es-co/secure-link',
  };
}

async function installWorkspaceMock(page, { rows = [], create, move } = {}) {
  let links = [...rows];
  const calls = { create: [], move: [] };

  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'auth/check/' && method === 'GET') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'panel/dashboard/' && method === 'GET') {
      return json({ finance: null, proposals: { total_proposals: 0, by_status: {}, recent: [] }, additional_modules: {}, operations: {}, attention: [] });
    }
    if (apiPath === 'secure-links/public/types/' && method === 'GET') return json({ types: secureLinkTypes });
    if (apiPath === 'secure-links/folders/' && method === 'GET') return json({ folders: FOLDERS, navigation });
    if (apiPath === 'accounting/projects/' && method === 'GET') {
      return json({ results: [{ id: PROJECT_ID, name: 'Proyecto Atlas', current_state: { operational_effect: 'operating' } }] });
    }
    if (apiPath === 'secure-links/' && method === 'GET') return json(listPayload(links));
    if (apiPath === 'secure-links/create/' && method === 'POST') {
      const payload = route.request().postDataJSON();
      calls.create.push(payload);
      if (create) return typeof create === 'function' ? create(payload) : create;
      const created = secureLinkRow({
        id: 801,
        title: payload.title,
        client: payload.client,
        project: payload.project,
        folder: payload.folder,
      });
      links = [created, ...links];
      return json({ ...created, url: CREATED_URL }, 201);
    }
    const moveMatch = apiPath.match(/^secure-links\/(\d+)\/move\/$/);
    if (moveMatch && method === 'POST') {
      const payload = route.request().postDataJSON();
      calls.move.push(payload);
      if (move) return typeof move === 'function' ? move(payload) : move;
      const current = links.find((row) => row.id === Number(moveMatch[1]));
      return json({ ...current, folder: payload.folder });
    }
    return null;
  });

  return calls;
}

async function openMoveForm(page, rowId) {
  await chooseRowAction(page, {
    kebab: `secure-link-actions-${rowId}`,
    menu: 'secure-link-actions-modal',
    action: `secure-link-move-${rowId}`,
  });
  const form = page.getByTestId('secure-folder-form');
  await expect(form.getByRole('heading')).toHaveText('Mover enlace');
  return form;
}

test.describe('Admin secure-link folders', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'secure-link-folders-token',
      userAuth: { id: 8901, role: 'admin', is_staff: true },
    });
  });

  // Bug caught: links created from a subfolder could silently fall back to the
  // root and lose the client/project inherited from that folder.
  test('creates a link in the selected subfolder with its inherited associations', {
    tag: ['@flow:admin-secure-link-create', '@outcome:success'],
  }, async ({ page }) => {
    const calls = await installWorkspaceMock(page);
    await page.goto(`/es-co/panel/secure-links?folder=${ROOT_FOLDER.id}`, { waitUntil: 'domcontentloaded' });

    await page.getByTestId(`secure-folder-child-${CHILD_FOLDER.id}`).click();
    await expect(page.getByTestId('folder-breadcrumb-root')).toHaveText('Todos los enlaces');
    await page.getByTestId('secure-links-new').click();
    await page.getByTestId('secure-link-title').fill('Llave de despliegue Atlas');
    await page.getByTestId('secure-link-field-message').fill('Comparte esta llave sólo con el equipo autorizado.');
    await page.getByTestId('secure-link-save').click();

    await expect(page.getByTestId('secure-link-created-url')).toHaveText(CREATED_URL);
    expect(calls.create).toHaveLength(1);
    expect(calls.create[0]).toMatchObject({
      folder: CHILD_FOLDER.id,
      client: CLIENT_ID,
      project: PROJECT_ID,
    });
  });

  // Bug caught: a stale folder move could close the dialog and falsely imply
  // that the link had moved even though the server rejected its revision.
  test('keeps the move form open and reports a revision conflict', {
    tag: ['@flow:admin-secure-link-manage', '@outcome:error'],
  }, async ({ page }) => {
    const row = secureLinkRow({ folder: ROOT_FOLDER.id, updated_at: '2026-10-20T12:10:00Z' });
    const calls = await installWorkspaceMock(page, {
      rows: [row],
      move: json({ detail: 'El enlace fue actualizado por otra persona. Vuelve a intentarlo.' }, 409),
    });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });

    const form = await openMoveForm(page, row.id);
    await form.getByTestId('secure-folder-parent').selectOption(String(DESTINATION_FOLDER.id));
    await page.getByTestId('secure-folder-save').click();

    await expect(page.getByRole('alert').filter({ hasText: 'El enlace fue actualizado por otra persona. Vuelve a intentarlo.' }))
      .toHaveText('El enlace fue actualizado por otra persona. Vuelve a intentarlo.');
    await expect(form.getByRole('heading')).toHaveText('Mover enlace');
    expect(calls.move).toEqual([{
      folder: DESTINATION_FOLDER.id,
      expected_updated_at: row.updated_at,
    }]);
  });

  // Bug caught: a server failure could dismiss the move form, preventing the
  // administrator from retrying after a transient error.
  test('keeps the move form available after a server failure', {
    tag: ['@flow:admin-secure-link-manage', '@outcome:failure'],
  }, async ({ page }) => {
    const row = secureLinkRow({ folder: ROOT_FOLDER.id, updated_at: '2026-10-20T12:10:00Z' });
    await installWorkspaceMock(page, {
      rows: [row],
      move: json({ error: 'El servicio de enlaces no responde.' }, 503),
    });
    await page.goto('/es-co/panel/secure-links', { waitUntil: 'domcontentloaded' });

    const form = await openMoveForm(page, row.id);
    await form.getByTestId('secure-folder-parent').selectOption(String(DESTINATION_FOLDER.id));
    await page.getByTestId('secure-folder-save').click();

    await expect(page.getByRole('alert').filter({ hasText: 'El servicio de enlaces no responde.' }))
      .toHaveText('El servicio de enlaces no responde.');
    await expect(form.getByRole('heading')).toHaveText('Mover enlace');
  });
});
