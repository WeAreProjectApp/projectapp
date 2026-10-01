/** Shared project actions and guarded permanent deletion. */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { openProjectAction } from '../helpers/projects.js';
import { waitForNuxtApp } from '../helpers/navigation.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(90_000);

function projectFixture() {
  return {
    id: 41, name: 'Proyecto de validación', description: '',
    status: 'development', status_label: 'En desarrollo',
    client: { profile_id: 12, name: 'Cliente de validación', company: '' },
    hostings_count: 0, incomes_count: 0,
    current_state: { id: 1, name: 'En desarrollo', color: 'blue', operational_effect: 'development' },
  };
}

const empty = () => ({ project: { id: 41, name: projectFixture().name }, can_delete: true, blockers: [] });
const blocked = () => ({
  project: { id: 41, name: projectFixture().name }, can_delete: false,
  blockers: [{ key: 'documents', label: 'Documentos', count: 3 }, { key: 'incomes', label: 'Ingresos', count: 2 }],
});
const json = (data, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(data) });

async function setup(page, options = {}) {
  let records = [projectFixture()];
  const calls = [];
  let loads = 0;
  let deletes = 0;
  await setAuthLocalStorage(page, { token: 'project-delete-test', userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true } });
  await mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'projects/') return json({ results: records, meta: { total: records.length, by_state: [], review_required: 0, clients_without_projects: 0, records_without_project: 0 } });
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/' || apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    if (apiPath === 'projects/41/delete-preview/') {
      loads += 1;
      if (options.failPreview && loads === 1) return json({ error: 'Dependencias temporalmente no disponibles' }, 503);
      return json(options.blocked ? blocked() : empty());
    }
    if (apiPath === 'projects/41/delete/' && method === 'DELETE') {
      calls.push(apiPath);
      deletes += 1;
      if (options.conflict) return json({ ...blocked(), code: 'project_delete_blocked', error: 'Se agregaron documentos al proyecto' }, 409);
      if (options.failDelete && deletes === 1) return json({ error: 'Eliminación temporalmente no disponible' }, 503);
      records = [];
      return { status: 204, body: '' };
    }
    return null;
  });
  return calls;
}

const enterByProfile = {
  compact: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Proyectos', exact: true }).click(); },
  portrait: async (page) => { await page.getByRole('button', { name: 'Abrir menú' }).click(); await page.getByRole('link', { name: 'Proyectos', exact: true }).click(); },
  desktop: (page) => page.getByRole('link', { name: 'Proyectos', exact: true }).click(),
};

const assertLayout = {
  compact: (page) => expect(page.getByTestId('project-card-41')).toContainText(projectFixture().name),
  portrait: (page) => expect(page.getByTestId('project-card-41')).toContainText(projectFixture().name),
  desktop: async (page) => {
    const header = page.getByRole('columnheader').first();
    await expect(header).toHaveAttribute('data-testid', 'accounting-actions-header');
    await expect(header).toHaveText('');
    await expect(page.getByRole('columnheader').nth(1)).toContainText('Proyecto');
  },
};

// quality: allow-deep-link (panel home is the authenticated shell entry; Projects is reached through visible navigation)
async function enter(page, profile) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  await waitForNuxtApp(page);
  await enterByProfile[profile](page);
  await expect(page).toHaveURL(/\/panel\/projects$/);
  await expect(page.getByTestId('project-actions-41')).toBeVisible();
}

for (const profile of ['compact', 'portrait', 'desktop']) {
  test.describe(`project deletion · ${profile}`, () => {
    test.use(viewportUse(profile));

    test('opens project actions from the leading kebab', { tag: ['@flow:admin-project-actions-menu', '@outcome:display'] }, async ({ page }) => {
      // quality: allow-deep-link (the panel home is the authenticated shell entry; the visible Projects link is exercised)
      await setup(page);
      await enter(page, profile);
      await assertLayout[profile](page);

      await page.getByTestId('project-actions-41').click();

      const menu = page.getByTestId('project-actions-modal');
      await expect(menu).toContainText(projectFixture().name);
      await expect(menu.getByTestId('project-actions-space')).toContainText('Abrir espacio');
      await expect(menu.getByTestId('project-actions-delete')).toContainText('Eliminar proyecto');
      await page.keyboard.press('Escape');
      await expect(menu).toBeHidden();
      await expect(page.getByTestId('project-actions-41')).toBeFocused();
    });

    test('deletes an unused project after confirmation', { tag: ['@flow:admin-project-delete', '@outcome:success'] }, async ({ page }) => {
      const calls = await setup(page);
      await enter(page, profile);

      await openProjectAction(page, 41, 'delete');
      await expect(page.getByTestId('project-delete-warning')).toContainText('No se puede deshacer');
      await page.getByTestId('project-delete-confirm').click();

      await expect(page.getByTestId('project-delete-modal')).toBeHidden();
      await expect(page.getByTestId('project-actions-41')).toBeHidden();
      await expect(page.getByText('Proyecto eliminado', { exact: true })).toBeVisible();
      expect(calls).toHaveLength(1);
    });

    test('lists the dependencies preventing deletion', { tag: ['@flow:admin-project-delete', '@outcome:error'] }, async ({ page }) => {
      const calls = await setup(page, { blocked: true });
      await enter(page, profile);

      await openProjectAction(page, 41, 'delete');

      const table = page.getByTestId('project-delete-dependencies');
      await expect(table.getByRole('row', { name: 'Documentos 3', exact: true })).toBeVisible();
      await expect(table.getByRole('row', { name: 'Ingresos 2', exact: true })).toBeVisible();
      await expect(page.getByTestId('project-delete-confirm')).toHaveCount(0);
      await page.getByTestId('project-delete-change-state').click();
      await expect(page.getByTestId('project-state-transition-modal')).toBeVisible();
      expect(calls).toEqual([]);
    });
  });
}

test('cancels deletion without sending a delete request', { tag: ['@flow:admin-project-delete', '@outcome:success'] }, async ({ page }) => {
  const calls = await setup(page);
  await enter(page, 'desktop');
  await openProjectAction(page, 41, 'delete');

  await page.getByTestId('project-delete-modal').getByRole('button', { name: 'Cancelar', exact: true }).click();

  await expect(page.getByTestId('project-actions-41')).toBeVisible();
  expect(calls).toEqual([]);
});

test('retries a failed dependency preview', { tag: ['@flow:admin-project-delete', '@outcome:failure'] }, async ({ page }) => {
  await setup(page, { failPreview: true });
  await enter(page, 'desktop');
  await openProjectAction(page, 41, 'delete');
  await expect(page.getByTestId('project-delete-error')).toHaveText('Dependencias temporalmente no disponibles');

  await page.getByTestId('project-delete-retry').click();

  await expect(page.getByTestId('project-delete-confirm')).toBeVisible();
  await expect(page.getByTestId('project-delete-error')).toHaveCount(0);
});

test('retries a failed deletion while retaining the project', { tag: ['@flow:admin-project-delete', '@outcome:failure'] }, async ({ page }) => {
  await setup(page, { failDelete: true });
  await enter(page, 'desktop');
  await openProjectAction(page, 41, 'delete');
  await page.getByTestId('project-delete-confirm').click();
  await expect(page.getByTestId('project-delete-error')).toHaveText('Eliminación temporalmente no disponible');

  await page.getByTestId('project-delete-confirm').click();

  await expect(page.getByTestId('project-delete-modal')).toBeHidden();
  await expect(page.getByTestId('project-actions-41')).toHaveCount(0);
});

test('shows dependencies added after preview', { tag: ['@flow:admin-project-delete', '@outcome:error'] }, async ({ page }) => {
  await setup(page, { conflict: true });
  await enter(page, 'desktop');
  await openProjectAction(page, 41, 'delete');

  await page.getByTestId('project-delete-confirm').click();

  await expect(page.getByTestId('project-delete-dependencies')).toContainText('Documentos');
  await expect(page.getByTestId('project-delete-confirm')).toHaveCount(0);
  await expect(page.getByTestId('project-actions-41')).toBeVisible();
});
