import { openProjectAction } from '../helpers/projects.js';
/**
 * Secure project URLs, credentials, and notes from the Projects module.
 *
 * @flow:admin-project-access-detail
 * @flow:admin-project-access-field-edit
 * @flow:admin-project-access-secrets
 * @flow:admin-project-access-notes
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { setAuthLocalStorage } from '../helpers/auth.js';
import {
  ADMIN_PROJECT_ACCESS_DETAIL,
  ADMIN_PROJECT_ACCESS_FIELD_EDIT,
  ADMIN_PROJECT_ACCESS_NOTES,
  ADMIN_PROJECT_ACCESS_SECRETS,
} from '../helpers/flow-tags.js';

test.setTimeout(60_000);

const PROJECT = {
  id: 1,
  name: 'Kore Health',
  description: 'Clinical platform',
  status: 'active',
  status_label: 'Activo',
  client: { profile_id: 5, name: 'Germán Franco', company: 'Kore' },
  hostings_count: 1,
  incomes_count: 2,
};

const ACCESS_DETAIL = {
  project: { id: 1, name: 'Kore Health', client_name: 'Germán Franco' },
  repository_url: 'https://git.example.test/kore/health',
  environments: [
    {
      environment: 'production',
      label: 'Producción',
      site_url: 'https://kore.example.test',
      admin_url: 'https://kore.example.test/admin/',
      admin_username: 'prod-admin',
      has_password: true,
      updated_by: 'Admin E2E',
    },
    {
      environment: 'staging',
      label: 'Staging',
      site_url: 'https://staging.kore.example.test',
      admin_url: 'https://staging.kore.example.test/admin/',
      admin_username: 'stage-admin',
      has_password: true,
      updated_by: 'Admin E2E',
    },
  ],
  notes: [
    { id: 11, title: 'Deployment owner', content: 'Operations team', has_content: true, is_sensitive: false, updated_by: 'Admin E2E' },
    { id: 12, title: 'Recovery token', content: '', has_content: true, is_sensitive: true, updated_by: 'Admin E2E' },
  ],
  legacy_access: null,
};

const json = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

async function setupProjectAccess(page, options = {}) {
  const calls = [];
  let detail = structuredClone(ACCESS_DETAIL);
  let detailLoads = 0;
  await mockApi(page, async ({ apiPath, method, route: requestRoute }) => {
    if (apiPath === 'auth/check/') return json({ user: { username: 'admin', is_staff: true, is_superuser: true } });
    if (apiPath === 'project-states/' || apiPath === 'project-state-groups/' || apiPath.startsWith('accounts/saved-filter-tabs')) return json([]);
    if (apiPath === 'projects/1/access/' && method === 'GET') {
      detailLoads += 1;
      if (options.failFirstLoad && detailLoads === 1) return json({ error: 'Access service unavailable.' }, 503);
      return json(detail);
    }
    if (apiPath === 'projects/1/access/' && method === 'PATCH') {
      const body = requestRoute.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (options.patchStatus) return json(options.patchBody || { error: 'Access update unavailable.' }, options.patchStatus);
      if (body.repository_url !== undefined) detail.repository_url = body.repository_url;
      const environment = detail.environments.find((item) => item.environment === body.environment);
      if (environment) Object.keys(body).filter((key) => key !== 'environment').forEach((key) => { environment[key] = body[key]; });
      return json(detail);
    }
    if (/projects\/1\/access\/environments\/\w+\/password\/reveal\/$/.test(apiPath) && method === 'POST') {
      if (options.revealStatus) return json({ error: 'Secret service unavailable.' }, options.revealStatus);
      return json({ secret: 'e2e-password-secret' });
    }
    if (apiPath === 'projects/1/access/notes/' && method === 'POST') {
      const body = requestRoute.request().postDataJSON();
      calls.push({ apiPath, method, body });
      if (options.noteStatus) return json({ error: 'Notes service unavailable.' }, options.noteStatus);
      detail.notes.unshift({ id: 21, ...body, content: body.is_sensitive ? '' : body.content, has_content: true, updated_by: 'Admin E2E' });
      return json(detail, 201);
    }
    if (apiPath === 'projects/1/access/notes/12/reveal/' && method === 'POST') return json({ secret: 'e2e-note-secret' });
    if (apiPath === 'projects/' && method === 'GET') return json({ results: [PROJECT], meta: { total: 1, by_state: [], review_required: 0, clients_without_projects: 0, records_without_project: 0 } });
    return null;
  });
  return { calls };
}

async function openAccessModal(page) {
  await page.goto('/panel', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Proyectos', exact: true }).click();
  await expect(page.getByTestId('accounting-row-1')).toBeVisible({ timeout: 25_000 });
  await openProjectAction(page, 1, 'detail');
  await expect(page.getByTestId('project-access-modal')).toBeVisible({ timeout: 25_000 });
  await expect(page.getByTestId('project-access-loading')).toHaveCount(0);
}

test.beforeEach(async ({ page }) => {
  await setAuthLocalStorage(page, {
    token: 'project-access-token',
    userAuth: { id: 9001, role: 'admin', is_staff: true, is_superuser: true },
  });
});

test('opens the project detail modal with both environments and masked secrets', {
  tag: ['@outcome:display', ...ADMIN_PROJECT_ACCESS_DETAIL, ...ADMIN_PROJECT_ACCESS_SECRETS, ...ADMIN_PROJECT_ACCESS_NOTES],
}, async ({ page }) => {
  await setupProjectAccess(page);
  await openAccessModal(page);

  const modal = page.getByTestId('project-access-modal');
  await expect(modal).toContainText('https://kore.example.test');
  await expect(modal).toContainText('https://staging.kore.example.test');
  await expect(modal).toContainText('Deployment owner');
  await expect(modal).toContainText('Recovery token');
  await expect(modal).toContainText('••••••••••••');
  await expect(modal).not.toContainText('e2e-password-secret');
});

test('recovers the modal after the detail request fails', {
  tag: ['@outcome:failure', ...ADMIN_PROJECT_ACCESS_DETAIL],
}, async ({ page }) => {
  await setupProjectAccess(page, { failFirstLoad: true });
  await openAccessModal(page);

  await expect(page.getByTestId('project-access-load-error')).toBeVisible();
  await page.getByTestId('project-access-load-error').getByRole('button').click();
  await expect(page.getByTestId('project-access-value-production-site_url'))
    .toHaveText('https://kore.example.test');
});

test('saves one environment URL and renders the returned value', {
  tag: ['@outcome:success', ...ADMIN_PROJECT_ACCESS_FIELD_EDIT],
}, async ({ page }) => {
  const { calls } = await setupProjectAccess(page);
  await openAccessModal(page);

  await page.getByTestId('project-access-edit-staging-site_url').click();
  await page.getByTestId('project-access-input-staging-site_url').fill('https://preview.kore.example.test');
  await page.getByTestId('project-access-save-staging-site_url').click();

  await expect(page.getByTestId('project-access-value-staging-site_url'))
    .toHaveText('https://preview.kore.example.test');
  expect(calls.at(-1).body).toEqual({ environment: 'staging', site_url: 'https://preview.kore.example.test' });
});

test('keeps an invalid URL in edit mode with its field error', {
  tag: ['@outcome:error', ...ADMIN_PROJECT_ACCESS_FIELD_EDIT],
}, async ({ page }) => {
  await setupProjectAccess(page, { patchStatus: 400, patchBody: { site_url: ['Ingresa una URL HTTP válida.'] } });
  await openAccessModal(page);

  await page.getByTestId('project-access-edit-staging-site_url').click();
  await page.getByTestId('project-access-input-staging-site_url').fill('not-a-url');
  await page.getByTestId('project-access-save-staging-site_url').click();

  await expect(page.getByTestId('project-access-field-staging-site_url').getByRole('alert'))
    .toContainText('Ingresa una URL HTTP válida.');
  await expect(page.getByTestId('project-access-input-staging-site_url')).toHaveValue('not-a-url');
});

test('keeps an edited field available after a server failure', {
  tag: ['@outcome:failure', ...ADMIN_PROJECT_ACCESS_FIELD_EDIT],
}, async ({ page }) => {
  await setupProjectAccess(page, { patchStatus: 503, patchBody: { error: 'Access update unavailable.' } });
  await openAccessModal(page);

  await page.getByTestId('project-access-edit-production-admin_username').click();
  await page.getByTestId('project-access-input-production-admin_username').fill('new-operator');
  await page.getByTestId('project-access-save-production-admin_username').click();

  await expect(page.getByText('Access update unavailable.', { exact: true })).toBeVisible();
  await expect(page.getByTestId('project-access-input-production-admin_username')).toHaveValue('new-operator');
});

test('reveals and hides a password only after the user requests it', {
  tag: ['@outcome:success', ...ADMIN_PROJECT_ACCESS_SECRETS],
}, async ({ page }) => {
  await setupProjectAccess(page);
  await openAccessModal(page);

  const reveal = page.getByTestId('project-access-reveal-password-production');
  await reveal.click();
  await expect(page.getByTestId('project-access-password-production')).toContainText('e2e-password-secret');
  await reveal.click();
  await expect(page.getByTestId('project-access-password-production')).not.toContainText('e2e-password-secret');
});

test('copies a hidden password without placing it in the modal', {
  tag: ['@outcome:success', ...ADMIN_PROJECT_ACCESS_SECRETS],
}, async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await setupProjectAccess(page);
  await openAccessModal(page);

  await page.getByTestId('project-access-copy-password-production').click();

  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toBe('e2e-password-secret');
  await expect(page.getByTestId('project-access-modal')).not.toContainText('e2e-password-secret');
});

test('reports a password reveal failure without unmasking the field', {
  tag: ['@outcome:failure', ...ADMIN_PROJECT_ACCESS_SECRETS],
}, async ({ page }) => {
  await setupProjectAccess(page, { revealStatus: 503 });
  await openAccessModal(page);

  await page.getByTestId('project-access-reveal-password-production').click();

  await expect(page.getByText('Secret service unavailable.', { exact: true })).toBeVisible();
  await expect(page.getByTestId('project-access-password-production')).toContainText('••••••••••••');
});

test('adds another project note', {
  tag: ['@outcome:success', ...ADMIN_PROJECT_ACCESS_NOTES],
}, async ({ page }) => {
  const { calls } = await setupProjectAccess(page);
  await openAccessModal(page);

  await page.getByTestId('project-access-add-note').click();
  const form = page.getByTestId('project-access-note-create');
  await form.locator('input').fill('VPN access');
  await form.locator('textarea').fill('Use the operations tailnet');
  await page.getByTestId('project-access-create-note-save').click();

  await expect(page.getByTestId('project-access-note-21')).toContainText('VPN access');
  expect(calls.at(-1).body).toEqual({ title: 'VPN access', content: 'Use the operations tailnet', is_sensitive: false });
});

test('validates a new note before sending it', {
  tag: ['@outcome:error', ...ADMIN_PROJECT_ACCESS_NOTES],
}, async ({ page }) => {
  const { calls } = await setupProjectAccess(page);
  await openAccessModal(page);

  await page.getByTestId('project-access-add-note').click();
  await page.getByTestId('project-access-create-note-save').click();

  await expect(page.getByTestId('project-access-note-create').getByRole('alert')).toHaveCount(2);
  expect(calls.filter((call) => call.apiPath.endsWith('/notes/'))).toHaveLength(0);
});

test('preserves the note draft after the server rejects creation', {
  tag: ['@outcome:failure', ...ADMIN_PROJECT_ACCESS_NOTES],
}, async ({ page }) => {
  await setupProjectAccess(page, { noteStatus: 503 });
  await openAccessModal(page);

  await page.getByTestId('project-access-add-note').click();
  const form = page.getByTestId('project-access-note-create');
  await form.locator('input').fill('Provider access');
  await form.locator('textarea').fill('Credential pending rotation');
  await page.getByTestId('project-access-create-note-save').click();

  await expect(page.getByTestId('project-access-notes-error')).toContainText('Notes service unavailable.');
  await expect(form.locator('textarea')).toHaveValue('Credential pending rotation');
});
