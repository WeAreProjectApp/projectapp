/**
 * E2E tests for the admin document folder hierarchy flow.
 *
 * @flow:admin-document-folder-hierarchy
 * Covers: root-only sidebar, subfolder rows inside the table, and breadcrumb
 *         navigation when entering and leaving nested folders.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_FOLDER_HIERARCHY } from '../helpers/flow-tags.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

const authCheck = {
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ user: { username: 'admin', is_staff: true } }),
};

// Árbol: Raíz A (11) -> Subcarpeta (21) -> Sub-sub (31) ; Raíz B (12)
//
// Los documentos se reparten 1 / 1 / 4 hacia abajo: cada carpeta guarda MENOS
// de lo que su rama contiene, que es la forma exacta del bug (una carpeta
// diciendo 1 mientras adentro hay 6).
function activeFolder(base) {
  return {
    ...base,
    is_archived: false,
    active_document_count: base.document_count,
    active_children_count: base.children_count,
    archived_document_count: 0,
    archived_children_count: 0,
  };
}

const FOLDER_ROOT = activeFolder({
  id: 11, name: 'Raiz A', slug: 'raiz-a', parent: null,
  order: 0, document_count: 1, children_count: 1,
});
const FOLDER_OTHER_ROOT = activeFolder({
  id: 12, name: 'Raiz B', slug: 'raiz-b', parent: null,
  order: 1, document_count: 0, children_count: 0,
});
const FOLDER_SUB = activeFolder({
  id: 21, name: 'Subcarpeta Uno', slug: 'subcarpeta-uno', parent: 11,
  order: 0, document_count: 1, children_count: 1,
});
const FOLDER_SUBSUB = activeFolder({
  id: 31, name: 'Sub Sub', slug: 'sub-sub', parent: 21,
  order: 0, document_count: 4, children_count: 0,
});

const ALL_FOLDERS = [FOLDER_ROOT, FOLDER_OTHER_ROOT, FOLDER_SUB, FOLDER_SUBSUB];

const GENERATED_FOLDERS = [
  activeFolder({ id: 41, name: 'Proyectos', slug: 'proyectos', parent: null, order: 10, document_count: 0, children_count: 1 }),
  activeFolder({ id: 42, name: 'Portal Nube', slug: 'portal-nube', parent: 41, order: 0, document_count: 0, children_count: 1 }),
  activeFolder({ id: 43, name: 'Cuentas de cobro', slug: 'cuentas-de-cobro-auto', parent: 42, order: 10, document_count: 0, children_count: 1 }),
  activeFolder({ id: 44, name: '2026', slug: 'cuentas-2026', parent: 43, order: 0, document_count: 0, children_count: 1 }),
  activeFolder({ id: 45, name: '08 - Agosto', slug: 'cuentas-2026-08', parent: 44, order: 8, document_count: 1, children_count: 0 }),
].map((folder) => ({ ...folder, is_system_managed: true }));

const GENERATED_ACCOUNT = {
  id: 401,
  title: '2026-08-14 · PA-2026-0042 · Soporte mensual',
  document_type_code: 'collection_account',
  commercial_status: 'issued',
  display_state: { key: 'sent', label: 'Enviada', variant: 'success' },
  active_states: [],
  folder: 45,
  folder_name: '08 - Agosto',
  project_name: 'Portal Nube',
  created_at: '2026-08-14T15:00:00Z',
};

const DOC_IN_ROOT = {
  id: 1, title: 'Doc En Raiz', status: 'published',
  client_name: 'ACME', created_at: '2026-04-01T10:00:00Z',
  folder: FOLDER_ROOT.id, folder_name: FOLDER_ROOT.name, tag_details: [],
};
const DOC_IN_SUB = {
  id: 2, title: 'Doc En Subcarpeta', status: 'draft',
  client_name: null, created_at: '2026-04-02T10:00:00Z',
  folder: FOLDER_SUB.id, folder_name: FOLDER_SUB.name, tag_details: [],
};

function jsonOk(body) {
  return { status: 200, contentType: 'application/json', body: JSON.stringify(body) };
}

const DOCS_IN_SUBSUB = Array.from({ length: FOLDER_SUBSUB.document_count }, (_, i) => ({
  id: 100 + i, title: `Doc Hondo ${i + 1}`, status: 'draft',
  client_name: null, created_at: '2026-04-03T10:00:00Z',
  folder: FOLDER_SUBSUB.id, folder_name: FOLDER_SUBSUB.name, tag_details: [],
}));

function documentsForFolder(folder) {
  if (folder === String(FOLDER_ROOT.id)) return [DOC_IN_ROOT];
  if (folder === String(FOLDER_SUB.id)) return [DOC_IN_SUB];
  if (folder === String(FOLDER_SUBSUB.id)) return DOCS_IN_SUBSUB;
  return [DOC_IN_ROOT, DOC_IN_SUB, ...DOCS_IN_SUBSUB];
}

async function openRootFolderFromDrawer(page) {
  await page.getByTestId('folder-drawer-trigger').click();
  await page.getByTestId('folder-drawer')
    .getByTestId('manual-folder-section')
    .getByRole('button', { name: /^Raiz A/ }).click();
}

function openRootFolderFromPanel(page) {
  return page.getByTestId('manual-folder-section')
    .getByRole('button', { name: /^Raiz A/ }).click();
}

const openRootFolderByProfile = Object.freeze({
  compact: openRootFolderFromDrawer,
  portrait: openRootFolderFromDrawer,
  landscape: openRootFolderFromPanel,
  desktop: openRootFolderFromPanel,
  wide: openRootFolderFromPanel,
});

test.describe('Admin Document Folder Hierarchy', () => {
  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 8701, role: 'admin', is_staff: true },
    });
  });

  function sidebar(page) {
    return page.getByTestId('manual-folder-section');
  }

  test('sidebar shows only root folders', {
    tag: [...ADMIN_DOCUMENT_FOLDER_HIERARCHY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'document-folders/') return jsonOk(ALL_FOLDERS);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath.startsWith('documents/')) {
        const u = new URL(route.request().url());
        return jsonOk(documentsForFolder(u.searchParams.get('folder')));
      }
      return null;
    });

    await page.goto('/panel/documents');
    await page.waitForLoadState('domcontentloaded');

    const bar = sidebar(page);
    await expect(bar.getByRole('button', { name: /^Raiz A/ })).toBeVisible();
    await expect(bar.getByRole('button', { name: /^Raiz B/ })).toBeVisible();
    // La subcarpeta no debe listarse en el sidebar.
    await expect(bar.getByRole('button', { name: /^Subcarpeta Uno/ })).toHaveCount(0);
  });

  test('a folder that organises into subfolders reports everything it holds', {
    tag: [...ADMIN_DOCUMENT_FOLDER_HIERARCHY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'document-folders/') return jsonOk(ALL_FOLDERS);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath.startsWith('documents/')) {
        const u = new URL(route.request().url());
        return jsonOk(documentsForFolder(u.searchParams.get('folder')));
      }
      return null;
    });

    // quality: allow-deep-link (lo que se verifica es el contador de la fila y
    // su desglose al entrar; la entrada por el sidebar la cubre el flujo del
    // módulo de documentos, y repetirla acá no agregaría cobertura.)
    await page.goto('/panel/documents');
    await page.waitForLoadState('domcontentloaded');

    // «Raiz A» sólo tiene 1 documento colgando directo, pero su rama guarda 6.
    // El contador decía 1 y dejaba a los otros 5 sin ninguna señal de dónde
    // estaban.
    const row = sidebar(page).getByRole('listitem').filter({ hasText: 'Raiz A' });
    await expect(row.getByTestId('folder-document-count')).toHaveText('6');
    await expect(row.getByTestId('folder-subfolder-count')).toHaveText('1');

    // Entrar es el desglose: el documento propio más la subcarpeta que declara
    // los otros 5 — la suma se puede verificar a ojo.
    await row.getByRole('button', { name: /^Raiz A/ }).click();

    const table = page.getByRole('table');
    await expect(table.getByText('Doc En Raiz')).toBeVisible();
    await expect(table.getByRole('row', { name: /Subcarpeta Uno/ }))
      .toContainText('5 documentos · 1 subcarpeta');
  });

  test('entering a folder reveals subfolder rows and the breadcrumb', {
    tag: [...ADMIN_DOCUMENT_FOLDER_HIERARCHY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    await mockApi(page, async ({ apiPath, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'document-folders/') return jsonOk(ALL_FOLDERS);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath.startsWith('documents/')) {
        const u = new URL(route.request().url());
        return jsonOk(documentsForFolder(u.searchParams.get('folder')));
      }
      return null;
    });

    await page.goto('/panel/documents');
    await page.waitForLoadState('domcontentloaded');

    await sidebar(page).getByRole('button', { name: /^Raiz A/ }).click();

    const breadcrumb = page.getByRole('navigation', { name: 'Ruta de carpetas' });
    await expect(breadcrumb).toBeVisible();
    await expect(breadcrumb.getByText('Raiz A')).toBeVisible();

    const table = page.getByRole('table');
    await expect(table.getByText('Subcarpeta Uno')).toBeVisible();
    await expect(table.getByText('Doc En Raiz')).toBeVisible();
  });

  test('navigates into a subfolder and back via the breadcrumb', {
    tag: [...ADMIN_DOCUMENT_FOLDER_HIERARCHY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    const requestedUrls = [];

    await mockApi(page, async ({ apiPath, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'document-folders/') return jsonOk(ALL_FOLDERS);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath.startsWith('documents/')) {
        const reqUrl = route.request().url();
        requestedUrls.push(reqUrl);
        const u = new URL(reqUrl);
        return jsonOk(documentsForFolder(u.searchParams.get('folder')));
      }
      return null;
    });

    await page.goto('/panel/documents');
    await page.waitForLoadState('domcontentloaded');

    // Entrar a la carpeta raíz, luego a la subcarpeta desde la tabla.
    await sidebar(page).getByRole('button', { name: /^Raiz A/ }).click();
    await page.getByRole('table').getByText('Subcarpeta Uno').click();

    await expect.poll(
      () => requestedUrls.some((u) => u.includes(`folder=${FOLDER_SUB.id}`)),
      { timeout: 5000 },
    ).toBe(true);

    const breadcrumb = page.getByRole('navigation', { name: 'Ruta de carpetas' });
    await expect(breadcrumb.getByText('Subcarpeta Uno')).toBeVisible();
    await expect(page.getByRole('table').getByText('Doc En Subcarpeta')).toBeVisible();

    // Volver a la carpeta raíz desde el breadcrumb.
    await breadcrumb.getByRole('button', { name: 'Raiz A' }).click();

    await expect.poll(
      () => requestedUrls.some((u) => u.includes(`folder=${FOLDER_ROOT.id}`)),
      { timeout: 5000 },
    ).toBe(true);

    await expect(page.getByRole('table').getByText('Doc En Raiz')).toBeVisible();
  });

  test('navigates the generated project and issue-month hierarchy', {
    tag: [...ADMIN_DOCUMENT_FOLDER_HIERARCHY, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the module entry; the test
    // exercises the hierarchy through its real folder-navigation controls)
    await mockApi(page, async ({ apiPath, route }) => {
      if (apiPath === 'auth/check/') return authCheck;
      if (apiPath === 'document-folders/') return jsonOk(GENERATED_FOLDERS);
      if (apiPath === 'document-tags/') return jsonOk([]);
      if (apiPath.startsWith('documents/')) {
        const folderId = new URL(route.request().url()).searchParams.get('folder');
        return jsonOk(folderId === '45' ? [GENERATED_ACCOUNT] : []);
      }
      return null;
    });
    await page.goto('/panel/documents');

    const root = sidebar(page).getByRole('listitem').filter({ hasText: 'Proyectos' });
    await expect(root.getByTestId('folder-edit')).toHaveCount(0);
    await expect(root.locator('.folder-drag-handle')).toHaveCount(0);
    await root.getByRole('button', { name: /^Proyectos/ }).click();
    await page.getByTestId('folder-open-42').click();
    await page.getByTestId('folder-open-43').click();
    await page.getByTestId('folder-open-44').click();
    await page.getByTestId('folder-open-45').click();

    await expect(page.getByRole('navigation', { name: 'Ruta de carpetas' }))
      .toContainText(/Proyectos[\s\S]*Portal Nube[\s\S]*Cuentas de cobro[\s\S]*2026[\s\S]*08 - Agosto/);
    await expect(page.getByText(GENERATED_ACCOUNT.title, { exact: true })).toBeVisible();
    await expect(page.getByText('Enviada', { exact: true }).first()).toBeVisible();
  });
});

for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
  test.describe(`Folder breadcrumb recovery — ${profile}`, { tag: [`@viewport:${profile}`] }, () => {
    test.use(viewportUse(profile));

    test(`returns to the chosen ancestor without clipping its breadcrumb target at ${profile}`, {
      // Bug this catches: a nested-folder breadcrumb is too small for touch or
      // no longer restores the ancestor selected by the administrator.
      tag: [...ADMIN_DOCUMENT_FOLDER_HIERARCHY, '@role:admin', '@outcome:success', '@responsive:documents'],
    }, async ({ page }) => {
      // quality: allow-duplicate (per-viewport contract: folder breadcrumb recovery)
      const requestedUrls = [];
      await mockApi(page, async ({ apiPath, route }) => {
        if (apiPath === 'auth/check/') return authCheck;
        if (apiPath === 'document-folders/') return jsonOk(ALL_FOLDERS);
        if (apiPath === 'document-tags/') return jsonOk([]);
        if (apiPath.startsWith('documents/')) {
          const requestUrl = route.request().url();
          requestedUrls.push(requestUrl);
          return jsonOk(documentsForFolder(new URL(requestUrl).searchParams.get('folder')));
        }
        return null;
      });

      await page.goto('/panel/documents', { waitUntil: 'domcontentloaded' });
      await openRootFolderByProfile[profile](page);
      await page.getByRole('link', { name: FOLDER_SUB.name, exact: true }).click();
      await page.getByRole('link', { name: FOLDER_SUBSUB.name, exact: true }).click();

      const breadcrumb = page.getByRole('navigation', { name: 'Ruta de carpetas' });
      const ancestor = breadcrumb.getByTestId(`folder-breadcrumb-${FOLDER_ROOT.id}`);
      await expect(ancestor).toHaveText(FOLDER_ROOT.name);
      const targetGeometry = await breadcrumb.getByRole('button').evaluateAll((elements) => elements.map((element) => ({
        declared: element.hasAttribute('data-responsive-touch-target'),
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
        width: element.getBoundingClientRect().width,
        height: element.getBoundingClientRect().height,
      })));
      const needsTouchTarget = ['compact', 'portrait', 'landscape'].includes(profile);
      expect(targetGeometry.every((target) => target.declared && target.scrollWidth <= target.clientWidth
        && (!needsTouchTarget || (target.width >= 43.5 && target.height >= 43.5)))).toBe(true);

      await ancestor.click();
      await expect.poll(() => requestedUrls.some((url) => url.includes(`folder=${FOLDER_ROOT.id}`))).toBe(true);
      await expect(page.getByText(DOC_IN_ROOT.title, { exact: true })).toBeVisible();
    });
  });
}
