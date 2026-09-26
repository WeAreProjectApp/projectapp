/**
 * E2E tests for the user-managed document state catalog.
 *
 * @flow:admin-document-states-manage
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { ADMIN_DOCUMENT_STATES_MANAGE } from '../helpers/flow-tags.js';

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const authCheck = json({ user: { username: 'admin', is_staff: true } });
const groups = [
  { id: 1, name: 'Ciclo', selection_mode: 'exclusive', order: 0, is_active: true, state_count: 4 },
  { id: 2, name: 'Señales', selection_mode: 'additive', order: 1, is_active: true, state_count: 4 },
];

function state(id, name, group, systemKey = '', overrides = {}) {
  const owner = groups.find((item) => item.id === group);
  return {
    id,
    name,
    slug: name.toLowerCase().replaceAll(' ', '-'),
    color: 'gray',
    system_key: systemKey,
    order: id,
    group,
    group_id: group,
    group_name: owner.name,
    group_mode: owner.selection_mode,
    group_order: owner.order,
    is_active: true,
    merged_into: null,
    incompatibility_ids: [],
    active_document_count: 0,
    historical_episode_count: 0,
    ...overrides,
  };
}

function initialStates() {
  return [
    state(10, 'Borrador', 1, 'draft', { color: 'gray', active_document_count: 3 }),
    state(11, 'Enviado', 1, 'sent', { color: 'blue', active_document_count: 2 }),
    state(12, 'En revisión', 1, 'in_review', { color: 'amber' }),
    state(13, 'Cerrado', 1, 'closed', { color: 'green' }),
    state(20, 'Solucionar bug', 2, 'needs_fix', { color: 'red', active_document_count: 2 }),
    state(21, 'Bug atendido', 2, 'bug_resolved', { color: 'green' }),
    state(22, 'Urgente', 2, '', { color: 'red', active_document_count: 2, historical_episode_count: 4 }),
    state(23, 'Prioritario', 2, '', { color: 'amber', historical_episode_count: 1 }),
  ];
}

function baseRoutes(apiPath, catalog) {
  if (apiPath === 'auth/check/') return authCheck;
  if (apiPath === 'documents/') return json([]);
  if (apiPath === 'documents/counts/') {
    return json({ documents: { active: 0, archived: 0 }, folders: { active: 0, archived: 0 } });
  }
  if (apiPath === 'document-folders/') return json([]);
  if (apiPath === 'document-states/') return json(catalog);
  if (apiPath === 'document-state-groups/') return json(groups);
  return null;
}

async function openCatalog(page) {
  await page.goto('/en-us/panel/documents', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('document-state-catalog-link').click();
  await expect(page.getByTestId('document-state-catalog')).toBeVisible();
}

async function expectInlineControlError(page, control, message) {
  await expect(control).toHaveAttribute('aria-invalid', 'true');
  const errorId = await control.getAttribute('aria-describedby');
  expect(errorId).toBeTruthy();
  await expect(page.locator(`[id="${errorId}"]`)).toHaveText(message);
}

test.describe('Admin Document States Manage', () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setAuthLocalStorage(page, {
      token: 'e2e-token',
      userAuth: { id: 8700, role: 'admin', is_staff: true },
    });
  });

  test('renders the seeded catalog inventory', {
    tag: [...ADMIN_DOCUMENT_STATES_MANAGE, '@role:admin', '@outcome:display'],
  }, async ({ page }) => {
    // quality: allow-deep-link (/panel/documents is the documented module entry; this test reaches the catalog through its visible administration link)
    const catalog = initialStates();
    await mockApi(page, async ({ apiPath }) => baseRoutes(apiPath, catalog));

    await openCatalog(page);

    await expect(page.getByRole('heading', { name: 'Estados de documentos' })).toBeVisible();
    await expect(page.getByTestId('catalog-group-1')).toContainText('Borrador');
    await expect(page.getByTestId('catalog-group-2')).toContainText('Solucionar bug');
    await expect(page.getByTestId('catalog-state-22')).toContainText('2 documentos activos · 4 episodios');
  });

  test('keeps catalog validation beside the incomplete fields', {
    tag: [...ADMIN_DOCUMENT_STATES_MANAGE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const catalog = initialStates();
    const writes = [];
    await mockApi(page, async ({ apiPath, method }) => {
      if (method === 'POST' && apiPath.startsWith('document-state')) writes.push(apiPath);
      return baseRoutes(apiPath, catalog);
    });
    await openCatalog(page);

    await page.getByTestId('catalog-create-state').click();
    await page.getByTestId('catalog-create-group').click();

    await expectInlineControlError(
      page,
      page.getByTestId('catalog-new-state-name'),
      'Escribe el nombre del estado.',
    );
    await expectInlineControlError(
      page,
      page.getByTestId('catalog-new-group-name'),
      'Escribe el nombre del grupo.',
    );
    expect(writes).toHaveLength(0);
  });

  test('creates a globally reusable state', {
    tag: [...ADMIN_DOCUMENT_STATES_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const catalog = initialStates();
    let createBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'document-states/' && method === 'POST') {
        createBody = route.request().postDataJSON();
        const created = state(24, createBody.name, Number(createBody.group), '', {
          color: createBody.color,
        });
        catalog.push(created);
        return json(created, 201);
      }
      return baseRoutes(apiPath, catalog);
    });
    await openCatalog(page);

    await page.getByTestId('catalog-new-state-name').fill('Esperando cliente');
    await page.getByLabel('Grupo del nuevo estado').selectOption('2');
    await page.getByLabel('Color del nuevo estado').selectOption('purple');
    await page.getByTestId('catalog-create-state').click();

    await expect.poll(() => createBody).not.toBeNull();
    expect(createBody).toMatchObject({ name: 'Esperando cliente', color: 'purple' });
    await expect(page.getByTestId('catalog-state-24')).toContainText('Esperando cliente');
  });

  test('persists state catalog metadata', {
    tag: [...ADMIN_DOCUMENT_STATES_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const catalog = initialStates();
    let updateBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'document-states/22/' && method === 'PATCH') {
        updateBody = route.request().postDataJSON();
        Object.assign(catalog.find((item) => item.id === 22), updateBody);
        return json(catalog.find((item) => item.id === 22));
      }
      return baseRoutes(apiPath, catalog);
    });
    await openCatalog(page);

    const row = page.getByTestId('catalog-state-22');
    await row.getByLabel('Nombre del estado').fill('Urgencia crítica');
    await row.locator('select').nth(0).selectOption('orange');
    await row.getByText('Combinaciones excluidas').click();
    await row.getByLabel('Cerrado').check();
    await page.getByTestId('catalog-save-state-22').click();

    await expect.poll(() => updateBody).not.toBeNull();
    expect(updateBody.name).toBe('Urgencia crítica');
    expect(updateBody.color).toBe('orange');
    expect(updateBody.incompatibility_ids).toContain(13);
  });

  test('merges a duplicate into an existing state', {
    tag: [...ADMIN_DOCUMENT_STATES_MANAGE, '@role:admin', '@outcome:success'],
  }, async ({ page }) => {
    const catalog = initialStates();
    let mergeBody = null;
    await mockApi(page, async ({ route, apiPath, method }) => {
      if (apiPath === 'document-states/23/merge/' && method === 'POST') {
        mergeBody = route.request().postDataJSON();
        const source = catalog.find((item) => item.id === 23);
        Object.assign(source, { is_active: false, merged_into: 22 });
        return json(source);
      }
      return baseRoutes(apiPath, catalog);
    });
    await openCatalog(page);

    await page.getByLabel('Destino para fusionar Prioritario').selectOption('22');
    await page.getByTestId('catalog-merge-state-23').click();
    await expect(page.getByRole('dialog')).toContainText('Fusionar estados');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect.poll(() => mergeBody).not.toBeNull();
    expect(mergeBody.target_state_id).toBe(22);
    await expect(page.getByRole('alert')).toContainText('Estados fusionados');
  });

  test('rejects retiring a state that is still active on documents', {
    tag: [...ADMIN_DOCUMENT_STATES_MANAGE, '@role:admin', '@outcome:error'],
  }, async ({ page }) => {
    const catalog = initialStates();
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'document-states/22/retire/' && method === 'POST') {
        return json({ detail: 'Cierra o fusiona primero sus episodios activos.', code: 'state_in_use' }, 409);
      }
      return baseRoutes(apiPath, catalog);
    });
    await openCatalog(page);

    await page.getByTestId('catalog-retire-state-22').click();
    await expect(page.getByRole('dialog')).toContainText('Retirar estado');
    await page.getByTestId('confirm-modal-confirm').click();

    await expect(page.getByRole('alert')).toContainText('No se puede retirar');
    await expect(page.getByRole('alert')).toContainText('Cierra o fusiona primero');
    await expect(page.getByTestId('catalog-state-22')).toContainText('Urgente');
  });

  test('keeps the edit draft after a server failure', {
    tag: [...ADMIN_DOCUMENT_STATES_MANAGE, '@role:admin', '@outcome:failure'],
  }, async ({ page }) => {
    const catalog = initialStates();
    await mockApi(page, async ({ apiPath, method }) => {
      if (apiPath === 'document-states/22/' && method === 'PATCH') {
        return json({ detail: 'El catálogo no está disponible.' }, 503);
      }
      return baseRoutes(apiPath, catalog);
    });
    await openCatalog(page);

    const name = page.getByTestId('catalog-state-22').getByLabel('Nombre del estado');
    await name.fill('Urgente hoy');
    await page.getByTestId('catalog-save-state-22').click();

    await expect(page.getByRole('alert')).toContainText('No se pudo actualizar');
    await expect(name).toHaveValue('Urgente hoy');
  });
});
