/**
 * E2E tests for platform admin project create flow.
 *
 * @flow:platform-admin-project-create
 * Covers: create project modal render, form validation,
 *         client dropdown, submit success, submit error,
 *         modal close behavior.
 */
import { test, expect } from '../helpers/test.js';
import { mockApi } from '../helpers/api.js';
import { PLATFORM_ADMIN_PROJECT_CREATE } from '../helpers/flow-tags.js';
import {
  setPlatformAuth,
  mockPlatformAdmin,
} from '../helpers/platform-auth.js';

const meResponse = (user) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(user),
});

const mockClients = [
  {
    user_id: 9002,
    first_name: 'Client',
    last_name: 'E2E',
    email: 'client@e2e-test.com',
    company_name: 'ACME Corp',
    is_active: true,
    is_onboarded: true,
  },
];

function setupCreateProjectMocks(page, createResponse = null) {
  return mockApi(page, async ({ apiPath, method }) => {
    if (apiPath === 'accounts/me/' && method === 'GET') return meResponse(mockPlatformAdmin);
    if (apiPath === 'accounts/proposals/' && method === 'GET') {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    if (method === 'GET' && apiPath.startsWith('accounts/projects/')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify([]) };
    }
    if (apiPath === 'accounts/projects/' && method === 'POST') {
      return createResponse ?? {
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 10,
          name: 'New Project',
          description: 'Test project',
          status: 'active',
          progress: 0,
          client_id: 9002,
          client_name: 'Client E2E',
          client_company: 'ACME Corp',
        }),
      };
    }
    if (apiPath.startsWith('accounts/clients')) {
      return { status: 200, contentType: 'application/json', body: JSON.stringify(mockClients) };
    }
    return null;
  });
}

test.describe('Platform Admin Project Create', () => {
  // SPA routes need longer timeout for Vite on-demand compilation on dev server
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await setPlatformAuth(page, { user: mockPlatformAdmin });
  });

  test('opens create project modal with required fields', {
    tag: [...PLATFORM_ADMIN_PROJECT_CREATE, '@role:platform-admin'],
  }, async ({ page }) => {
    await setupCreateProjectMocks(page);
    await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });

    await page.getByRole('button', { name: /nuevo proyecto/i }).click();

    await expect(page.getByRole('heading', { name: 'Nuevo proyecto' })).toBeVisible();
    await expect(page.getByPlaceholder(/plataforma e-commerce/i)).toBeVisible();
    // 'Selecciona un cliente' is a disabled <option> inside select — verify the select exists
    await expect(page.getByRole('combobox').first()).toBeVisible();
  });

  test('create button is disabled when required fields are empty', {
    tag: [...PLATFORM_ADMIN_PROJECT_CREATE, '@role:platform-admin'],
  }, async ({ page }) => {
    await setupCreateProjectMocks(page);
    await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });

    await page.getByRole('button', { name: /nuevo proyecto/i }).click();

    const createBtn = page.getByRole('button', { name: /crear proyecto/i });
    await expect(createBtn).toBeDisabled();
  });

  test('successful project creation closes modal', {
    tag: [...PLATFORM_ADMIN_PROJECT_CREATE, '@role:platform-admin'],
  }, async ({ page }) => {
    await setupCreateProjectMocks(page);
    await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });

    await page.getByRole('button', { name: /nuevo proyecto/i }).click();
    const clientSelect = page.locator('select').filter({ has: page.locator('option[value="9002"]') });
    await expect(clientSelect).toBeVisible({ timeout: 20_000 });
    await page.getByPlaceholder(/plataforma e-commerce/i).fill('New Project');
    await clientSelect.selectOption({ value: '9002' });
    await page.getByRole('button', { name: /crear proyecto/i }).click();

    await expect(page.getByRole('heading', { name: 'Nuevo proyecto' })).not.toBeVisible({ timeout: 5000 });
  });

  // Catches a manual root conflict being hidden or a rejected project being inserted.
  test('server root folder conflict keeps the create modal open', {
    tag: [...PLATFORM_ADMIN_PROJECT_CREATE, '@role:platform-admin', '@outcome:error'],
  }, async ({ page }) => {
    await setupCreateProjectMocks(page, {
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: 'Ya existe una carpeta manual con el nombre del proyecto.',
        code: 'project_root_name_conflict',
        folder_ids: [66],
        paths: ['ProjectApp'],
        reasons: [{ code: 'pinned', resource_type: 'folder', resource_id: 121 }],
        hint: 'Usa create_project con root_folder_id tras revisar preview_folder_migration, o renombra la carpeta existente.',
      }),
    });
    await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });
    await expect(page.getByText('No hay proyectos creados.', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: /nuevo proyecto/i }).click();

    const clientSelect = page.getByRole('combobox').filter({ has: page.locator('option[value="9002"]') });
    await expect(clientSelect).toBeVisible({ timeout: 20_000 });
    await page.getByPlaceholder(/plataforma e-commerce/i).fill('ProjectApp');
    await clientSelect.selectOption({ value: '9002' });
    const createResponse = page.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith('/api/accounts/projects/'));
    await page.getByRole('button', { name: /crear proyecto/i }).click();

    expect((await createResponse).status()).toBe(400);
    await expect(page.getByText('Ya existe una carpeta manual con el nombre del proyecto.', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Nuevo proyecto', exact: true })).toBeVisible();
    await expect(page.getByText('No hay proyectos creados.', { exact: true })).toBeVisible();
    await expect(page.getByTestId(/^project-(row|card)-/)).toHaveCount(0);
  });

  test('cancel button closes modal without submitting', {
    tag: [...PLATFORM_ADMIN_PROJECT_CREATE, '@role:platform-admin'],
  }, async ({ page }) => {
    await setupCreateProjectMocks(page);
    await page.goto('/platform/projects', { waitUntil: 'domcontentloaded' });

    await page.getByRole('button', { name: /nuevo proyecto/i }).click();
    await expect(page.getByRole('heading', { name: 'Nuevo proyecto' })).toBeVisible();

    await page.getByRole('button', { name: /cancelar/i }).click();
    await expect(page.getByRole('heading', { name: 'Nuevo proyecto' })).not.toBeVisible({ timeout: 5000 });
  });
});
