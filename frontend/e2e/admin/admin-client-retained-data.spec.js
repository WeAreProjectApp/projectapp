/**
 * E2E coverage for the read-only consultation of data kept after a project is deleted.
 *
 * The assertions catch a client-detail button that cannot reach the retained records,
 * preloads records before the operator chooses a category, or turns consultation into
 * a mutation endpoint.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { PANEL_BREAKPOINTS } from '../../config/responsive.js';

test.setTimeout(60_000);

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const client = {
  id: 301,
  name: 'Laura Datos Conservados',
  email: 'laura@example.test',
  phone: '',
  company: 'Laura Estudio',
  is_onboarded: true,
  is_email_placeholder: false,
  total_proposals: 0,
  projects_count: 0,
  diagnostics_count: 0,
  is_orphan: false,
  is_archived: false,
  created_at: '2026-09-01T10:00:00Z',
  updated_at: '2026-10-01T10:00:00Z',
};

const retainedContexts = {
  contexts: [{
    id: 71,
    project_name: 'Portal histórico de Laura',
    categories: [{
      key: 'documents',
      label: 'Documentos',
      description: 'Documentos guardados en el proyecto eliminado.',
      count: 1,
    }],
  }],
};

function retainedRecords() {
  return {
    count: 1,
    results: [{
      id: 'document-11',
      key: 'documents',
      title: 'Acta de cierre',
      fields: { title: 'Acta de cierre', status: 'Firmado' },
      files: [],
      can_reveal: false,
    }],
  };
}

async function setup(page, { contexts = retainedContexts, contextsStatus = 200, categoryStatus = 200 } = {}) {
  const state = { contextReads: 0, categoryReads: 0, writes: [] };
  await setAuthLocalStorage(page, {
    token: 'retained-data-admin-token',
    userAuth: { id: 9300, role: 'admin', is_staff: true },
  });
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (method !== 'GET') state.writes.push({ apiPath, method });
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true } });
    if (apiPath === 'proposals/client-profiles/status-counts/') return json({ all: 1, active: 1, orphans: 0, archived: 0 });
    if (apiPath === 'proposals/client-profiles/') return json([client]);
    if (apiPath === 'proposals/client-profiles/301/') {
      return json({ ...client, proposals: [], projects: [], diagnostics: [], hostings: [], incomes: [], documents: [] });
    }
    if (apiPath === 'proposals/client-profiles/301/retained-project-data/' && method === 'GET') {
      const query = new URL(route.request().url()).searchParams;
      if (!query.get('category')) {
        state.contextReads += 1;
        return json(contexts, contextsStatus);
      }
      state.categoryReads += 1;
      return json(retainedRecords(), categoryStatus);
    }
    if (apiPath === 'projects/' || apiPath === 'project-states/' || apiPath === 'project-state-groups/') return json([]);
    return null;
  });
  return state;
}

async function enterClients(page) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  if (page.viewportSize().width < PANEL_BREAKPOINTS.landscape) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
  }
  const clientsLink = page.getByRole('link', { name: 'Clientes', exact: true });
  await expect(clientsLink).toBeVisible();
  await expect(clientsLink).toHaveAttribute('href', '/es-co/panel/clients');
  await Promise.all([
    page.waitForURL(/\/panel\/clients$/),
    clientsLink.click(),
  ]);
  await expect(page.getByTestId('client-header-301')).toContainText('Laura Datos Conservados');
  await page.getByTestId('client-header-301').click();
  await expect(page.getByTestId('client-retained-data-301')).toHaveText('Datos sin proyecto');
}

test('opens a client consultation with the retained-project provenance before reading records', {
  tag: ['@flow:admin-client-retained-data', '@outcome:display'],
}, async ({ page }) => {
  // quality: allow-deep-link (starts at the panel shell and navigates through the visible Clientes link)
  // Bug caught: the retained-data action is unreachable, lacks provenance, or eagerly reads retained records.
  const state = await setup(page);
  await enterClients(page);

  await page.getByTestId('client-retained-data-301').click();
  const modal = page.getByTestId('client-retained-project-data');
  await expect(modal).toContainText('Portal histórico de Laura');
  await expect(modal).toContainText('Nombre del proyecto de origen, ya eliminado.');
  await expect(page.getByTestId('retained-category-documents')).toHaveText('Documentos (1)');
  expect(state.contextReads).toBe(1);
  expect(state.categoryReads).toBe(0);
  expect(state.writes).toEqual([]);
});

test('returns from a retained-data category to the original-project list without changing the client', {
  tag: ['@flow:admin-client-retained-data', '@outcome:display'],
}, async ({ page }) => {
  // quality: allow-deep-link (starts at the panel shell and navigates through the visible Clientes link)
  // Bug caught: selecting a retained category does not show its safe fields or changes the client while navigating back.
  const state = await setup(page);
  await enterClients(page);

  await page.getByTestId('client-retained-data-301').click();
  await page.getByTestId('retained-category-documents').click();
  await expect(page.getByTestId('retained-data-record')).toContainText('Acta de cierre');
  await expect(page.getByTestId('retained-data-record')).toContainText('Firmado');
  expect(state.categoryReads).toBe(1);
  await page.getByRole('button', { name: 'Volver a los proyectos de origen', exact: true }).click();
  await expect(page.getByTestId('client-retained-project-data')).toContainText('Portal histórico de Laura');
  await page.getByRole('button', { name: 'Cerrar', exact: true }).click();
  await expect(page.getByTestId('client-header-301')).toContainText('Laura Datos Conservados');
  expect(state.writes).toEqual([]);
});

test('shows the empty retained-data result without issuing a mutation', {
  tag: ['@flow:admin-client-retained-data', '@outcome:display'],
}, async ({ page }) => {
  // quality: allow-deep-link (starts at the panel shell and navigates through the visible Clientes link)
  // Bug caught: an empty consultation hides its state or performs an unrelated write while opening.
  const state = await setup(page, { contexts: { contexts: [] } });
  await enterClients(page);

  await page.getByTestId('client-retained-data-301').click();
  await expect(page.getByTestId('retained-data-empty')).toHaveText(
    'Este cliente no tiene datos conservados de proyectos eliminados.',
  );
  expect(state.contextReads).toBe(1);
  expect(state.categoryReads).toBe(0);
  expect(state.writes).toEqual([]);
});

test('keeps the consultation read-only when the retained-record service rejects access', {
  tag: ['@flow:admin-client-retained-data', '@outcome:error'],
}, async ({ page }) => {
  // Bug caught: a failed category read leaves stale records visible or retries through a write endpoint.
  const state = await setup(page, { categoryStatus: 403 });
  await enterClients(page);

  await page.getByTestId('client-retained-data-301').click();
  await page.getByTestId('retained-category-documents').click();
  await expect(page.getByRole('alert')).toHaveText(
    'No se pudieron cargar los datos. Cierra y vuelve a abrir la consulta para reintentar.',
  );
  await expect(page.getByTestId('retained-data-record')).toHaveCount(0);
  expect(state.categoryReads).toBe(1);
  expect(state.writes).toEqual([]);
});

test('shows a failure when the retained-project service cannot load the consultation', {
  tag: ['@flow:admin-client-retained-data', '@outcome:failure'],
}, async ({ page }) => {
  // Bug caught: a service outage opens an empty-looking consultation that suggests retained data was deleted.
  const state = await setup(page, { contextsStatus: 500 });
  await enterClients(page);

  await page.getByTestId('client-retained-data-301').click();
  await expect(page.getByRole('alert')).toHaveText(
    'No se pudieron cargar los datos. Cierra y vuelve a abrir la consulta para reintentar.',
  );
  await expect(page.getByTestId('retained-data-empty')).toHaveCount(0);
  await expect(page.getByTestId('retained-category-documents')).toHaveCount(0);
  expect(state.contextReads).toBe(1);
  expect(state.writes).toEqual([]);
});
