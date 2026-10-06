/**
 * E2E coverage for the superuser-only forced project-deletion path.
 *
 * @flow:admin-project-delete
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import { openProjectAction } from '../helpers/projects.js';
import { viewportUse } from '../helpers/viewports.js';

test.setTimeout(60_000);

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const forceImpactToken = (keys = []) => `force-impact-${[...keys].sort().join('-') || 'none'}`;

function projectFixture() {
  return {
    id: 41,
    name: 'Proyecto de eliminación forzada',
    description: '',
    status: 'development',
    status_label: 'En desarrollo',
    client: { profile_id: 12, name: 'Cliente de validación', company: '' },
    hostings_count: 0,
    incomes_count: 0,
    current_state: {
      id: 1,
      name: 'En desarrollo',
      color: 'blue',
      operational_effect: 'development',
    },
  };
}

const stateCatalog = () => [
  projectFixture().current_state,
  {
    id: 2,
    name: 'Suspendido',
    description: 'El servicio puede reactivarse.',
    color: 'orange',
    operational_effect: 'suspended',
    is_active: true,
  },
];

const regularPreview = () => ({
  project: { id: 41, name: projectFixture().name },
  can_delete: false,
  blockers: [{ key: 'documents', label: 'Documentos', count: 3 }],
});

const forcedDependencies = () => [
  {
    key: 'documents', label: 'Documentos', count: 3,
    description: 'Documentos guardados en este proyecto.',
  },
  {
    key: 'document_files', label: 'Archivos de documentos', count: 2,
    description: 'Archivos vinculados a los documentos del proyecto.',
  },
];

const forcedPreview = (deleteKeys = [], overrides = {}) => {
  const blockers = deleteKeys.includes('documents') && !deleteKeys.includes('document_files')
    ? [{ message: 'Para eliminar Documentos, también debes seleccionar Archivos de documentos.' }]
    : [];
  return {
    project: { id: 41, name: projectFixture().name },
    can_delete: blockers.length === 0,
    dependencies: forcedDependencies(),
    blockers,
    impact_token: forceImpactToken(deleteKeys),
    delete_keys: deleteKeys,
    ...overrides,
  };
};

async function setup(page, options = {}) {
  let records = [projectFixture()];
  const calls = { deletes: [], forcePreviews: [], transitionApplies: 0 };
  let forcedPreviewAttempts = 0;
  await setAuthLocalStorage(page, {
    token: 'project-force-delete-test',
    userAuth: {
      id: 9001,
      role: 'admin',
      is_staff: true,
      is_superuser: options.isSuperuser !== false,
    },
  });
  await mockApi(page, async ({ route, apiPath, method }) => {
    if (apiPath === 'auth/check/') {
      return json({
        user: {
          username: options.isSuperuser === false ? 'admin' : 'superadmin',
          is_staff: true,
          is_superuser: options.isSuperuser !== false,
        },
      });
    }
    if (apiPath === 'projects/' && method === 'GET') {
      return json({
        results: records,
        meta: {
          total: records.length,
          by_state: [],
          review_required: 0,
          clients_without_projects: 0,
          records_without_project: 0,
        },
      });
    }
    if (apiPath === 'project-states/' && method === 'GET') return json(stateCatalog());
    if (apiPath === 'project-state-groups/' || apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    if (apiPath === 'projects/41/delete-preview/' && method === 'POST') {
        const deleteKeys = route.request().postDataJSON()?.delete_keys || [];
        calls.forcePreviews.push(deleteKeys);
        forcedPreviewAttempts += 1;
        if (options.failForcePreview && forcedPreviewAttempts === 1) {
          return json({ error: 'No se pudo revisar las dependencias forzadas' }, 503);
        }
        return json(forcedPreview(deleteKeys, options.forcePreview));
    }
    if (apiPath === 'projects/41/delete-preview/' && method === 'GET') {
      return json(regularPreview());
    }
    if (apiPath === 'projects/41/delete/' && method === 'DELETE') {
      calls.deletes.push(route.request().postDataJSON());
      if (options.staleForcePreview) {
        return json({
          ...forcedPreview([], {
            can_delete: false,
            blockers: [{ message: 'Se agregaron datos compartidos al proyecto.' }],
          }),
          code: 'stale_project_delete_preview',
          error: 'La vista previa cambió; revisa las dependencias de nuevo.',
        }, 409);
      }
      if (options.failForceDeletion) {
        return json({ error: 'La eliminación forzada no se pudo completar' }, 503);
      }
      records = [];
      return { status: 204, body: '' };
    }
    if (apiPath === 'projects/41/state-transitions/' && method === 'POST') {
      calls.transitionApplies += 1;
      return json({ project: projectFixture() });
    }
    return null;
  });
  return calls;
}

async function enterProjects(page, profile) {
  await page.goto('/es-co/panel', { waitUntil: 'domcontentloaded' });
  if (['compact', 'portrait'].includes(profile)) {
    await page.getByRole('button', { name: 'Abrir menú' }).click();
  }
  await page.getByRole('link', { name: 'Proyectos', exact: true }).click();
  await expect(page).toHaveURL(/\/panel\/projects$/);
  await expect(page.getByTestId('project-actions-41')).toBeVisible();
}

async function openBlockedDeletion(page) {
  await openProjectAction(page, 41, 'delete');
  await expect(page.getByTestId('project-delete-dependencies')).toContainText('Documentos');
}

async function openForcedDeletion(page) {
  await openBlockedDeletion(page);
  await page.getByTestId('project-delete-change-state').click();
  await expect(page.getByTestId('project-state-transition-modal')).toBeVisible();
  await page.getByTestId('project-force-delete-toggle').click();
  await expect(page.getByTestId('project-force-delete-review')).toContainText('Documentos');
}

async function expectNoHorizontalOverflow(page, locator) {
  await expect(locator).toBeVisible();
  await expect.poll(() => locator.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await expect.poll(() => page.evaluate(() => (
    document.documentElement.scrollWidth <= document.documentElement.clientWidth
  ))).toBe(true);
}

for (const profile of ['compact', 'portrait', 'landscape', 'desktop', 'wide']) {
  test.describe(`blocked project deletion @ ${profile}`, { tag: ['@viewport:' + profile] }, () => {
    test.use(viewportUse(profile));

    test('keeps the full state-change label and opens the state modal without deleting', {
      tag: ['@flow:admin-project-delete', '@outcome:error'],
    }, async ({ page }) => {
      // quality: allow-duplicate (per-viewport contract: admin-project-delete @ responsive width)
      // Bug caught: a narrow delete modal truncates Cambiar estado or submits deletion from the blocked path.
      const calls = await setup(page);
      await enterProjects(page, profile);
      await openBlockedDeletion(page);

      const changeState = page.getByTestId('project-delete-change-state');
      await expect(changeState).toHaveText('Cambiar estado');
      await expectNoHorizontalOverflow(page, changeState);
      await changeState.click();

      await expect(page.getByRole('heading', { name: 'Cambiar estado', exact: true })).toBeVisible();
      expect(calls.deletes).toEqual([]);
    });
  });
}

test('keeps forced deletion unavailable when normal state change does not originate in deletion', {
  tag: ['@flow:admin-project-delete', '@outcome:success'],
}, async ({ page }) => {
  // Bug caught: ordinary state changes accidentally expose a destructive forced-deletion toggle.
  await setup(page);
  await enterProjects(page, 'desktop');

  await openProjectAction(page, 41, 'state');

  await expect(page.getByRole('heading', { name: 'Cambiar estado', exact: true })).toBeVisible();
  await expect(page.getByTestId('project-force-delete-toggle')).toHaveCount(0);
  await expect(page.getByTestId('project-state-target')).toHaveValue('');
});

test('keeps forced deletion unavailable to an ordinary admin from the blocked delete route', {
  tag: ['@flow:admin-project-delete', '@outcome:error'],
}, async ({ page }) => {
  // Bug caught: a non-superuser can reach permanent deletion through the otherwise safe state route.
  await setup(page, { isSuperuser: false });
  await enterProjects(page, 'desktop');
  await openBlockedDeletion(page);

  await page.getByTestId('project-delete-change-state').click();

  await expect(page.getByRole('heading', { name: 'Cambiar estado', exact: true })).toBeVisible();
  await expect(page.getByTestId('project-force-delete-toggle')).toHaveCount(0);
});

test('requires exact DELETE and sends one forced deletion request instead of a state transition', {
  tag: ['@flow:admin-project-delete', '@outcome:success'],
}, async ({ page }) => {
  // Bug caught: the force route accepts a loose confirmation, changes state, or drops the impact token.
  const calls = await setup(page);
  await enterProjects(page, 'desktop');
  await openForcedDeletion(page);

  const confirmation = page.getByTestId('project-force-delete-confirmation');
  const confirm = page.getByTestId('project-force-delete-confirm');
  await confirmation.fill('delete');
  await expect(confirm).toBeDisabled();
  await confirmation.fill('DELETE');
  await expect(confirm).toBeEnabled();
  await confirm.click();

  await expect(page.getByTestId('project-state-transition-modal')).toBeHidden();
  await expect(page.getByTestId('project-actions-41')).toHaveCount(0);
  await expect(page.getByText('Proyecto eliminado', { exact: true })).toBeVisible();
  expect(calls.forcePreviews).toEqual([[]]);
  expect(calls.deletes).toEqual([{
    force: true,
    delete_keys: [],
    confirmation: 'DELETE',
    impact_token: forceImpactToken(),
  }]);
  expect(calls.transitionApplies).toBe(0);
});

test('requires manual selection of dependent data before deleting exactly the reviewed categories', {
  tag: ['@flow:admin-project-delete', '@outcome:success'],
}, async ({ page }) => {
  // Bug caught: forced deletion starts armed, silently enables a dependency, or sends keys from an older review.
  const calls = await setup(page);
  await enterProjects(page, 'desktop');
  await openForcedDeletion(page);

  const documents = page.getByTestId('project-delete-category-documents');
  const files = page.getByTestId('project-delete-category-document_files');
  await expect(documents).toHaveAttribute('aria-checked', 'false');
  await expect(files).toHaveAttribute('aria-checked', 'false');
  await expect(page.getByTestId('project-force-delete-dependencies')).toContainText('Se conserva sin proyecto');

  await documents.click();
  await expect(documents).toHaveAttribute('aria-checked', 'true');
  await expect(files).toHaveAttribute('aria-checked', 'false');
  await expect(page.getByTestId('project-force-delete-blockers')).toContainText(
    'también debes seleccionar Archivos de documentos',
  );
  await page.getByTestId('project-force-delete-confirmation').fill('DELETE');
  await expect(page.getByTestId('project-force-delete-confirm')).toBeDisabled();

  await files.click();
  await expect(page.getByTestId('project-force-delete-blockers')).toHaveCount(0);
  await expect(page.getByTestId('project-force-delete-confirmation')).toHaveValue('');
  await page.getByTestId('project-force-delete-confirmation').fill('DELETE');
  await page.getByTestId('project-force-delete-confirm').click();

  await expect(page.getByTestId('project-actions-41')).toHaveCount(0);
  expect(calls.forcePreviews).toEqual([[], ['documents'], ['documents', 'document_files']]);
  expect(calls.deletes).toEqual([{
    force: true,
    delete_keys: ['documents', 'document_files'],
    confirmation: 'DELETE',
    impact_token: forceImpactToken(['documents', 'document_files']),
  }]);
});

test('clears confirmation and keeps the project visible when the force preview becomes stale', {
  tag: ['@flow:admin-project-delete', '@outcome:error'],
}, async ({ page }) => {
  // Bug caught: a stale dependency graph lets an old DELETE confirmation erase new shared data.
  const calls = await setup(page, { staleForcePreview: true });
  await enterProjects(page, 'desktop');
  await openForcedDeletion(page);

  const confirmation = page.getByTestId('project-force-delete-confirmation');
  await confirmation.fill('DELETE');
  await page.getByTestId('project-force-delete-confirm').click();

  await expect(page.getByTestId('project-force-delete-error')).toHaveText(
    'La vista previa cambió; revisa las dependencias de nuevo.',
  );
  await expect(confirmation).toHaveValue('');
  await expect(page.getByTestId('project-force-delete-blockers')).toContainText('Se agregaron datos compartidos');
  await expect(page.getByTestId('project-actions-41')).toBeVisible();
  expect(calls.deletes).toHaveLength(1);
});

test('retries a failed forced preview without deleting the project', {
  tag: ['@flow:admin-project-delete', '@outcome:failure'],
}, async ({ page }) => {
  // Bug caught: a force-preview outage hides the retry path or silently submits a deletion.
  const calls = await setup(page, { failForcePreview: true });
  await enterProjects(page, 'desktop');
  await openBlockedDeletion(page);
  await page.getByTestId('project-delete-change-state').click();
  await page.getByTestId('project-force-delete-toggle').click();

  await expect(page.getByTestId('project-force-delete-error')).toHaveText('No se pudo revisar las dependencias forzadas');
  await page.getByTestId('project-force-delete-retry').click();

  await expect(page.getByTestId('project-force-delete-dependencies')).toContainText('Documentos');
  expect(calls.forcePreviews).toEqual([[], []]);
  expect(calls.deletes).toEqual([]);
});

test('cancels forced deletion without issuing a destructive request', {
  tag: ['@flow:admin-project-delete', '@outcome:success'],
}, async ({ page }) => {
  // Bug caught: cancelling the force review leaves an armed delete request or removes the project locally.
  const calls = await setup(page);
  await enterProjects(page, 'desktop');
  await openForcedDeletion(page);

  await page.getByRole('dialog', { name: 'Cambiar estado', exact: true })
    .getByRole('button', { name: 'Cancelar', exact: true })
    .click();

  await expect(page.getByTestId('project-state-transition-modal')).toBeHidden();
  await expect(page.getByTestId('project-actions-41')).toBeVisible();
  expect(calls.deletes).toEqual([]);
});
