/**
 * Project-scoped access editor in the JWT platform.
 *
 * @flow:platform-project-access-detail
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_PROJECT_ACCESS_DETAIL } from '../helpers/flow-tags.js';
import {
  mockPlatformAdmin,
  mockPlatformClient,
  setPlatformAuth,
} from '../helpers/platform-auth.js';

test.setTimeout(60_000);

const project = {
  id: 1,
  name: 'E-commerce Platform',
  description: 'Full-stack commerce product',
  status: 'active',
  status_label: 'Activo',
  current_state: { id: 2, name: 'Activo', system_key: 'active', operational_effect: 'operating', color: 'emerald' },
  progress: 65,
  client_id: 9002,
  client_name: 'Client E2E',
  client_email: 'client@e2e-test.com',
  client_company: 'ACME Corp',
};

const accessDetail = {
  project: { id: 1, name: project.name, client_name: project.client_name },
  repository_url: 'https://git.example.test/acme/commerce',
  environments: [
    { environment: 'production', label: 'Producción', site_url: 'https://shop.example.test', admin_url: 'https://shop.example.test/admin/', admin_username: 'shop-admin', has_password: true },
    { environment: 'staging', label: 'Staging', site_url: 'https://preview.shop.example.test', admin_url: 'https://preview.shop.example.test/admin/', admin_username: 'preview-admin', has_password: false },
  ],
  notes: [],
  legacy_access: null,
};

const json = (body, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) });

async function setupPlatformAccess(page, { user = mockPlatformAdmin, accessStatus = 200 } = {}) {
  const calls = [];
  let detail = structuredClone(accessDetail);
  await setPlatformAuth(page, { user });
  await mockApi(page, async ({ apiPath, method, route }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return json(user);
    if (apiPath === 'accounts/projects/' && method === 'GET') return json([project]);
    if (apiPath === 'accounts/projects/1/' && method === 'GET') return json(project);
    if (apiPath === 'accounts/projects/1/client-access/' && method === 'GET') return json({ project_id: 1, environments: [] });
    if (apiPath === 'accounts/projects/1/access/client-policy/' && method === 'GET') return json({ detail: 'Policy fixture omitted' }, 503);
    if (apiPath === 'accounts/projects/1/phases/' && method === 'GET') return json([]);
    if (apiPath === 'accounts/projects/1/access/' && method === 'GET') {
      return accessStatus === 200
        ? json(detail)
        : json({ error: 'Platform access service unavailable.' }, accessStatus);
    }
    if (apiPath === 'accounts/projects/1/access/' && method === 'PATCH') {
      const body = route.request().postDataJSON();
      calls.push(body);
      detail = { ...detail, repository_url: body.repository_url };
      return json(detail);
    }
    return null;
  });
  return { calls };
}

async function openFromProjectList(page) {
  await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('project-row-1').click();
  await expect(page).toHaveURL(/\/platform\/projects\/1$/);
  const accessLink = page.getByRole('link', { name: /^(Access|Accesos)$/ });
  await expect(accessLink).toBeVisible({ timeout: 25_000 });
  await accessLink.click();
  await expect(page).toHaveURL(/\/platform\/projects\/1\/access$/);
}

test('admin reaches the scoped access detail through project navigation', {
  tag: ['@outcome:display', ...PLATFORM_PROJECT_ACCESS_DETAIL, '@role:platform-admin'],
}, async ({ page }) => {
  await setupPlatformAccess(page);
  // quality: allow-deep-link (the project list is the authenticated entry surface; the test clicks through both navigation steps)
  await openFromProjectList(page);

  await expect(page.getByTestId('project-access-value-production-site_url'))
    .toHaveText('https://shop.example.test');
  await expect(page.getByTestId('project-access-password-production')).toContainText('••••••••••••');
  await expect(page.getByTestId('project-access-editor').locator('input[type="password"]'))
    .toHaveCount(0);
});

test('admin edits the repository through the platform transport', {
  tag: ['@outcome:success', ...PLATFORM_PROJECT_ACCESS_DETAIL, '@role:platform-admin'],
}, async ({ page }) => {
  const { calls } = await setupPlatformAccess(page);
  await openFromProjectList(page);

  await page.getByTestId('project-access-edit-repository_url').click();
  await page.getByTestId('project-access-input-repository_url').fill('https://git.example.test/acme/commerce-v2');
  await page.getByTestId('project-access-save-repository_url').click();

  await expect(page.getByTestId('project-access-value-repository_url'))
    .toHaveText('https://git.example.test/acme/commerce-v2');
  expect(calls).toEqual([{ repository_url: 'https://git.example.test/acme/commerce-v2' }]);
});

test('shows a recoverable error when the scoped detail fails to load', {
  tag: ['@outcome:failure', ...PLATFORM_PROJECT_ACCESS_DETAIL, '@role:platform-admin'],
}, async ({ page }) => {
  await setupPlatformAccess(page, { accessStatus: 503 });
  await openFromProjectList(page);

  await expect(page.getByTestId('project-access-load-error'))
    .toContainText('Platform access service unavailable.');
  await expect(page.getByTestId('project-access-load-error').getByRole('button')).toBeVisible();
});

test('keeps the client on a limited empty access view', {
  tag: ['@outcome:error', ...PLATFORM_PROJECT_ACCESS_DETAIL, '@role:platform-client'],
}, async ({ page }) => {
  // quality: allow-deep-link (client authorization boundary on the former admin-only route; full navigation is covered by P4 live browser tests)
  await setupPlatformAccess(page, { user: mockPlatformClient });

  await page.goto('/platform/projects/1/access', { waitUntil: 'domcontentloaded' });

  await expect(page.getByTestId('project-client-access')).toContainText(/No (access|hay accesos)/);
  await page.getByTestId('project-client-access').getByRole('button', { name: /Refresh|Actualizar/ }).click();
  await expect(page.getByTestId('project-client-access').getByRole('link')).toHaveCount(0);
  await expect(page).toHaveURL(/\/platform\/projects\/1\/access$/);
  await expect(page.getByTestId('project-access-editor')).toHaveCount(0);
});
